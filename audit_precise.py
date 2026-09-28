"""
Precise audit — exact section number matching.
Run: python audit_precise.py
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sheria_ai.settings')
django.setup()
from cases.models import Law
import re

def find_exact(title_kw, section_num):
    """Find a section with an exact section number (not substring match)."""
    qs = Law.objects.filter(title__icontains=title_kw)
    for row in qs:
        # Match section number at start of section string
        # e.g. "33." or "33 " or "33A." 
        if re.match(r'^' + re.escape(str(section_num)) + r'[.\s]', row.section.strip()):
            return row
    return None

print("=" * 70)
print("PRECISE SECTION CHECK — CPC (Criminal Procedure Code)")
print("=" * 70)

CPC_CRITICAL = [
    ("21", "How arrest is made"),
    ("24", "No unnecessary restraint"),
    ("25", "Search of arrested person"),
    ("29", "Arrest by police officer without warrant"),
    ("30", "Arrest of vagabonds / habitual robbers"),
    ("31", "Procedure when officer deputes subordinate"),
    ("32", "Refusal to give name and residence"),
    ("33", "Disposal of persons arrested by police officer"),
    ("34", "Arrest by private person"),
    ("36", "Detention of persons arrested without warrant"),
    ("36A", "Remand by court"),
    ("37", "Police to report apprehensions"),
    ("38", "Offence committed in magistrate's presence"),
    ("42", "Assistance to magistrate or police officer"),
    ("89", "Complaint and charge"),
    ("103", "Court may direct security to be taken"),
    ("107", "Notification of substance of warrant"),
    ("108", "Person arrested to be brought before court without delay"),
    ("112", "Procedure on arrest of person outside jurisdiction"),
    ("123", "Bail in certain cases"),
    ("123A", "Exception to right to bail"),
    ("149", "Penalty for non-attendance of witness"),
    ("162", "Inquiry by court as to soundness of mind"),
    ("389", "Power to issue habeas corpus"),
]

missing_cpc = []
for num, desc in CPC_CRITICAL:
    row = find_exact("Criminal Procedure", num)
    if row:
        emb = "✅" if row.embedding_json else "❌ NO EMB"
        print(f"  {emb}  S.{num}  — {row.section[:60]}")
    else:
        print(f"  ❌ MISSING  S.{num}  — {desc}")
        missing_cpc.append((num, desc))

print("\n" + "=" * 70)
print("PRECISE SECTION CHECK — Employment Act 2007")
print("=" * 70)

EMP_CRITICAL = [
    ("1",  "Short title"),
    ("2",  "Interpretation"),
    ("3",  "Application"),
    ("4",  "Prohibition against forced labour"),
    ("5",  "Discrimination in employment"),
    ("6",  "Sexual harassment"),
    ("7",  "Contract of service"),
    ("10", "Employment particulars"),
    ("15", "Informing employees of rights"),
    ("16", "Enforcement"),
    ("17", "Payment of wages"),
    ("18", "When wages due"),
    ("19", "Deduction of wages"),
    ("22", "Power to amend"),
    ("25", "Repayment wrongfully withheld"),
    ("27", "Hours of work"),
    ("28", "Annual leave"),
    ("29", "Maternity leave"),
    ("29A","Pre-adoptive leave"),
    ("30", "Sick leave"),
    ("35", "Termination notice"),
    ("36", "Payment in lieu of notice"),
    ("37", "Conversion casual to term"),
    ("38", "Waiver of notice"),
    ("40", "Redundancy"),
    ("41", "Notification and hearing before termination"),
    ("42", "Termination of probationary contracts"),
    ("43", "Proof of reason for termination"),
    ("44", "Summary dismissal"),
    ("45", "Unfair termination"),
    ("46", "Reasons for termination"),
    ("47", "Complaint of summary dismissal"),
    ("48", "Representation"),
    ("49", "Remedies for wrongful dismissal"),
    ("50", "Courts to be guided"),
    ("51", "Certificate of service"),
    ("60", "Emergencies"),
    ("64", "Penalty for unlawful employment of child"),
    ("66", "Insolvency of employer"),
    ("68", "Debts to which Part applies"),
    ("69", "Limitation on amount payable"),
    ("71", "Complaint to ELRC"),
    ("87", "General penalty"),
]

missing_emp = []
for num, desc in EMP_CRITICAL:
    row = find_exact("Employment", num)
    if row:
        emb = "✅" if row.embedding_json else "❌ NO EMB"
        print(f"  {emb}  S.{num}  — {row.section[:65]}")
    else:
        print(f"  ❌ MISSING  S.{num}  — {desc}")
        missing_emp.append((num, desc))

print("\n" + "=" * 70)
print("CONSTITUTION — MISSING ARTICLES (only 21 loaded, need more)")
print("=" * 70)

CONST_SHOULD_HAVE = [
    ("22", "Application of rights to juristic persons"),
    ("23", "Authority of courts to uphold and enforce Bill of Rights"),
    ("24", "Limitation of rights"),
    ("25", "Fundamental rights that cannot be limited"),
    ("30", "Use of language and participation in cultural life"),
    ("33", "Freedom of expression"),
    ("34", "Freedom and independence of the media"),
    ("35", "Access to information"),
    ("36", "Freedom of association"),
    ("37", "Assembly, demonstration, picketing and petition"),
    ("38", "Political rights"),
    ("39", "Freedom of movement and residence"),
    ("42", "Environment"),
    ("44", "Language and culture"),
    ("46", "Consumer rights"),
    ("48", "Access to justice"),
    ("52", "Interpretation of this Chapter"),
    ("55", "Youth rights"),
    ("58", "State of emergency"),
    ("59", "Kenya National Human Rights Commission"),
]

const_loaded = set()
for row in Law.objects.filter(title='Constitution of Kenya 2010'):
    m = re.match(r'^Article\s+(\d+)', row.section)
    if m:
        const_loaded.add(m.group(1))

missing_const = []
for num, desc in CONST_SHOULD_HAVE:
    if num in const_loaded:
        print(f"  ✅  Article {num} — {desc}")
    else:
        print(f"  ❌ MISSING  Article {num} — {desc}")
        missing_const.append((num, desc))

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  CPC missing     : {len(missing_cpc)} sections")
print(f"  Employment missing: {len(missing_emp)} sections")
print(f"  Constitution missing: {len(missing_const)} articles")
if missing_cpc:
    print(f"\n  Missing CPC: {[n for n,_ in missing_cpc]}")
if missing_emp:
    print(f"\n  Missing Employment: {[n for n,_ in missing_emp]}")
if missing_const:
    print(f"\n  Missing Constitution articles: {[n for n,_ in missing_const]}")

print("\nAudit complete.")
