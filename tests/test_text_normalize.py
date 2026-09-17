"""Vietnamese-aware normalization primitives.

The Unicode tests are the important ones: NFC vs NFD is invisible on screen
but breaks equality, lookups and DOCX rendering.
"""
import unicodedata

import pytest

from app.utils.text_normalize import (
    apply_primitives,
    capitalize_first,
    collapse_whitespace,
    company_name_case,
    is_protected_field,
    normalize_punctuation,
    sentence_case,
    strip_diacritics,
    title_case,
    to_nfc,
    upper,
)


# --- Unicode correctness --------------------------------------------------

def test_decomposed_vietnamese_is_recomposed():
    """NFD and NFC render identically but are unequal — the classic trap."""
    nfc = "Việt"
    nfd = unicodedata.normalize('NFD', nfc)

    assert nfc != nfd, "precondition: the two forms differ as strings"
    assert to_nfc(nfd) == nfc
    assert len(to_nfc(nfd)) < len(nfd), "decomposed form should be shorter after NFC"


def test_nfc_is_idempotent():
    assert to_nfc(to_nfc("Nguyễn Văn Ạ")) == to_nfc("Nguyễn Văn Ạ")


def test_uppercase_preserves_vietnamese_diacritics():
    assert upper("nguyễn văn a") == "NGUYỄN VĂN A"
    assert upper("cộng hòa xã hội") == "CỘNG HÒA XÃ HỘI"


def test_uppercase_handles_d_with_stroke():
    assert upper("đồng") == "ĐỒNG"


# --- casing ---------------------------------------------------------------

def test_title_case_on_a_vietnamese_person_name():
    assert title_case("nguyễn văn a") == "Nguyễn Văn A"


def test_title_case_preserves_known_acronyms():
    """str.title() would produce 'Tnhh' / 'Mtv' — the reason we don't use it."""
    assert title_case("công ty TNHH MTV an phát") == "Công Ty TNHH MTV An Phát"


def test_title_case_does_not_capitalize_after_a_dot_inside_a_word():
    """str.title() turns 'a.b' into 'A.B'."""
    assert title_case("nội thất a.b") == "Nội Thất A.b"


def test_company_name_case_uppercases_the_legal_form():
    assert company_name_case("cty tnhh sản xuất nội thất an phát") == \
        "CÔNG TY TNHH Sản Xuất Nội Thất An Phát"


def test_company_name_case_handles_the_full_prefix():
    assert company_name_case("công ty cp nội thất bình minh") == \
        "CÔNG TY CP Nội Thất Bình Minh"


def test_company_name_case_falls_back_to_title_case_for_non_companies():
    assert company_name_case("nguyễn văn a") == "Nguyễn Văn A"


def test_capitalize_first_touches_only_the_first_letter():
    assert capitalize_first("ghế sofa da BÒ") == "Ghế sofa da BÒ"


def test_sentence_case_capitalizes_after_each_full_stop():
    assert sentence_case("giao hàng tận nơi. bảo hành 2 năm. hết.") == \
        "Giao hàng tận nơi. Bảo hành 2 năm. Hết."


def test_sentence_case_leaves_interior_words_alone():
    """It must not rewrite the whole text, only sentence starts."""
    assert sentence_case("bọc ghế da BÒ thật. giá tốt.") == \
        "Bọc ghế da BÒ thật. Giá tốt."


# --- whitespace and punctuation -------------------------------------------

def test_collapse_whitespace():
    assert collapse_whitespace("  ghế   sofa \t góc  ") == "ghế sofa góc"


def test_normalize_punctuation_converts_curly_quotes_and_dashes():
    assert normalize_punctuation('“ghế” – sofa') == '"ghế" - sofa'


def test_normalize_punctuation_removes_space_before_comma():
    assert normalize_punctuation("ghế , sofa") == "ghế, sofa"


def test_nbsp_becomes_a_normal_space():
    assert normalize_punctuation("ghế sofa") == "ghế sofa"


# --- diacritic stripping (search keys only) -------------------------------

def test_strip_diacritics_for_search_keys():
    assert strip_diacritics("Nguyễn Văn Đức") == "Nguyen Van Duc"


def test_strip_diacritics_handles_d_with_stroke():
    assert strip_diacritics("đồng") == "dong"


# --- protected fields -----------------------------------------------------

@pytest.mark.parametrize("field", [
    'tax_code', 'company_tax_code', 'bank_account_number', 'quotation_number',
    'contract_number', 'customer_code', 'password_hash', 'email', 'phone',
])
def test_identifier_fields_are_protected(field):
    """Legal identifiers must never be 'tidied' — that corrupts them."""
    assert is_protected_field(field) is True


@pytest.mark.parametrize("field", ['name', 'title', 'notes', 'address',
                                   'description', 'representative_name'])
def test_free_text_fields_are_not_protected(field):
    assert is_protected_field(field) is False


def test_unknown_field_name_is_protected_by_default():
    assert is_protected_field(None) is True
    assert is_protected_field('') is True


# --- composition ----------------------------------------------------------

def test_primitives_apply_in_order():
    out = apply_primitives("  cty   tnhh  an phát  ",
                           ['nfc', 'trim', 'collapse_whitespace',
                            'company_name_case'])
    assert out == "CÔNG TY TNHH An Phát"


def test_unknown_primitive_is_skipped_not_fatal():
    assert apply_primitives("abc", ['nope', 'upper']) == "ABC"


def test_non_string_values_pass_through_untouched():
    assert apply_primitives(42, ['upper']) == 42
    assert apply_primitives(None, ['upper']) is None
