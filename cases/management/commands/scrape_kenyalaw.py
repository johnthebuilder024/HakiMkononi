"""
Management command: scrape_kenyalaw

Fetches recent judgments from kenyalaw.org and saves new Law sections
to the database, then triggers Gemini embedding generation for new rows.

Usage:
  python manage.py scrape_kenyalaw          # last 7 days
  python manage.py scrape_kenyalaw --days 30
  python manage.py scrape_kenyalaw --dry-run

Render cron job (add to render.yaml):
  - type: cron
    name: scrape-kenyalaw
    schedule: "0 2 * * *"        # 2am Nairobi time daily
    command: python manage.py scrape_kenyalaw

How it works:
  1. Fetches the Kenya Law "Recent Judgments" RSS / search page
  2. Parses judgment titles and URLs
  3. For each new judgment: fetches the text, extracts cited law sections
  4. Saves new Law rows (sections not already in the DB) with source_url
  5. Generates Gemini embeddings for new rows
"""

import re
import time
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


KENYALAW_SEARCH_URL = "https://www.kenyalaw.org:8181/exist/rest/db/kenyalex/Kenya/Legislation/"
KENYALAW_RECENT_URL = "https://new.kenyalaw.org/judgments/?ordering=-date_of_judgment"

# Regex for common law section citations in judgment text
CITATION_RE = re.compile(
    r'(?:section|article|s\.?)\s+(\d+[A-Z]?(?:\([a-z0-9]+\))?)'
    r'\s+(?:of\s+)?(?:the\s+)?([A-Z][A-Za-z &,()]+?Act\s+\d{4})',
    re.IGNORECASE,
)

# Known category mapping by act name keywords
ACT_CATEGORY = {
    'constitution':         'constitution',
    'employment':           'employment',
    'labour':               'employment',
    'rent restriction':     'landlord_tenant',
    'landlord':             'landlord_tenant',
    'criminal procedure':   'criminal_procedure',
    'penal code':           'criminal_procedure',
    'children':             'children',
    'land act':             'land',
    'succession':           'land',
    'consumer':             'consumer',
    'data protection':      'other',
    'sexual offences':      'other',
    'domestic violence':    'other',
}


def _guess_category(act_name: str) -> str:
    act_lower = act_name.lower()
    for keyword, category in ACT_CATEGORY.items():
        if keyword in act_lower:
            return category
    return 'other'


class Command(BaseCommand):
    help = "Scrape recent Kenya Law judgments and add newly cited law sections to the DB"

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=7,
            help='Scrape judgments from the last N days (default: 7)'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would be added without actually saving'
        )
        parser.add_argument(
            '--max-judgments', type=int, default=20,
            help='Maximum number of judgment pages to fetch (default: 20)'
        )

    def handle(self, *args, **options):
        import requests
        from bs4 import BeautifulSoup
        from cases.models import Law

        days        = options['days']
        dry_run     = options['dry_run']
        max_j       = options['max_judgments']

        self.stdout.write(f"[scrape_kenyalaw] Starting — last {days} days, max {max_j} judgments")
        if dry_run:
            self.stdout.write("  DRY RUN — nothing will be saved")

        # ── Fetch recent judgment list ────────────────────────────────
        try:
            resp = requests.get(
                KENYALAW_RECENT_URL,
                timeout=30,
                headers={'User-Agent': 'HakiMkononi-scraper/1.0 (legal AI Kenya)'},
            )
            resp.raise_for_status()
        except Exception as e:
            self.stderr.write(f"[scrape_kenyalaw] Failed to fetch judgment list: {e}")
            return

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Extract judgment links — the site uses <a> with /judgments/ paths
        judgment_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/judgments/' in href and href not in judgment_links:
                if not href.startswith('http'):
                    href = f"https://new.kenyalaw.org{href}"
                judgment_links.append(href)
                if len(judgment_links) >= max_j:
                    break

        self.stdout.write(f"  Found {len(judgment_links)} judgment links")

        new_sections = 0
        skipped      = 0

        for i, url in enumerate(judgment_links):
            try:
                r = requests.get(url, timeout=20,
                                 headers={'User-Agent': 'HakiMkononi-scraper/1.0'})
                if r.status_code != 200:
                    continue
                j_soup = BeautifulSoup(r.text, 'html.parser')

                # Extract text content
                body = j_soup.find('div', class_='judgment-body') or j_soup.find('main') or j_soup
                text = body.get_text(' ', strip=True)

                # Find all law citations in the text
                citations = CITATION_RE.findall(text)

                for section_num, act_name in citations:
                    act_name = act_name.strip()
                    section  = f"Section {section_num.strip()}"

                    # Check if already in DB
                    exists = Law.objects.filter(
                        title__icontains=act_name[:50],
                        section__iexact=section,
                    ).exists()

                    if exists:
                        skipped += 1
                        continue

                    # Extract the surrounding sentence as the content
                    # Find the sentence in the text that contains this citation
                    pattern = re.compile(
                        re.escape(f"section {section_num}") + r'.{0,300}',
                        re.IGNORECASE
                    )
                    match = pattern.search(text)
                    content = match.group(0).strip() if match else f"Cited in: {url}"

                    category = _guess_category(act_name)

                    if not dry_run:
                        Law.objects.create(
                            title=act_name,
                            section=section,
                            content=content[:2000],
                            category=category,
                            source_url=url,
                        )

                    new_sections += 1
                    self.stdout.write(f"  + {act_name} — {section}")

                time.sleep(1)  # be polite to kenyalaw.org

            except Exception as e:
                self.stderr.write(f"  Error fetching {url}: {e}")
                continue

        self.stdout.write(
            f"[scrape_kenyalaw] Done — {new_sections} new sections added, {skipped} already existed"
        )

        # ── Trigger embedding generation for new rows ─────────────────
        if new_sections > 0 and not dry_run:
            self.stdout.write("[scrape_kenyalaw] Generating embeddings for new sections...")
            try:
                from cases.rag import embed_text
                unembedded = Law.objects.filter(embedding_json='').exclude(content='')
                count = 0
                for law in unembedded:
                    text = f"{law.title} {law.section}: {law.content}"
                    vec = embed_text(text)
                    if vec:
                        law.set_embedding(vec)
                        law.save(update_fields=['embedding_json'])
                        count += 1
                self.stdout.write(f"[scrape_kenyalaw] Embedded {count} new sections")
            except Exception as e:
                self.stderr.write(f"[scrape_kenyalaw] Embedding error: {e}")
