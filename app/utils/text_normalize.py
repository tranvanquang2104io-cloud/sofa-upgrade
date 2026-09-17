"""Vietnamese-aware text normalization primitives.

Small, composable transforms. A field's rule set is an ordered list of these,
so behaviour is configured as data rather than coded per field.

TWO THINGS THAT MATTER MORE THAN THE CASING RULES
-------------------------------------------------
1. **Unicode NFC.** Vietnamese diacritics can be stored precomposed (NFC, e.g.
   ``ệ`` = U+1EC7) or decomposed (NFD, ``e`` + combining marks). The two render
   identically but compare UNEQUAL, which silently breaks ``WHERE name = ?``
   lookups, duplicate detection and DOCX rendering. Windows fields, OCR and
   macOS clipboards commonly produce NFD. So ``to_nfc`` runs first, always,
   silently, on every text write — it is a correctness fix, not a style choice.

2. **Some fields must never be touched.** Tax codes, bank accounts, document
   numbers and national ID numbers are exact-match legal identifiers. "Tidying"
   them can corrupt a valid identifier or mask a real data-entry error that
   should have been rejected. See ``PROTECTED_FIELD_HINTS``.

Casing is identity-sensitive: rewriting how a person's name is spelled can
misrepresent a party on a legal document. Every primitive therefore declares
whether it is safe to apply silently (``AUTO_SAFE``) or should be offered as a
suggestion (``CONFIRM_RECOMMENDED``); the per-company configuration can still
override this, because the business explicitly asked for automatic casing on
customer and item names.
"""
import re
import unicodedata

# Field names that must never be normalized, whatever the configuration says.
# Matched as a substring of the lowercased field name.
PROTECTED_FIELD_HINTS = (
    'tax_code', 'mst', 'bank', 'account_number', 'password', 'hash',
    'number', 'code', 'id', 'email', 'url', 'path', 'phone',
)

# Tokens that stay uppercase inside an otherwise Title-Cased Vietnamese name.
# Vietnamese company names read "CÔNG TY TNHH MTV ..." — a naive .title()
# would render these as "Tnhh"/"Mtv".
UPPER_TOKENS = {
    'TNHH', 'MTV', 'CP', 'CTCP', 'TM', 'DV', 'SX', 'XD', 'XNK', 'TNHH-MTV',
    'HTX', 'DNTN', 'VN', 'TP', 'HCM', 'VAT', 'GTGT', 'ĐVT',
}

# Legal-form prefixes that identify a Vietnamese company name.
COMPANY_PREFIX_RE = re.compile(
    r'^\s*(c[ôo]ng\s*ty|cty|c[ơo]ng\s*ti)\b', re.IGNORECASE | re.UNICODE)


def to_nfc(value):
    """Canonical precomposed form. Run first, always."""
    if not isinstance(value, str):
        return value
    return unicodedata.normalize('NFC', value)


def trim(value):
    return value.strip() if isinstance(value, str) else value


def collapse_whitespace(value):
    """Collapse runs of whitespace to a single space."""
    if not isinstance(value, str):
        return value
    return re.sub(r'\s+', ' ', value).strip()


def normalize_punctuation(value):
    """Curly quotes/dashes and full-width forms to their ASCII equivalents."""
    if not isinstance(value, str):
        return value
    replacements = {
        '‘': "'", '’': "'", '“': '"', '”': '"',
        '–': '-', '—': '-', '…': '...',
        '，': ',', '．': '.', '：': ':', '；': ';',
        ' ': ' ',
    }
    for bad, good in replacements.items():
        value = value.replace(bad, good)
    # ", x" not " ,x"
    value = re.sub(r'\s+([,.;:])', r'\1', value)
    return value


def upper(value):
    """Uppercase. Python's Unicode tables handle Vietnamese correctly."""
    return to_nfc(value).upper() if isinstance(value, str) else value


def lower(value):
    return to_nfc(value).lower() if isinstance(value, str) else value


def _title_word(word):
    """Capitalise one whitespace-separated token, preserving known acronyms."""
    if not word:
        return word
    if word.upper() in UPPER_TOKENS:
        return word.upper()
    # Keep an existing all-caps acronym of 2+ chars (e.g. "ABC") as-is.
    stripped = word.strip('()[].,')
    if len(stripped) > 1 and stripped.isupper() and not any(c.isdigit() for c in stripped):
        return word
    return word[:1].upper() + word[1:].lower()


def title_case(value):
    """Title Case per syllable — the Vietnamese name convention.

    ``.title()`` from the standard library is unusable here: it lowercases
    acronyms ("TNHH" -> "Tnhh") and capitalises after every non-letter, so
    "cong ty a.b" becomes "Cong Ty A.B".
    """
    if not isinstance(value, str):
        return value
    value = to_nfc(value)
    return ' '.join(_title_word(w) for w in value.split(' '))


def sentence_case(value):
    """Capitalise the first letter of each sentence; leave the rest alone.

    Used for free text (notes, descriptions) where the business wants a
    capital after each full stop but must not have the whole text rewritten.
    """
    if not isinstance(value, str):
        return value
    value = to_nfc(value)

    out = []
    capitalize_next = True
    for ch in value:
        if capitalize_next and ch.isalpha():
            out.append(ch.upper())
            capitalize_next = False
        else:
            out.append(ch)
            if ch in '.!?':
                capitalize_next = True
    return ''.join(out)


def capitalize_first(value):
    """Capitalise only the very first letter of the string."""
    if not isinstance(value, str):
        return value
    value = to_nfc(value)
    for i, ch in enumerate(value):
        if ch.isalpha():
            return value[:i] + ch.upper() + value[i + 1:]
    return value


def company_name_case(value):
    """Vietnamese company-name convention.

    Legal-form prefix and acronyms uppercase, the distinctive part Title Cased:
        "cty tnhh sản xuất nội thất an phát"
        -> "CÔNG TY TNHH Sản Xuất Nội Thất An Phát"
    Falls back to plain Title Case when the string is not a company name.
    """
    if not isinstance(value, str):
        return value
    value = collapse_whitespace(to_nfc(value))
    if not value:
        return value

    match = COMPANY_PREFIX_RE.match(value)
    if not match:
        return title_case(value)

    rest = value[match.end():].lstrip()
    # Pull any leading legal-form acronyms (TNHH, MTV, CP...) into the prefix.
    words = rest.split(' ')
    acronyms = []
    while words and words[0].upper() in UPPER_TOKENS:
        acronyms.append(words.pop(0).upper())

    prefix = 'CÔNG TY'
    if acronyms:
        prefix = prefix + ' ' + ' '.join(acronyms)
    remainder = title_case(' '.join(words)) if words else ''
    return (prefix + ' ' + remainder).strip()


def strip_diacritics(value):
    """Remove Vietnamese tone/vowel marks.

    For SEARCH KEYS AND SLUGS ONLY — never for a stored display value, since
    it destroys meaning ("ma" != "má" != "mà").
    """
    if not isinstance(value, str):
        return value
    decomposed = unicodedata.normalize('NFD', value)
    without = ''.join(c for c in decomposed
                      if unicodedata.category(c) != 'Mn')
    # đ/Đ carry no combining mark and survive decomposition.
    without = without.replace('đ', 'd').replace('Đ', 'D')
    return unicodedata.normalize('NFC', without)


# name -> (callable, is_auto_safe, human description)
PRIMITIVES = {
    'nfc': (to_nfc, True, 'Normalize Unicode (NFC)'),
    'trim': (trim, True, 'Trim leading/trailing spaces'),
    'collapse_whitespace': (collapse_whitespace, True, 'Collapse repeated spaces'),
    'normalize_punctuation': (normalize_punctuation, True, 'Normalize punctuation'),
    'upper': (upper, False, 'UPPERCASE'),
    'lower': (lower, False, 'lowercase'),
    'title_case': (title_case, False, 'Title Case Each Word'),
    'sentence_case': (sentence_case, False, 'Capitalize after each sentence'),
    'capitalize_first': (capitalize_first, False, 'Capitalize first letter only'),
    'company_name_case': (company_name_case, False, 'Vietnamese company name'),
    'strip_diacritics': (strip_diacritics, False, 'Remove diacritics (search keys only)'),
}

AUTO_SAFE = tuple(name for name, (_f, safe, _d) in PRIMITIVES.items() if safe)


def is_protected_field(field_name):
    """True when a field must never be normalized."""
    if not field_name:
        return True
    name = field_name.lower()
    return any(hint in name for hint in PROTECTED_FIELD_HINTS)


def apply_primitives(value, primitive_names):
    """Run an ordered list of primitives over one value."""
    if not isinstance(value, str):
        return value
    for name in primitive_names:
        entry = PRIMITIVES.get(name)
        if entry is None:
            continue
        value = entry[0](value)
    return value
