"""
Loads the 2 large PDFs that hang pdfplumber when reading all pages at once.
Strategy: read only 10 pages at a time, extract text, find sections.
Run: python load_large_pdfs.py
"""
import os, re, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sheria_ai.settings')
django.setup()
from cases.models import Law
import pdfplumber

LARGE_PDFS = [
    {
        "pdf":      "data/Children Act 2022.pdf",
        "title":    "Children Act 2022 (No. 29 of 2022)",
        "category": "children",
        "url":      "https://new.kenyalaw.org/akn/ke/act/2022/29/eng@2022-07-29",
    },
    {
        "pdf":      "data/Land Act 2012.pdf",
        "title":    "Land Act 2012 (No. 6 of 2012)",
        "category": "land",
        "url":      "https://new.kenyalaw.org/akn/ke/act/2012/6/eng@2022-12-31",
    },
]

SECTION_RE = re.compile(r'^(\d+[A-Z]?)\.\s+([A-Z][^\n]{5,})$', re.MULTILINE)

def load_pdf_chunked(pdf_path, title, category, url, chunk_size=8):
    """Read PDF in chunks of chunk_size pages, extract sections, save to DB."""
    if not os.path.exists(pdf_path):
        print(f"  ❌ File not found: {pdf_path}")
        return 0

    # Check already loaded
    existing = Law.objects.filter(title=title).count()
    if existing > 0:
        print(f"  ✅ SKIP — already in DB ({existing} sections): {title}")
        return 0

    print(f"\n📖 Loading (chunked): {title}")
    print(f"   PDF: {pdf_path} ({os.path.getsize(pdf_path)//1024} KB)")

    all_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"   Pages: {total_pages}  — reading in chunks of {chunk_size}")
            for start in range(0, total_pages, chunk_size):
                end = min(start + chunk_size, total_pages)
                chunk_text = ""
                for page in pdf.pages[start:end]:
                    t = page.extract_text() or ""
                    chunk_text += t + "\n"
                all_text += chunk_text
                print(f"   Read pages {start+1}–{end}/{total_pages}...", end="\r")
    except Exception as e:
        print(f"\n  ❌ PDF read error: {e}")
        return 0

    print(f"\n   Text extracted ({len(all_text)//1000} KB). Finding sections...")

    # Find all section headings
    sections = []
    matches = list(SECTION_RE.finditer(all_text))
    print(f"   Found {len(matches)} section headings")

    for i, match in enumerate(matches):
        heading = match.group(0).strip()
        start_pos = match.end()
        end_pos = matches[i+1].start() if i+1 < len(matches) else len(all_text)
        content = all_text[start_pos:end_pos].strip()
        if len(content) >= 30:  # skip trivial sections
            sections.append({"heading": heading, "content": content[:3000]})

    if not sections:
        print("  ⚠️  No sections found — PDF may have unusual formatting")
        return 0

    created = 0
    for sec in sections:
        if not Law.objects.filter(title=title, section=sec["heading"]).exists():
            Law.objects.create(
                title=title,
                section=sec["heading"],
                content=sec["content"],
                category=category,
                source_url=url,
                simple_swahili="",
                related_to="",
                embedding_json="",
            )
            created += 1

    print(f"   ✅ Created {created} sections in DB")
    return created


total_new = 0
for entry in LARGE_PDFS:
    n = load_pdf_chunked(
        entry["pdf"], entry["title"], entry["category"], entry["url"],
        chunk_size=6,
    )
    total_new += n

if total_new > 0:
    print(f"\n{'='*55}")
    print(f"Building embeddings for {total_new} new sections...")
    import subprocess, sys
    subprocess.run([sys.executable, "manage.py", "build_embeddings"], cwd=os.getcwd())

# Final count
from collections import Counter
counts = Counter(Law.objects.values_list("title", flat=True))
total = Law.objects.count()
emb   = Law.objects.exclude(embedding_json="").count()
print(f"\n{'='*55}")
print(f"TOTAL: {total} sections, {emb} with embeddings, {total-emb} missing")
for t, c in sorted(counts.items()):
    print(f"  {c:4d}  {t}")
