"""
HakiMkononi API - 6-scenario integration test
Run: python test_api_scenarios.py
"""

import requests
import time
import json

BASE_URL = "https://hakimkononi.onrender.com"
SUBMIT_URL = f"{BASE_URL}/api/submit/"
STATUS_URL = f"{BASE_URL}/api/status/{{job_id}}/"


def get_sheria(r: dict) -> str:
    """Extract sheria_inasema from either nested answer dict or top level."""
    answer = r.get("answer") or {}
    if isinstance(answer, dict):
        s = answer.get("sheria_inasema") or ""
    else:
        s = str(answer)
    if not s:
        s = r.get("sheria_inasema") or ""
    return s


SCENARIOS = [
    {
        "id": 1,
        "name": "Land TRANSACTION English",
        "payload": {
            "story": "I want to buy a plot in Kiambu. The seller showed me title deed KIAMBU/001/234. Is this land clean?",
            "lang": "en",
            "county": "",
        },
        "checks": lambda r: (
            r.get("land_subtype") == "transaction"
            and any(
                kw in get_sheria(r).lower()
                for kw in ["check", "ardhisasa", "title"]
            )
            and not get_sheria(r).startswith("❌")
        ),
        "check_desc": 'land_subtype="transaction" AND sheria_inasema contains "check"/"ardhisasa"/"title" (no error)',
    },
    {
        "id": 2,
        "name": "Land DISPUTE English",
        "payload": {
            "story": "My neighbour grabbed my land and built a fence on my property. I have a title deed.",
            "lang": "en",
            "county": "",
        },
        "checks": lambda r: (
            r.get("land_subtype") == "dispute"
            and "Act" in get_sheria(r)
        ),
        "check_desc": 'land_subtype="dispute" AND sheria_inasema contains Act citations',
    },
    {
        "id": 3,
        "name": "Land TRANSACTION Swahili",
        "payload": {
            "story": "Nataka kununua kiwanja Nairobi. Muuzaji ananipa hati nambari NAIROBI/BLOCK24/123. Ardhi iko safi?",
            "lang": "sw",
            "county": "",
        },
        "checks": lambda r: (
            r.get("land_subtype") == "transaction"
            and not get_sheria(r).startswith("❌")
        ),
        "check_desc": 'land_subtype="transaction" AND sheria_inasema does NOT start with "❌"',
    },
    {
        "id": 4,
        "name": "Mode switch (paid, seller disappeared)",
        "payload": {
            "story": "I already paid the deposit but the seller disappeared with my money and won't give me the title deed.",
            "lang": "en",
            "county": "",
        },
        "checks": lambda r: (
            r.get("land_subtype") == "dispute"
            and any(
                any(kw in src.get("title", "").lower()
                    for kw in ["land", "fraud", "registration", "contract", "deposit"])
                for src in (r.get("sources") or [])
            )
            # Primary source must NOT be a rent/tenancy Act (it's ok if it appears lower in sources)
            and not any(
                kw in (r.get("sources") or [{}])[0].get("title", "").lower()
                for kw in ["distress for rent", "rent restriction"]
            )
        ),
        "check_desc": 'land_subtype="dispute" AND primary source is land/fraud/contract (not rent Act)',
    },
    {
        "id": 5,
        "name": "Employment (non-land)",
        "payload": {
            "story": "My employer fired me without notice after 3 years and refused to pay my salary.",
            "lang": "en",
            "county": "",
        },
        "checks": lambda r: (
            r.get("land_subtype") in ("", None)
            and "employment act" in get_sheria(r).lower()
        ),
        "check_desc": 'land_subtype="" AND sheria_inasema cites Employment Act',
    },
    {
        "id": 6,
        "name": "Landlord lockout (pure rental)",
        "payload": {
            "story": "My landlord locked me out of my house without notice and kept my belongings inside.",
            "lang": "en",
            "county": "",
        },
        "checks": lambda r: (
            r.get("status") == "done"
            and not get_sheria(r).startswith("❌")
            and len(get_sheria(r)) > 30
        ),
        "check_desc": 'status="done" AND sheria_inasema does NOT start with "❌" AND contains actual legal content',
    },
]


def poll_status(job_id: str, max_wait: int = 90) -> dict:
    url = STATUS_URL.format(job_id=job_id)
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "")
            if status in ("done", "error"):
                return data
            print(f"    status={status!r}, waiting 5 s …")
        except Exception as exc:
            print(f"    poll error: {exc}")
        time.sleep(5)
    return {"status": "timeout", "error": "Max wait exceeded"}


def run_scenario(s: dict) -> dict:
    print(f"\n{'='*60}")
    print(f"SCENARIO {s['id']}: {s['name']}")
    print(f"{'='*60}")

    # Submit
    try:
        resp = requests.post(SUBMIT_URL, json=s["payload"], timeout=30)
        resp.raise_for_status()
        sub = resp.json()
    except Exception as exc:
        result = {"passed": False, "error": f"Submit failed: {exc}",
                  "land_subtype": "N/A", "status": "submit_error",
                  "sheria_excerpt": "", "sources": []}
        print(f"  ❌ Submit error: {exc}")
        return result

    job_id = sub.get("job_id")
    if not job_id:
        result = {"passed": False, "error": f"No job_id in response: {sub}",
                  "land_subtype": "N/A", "status": "no_job_id",
                  "sheria_excerpt": "", "sources": []}
        print(f"  ❌ No job_id: {sub}")
        return result

    print(f"  job_id: {job_id}")

    # Poll
    data = poll_status(job_id)

    status       = data.get("status", "")
    land_subtype = data.get("land_subtype", "")
    # answer can be a dict (nested) or a string depending on API version
    answer_raw = data.get("answer") or {}
    if isinstance(answer_raw, dict):
        sheria = answer_raw.get("sheria_inasema") or ""
    else:
        sheria = str(answer_raw)
    # Also check top-level sheria_inasema as fallback
    if not sheria:
        sheria = data.get("sheria_inasema") or ""
    sources_raw  = data.get("sources", [])
    error        = data.get("error", "")

    # Normalise sources to list of dicts
    sources = []
    for src in sources_raw:
        if isinstance(src, dict):
            sources.append(src)
        elif isinstance(src, str):
            sources.append({"title": src})

    sheria_excerpt = sheria[:200]

    # Evaluate pass/fail
    try:
        passed = s["checks"](data)
    except Exception as exc:
        passed = False
        error = f"Check threw exception: {exc}"

    verdict = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {verdict}")
    print(f"  land_subtype : {land_subtype!r}")
    print(f"  status       : {status!r}")
    print(f"  sheria (200) : {sheria_excerpt!r}")
    src_titles = [s.get("title", "?") for s in sources[:3]]
    print(f"  sources      : {src_titles}")
    if error:
        print(f"  error        : {error}")

    return {
        "passed": passed,
        "land_subtype": land_subtype,
        "status": status,
        "sheria_excerpt": sheria_excerpt,
        "sources": src_titles,
        "error": error,
    }


def main():
    results = []
    for i, s in enumerate(SCENARIOS):
        if i > 0:
            print(f"\n  ⏳ Waiting 20s between tests (Groq rate limit)...")
            time.sleep(20)
        r = run_scenario(s)
        r["id"] = s["id"]
        r["name"] = s["name"]
        r["check_desc"] = s["check_desc"]
        results.append(r)

    # Summary
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    passed_count = sum(1 for r in results if r["passed"])
    print(f"\n{passed_count}/6 passed\n")

    for r in results:
        verdict = "✅ PASS" if r["passed"] else "❌ FAIL"
        print(f"  Scenario {r['id']} ({r['name']}): {verdict}")
        if not r["passed"]:
            print(f"    Expected : {r['check_desc']}")
            print(f"    Got      : land_subtype={r['land_subtype']!r}, status={r['status']!r}")
            print(f"    sheria   : {r['sheria_excerpt']!r}")
            if r["error"]:
                print(f"    error    : {r['error']}")


if __name__ == "__main__":
    main()
