"""
Quick RAG-only test: verifies that find_relevant_laws returns on-topic
sections for Swahili, English and Sheng queries — no real AI calls made.
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sheria_ai.settings')
django.setup()

from cases.rag import find_relevant_laws

TESTS = [
    {
        "label": "Employment — Kiswahili",
        "story": (
            "Mwajiri wangu alinifukuza kazi bila notisi na bila kulipa mshahara "
            "wangu wa mwisho. Nilifanya kazi miaka 5 na hakuna chochote alichonipa."
        ),
        "lang": "sw",
        "expect_cats": {"employment", "constitution"},
        "must_have_cat": "employment",   # at least one employment section required
    },
    {
        "label": "Land / Landlord — English",
        "story": (
            "My landlord changed the locks and threw my belongings outside without "
            "giving me any notice. I have been paying rent on time for 2 years."
        ),
        "lang": "en",
        "expect_cats": {"landlord_tenant", "land", "constitution"},
        "must_have_cat": "land",
    },
    {
        "label": "Criminal — Sheng",
        "story": (
            "Polisi walinishika bila warrant, wakaniweka ndani masaa 48 bila "
            "kunipeleka kortini. Hawakunitajia charges wala hawakuniambia rights zangu."
        ),
        "lang": "sheng",
        "expect_cats": {"criminal_procedure", "constitution"},
        "must_have_cat": "criminal_procedure",
    },
    {
        "label": "Criminal — Sheng (karao slang)",
        "story": (
            "Karao amenishika bila kunisomea my rights. "
            "Polisi hafai kufanya ivo. Nifanye nini?"
        ),
        "lang": "sheng",
        "expect_cats": {"criminal_procedure", "constitution"},
        "must_have_cat": "criminal_procedure",
    },
        "story": (
            "Boss wangu alinifukuza job bila notice, akasema redundancy but "
            "alichukua mtu mwingine mahali pangu. Mshahara wa last month hakulipa."
        ),
        "lang": "sheng",
        "expect_cats": {"employment", "constitution"},
        "must_have_cat": "employment",
    },
]

print("=== HakiMkononi Language Test (RAG only, no AI calls) ===")
print("-" * 70)

passed = 0
failed = 0
results_lines = []

for i, t in enumerate(TESTS, 1):
    label = t["label"]
    story = t["story"]
    lang  = t["lang"]
    expect_cats  = t["expect_cats"]
    must_have    = t["must_have_cat"]

    print(f"[{i}/{len(TESTS)}] {label}")
    print(f"  Story: {story[:80]}...")
    print(f"  Lang : {lang}")

    sections = find_relevant_laws(story, top_n=6, category_boost=['constitution'])
    cats = [s.category for s in sections]

    print(f"  RAG  : {len(sections)} sections | cats = {cats}")
    for s in sections:
        print(f"    {s.category:<20} {s.title[:55]} — {s.section}")

    # Check 1: no unexpected categories
    unexpected = [c for c in cats if c not in expect_cats]
    # Check 2: must have at least one primary-topic section
    has_primary = any(c == must_have for c in cats)

    if unexpected:
        print(f"  FAIL: unexpected categories {unexpected}")
        failed += 1
        results_lines.append(f"FAIL [{label}]: unexpected cats {unexpected}")
    elif not has_primary:
        print(f"  FAIL: no '{must_have}' section returned (all constitution?)")
        failed += 1
        results_lines.append(f"FAIL [{label}]: no '{must_have}' section in results")
    else:
        print(f"  PASS: has '{must_have}' + no off-topic sections")
        passed += 1
        results_lines.append(f"PASS [{label}]")

    print()

print("-" * 70)
print(f"Result: {passed} passed, {failed} failed out of {len(TESTS)} tests")

output_path = os.path.join(os.path.dirname(__file__), 'test_lang_result.txt')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(results_lines))
print(f"Results saved to: {output_path}")
