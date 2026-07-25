# AUDIT — CHANGELOG (Giai đoạn 5 refactor)

> Nhật ký thay đổi trong vòng lặp refactor. Mỗi mục = 1 work item (W#) đã VERIFY xanh.

## W2 — Fix cross-tenant IDOR khi tạo Order  ✅
- **Finding:** B5/B7/S2 (High). `create_order` dùng `customer_repo.get_by_id` (không scope) và chỉ kiểm `customer.store_id == store_id`, không kiểm company → user cty A tạo được order tham chiếu store/customer cty B.
- **Fix:** thêm `CustomerRepository.get_for_company(id, company_id)` (scoped); route yêu cầu customer thuộc company hiện tại **và** store nằm trong danh sách store user được phép truy cập.
- **Test:** bỏ `xfail` ở `test_create_order_rejects_cross_tenant_customer` → PASS. Suite: 14 passed, 3 xfailed.
- **Files:** `app/repositories/repository.py`, `app/routes/dashboard_routes.py`, `tests/test_access_control_post.py`.

## W7 — Chặn số lượng/đơn giá âm khi tạo Quotation  ✅
- **Finding:** B2/U2 (Medium). `create_quotation` không validate → nhập âm cho ra subtotal/total âm.
- **Fix:** raise `ValueError` khi `qty < 0` hoặc `price < 0` (bị bắt bởi except → flash lỗi, không tạo bản ghi). *(W9 sẽ gom logic này ra helper dùng chung cho contract/handover/payment.)*
- **Test:** bỏ `xfail` ở `test_negative_quantity_is_rejected` → PASS. Suite: 15 passed, 2 xfailed.
- **Files:** `app/routes/dashboard_routes.py`, `tests/test_quotation_money.py`.

## W19 — Xóa route trùng `/api/quotations/<id>`  ✅
- **Finding:** B1 (Low). Decorator `@route` đăng ký 2 lần liên tiếp (copy-paste).
- **Fix:** xóa 1 dòng decorator. Endpoint chỉ còn đăng ký 1 lần.
- **Files:** `app/routes/dashboard_routes.py`.

## W3 — `SECRET_KEY` fail-fast trong production  ✅
- **Finding:** S3/P6 (Medium). Default key hardcode; prod có thể chạy với key dev.
- **Fix:** `create_app('production')` raise `RuntimeError` nếu `SECRET_KEY` là None/rỗng/đúng default. Chỉ ảnh hưởng prod; dev/test giữ nguyên.
- **Test:** `test_config_security.py` (2) — refuse default, chấp nhận key thật.
- **Files:** `app/__init__.py`, `tests/test_config_security.py`.

## W4 — Rotate session khi login (chống fixation)  ✅
- **Finding:** S4 (Medium). `set_user_context` không clear session trước khi set → session fixation.
- **Fix:** `session.clear()` trước khi set danh tính (giữ lại `lang`).
- **Test:** `test_auth_session.py` — giá trị lạ pre-auth bị xóa, vẫn đăng nhập, giữ ngôn ngữ.
- **Files:** `app/utils/auth_utils.py`, `tests/test_auth_session.py`.

**Suite sau W2–W4,W7,W19:** 18 passed, 2 xfailed (còn B3, B6).

## W1 — CSRF protection toàn site  ✅
- **Finding:** S1 (High). Không có CSRF trên bất kỳ form POST nào (Flask-WTF chưa có).
- **Fix:**
  - Thêm `Flask-WTF` (requirements.txt), khởi tạo `CSRFProtect(app)` trong factory.
  - Chèn `{{ csrf_token() }}` (hidden input) vào **69 form POST / 39 template** (script regex, single- & multi-line form tag).
  - **Exempt** `dashboard.check_code` (API kiểm tra mã trùng — read-only, gọi qua fetch POST) → không cần sửa JS.
  - `TestingConfig.WTF_CSRF_ENABLED=False` nên toàn bộ test cũ vẫn xanh.
- **Test:** `test_csrf.py` (2) — POST thiếu token → **400**; `check_code` vẫn dùng được (exempt, không 400).
- **Files:** `app/__init__.py`, `requirements.txt`, 39 templates, `tests/test_csrf.py`.
- **Verify:** GET `/auth/login` (có token) render 200; luồng login (test CSRF off) vẫn chạy. Suite: **20 passed, 2 xfailed**.
- **Lưu ý bàn giao:** khi bật CSRF (prod/dev), mọi form đã có token; nếu sau này thêm `fetch(POST)` mới đổi state → cần gửi header `X-CSRFToken` (token có thể lấy từ `csrf_token()`).

---

## W5 — Dựng Alembic (hạ tầng migration)  ✅
- **Finding:** DB4 (Medium). Không có công cụ migration; schema đổi bằng script tay.
- **Fix:**
  - Thêm `alembic` (requirements-dev.txt), `alembic init migrations`.
  - `migrations/env.py`: lấy metadata từ `db.metadata` (import models trực tiếp, KHÔNG build app để tránh `create_all`); URL từ `DATABASE_URL`/Config; `compare_type=True`; `render_as_batch` cho SQLite.
  - `script.py.mako` + baseline: thêm `import app.models.types` để render kiểu `GUID`.
  - Baseline migration `2ede8fb2868b` (18 bảng) — **autogenerate**.
- **Verify:** `alembic upgrade head` tạo đủ 18 bảng; `alembic downgrade base` xóa sạch (reversible). App suite: **20 passed, 2 xfailed** (không ảnh hưởng).
- **Lưu ý bàn giao:** app vẫn gọi `create_all()` lúc khởi động. Với DB hiện có: chạy **`alembic stamp head`** 1 lần để đánh dấu baseline, rồi các migration W6/W8 áp lên trên. Migration Postgres-compatible.
- **Files:** `alembic.ini`, `migrations/*`, `requirements-dev.txt`.

## W6 — Số hiệu Quotation unique per-order + enforce per-company (app)  ✅
- **Finding:** B3/DB1 (High). `quotation_number` unique **toàn cục** (model + route + service) → tenant khác không dùng lại số được.
- **Quyết định:** xem **D5** — DB unique theo `(order_id, quotation_number)`; enforce per-company ở tầng app (tránh phải thêm cột `company_id` + backfill prod đêm nay). Bản chặt hơn (per-company DB) → **NR3**.
- **Fix:** model bỏ `unique=True`, thêm `UniqueConstraint(order_id, quotation_number)`; `QuotationRepository.get_by_company_and_number` (join Order); service + route check trùng theo company; route truyền `company_id`.
- **Migration:** `acb618e15b19` — dialect-aware (Postgres: drop `quotations_quotation_number_key` + add composite; SQLite: batch add). **Verify upgrade/downgrade round-trip trên SQLite OK.** Không xóa dữ liệu.
- **Test:** bỏ `xfail` `test_same_quotation_number_allowed_across_tenants` → PASS. Suite: **21 passed, 1 xfailed** (chỉ còn B6/NR1).
- **CÒN LẠI (W6b):** contract_number, report_number (handover), report_number (payment) vẫn unique toàn cục — sửa cùng mẫu ở vòng sau.
- **Files:** `app/models/models.py`, `app/repositories/repository.py`, `app/services/services.py`, `app/routes/dashboard_routes.py`, `migrations/versions/acb618e15b19_*.py`, `tests/test_quotation_money.py`.

## W6b — Áp per-order unique cho Contract/Handover/Payment  ✅
- **Finding:** B3/DB1 (High) — nốt nốt còn lại: `contract_number`, `report_number`(handover), `report_number`(payment) vẫn unique toàn cục.
- **Fix (cùng mẫu W6):** model bỏ `unique=True` + `UniqueConstraint(order_id, <number>)` cho 3 bảng; thêm `get_by_company_and_number` (join Order) cho 3 repo; scope lại **cả 6 chỗ check trùng** (3 route + 3 service — service create_contract/handover/payment lấy company từ order).
- **Migration:** `e1b399a3d96d` — dialect-aware cho 3 bảng (Postgres drop `<table>_<col>_key` + add composite; SQLite batch). **Verify upgrade/downgrade round-trip SQLite OK.** Không xóa dữ liệu.
- **Test:** `test_contract_number.py` — 2 công ty cùng số hợp đồng `C-DUP` → OK. Suite: **22 passed, 1 xfailed**.
- **Kết quả:** B3 đã fix hoàn toàn cho cả 4 loại chứng từ (quotation+contract+handover+payment). Bản DB-level per-company chặt hơn vẫn ở **NR3**.
- **Files:** `app/models/models.py`, `app/repositories/repository.py`, `app/services/services.py`, `app/routes/dashboard_routes.py`, `migrations/versions/e1b399a3d96d_*.py`, `tests/test_contract_number.py`.

## W8 — Index tổ hợp cho Orders & Customers  ✅
- **Finding:** DB2 (Medium). Thiếu index cho truy vấn list phổ biến (lọc theo company + sắp xếp theo created_at / lọc is_active).
- **Fix:** thêm vào model:
  - `orders`: `ix_orders_company_created(company_id, created_at)`, `ix_orders_company_active(company_id, is_active)`.
  - `customers`: `ix_customers_company_active(company_id, is_active)`, `ix_customers_company_created(company_id, created_at)`.
- **Migration:** `68c0ef8699e4` (autogenerate, portable — index ops chạy cả Postgres lẫn SQLite). **Round-trip OK.**
- **Test:** suite **22 passed, 1 xfailed** (không đổi hành vi). → **Kết thúc Nhóm 2 (schema).**
- **Files:** `app/models/models.py`, `migrations/versions/68c0ef8699e4_*.py`.

---

## W9 — Trích helper `parse_line_items` (Decimal) + gom validate  ✅
- **Finding:** A2/A3/B4 (Medium/Low). 5+ block parse item lặp lại; tính tiền bằng `float`; negative-guard mới chỉ có ở create_quotation.
- **Fix:** thêm `parse_line_items(form, files=None, with_images=False)` (đầu `dashboard_routes.py`): parse item_name/unit/quantity/price, **validate qty/price ≥ 0** (tổng quát hóa W7 cho contract/payment), tính line total & subtotal bằng `Decimal` rồi trả float (JSON-friendly, khớp `Numeric`). Thay 5 block: create/edit quotation (with_images), create/edit contract, create payment. **Handover giữ parser riêng** (schema item khác: delivered/accepted qty, status, reason).
- **Giữ hành vi:** kết quả số học không đổi (`test_quotation_money.py` là lưới an toàn); chuẩn hóa `name.strip()` (bỏ khoảng trắng thừa) — thay đổi vô hại.
- **Test:** thêm `test_negative_quantity_rejected_on_contract`. Suite: **23 passed, 1 xfailed**.
- **Files:** `app/routes/dashboard_routes.py`, `tests/test_contract_number.py`.
