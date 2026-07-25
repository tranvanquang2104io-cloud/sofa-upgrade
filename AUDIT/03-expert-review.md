# GIAI ĐOẠN 3 — Hội đồng chuyên gia (Multi-persona review)

**Ngày:** 2026-07-25 · **Nhánh:** `refactor/full-audit` · Dựa trên bằng chứng đã đọc/đo (không phỏng đoán).
Mã finding: tái dùng **B1–B7** (bug catalog) & **P1–P8** (baseline); thêm mới theo panel (U/A/DB/S/PF).

---

## A. UX/UI & Product — Norman · Nielsen · Krug · Wroblewski

| Mã | Mức | Finding | Vị trí (bằng chứng) | Khuyến nghị |
|----|-----|---------|---------------------|-------------|
| U1 | Med | **i18n không nhất quán:** app song ngữ nhưng nhiều heading/title/placeholder hardcode tiếng Anh, không qua `t()` | `templates/orders/create.html:3,8,49` (`Create Order - SofaFlow`, `<h1>Create Order</h1>`, `placeholder="e.g., Sofa Repair"`); mẫu lặp ở nhiều form | Bọc mọi chuỗi hiển thị bằng `t()`; thêm khóa EN+VI. (Nielsen #2 match real world, #4 consistency) |
| U2 | Med | **Không chống lỗi người dùng ở input số tiền/số lượng:** cho nhập âm (B2) + không có CSRF token | tất cả form POST (0 `csrf_token` — grep toàn `templates/`) | Thêm `min="0" step` cho input number; validate cả client+server; thêm CSRF (xem S1). (Norman: error prevention) |
| U3 | Low | **Phụ thuộc CDN** (Bootstrap/Icons) → hỏng khi offline, chậm first paint, lộ referrer sang jsDelivr, không có SRI | `templates/base.html:11-13` | Vendor asset vào `static/`, hoặc thêm `integrity`/`crossorigin` (SRI). (cũng là S6/PF4) |
| U4 | Low | **Form chứng từ dài, 1 cột, nhiều dòng item động** → dễ sai, chật trên mobile | `quotations/create.html`, `contracts/create.html`, `handover/*`, `payment/*` | Nhóm field theo section, tổng tiền "sticky", nút thêm/xóa dòng rõ ràng; kiểm mobile. (Krug/Wroblewski) |
| U5 | Low | **Hành động phá hủy** (cancel/delete document) cần xác nhận + nêu hậu quả rõ | `documents/delete/<id>`, các `*/cancel` | Confirm dialog + mô tả hệ quả (đặc biệt cascade delete — xem DB5). (Norman) |

**Điểm tốt:** có `<meta viewport>` (responsive-ready), `<html lang>` động, label + `for=` + `required` (accessibility cơ bản OK), timeline vòng đời trực quan.

## B. Clean Code & Kiến trúc — Uncle Bob · Fowler · Beck

| Mã | Mức | Finding | Bằng chứng | Khuyến nghị |
|----|-----|---------|-----------|-------------|
| A1 | **High** | **God controller:** `dashboard_routes.py` 2838 dòng, ~75 route, mọi domain trộn lẫn | `wc -l` = 2838 | Tách theo domain thành blueprint riêng: orders/quotations/contracts/handover/payment/materials/settings. (SRP) |
| A2 | **High** | **Logic nghiệp vụ + tính tiền nằm trong route**, bỏ qua service layer | `create_quotation` (588-648), `create_contract` (829-919), `create_payment` (1553-1616) tự tính subtotal/VAT/total | Chuyển tính toán vào service (`QuotationService.build_totals(...)`). (Fowler: long method, feature envy) |
| A3 | Med | **Trùng lặp parse item + tính tổng ~7 lần** | 7× `getlist('item_name[]')` | Trích 1 helper `parse_line_items(form) -> (items, subtotal)` dùng `Decimal`. (DRY) |
| A4 | Med | **47× `except Exception`** nuốt mọi lỗi → giấu bug, luôn flash chung chung | `grep -c except Exception` = 47 | Bắt hẹp (ValueError/IntegrityError...); lỗi bất ngờ để bubble lên 500 handler + log stacktrace. |
| A5 | Low | **60× import cục bộ trong hàm** (`from app... ` lặp trong handler) | `grep` = 60 | Đưa import lên đầu module; nếu do circular import → tách module để lộ nợ kiến trúc. |
| A6 | Med | **Kiểm tra tenant thủ công, lặp & không nhất quán** ở route (`x.order.company_id != company_id`); nơi quên → IDOR | root **B7** (`repository.py:30`), thiếu ở **B5** | Thêm lookup có scope (`get_by_id_for_company`) hoặc decorator guard tập trung; xóa kiểm thủ công rải rác. |

## C. Database — Senior DBA

| Mã | Mức | Finding | Bằng chứng | Khuyến nghị (migration Postgres-compat, rollback được) |
|----|-----|---------|-----------|-------------|
| DB1 | **High** | Số hiệu chứng từ unique **toàn cục** (B3) | model `unique=True`; route 591/834/1218/1518 | Đổi sang `UniqueConstraint(company_id, number)` + bỏ filter toàn cục (D1 đã duyệt) |
| DB2 | Med | Thiếu index tổ hợp cho truy vấn list phổ biến | list_orders lọc `(company_id, store_id, is_active)` + order by `created_at` | Thêm index `(company_id, created_at)`, `(company_id, is_active)` cho orders/customers |
| DB3 | Med | **Line-items JSON denormalized** + cột tổng → dễ lệch (P5) | `items` JSON trên 4 bảng chứng từ | Ngắn hạn: validate tổng khi ghi. Dài hạn (Đề xuất tương lai): bảng line-item chuẩn hóa |
| DB4 | Med | **Không có Alembic**; schema đổi bằng script tay | `scripts/*.py` | Dựng Alembic (hạ tầng an toàn) — baseline migration từ models hiện tại |
| DB5 | Low | Cascade delete Company/Order xóa sạch chứng từ, không soft-delete/confirm | `models.py` cascade | Soft-delete hoặc chặn/hỏi trước khi xóa cứng; ưu tiên dùng cờ `is_canceled` sẵn có |
| DB6 | Low | `datetime.utcnow` naive (không tz) dù có cột `timezone` | toàn model | Chuyển sang timezone-aware (`datetime.now(timezone.utc)`); cột `TIMESTAMPTZ` |

**Điểm tốt:** tiền dùng `Numeric(15,2)` (đúng); FK có index; UUID PK.

## D. Security — OWASP Top 10

| Mã | Mức | OWASP | Finding | Bằng chứng | Khuyến nghị |
|----|-----|-------|---------|-----------|-------------|
| S1 | **High** | A01/A05 | **Không có CSRF** trên bất kỳ form POST nào | 0 `csrf_token` trong `templates/`; Flask-WTF không có trong deps | Thêm `Flask-WTF CSRFProtect`, token vào mọi form + fetch POST |
| S2 | **High** | A01 | **IDOR ghi xuyên tenant** (B5, root B7) | test `test_create_order_rejects_cross_tenant_customer` xfail | Lookup có scope company; verify customer/store thuộc tenant |
| S3 | Med | A05 | `SECRET_KEY` default hardcode (P6) | `config.py:15` | Fail-fast nếu prod thiếu `SECRET_KEY` env |
| S4 | Med | A07 | **Không rotate session khi login** (session fixation) | `auth_utils.set_user_context` không `session.clear()`/regenerate trước khi set | `session.clear()` rồi set lại khi đăng nhập thành công |
| S5 | Low | A09 | 47 bare-except + flash chung → thiếu log an ninh hữu ích | A4 | Log có ngữ cảnh; đảm bảo prod `DEBUG=False` (rò traceback) |
| S6 | Low | A06 | CDN không SRI (supply-chain) | base.html:11-13 | SRI hoặc vendor asset |
| S7 | Med(verify) | A05/A08 | Upload template/ảnh cần kiểm loại/đuôi/kích thước | `upload_template`, `_save_item_image` | Allowlist đuôi (.docx/.png/.jpg), kiểm MIME; `MAX_CONTENT_LENGTH` đã có (50MB) |

## E. Performance & Reliability

| Mã | Mức | Finding | Bằng chứng | Khuyến nghị |
|----|-----|---------|-----------|-------------|
| PF1 | Med | **N+1** ở list views (mỗi order truy cập lazy `customer`/`store`/`lifecycle`) | `list_orders` trả list, template lặp | `joinedload`/`selectinload` các quan hệ hiển thị |
| PF2 | Med | **Phân trang giả:** hardcode `limit(20)/offset`, không đếm tổng → không biết trang cuối | `list_orders` (không dùng `.paginate()`); `ITEMS_PER_PAGE` khai báo nhưng không dùng | Dùng `db.paginate()`; render next/prev + tổng trang |
| PF3 | Low | Sinh DOCX/PDF **đồng bộ** trong request | `generate_document`, template_engine | Chấp nhận ở tải thấp; ghi chú; cân nhắc job nền nếu tăng tải |

---

## Tổng hợp mức độ (đầu vào cho GĐ4)
- **High:** B5/S2 (IDOR ghi), B3/DB1 (số hiệu toàn cục), S1 (CSRF), A1 (god controller), A2 (logic trong route).
- **Medium:** B6, B2, A3, A4, A6, DB2, DB3, DB4, S3, S4, S7, PF1, PF2, U1, U2.
- **Low:** B1, B4, A5, DB5, DB6, S5, S6, U3, U4, U5, PF3.

**Đề xuất tương lai (không tự làm):** bảng line-item chuẩn hóa (DB3); job nền sinh tài liệu (PF3); soft-delete toàn diện (DB5).
