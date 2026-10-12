"""
load_new_acts.py
----------------
Loads all new PDFs into Supabase then builds embeddings.
Safe to re-run — skips titles already in DB.
Run: python load_new_acts.py
"""
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'sheria_ai.settings'
django.setup()

from cases.pdf_parser import parse_pdf
from cases.rag import build_embeddings_for_all_laws
from cases.models import Law

ACTS = [
    # Banking & mobile money
    ("data/Banking Act.pdf",
     "Banking Act (Cap 488)",
     "other",
     "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/BankingAct_Cap488.pdf"),

    ("data/National Payment System Act 2011.pdf",
     "National Payment System Act 2011 (No. 39 of 2011)",
     "other",
     "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/NationalPaymentSystemsAct__No39of2011.pdf"),

    # Insurance
    ("data/Insurance Act.pdf",
     "Insurance Act (Cap 487)",
     "other",
     "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/InsuranceAct_Cap487.pdf"),

    # Copyright & IP
    ("data/Copyright Act.pdf",
     "Copyright Act (Cap 130)",
     "other",
     "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/CopyrightAct_No12of2001.pdf"),

    ("data/Industrial Property Act.pdf",
     "Industrial Property Act 2001 (No. 3 of 2001)",
     "other",
     "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/IndustrialPropertyAct_No3of2001.pdf"),

    ("data/Trade Marks Act Cap 506.pdf",
     "Trade Marks Act (Cap 506)",
     "other",
     "https://www.jpo.go.jp/e/system/laws/gaikoku/document/index/kenya-e_shouhyou_act.pdf"),

    # Disability
    ("data/Persons with Disabilities Act.pdf",
     "Persons with Disabilities Act 2003 (No. 14 of 2003)",
     "other",
     "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/PersonswithDisabilitiesAct_No14of2003.pdf"),

    # Environment
    ("data/Environmental Management and Coordination Act.pdf",
     "Environmental Management and Coordination Act (Cap 387)",
     "other",
     "https://kenya.eregulations.org/media/emca_1.pdf"),

    # Public procurement
    ("data/Public Procurement and Asset Disposal Act 2015.pdf",
     "Public Procurement and Asset Disposal Act 2015 (No. 33 of 2015)",
     "other",
     "https://new.kenyalaw.org/akn/ke/act/2015/33/eng@2016-05-06/source"),

    # Health
    ("data/Health Act 2017.pdf",
     "Health Act 2017 (No. 21 of 2017)",
     "other",
     "https://new.kenyalaw.org/akn/ke/act/2017/21/eng@2022-07-11/source"),
]

print("=" * 65)
print("  Loading new Acts into Supabase")
print("=" * 65)

total_new = 0
for pdf, title, cat, url in ACTS:
    existing = Law.objects.filter(title=title).count()
    if existing > 0:
        print(f"  SKIP  {title} ({existing} sections already in DB)")
        continue
    if not os.path.exists(pdf):
        print(f"  MISS  {pdf} — file not found, skipping")
        continue
    print(f"  LOAD  {title} ...")
    try:
        count = parse_pdf(pdf_path=pdf, act_title=title, category=cat, source_url=url)
        print(f"        → {count} sections created")
        total_new += count
    except Exception as e:
        print(f"        ✗ ERROR: {e}")

print(f"\n  Total new sections: {total_new}")

if total_new > 0:
    print("\n  Building embeddings for new sections ...")
    build_embeddings_for_all_laws()
    print("  ✅  Done!")
else:
    print("\n  No new sections — all acts already loaded or files missing.")

total = Law.objects.count()
emb   = Law.objects.exclude(embedding_json='').count()
print(f"\n  DB final: {total} sections total, {emb} embedded, {total-emb} missing")
print("=" * 65)
