"""
Loads all new law PDFs into the database in one shot.
Run: python load_all_laws.py
"""
import os
import django
import subprocess
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sheria_ai.settings')
django.setup()

from cases.models import Law

LAWS = [
    # (pdf_filename, title_in_db, category, source_url)
    (
        "Marriage Act 2014.pdf",
        "Marriage Act 2014 (No. 4 of 2014)",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/2014/4/eng@2022-12-31",
    ),
    (
        "Matrimonial Property Act 2013.pdf",
        "Matrimonial Property Act 2013 (No. 49 of 2013)",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/2013/49/eng@2022-12-31",
    ),
    (
        "Law of Succession Act.pdf",
        "Law of Succession Act (Cap 160)",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/1972/14/eng@2022-12-31",
    ),
    # Children Act 2022 skipped — PDF too large/complex, load manually later
    (
        "Protection Against Domestic Violence Act 2015.pdf",
        "Protection Against Domestic Violence Act 2015 (No. 2 of 2015)",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/2015/2/eng@2022-12-31",
    ),
    (
        "Sexual Offences Act 2006.pdf",
        "Sexual Offences Act 2006 (No. 3 of 2006)",
        "criminal_procedure",
        "https://new.kenyalaw.org/akn/ke/act/2006/3/eng@2024-04-26",
    ),
    (
        "Consumer Protection Act 2012.pdf",
        "Consumer Protection Act 2012 (No. 46 of 2012)",
        "consumer",
        "https://new.kenyalaw.org/akn/ke/act/2012/46/eng@2022-12-31",
    ),
    (
        "Land Act 2012.pdf",
        "Land Act 2012 (No. 6 of 2012)",
        "land",
        "https://new.kenyalaw.org/akn/ke/act/2012/6/eng@2022-12-31",
    ),
    (
        "Land Registration Act 2012.pdf",
        "Land Registration Act 2012 (No. 3 of 2012)",
        "land",
        "https://new.kenyalaw.org/akn/ke/act/2012/3/eng@2022-12-31",
    ),
    (
        "Traffic Act Cap 403.pdf",
        "Traffic Act (Cap 403)",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/1953/39/eng@2024-04-26",
    ),
    (
        "Fair Administrative Action Act 2015.pdf",
        "Fair Administrative Action Act 2015 (No. 4 of 2015)",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/2015/4/eng@2022-12-31",
    ),
]

print("=" * 65)
print("LOADING ALL NEW LAWS INTO DATABASE")
print("=" * 65)

for pdf_file, title, category, url in LAWS:
    pdf_path = os.path.join("data", pdf_file)

    if not os.path.exists(pdf_path):
        print(f"\n⚠️  SKIP (no PDF): {pdf_file}")
        continue

    if Law.objects.filter(title=title).exists():
        count = Law.objects.filter(title=title).count()
        print(f"\n✅ SKIP (already in DB, {count} sections): {title}")
        continue

    print(f"\n📖 Loading: {title}")

    result = subprocess.run(
        [
            sys.executable, "manage.py", "load_pdf",
            "--pdf", pdf_path,
            "--title", title,
            "--category", category,
            "--url", url,
        ],
        capture_output=True,
        text=True,
        cwd=os.getcwd(),
        timeout=120,
    )

    output = result.stdout + result.stderr
    for line in output.splitlines():
        if any(k in line for k in ["Created:", "Found", "Done", "Error", "error"]):
            print(f"   {line.strip()}")

    count = Law.objects.filter(title=title).count()
    print(f"   ✅ {count} sections in DB")

print()
print("=" * 65)
print("Building embeddings for new sections...")
print("=" * 65)

subprocess.run(
    [sys.executable, "manage.py", "build_embeddings"],
    cwd=os.getcwd(),
)

# Final count
from collections import Counter
counts = Counter(Law.objects.values_list('title', flat=True))
total = Law.objects.count()
emb   = Law.objects.exclude(embedding_json='').count()

print()
print("=" * 65)
print(f"FINAL STATE — {total} sections, {emb} with embeddings")
print("=" * 65)
for t, c in sorted(counts.items()):
    print(f"  {c:4d}  {t}")
