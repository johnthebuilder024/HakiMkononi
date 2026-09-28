"""Check if new PDFs are readable and show sample content. Run: python check_new_pdfs.py"""
import pdfplumber

PDFS = [
    "data/Distress for Rent Act.pdf",
    "data/Landlord and Tenant (Shops Hotels and Catering Establishments) Act.pdf",
    "data/Rent Restriction Act.pdf",
]

for path in PDFS:
    print("=" * 70)
    print(f"PDF: {path}")
    print("=" * 70)
    try:
        with pdfplumber.open(path) as pdf:
            print(f"  Total pages: {len(pdf.pages)}")
            # Check first 3 readable pages
            readable = 0
            for i, page in enumerate(pdf.pages[:10]):
                text = page.extract_text() or ""
                if text.strip():
                    readable += 1
                    if readable <= 2:
                        lines = [l for l in text.strip().split("\n") if l.strip()]
                        print(f"  Page {i+1} first lines:")
                        for line in lines[:6]:
                            print(f"    {line[:80]}")
                        print()
            print(f"  Readable pages (first 10): {readable}/10")
            
            # Look for section patterns
            all_text = ""
            for page in pdf.pages[:15]:
                t = page.extract_text() or ""
                all_text += t + "\n"
            
            import re
            # Count how many section headings we can find
            sections_found = re.findall(r'\n\d+[A-Z]?\.\s+[A-Z][^\n]{5,}', all_text)
            print(f"  Section headings found in first 15 pages: {len(sections_found)}")
            if sections_found:
                print(f"  Sample sections:")
                for s in sections_found[:5]:
                    print(f"    {s.strip()[:70]}")
    except Exception as e:
        print(f"  ERROR: {e}")
    print()
