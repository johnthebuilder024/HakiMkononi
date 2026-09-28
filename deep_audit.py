"""
Deep audit — for every act in the DB, compare what we have
against what the PDF actually contains (first 8 pages sample).
Flags: missing early sections, empty content, wrong text.

Run: python deep_audit.py
"""
import os, re, django, pdfplumber
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sheria_ai.settings')
django.setup()
from cases.models import Law

DATA_DIR = "data"
SECTION_RE = re.compile(r'^(\d+[A-Z]?)\.\s+[A-Z]', re.MULTILINE)

# Map DB title -> PDF filename
ACTS = {
    "Children Act 2022 (No. 29 of 2022)":                          "Children Act 2022.pdf",
    "Community Land Act 2016 (No. 27 of 2016)":                    "Community Land Act.pdf",
    "Constitution of Kenya 2010":                                   "Constitution of Kenya.pdf",
    "Consumer Protection Act 2012 (No. 46 of 2012)":               "Consumer Protection Act 2012.pdf",
    "Criminal Procedure Code (Cap 75)":                             "Criminal Procedure Code.pdf",
    "Distress for Rent Act (Cap 293)":                              "Distress for Rent Act.pdf",
    "Employment Act 2007":                                          "Employment Act.pdf",
    "Fair Administrative Action Act 2015 (No. 4 of 2015)":         "Fair Administrative Action Act 2015.pdf",
    "Land Act 2012 (No. 6 of 2012)":                               "Land Act 2012.pdf",
    "Land Control Act (Cap 302)":                                   "Land Control Act.pdf",
    "Land Registration Act 2012 (No. 3 of 2012)":                  "Land Registration Act 2012.pdf",
    "Landlord and Tenant Act (Cap 301)":                            "Landlord and Tenant (Shops Hotels and Catering Establishments) Act.pdf",
    "Law of Succession Act (Cap 160)":                              "Law of Succession Act.pdf",
    "Marriage Act 2014 (No. 4 of 2014)":                           "Marriage Act 2014.pdf",
    "Matrimonial Property Act 2013 (No. 49 of 2013)":              "Matrimonial Property Act 2013.pdf",
    "Protection Against Domestic Violence Act 2015 (No. 2 of 2015)": "Protection Against Domestic Violence Act 2015.pdf",
    "Rent Restriction Act (Cap 296)":                               "Rent Restriction Act.pdf",
    "Sexual Offences Act 2006 (No. 3 of 2006)":                    "Sexual Offences Act 2006.pdf",
    "The Marriage (Customary Marriage) Rules":                      "The Marriage (Customary Marriage) Rules.pdf",
    "The Marriage (General) Rules":                                 "The Marriage (General) Rules.pdf",
    "The Marriage (Hindu Marriage) Rules":                          "The Marriage (Hindu Marriage) Rules.pdf",
    "The Marriage (Matrimonial Proceedings) Rules":                 "The Marriage (Matrimonial Proceedings) Rules.pdf",
    "The Marriage (Muslim Marriage) Rules":                         "The Marriage (Muslim Marriage) Rules.pdf",
    "Traffic Act (Cap 403)":                                        "Traffic Act Cap 403.pdf",
    "Widows and Children's Pensions Act (Cap 195)":                 "Widows and Childrens Pensions Act.pdf",
}

print("=" * 75)
print("DEEP DATABASE AUDIT")
print("=" * 75)
print(f"{'ACT':<50} {'PDF_S':>5}  {'DB_S':>5}  {'EMB':>4}  {'EARLY':>5}  STATUS")
print("-" * 75)

issues = []
all_ok = []

for title, pdf_file in sorted(ACTS.items()):
    pdf_path = os.path.join(DATA_DIR, pdf_file)

    # DB stats
    db_sections  = Law.objects.filter(title=title).count()
    db_with_emb  = Law.objects.filter(title=title).exclude(embedding_json="").count()
    db_empty_content = Law.objects.filter(title=title, content="").count()

    # Check early sections exist (S.1, S.2, S.3)
    has_s1 = Law.objects.filter(title=title, section__regex=r'^1\.').exists()
    has_s2 = Law.objects.filter(title=title, section__regex=r'^2\.').exists()
    early_ok = "✅" if (has_s1 and has_s2) else "❌"

    # PDF section count (first 8 pages only — fast)
    pdf_sects = 0
    if os.path.exists(pdf_path):
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for pg in pdf.pages[:8]:
                    text += (pg.extract_text() or "") + "\n"
                pdf_sects = len(SECTION_RE.findall(text))
        except Exception:
            pdf_sects = -1

    # Embedding check
    emb_ok = "✅" if db_with_emb == db_sections else f"❌{db_with_emb}"

    # Content quality — sample first section
    first = Law.objects.filter(title=title).order_by("pk").first()
    content_len = len(first.content) if first else 0

    # Overall verdict
    problems = []
    if db_sections == 0:
        problems.append("NO SECTIONS IN DB")
    if db_with_emb < db_sections:
        problems.append(f"{db_sections - db_with_emb} missing embeddings")
    if db_empty_content > 0:
        problems.append(f"{db_empty_content} empty content")
    if early_ok == "❌":
        problems.append("missing S.1/S.2")
    if content_len < 50 and db_sections > 0:
        problems.append(f"content too short ({content_len} chars)")

    status = "✅ OK" if not problems else "⚠️  " + " | ".join(problems)

    short_title = title[:48]
    print(f"{short_title:<50} {pdf_sects:>5}  {db_sections:>5}  {emb_ok:>4}  {early_ok:>5}  {status}")

    if problems:
        issues.append((title, problems))
    else:
        all_ok.append(title)

print()
print("=" * 75)
print(f"✅ All good : {len(all_ok)}")
print(f"⚠️  Issues  : {len(issues)}")
if issues:
    print()
    print("ISSUES TO FIX:")
    for title, probs in issues:
        print(f"  {title}")
        for p in probs:
            print(f"    → {p}")

# Extra: check for sections with very short content
print()
print("=" * 75)
print("CONTENT QUALITY CHECK — sections with < 50 chars content:")
short = Law.objects.filter(content__regex=r'^.{0,49}$').exclude(content="")
if short.count() > 0:
    for s in short[:10]:
        print(f"  [{s.title[:35]}] {s.section[:40]} → '{s.content[:60]}'")
    if short.count() > 10:
        print(f"  ... and {short.count()-10} more")
else:
    print("  None — all sections have substantial content ✅")
