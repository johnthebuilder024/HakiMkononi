"""
RAG Engine — Retrieval-Augmented Generation for HakiMkononi.

Flow:
  1. Convert user story to a vector (embedding)
  2. Compare against all law section embeddings in the DB
  3. Return the top N most relevant law sections
  4. Feed ONLY those sections to GPT — no hallucination possible

The AI can only cite what is in our database.
"""

import json
import os
import time
import numpy as np
import requests as _requests

# ── Google Gemini Embedding API — free tier, no credit card ──────────────────
# Model: gemini-embedding-001  (3072-dim, free on Google AI Studio)
_GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"

# ── Law section in-memory cache ───────────────────────────────────────────────
# Loaded once at first query, then reused forever (or until invalidated).
# Each entry is a plain dict — no ORM overhead, no DB hit per question.
# Structure: {id, title, section, category, source_url, vec (np.ndarray)}
#
# RAM estimate: 4,231 sections × 3,072 floats × 4 bytes ≈ 52 MB
# Well within Render's 512 MB free-tier limit now that torch is gone.
#
# To force a reload (e.g. after loading new laws) call: invalidate_law_cache()

_law_cache: list = []           # list of dicts, one per section
_law_cache_loaded: bool = False  # True once loaded
_law_cache_lock = __import__('threading').Lock()


def _load_law_cache():
    """Load all embedded law sections from DB into memory in chunks to avoid OOM."""
    global _law_cache, _law_cache_loaded
    from cases.models import Law
    print("[RAG] Loading law sections into memory cache (chunked)...")

    # Get all IDs first — lightweight
    ids = list(
        Law.objects.exclude(embedding_json='')
                   .exclude(embedding_json__isnull=True)
                   .values_list('id', flat=True)
    )

    cache = []
    CHUNK = 100  # process 100 rows at a time — keeps peak RAM low
    for i in range(0, len(ids), CHUNK):
        chunk_ids = ids[i:i + CHUNK]
        for r in Law.objects.filter(id__in=chunk_ids).values(
            'id', 'title', 'section', 'category', 'source_url', 'embedding_json'
        ):
            try:
                vec = np.array(json.loads(r['embedding_json']), dtype=np.float32)
                cache.append({
                    'id':         r['id'],
                    'title':      r['title'],
                    'section':    r['section'],
                    'category':   r['category'],
                    'source_url': r['source_url'],
                    'vec':        vec,
                })
            except Exception:
                continue

    _law_cache = cache
    _law_cache_loaded = True
    print(f"[RAG] ✅ Cached {len(cache)} law sections in memory.")


def _get_law_cache() -> list:
    """Return the cache, loading it first if needed. Thread-safe."""
    global _law_cache_loaded
    if not _law_cache_loaded:
        with _law_cache_lock:
            if not _law_cache_loaded:   # double-checked locking
                _load_law_cache()
    return _law_cache


def invalidate_law_cache():
    """
    Call this after adding/updating law sections so the next query
    reloads from DB. E.g. after running load_pdf management command.
    """
    global _law_cache, _law_cache_loaded
    with _law_cache_lock:
        _law_cache = []
        _law_cache_loaded = False
    print("[RAG] Law cache invalidated — will reload on next query.")


# ── Slang keyword cache — refreshes every 5 minutes ──────────────────────────
_slang_cache: dict = {}
_slang_cache_time: float = 0.0
_SLANG_CACHE_TTL = 300


def _load_slang_from_db() -> dict:
    global _slang_cache, _slang_cache_time
    now = time.time()
    if now - _slang_cache_time < _SLANG_CACHE_TTL and _slang_cache:
        return _slang_cache
    try:
        from cases.models import SlangKeyword
        result: dict = {}
        for kw in SlangKeyword.objects.filter(active=True).values('word', 'topic'):
            result.setdefault(kw['topic'], []).append(kw['word'])
        _slang_cache      = result
        _slang_cache_time = now
        return result
    except Exception:
        return _slang_cache or {}


def embed_text(text: str) -> list:
    """Convert a string to a vector using Google Gemini embedding API (free, no RAM cost)."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set — cannot generate embeddings.")
    resp = _requests.post(
        f"{_GEMINI_EMBED_URL}?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={
            "model": "models/gemini-embedding-001",
            "content": {"parts": [{"text": text}]},
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]


def cosine_similarity(vec_a: list, vec_b: list) -> float:
    """Dot product of two normalised vectors = cosine similarity."""
    a = np.array(vec_a)
    b = np.array(vec_b)
    return float(np.dot(a, b))


# ── Query expansion map — Swahili/Sheng → English legal concepts ─────────────
# When the embedding model sees these Swahili words it gets poor similarity.
# We append English equivalents so the embedding captures the legal intent.
_EXPANSION_MAP = {
    # Employment
    'mwajiri':          'employer',
    'mfanyakazi':       'employee',
    'kazi':             'employment work job',
    'mshahara':         'salary wages payment',
    'mishahara':        'wages salary',
    'kuachishwa':       'dismissed fired termination',
    'kufukuzwa':        'dismissed fired termination',
    'alinifukuza':      'fired dismissed without notice',
    'alinifuta':        'fired dismissed termination',
    'nilifukuzwa':      'I was fired dismissed',
    'nilifutwa':        'I was fired dismissed',
    'notisi':           'notice termination',
    'mkataba':          'contract employment',
    'likizo':           'leave annual leave',
    'hakulipa':         'did not pay wages unpaid',
    'hawakumulipa':     'did not pay wages unpaid',
    'malipo':           'payment wages salary',
    'redundancy':       'redundancy retrenchment',
    # Criminal / Police
    'polisi':           'police officer arrest',
    'askari':           'police officer security',
    'afande':           'police officer',
    'karao':            'police officer arrest',
    'karau':            'police officer arrest',
    'sanse':            'police officer arrest',
    'makarao':          'police officers arrest',
    'kukamatwa':        'arrested detained custody',
    'kushikwa':         'arrested detained',
    'walinishika':      'arrested me detained',
    'amenishika':       'arrested me detained',
    'wamenishika':      'arrested detained',
    'kizuizini':        'detained custody',
    'dhamana':          'bail bond release',
    'mashtaka':         'charges prosecution offence',
    'gereza':           'prison jail custody',
    'seleli':           'cell jail detained',
    'warrant':          'warrant arrest',
    'haki zangu':       'my rights constitutional rights',
    'rights zangu':     'my rights constitutional rights',
    'hawakusomea':      'did not read rights Miranda',
    'hawakunitajia':    'did not inform rights',
    'kortini':          'court magistrate',
    # Land / Landlord
    'mwenye nyumba':    'landlord property owner',
    'mpangaji':         'tenant renter',
    'pango':            'rent rental',
    'kodi':             'rent rental',
    'ardhi':            'land property',
    'kiwanja':          'plot land',
    'hati':             'title deed registration',
    'mmiliki':          'owner landlord',
    'alinifunga':       'locked out eviction',
    'amenifunga':       'locked out eviction',
    'kukimbia':         'eviction removal',
    'nyumba':           'house property tenant',
    # Family / Marriage / Divorce
    'talaka':           'divorce marriage dissolution',
    'ndoa':             'marriage matrimonial',
    'mke':              'wife spouse marriage',
    'mume':             'husband spouse marriage',
    'mirathi':          'inheritance succession estate',
    'urithi':           'inheritance succession property',
    'ulezi':            'custody children guardianship',
    'watoto':           'children custody minor',
    'dem wangu':        'wife girlfriend spouse',
    'buda wangu':       'husband boyfriend spouse',
    'mali yetu':        'shared property matrimonial assets',
    'anaficha mali':    'hiding property matrimonial assets',
    # Domestic violence
    'ananipiga':        'assault domestic violence beating',
    'alinipiga':        'assaulted domestic violence',
    'wananipiga':       'assault domestic violence',
    'kunidhulumu':      'abuse domestic violence harassment',
    'jeuri ya nyumbani': 'domestic violence abuse',
    'ukatili':          'violence abuse domestic',
    'kuteswa':          'torture abuse domestic violence',
    # Data protection
    'data yangu':       'personal data privacy protection',
    'wanashare data':   'sharing personal data consent',
    'kampuni imeshare': 'company shared personal data',
    'bila ruhusa':      'without consent permission',
    'kibinafsi':        'personal private data',
    # Consumer
    'bidhaa mbaya':     'defective goods product consumer',
    'duka lilikataa':   'shop refused refund consumer rights',
    'hawakurejesha':    'no refund consumer protection',
    # Physical assault / criminal violence
    'alinipiga':        'assault bodily harm penal code criminal offence',
    'wananipiga':       'assault bodily harm criminal',
    'alinishambulia':   'attack assault bodily harm criminal',
    'jirani':           'neighbour assault penal code',
    'waliiba':          'theft robbery stealing penal code',
    'walimnyang\'anya': 'robbery theft penal code criminal',
    # County enforcement / Kanjo
    'kanjo':            'county enforcement officer business permit license confiscate',
    'county askari':    'county enforcement officer business permit',
    'kaounti':          'county government enforcement by-law',
    'kibanda changu':   'business premises shop stall',
    'wamechukua mali':  'confiscated goods property county enforcement',
    'wamefunga duka':   'closed shop business county enforcement license',
}


def _expand_query(text: str) -> str:
    """
    Append English legal terms for any Swahili/Sheng words found in the query.
    This dramatically improves embedding similarity for the English-trained model.
    Example: "Mwajiri alinifukuza" → "Mwajiri alinifukuza employer fired dismissed without notice"
    """
    text_lower = text.lower()
    expansions = []
    for sw_word, en_expansion in _EXPANSION_MAP.items():
        if sw_word in text_lower:
            expansions.append(en_expansion)
    if expansions:
        return text + " " + " ".join(expansions)
    return text


def find_relevant_laws(user_story: str, top_n: int = 5, category_boost: list = None):
    """
    Given a user story, return the top_n most relevant Law objects.
    Uses in-memory cache for embeddings — zero DB hits for the search itself.
    Only fetches the top N matching Law objects from DB at the end.
    """
    # ── Query expansion: add English equivalents for Swahili/Sheng words ────
    expanded_story = _expand_query(user_story)
    story_vector   = embed_text(expanded_story)
    story_lower    = user_story.lower()

    # ── Load slang from DB (cached 5 min) ────────────────────────────────────
    db_slang = _load_slang_from_db()

    # ── Topic keyword detection ───────────────────────────────────────────────
    _emp_en = [
        'fired', 'dismissed', 'notice', 'salary', 'wages', 'employer',
        'employee', 'job', 'work', 'termination', 'redundancy', 'contract',
        'certificate of service', 'maternity', 'unfair', 'retrenchment',
        'resignation', 'probation', 'overtime', 'union',
    ]
    _emp_sw = [
        'mwajiri', 'mfanyakazi', 'kazi', 'mshahara', 'likizo', 'kuachishwa',
        'notisi', 'mkataba', 'ziada', 'mishahara', 'malipo', 'likizo ya uzazi',
        'boss', 'job', 'kampuni', 'kulipwa', 'hakulipa', 'hawakumulipa',
        'alifutwa', 'alifukuzwa', 'alinifukuza', 'alinifukuzwa',
        'niliachishwa', 'nilifutwa', 'nilifukuzwa', 'kunifukuza', 'alinifuta',
    ]
    _land_en = [
        'land', 'title deed', 'plot', 'property', 'eviction', 'landlord',
        'tenant', 'rent', 'lease', 'allotment', 'locked out',
    ]
    _land_sw = [
        'ardhi', 'hati', 'kiwanja', 'nyumba', 'mpangaji', 'pango', 'mmiliki',
        'mwenye nyumba', 'kodi', 'kupigwa lock', 'lock out',
        'amenifunga', 'alinifunga', 'kunifukuza nyumba',
    ]
    _criminal_en = [
        'arrested', 'police', 'warrant', 'bail', 'charge', 'crime', 'offence',
        'detained', 'custody', 'prosecution', 'rights not read', 'handcuffed',
        'locked up', 'cell', 'station', 'OCS', 'officer',
        # Physical assault / violence (not domestic)
        'assault', 'assaulted', 'attacked', 'beat', 'beaten', 'hit', 'hit me',
        'punched', 'stabbed', 'injury', 'bodily harm', 'physical harm',
        'neighbour', 'neighbor', 'mob', 'gang', 'threatened', 'threatening',
        'stole', 'robbery', 'robbed', 'mugged', 'thief', 'stolen',
    ]
    _criminal_sw = [
        'polisi', 'kufungwa', 'watuhumiwa', 'dhamana', 'mashtaka', 'uhalifu',
        'kizuizini', 'kortini', 'warrant', 'kushikwa', 'askari', 'afande',
        'kukamatwa', 'haki zangu', 'haki zake', 'kushtakiwa', 'kifungo', 'gereza',
        'karao', 'karau', 'sanse', 'makarao', 'ma-karao',
        'kunishika', 'walinishika', 'amenishika', 'wamenishika',
        'seleli', 'ndani ya seleli', 'lock-up', 'station',
        'hawakusomea', 'hawakuambia', 'hawakunitajia', 'rights zangu', 'miranda',
    ]
    _family_en = [
        'divorce', 'marriage', 'spouse', 'wife', 'husband', 'custody',
        'inheritance', 'succession', 'domestic violence', 'matrimonial',
        'domestic abuse', 'spousal abuse',
    ]
    _family_sw = [
        'talaka', 'ndoa', 'mke', 'mume', 'watoto', 'mirathi', 'urithi',
        'jeuri ya nyumbani', 'ulezi', 'dem wangu', 'buda wangu', 'mali yetu',
        'anaficha mali', 'ananipiga', 'alinipiga', 'wananipiga',
        'kunidhulumu', 'ukatili', 'kuteswa', 'kubakwa', 'unyanyasaji',
    ]
    _data_en = [
        'personal data', 'data protection', 'privacy', 'consent', 'data breach',
        'cctv', 'surveillance', 'data controller', 'data processor',
    ]
    _data_sw = [
        'data yangu', 'wanashare data', 'bila ruhusa', 'kibinafsi',
        'walichukua picha', 'kampuni imeshare', 'taarifa zangu',
    ]
    _consumer_en = [
        'consumer', 'refund', 'defective', 'faulty', 'product', 'goods',
        'warranty', 'receipt', 'overcharged', 'misleading',
    ]
    _consumer_sw = [
        'bidhaa mbaya', 'duka lilikataa', 'hawakurejesha', 'bidhaa bandia',
        'walimnyang\'anya', 'walidanganya', 'bei ya juu',
    ]
    _county_en = [
        'kanjo', 'county enforcement', 'county officer', 'county askari',
        'business permit', 'trade license', 'hawker', 'street vendor',
        'county by-law', 'county government', 'nairobi city', 'confiscated',
        'county council',
    ]
    _county_sw = [
        'kanjo', 'county askari', 'kaounti', 'kibanda changu',
        'wamechukua mali', 'wamefunga duka', 'leseni ya biashara',
        'ruhusa ya biashara', 'hawkers', 'wafanyabiashara',
    ]

    is_employment = any(k in story_lower for k in _emp_en + _emp_sw + db_slang.get('employment', []))
    is_land       = any(k in story_lower for k in _land_en + _land_sw + db_slang.get('land', []))
    is_criminal   = any(k in story_lower for k in _criminal_en + _criminal_sw + db_slang.get('criminal', []))
    is_family     = any(k in story_lower for k in _family_en + _family_sw + db_slang.get('family', []))
    is_data       = any(k in story_lower for k in _data_en + _data_sw + db_slang.get('other', []))
    is_consumer   = any(k in story_lower for k in _consumer_en + _consumer_sw)
    is_county     = any(k in story_lower for k in _county_en + _county_sw)
    # County enforcement overrides criminal classification for kanjo queries
    if is_county:
        is_criminal = False

    # ── On-topic categories ───────────────────────────────────────────────────
    on_topic_cats = {'constitution'}
    if is_employment: on_topic_cats.add('employment')
    if is_land:       on_topic_cats.update({'land', 'landlord_tenant'})
    if is_criminal:   on_topic_cats.add('criminal_procedure')
    if is_family:     on_topic_cats.add('other')
    if is_data:       on_topic_cats.add('other')
    if is_consumer:   on_topic_cats.add('consumer')
    if is_county:     on_topic_cats.add('other')   # county acts sit under 'other'

    topic_detected = is_employment or is_land or is_criminal or is_family or is_data or is_consumer or is_county
    OFF_TOPIC_MIN_SCORE = 0.48

    # ── Use in-memory cache — zero DB hits ────────────────────────────────────
    story_vec = np.array(story_vector, dtype=np.float32)
    cached_laws = _get_law_cache()

    scored = []
    for entry in cached_laws:
        raw_score = float(np.dot(story_vec, entry['vec']))

        # Drop off-topic low-scorers
        if topic_detected and entry['category'] not in on_topic_cats:
            if raw_score < OFF_TOPIC_MIN_SCORE:
                continue

        score = raw_score

        # Constitution boost
        if category_boost and entry['category'] in category_boost:
            score += 0.12

        # Topic-specific boosts
        if is_employment and entry['category'] == 'employment':
            score += 0.14
        if is_land and entry['category'] == 'land':
            score += 0.14
        if is_land and entry['category'] == 'landlord_tenant':
            score += 0.10
        if is_criminal and entry['category'] == 'criminal_procedure':
            score += 0.14
        if is_consumer and entry['category'] == 'consumer':
            score += 0.14
        if is_family and entry['category'] == 'other' and any(
            k in (entry['title'] or '').lower()
            for k in ['marriage', 'succession', 'children', 'matrimonial',
                      'domestic', 'protection against', 'widows']
        ):
            score += 0.14
        if is_data and entry['category'] == 'other' and 'data protection' in (entry['title'] or '').lower():
            score += 0.14
        if is_county and entry['category'] == 'other' and any(
            k in (entry['title'] or '').lower()
            for k in ['county', 'local government', 'trade', 'hawker',
                      'physical planning', 'fair administrative', 'business']
        ):
            score += 0.16

        scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Fetch only the top_n Law objects from DB by ID — one tiny query
    top_entries = [e for _, e in scored[:top_n]]
    top_ids     = [e['id'] for e in top_entries]

    # Guarantee at least one primary-topic section
    if topic_detected:
        top_cats     = {e['category'] for e in top_entries}
        primary_cats = on_topic_cats - {'constitution'}
        if primary_cats and not (top_cats & primary_cats):
            for _, entry in scored[top_n:]:
                if entry['category'] in primary_cats:
                    top_entries[-1] = entry
                    top_ids[-1]     = entry['id']
                    break

    from cases.models import Law
    law_map = {l.pk: l for l in Law.objects.filter(pk__in=top_ids)}
    # Return in scored order, preserving ranking
    return [law_map[eid] for eid in top_ids if eid in law_map]


def build_embeddings_for_all_laws():
    """
    One-time (or on-demand) function: generate and save embeddings
    for every Law row that doesn't have one yet.
    Run via: python manage.py shell -> from cases.rag import build_embeddings_for_all_laws; build_embeddings_for_all_laws()
    Or run via the management command: python manage.py build_embeddings
    """
    from cases.models import Law

    laws_without = Law.objects.filter(embedding_json='') | Law.objects.filter(embedding_json__isnull=True)
    total = laws_without.count()

    if total == 0:
        print("[RAG] All laws already have embeddings.")
        return

    print(f"[RAG] Building embeddings for {total} law sections...")

    for i, law in enumerate(laws_without, 1):
        text_to_embed = f"{law.title} {law.section}: {law.content}"
        vector = embed_text(text_to_embed)
        law.set_embedding(vector)
        law.save(update_fields=['embedding_json'])
        if i % 10 == 0:
            print(f"[RAG] {i}/{total} done...")

    print(f"[RAG] Done. {total} embeddings built.")
