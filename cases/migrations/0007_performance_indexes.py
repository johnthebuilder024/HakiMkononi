"""
0007_performance_indexes.py

Adds DB indexes to the most-queried fields:

  cases_law
    - category          → used in every RAG search for topic filtering
    - embedding_notempty → partial index for sections that have embeddings

  cases_whatsappuser
    - phone             → looked up on every WhatsApp/Telegram message

  cases_answerjob
    - status            → polled constantly by the frontend
    - (id, status)      → composite for the common pk + status check

These are read-only performance indexes — no data changes, fully reversible.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cases', '0006_alter_law_section'),
    ]

    operations = [

        # ── cases_law ─────────────────────────────────────────────────────────
        migrations.AddIndex(
            model_name='law',
            index=models.Index(fields=['category'], name='law_category_idx'),
        ),

        # ── cases_whatsappuser ────────────────────────────────────────────────
        migrations.AddIndex(
            model_name='whatsappuser',
            index=models.Index(fields=['phone'], name='whatsappuser_phone_idx'),
        ),

        # ── cases_answerjob ───────────────────────────────────────────────────
        migrations.AddIndex(
            model_name='answerjob',
            index=models.Index(fields=['status'], name='answerjob_status_idx'),
        ),
        migrations.AddIndex(
            model_name='answerjob',
            index=models.Index(fields=['id', 'status'], name='answerjob_id_status_idx'),
        ),
    ]
