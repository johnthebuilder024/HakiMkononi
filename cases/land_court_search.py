"""
cases/land_court_search.py

Searches kenyalaw.org for court judgments mentioning a specific
LR number or title number.

Used by the land due diligence pipeline to detect if land has been
involved in court cases — the most dangerous scenario for a buyer.

Usage:
    from cases.land_court_search import search_land_in_courts
    results = search_land_in_courts("KIAMBU/001/234")
    # Returns list of {case_name, url, snippet, date}
"""

import re
import logging
import requests

logger = logging.getLogger(__name__)

KENYALAW_SEARCH_URL = "https://kenyalaw.org/caselaw/cases/advanced_search/"
HEADERS = {
    'User-Agent': 'HakiMkononi-land-search/1.0 (legal AI Kenya; contact@hakimkononi.co.ke)'
}


def _normalize_lr(lr_number: str) -> str:
    """
    Clean an LR number for searching.
    Removes extra spaces, normalises slashes.
    e.g. "KIAMBU / 001 / 234" → "KIAMBU/001/234"
    """
    # Remove spaces around slashes
    s = re.sub(r'\s*/\s*', '/', lr_number.strip())
    # Collapse multiple spaces
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def search_land_in_courts(lr_number: str, max_results: int = 5) -> list:
    """
    Search kenyalaw.org for judgments mentioning this LR/title number.

    Returns list of dicts:
      [{case_name, url, snippet, date}]

    Returns [] if no cases found or search fails.
    """
    if not lr_number or len(lr_number.strip()) < 5:
        return []

    lr_clean = _normalize_lr(lr_number)
    logger.info(f"[LandSearch] Searching kenyalaw.org for: {lr_clean}")

    # Try two search terms: exact LR number and without county prefix
    search_terms = [lr_clean]
    # Also try just the parcel number portion (e.g. "001/234" from "KIAMBU/001/234")
    parts = lr_clean.split('/')
    if len(parts) >= 2:
        search_terms.append('/'.join(parts[-2:]))  # last two segments

    results = []
    seen_urls = set()

    for term in search_terms:
        try:
            resp = requests.get(
                KENYALAW_SEARCH_URL,
                params={
                    'q':             term,
                    'court':         'Environment and Land Court',
                    'ordering':      '-date_of_judgment',
                    'format':        'json',
                },
                headers=HEADERS,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get('results', [])[:max_results]:
                    url = item.get('url') or item.get('expression_frbr_uri', '')
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    results.append({
                        'case_name': item.get('title', ''),
                        'url':       url,
                        'snippet':   item.get('snippet', '')[:300],
                        'date':      item.get('date_of_judgment', ''),
                        'court':     item.get('court', ''),
                    })
        except Exception as e:
            logger.debug(f"[LandSearch] API search failed for '{term}': {e}")

        if results:
            break  # found results with first term — don't need second

    # Fallback: try a simple text search on the judgments page
    if not results:
        try:
            resp = requests.get(
                "https://kenyalaw.org/judgments/",
                params={
                    'search': lr_clean,
                    'ordering': '-date_of_judgment',
                },
                headers=HEADERS,
                timeout=15,
            )
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, 'html.parser')
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if '/judgments/' in href and href not in seen_urls:
                        text = a.get_text(' ', strip=True)
                        # Only include if the LR number appears in the link text or nearby
                        parent_text = (a.parent.get_text(' ', strip=True) if a.parent else '')
                        if any(part in parent_text for part in parts[-2:]):
                            if not href.startswith('http'):
                                href = f"https://kenyalaw.org{href}"
                            seen_urls.add(href)
                            results.append({
                                'case_name': text[:150],
                                'url':       href,
                                'snippet':   parent_text[:300],
                                'date':      '',
                                'court':     'Kenya',
                            })
                            if len(results) >= max_results:
                                break
        except Exception as e:
            logger.debug(f"[LandSearch] HTML fallback failed: {e}")

    logger.info(f"[LandSearch] Found {len(results)} cases for '{lr_clean}'")
    return results[:max_results]


def format_court_results_for_ai(results: list, lr_number: str, lang: str = 'en') -> str:
    """
    Format search results as text to inject into the AI context.
    Returns empty string if no results found.
    """
    if not results:
        if lang == 'sw':
            return (
                f"UTAFUTAJI WA KESI ZA MAHAKAMA: Hakuna kesi zilizoonekana kwa LR nambari '{lr_number}' "
                f"kwenye kenyalaw.org. Hii ni ishara nzuri — lakini thibitisha kwenye Ardhisasa pia."
            )
        return (
            f"COURT CASE SEARCH: No published judgments found for LR number '{lr_number}' "
            f"on kenyalaw.org. This is a good sign — but also verify on Ardhisasa."
        )

    lines = []
    if lang == 'sw':
        lines.append(
            f"⚠️ KESI ZA MAHAKAMA ZILIZOPATIKANA kwa '{lr_number}': "
            f"Ardhi hii imeonekana katika kesi {len(results)} za mahakama iliyochapishwa."
        )
    else:
        lines.append(
            f"⚠️ COURT CASES FOUND for '{lr_number}': "
            f"This land appears in {len(results)} published court judgment(s). "
            f"This is a serious red flag — the buyer must investigate before paying."
        )

    for i, r in enumerate(results, 1):
        lines.append(
            f"\n{i}. {r['case_name']}"
            + (f" ({r['date']})" if r['date'] else "")
            + (f"\n   {r['snippet'][:200]}" if r['snippet'] else "")
            + (f"\n   URL: {r['url']}" if r['url'] else "")
        )

    return '\n'.join(lines)
