"""Tài liệu đã tạo: thứ tự mới-nhất-trước và chốt an toàn cho redirect sau khi xoá.

Bối cảnh: người dùng in lại báo giá nhiều lần (cả PDF lẫn DOCX), nên danh sách
tài liệu phải luôn xếp bản in gần nhất lên đầu để họ khỏi phải dò ngày giờ.
Nút xoá nay có mặt trên cả bốn màn hình xem chứng từ, và route xoá quay lại
đúng nơi vừa bấm — nghĩa là nó nhận đường dẫn từ trình duyệt, nên phải chặn
open redirect.
"""
from datetime import datetime, timedelta

import pytest

from app.routes.dashboard_routes import _is_safe_redirect_url


def _mk_doc(db, seed, order_id, quotation_id, name, when, fmt="pdf"):
    from app.models import Document

    doc = Document(
        company_id=seed["company_id"],
        order_id=order_id,
        quotation_id=quotation_id,
        document_name=name,
        document_type="quotation",
        document_format=fmt,
        file_path=f"/tmp/{name}",
        generated_at=when,
    )
    db.session.add(doc)
    return doc


@pytest.fixture()
def quotation_with_docs(app, seeded_order):
    """Một báo giá kèm 3 tài liệu được tạo lệch giờ, cố tình chèn KHÔNG theo
    thứ tự thời gian để bài test không vô tình đúng nhờ thứ tự chèn."""
    from app.config import db
    from app.models import Quotation

    base = datetime(2026, 8, 29, 3, 0, 0)
    with app.app_context():
        quotation = Quotation(
            company_id=seeded_order["company_id"],
            order_id=seeded_order["order_id"],
            quotation_number="QT-011",
            quotation_date=base.date(),
            total_amount=1000,
        )
        db.session.add(quotation)
        db.session.flush()

        _mk_doc(db, seeded_order, seeded_order["order_id"], quotation.id,
                "BaoGia_giua", base + timedelta(hours=1))
        _mk_doc(db, seeded_order, seeded_order["order_id"], quotation.id,
                "BaoGia_moi_nhat", base + timedelta(hours=2), fmt="docx")
        _mk_doc(db, seeded_order, seeded_order["order_id"], quotation.id,
                "BaoGia_cu_nhat", base)
        db.session.commit()
        return {**seeded_order, "quotation_id": str(quotation.id)}


def test_quotation_documents_moi_nhat_len_dau(app, quotation_with_docs):
    """Quan hệ `quotation.documents` phải trả về mới nhất trước."""
    from app.models import Quotation

    with app.app_context():
        quotation = Quotation.query.get(quotation_with_docs["quotation_id"])
        names = [d.document_name for d in quotation.documents]

    assert names == ["BaoGia_moi_nhat", "BaoGia_giua", "BaoGia_cu_nhat"]


def test_repository_cung_sap_moi_nhat_truoc(app, quotation_with_docs):
    """Đường đi qua repository phải khớp với quan hệ — nếu lệch thì màn hình
    danh sách và màn hình xem sẽ hiển thị hai thứ tự khác nhau."""
    from app.repositories.repository import DocumentRepository

    with app.app_context():
        docs = DocumentRepository().get_for_quotation(quotation_with_docs["quotation_id"])
        names = [d.document_name for d in docs]

        for_order = DocumentRepository().get_for_order(quotation_with_docs["order_id"])
        order_names = [d.document_name for d in for_order]

    assert names == ["BaoGia_moi_nhat", "BaoGia_giua", "BaoGia_cu_nhat"]
    assert order_names == names


@pytest.mark.parametrize("target", [
    "/quotations/abc/view",
    "/quotations/abc/view?tab=docs",
    "/",
])
def test_redirect_noi_bo_duoc_chap_nhan(target):
    assert _is_safe_redirect_url(target) is True


@pytest.mark.parametrize("target", [
    "//evil.com/steal",              # protocol-relative — trình duyệt hiểu là host ngoài
    "https://evil.com/steal",
    "http://evil.com",
    "javascript:alert(1)",
    "quotations/abc/view",           # không bắt đầu bằng '/' → mơ hồ
    "",
    None,
])
def test_redirect_ra_ngoai_bi_chan(target):
    assert _is_safe_redirect_url(target) is False


def test_man_hinh_xem_bao_gia_hien_nhan_moi_nhat_va_nut_xoa(client, login, quotation_with_docs):
    """Kiểm tra thật trên HTML trả về: bản mới nhất đứng trước bản cũ, được gắn
    nhãn, và mỗi tài liệu đều có nút xoá."""
    login("admin")
    resp = client.get(f"/quotations/{quotation_with_docs['quotation_id']}/view")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Thứ tự xuất hiện trong HTML phản ánh thứ tự hiển thị cho người dùng.
    assert html.index("BaoGia_moi_nhat") < html.index("BaoGia_giua") < html.index("BaoGia_cu_nhat")

    # Nhãn đánh dấu bản mới nhất, và chỉ một nhãn duy nhất.
    assert html.count("Mới nhất") == 1

    # Ba nút xoá cho ba tài liệu.
    assert html.count('data-bs-target="#docDeleteModal"') == 3
