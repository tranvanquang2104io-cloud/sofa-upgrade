# AUDIT — PROGRESS TRACKER

> File theo dõi tiến độ liên tục cho công cuộc audit & refactor SofaFlow.
> Nhánh làm việc: `refactor/full-audit`. Cập nhật mỗi khi có thay đổi đáng kể.

**Bắt đầu:** 2026-07-25
**Người thực hiện:** Coding agent (Principal Engineer + Product Owner persona)
**Trạng thái tổng thể:** 🟡 Đang chạy — Giai đoạn 5 — ✅ Nhóm 1 & Nhóm 2 (schema) XONG

**Điểm resume (đọc khi khởi động lại):** GĐ2/3/4 **đã xong**. Có `03-expert-review.md` (panel UX/Code/DBA/Security/Perf) + `04-backlog.md` (W1–W21 ưu tiên) + `NEEDS-REVIEW.md` (NR1 B6, NR2 cascade — KHÔNG tự đổi). Việc TIẾP THEO = **GĐ5 loop refactor**, theo thứ tự trong `04-backlog.md`:
`W2 (IDOR create_order) → W7 (validate qty≥0) → W19 (xóa route trùng) → W3 (SECRET_KEY fail-fast) → W4 (session rotate) → W1 (CSRF)` rồi schema `W5 Alembic → W6 unique per-tenant → W8 index` ...
**ĐÃ XONG (Nhóm 1):** W2 (IDOR create_order), W7 (qty/price ≥ 0), W19 (route trùng), W3 (SECRET_KEY fail-fast), W4 (session rotation), **W1 (CSRF toàn site — 69 form/39 template + Flask-WTF + exempt check_code)**. Suite: **20 passed, 2 xfailed** (còn B3→W6, B6→NR1). Xem `CHANGELOG.md`.

**ĐÃ XONG (Nhóm 2 — schema):** W5 (Alembic + baseline `2ede8fb2868b`), W6 (quotation), W6b (contract/handover/payment) — migrations `acb618e15b19`, `e1b399a3d96d`; **B3 fix hoàn toàn cả 4 loại chứng từ**. W8 (index tổ hợp orders/customers, `68c0ef8699e4`). Suite **22 passed, 1 xfailed** (chỉ còn B6/NR1). Tất cả migration reversible + round-trip SQLite OK.

**TIẾP THEO — Nhóm 3 (dọn backend, giữ hành vi):**
1. **W9 — trích helper `parse_line_items(form) -> (items, subtotal)` dùng `Decimal`:** hiện 5+ chỗ trong `dashboard_routes.py` lặp block `getlist('item_name[]')...` + tính subtotal bằng `float`. Trích 1 helper (đặt gần đầu `dashboard_routes.py` hoặc `app/utils/`), thay validate `qty/price >= 0` (đã có ở create_quotation — gom vào helper cho cả contract/handover/payment ⇒ mở rộng W7). Test tiền hiện có (`test_quotation_money.py`) là lưới an toàn; thêm test cho 1 chỗ khác nếu tiện. **Giữ nguyên kết quả số học** (Decimal→so khớp Numeric). VERIFY suite.
2. **W11 — thu hẹp `except Exception` (47 chỗ) + đưa import cục bộ (60) lên đầu module:** làm TỪNG BƯỚC nhỏ, mỗi commit vài chỗ, chạy suite mỗi lần. Cẩn thận KHÔNG đổi thông điệp flash/redirect (hành vi). Nếu một chỗ khó tách an toàn → để lại, ghi chú.
Sau Nhóm 3 → Nhóm 4 UX (W14 i18n, W15 min=0/confirm, W16 vendor CDN), Nhóm 5 perf (W17 joinedload, W18 pagination), rồi W10 (tách god-controller, rủi ro cao — cân nhắc), W21 (README + FINAL-REPORT = GĐ6). NR1/NR2/NR3 KHÔNG tự làm.

---

## Bảng trạng thái các giai đoạn

| GĐ | Tên | Trạng thái | Artifact | Ghi chú |
|----|-----|-----------|----------|---------|
| 0 | Thiết lập an toàn & Baseline | ✅ Xong | `00-baseline.md` | Branch tạo, app import OK, SQLite build 18 bảng OK |
| 1 | Đọc hiểu sâu (Kiến trúc sư) | 🟡 Bản nháp v1 | `01-architecture.md` | ERD + layer map + user journeys xong; cần xác nhận vài business rule |
| 2 | Testing E2E (QA Lead) | ✅ Xong (v1) | `02-bug-catalog.md` | 17 test. 7 bug (B1–B7). Xác nhận đúng: RBAC, payment-seq, approve-state, tenant-GET. Residual input-fuzz để GĐ3/5 |
| 3 | Hội đồng chuyên gia | ✅ Xong | `03-expert-review.md` | 5 panel; finding U/A/DB/S/PF + tổng hợp mức |
| 4 | Ưu tiên hóa | ✅ Xong | `04-backlog.md` | W1–W21 theo I/E; NR1/NR2 → NEEDS-REVIEW |
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
