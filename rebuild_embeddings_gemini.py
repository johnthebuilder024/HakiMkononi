"""
rebuild_embeddings_gemini.py
-----------------------------
Re-embeds all law sections in Supabase using Google Gemini embedding-001 (3072-dim).
Uses a raw SQL length check to avoid downloading huge embedding vectors during scan.

Run:
    python rebuild_embeddings_gemini.py
"""

import os
import sys
import json
import time
import requests
from dotenv import load_dotenv

# Load .env FIRST
load_dotenv(override=True)

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sheria_ai.settings")
import django
django.setup()

from cases.models import Law
from django.db import connection

# ── Config ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={GEMINI_API_KEY}"
SLEEP_BETWEEN = 1.5   # 1.5s between calls = ~40 RPM

if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY not set in .env")
    sys.exit(1)

print(f"✅ Gemini key: {GEMINI_API_KEY[:20]}...")
print(f"✅ Django + Supabase ready")


def embed_text(text: str) -> list:
    resp = requests.post(
        EMBED_URL,
        headers={"Content-Type": "application/json"},
        json={
            "model": "models/gemini-embedding-001",
            "content": {"parts": [{"text": text[:2048]}]},
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]


# ── Smart scan: use SQL char_length to find short/missing embeddings ──────────
# 3072-dim vector JSON is ~24,000 chars. Old 384-dim is ~3,000 chars.
# Empty is 0. We only re-embed if char_length < 10000 (catches empty + 384-dim).
print("\nScanning via SQL (fast — no data download)...")
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT id FROM cases_law
        WHERE char_length(embedding_json) < 10000
        ORDER BY id
    """)
    rows = cursor.fetchall()

ids_to_process = [r[0] for r in rows]
total_all = Law.objects.count()
total_to_do = len(ids_to_process)
already_done = total_all - total_to_do

print(f"Total sections : {total_all}")
print(f"Already 3072-dim: {already_done}")
print(f"Need embedding : {total_to_do}")

if total_to_do == 0:
    print("\n✅ All embeddings already up to date!")
    sys.exit(0)

est_mins = int(total_to_do * SLEEP_BETWEEN / 60)
print(f"Estimated time : ~{est_mins} minutes\n")

# ── Main embedding loop ───────────────────────────────────────────────────────
done = 0
errors = 0
start_time = time.time()
CHUNK = 20  # fetch 20 rows at a time (only title/section/content — no embedding)

for i in range(0, total_to_do, CHUNK):
    chunk_ids = ids_to_process[i:i + CHUNK]

    # Fetch only the fields we need — NOT embedding_json (huge)
    try:
        laws = list(Law.objects.filter(id__in=chunk_ids).only('id', 'title', 'section', 'content'))
    except Exception as e:
        print(f"  DB fetch error: {e}, reconnecting...")
        connection.close()
        time.sleep(5)
        laws = list(Law.objects.filter(id__in=chunk_ids).only('id', 'title', 'section', 'content'))

    for law in laws:
        text = f"{law.title} {law.section}: {law.content}"

        try:
            vector = embed_text(text)
            # Save only embedding_json — don't touch other fields
            Law.objects.filter(pk=law.pk).update(
                embedding_json=json.dumps(vector)
            )
            done += 1

            if done % 50 == 0 or done == total_to_do:
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 1
                remaining = int((total_to_do - done) / rate)
                print(f"  [{done}/{total_to_do}] ✅  {law.title[:45]}  — {remaining}s left")

            time.sleep(SLEEP_BETWEEN)

        except Exception as e:
            err_str = str(e)
            if "429" in err_str:
                print(f"  ⏳ Rate limit — waiting 60s...")
                time.sleep(60)
                try:
                    vector = embed_text(text)
                    Law.objects.filter(pk=law.pk).update(embedding_json=json.dumps(vector))
                    done += 1
                    print(f"  [{done}/{total_to_do}] ✅  Retried OK: {law.title[:40]}")
                    time.sleep(SLEEP_BETWEEN)
                except Exception as e2:
                    errors += 1
                    print(f"  ❌ Retry failed [{errors}]: {e2}")
            else:
                errors += 1
                print(f"  ❌ Error [{errors}]: {law.title[:40]} — {e}")
                time.sleep(2)

# ── Summary ───────────────────────────────────────────────────────────────────
elapsed = time.time() - start_time
print(f"\n{'='*55}")
print(f"DONE in {int(elapsed/60)}m {int(elapsed%60)}s")
print(f"  Embedded : {done}")
print(f"  Errors   : {errors}")
print(f"  Total DB : {total_all}")
print(f"\n✅ Supabase embeddings updated to gemini-embedding-001 (3072-dim)")
print(f"✅ Push code to GitHub — Render will use real AI embeddings")
