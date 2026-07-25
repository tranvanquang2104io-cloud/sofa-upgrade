# GIAI ĐOẠN 4 — Backlog ưu tiên

**Ngày:** 2026-07-25. Gộp bug catalog (GĐ2: B1–B7) + expert review (GĐ3: A/DB/S/PF/U) + baseline (P1–P8).
Thứ tự thực thi theo spec: **(1) bug Critical/High & bảo mật → (2) toàn vẹn dữ liệu/schema → (3) dọn backend → (4) UX → (5) performance → (6) đánh bóng & tài liệu.**
Cột: **I** = Impact, **E** = Effort (L/M/H). "Test" = đã có test đỏ/xfail làm lưới an toàn.

---

## Nhóm 1 — Bảo mật & bug High (làm trước)
| W | Việc | Finding | I | E | Test | Ghi chú |
|---|------|---------|---|---|------|---------|
| W2 | Chặn IDOR ghi xuyên tenant ở `create_order` (+helper lookup có scope) | B5/B7/S2/A6 | H | L-M | ✅ | Bỏ xfail sau khi fix |
| W3 | `SECRET_KEY` fail-fast khi prod thiếu env | S3/P6 | M | L | — | Chỉ prod; dev giữ default |
| W4 | Rotate session khi login (chống fixation) | S4 | M | L | thêm test | `session.clear()` trước khi set |
| W7 | Validate số lượng/đơn giá ≥ 0 (tập trung) | B2/U2 | M | L | ✅ | Bỏ xfail sau khi fix |
| W1 | Thêm CSRF (Flask-WTF CSRFProtect) + token mọi form/fetch POST | S1/U2 | H | M | thêm test | Thêm dependency; `TestingConfig` đã tắt CSRF |
| W19 | Xóa route trùng `/api/quotations/<id>` | B1 | L | L | — | 1 dòng |

## Nhóm 2 — Toàn vẹn dữ liệu & schema (cần Alembic trước)
| W | Việc | Finding | I | E | Test | Ghi chú |
|---|------|---------|---|---|------|---------|
| W5 | Dựng **Alembic** + baseline migration từ models hiện tại | DB4 | M | M | — | Hạ tầng an toàn; **backup trước**; Postgres-compat |
| W6 | Số hiệu chứng từ unique theo `(company_id, number)` + bỏ filter toàn cục (4 chỗ) | B3/DB1 | H | M | ✅ | Depends W5; migration rollback được (D1) |
| W8 | Thêm index tổ hợp `(company_id, created_at)`, `(company_id, is_active)` | DB2 | M | L | — | Depends W5 |
| W7b | Khi ghi chứng từ: verify tổng khớp `items` (chống lệch JSON) | DB3/P5 | M | L | thêm test | Không đổi schema |

## Nhóm 3 — Dọn backend
| W | Việc | Finding | I | E | Test | Ghi chú |
|---|------|---------|---|---|------|---------|
| W9 | Trích `parse_line_items(form)->(items, subtotal)` dùng `Decimal`; chuyển tính tiền vào service | A2/A3/B4 | M | M | dùng test tiền sẵn có | Giữ kết quả số học |
| W11 | Thu hẹp `except Exception` (47) + đưa import cục bộ (60) lên đầu module | A4/A5 | M | M | regression | Cẩn thận không đổi hành vi flash |
| W10 | Tách god-controller `dashboard_routes.py` thành blueprint theo domain | A1 | H | H | regression đầy đủ | **Rủi ro cao** — làm sau, giữ đường lui; nếu VERIFY fail → revert |
| W12 | Gom lookup có scope tenant, xóa kiểm thủ công rải rác | A6/B7 | M | M | regression | Gộp với W2 |

## Nhóm 4 — UX/UI
| W | Việc | Finding | I | E | Ghi chú |
|---|------|---------|---|---|---------|
| W14 | i18n pass: bọc `t()` cho heading/title/placeholder hardcode | U1 | M | M | thêm khóa EN+VI |
| W15 | `min="0"` cho input number + confirm dialog cho hành động phá hủy | U2/U5 | M | L | mirror W7 phía client |
| W16 | Vendor asset CDN vào `static/` hoặc thêm SRI | U3/S6 | L | L | |

## Nhóm 5 — Performance
| W | Việc | Finding | I | E | Ghi chú |
|---|------|---------|---|---|---------|
| W17 | `joinedload`/`selectinload` cho list views | PF1 | M | L | |
| W18 | Phân trang thực bằng `db.paginate()` + next/prev | PF2 | M | L-M | |

## Nhóm 6 — Đánh bóng & tài liệu
| W | Việc | Finding | I | E | Ghi chú |
|---|------|---------|---|---|---------|
| W20 | (Cân nhắc) datetime timezone-aware | DB6 | L | M | phạm vi rộng — có thể để "Đề xuất tương lai" |
| W21 | Cập nhật README + viết `FINAL-REPORT.md` | — | M | M | GĐ6 |

---

## Chuyển sang NEEDS-REVIEW (quyết định nghiệp vụ — KHÔNG tự đổi)
- **B6** — "Contract có bắt buộc quotation đã duyệt không?": enforce hard-block có thể phá luồng đang dùng → hỏi chủ dự án.
- **DB5** — chính sách cascade delete vs soft-delete Company/Order: quyết định nghiệp vụ/pháp lý (lưu trữ chứng từ).

## Thứ tự chạy GĐ5 (đề xuất)
`W2 → W7 → W19 → W3 → W4 → W1` (bảo mật & bug) → `W5 → W6 → W8 → W7b` (schema) → `W9 → W11 → W12` (backend) → `W14 → W15 → W16` (UX) → `W17 → W18` (perf) → `W10` (nếu đủ an toàn) → `W21` (tài liệu). Mỗi W = 1 vòng `PLAN→TEST→FIX→VERIFY→COMMIT→LOG`.
