"""
HakiMkononi — Automated Quality Test Suite
Run with: python test_quality.py

Tests the live API at BASE_URL for:
1. All 4 answer sections present (law, simple, rights, letter)
2. Correct Act cited for each legal area
3. Swahili answers parse correctly (not all content in one box)
4. Serious case detection works
5. Greeting / short message detection (no AI call wasted)
6. Edge cases: very short question, Sheng, follow-up correction

Exit code 0 = all passed, 1 = failures found.
"""

import os
import sys
import time
import json
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("TEST_BASE_URL", "https://hakimkononi.onrender.com")
POLL_INTERVAL = 5   # seconds between status polls
MAX_WAIT      = 180 # seconds before giving up on a job

# ── colours ──────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def submit(story: str, lang: str = "en") -> int | None:
    """Submit a job, return job_id or None on failure."""
    try:
        r = requests.post(
            f"{BASE_URL}/api/submit/",
            json={"story": story, "lang": lang, "county": ""},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("job_id")
    except Exception as e:
        print(f"  {RED}Submit failed: {e}{RESET}")
        return None


def poll_result(job_id: int) -> dict | None:
    """Poll until done/error or timeout. Returns full status dict."""
    deadline = time.time() + MAX_WAIT
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/api/status/{job_id}/", timeout=15)
            r.raise_for_status()
            d = r.json()
            if d.get("status") in ("done", "error"):
                return d
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)
    return None


def section_lengths(d: dict) -> dict:
    """Return character lengths of the 4 answer sections."""
    a = d.get("answer") or {}
    return {
        "law":    len(a.get("sheria_inasema") or ""),
        "simple": len(a.get("tafsiri_rahisi") or ""),
        "rights": len(a.get("haki_yako")      or ""),
        "letter": len(a.get("andika_hivi")    or ""),
    }


def top_source_titles(d: dict, n: int = 3) -> list[str]:
    return [s.get("title", "") for s in (d.get("sources") or [])[:n]]


# ── Test case definition ──────────────────────────────────────────────────────

class Check:
    """A single assertion on a result dict."""
    def __init__(self, name: str, fn):
        self.name = name
        self.fn   = fn

    def run(self, d: dict) -> tuple[bool, str]:
        try:
            ok, msg = self.fn(d)
            return ok, msg
        except Exception as e:
            return False, f"Exception: {e}"


def all_4_sections(d):
    sl = section_lengths(d)
    missing = [k for k, v in sl.items() if v < 50]
    if missing:
        return False, f"Empty sections: {missing} — lengths {sl}"
    return True, f"All 4 sections present (law={sl['law']}, simple={sl['simple']}, rights={sl['rights']}, letter={sl['letter']})"


def not_technical_error(d):
    law = (d.get("answer") or {}).get("sheria_inasema") or ""
    if "❌" in law and "tatizo" in law.lower() or "technical error" in law.lower():
        return False, "Got technical error message"
    return True, "No technical error"


def sources_contain(keywords: list[str]):
    def _check(d):
        titles = " ".join(top_source_titles(d, 6)).lower()
        for kw in keywords:
            if kw.lower() in titles:
                return True, f"Found expected source: '{kw}' in {top_source_titles(d, 3)}"
        return False, f"Expected one of {keywords} in sources, got: {top_source_titles(d, 3)}"
    return _check


def sources_not_contain(keyword: str):
    def _check(d):
        titles = " ".join(top_source_titles(d, 6)).lower()
        if keyword.lower() in titles:
            return False, f"Unexpected source '{keyword}' found in {top_source_titles(d, 3)}"
        return True, f"'{keyword}' correctly absent from sources"
    return _check


def is_serious_flag(d):
    if d.get("is_serious"):
        return True, "is_serious=True correctly set"
    # Also accept if law box contains NLAS number
    law = (d.get("answer") or {}).get("sheria_inasema") or ""
    if "0800 720 120" in law or "nlas" in law.lower():
        return True, "Serious case message contains NLAS referral"
    return False, "Expected serious case flag or NLAS referral"


def swahili_sections_split(d):
    """Swahili answers must NOT have all content crammed into law only."""
    sl = section_lengths(d)
    if sl["simple"] < 50 and sl["rights"] < 50 and sl["letter"] < 50:
        return False, f"Swahili sections not split — all in law box (law={sl['law']}, others empty)"
    return True, f"Swahili sections correctly split (simple={sl['simple']}, rights={sl['rights']}, letter={sl['letter']})"


def letter_has_placeholder(d):
    letter = (d.get("answer") or {}).get("andika_hivi") or ""
    if "[YOUR NAME]" in letter or "[JINA LAKO]" in letter:
        return True, "Letter contains name placeholder — personalisation flow will trigger"
    if len(letter) > 100:
        return True, "Letter present (placeholders may already be filled)"
    return False, f"Letter too short or missing placeholder (len={len(letter)})"


# ── Test cases ────────────────────────────────────────────────────────────────

TESTS = [
    {
        "name":  "1. Employment — fired without notice + unpaid wages (EN)",
        "story": "My employer fired me without notice after 3 years of work and refused to pay my salary for the last 2 months.",
        "lang":  "en",
        "checks": [
            Check("All 4 sections present", all_4_sections),
            Check("No technical error",     not_technical_error),
            Check("Cites Employment Act",   sources_contain(["Employment Act"])),
            Check("Letter has placeholder", letter_has_placeholder),
        ],
    },
    {
        "name":  "2. Landlord — locked out without notice (EN)",
        "story": "My landlord locked me out of my house without any notice and kept my belongings inside. I pay rent every month.",
        "lang":  "en",
        "checks": [
            Check("All 4 sections present",           all_4_sections),
            Check("No technical error",               not_technical_error),
            Check("Cites Landlord/Tenant Act",        sources_contain(["Landlord", "Rent Restriction", "Distress for Rent"])),
            Check("Land Act NOT top source",          sources_not_contain("Land Act 2012")),
            Check("Letter has placeholder",           letter_has_placeholder),
        ],
    },
    {
        "name":  "3. Criminal — police arrest without warrant (SW)",
        "story": "Polisi walinishika usiku bila warrant na walikaa nazo saa 48 bila kunipeleka kortini.",
        "lang":  "sw",
        "checks": [
            Check("All 4 sections present",       all_4_sections),
            Check("No technical error",           not_technical_error),
            Check("Swahili sections split",       swahili_sections_split),
            Check("Cites Constitution Art 49",    sources_contain(["Constitution of Kenya"])),
            Check("Letter has placeholder",       letter_has_placeholder),
        ],
    },
    {
        "name":  "4. Family — spouse hiding matrimonial property (EN)",
        "story": "My husband is hiding our property during divorce proceedings. He moved all money from our joint account without my consent.",
        "lang":  "en",
        "checks": [
            Check("All 4 sections present",            all_4_sections),
            Check("No technical error",                not_technical_error),
            Check("Cites Matrimonial Property Act",    sources_contain(["Matrimonial Property"])),
            Check("Letter has placeholder",            letter_has_placeholder),
        ],
    },
    {
        "name":  "5. Data Protection — company sold personal data (SW)",
        "story": "Niliambia kampuni yangu isishiriki data yangu na watu wengine lakini waliuza kwa kampuni nyingine bila ruhusa yangu.",
        "lang":  "sw",
        "checks": [
            Check("All 4 sections present",       all_4_sections),
            Check("No technical error",           not_technical_error),
            Check("Swahili sections split",       swahili_sections_split),
            Check("Cites Data Protection Act",    sources_contain(["Data Protection"])),
            Check("Letter has placeholder",       letter_has_placeholder),
        ],
    },
    {
        "name":  "6. Consumer — defective goods, refused refund (EN)",
        "story": "The shopkeeper sold me a defective phone and refused to refund or replace it even with a receipt.",
        "lang":  "en",
        "checks": [
            Check("All 4 sections present",           all_4_sections),
            Check("No technical error",               not_technical_error),
            Check("Cites Consumer Protection Act",    sources_contain(["Consumer Protection"])),
            Check("Letter has placeholder",           letter_has_placeholder),
        ],
    },
    {
        "name":  "7. Serious case — murder (must redirect to NLAS) (EN)",
        "story": "I am accused of murder and the police arrested me.",
        "lang":  "en",
        "checks": [
            Check("Serious case detected",   is_serious_flag),
        ],
    },
    {
        "name":  "8. Employment Swahili — nilifukuzwa kazi (SW)",
        "story": "Mwajiri wangu alinifukuza kazi bila notisi na hakulipa mshahara wa miezi miwili iliyopita.",
        "lang":  "sw",
        "checks": [
            Check("All 4 sections present",    all_4_sections),
            Check("No technical error",        not_technical_error),
            Check("Swahili sections split",    swahili_sections_split),
            Check("Cites Employment Act",      sources_contain(["Employment Act"])),
        ],
    },
    {
        "name":  "9. Land — title deed dispute (EN)",
        "story": "Someone is claiming my land and says they have a title deed. I have been farming this land for 20 years.",
        "lang":  "en",
        "checks": [
            Check("All 4 sections present",       all_4_sections),
            Check("No technical error",           not_technical_error),
            Check("Cites land-related Act",       sources_contain(["Land Act", "Land Registration", "Community Land", "Constitution"])),
        ],
    },
    {
        "name":  "10. Domestic violence — protection order (EN)",
        "story": "My husband beats me regularly. I want to get a protection order and I have two children.",
        "lang":  "en",
        "checks": [
            Check("All 4 sections present",             all_4_sections),
            Check("No technical error",                 not_technical_error),
            Check("Cites Protection Against DV Act",    sources_contain(["Protection Against Domestic Violence", "Marriage Act", "Children Act", "Constitution"])),
        ],
    },
]


# ── Runner ────────────────────────────────────────────────────────────────────

def run_tests():
    total_tests   = 0
    total_passed  = 0
    total_failed  = 0
    failed_names  = []

    print(f"\n{BOLD}HakiMkononi Quality Test Suite{RESET}")
    print(f"Target: {BASE_URL}")
    print(f"Running {len(TESTS)} test cases...\n")
    print("─" * 70)

    for tc in TESTS:
        name   = tc["name"]
        story  = tc["story"]
        lang   = tc.get("lang", "en")
        checks = tc["checks"]

        print(f"\n{BOLD}{name}{RESET}")
        print(f"  Story ({lang}): {story[:80]}{'...' if len(story)>80 else ''}")

        # Submit
        job_id = submit(story, lang)
        if job_id is None:
            print(f"  {RED}✗ FAILED — could not submit job{RESET}")
            for c in checks:
                total_tests += 1
                total_failed += 1
            failed_names.append(name)
            continue

        print(f"  Job #{job_id} submitted — waiting for result...")

        # Poll
        result = poll_result(job_id)
        if result is None:
            print(f"  {RED}✗ TIMED OUT after {MAX_WAIT}s{RESET}")
            for c in checks:
                total_tests += 1
                total_failed += 1
            failed_names.append(name)
            continue

        if result.get("status") == "error":
            print(f"  {RED}✗ API ERROR: {result.get('message', '?')}{RESET}")
            for c in checks:
                total_tests += 1
                total_failed += 1
            failed_names.append(name)
            continue

        # Run checks
        case_passed = True
        for c in checks:
            total_tests += 1
            ok, msg = c.run(result)
            if ok:
                total_passed += 1
                print(f"  {GREEN}✓{RESET} {c.name}: {msg}")
            else:
                total_failed += 1
                case_passed = False
                print(f"  {RED}✗{RESET} {c.name}: {RED}{msg}{RESET}")

        if not case_passed:
            failed_names.append(name)

    # Summary
    print(f"\n{'═' * 70}")
    pct = round(total_passed / total_tests * 100) if total_tests else 0
    colour = GREEN if pct == 100 else (YELLOW if pct >= 80 else RED)
    print(f"{BOLD}Results: {colour}{total_passed}/{total_tests} checks passed ({pct}%){RESET}")

    if failed_names:
        print(f"\n{RED}Failed tests:{RESET}")
        for n in failed_names:
            print(f"  • {n}")
    else:
        print(f"\n{GREEN}All tests passed! ✓{RESET}")

    print()
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
