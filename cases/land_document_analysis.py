"""
cases/land_document_analysis.py

Extends the existing document extraction pipeline for land documents.

When a user uploads a title deed or sale agreement, this module:
1. Extracts key fields (LR number, registered proprietor, area, date, encumbrances)
2. Validates the format against known Kenyan title deed structures
3. Flags any suspicious elements
4. Returns the extracted data + red flags for the AI to use

Called from cases/views.py extract_text endpoint when land context is detected.
"""

import re
import logging

logger = logging.getLogger(__name__)


# ─── Title deed field extraction ─────────────────────────────────────────────

def extract_title_deed_fields(text: str) -> dict:
    """
    Extract key fields from a Kenyan title deed text.

    Returns dict:
    {
        lr_number, title_number, proprietor_name, area, area_unit,
        registration_date, county, encumbrances, deed_type,
        red_flags (list of strings)
    }
    """
    result = {
        'lr_number':         '',
        'title_number':      '',
        'proprietor_name':   '',
        'area':              '',
        'area_unit':         '',
        'registration_date': '',
        'county':            '',
        'encumbrances':      [],
        'deed_type':         '',   # 'freehold' | 'leasehold' | 'unknown'
        'red_flags':         [],
    }

    text_upper = text.upper()

    # ── LR / Title number ────────────────────────────────────────────────────
    # Patterns: NAIROBI/BLOCK 24/123, KIAMBU/001/234, L.R. NO. 209/3456
    lr_patterns = [
        r'(?:L\.?R\.?\s*NO\.?\s*|PARCEL\s*NO\.?\s*|TITLE\s*NO\.?\s*)'
        r'([A-Z]+(?:/[A-Z\s]+)?/[\d]+(?:/[\d]+)*)',
        r'([A-Z]{3,}/(?:[A-Z\s/]+/)?[\d]+(?:/[\d]+)*)',
        r'L\.R\.\s*NO\.?\s*([\d/]+)',
    ]
    for pattern in lr_patterns:
        m = re.search(pattern, text_upper)
        if m:
            result['lr_number'] = m.group(1).strip()
            break

    # ── Registered proprietor ────────────────────────────────────────────────
    prop_patterns = [
        r'REGISTERED\s+PROPRIETOR[:\s]+([A-Z][A-Z\s]+?)(?:\n|OF\s|ID\s|I\.D)',
        r'PROPRIETOR[:\s]+([A-Z][A-Z\s]{5,60})(?:\n|OF\s)',
        r'OWNER[:\s]+([A-Z][A-Z\s]{5,60})(?:\n)',
    ]
    for pattern in prop_patterns:
        m = re.search(pattern, text_upper)
        if m:
            result['proprietor_name'] = m.group(1).strip().title()
            break

    # ── Area ─────────────────────────────────────────────────────────────────
    area_m = re.search(
        r'(?:AREA|SIZE|APPROXIMATELY)[:\s]*([\d,\.]+)\s*(HECTARES?|ACRES?|SQ\.?\s*M|SQUARE\s*METRES?)',
        text_upper
    )
    if area_m:
        result['area']      = area_m.group(1).replace(',', '')
        result['area_unit'] = area_m.group(2).strip()

    # ── Registration date ─────────────────────────────────────────────────────
    date_m = re.search(
        r'(?:REGISTERED|DATE OF REGISTRATION|DATED?)[:\s]+'
        r'(\d{1,2}(?:ST|ND|RD|TH)?\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*'
        r'\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{4})',
        text_upper
    )
    if date_m:
        result['registration_date'] = date_m.group(1).strip()

    # ── Deed type ─────────────────────────────────────────────────────────────
    if 'FREEHOLD' in text_upper or 'ABSOLUTE OWNERSHIP' in text_upper:
        result['deed_type'] = 'freehold'
    elif 'LEASEHOLD' in text_upper or 'YEARS' in text_upper and 'LEASE' in text_upper:
        result['deed_type'] = 'leasehold'

    # ── County detection ──────────────────────────────────────────────────────
    COUNTIES = [
        'NAIROBI', 'MOMBASA', 'KISUMU', 'NAKURU', 'KIAMBU', 'KILIFI',
        'KWALE', 'MERU', 'MACHAKOS', 'KAJIADO', 'MURANG\'A', 'MURANGA',
        'LAIKIPIA', 'NYERI', 'UASIN GISHU', 'TRANS NZOIA', 'BUNGOMA',
        'KAKAMEGA', 'LAMU', 'TAITA TAVETA',
    ]
    for county in COUNTIES:
        if county in text_upper:
            result['county'] = county.title()
            break

    # ── Encumbrances ──────────────────────────────────────────────────────────
    enc_terms = {
        'CAUTION':      'Caution registered — someone has a dispute claim on this land',
        'CHARGE':       'Charge registered — land is security for a loan',
        'CAVEAT':       'Caveat registered — someone claims an interest preventing transfer',
        'RESTRICTION':  'Restriction registered — transfer blocked by court or government',
        'EASEMENT':     'Easement registered — another party has right of access',
        'RIGHT OF WAY': 'Right of way registered — public or private access right exists',
        'MORTGAGE':     'Mortgage registered — bank has interest in the land',
        'DEBENTURE':    'Debenture registered — corporate charge on the land',
    }
    for term, meaning in enc_terms.items():
        if term in text_upper:
            result['encumbrances'].append(meaning)

    # ── Red flag detection ────────────────────────────────────────────────────
    red_flags = []

    # No LR number found
    if not result['lr_number']:
        red_flags.append(
            "No LR number found — a genuine title deed always has a land reference number"
        )

    # No proprietor name found
    if not result['proprietor_name']:
        red_flags.append(
            "Could not extract registered proprietor name — verify manually"
        )

    # Encumbrances found
    for enc in result['encumbrances']:
        if 'Charge' in enc or 'Mortgage' in enc:
            red_flags.append(
                f"⚠️ {enc} — seller must provide bank discharge before transfer"
            )
        elif 'Caution' in enc or 'Caveat' in enc or 'Restriction' in enc:
            red_flags.append(
                f"🔴 {enc} — do not pay until this is resolved"
            )

    # Post-2012 title should have a serial number
    has_serial = bool(re.search(r'SERIAL\s*(?:NO\.?|NUMBER)[:\s]*[\dA-Z]+', text_upper))
    if not has_serial and result['registration_date']:
        # Try to parse year
        year_m = re.search(r'\b(20\d{2}|19\d{2})\b', result['registration_date'])
        if year_m and int(year_m.group(1)) >= 2013:
            red_flags.append(
                "Post-2012 title should have a serial number — not found in document"
            )

    result['red_flags'] = red_flags
    return result


def format_extracted_fields_for_ai(fields: dict, lang: str = 'en') -> str:
    """
    Format extracted title deed fields as context for the AI.
    """
    lines = []

    if lang == 'sw':
        lines.append("TAARIFA ZILIZOTOLEWA KUTOKA KWA HATI:")
    else:
        lines.append("EXTRACTED FROM UPLOADED DOCUMENT:")

    if fields.get('lr_number'):
        lines.append(f"  LR/Title Number: {fields['lr_number']}")
        lines.append(f"  → Use this exact number on Ardhisasa to verify")

    if fields.get('proprietor_name'):
        lines.append(f"  Registered Proprietor: {fields['proprietor_name']}")
        lines.append(f"  → Buyer must check this name matches the seller's National ID")

    if fields.get('area'):
        lines.append(f"  Area: {fields['area']} {fields.get('area_unit', '')}")

    if fields.get('registration_date'):
        lines.append(f"  Registration Date: {fields['registration_date']}")

    if fields.get('county'):
        lines.append(f"  County: {fields['county']}")

    if fields.get('deed_type'):
        lines.append(f"  Tenure: {fields['deed_type'].title()}")

    if fields.get('encumbrances'):
        lines.append(f"\n  Encumbrances on title:")
        for enc in fields['encumbrances']:
            lines.append(f"    • {enc}")

    if fields.get('red_flags'):
        lines.append(f"\n  ⚠️ RED FLAGS:")
        for flag in fields['red_flags']:
            lines.append(f"    • {flag}")

    return '\n'.join(lines)


def analyse_land_document(text: str, lang: str = 'en') -> dict:
    """
    Main entry point. Takes extracted document text and returns:
    {
        fields: dict of extracted fields,
        context_for_ai: string to inject into AI prompt,
        lr_number: string (for court case search),
        has_red_flags: bool,
    }
    """
    fields = extract_title_deed_fields(text)
    context = format_extracted_fields_for_ai(fields, lang)

    return {
        'fields':         fields,
        'context_for_ai': context,
        'lr_number':      fields.get('lr_number', ''),
        'has_red_flags':  len(fields.get('red_flags', [])) > 0,
    }
