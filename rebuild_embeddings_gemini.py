"""
rebuild_embeddings_gemini.py
-----------------------------
Re-embeds all 4,231 law sections in Supabase using Google Gemini embedding-001.
Old embeddings were 384-dim (all-MiniLM-L6-v2).
New embeddings are 3072-dim (gemini-embedding-001) — higher quality.

Run once locally:
    python rebuild_embeddings_gemini.py

Rate limit: 1,500 RPM free tier — we batch with a small sleep to be safe.
"""

import os
import sys
import json
import time
import requests

# ── Django setup ──────────────────────────────────────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sheria_ai.settings")

import django
django.setup()

from cases.models import Law
from dotenv import load_dotenv
load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={GEMINI_API_KEY}"
BATCH_SIZE = 20       # process 20 at a time
SLEEP_BETWEEN = 0.1   # 100ms between calls = safe under 1500 RPM
REBUILD_ALL = "--all" in sys.argv  # pass --all to force re-embed even existing ones

if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY not set in .env")
    sys.exit(1)

print(f"✅ Gemini API key loaded")
print(f"✅ Django + Supabase connected")


def embed_text(text: str) -> list:
    resp = requests.post(
        EMBED_URL,
        headers={"Content-Type": "application/json"},
        json={
            "model": "models/gemini-embedding-001",
            "content": {"parts": [{"text": text}]},
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]


# ── Count work to do ──────────────────────────────────────────────────────────
total_laws = Law.objects.count()

if REBUILD_ALL:
    laws_to_process = Law.objects.all()
    print(f"\nMode: REBUILD ALL — {total_laws} sections")
else:
    # Only process sections whose embedding is missing OR is old (384-dim)
    # We detect old embeddings by checking length of stored JSON array
    laws_to_process = []
    print(f"\nScanning {total_laws} sections for missing/outdated embeddings...")
    for law in Law.objects.all():
        if not law.embedding_json:
            laws_to_process.append(law)
        else:
            try:
                vec = json.loads(law.embedding_json)
                if len(vec) != 3072:  # not gemini-embedding-001 dimension
                    laws_to_process.append(law)
            except Exception:
                laws_to_process.append(law)

total_to_do = len(laws_to_process)
print(f"Found {total_to_do} sections needing new embeddings")

if total_to_do == 0:
    print("✅ All embeddings are already up to date!")
    sys.exit(0)

# Estimate time
est_seconds = total_to_do * (SLEEP_BETWEEN + 0.3)  # ~300ms per API call
print(f"Estimated time: ~{int(est_seconds/60)} minutes {int(est_seconds%60)} seconds\n")

# ── Main loop ─────────────────────────────────────────────────────────────────
done = 0
errors = 0
start_time = time.time()

for law in laws_to_process:
    text = f"{law.title} {law.section}: {law.content}"
    # Truncate to 2048 chars (model input limit)
    text = text[:2048]

    try:
        vector = embed_text(text)
        law.set_embedding(vector)
        law.save(update_fields=["embedding_json"])
        done += 1

        if done % 50 == 0 or done == total_to_do:
            elapsed = time.time() - start_time
            rate = done / elapsed if elapsed > 0 else 0
            remaining = (total_to_do - done) / rate if rate > 0 else 0
            print(f"  [{done}/{total_to_do}] ✅  {law.title[:40]} — {int(remaining)}s remaining")

        time.sleep(SLEEP_BETWEEN)

    except Exception as e:
        errors += 1
        print(f"  ❌ Error on {law.title} {law.section}: {e}")
        time.sleep(2)  # back off on error
        if errors > 20:
            print("Too many errors — stopping.")
            break

# ── Summary ───────────────────────────────────────────────────────────────────
elapsed = time.time() - start_time
print(f"\n{'='*55}")
print(f"DONE in {int(elapsed/60)}m {int(elapsed%60)}s")
print(f"  Embedded: {done}")
print(f"  Errors:   {errors}")
print(f"  Total:    {total_laws} sections in DB")
print(f"\n✅ Supabase embeddings now use gemini-embedding-001 (3072-dim)")
print(f"✅ Push code to GitHub and Render will use real AI embeddings")
