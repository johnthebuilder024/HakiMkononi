"""Check what law sections we have for arrest rights. Run: python check_law.py"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sheria_ai.settings')
django.setup()

from cases.models import Law

print("=" * 60)
print("CONSTITUTION SECTIONS LOADED")
print("=" * 60)
const = Law.objects.filter(title__icontains='constitution').order_by('section')
print(f"Total constitution sections: {const.count()}")
for r in const[:30]:
    print(f"  pk={r.pk}  section={r.section[:60]}")

print()
print("=" * 60)
print("SEARCHING FOR ARTICLE 49 / ARREST RIGHTS")
print("=" * 60)
art49 = Law.objects.filter(section__icontains='49')
for r in art49[:10]:
    print(f"  [{r.title}] {r.section}")
    print(f"    {r.content[:100]}")

print()
print("=" * 60)
print("SEARCHING FOR 'arrest' IN CONTENT")
print("=" * 60)
arrest = Law.objects.filter(content__icontains='arrested without a warrant')
print(f"Sections mentioning 'arrested without a warrant': {arrest.count()}")
for r in arrest[:5]:
    print(f"  [{r.title}] {r.section}")
