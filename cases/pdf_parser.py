"""
PDF Parser — splits a Kenyan law PDF into individual sections
and saves each as a Law row in the database.

Usage (from Django shell or management command):
    from cases.pdf_parser import parse_pdf
    parse_pdf(
        pdf_path='data/employment_act_2007.pdf',
        act_title='Employment Act 2007',
        category='employment',
        source_url='https://kenyalaw.org/kl/fileadmin/pdfdownloads/Acts/EmploymentAct_No11of2007.pdf'
    )
"""

import re
import pdfplumber
from cases.models import Law


# Patterns to detect section/article headings in Kenyan law PDFs
SECTION_PATTERNS = [
    # "35." or "35 ." or "Section 35" or "Sec. 35"
    re.compile(r'^(?:Section\s+|Sec\.\s+)?(\d+[A-Z]?)\.\s+(.+)$', re.IGNORECASE),
    # "Article 49" or "49."
    re.compile(r'^(?:Article\s+)?(\d+[A-Z]?)\.\s+(.+)$', re.IGNORECASE),
    # "(1)" sub-sections — these get folded into the parent section
]


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF, page by page."""
    full_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text.append(text)
    return "\n".join(full_text)


def split_into_sections(text: str, is_constitution: bool = False) -> list:
    """
    Split raw law text into a list of (section_number, section_title, content) tuples.
    Works for both numbered Acts and Articles.
    """
    sections = []

    if is_constitution:
        # Constitution uses "Article X." pattern
        pattern = re.compile(r'\n((?:Article|ARTICLE)\s+\d+[A-Z]?\.?\s+[A-Z][^\n]+)', re.MULTILINE)
    else:
        # Standard Acts use "X. Title" pattern
        pattern = re.compile(r'\n(\d+[A-Z]?\.\s+[A-Z][^\n]+)', re.MULTILINE)

    matches = list(pattern.finditer(text))

    for i, match in enumerate(matches):
        heading = match.group(1).strip()

        # Content is everything between this heading and the next
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        # Skip very short fragments (table of contents entries, page numbers)
        if len(content) < 50:
            continue

        sections.append({
            'heading': heading,
            'content': content[:3000],  # cap at 3000 chars per section
        })

    return sections


def parse_pdf(
    pdf_path: str,
    act_title: str,
    category: str,
    source_url: str,
    is_constitution: bool = False,
    overwrite: bool = False,
) -> int:
    """
    Parse a PDF and save each section as a Law row.

    Returns the number of sections created.
    """
    print(f"[PDF Parser] Reading: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)

    print(f"[PDF Parser] Splitting into sections...")
    sections = split_into_sections(text, is_constitution=is_constitution)

    print(f"[PDF Parser] Found {len(sections)} sections. Saving to database...")

    created = 0
    skipped = 0

    for sec in sections:
        heading = sec['heading']
        content = sec['content']

        # Check if already exists (avoid duplicates)
        exists = Law.objects.filter(title=act_title, section=heading).exists()
        if exists and not overwrite:
            skipped += 1
            continue

        if overwrite:
            Law.objects.filter(title=act_title, section=heading).delete()

        Law.objects.create(
            title=act_title,
            section=heading,
            content=content,
            category=category,
            source_url=source_url,
            simple_swahili='',  # You fill this in the admin, or we add it later
            related_to='',
            embedding_json='',  # Built separately via build_embeddings command
        )
        created += 1

    print(f"[PDF Parser] Done. Created: {created}, Skipped (already exist): {skipped}")
    print(f"[PDF Parser] Next step: run 'python manage.py build_embeddings' to build AI embeddings.")
    return created
