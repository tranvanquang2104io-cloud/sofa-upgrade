"""Document file naming convention (BaoGia_/HopDong_/TamUng_/BanGiao_/ThanhToan_)."""
from app.services.services import DocumentService as D

TS = '20260226_193650'


def test_quotation_name():
    assert D._build_doc_basename('quotation', {'quotation_number': 'BG 2026/001'}, TS) \
        == 'BaoGia_BG2026-001_20260226_193650'


def test_contract_name():
    assert D._build_doc_basename('contract', {'contract_number': 'HD-2026-001'}, TS) \
        == 'HopDong_HD-2026-001_20260226_193650'


def test_delivery_uses_contract_number():
    assert D._build_doc_basename('delivery', {'contract_number': 'HD-2026-001',
                                              'report_number': 'BBBG-1'}, TS) \
        == 'BanGiao_HD-2026-001_20260226_193650'


def test_advance_payment_name():
    assert D._build_doc_basename('payment', {'payment_type': 'advance',
                                             'contract_number': 'HD-2026-001'}, TS) \
        == 'TamUng_HD-2026-001_20260226_193650'


def test_final_payment_name():
    assert D._build_doc_basename('payment', {'payment_type': 'final',
                                             'contract_number': 'HD-2026-001'}, TS) \
        == 'ThanhToan_HD-2026-001_20260226_193650'


def test_missing_code_falls_back_to_NA():
    assert D._build_doc_basename('quotation', {}, TS) == 'BaoGia_NA_20260226_193650'
