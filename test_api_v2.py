import requests
import time
import json

BASE = "https://hakimkononi.onrender.com"

SCENARIOS = [
    {
        "name": "SCENARIO 1 - Land TRANSACTION (English)",
        "story": "I want to buy a plot in Kiambu. The seller showed me title deed KIAMBU/001/234. Is this land clean?",
        "lang": "en",
        "expected_subtype": "transaction",
    },
    {
        "name": "SCENARIO 2 - Land DISPUTE (English)",
        "story": "My neighbour has grabbed my land and built a fence on my property. I have a title deed.",
        "lang": "en",
        "expected_subtype": "dispute",
    },
    {
        "name": "SCENARIO 3 - Land TRANSACTION (Swahili)",
        "story": "Nataka kununua kiwanja Nairobi. Muuzaji ananipa hati nambari NAIROBI/BLOCK24/123. Ardhi iko safi?",
        "lang": "sw",
        "expected_subtype": "transaction",
    },
    {
        "name": "SCENARIO 4 - Mode switch (transaction->dispute)",
        "story": "I already paid the deposit but the seller has disappeared with my money and won't give me the title deed.",
        "lang": "en",
        "expected_subtype": "dispute",
    },
    {
        "name": "SCENARIO 5 - Employment (non-land)",
        "story": "My employer fired me without notice after 3 years and refused to pay my salary.",
        "lang": "en",
        "expected_subtype": "",
    },
    {
        "name": "SCENARIO 6 - Landlord DISPUTE (not a purchase)",
        "story": "My landlord locked me out of my house without notice and kept my belongings.",
        "lang": "en",
        "expected_subtype": "dispute",
    },
]

# Nested inside result["answer"]
ANSWER_BOXES = ["sheria_inasema", "hatua_za_kuchukua", "tafsiri_rahisi", "rasilimali"]
MAX_WAIT = 90
POLL_INTERVAL = 5


def run_scenario(s):
    print()
    print("=" * 70)
    print(s["name"])
    print("=" * 70)

    # 1. POST /api/submit/
    payload = {"story": s["story"], "lang": s["lang"]}
    try:
        r = requests.post(f"{BASE}/api/submit/", json=payload, timeout=30)
        submit_http = r.status_code
        data = r.json()
    except Exception as e:
        print(f"Submit FAILED: {e}")
        return

    print(f"Submit HTTP status : {submit_http}")

    if submit_http not in (200, 201, 202):
        print(f"Submit error body  : {data}")
        return

    job_id = data.get("job_id")
    print(f"job_id             : {job_id}")

    if not job_id:
        print("No job_id in response — cannot poll")
        return

    # 2. Poll /api/status/{job_id}/
    elapsed = 0
    result = None

    while elapsed < MAX_WAIT:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        try:
            sr = requests.get(f"{BASE}/api/status/{job_id}/", timeout=30)
            sdata = sr.json()
        except Exception as e:
            print(f"  [{elapsed}s] Poll error: {e}")
            continue

        status = sdata.get("status", "unknown")
        print(f"  [{elapsed}s] status={status}")

        if status in ("done", "error"):
            result = sdata
            break

    if result is None:
        print(f"FINAL STATUS: TIMEOUT after {MAX_WAIT}s")
        return

    # 3. Report
    print(f"\nFINAL STATUS       : {result.get('status')}")

    land_subtype = result.get("land_subtype", "(missing)")
    if land_subtype is None:
        land_subtype = ""
    expected = s["expected_subtype"]
    match_icon = "PASS" if str(land_subtype) == str(expected) else "FAIL"
    print(f"land_subtype       : '{land_subtype}'  (expected: '{expected}')  [{match_icon}]")

    # Answer boxes are nested under "answer"
    answer_obj = result.get("answer") or {}

    all_non_empty = True
    print("\nAnswer boxes (inside result['answer']):")
    for box in ANSWER_BOXES:
        val = answer_obj.get(box) or ""
        empty = not val.strip()
        if empty:
            all_non_empty = False
        flag = "NON-EMPTY" if not empty else "EMPTY    "
        print(f"  {box:22s}: [{flag}]  len={len(val)}")

    print(f"\nAll 4 boxes non-empty : {'YES' if all_non_empty else 'NO'}")

    sheria  = answer_obj.get("sheria_inasema") or ""
    tafsiri = answer_obj.get("tafsiri_rahisi") or ""
    print(f"\nsheria_inasema  first 120 chars:\n  '{sheria[:120]}'")
    print(f"\ntafsiri_rahisi  first  80 chars:\n  '{tafsiri[:80]}'")

    if result.get("error"):
        print(f"\nERROR FIELD: {result['error']}")

    # Also show elapsed_seconds for transparency
    if result.get("elapsed_seconds"):
        print(f"\nServer elapsed_seconds: {result['elapsed_seconds']}")


def main():
    for s in SCENARIOS:
        run_scenario(s)

    print()
    print("=" * 70)
    print("ALL SCENARIOS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
