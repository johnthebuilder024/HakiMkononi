import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sheria_ai.settings')
django.setup()
from cases.models import Law
import re

def check_sections(title, check_nums):
    qs = Law.objects.filter(title=title)
    print(f"\n{'='*60}")
    print(f"{title} — {qs.count()} sections total")
    print(f"{'='*60}")
    for n in check_nums:
        # Match section starting with number
        row = qs.filter(section__iregex=rf'^{n}[.\s]').first()
        if row:
            print(f"  S.{n:3d} ✅  {row.section[:60]}")
            print(f"         content: {row.content[:80]}")
        else:
            print(f"  S.{n:3d} ❌  MISSING")

# Employment Act — check S.1 to S.10 (key early sections)
check_sections("Employment Act 2007", range(1, 11))

# Traffic Act — check S.1 to S.5
check_sections("Traffic Act (Cap 403)", range(1, 6))

# Marriage Act — check S.1 to S.5
check_sections("Marriage Act 2014 (No. 4 of 2014)", range(1, 6))

# Check the really important Wanjiku sections are there
print(f"\n{'='*60}")
print("WANJIKU CRITICAL SECTIONS CHECK")
print(f"{'='*60}")

CRITICAL = [
    ("Employment Act 2007", [35, 36, 40, 41, 44, 45, 46, 47, 49]),
    ("Traffic Act (Cap 403)", [41, 44, 46, 47, 52, 53, 55, 73]),
    ("Marriage Act 2014 (No. 4 of 2014)", [3, 6, 11, 14, 68, 70, 71]),
    ("Children Act 2022 (No. 29 of 2022)", [4, 5, 22, 23, 24, 26, 73, 74]),
    ("Land Act 2012 (No. 6 of 2012)", [2, 3, 6, 7, 24, 97, 119, 157]),
    ("Protection Against Domestic Violence Act 2015 (No. 2 of 2015)", [2, 3, 6, 8, 10, 14, 17]),
    ("Law of Succession Act (Cap 160)", [2, 3, 5, 35, 36, 38, 65, 66, 70]),
]

for title, nums in CRITICAL:
    qs = Law.objects.filter(title=title)
    total = qs.count()
    found = []
    missing = []
    for n in nums:
        if qs.filter(section__iregex=rf'^{n}[.\s]').exists():
            found.append(n)
        else:
            missing.append(n)
    status = "✅" if not missing else f"⚠️  missing: {missing}"
    print(f"  {title[:50]:<50} ({total:3d} sects)  {status}")
