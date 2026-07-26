# AUDIT — NEEDS REVIEW

## Quyết định nghiệp vụ — ĐÃ GIẢI QUYẾT (chủ dự án ủy quyền 2026-07-26)

| # | Vấn đề | Quyết định | Ghi ở |
|---|--------|-----------|-------|
| NR1 | B6 — Contract bắt buộc Quotation duyệt? | ✅ **KHÔNG bắt buộc (by design)** — theo chuẩn quote-to-cash/CPQ. | DECISIONS D6 |
| NR2 | Cascade delete vs soft-delete | ✅ **Soft-delete là chuẩn**; xác minh không có đường hard-delete Company/Order → giữ nguyên. | DECISIONS D7 |
| NR3 | Unique per-company ở tầng DB | ✅ **LÀM** — thêm `company_id` + đổi unique `(company_id, number)`. | DECISIONS D8, CHANGELOG |

**Tất cả NEEDS-REVIEW đã được xử lý — không còn blocker nghiệp vụ.**

*(Nếu về sau gặp migration nguy cơ mất dữ liệu hoặc cần secret prod, sẽ thêm mục mới vào đây.)*
