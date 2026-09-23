"""The status column is the one column people actually read.

Two defects, found by reading what the live screens render rather than what
the code intends:

1. **A framework agreement's status fell through the token map.** `active`,
   `suspended` and `terminated` are not in DOCUMENT_STATUS, so `status_meta`
   returned the raw database value — the screen printed lowercase `active` and
   `terminated` — and, worse, coloured all of them `neutral`. A TERMINATED
   agreement looked exactly like an active one. The colour is supposed to carry
   the state; here it carried nothing, which is worse than no colour at all
   because it reads as deliberate.

2. **Several labels had no Vietnamese entry**, so a column read half in
   Vietnamese and half in English: `/production` showed "In Production" beside
   "Hoàn thành", `/requisitions` showed "Submitted" and "Converted" beside
   "Nháp" and "Đã Duyệt". Mixed languages in one column are harder to scan than
   either language alone.
"""
import pytest

from app.utils.i18n import TRANSLATIONS
from app.utils.status_tokens import ENTITY_MAPS, status_meta


def test_every_status_label_in_every_map_has_a_vietnamese_entry():
    vi = TRANSLATIONS['vi']
    missing = []
    for entity, mapping in ENTITY_MAPS.items():
        for status, (_token, label) in mapping.items():
            if label not in vi:
                missing.append(f'{entity}.{status} -> {label!r}')

    assert missing == [], (
        'these status labels render in English on a Vietnamese screen, next '
        f'to labels that are translated: {sorted(set(missing))}')


@pytest.mark.parametrize('status', ['active', 'suspended', 'terminated'])
def test_an_agreement_status_is_not_the_raw_database_value(status):
    _token, label = status_meta(status, 'agreement')
    assert label != status, (
        f'{status!r} fell through the map and printed the database value')


def test_a_terminated_agreement_does_not_look_like_a_live_one():
    """Colour carries the state, or it should not be there at all."""
    active_token, _ = status_meta('active', 'agreement')
    terminated_token, _ = status_meta('terminated', 'agreement')
    suspended_token, _ = status_meta('suspended', 'agreement')

    assert active_token != terminated_token
    assert active_token != suspended_token


def test_no_status_token_is_unknown_to_the_colour_table():
    """A token with no colour is the same failure one layer down."""
    from app.utils.status_tokens import TOKEN_CLASSES

    unknown = []
    for entity, mapping in ENTITY_MAPS.items():
        for status, (token, _label) in mapping.items():
            if token not in TOKEN_CLASSES:
                unknown.append(f'{entity}.{status} -> {token!r}')

    assert unknown == [], f'these tokens have no colour: {unknown}'
