"""
Loads every PDF in data/ that is not yet in the database.
Handles each PDF sequentially with a 90-second timeout per load.
Builds embeddings at the end and prints the full final state.

Run: python load_missing.py
"""
import os, django, subprocess, sys, time
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sheria_ai.settings')
django.setup()

from cases.models import Law
from collections import Counter

# ── Map every PDF filename → (db_title, category, source_url) ─────────────
PDF_MAP = {
    "Children Act 2022.pdf": (
        "Children Act 2022 (No. 29 of 2022)",
        "children",
        "https://new.kenyalaw.org/akn/ke/act/2022/29/eng@2022-07-29",
    ),
    "Community Land Act.pdf": (
        "Community Land Act 2016 (No. 27 of 2016)",
        "land",
        "https://new.kenyalaw.org/akn/ke/act/2016/27/eng@2022-12-31",
    ),
    "Constitution of Kenya.pdf": (
        "Constitution of Kenya 2010",
        "constitution",
        "https://new.kenyalaw.org/akn/ke/act/2010/constitution/eng@2010-09-03",
    ),
    "Consumer Protection Act 2012.pdf": (
        "Consumer Protection Act 2012 (No. 46 of 2012)",
        "consumer",
        "https://new.kenyalaw.org/akn/ke/act/2012/46/eng@2022-12-31",
    ),
    "Criminal Procedure Code.pdf": (
        "Criminal Procedure Code (Cap 75)",
        "criminal_procedure",
        "https://new.kenyalaw.org/akn/ke/act/1930/11/eng@2023-12-11",
    ),
    "Distress for Rent Act.pdf": (
        "Distress for Rent Act (Cap 293)",
        "landlord_tenant",
        "https://new.kenyalaw.org/akn/ke/act/1951/293/eng@2022-12-31",
    ),
    "Employment Act.pdf": (
        "Employment Act 2007",
        "employment",
        "https://new.kenyalaw.org/akn/ke/act/2007/11/eng@2024-03-22",
    ),
    "Fair Administrative Action Act 2015.pdf": (
        "Fair Administrative Action Act 2015 (No. 4 of 2015)",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/2015/4/eng@2022-12-31",
    ),
    "Land Act 2012.pdf": (
        "Land Act 2012 (No. 6 of 2012)",
        "land",
        "https://new.kenyalaw.org/akn/ke/act/2012/6/eng@2022-12-31",
    ),
    "Land Control Act.pdf": (
        "Land Control Act (Cap 302)",
        "land",
        "https://new.kenyalaw.org/akn/ke/act/1967/302/eng@2022-12-31",
    ),
    "Land Registration Act 2012.pdf": (
        "Land Registration Act 2012 (No. 3 of 2012)",
        "land",
        "https://new.kenyalaw.org/akn/ke/act/2012/3/eng@2022-12-31",
    ),
    "Landlord and Tenant (Shops Hotels and Catering Establishments) Act.pdf": (
        "Landlord and Tenant Act (Cap 301)",
        "landlord_tenant",
        "https://new.kenyalaw.org/akn/ke/act/1965/301/eng@2022-12-31",
    ),
    "Law of Succession Act.pdf": (
        "Law of Succession Act (Cap 160)",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/1972/14/eng@2022-12-31",
    ),
    "Marriage Act 2014.pdf": (
        "Marriage Act 2014 (No. 4 of 2014)",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/2014/4/eng@2022-12-31",
    ),
    "Matrimonial Property Act 2013.pdf": (
        "Matrimonial Property Act 2013 (No. 49 of 2013)",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/2013/49/eng@2022-12-31",
    ),
    "Protection Against Domestic Violence Act 2015.pdf": (
        "Protection Against Domestic Violence Act 2015 (No. 2 of 2015)",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/2015/2/eng@2022-12-31",
    ),
    "Rent Restriction Act.pdf": (
        "Rent Restriction Act (Cap 296)",
        "landlord_tenant",
        "https://new.kenyalaw.org/akn/ke/act/1959/296/eng@2022-12-31",
    ),
    "Sexual Offences Act 2006.pdf": (
        "Sexual Offences Act 2006 (No. 3 of 2006)",
        "criminal_procedure",
        "https://new.kenyalaw.org/akn/ke/act/2006/3/eng@2024-04-26",
    ),
    "The Marriage (Customary Marriage) Rules.pdf": (
        "The Marriage (Customary Marriage) Rules",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/2014/4/eng@2022-12-31",
    ),
    "The Marriage (General) Rules.pdf": (
        "The Marriage (General) Rules",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/2014/4/eng@2022-12-31",
    ),
    "The Marriage (Hindu Marriage) Rules.pdf": (
        "The Marriage (Hindu Marriage) Rules",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/2014/4/eng@2022-12-31",
    ),
    "The Marriage (Matrimonial Proceedings) Rules.pdf": (
        "The Marriage (Matrimonial Proceedings) Rules",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/2014/4/eng@2022-12-31",
    ),
    "The Marriage (Muslim Marriage) Rules.pdf": (
        "The Marriage (Muslim Marriage) Rules",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/2014/4/eng@2022-12-31",
    ),
    "Traffic Act Cap 403.pdf": (
        "Traffic Act (Cap 403)",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/1953/39/eng@2024-04-26",
    ),
    "Widows and Childrens Pensions Act.pdf": (
        "Widows and Children's Pensions Act (Cap 195)",
        "other",
        "https://new.kenyalaw.org/akn/ke/act/1968/195/eng@2022-12-31",
    ),
}

DATA_DIR = "data"

print("=" * 65)
print("LOADING ALL MISSING PDFs INTO DATABASE")
print("=" * 65)

loaded_count = 0
skipped_count = 0
failed = []

for pdf_file, (title, category, url) in PDF_MAP.items():
    pdf_path = os.path.join(DATA_DIR, pdf_file)

    # Skip if PDF not on disk
    if not os.path.exists(pdf_path):
        print(f"  ⚠️  NO FILE   : {pdf_file}")
        continue

    # Skip if already in DB with sections
    existing = Law.objects.filter(title=title).count()
    if existing > 0:
        print(f"  ✅ SKIP      : {title} ({existing} sections already)")
        skipped_count += 1
        continue

    print(f"\n  📖 LOADING   : {title}")
    t0 = time.time()

    try:
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
            timeout=120,   # 2-minute hard timeout per PDF
        )
        elapsed = int(time.time() - t0)
        output = result.stdout + result.stderr
        created = 0
        for line in output.splitlines():
            if "Created:" in line or "Found" in line:
                print(f"     {line.strip()}")
            if "Created:" in line:
                try:
                    created = int(line.split("Created:")[1].split(",")[0].strip())
                except Exception:
                    pass

        if result.returncode != 0:
            print(f"     ❌ returncode={result.returncode}  {result.stderr[:80]}")
            failed.append(pdf_file)
        else:
            actual = Law.objects.filter(title=title).count()
            print(f"     ✅ Done in {elapsed}s — {actual} sections in DB")
            loaded_count += 1

    except subprocess.TimeoutExpired:
        print(f"     ❌ TIMEOUT after 120s — skipping")
        failed.append(pdf_file)

print()
print("=" * 65)
print(f"Load phase done — {loaded_count} loaded, {skipped_count} skipped, {len(failed)} failed")
if failed:
    print(f"  Failed: {failed}")

# ── Build embeddings for any section without one ─────────────────────────
missing_emb = Law.objects.filter(embedding_json="").count()
if missing_emb > 0:
    print(f"\n{'='*65}")
    print(f"Building embeddings for {missing_emb} sections...")
    print("=" * 65)
    subprocess.run(
        [sys.executable, "manage.py", "build_embeddings"],
        cwd=os.getcwd(),
    )
else:
    print("\nAll sections already have embeddings — skipping build step.")

# ── Final verification ────────────────────────────────────────────────────
print()
print("=" * 65)
counts = Counter(Law.objects.values_list('title', flat=True))
total  = Law.objects.count()
emb    = Law.objects.exclude(embedding_json="").count()
no_emb = total - emb
print(f"FINAL DATABASE STATE")
print(f"  Total sections   : {total}")
print(f"  With embeddings  : {emb}")
print(f"  Missing embeddings: {no_emb}")
print("=" * 65)
for t, c in sorted(counts.items()):
    e = Law.objects.filter(title=t).exclude(embedding_json="").count()
    flag = "✅" if e == c else f"⚠️  ({e}/{c} emb)"
    print(f"  {flag}  {c:4d}  {t}")
print("=" * 65)
if no_emb > 0:
    print(f"\n⚠️  {no_emb} sections still missing embeddings — run: python manage.py build_embeddings")
else:
    print("\n✅ All sections have embeddings. Database is fully ready.")
