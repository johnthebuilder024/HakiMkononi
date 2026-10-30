"""
Management command: scrape_kenyalaw

Fetches recent Kenya Law judgments and stores deep jurisprudence in the DB.

Strategy — tries BOTH methods for each judgment, best of both worlds:

  Option A — Full PDF (primary):
    Downloads the judgment PDF from kenyalaw.org/source
    Uses pdfplumber to extract the FULL text (every word, no truncation)
    Splits into 500-word overlapping chunks
    Each chunk becomes its own Law row with embedding
    This gives the AI the complete court reasoning

  Option B — HTML citation extraction (fallback):
    If PDF fails (not available, download error, etc.) falls back to
    scraping the HTML page for law citations + interpretation windows
    Same as before but now truly a fallback, not the only method

Result: each judgment is fully understood — not guessed from snippets.

Usage:
  python manage.py scrape_kenyalaw          # last 30 judgments
  python manage.py scrape_kenyalaw --days 30
  python manage.py scrape_kenyalaw --dry-run
  python manage.py scrape_kenyalaw --max-judgments 50

Render cron (render.yaml):
  schedule: "0 2 * * *"   # 2am Nairobi daily
"""

import re
import time
import logging
import os
import tempfile

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# ── Kenya Law URLs ─────────────────────────────────────────────────────────────
KENYALAW_JUDGMENTS_URL = "https://kenyalaw.org/judgments/?ordering=-date_of_judgment"
KENYALAW_ALL_URL       = "https://kenyalaw.org/judgments/all/?ordering=-date_of_judgment"

# ── PDF chunk settings ────────────────────────────────────────────────────────
# Each chunk is CHUNK_WORDS words, overlapping OVERLAP_WORDS with the next.
# Overlap ensures a sentence split across two chunks isn't lost.
CHUNK_WORDS   = 500
OVERLAP_WORDS = 80

# ── Minimum text length to bother saving ──────────────────────────────────────
MIN_CHUNK_LEN = 100   # characters

# ── Citation regex (used in HTML fallback) ────────────────────────────────────
CITATION_RE = re.compile(
    r'(?:section|article|s\.?)\s+(\d+[A-Z]?(?:\([a-z0-9]+\))?)'
    r'\s+(?:of\s+)?(?:the\s+)?([A-Z][A-Za-z &,()]+?Act(?:\s+(?:No\.?\s*)?\d{4})?)',
    re.IGNORECASE,
)

# ── Interpretation signals (used in HTML fallback) ────────────────────────────
INTERPRETATION_SIGNALS = [
    r'(?:I )?(?:hold|held|find|found|determine|determined|rule|ruled|conclude|concluded)\s+that',
    r'(?:the court|this court|the tribunal)\s+(?:is of the view|finds|holds|rules|determines)',
    r'(?:it is|I am)\s+(?:clear|satisfied|of the opinion|of the view)\s+that',
    r'(?:the )?(?:correct|proper|true|right)\s+interpretation\s+(?:of|is)',
    r'the\s+(?:plain|ordinary|natural)\s+meaning\s+of',
    r'pursuant to\s+(?:section|article)',
    r'a\s+(?:breach|violation)\s+of\s+(?:section|article)',
    r'the\s+employer\s+(?:was|is)\s+(?:required|obligated|bound)',
    r'the\s+(?:landlord|tenant)\s+(?:has|had)\s+(?:no right|the right)',
    r'the\s+police\s+(?:were|are)\s+(?:required|obligated|bound)',
    r'amounts\s+to\s+(?:a\s+)?(?:violation|breach|infringement)',
    r'contrary\s+to\s+(?:section|article)',
    r'in\s+contravention\s+of',
    r'the\s+respondent\s+(?:failed|breached|violated)',
]
INTERP_RE = re.compile('|'.join(INTERPRETATION_SIGNALS), re.IGNORECASE)

# ── Category mapping ───────────────────────────────────────────────────────────
ACT_CATEGORY = {
    'constitution':        'constitution',
    'employment':          'employment',
    'labour':              'employment',
    'occupational safety': 'employment',
    'work injury':         'employment',
    'rent restriction':    'landlord_tenant',
    'landlord':            'landlord_tenant',
    'distress for rent':   'landlord_tenant',
    'criminal procedure':  'criminal_procedure',
    'penal code':          'criminal_procedure',
    'national police':     'criminal_procedure',
    'sexual offences':     'criminal_procedure',
    'children':            'children',
    'land act':            'land',
    'land registration':   'land',
    'community land':      'land',
    'land control':        'land',
    'succession':          'land',
    'widows':              'family',
    'marriage':            'family',
    'matrimonial':         'family',
    'domestic violence':   'family',
    'consumer':            'consumer',
    'computer misuse':     'fraud',
    'cybercrimes':         'fraud',
    'hire purchase':       'fraud',
    'data protection':     'other',
    'elections':           'other',
    'basic education':     'other',
    'refugees':            'other',
    'traffic':             'other',
    'banking':             'other',
    'insurance':           'other',
    'copyright':           'other',
    'industrial property': 'other',
    'trade marks':         'other',
    'disabilities':        'other',
    'environment':         'other',
    'procurement':         'other',
    'health act':          'other',
    'national payment':    'other',
}


def _guess_category(text: str) -> str:
    t = text.lower()
    for keyword, category in ACT_CATEGORY.items():
        if keyword in t:
            return category
    return 'other'


# ─────────────────────────────────────────────────────────────────────────────
# OPTION A — Full PDF extraction
# ─────────────────────────────────────────────────────────────────────────────

def _pdf_url_from_judgment_url(judgment_url: str) -> str:
    """
    Derive the PDF download URL from a judgment HTML URL.
    Kenya Law pattern:
      HTML: https://kenyalaw.org/akn/ke/judgment/keelc/2024/4992/eng@2024-01-16
      PDF:  https://kenyalaw.org/akn/ke/judgment/keelc/2024/4992/eng@2024-01-16/source
    """
    url = judgment_url.rstrip('/')
    if not url.endswith('/source'):
        url = url + '/source'
    return url


def _extract_full_pdf(session, pdf_url: str, stdout) -> str | None:
    """
    Download the judgment PDF to a temp file and extract full text with pdfplumber.
    Returns the full text string, or None on failure.
    """
    try:
        import pdfplumber
    except ImportError:
        stdout.write("  [PDF] pdfplumber not installed — skipping PDF extraction")
        return None

    tmp_path = None
    try:
        resp = session.get(pdf_url, timeout=60, stream=True)
        if resp.status_code != 200:
            return None

        # Check it's actually a PDF (not an HTML error page)
        content_type = resp.headers.get('Content-Type', '')
        if 'pdf' not in content_type.lower() and not pdf_url.endswith('/source'):
            return None

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name
            for chunk in resp.iter_content(chunk_size=8192):
                tmp.write(chunk)

        # Extract text with pdfplumber
        pages_text = []
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)

        full_text = '\n'.join(pages_text)
        return full_text if len(full_text) > 200 else None

    except Exception as e:
        logger.debug(f"PDF extraction failed for {pdf_url}: {e}")
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _chunk_text(text: str, case_ref: str, source_url: str) -> list:
    """
    Split full judgment text into overlapping word chunks.
    Each chunk becomes one Law row.

    Returns list of dicts: {title, section, content, category}
    """
    words = text.split()
    chunks = []
    step = CHUNK_WORDS - OVERLAP_WORDS
    i = 0
    chunk_num = 1

    while i < len(words):
        chunk_words = words[i:i + CHUNK_WORDS]
        chunk_text  = ' '.join(chunk_words)

        if len(chunk_text) >= MIN_CHUNK_LEN:
            # Guess category from the chunk content itself
            category = _guess_category(chunk_text)

            chunks.append({
                'title':      f"Judgment: {case_ref}"[:300],
                'section':    f"Part {chunk_num}",
                'content':    chunk_text[:3000],
                'category':   category,
                'source_url': source_url,
            })
            chunk_num += 1

        i += step

    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# OPTION B — HTML citation + interpretation extraction (fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_interpretation_window(text: str, citation_pos: int, window: int = 600) -> str:
    start  = max(0, citation_pos - window)
    end    = min(len(text), citation_pos + window)
    region = text[start:end]

    interp_match = INTERP_RE.search(region)
    if interp_match:
        abs_pos    = start + interp_match.start()
        sent_start = text.rfind('.', max(0, abs_pos - 300), abs_pos)
        sent_start = sent_start + 2 if sent_start > 0 else max(0, abs_pos - 200)
        sent_end   = text.find('.', abs_pos + 50)
        sent_end   = sent_end + 1 if sent_end > 0 else abs_pos + 300
        extra_end  = text.find('.', sent_end + 1)
        extra_end  = extra_end + 1 if extra_end > 0 else sent_end + 200
        return text[sent_start:extra_end].strip()

    sent_start = text.rfind('.', max(0, citation_pos - 200), citation_pos)
    sent_start = sent_start + 2 if sent_start > 0 else max(0, citation_pos - 150)
    sent_end   = text.find('.', citation_pos + 50)
    sent_end   = sent_end + 1 if sent_end > 0 else citation_pos + 300
    return text[sent_start:sent_end].strip()


def _extract_html_rows(html_text: str, case_ref: str, source_url: str, min_len: int) -> list:
    """
    Option B: extract citation + interpretation snippets from HTML text.
    Returns list of dicts: {title, section, content, category, source_url}
    """
    rows = []
    seen = set()

    for m in CITATION_RE.finditer(html_text):
        section_num = m.group(1).strip()
        act_name    = m.group(2).strip()
        key         = f"{act_name}|{section_num}"
        if key in seen:
            continue
        seen.add(key)

        interp = _extract_interpretation_window(html_text, m.start())

        if case_ref:
            neutral = re.search(r'\[\d{4}\]\s+[A-Z]+\s+\d+', case_ref)
            cite    = neutral.group(0) if neutral else case_ref[:60]
            content = f"Court interpretation ({cite}): {interp}"
        else:
            content = f"Court interpretation: {interp}"

        if len(content) < min_len:
            continue

        rows.append({
            'title':      act_name,
            'section':    f"Section {section_num}",
            'content':    content[:2000],
            'category':   _guess_category(act_name),
            'source_url': source_url,
        })

    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Judgment link extraction
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_judgment_links(session, max_j: int, stdout) -> list:
    links = []
    for listing_url in [KENYALAW_JUDGMENTS_URL, KENYALAW_ALL_URL]:
        try:
            resp = session.get(listing_url, timeout=30)
            if resp.status_code != 200:
                continue
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')

            for a in soup.find_all('a', href=True):
                href = a['href']
                if (
                    ('/akn/ke/judgment/' in href or '/judgments/' in href)
                    and href not in links
                    and 'ordering=' not in href
                    and '/all/' not in href
                    and '/source' not in href
                ):
                    if not href.startswith('http'):
                        href = f"https://kenyalaw.org{href}"
                    links.append(href)
                    if len(links) >= max_j:
                        break
            if links:
                break
        except Exception as e:
            stdout.write(f"  Warning: listing fetch failed ({e})")
            continue
    return links


def _extract_case_name(soup) -> str:
    for selector in ['h1', '.judgment-title', 'title', '.case-title']:
        el = soup.find(selector)
        if el:
            t = el.get_text(' ', strip=True)
            if len(t) > 10:
                return t[:200]
    return ""


def _extract_html_text(soup) -> str:
    for cls in ['judgment-body', 'judgment-content', 'document-body', 'akn-body']:
        el = soup.find(class_=cls)
        if el:
            return el.get_text(' ', strip=True)
    for tag in ['article', 'main']:
        el = soup.find(tag)
        if el:
            t = el.get_text(' ', strip=True)
            if len(t) > 500:
                return t
    return soup.get_text(' ', strip=True)


# ─────────────────────────────────────────────────────────────────────────────
# Shared: save rows + embed
# ─────────────────────────────────────────────────────────────────────────────

def _save_rows(rows: list, dry_run: bool, stdout) -> int:
    """Save a list of row dicts to the Law model. Returns count of new rows saved."""
    from cases.models import Law
    saved = 0
    for row in rows:
        already = Law.objects.filter(
            title__icontains=row['title'][:50],
            section__iexact=row['section'],
            content__startswith=row['content'][:80],
        ).exists()
        if already:
            continue
        if not dry_run:
            Law.objects.create(
                title      = row['title'],
                section    = row['section'],
                content    = row['content'],
                category   = row['category'],
                source_url = row['source_url'],
            )
        saved += 1
        stdout.write(f"    + [{row['category']}] {row['title'][:60]} — {row['section']}")
    return saved


def _embed_and_reload(stdout):
    """Embed all unembedded Law rows and invalidate the RAG cache."""
    from cases.rag import embed_text, invalidate_law_cache
    from cases.models import Law

    unembedded = Law.objects.filter(embedding_json='').exclude(content='')
    total = unembedded.count()
    if total == 0:
        return

    stdout.write(f"[scrape_kenyalaw] Embedding {total} new rows...")
    count = failed = 0
    for law in unembedded:
        try:
            vec = embed_text(f"{law.title} {law.section}: {law.content}")
            if vec:
                law.set_embedding(vec)
                law.save(update_fields=['embedding_json'])
                count += 1
                time.sleep(0.2)   # stay within Gemini free tier
        except Exception as e:
            failed += 1
            logger.warning(f"Embedding failed for Law #{law.pk}: {e}")

    stdout.write(f"[scrape_kenyalaw] Embedded {count} rows ({failed} failed)")
    invalidate_law_cache()
    stdout.write("[scrape_kenyalaw] RAG cache reloaded — new knowledge is live")


# ─────────────────────────────────────────────────────────────────────────────
# Django management command
# ─────────────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Scrape Kenya Law judgments — full PDF (Option A) with HTML fallback (Option B). "
        "Stores complete judgment text in chunks so the AI never has to guess."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-judgments', type=int, default=30,
            help='Maximum number of judgments to process (default: 30)'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would be added without saving'
        )
        parser.add_argument(
            '--min-content-len', type=int, default=100,
            help='Minimum characters for a row to be saved (default: 100)'
        )

    def handle(self, *args, **options):
        import requests
        from bs4 import BeautifulSoup

        dry_run  = options['dry_run']
        max_j    = options['max_judgments']
        min_len  = options['min_content_len']

        self.stdout.write(
            f"\n[scrape_kenyalaw] Starting — max {max_j} judgments"
            + (" (DRY RUN)" if dry_run else "")
        )

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'HakiMkononi-scraper/2.0 (legal AI Kenya; contact@hakimkononi.co.ke)'
        })

        # ── Get judgment URLs ─────────────────────────────────────────────────
        judgment_links = _fetch_judgment_links(session, max_j, self.stdout)
        self.stdout.write(f"  Found {len(judgment_links)} judgment links\n")

        if not judgment_links:
            self.stderr.write(
                "[scrape_kenyalaw] No judgment links found. "
                "Check: https://kenyalaw.org/judgments/"
            )
            return

        total_new   = 0
        pdf_success = 0
        html_used   = 0
        errors      = 0

        for i, url in enumerate(judgment_links, 1):
            self.stdout.write(f"  [{i}/{len(judgment_links)}] {url[:90]}")

            rows     = []
            method   = None

            # ── OPTION A: Try full PDF first ──────────────────────────────────
            pdf_url  = _pdf_url_from_judgment_url(url)
            pdf_text = _extract_full_pdf(session, pdf_url, self.stdout)

            if pdf_text and len(pdf_text) >= 300:
                # Extract case reference from URL for labelling chunks
                # e.g. /akn/ke/judgment/keelc/2024/4992/... → KEELC 4992 (2024)
                url_match = re.search(
                    r'/akn/ke/judgment/([a-z]+)/(\d{4})/(\d+)/', url, re.IGNORECASE
                )
                if url_match:
                    court, year, num = url_match.groups()
                    case_ref = f"[{year}] {court.upper()} {num}"
                else:
                    case_ref = url.split('/')[-1][:60]

                rows   = _chunk_text(pdf_text, case_ref, url)
                method = f"PDF ({len(pdf_text):,} chars → {len(rows)} chunks)"
                pdf_success += 1

            # ── OPTION B: HTML fallback ───────────────────────────────────────
            if not rows:
                try:
                    r = session.get(url, timeout=25)
                    if r.status_code == 200:
                        soup      = BeautifulSoup(r.text, 'html.parser')
                        case_name = _extract_case_name(soup)
                        html_text = _extract_html_text(soup)

                        if len(html_text) >= 300:
                            rows   = _extract_html_rows(html_text, case_name, url, min_len)
                            method = f"HTML fallback ({len(rows)} citation snippets)"
                            html_used += 1
                except Exception as e:
                    errors += 1
                    self.stderr.write(f"    HTML fallback failed: {e}")

            if not rows:
                self.stdout.write(f"    ↳ No content extracted — skipping")
                errors += 1
                time.sleep(1)
                continue

            self.stdout.write(f"    ↳ Method: {method}")

            # ── Save rows ─────────────────────────────────────────────────────
            saved = _save_rows(rows, dry_run, self.stdout)
            total_new += saved
            self.stdout.write(f"    ↳ Saved {saved} new rows")

            time.sleep(1.5)   # polite delay

        # ── Embed all new rows and reload RAG ─────────────────────────────────
        if total_new > 0 and not dry_run:
            _embed_and_reload(self.stdout)

        self.stdout.write(f"""
[scrape_kenyalaw] ✅ Complete
  Judgments processed : {len(judgment_links)}
  Full PDF (Option A) : {pdf_success}
  HTML fallback (B)   : {html_used}
  Errors / skipped    : {errors}
  New rows saved      : {total_new}
""")
