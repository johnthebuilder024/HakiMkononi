"""
Full audit of law sections in the database.
Run: python audit_laws.py

Checks:
1. How many sections per act
2. Which sections are present / missing vs the PDF
3. Embedding coverage
4. Sample content to verify accuracy
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sheria_ai.settings')
django.setup()

from cases.models import Law
from collections import Counter

print("=" * 70)
print("HAKIKONONI — LAW DATABASE AUDIT")
print("=" * 70)

all_laws = Law.objects.all().order_by('title', 'section')
total = all_laws.count()
with_embeddings = Law.objects.exclude(embedding_json='').count()

print(f"\nTOTAL SECTIONS IN DB : {total}")
print(f"WITH EMBEDDINGS      : {with_embeddings}")
print(f"MISSING EMBEDDINGS   : {total - with_embeddings}")

# ── Per-act breakdown ─────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SECTIONS PER ACT")
print("=" * 70)
titles = Counter(Law.objects.values_list('title', flat=True))
for title, count in sorted(titles.items()):
    emb = Law.objects.filter(title=title).exclude(embedding_json='').count()
    print(f"  {count:4d} sections  ({emb:4d} with embeddings)  {title}")

# ── Constitution: list all sections ──────────────────────────────────────
print("\n" + "=" * 70)
print("CONSTITUTION OF KENYA 2010 — ALL SECTIONS")
print("=" * 70)
const = Law.objects.filter(title='Constitution of Kenya 2010').order_by('section')
if not const.exists():
    # Try alternate title
    const = Law.objects.filter(title__icontains='constitution').order_by('section')
for r in const:
    print(f"  {r.section[:80]}")

# ── Employment Act: list all sections ────────────────────────────────────
print("\n" + "=" * 70)
print("EMPLOYMENT ACT 2007 — ALL SECTIONS")
print("=" * 70)
emp = Law.objects.filter(title__icontains='employment').order_by('section')
for r in emp:
    print(f"  {r.section[:80]}")

# ── Criminal Procedure Code: section count + sample ──────────────────────
print("\n" + "=" * 70)
print("CRIMINAL PROCEDURE CODE — SECTION COUNT & RANGE")
print("=" * 70)
cpc = Law.objects.filter(title__icontains='Criminal Procedure').order_by('pk')
print(f"  Total: {cpc.count()} sections")
print(f"  First 10:")
for r in cpc[:10]:
    print(f"    {r.section[:80]}")
print(f"  Last 10:")
for r in cpc.order_by('-pk')[:10]:
    print(f"    {r.section[:80]}")

# ── Key sections check ────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("KEY SECTIONS CHECK — Must-have for Wanjiku")
print("=" * 70)

KEY_SECTIONS = [
    # Constitution
    ("Constitution", "Article 27"),   # equality
    ("Constitution", "Article 28"),   # dignity
    ("Constitution", "Article 29"),   # freedom & security
    ("Constitution", "Article 40"),   # property rights
    ("Constitution", "Article 41"),   # labour rights
    ("Constitution", "Article 43"),   # economic rights
    ("Constitution", "Article 45"),   # family
    ("Constitution", "Article 47"),   # fair admin
    ("Constitution", "Article 49"),   # arrested persons ← critical
    ("Constitution", "Article 50"),   # fair hearing
    ("Constitution", "Article 51"),   # detained persons
    ("Constitution", "Article 53"),   # children
    # Employment Act
    ("Employment", "35"),   # termination notice
    ("Employment", "36"),   # payment in lieu
    ("Employment", "38"),   # waiver of notice
    ("Employment", "41"),   # notification before termination
    ("Employment", "45"),   # unfair termination ← critical
    ("Employment", "49"),   # remedies
    ("Employment", "68"),   # wage debts
    # CPC
    ("Criminal Procedure", "29"),    # arrest without warrant
    ("Criminal Procedure", "33"),    # disposal of arrested person
    ("Criminal Procedure", "36"),    # 24-hour rule
    ("Criminal Procedure", "36A"),   # remand by court ← 2014 addition
    ("Criminal Procedure", "49"),    # summons procedure
    ("Criminal Procedure", "123"),   # bail
    ("Criminal Procedure", "123A"),  # bail exceptions
]

for act_kw, section_kw in KEY_SECTIONS:
    match = Law.objects.filter(
        title__icontains=act_kw,
        section__icontains=section_kw
    ).first()
    if match:
        has_emb = bool(match.embedding_json)
        emb_mark = "✅ emb" if has_emb else "⚠️  NO EMB"
        print(f"  ✅ FOUND    [{emb_mark}]  {match.title[:30]} — {match.section[:60]}")
    else:
        print(f"  ❌ MISSING              [{act_kw}] — section containing '{section_kw}'")

# ── Content quality sample ────────────────────────────────────────────────
print("\n" + "=" * 70)
print("CONTENT QUALITY SAMPLE — Article 49 (arrest rights)")
print("=" * 70)
art49 = Law.objects.filter(
    title__icontains='constitution',
    section__icontains='49'
).exclude(section__icontains='Summons').first()
if art49:
    print(f"Section : {art49.section}")
    print(f"Content : {art49.content[:500]}")
    print(f"Source  : {art49.source_url}")
else:
    print("  ❌ Article 49 not found")

print("\n" + "=" * 70)
print("CONTENT QUALITY SAMPLE — Employment Act S.45 (unfair termination)")
print("=" * 70)
s45 = Law.objects.filter(
    title__icontains='employment',
    section__icontains='45'
).first()
if s45:
    print(f"Section : {s45.section}")
    print(f"Content : {s45.content[:500]}")
else:
    print("  ❌ Section 45 not found")

print("\nAudit complete.")
