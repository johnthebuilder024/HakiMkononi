"""Look at pages 20-30 raw text. Run: python check_constitution_pdf.py"""
import pdfplumber

pdf_path = 'data/Constitution of Kenya.pdf'
with pdfplumber.open(pdf_path) as pdf:
    print(f"Total pages: {len(pdf.pages)}")
    # Show full text of pages 20-25
    for i in range(19, 26):
        page = pdf.pages[i]
        text = page.extract_text() or ''
        print(f"\n{'='*60}")
        print(f"PAGE {i+1}")
        print('='*60)
        print(repr(text[:500]))  # repr shows whitespace/newlines clearly
