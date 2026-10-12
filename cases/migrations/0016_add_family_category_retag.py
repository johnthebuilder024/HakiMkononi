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
    # Use a single bulk UPDATE per title fragment — much faster than row-by-row
    updated_total = 0
    for frag in FAMILY_TITLE_FRAGMENTS:
        updated = Law.objects.filter(
            category='other',
            title__icontains=frag
        ).update(category='family')
        if updated:
            print(f"  → Re-tagged {updated} '{frag}' sections to 'family'")
            updated_total += updated
    print(f"  → Total re-tagged: {updated_total} law sections")


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
