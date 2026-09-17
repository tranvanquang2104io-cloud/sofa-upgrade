# CLAUDE.md — Hướng dẫn cho AI coding agent làm việc trên SofaFlow

> Đọc file này trước khi sửa code. Mục tiêu: giúp agent thay đổi đúng chỗ, đúng tầng, không phá multi-tenant và không làm hỏng luồng chứng từ.

## 1. SofaFlow là gì
SaaS multi-tenant quản lý vòng đời khách hàng + tự động sinh chứng từ (DOCX/PDF) cho cơ sở sửa chữa & sản xuất sofa. UI song ngữ EN/VI (mặc định `vi`). Version tại `VERSION`.

## 2. Tech stack
- **Backend:** Python 3.11, Flask 2.3, SQLAlchemy 2.0 (Flask-SQLAlchemy 3.1), Werkzeug auth.
- **DB:** PostgreSQL 16 (prod/dev, Docker, host port **5433**). Test: SQLite in-memory (`TestingConfig`).
- **Frontend:** Jinja2 + Bootstrap 5.3 + Vanilla JS (không có build step).
- **Docs:** python-docx / docxtpl / reportlab.
- **Chạy:** `wsgi.py` (dev) / Gunicorn (prod); Docker compose (`docker compose up` → app :5000, adminer :8080).

## 3. Kiến trúc & quy tắc phân tầng (QUAN TRỌNG)
```
routes/ (HTTP)  →  services/ (business logic)  →  repositories/ (truy vấn DB)  →  models/
utils/auth_utils.py  = session, phân quyền, nạp g.user & g.company_id
utils/template_engine.py = sinh tài liệu; utils/i18n.py = dịch EN/VI
```
**Nguyên tắc khi thêm/sửa tính năng:**
- Logic nghiệp vụ đặt ở `services/`, KHÔNG viết thẳng trong route. (`dashboard_routes.py` hiện đang vi phạm điều này — đừng bắt chước; nếu đụng vào, kéo logic ra service.)
- Truy vấn DB đi qua `repositories/` khi có thể.
- **Luôn filter theo tenant:** mọi query dữ liệu công ty PHẢI ràng theo `g.company_id` (và `store_id` nếu vai trò là store-scoped). Không bao giờ tra cứu tài nguyên chỉ bằng `id` mà không kiểm quyền sở hữu → tránh IDOR.

## 4. Mô hình dữ liệu (xem chi tiết `AUDIT/01-architecture.md`)
UUID PK cho mọi bảng. Trục bán hàng: **Company → Store → User/Customer → Order →
{Quotation → [Contract | OrderConfirmation] → HandoverRecord → PaymentReport} → Document**,
`LifecycleStatus` 1-1 với Order. Một đơn đi theo **Contract** hoặc **OrderConfirmation**
(ĐĐH dưới một HĐNT) — cùng một vị trí trong luồng, do `AgreementService` chọn.
Trục mua hàng: **PurchaseRequisition → PurchaseOrder → GoodsReceipt → SupplierInvoice →
SupplierPayment** (+ `SupplierPaymentAllocation`), tồn kho ở `MaterialStock`.
Cấu hình theo công ty: `workflow_rules`, `normalization_rules`, `extension_field_configs`.
- **Tiền:** dùng `Numeric` (decimal) — không dùng float.
- **Line-items:** lưu trong cột JSON `items` + cột tổng (subtotal/vat/total). Khi sửa items PHẢI tính lại tổng cho khớp.
- **Trạng thái chứng từ:** dùng các method `can_edit/can_approve/can_sign/can_confirm/can_cancel` trên model — tôn trọng chúng, đừng bỏ qua.

## 5. Chạy & test
```bash
# Import kiểm tra nhanh
python -c "from app import create_app; create_app('testing'); print('ok')"

# Bộ test đầy đủ — chạy trên SQLite, KHÔNG cần Postgres/Docker
python -m pytest -q

# Đếm số test (dòng tổng kết của pytest không hiện trên máy này)
python -m pytest --collect-only -q

# Verify một migration (BẮT BUỘC trước khi commit thay đổi schema)
python -m alembic upgrade head && python -m alembic downgrade -1 && python -m alembic upgrade head

# Seed dữ liệu mẫu (cần DB thật đang chạy)
python scripts/create_master_admin.py
python scripts/create_sample_data.py
```

## 6. Quy ước & cạm bẫy
- **i18n:** chuỗi hiển thị cho người dùng nên đi qua `t(key)` (xem `app/utils/i18n.py`), thêm cả EN và VI.
- **CSRF: ĐÃ CÓ** (Flask-WTF `CSRFProtect`, bật toàn site). Mọi form POST PHẢI kèm
  `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`. `TestingConfig`
  tắt CSRF; endpoint `check_code` được exempt vì chỉ đọc.
- **Migration: ĐÃ CÓ Alembic** (`migrations/`). Thay đổi schema = một revision
  **đảo ngược được**, tương thích PostgreSQL, và phải verify round-trip
  `upgrade → downgrade → upgrade` trước khi commit. Không sửa schema bằng script tay nữa.
- **Tiền:** dùng `app/services/money.py` (`compute_totals` / `totals_from_form`) —
  KHÔNG tự tính lại công thức VAT/phí trong route. VAT chỉ tính trên subtotal;
  phí vận chuyển + phí khác cộng SAU VAT và không chịu thuế.
- **Trạng thái & màu:** dùng `app/utils/status_tokens.py` + macro `status_badge`.
  KHÔNG đặt bảng màu riêng trong template — có test lint chặn việc này.
- **Quy trình chứng từ:** thứ tự các bước do `app/services/workflow_service.py`
  quyết định (bảng `workflow_rules` theo từng công ty). KHÔNG thêm `if ...: raise`
  mới rải rác trong service.
- **Chuẩn hóa dữ liệu:** chạy ở tầng ORM (`normalization_service`), không ở route.
  Trường định danh (mã số thuế, số tài khoản, số chứng từ, email, phone) KHÔNG BAO GIỜ
  được chuẩn hóa.
- **Secrets:** không hardcode; đọc từ env. `.env` đã gitignore — không commit. `SECRET_KEY` prod phải set qua env.
- **Uploads:** file sinh ra nằm dưới `app/uploads/documents/` (đã gitignore) — đừng commit.
- **Windows/PowerShell:** dev trên Windows. Clone này KHÔNG có `venv/` — dùng
  `python` toàn cục (3.14). Cần cài thêm: `docxtpl`, `python-docx`, `reportlab`,
  `alembic` thì test template + migration mới chạy.

## 7. Git & quy trình
- Nhánh refactor hiện tại: `refactor/sofa-upgrade-2026q3` (kế hoạch + sổ việc ở
  `REFACTOR-2026Q3.md` — đọc trước khi làm tiếp). Nhánh audit cũ `refactor/full-audit`
  đã xong, tài liệu ở `AUDIT/`.
- Commit nhỏ, Conventional Commits, mỗi commit phải XANH toàn bộ test.
- Tài liệu audit sống trong `AUDIT/` (baseline, architecture, bug catalog, backlog, changelog, final report). Đọc `AUDIT/PROGRESS.md` để biết trạng thái hiện tại.

## 8. Definition of Done cho thay đổi
Có test bảo vệ vùng sửa · không regression luồng khác · tôn trọng tenant isolation & state machine chứng từ · tiền khớp giữa items và tổng · cập nhật i18n · commit sạch, message rõ.
