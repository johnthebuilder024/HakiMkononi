"""
Management command: scrape_kenyalaw

Fetches recent judgments from kenyalaw.org and saves DEEP jurisprudence to the DB.

Unlike a simple citation extractor, this command:
  1. Fetches every judgment page fully
  2. Extracts EVERY legal interpretation the court made — the ratio decidendi,
     the court's reasoning on each law point, key holdings, and what each
     cited section means in practice
  3. Saves each interpretation as a rich Law row (title = Act, section = section,
     content = court's interpretation + judgment reference)
  4. Generates Gemini embeddings for all new rows so RAG can find them

This means when Wanjiku asks about wrongful termination, the AI can cite not
just the bare Employment Act text but also "In [2024] KEELC 4992, the court
held that section 45 requires..." — the real, current interpretation.

Usage:
  python manage.py scrape_kenyalaw          # last 7 days, default 30 judgments
  python manage.py scrape_kenyalaw --days 30
  python manage.py scrape_kenyalaw --dry-run
  python manage.py scrape_kenyalaw --max-judgments 50

Render cron (already in render.yaml):
  schedule: "0 2 * * *"   # 2am Nairobi daily
"""

import re
import time
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# ── Kenya Law URLs ─────────────────────────────────────────────────────────────
# The live site redirects new.kenyalaw.org → kenyalaw.org; use the canonical URL.
KENYALAW_JUDGMENTS_URL = "https://kenyalaw.org/judgments/?ordering=-date_of_judgment"
KENYALAW_ALL_URL       = "https://kenyalaw.org/judgments/all/?ordering=-date_of_judgment"

# ── Citation regex — finds "Section 45 of the Employment Act 2007" patterns ───
CITATION_RE = re.compile(
    r'(?:section|article|s\.?)\s+(\d+[A-Z]?(?:\([a-z0-9]+\))?)'
    r'\s+(?:of\s+)?(?:the\s+)?([A-Z][A-Za-z &,()]+?Act(?:\s+(?:No\.?\s*)?\d{4})?)',
    re.IGNORECASE,
)

# ── Interpretation paragraph markers ─────────────────────────────────────────
# Phrases a Kenyan judge uses when actually explaining what a law means.
# We grab the full sentence/paragraph around any of these markers.
INTERPRETATION_SIGNALS = [
    r'(?:I )?(?:hold|held|find|found|determine|determined|rule|ruled|conclude|concluded)\s+that',
    r'(?:the court|this court|the tribunal)\s+(?:is of the view|finds|holds|rules|determines)',
    r'(?:it is|I am)\s+(?:clear|satisfied|of the opinion|of the view)\s+that',
    r'(?:the )?(?:correct|proper|true|right)\s+interpretation\s+(?:of|is)',
    r'the\s+(?:plain|ordinary|natural)\s+meaning\s+of',
    r'pursuant to\s+(?:section|article)',
    r'in\s+(?:terms|light)\s+of\s+(?:section|article)',
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
    'constitution':          'constitution',
    'employment':            'employment',
    'labour':                'employment',
    'occupational safety':   'employment',
    'work injury':           'employment',
    'rent restriction':      'landlord_tenant',
    'landlord':              'landlord_tenant',
    'distress for rent':     'landlord_tenant',
    'criminal procedure':    'criminal_procedure',
    'penal code':            'criminal_procedure',
    'national police':       'criminal_procedure',
    'sexual offences':       'criminal_procedure',
    'children':              'children',
    'land act':              'land',
    'land registration':     'land',
    'community land':        'land',
    'land control':          'land',
    'succession':            'land',
    'widows':                'family',
    'marriage':              'family',
    'matrimonial':           'family',
    'domestic violence':     'family',
    'consumer':              'consumer',
    'computer misuse':       'fraud',
    'cybercrimes':           'fraud',
    'hire purchase':         'fraud',
    'data protection':       'other',
    'elections':             'other',
    'basic education':       'other',
    'refugees':              'other',
    'traffic':               'other',
    'banking':               'other',
    'insurance':             'other',
    'copyright':             'other',
    'industrial property':   'other',
    'trade marks':           'other',
    'disabilities':          'other',
    'environment':           'other',
    'procurement':           'other',
    'health act':            'other',
    'national payment':      'other',
}


def _guess_category(act_name: str) -> str:
    act_lower = act_name.lower()
    for keyword, category in ACT_CATEGORY.items():
        if keyword in act_lower:
            return category
    return 'other'


def _split_sentences(text: str) -> list:
    """Split text into sentences, preserving legal references that contain periods."""
    # Split on ". " followed by a capital letter, but not on "S. 45" or "No. 5"
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return [p.strip() for p in parts if len(p.strip()) > 20]


def _extract_interpretation_window(text: str, citation_pos: int, window: int = 600) -> str:
    """
    Given the position of a citation in text, find the best interpretation
    paragraph near it. We search ±window characters for an interpretation signal.
    If found, return the full sentence containing it + surrounding context.
    If not found, return the sentence the citation is in.
    """
    # Search window around the citation
    start = max(0, citation_pos - window)
    end   = min(len(text), citation_pos + window)
    region = text[start:end]

    # Try to find an interpretation signal in this region
    interp_match = INTERP_RE.search(region)
    if interp_match:
        # Expand to the full sentence(s) around the interpretation signal
        # Go back to the nearest sentence start
        abs_pos = start + interp_match.start()
        sent_start = text.rfind('.', max(0, abs_pos - 300), abs_pos)
        sent_start = sent_start + 2 if sent_start > 0 else max(0, abs_pos - 200)
        sent_end   = text.find('.', abs_pos + 50)
        sent_end   = sent_end + 1 if sent_end > 0 else abs_pos + 300
        # Grab 2 sentences forward for full context
        extra_end  = text.find('.', sent_end + 1)
        extra_end  = extra_end + 1 if extra_end > 0 else sent_end + 200
        return text[sent_start:extra_end].strip()

    # Fallback: return the sentence the citation sits in
    sent_start = text.rfind('.', max(0, citation_pos - 200), citation_pos)
    sent_start = sent_start + 2 if sent_start > 0 else max(0, citation_pos - 150)
    sent_end   = text.find('.', citation_pos + 50)
    sent_end   = sent_end + 1 if sent_end > 0 else citation_pos + 300
    return text[sent_start:sent_end].strip()


def _extract_case_name(soup) -> str:
    """Extract judgment name/citation from the page."""
    for selector in ['h1', '.judgment-title', 'title', '.case-title']:
        el = soup.find(selector)
        if el:
            t = el.get_text(' ', strip=True)
            if len(t) > 10:
                return t[:200]
    return ""


def _extract_judgment_text(soup) -> str:
    """Extract the full judgment body text."""
    # Try specific judgment containers first
    for cls in ['judgment-body', 'judgment-content', 'document-body', 'akn-body']:
        el = soup.find(class_=cls)
        if el:
            return el.get_text(' ', strip=True)
    # Try semantic tags
    for tag in ['article', 'main']:
        el = soup.find(tag)
        if el:
            text = el.get_text(' ', strip=True)
            if len(text) > 500:
                return text
    # Full page fallback
    return soup.get_text(' ', strip=True)


def _fetch_judgment_links(session, max_j: int, stdout) -> list:
    """Fetch the judgment listing page and extract individual judgment URLs."""
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
                # Kenya Law judgment URLs: /akn/ke/judgment/... or /judgments/YYYY/...
                if (
                    ('/akn/ke/judgment/' in href or '/judgments/' in href)
                    and href not in links
                    and 'ordering=' not in href
                    and '/all/' not in href
                ):
                    if not href.startswith('http'):
                        href = f"https://kenyalaw.org{href}"
                    links.append(href)
                    if len(links) >= max_j:
                        break
            if links:
                break
        except Exception as e:
            stdout.write(f"  Warning: could not fetch listing {listing_url}: {e}")
            continue

    return links


class Command(BaseCommand):
    help = "Scrape Kenya Law judgments and store deep jurisprudence interpretations in the DB"

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=7,
            help='Informational only — filter by date if the listing supports it (default: 7)'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would be added without saving'
        )
        parser.add_argument(
            '--max-judgments', type=int, default=30,
            help='Maximum number of judgment pages to fetch (default: 30)'
        )
        parser.add_argument(
            '--min-content-len', type=int, default=80,
            help='Minimum character length of extracted interpretation to save (default: 80)'
        )

    def handle(self, *args, **options):
        import requests
        from bs4 import BeautifulSoup
        from cases.models import Law
        from cases.rag import invalidate_law_cache

        dry_run      = options['dry_run']
        max_j        = options['max_judgments']
        min_len      = options['min_content_len']

        self.stdout.write(f"[scrape_kenyalaw] Starting — max {max_j} judgments")
        if dry_run:
            self.stdout.write("  DRY RUN — nothing will be saved")

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'HakiMkononi-scraper/2.0 (legal AI Kenya; contact@hakimkononi.co.ke)'
        })

        # ── Step 1: Get judgment URLs ─────────────────────────────────────────
        judgment_links = _fetch_judgment_links(session, max_j, self.stdout)
        self.stdout.write(f"  Found {len(judgment_links)} judgment links")

        if not judgment_links:
            self.stderr.write(
                "[scrape_kenyalaw] No judgment links found. "
                "Kenya Law may have changed their HTML structure. "
                "Check: https://kenyalaw.org/judgments/"
            )
            return

        new_sections  = 0
        skipped       = 0
        errors        = 0

        # ── Step 2: Process each judgment ────────────────────────────────────
        for i, url in enumerate(judgment_links, 1):
            self.stdout.write(f"  [{i}/{len(judgment_links)}] {url[:80]}")
            try:
                r = session.get(url, timeout=25)
                if r.status_code != 200:
                    errors += 1
                    continue

                soup = BeautifulSoup(r.text, 'html.parser')
                case_name = _extract_case_name(soup)
                text      = _extract_judgment_text(soup)

                if len(text) < 300:
                    self.stdout.write(f"    ↳ Too short ({len(text)} chars), skipping")
                    continue

                # ── Step 3: Find all law citations in judgment text ─────────
                seen_in_this_judgment = set()  # avoid duplicate rows from same judgment

                for m in CITATION_RE.finditer(text):
                    section_num = m.group(1).strip()
                    act_name    = m.group(2).strip()
                    section_key = f"{act_name}|{section_num}"

                    if section_key in seen_in_this_judgment:
                        continue
                    seen_in_this_judgment.add(section_key)

                    # ── Step 4: Extract the court's INTERPRETATION of this section ─
                    # This is the key difference from the old scraper.
                    # We don't just grab the sentence with the citation.
                    # We find what the COURT SAID about this section.
                    interp = _extract_interpretation_window(text, m.start())

                    # Prefix with case reference for traceability
                    if case_name:
                        # Extract just the neutral citation e.g. [2024] KEELC 4992
                        neutral_cite = re.search(r'\[\d{4}\]\s+[A-Z]+\s+\d+', case_name)
                        cite_ref = neutral_cite.group(0) if neutral_cite else case_name[:60]
                        content = f"Court interpretation ({cite_ref}): {interp}"
                    else:
                        content = f"Court interpretation: {interp}"

                    if len(content) < min_len:
                        continue

                    # ── Step 5: Check if this EXACT interpretation is already stored ─
                    # We match on title + section + the first 100 chars of content
                    # (same section can have multiple judgment interpretations — store all)
                    content_fingerprint = content[:100]
                    already_exists = Law.objects.filter(
                        title__icontains=act_name[:50],
                        section__iexact=f"Section {section_num}",
                        content__startswith=content_fingerprint[:80],
                    ).exists()

                    if already_exists:
                        skipped += 1
                        continue

                    category = _guess_category(act_name)

                    if not dry_run:
                        Law.objects.create(
                            title=act_name,
                            section=f"Section {section_num}",
                            content=content[:2000],
                            category=category,
                            source_url=url,
                        )

                    new_sections += 1
                    self.stdout.write(
                        f"    + [{category}] {act_name} — Section {section_num}: "
                        f"{interp[:80]}..."
                    )

                time.sleep(1.5)  # polite delay — don't hammer kenyalaw.org

            except Exception as e:
                errors += 1
                self.stderr.write(f"  Error fetching {url}: {e}")
                continue

        self.stdout.write(
            f"\n[scrape_kenyalaw] Done — "
            f"{new_sections} new interpretations added, "
            f"{skipped} already existed, "
            f"{errors} fetch errors"
        )

        # ── Step 6: Generate Gemini embeddings for new rows ───────────────────
        if new_sections > 0 and not dry_run:
            self.stdout.write("[scrape_kenyalaw] Generating embeddings for new sections...")
            try:
                from cases.rag import embed_text
                unembedded = Law.objects.filter(embedding_json='').exclude(content='')
                count = 0
                failed = 0
                for law in unembedded:
                    # Rich embedding text: title + section + full interpretation
                    embed_input = f"{law.title} {law.section}: {law.content}"
                    try:
                        vec = embed_text(embed_input)
                        if vec:
                            law.set_embedding(vec)
                            law.save(update_fields=['embedding_json'])
                            count += 1
                            # Small delay to stay within Gemini free tier
                            # (1,500 requests/day = ~1 per minute max sustained)
                            # In practice a nightly run will do 5–50 sections — fine.
                            time.sleep(0.2)
                    except Exception as e:
                        failed += 1
                        logger.warning(f"Embedding failed for Law #{law.pk}: {e}")

                self.stdout.write(
                    f"[scrape_kenyalaw] Embedded {count} new sections "
                    f"({failed} failed)"
                )

                # Invalidate the in-memory cache so next query picks up new sections
                invalidate_law_cache()

            except Exception as e:
                self.stderr.write(f"[scrape_kenyalaw] Embedding step error: {e}")
