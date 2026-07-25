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
