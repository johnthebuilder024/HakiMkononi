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
import time
import numpy as np
from sentence_transformers import SentenceTransformer

# Load once at startup — model is cached after first load
_model = None

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


def get_model():
    global _model
    if _model is None:
        print("[RAG] Loading SentenceTransformer model...")
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        print("[RAG] Model loaded.")
    return _model


def embed_text(text: str) -> list:
    """Convert a string to a vector (list of floats)."""
    model = get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


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
    Uses query expansion for Swahili/Sheng to improve embedding similarity.
    """
    from cases.models import Law

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
    ]
    _criminal_sw = [
        'polisi', 'kufungwa', 'watuhumiwa', 'dhamana', 'mashtaka', 'uhalifu',
        'kizuizini', 'kortini', 'warrant', 'kushikwa', 'askari', 'afande',
        'kukamatwa', 'haki zangu', 'haki zake', 'kushtakiwa', 'kifungo', 'gereza',
        'karao', 'karau', 'sanse', 'makarao', 'ma-karao', 'kanjo',
        'kunishika', 'walinishika', 'amenishika', 'wamenishika',
        'seleli', 'ndani ya seleli', 'lock-up', 'station',
        'hawakusomea', 'hawakuambia', 'hawakunitajia', 'rights zangu', 'miranda',
    ]
    _family_en = [
        'divorce', 'marriage', 'spouse', 'wife', 'husband', 'custody',
        'inheritance', 'succession', 'domestic violence', 'matrimonial',
        'beating', 'assault', 'abuse',
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

    is_employment = any(k in story_lower for k in _emp_en + _emp_sw + db_slang.get('employment', []))
    is_land       = any(k in story_lower for k in _land_en + _land_sw + db_slang.get('land', []))
    is_criminal   = any(k in story_lower for k in _criminal_en + _criminal_sw + db_slang.get('criminal', []))
    is_family     = any(k in story_lower for k in _family_en + _family_sw + db_slang.get('family', []))
    is_data       = any(k in story_lower for k in _data_en + _data_sw + db_slang.get('other', []))
    is_consumer   = any(k in story_lower for k in _consumer_en + _consumer_sw)

    # ── On-topic categories ───────────────────────────────────────────────────
    on_topic_cats = {'constitution'}
    if is_employment: on_topic_cats.add('employment')
    if is_land:       on_topic_cats.update({'land', 'landlord_tenant'})
    if is_criminal:   on_topic_cats.add('criminal_procedure')
    if is_family:     on_topic_cats.add('other')
    if is_data:       on_topic_cats.add('other')
    if is_consumer:   on_topic_cats.add('consumer')

    topic_detected    = is_employment or is_land or is_criminal or is_family or is_data or is_consumer
    OFF_TOPIC_MIN_SCORE = 0.48

    laws = Law.objects.exclude(embedding_json='').exclude(embedding_json__isnull=True)

    scored = []
    for law in laws:
        law_vector = law.get_embedding()
        if law_vector is None:
            continue
        raw_score = cosine_similarity(story_vector, law_vector)

        # Drop off-topic low-scorers
        if topic_detected and law.category not in on_topic_cats:
            if raw_score < OFF_TOPIC_MIN_SCORE:
                continue

        score = raw_score

        # Constitution boost
        if category_boost and law.category in category_boost:
            score += 0.12

        # Topic-specific boosts — stronger than constitution boost so
        # primary-topic sections rank above generic constitution articles
        if is_employment and law.category == 'employment':
            score += 0.14
        if is_land and law.category == 'land':
            score += 0.14
        if is_land and law.category == 'landlord_tenant':
            score += 0.10
        if is_criminal and law.category == 'criminal_procedure':
            score += 0.14
        if is_consumer and law.category == 'consumer':
            score += 0.14
        if is_family and law.category == 'other' and any(
            k in (law.title or '').lower()
            for k in ['marriage', 'succession', 'children', 'matrimonial',
                      'domestic', 'protection against', 'widows']
        ):
            score += 0.14
        if is_data and law.category == 'other' and 'data protection' in (law.title or '').lower():
            score += 0.14

        scored.append((score, law))

    scored.sort(key=lambda x: x[0], reverse=True)

    result = [law for _, law in scored[:top_n]]

    # ── Guarantee at least one primary-topic section ──────────────────────────
    if topic_detected:
        result_cats = {l.category for l in result}
        primary_cats = on_topic_cats - {'constitution'}
        if primary_cats and not (result_cats & primary_cats):
            for score, law in scored[top_n:]:
                if law.category in primary_cats:
                    result[-1] = law
                    break

    return result


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
