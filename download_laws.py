"""
Downloads all remaining Kenyan law PDFs into the data/ folder.
Run: python download_laws.py
"""
import os
import time
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*",
    "Referer": "https://kenyalaw.org/",
}

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

DOWNLOADS = [
    # ── 3 that failed on old site — using new.kenyalaw.org instead ───────
    (
        "Law of Succession Act.pdf",
        "https://new.kenyalaw.org/akn/ke/act/1972/14/eng@2022-12-31/source.pdf",
    ),
    (
        "Sexual Offences Act 2006.pdf",
        "https://new.kenyalaw.org/akn/ke/act/2006/3/eng@2024-04-26/source.pdf",
    ),
    (
        "Traffic Act Cap 403.pdf",
        "https://new.kenyalaw.org/akn/ke/act/1953/39/eng@2024-04-26/source.pdf",
    ),
]

print("=" * 60)
print("Downloading Kenyan Law PDFs into data/")
print("=" * 60)

success = []
failed  = []

for filename, url in DOWNLOADS:
    out_path = os.path.join(DATA_DIR, filename)

    # Skip if already downloaded and non-empty
    if os.path.exists(out_path) and os.path.getsize(out_path) > 5000:
        print(f"  ✅ SKIP (exists)  {filename}")
        success.append(filename)
        continue

    print(f"  ⬇️  Downloading  {filename}")
    print(f"       {url[:70]}...")

    try:
        r = requests.get(url, headers=HEADERS, timeout=(15, 60), stream=True)
        if r.status_code == 200:
            content_type = r.headers.get("Content-Type", "")
            if "html" in content_type.lower():
                print(f"  ⚠️  Got HTML instead of PDF — URL may be wrong")
                failed.append((filename, f"HTML response from {url}"))
                continue

            total = 0
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)

            size_kb = total // 1024
            if total < 5000:
                os.remove(out_path)
                print(f"  ❌ Too small ({total} bytes) — likely an error page")
                failed.append((filename, f"Only {total} bytes"))
            else:
                print(f"  ✅ Done  ({size_kb} KB)  {filename}")
                success.append(filename)
        else:
            print(f"  ❌ HTTP {r.status_code}  {filename}")
            failed.append((filename, f"HTTP {r.status_code}"))

    except requests.exceptions.Timeout:
        print(f"  ⏱️  Timeout  {filename}")
        failed.append((filename, "Timeout"))
    except Exception as e:
        print(f"  ❌ Error: {str(e)[:60]}")
        failed.append((filename, str(e)[:60]))

    time.sleep(1)  # be polite to the server

print()
print("=" * 60)
print(f"DONE — {len(success)} succeeded, {len(failed)} failed")
print("=" * 60)

if success:
    print("\n✅ Downloaded:")
    for f in success:
        size = os.path.getsize(os.path.join(DATA_DIR, f)) // 1024
        print(f"   {f}  ({size} KB)")

if failed:
    print("\n❌ Failed:")
    for f, reason in failed:
        print(f"   {f}  — {reason}")
    print("\n  For failed ones, open the URL in your browser and save manually to data/")
