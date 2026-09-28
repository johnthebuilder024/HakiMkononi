"""Full law DB audit. Run: python check_law2.py"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sheria_ai.settings')
django.setup()

from cases.models import Law
from collections import Counter

print("=" * 60)
print("ALL LAW TITLES IN DB")
print("=" * 60)
titles = Law.objects.values_list('title', flat=True)
counts = Counter(titles)
for title, count in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {count:4d}  {title}")

print()
print(f"TOTAL SECTIONS: {Law.objects.count()}")
print()

print("=" * 60)
print("FIRST 5 CONSTITUTION SECTIONS")
print("=" * 60)
for r in Law.objects.filter(title__icontains='constitution').order_by('pk')[:5]:
    print(f"  section={r.section}")
    print(f"  content={r.content[:150]}")
    print()
