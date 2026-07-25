# AUDIT — PROGRESS TRACKER

> File theo dõi tiến độ liên tục cho công cuộc audit & refactor SofaFlow.
> Nhánh làm việc: `refactor/full-audit`. Cập nhật mỗi khi có thay đổi đáng kể.

**Bắt đầu:** 2026-07-25
**Người thực hiện:** Coding agent (Principal Engineer + Product Owner persona)
**Trạng thái tổng thể:** 🟡 Đang chạy — Giai đoạn 2 (đang dựng test & bug catalog)

**Điểm resume (đọc khi khởi động lại):** GĐ2 đang mở. 13 test (11 xanh, 2 xfail = B2 & B3). Đã xác nhận: money math đúng cho input dương; B2 (qty âm), B3 (số hiệu unique toàn cục). Việc TIẾP THEO:
1. **create_order access control:** `dashboard_routes.py:510` dùng `customer_repo.get_by_id(customer_id)` — kiểm xem có lọc company không (nghi IDOR: user cty A tạo order tham chiếu customer cty B nếu get_by_id không scoped). Viết test.
2. **State machine:** create_contract có bắt buộc quotation đã duyệt không? (đọc 816-1070). approve_quotation có chặn re-approve/approve khi canceled? create_payment `final` khi chưa handover?
3. **Role permission:** login `staff` (role user) gọi endpoint company-admin (tạo store/user, /settings/company) → phải 403/redirect.
4. **POST IDOR:** cancel/approve/sign/confirm với id công ty khác.
Sau đó chốt GĐ2 → sang **GĐ3** (hội đồng chuyên gia). Xem checklist trong `02-bug-catalog.md`.

---

## Bảng trạng thái các giai đoạn

| GĐ | Tên | Trạng thái | Artifact | Ghi chú |
|----|-----|-----------|----------|---------|
| 0 | Thiết lập an toàn & Baseline | ✅ Xong | `00-baseline.md` | Branch tạo, app import OK, SQLite build 18 bảng OK |
| 1 | Đọc hiểu sâu (Kiến trúc sư) | 🟡 Bản nháp v1 | `01-architecture.md` | ERD + layer map + user journeys xong; cần xác nhận vài business rule |
| 2 | Testing E2E (QA Lead) | 🟡 Đang chạy | `02-bug-catalog.md` | Harness xong (9 test xanh). Tenant-GET an toàn. B1 tìm được. Còn: luồng tạo, tiền/VAT, state machine, IDOR-POST |
| 3 | Hội đồng chuyên gia | ⬜ Chưa | `03-expert-review.md` | |
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
