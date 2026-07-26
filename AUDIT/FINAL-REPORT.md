# SofaFlow — BÁO CÁO BÀN GIAO (Audit & Refactor)

**Nhánh:** `refactor/full-audit` (tách từ `main` @ `22fb9eb`) · **Ngày:** 2026-07-25 → 2026-07-26
**Người thực hiện:** Coding agent (Principal Engineer + Product Owner) — chạy tự chủ qua đêm theo spec đã duyệt.
**Trạng thái:** ✅ Bảo mật, toàn vẹn dữ liệu/schema, refactor lõi, perf, UX cơ bản **đã xong & verify**. **Phase 7 (ủy quyền 2026-07-26):** đã quyết NR1/NR2/NR3 theo chuẩn ngành + xây feature **cột mở rộng extend01–10 có config admin** + test E2E vài đơn hàng. **Chưa merge** — chờ bạn review. **39 commit, 42 test pass, 1 xfail (B6 = NR1 "by design", giữ làm tài liệu).**

> **Phase 7 mới nhất:** xem §10 (cột mở rộng) + §6 (NR đã giải quyết). B6/NR1 xfail được GIỮ để làm tài liệu về quyết định "không bắt buộc quotation duyệt".

> ĐỌC FILE NÀY TRƯỚC. Chi tiết từng bước ở `AUDIT/CHANGELOG.md`; quyết định tự chủ ở `AUDIT/DECISIONS.md`; việc cần bạn quyết ở `AUDIT/NEEDS-REVIEW.md`.

---

## 1. Trước / Sau

| Hạng mục | Trước | Sau |
|----------|-------|-----|
| Test tự động | **0** | **43** (42 pass, 1 xfail) gồm 3 E2E đơn hàng — pytest trên SQLite, không cần Docker |
| Cột mở rộng do người dùng | Không có | **extend01–10 / mỗi loại chứng từ**, admin bật/tắt + đặt nhãn + kiểu + bắt buộc |
| Số hiệu chứng từ | Global unique | **Unique per company (DB-level, có cột company_id)** |
| CSRF | Không có ở bất kỳ form nào | Bật toàn site (Flask-WTF) — 69 form/39 template |
| IDOR ghi xuyên tenant | Có (tạo order cho tenant khác) | Đã chặn (lookup có scope company) |
| Số hiệu chứng từ | Unique **toàn cục** (rò rỉ giữa tenant) | Unique **per-order** + enforce **per-company** ở app (cả 4 loại chứng từ) |
| Session fixation | Không rotate khi login | `session.clear()` khi login |
| SECRET_KEY prod | Default hardcode chạy được | Fail-fast nếu prod thiếu env |
| Migration | Không có (script tay) | **Alembic** + 4 migration reversible, Postgres-compatible |
| Index list query | Thiếu | `(company_id, created_at)` & `(company_id, is_active)` cho orders/customers |
| N+1 danh sách đơn | Có | `joinedload(customer, lifecycle)` |
| Trùng lặp parse item | 5+ block `float` | 1 helper `parse_line_items` (Decimal) |
| Chạy được app | Có | Có (mỗi commit đều build + test xanh) |

---

## 2. Bug đã sửa (bug catalog GĐ2 → fix GĐ5)

| ID | Mức | Bug | Fix (W#) |
|----|-----|-----|----------|
| B5/B7 | High | Tạo order xuyên tenant (IDOR ghi); `BaseRepository.get_by_id` không scope | W2 — `CustomerRepository.get_for_company` + kiểm store accessible |
| B3 | High | Số hiệu chứng từ unique toàn cục | W6 (quotation) + W6b (contract/handover/payment) |
| B2 | Medium | Số lượng/đơn giá âm được chấp nhận | W7 + W9 (validate tập trung trong `parse_line_items`) |
| B1 | Low | Route `/api/quotations/<id>` đăng ký trùng | W19 |
| B4 | Low | Tính tiền bằng `float` | W9 (Decimal trong helper) |
| B6 | Medium | Contract tạo được không cần quotation duyệt | **KHÔNG tự sửa** → NR1 (quyết định nghiệp vụ) |

## 3. Sửa bảo mật (OWASP)

- **CSRF (S1, A01/A05):** `CSRFProtect` trong app factory; token ẩn trong mọi form POST; API `check_code` (read-only) được exempt. Test: POST thiếu token → 400.
- **IDOR (S2/B5):** tạo order xác minh customer + store thuộc company hiện tại.
- **Số hiệu per-tenant (B3):** không còn dùng chung không gian số hiệu giữa các công ty.
- **Session fixation (S4):** clear session khi đăng nhập (giữ ngôn ngữ).
- **SECRET_KEY (S3):** prod bắt buộc set qua env, nếu không → refuse start.

## 4. Thay đổi kiến trúc & schema

**Kiến trúc:**
- `app/models/types.py::GUID` — kiểu UUID portable (Postgres `uuid` native, SQLite CHAR(36)) → app test được trên SQLite, **prod Postgres không đổi DDL/dữ liệu**.
- `parse_line_items(form, files, with_images)` — gom 5 block parse item, validate, Decimal.
- Import repository đưa lên đầu `dashboard_routes.py` (bỏ 27 import inline trùng).

**Schema (Alembic, đều reversible + round-trip đã verify trên SQLite):**
| Revision | Nội dung |
|----------|----------|
| `2ede8fb2868b` | Baseline (18 bảng) |
| `acb618e15b19` | `quotations`: bỏ unique toàn cục → `unique(order_id, quotation_number)` |
| `e1b399a3d96d` | contract/handover/payment: tương tự (3 bảng) |
| `68c0ef8699e4` | Index tổ hợp `(company_id, created_at)`/`(company_id, is_active)` |

> **Áp dụng lên prod:** backup trước → `alembic stamp head` một lần nếu DB đã tồn tại (đánh dấu baseline) → hoặc chạy tuần tự các revision sau baseline. App vẫn `create_all()` lúc khởi động (fresh install tự có schema mới).

## 5. Giả định nghiệp vụ CẦN BẠN RÀ

- **`advance_skipped` (giữ nguyên logic — D1):** luật suy luận từ code (`skip_advance_payment`): *chỉ khi hợp đồng đã ký* mới được "bỏ qua tạm ứng"; khi bỏ qua, hệ thống đặt `advance_skipped=True` **và** `advance_paid=True` để mở khóa bàn giao + thanh toán cuối mà không ghi nhận một chứng từ tạm ứng. Nếu luật đúng của bạn khác (vd không coi là đã trả), cần điều chỉnh — **agent KHÔNG đổi logic dòng tiền**.
- **Chuẩn hóa `name.strip()`** trong `parse_line_items`: item name bị bỏ khoảng trắng thừa (trước đây một số chỗ giữ nguyên). Vô hại nhưng nêu để bạn biết.

## 6. NEEDS-REVIEW — ĐÃ GIẢI QUYẾT (bạn ủy quyền 2026-07-26; xem DECISIONS D6–D8)

- **NR1 — B6:** ✅ **KHÔNG bắt buộc quotation duyệt (by design)** — chuẩn quote-to-cash/CPQ. Không đổi code; test `test_create_contract_requires_approved_quotation` giữ `xfail` như tài liệu "đây là hành vi cố ý".
- **NR2 — cascade vs soft-delete:** ✅ **Soft-delete là chuẩn.** Xác minh không có route hard-delete Company/Order → giữ nguyên; không expose xóa cứng.
- **NR3 — per-company DB-level:** ✅ **ĐÃ LÀM.** Thêm cột `company_id` (auto-backfill từ order qua `before_insert`) + unique `(company_id, number)` cho cả 4 bảng chứng từ (migration `42d15126ff2c`).
- **`advance_skipped`:** vẫn giữ nguyên logic (D1) — luật đã ghi ở §5, chờ bạn xác nhận nếu khác.

## 7. Đánh bóng — trạng thái

**Đã làm thêm (verify được):**
- ✅ **W18 + W18b (perf):** phân trang thật `db.paginate` cho danh sách **đơn hàng** và **khách hàng** (+ partial `_pagination.html` dùng lại, giữ filter store_id/search).
- ✅ **W15 (UX):** `min="0"` cho 22 input số lượng/đơn giá (mirror guard B2 phía server).
- ✅ **W14 (UX/i18n):** khóa `Previous`/`Next`, bọc `t()` heading "Create Order" (đa số heading khác đã dùng `t()` sẵn).

**Còn lại — vòng lặp ĐÃ DỪNG ở đây (lý do: long-tail / không verify được tự động / rủi ro cao). Cách tiếp tục nếu bạn muốn:**
| Mục | Việc | Vì sao chưa làm | Gợi ý resume |
|-----|------|-----------------|--------------|
| W14 (còn) | Bọc `t()` cho `<title>`/placeholder hardcode còn lại | Long-tail nhiều template, giá trị hiển thị thấp | Làm dần khi động vào từng template |
| W15b | `confirm()` cho form hủy/xóa còn thiếu | Đa số đã dùng **modal xác nhận**; confirm không test tự động được | Rà thủ công lúc review UI |
| W16 | SRI cho link CDN Bootstrap | **Cần hash đúng** — hash sai chặn tải trang, không verify offline | Chạy khi có mạng, hoặc vendor asset vào `static/` |
| W10 | Tách god-controller `dashboard_routes.py` (~2900 dòng) thành blueprint theo domain | **Rủi ro cao**, cần regression net rộng | Làm có chủ đích, từng domain, giữ đường lui |
| W11 (còn) | Thu hẹp 47 `except Exception` | Đường lỗi không có test → đổi (500 thay vì flash) không verify an toàn | Thêm test cho đường lỗi trước, rồi thu hẹp |
| NR3 | Ràng buộc DB-level per-company cho số hiệu | Cần prod DB + backup để kiểm backfill | Xem NEEDS-REVIEW |

## 8. Rủi ro còn lại

- Migration Postgres **chưa chạy trên prod thật** (máy audit không có Postgres). Kiểu `GUID` và các migration được thiết kế Postgres-compatible & verify trên SQLite; **cần smoke test trên 1 bản sao prod trước khi merge** (xem D4).
- Bare-except còn nhiều → lỗi bất ngờ vẫn bị nuốt thành flash chung (không phải regression mới; là hiện trạng chưa dọn).
- Test bao phủ luồng chính + bảo mật, chưa phủ hết mọi edge case/route.

## 9. Hướng dẫn merge an toàn `refactor/full-audit`

1. **Backup DB prod.**
2. Review diff + `AUDIT/CHANGELOG.md`; quyết NR1/NR2/NR3.
3. Dựng 1 bản sao Postgres từ prod → `pip install -r requirements.txt` (đã thêm Flask-WTF) → `alembic stamp head` (nếu DB đã có schema) hoặc chạy migration → smoke test đăng nhập + tạo quotation/contract/payment + sinh tài liệu.
4. Chạy `venv/Scripts/python.exe -m pytest` (cần `pip install -r requirements-dev.txt`).
5. Đặt biến môi trường prod: **`SECRET_KEY` bắt buộc** (nếu không app sẽ refuse start — đúng thiết kế).
6. Merge (không force-push; agent chưa merge/không đụng prod theo lằn ranh đã thống nhất).

---
## 10. Feature mới — Cột mở rộng do người dùng (extend01–extend10)

Mục tiêu: 1 hệ thống không cover hết nhu cầu doanh nghiệp → mỗi loại chứng từ có **10 cột mở rộng** admin tự cấu hình.

- **Mô hình (D9 — chuẩn "flexfield" như Oracle/SAP/Odoo):** 4 bảng chứng từ có `extend01..extend10` (TEXT). Bảng `extension_field_configs` (per company, per entity_type, per slot) giữ: bật/tắt, **nhãn**, **kiểu dữ liệu** (text/number/date/boolean), **bắt buộc**, thứ tự.
- **Admin cấu hình:** `/settings/extension-fields` (chỉ company_admin) — tab theo loại chứng từ, 10 slot mỗi loại.
- **Người dùng nhập:** field đang bật tự hiện trên form tạo chứng từ (nhãn + kiểu do admin đặt); validate bắt buộc + kiểu ở server; lưu vào cột `extendNN`.
- **Cách ly tenant:** config theo `company_id`; công ty khác không thấy field của nhau.
- **Item-level:** item hiện lưu JSON (schemaless) → có thể thêm khóa `extendNN` vào item mà không đổi schema; UI render item-extension để **Đề xuất tương lai** (chưa làm).
- **Test:** validation (required/number/date/boolean), config-save→hiện-trên-form, persist qua HTTP, + E2E đơn hàng có extension.
- **Files:** `app/models/models.py` (`DocExtensionMixin`, `ExtensionFieldConfig`), `app/utils/extension_fields.py`, `app/templates/settings/extension_fields.html`, `_extension_fields_form.html`, migration `42d15126ff2c`.

---
*Tổng: 39 commit trên nhánh, mỗi commit build + test xanh (42 pass, 1 xfail). Không merge, không force-push, không đụng production. Feature cột mở rộng được thêm theo yêu cầu trực tiếp của chủ dự án.*
