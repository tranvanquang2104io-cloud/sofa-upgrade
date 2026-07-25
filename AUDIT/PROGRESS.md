# AUDIT — PROGRESS TRACKER

> File theo dõi tiến độ liên tục cho công cuộc audit & refactor SofaFlow.
> Nhánh làm việc: `refactor/full-audit`. Cập nhật mỗi khi có thay đổi đáng kể.

**Bắt đầu:** 2026-07-25
**Người thực hiện:** Coding agent (Principal Engineer + Product Owner persona)
**Trạng thái tổng thể:** 🟡 Đang chạy — Giai đoạn 3 (hội đồng chuyên gia)

**Điểm resume (đọc khi khởi động lại):** GĐ2 **đã chốt v1** (17 test: 13 pass + 4 xfail = B2,B3,B5,B6). Bug catalog có B1–B7 (B5 High-security, B3 High-data, B7 root). Việc TIẾP THEO = **GĐ3** → viết `AUDIT/03-expert-review.md`:
- **UX** (Norman/Nielsen/Krug/Wroblewski): review `app/templates/` (form nhập dài, feedback, chống lỗi, mobile/responsive, accessibility, i18n).
- **Clean code/kiến trúc** (Uncle Bob/Fowler/Beck): `dashboard_routes.py` 2838 dòng god-controller; tính tiền trong route; lặp parse-items ~5 lần; bare `except Exception`; import cục bộ lặp.
- **DBA:** unique toàn cục (B3), thiếu index tổ hợp `(company_id,...)`, JSON items denormalized, cascade delete, thiếu Alembic.
- **Security OWASP:** CSRF (P1) mọi form POST; IDOR (B5/B7); SECRET_KEY default (P6); session cookie.
- **Performance:** N+1 ở list_orders/list_documents; phân trang thực (ITEMS_PER_PAGE dùng chưa?).
Gộp finding có mã + vị trí + mức. Sau đó **GĐ4** backlog ưu tiên → **GĐ5** loop refactor.

---

## Bảng trạng thái các giai đoạn

| GĐ | Tên | Trạng thái | Artifact | Ghi chú |
|----|-----|-----------|----------|---------|
| 0 | Thiết lập an toàn & Baseline | ✅ Xong | `00-baseline.md` | Branch tạo, app import OK, SQLite build 18 bảng OK |
| 1 | Đọc hiểu sâu (Kiến trúc sư) | 🟡 Bản nháp v1 | `01-architecture.md` | ERD + layer map + user journeys xong; cần xác nhận vài business rule |
| 2 | Testing E2E (QA Lead) | ✅ Xong (v1) | `02-bug-catalog.md` | 17 test. 7 bug (B1–B7). Xác nhận đúng: RBAC, payment-seq, approve-state, tenant-GET. Residual input-fuzz để GĐ3/5 |
| 3 | Hội đồng chuyên gia | 🟡 Bắt đầu | `03-expert-review.md` | UX / Clean-code / DBA / Security / Perf |
| 4 | Ưu tiên hóa | ⬜ Chưa | `04-backlog.md` | |
| 5 | Vòng lặp refactor | ⬜ Chưa | `CHANGELOG.md` | |
| 6 | Hoàn thiện & bàn giao | ⬜ Chưa | `FINAL-REPORT.md` | |

---

## Nhật ký (mới nhất trên cùng)

### 2026-07-25
- Tạo nhánh `refactor/full-audit`.
- Dò tech stack: Flask 2.3 / SQLAlchemy 2.0 / PostgreSQL 16 (Docker) / Bootstrap 5 + Vanilla JS. Python 3.11, venv sẵn có.
- **Feasibility quan trọng:** Docker/Postgres KHÔNG chạy trên máy này, nhưng `TestingConfig` dùng SQLite in-memory → `db.create_all()` dựng **18 bảng OK**. ⇒ có thể chạy app + test E2E hoàn toàn bằng SQLite, không cần Docker.
- Xác nhận `.env` KHÔNG bị commit (an toàn secret).
- Ghi nhận sơ bộ một số vấn đề (chi tiết ở `00-baseline.md` §7 và sẽ chính thức hóa ở GĐ3):
  - Không có Alembic; migration là script tay rời rạc trong `scripts/`.
  - `dashboard_routes.py` = 2838 dòng (god controller).
  - Không có CSRF protection (Flask-WTF không có trong requirements).
  - Số hiệu chứng từ (quotation/contract/report_number) `unique=True` toàn cục thay vì theo tenant.
  - Chưa có test tự động nào.

---

## Câu hỏi mở cho chủ dự án (xem chi tiết `01-architecture.md` §6)
1. Số hiệu chứng từ nên unique theo công ty hay toàn hệ thống?
2. Luồng trạng thái đơn: `advance_skipped` hoạt động chính xác thế nào (bỏ qua tạm ứng)?
3. Có bắt buộc phải giữ Postgres cho prod, hay chấp nhận chạy demo/test trên SQLite?

*(Mặc định nếu không trả lời: (1) chuyển sang unique theo company, (2) suy luận từ code, (3) giữ Postgres cho prod, SQLite chỉ cho test.)*
