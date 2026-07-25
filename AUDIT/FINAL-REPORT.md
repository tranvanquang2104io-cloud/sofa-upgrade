# SofaFlow — BÁO CÁO BÀN GIAO (Audit & Refactor)

**Nhánh:** `refactor/full-audit` (tách từ `main` @ `22fb9eb`) · **Ngày:** 2026-07-25 → 2026-07-26
**Người thực hiện:** Coding agent (Principal Engineer + Product Owner) — chạy tự chủ qua đêm theo spec đã duyệt.
**Trạng thái:** ✅ Bảo mật, toàn vẹn dữ liệu/schema, refactor lõi, perf (N+1 + phân trang), UX cơ bản **đã xong & verify**. Vòng lặp refactor đã **DỪNG** — phần còn lại (§7) là long-tail giá trị thấp / rủi ro cao / cần bạn quyết. **Chưa merge** — chờ bạn review. **32 commit, 30 test pass, 1 xfail (B6/NR1).**

> ĐỌC FILE NÀY TRƯỚC. Chi tiết từng bước ở `AUDIT/CHANGELOG.md`; quyết định tự chủ ở `AUDIT/DECISIONS.md`; việc cần bạn quyết ở `AUDIT/NEEDS-REVIEW.md`.

---

## 1. Trước / Sau

| Hạng mục | Trước | Sau |
|----------|-------|-----|
| Test tự động | **0** | **31** (30 pass, 1 xfail = business rule chờ bạn) — pytest trên SQLite, không cần Docker |
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

## 6. NEEDS-REVIEW (chờ bạn quyết — agent KHÔNG tự làm)

- **NR1 — B6:** Contract có bắt buộc quotation đã duyệt? (enforce có thể phá luồng đang dùng). Mặc định đề xuất: cảnh báo mềm, không chặn.
- **NR2 — Cascade delete vs soft-delete** Company/Order (lưu trữ hồ sơ tài chính).
- **NR3 — Ràng buộc DB-level per-company** cho số hiệu chứng từ (cần thêm cột `company_id` + backfill trên prod — muốn có prod DB + backup để kiểm chứng). Hiện đã per-order (DB) + per-company (app), đủ chặn bug.

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
*Tổng: 32 commit trên nhánh, mỗi commit build + test xanh. Không merge, không force-push, không đụng production, không thêm tính năng mới lớn.*
