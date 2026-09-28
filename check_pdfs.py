"""
Check each PDF - pages, readable pages, section count.
Uses only first 5 pages to avoid hanging on large PDFs.
Run: python check_pdfs.py
"""
import os, re, pdfplumber

DATA_DIR = "data"
pdfs = sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".pdf"))
print(f"Checking {len(pdfs)} PDFs...\n")
print(f"{'FILE':<55} {'KB':>5}  {'PGS':>4}  {'READ':>4}  {'SECTS':>5}  STATUS")
print("-" * 100)

good, warn, bad = [], [], []

for fname in pdfs:
    path = os.path.join(DATA_DIR, fname)
    kb = os.path.getsize(path) // 1024
    try:
        with pdfplumber.open(path) as pdf:
            npages = len(pdf.pages)
            readable = 0
            text = ""
            # Only read first 8 pages max — fast, avoids hanging
            for pg in pdf.pages[:8]:
                t = pg.extract_text() or ""
                if t.strip():
                    readable += 1
                    text += t + "\n"
            sects = len(re.findall(r'\n\d+[A-Z]?\.\s+[A-Z][^\n]{5,}', text))
            if readable == 0:
                status = "❌ UNREADABLE"
                bad.append(fname)
            elif sects == 0:
                status = "⚠️  NO SECTIONS FOUND"
                warn.append(fname)
            else:
                status = "✅ OK"
                good.append(fname)
            print(f"{fname:<55} {kb:>5}  {npages:>4}  {readable:>4}  {sects:>5}  {status}")
    except Exception as e:
        print(f"{fname:<55} {kb:>5}     ?     ?      ?  ❌ ERROR: {str(e)[:40]}")
        bad.append(fname)

print()
print(f"✅ Good: {len(good)}   ⚠️  Warn: {len(warn)}   ❌ Bad: {len(bad)}")
if warn or bad:
    print("\nNeeds attention:")
    for f in warn + bad:
        print(f"  → {f}")
