"""
Downloads the 3 remaining PDFs using new.kenyalaw.org.
Run: python download_remaining.py
"""
import os
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*",
    "Referer": "https://new.kenyalaw.org/",
}

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

DOWNLOADS = [
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

print("Downloading 3 remaining PDFs...")
print()

for filename, url in DOWNLOADS:
    out_path = os.path.join(DATA_DIR, filename)
    print(f"Downloading: {filename}")
    print(f"       URL : {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=(15, 60), stream=True)
        print(f"    Status : {r.status_code}  Content-Type: {r.headers.get('Content-Type','?')[:40]}")
        if r.status_code == 200:
            total = 0
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
            print(f"    Result : {'✅ ' + str(total//1024) + ' KB saved' if total > 5000 else '❌ Too small: ' + str(total) + ' bytes'}")
            if total < 5000:
                os.remove(out_path)
        else:
            print(f"    Result : ❌ HTTP {r.status_code}")
            print(f"    Body   : {r.text[:100]}")
    except Exception as e:
        print(f"    Result : ❌ {str(e)[:80]}")
    print()

# Final check — list everything in data/
print("=" * 50)
print("Files now in data/:")
for f in sorted(os.listdir(DATA_DIR)):
    if f.endswith(".pdf"):
        size = os.path.getsize(os.path.join(DATA_DIR, f)) // 1024
        print(f"  {size:5d} KB  {f}")
