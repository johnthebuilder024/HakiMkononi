"""
load_cybercrime_acts.py
-----------------------
Loads the Computer Misuse and Cybercrimes Act (2018 + 2025 Amendment)
into the database and builds embeddings for the new sections.

Run from the project root:
    python load_cybercrime_acts.py

This is safe to re-run — it skips titles already in the database.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sheria_ai.settings')
django.setup()

from cases.pdf_parser import parse_pdf
from cases.rag import build_embeddings_for_all_laws
from cases.models import Law

ACTS = [
    {
        "pdf":      "data/Computer Misuse and Cybercrimes.pdf",
        "title":    "Computer Misuse and Cybercrimes Act 2018",
        "category": "fraud",
        "url":      "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/ComputerMisuseAndCybercrimesAct_No5of2018.pdf",
    },
    {
        "pdf":      "data/Computer Misuse and Cybercrimes (Amendment) Act 2025.pdf",
        "title":    "Computer Misuse and Cybercrimes (Amendment) Act 2025",
        "category": "fraud",
        "url":      "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/ComputerMisuseAndCybercrimesAmendmentAct2025.pdf",
    },
]

print("=" * 60)
print("  Loading Computer Misuse & Cybercrimes Acts")
print("=" * 60)

total_new = 0
for act in ACTS:
    already = Law.objects.filter(title=act["title"]).count()
    if already > 0:
        print(f"\n[SKIP] '{act['title']}' — {already} sections already in DB.")
        continue

    print(f"\n[LOADING] {act['title']} ...")
    if not os.path.exists(act["pdf"]):
        print(f"  ✗ PDF not found: {act['pdf']}")
        print(f"    Make sure the file is in the data/ folder and try again.")
        continue

    count = parse_pdf(
        pdf_path=act["pdf"],
        act_title=act["title"],
        category=act["category"],
        source_url=act["url"],
    )
    print(f"  ✓ Created {count} sections.")
    total_new += count

if total_new == 0:
    print("\nNo new sections added — both Acts may already be in the database.")
    fraud_count = Law.objects.filter(category="fraud").count()
    print(f"Current fraud-category sections in DB: {fraud_count}")
    if fraud_count > 0:
        print("\nSections already loaded:")
        for law in Law.objects.filter(category="fraud").values("title").distinct():
            print(f"  - {law['title']}")
else:
    print(f"\n{total_new} new sections added. Building embeddings now...")
    print("(This may take 2-5 minutes — do not close the window)")
    build_embeddings_for_all_laws()
    print("\n✅  Done! Computer Misuse Act is now fully embedded.")
    fraud_count = Law.objects.filter(category="fraud").count()
    print(f"Total fraud-category sections in DB: {fraud_count}")

print("\n" + "=" * 60)
