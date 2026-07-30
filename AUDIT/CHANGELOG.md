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

## W11 (một phần an toàn) — Gom import repository lên đầu module  ✅
- **Finding:** A5 (Low). ~60 import cục bộ lặp trong hàm.
- **Fix (phần AN TOÀN):** thêm 6 repo (Quotation/Contract/Handover/Payment/Lifecycle/DocumentTemplate) vào import đầu `dashboard_routes.py`; xóa **27 dòng import inline trùng** (không alias). Giữ import có alias (`... as _X`) và import model (nhiều alias `_CompanyQ/_Store/...`) để tránh sửa hàng loạt điểm dùng.
- **Verify:** `import app.routes.dashboard_routes` OK; suite **23 passed, 1 xfailed**.
- **HOÃN (ghi rõ lý do):** (a) thu hẹp 47 `except Exception` — đa số bọc cả DB + parse trong 1 try, đổi sẽ khiến lỗi bất ngờ nhảy 500 thay vì flash; **đường lỗi không có test → không verify an toàn được** → để nguyên (đưa vào "Đề xuất tương lai"). (b) gom import model có alias — rủi ro/nhiều điểm dùng, giá trị thấp. → xem FINAL-REPORT.
- **Files:** `app/routes/dashboard_routes.py`.

## W17 — Chống N+1 ở danh sách đơn hàng  ✅
- **Finding:** PF1 (Medium). `orders/list.html` truy cập `order.customer.name` + `order.lifecycle.*` mỗi dòng → lazy-load N+1.
- **Fix:** `joinedload(customer, lifecycle)` ở `OrderRepository.get_orders_for_company` (đường company_admin) **và** ở query nhánh non-admin trong `list_orders`.
- **Test:** `test_list_views.py` — `/orders` render 200 có/không có đơn.
- **Suite:** **25 passed, 1 xfailed**.
- **Files:** `app/repositories/repository.py`, `app/routes/dashboard_routes.py`, `tests/test_list_views.py`.

## W18 — Phân trang thật cho danh sách đơn hàng  ✅
- **Finding:** PF2 (Medium). `list_orders` dùng `limit/offset` thủ công, không tổng số/next/prev.
- **Fix:** hợp nhất 2 nhánh (admin/non-admin) thành 1 query + `db.paginate(..., error_out=False)`; dùng `ITEMS_PER_PAGE`. Partial dùng lại `templates/_pagination.html` (total + prev/next, giữ query params). Trang ngoài phạm vi → render rỗng (không 404/500).
- **Test:** `test_orders_list_out_of_range_page_does_not_crash`. Suite: **26 passed, 1 xfailed**.
- **Files:** `app/routes/dashboard_routes.py`, `app/templates/orders/list.html`, `app/templates/_pagination.html`, `tests/test_list_views.py`. *(list_customers: xem W18b nếu làm.)*

## W15 (một phần) — `min="0"` cho input số lượng/đơn giá  ✅
- **Finding:** U2 (Medium). Input số cho phép nhập âm ở client (mirror B2 phía server).
- **Fix:** thêm `min="0"` vào 22 input `item_quantity[]`/`item_price[]` (7 template) còn thiếu.
- **Test:** `test_create_pages_render.py` — trang tạo quotation/order render 200 sau khi sửa.
- **Suite:** **28 passed, 1 xfailed**.
- **CÒN LẠI (W15b, UX — ghi future):** rà & thêm `confirm()` cho các form hủy/xóa còn thiếu; không có test tự động cho confirm → làm thủ công/khi review.
- **Files:** 7 template create/edit, `tests/test_create_pages_render.py`.

## W18b — Phân trang thật cho danh sách khách hàng  ✅
- **Finding:** PF2. `list_customers` dùng `limit/offset` thủ công.
- **Fix:** đường "browse" (không search) — single-store & all-stores — dùng `db.paginate(error_out=False)` + `order_by(customer_code)`; đường **search giữ nguyên** (trả full list, `pagination=None`). Truyền `extra_query` (store_id, search) để `_pagination.html` giữ filter khi chuyển trang.
- **Test:** `/customers` render 200; `/customers?store_id=..&page=999` không crash.
- **Suite:** **30 passed, 1 xfailed**.
- **Files:** `app/routes/dashboard_routes.py`, `app/templates/customers/list.html`, `tests/test_list_views.py`.

---

# PHASE 7 — NR decisions + Extension fields feature (ủy quyền 2026-07-26)

## NR1/NR2/NR3 — Giải quyết (xem DECISIONS D6–D8)
- **NR1:** Contract KHÔNG bắt buộc quotation duyệt (by design, chuẩn CPQ). Không đổi code.
- **NR2:** Soft-delete là chuẩn; xác minh không có đường hard-delete Company/Order. Không đổi code.
- **NR3:** Làm — số hiệu chứng từ unique per `(company_id, number)` ở tầng DB.

## W-NR3 + W-EXT — company_id per-tenant + cột mở rộng extend01–10 + config
- **Schema:** `DocExtensionMixin` thêm `company_id` (NOT NULL, auto-backfill qua `before_insert`) + `extend01..extend10 (TEXT)` cho 4 bảng chứng từ; unique đổi sang `(company_id, number)`. Model mới `ExtensionFieldConfig` (per company/entity/slot: enabled/label/data_type/required/sort_order).
- **Migration:** `42d15126ff2c` — thêm cột (nullable) → **backfill company_id từ orders** → NOT NULL + swap unique + index + FK; tạo bảng config. Dialect-aware, reversible. **Verify với dữ liệu thật + round-trip trên SQLite.**
- **Logic:** `app/utils/extension_fields.py` — đọc config, validate (required + data_type: text/number/date/boolean), collect + apply. Wire vào 4 luồng tạo chứng từ.
- **UI:** trang admin `/settings/extension-fields` (company_admin) cấu hình bật/tắt + nhãn + kiểu + bắt buộc theo entity; partial `_extension_fields_form.html` render field bật trên form tạo (qua context processor); link nav.
- **Test:** `test_extension_fields.py` (9: validation + config-save→hiện-trên-form + persist + required), `test_e2e_orders.py` (3 đơn E2E: full lifecycle→completed, đơn có extension field, đơn hủy).
- **Suite:** **42 passed, 1 xfailed.**
- **Files:** `app/models/models.py`, `app/utils/extension_fields.py`, `app/routes/dashboard_routes.py`, `app/__init__.py`, `app/templates/settings/extension_fields.html`, `app/templates/_extension_fields_form.html`, 4× create templates, `base.html`, `migrations/versions/42d15126ff2c_*.py`, tests.

---

# FEATURE 2 — Kế hoạch sản xuất (2026-07-27)

## F2 — Production Planning (Hybrid định mức + trừ kho + cảnh báo tồn)  ✅
- **Models:** `ProductionPlan` (1/order, auto company_id qua before_insert, unique plan_number/company), `ProductionPlanItem`, `ProductionMaterialLine`, `MaterialNorm` (định mức tái sử dụng theo product_key). Migration `276bb213979a` (reversible, round-trip OK).
- **Service `ProductionPlanService`:** `create_from_contract` (copy item HĐ + gợi ý vật tư từ định mức = qty_per_unit × SL), `issue_materials` (kiểm tồn → nếu đủ trừ `MaterialStock` + set quantity_issued + status in_progress; nếu thiếu trả shortages, KHÔNG trừ), `save_as_norm` (upsert định mức), `low_stock_materials`.
- **Hook:** `ContractService.mark_signed` tự tạo kế hoạch (best-effort, không chặn ký nếu lỗi).
- **Routes/UI:** `/orders/<id>/production-plan` (xem/sửa), thêm/xóa vật tư, `/issue` (cấp phát), `/save-norm/<item>`, `/materials/low-stock`. Template `production/plan.html`, `materials/low_stock.html`; link ở order view + nav (Low Stock). CSRF token đầy đủ.
- **Test:** `test_production_plan.py` (6) + E2E sign→auto-plan. Scope đợt 1: KH + trừ kho + cảnh báo tồn (PO để sau).
- **VERSION → 1.4.0.**

---

# LOGIN + TEMPLATE FIELDS (2026-07-27)

## L1 — Đăng nhập bằng email + password (thay hẳn 3 trường)  ✅
- **Model:** `User.email` → **unique toàn cục** (migration `3b58dbc4e87a`, round-trip OK). Email là định danh đăng nhập, company suy từ user.
- **Service:** `UserService.authenticate_by_email(email, password)` — tra user theo email (case-insensitive, chỉ active).
- **Route/UI:** `/auth/login` nhận `email`+`password`; form login còn 2 trường (bỏ company_code + username).
- **Test:** `test_email_login.py` (5: login OK, case-insensitive, sai pass/email, email unique). Cập nhật `conftest.login` (resolve username→email) + `test_auth_session`.

## L2 — Bổ sung field DB cho template chuẩn  ✅
- **Model:** `Company.business_registration_number` (Số ĐKKD/GPKD), `Company.website`, `Company.logo_path`; `Contract.warranty_months`, `Contract.delivery_terms`. Migration `5c706597ac41` (round-trip OK).
- **Template:** `DocumentVariableCollector` expose `company_business_registration_number`, `company_website`, `warranty_months`, `delivery_terms` (dùng được trong .docx).
- **UI:** trang Cài đặt công ty thêm ô Số ĐKKD + Website (route lưu). Test `test_company_fields.py`.
- **VERSION → 1.5.0.**

---

# HANDOVER-PREP + POLISH (2026-07-29..30) — VERSION 1.6.0 → 1.6.6

## Chứng từ & i18n
- **i18n:** dịch 122 khóa còn thiếu → tiếng Việt phủ 100% `t()` trong template. Sửa collector: `COMPANY_NAME` alias, `quotation_number`/`total_amount` cho phiếu thanh toán, fallback quotation của hợp đồng.
- **Header ngày/tỉnh:** dòng "`<Tỉnh/TP>, ngày … tháng … năm …`" lấy **city từ Store** (`order.store`) + ngày của chính chứng từ; sửa header hợp đồng in trống. Test `test_document_variables.py`.
- **Rà soát 100% template:** trình audit đối chiếu mọi placeholder (body+header+footer) với context thật → **0 ô trống**. Templates thật ở `uploads/templates/NGOCHAN/` (không phải `SOFA-NGOCHAN/`).
- **Tách phiếu tạm ứng vs thanh toán:** `scripts/create_payment_templates.py` sinh 2 mẫu `payment_advance`/`payment_final` (docxtpl, dùng đúng pattern for-row/content/endfor-row). Test `test_payment_templates.py`.
- **PDF thật:** Dockerfile cài `libreoffice-writer` + `fonts-liberation`; convert profile-per-call; báo rõ nếu fallback DOCX.

## Kế hoạch sản xuất
- **Chốt lệnh:** `can_edit()` = draft-only (duyệt = khóa BOM), thêm `can_issue()` (approved/processing/rejected); guard route + UI. Test `test_production_plan.py`.
- **F2 phase-2 — Đề xuất mua hàng (PO):** `ProductionPlanService.purchase_suggestions` bung định mức các kế hoạch active, trừ tồn + bù min, gộp theo NCC; trang `/materials/purchase-suggestions`. Test `test_purchase_suggestions.py`.

## Vận hành & UX
- **Backup DB:** `scripts/backup_db.sh` + cron 02:30; giữ 3 ngày + 2 tháng (max 5); kiểm tra gzip/size trước khi xoay vòng.
- **Reset/seed bàn giao:** `scripts/reset_company_data.py`, `scripts/seed_demo_order.py`, `scripts/seed_sofa_taxonomy.py`.
- **W14/W15b/W16:** tiền tệ VND (`… đ`, bỏ `$X.XX` ở 11 chỗ); confirm() cho deactivate user/store; chuẩn hóa bootstrap-icons 1.11.0.

---

# FEATURE 3 — Vòng tuần hoàn cung ứng + Extend fields (2026-07-30) — VERSION 1.7.0

## Đóng vòng vận hành: Order → SX → trừ kho → PR → PO → GR → tăng tồn → SX/bán
- **Models mới:** `PurchaseOrder`(+`PurchaseOrderLine`), `GoodsReceipt`(+`GoodsReceiptLine`) — có máy trạng thái PO (draft→ordered→partial→received/canceled) và extend fields. Migration `a4733fe5b1e5` (4 bảng + extend01..10 cho stores/customers/orders/suppliers/materials; additive/nullable, reversible, round-trip OK).
- **`ProcurementService`:** `create_pos_from_suggestions` (PR→PO, gộp theo NCC), `add_line/delete_line/set_header`, `transition`, và `receive` (GR) — **tăng `MaterialStock`** + đồng bộ trạng thái PO. `print_purchase_order` sinh docx "ĐƠN ĐẶT HÀNG".
- **UI:** trang Đơn mua hàng (list + chi tiết), nút "Tạo đơn mua từ đề xuất" ở trang PR, form Nhận hàng (GR), nav links.
- **Test:** `test_procurement.py` (service + HTTP loop), `test_full_loop.py` (E2E: order→plan→issue→shortage→PR→PO→GR→issue thành công, tồn kho khớp từng bước).

## Redesign CRUD tài liệu PR/PO/GR (ERP-lite, 1.7.1)
- **PR (Đề nghị mua hàng)** trở thành tài liệu đầy đủ CRUD: model `PurchaseRequisition`(+lines), tạo tay không phụ thuộc tồn kho (mua dự phòng), điền sẵn từ đề xuất tự động; vòng đời draft→submitted→approved→converted/canceled; duyệt xong **convert → PO** (gộp theo NCC). `PurchaseOrder.pr_id` (ref PR hoặc đứng độc lập). Migration `61397f4c3104` (named FK, round-trip OK).
- **PO** đổi sang CRUD kiểu tài liệu: form tạo/sửa gồm header + nhiều dòng, **lưu một lần** (bỏ kiểu tạo-PO-rỗng-rồi-tự-lưu-từng-dòng). View chỉ đọc + hành động (gửi NCC/hủy/in/nhận hàng) + hiển thị nguồn PR.
- **GR (Nhập kho)** thành đối tượng quản lý riêng: danh sách `/goods-receipts` + chi tiết. Hỗ trợ **nhận một phần** (PO→partial), **nhiều đợt** (mỗi đợt 1 GR), **nhận đủ** (PO→received); mỗi GR tăng `MaterialStock`.
- Partial `_material_lines_editor.html` (JS thêm dòng + tự điền ĐVT/đơn giá). Nav: Đề xuất tự động → PR → PO → GR. Test `test_requisition.py` + `test_procurement_crud.py` (CRUD HTTP đầy đủ).

## Extend fields cho master data
- `ExtensionFieldConfig.ENTITY_TYPES` phủ customer/supplier/material/store/order/purchase_order/goods_receipt (trang cấu hình dùng chung → tự có, nhãn VI). Wire collect/apply vào create customer/supplier/material; partial pre-fill giá trị khi sửa. Test `test_extend_master.py`.
- **Còn lại (để sẵn, cùng mẫu):** wire form store/order + các form edit — cột & cấu hình đã sẵn, chỉ cần include partial + collect/apply.

---

## HOÃN (khuyến nghị làm riêng, có review)
- **W10** tách god-controller `dashboard_routes.py` thành blueprints — rủi ro cao trên prod đang chạy; cần regression đầy đủ + đường lui.
- **W11** thu hẹp 47 `except Exception` — đường lỗi thiếu test, đổi có thể biến flash thành 500.
- **W20** datetime timezone-aware — phạm vi rộng.
- **W16 (đầy đủ):** localize toàn bộ vendor asset vào `static/` hoặc thêm SRI — cần tải + hash file, làm chủ đích.
