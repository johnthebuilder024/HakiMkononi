"""
Migration 0016 — Add 'family' to Law.CATEGORY_CHOICES and re-tag existing laws.

Laws currently stored as 'other' that belong to the family/marriage/domestic
violence topic are re-tagged to the new 'family' category so the RAG can
boost them correctly.

No schema change is needed — CATEGORY_CHOICES is a Python-level validation
only; the DB column is a plain VARCHAR(50).
"""

from django.db import migrations

# Acts that belong to the 'family' category — matched by title substring (lowercase)
FAMILY_TITLE_FRAGMENTS = [
    'marriage',
    'matrimonial',
    'protection against domestic violence',
    'domestic violence',
    'widows and children',
    'widows',
    'divorce',
]


def retag_family_laws(apps, schema_editor):
    Law = apps.get_model('cases', 'Law')
    updated = 0
    for law in Law.objects.filter(category='other'):
        title_lower = law.title.lower()
        if any(frag in title_lower for frag in FAMILY_TITLE_FRAGMENTS):
            law.category = 'family'
            law.save(update_fields=['category'])
            updated += 1
    print(f"  → Re-tagged {updated} law sections to 'family' category")


def undo_retag(apps, schema_editor):
    Law = apps.get_model('cases', 'Law')
    Law.objects.filter(category='family').update(category='other')


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0015_add_query_review_fields'),
    ]

    operations = [
        migrations.RunPython(retag_family_laws, reverse_code=undo_retag),
    ]
