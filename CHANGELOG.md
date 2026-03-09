# Changelog

All notable changes to SofaFlow will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [1.0.0] - 2026-03-09

### Added
- Quản lý đơn hàng (Order management) với vòng đời đầy đủ
- Báo giá (Quotation): tạo, duyệt, hủy, xuất tài liệu
- Hợp đồng (Contract): tạo, ký, hủy, xuất PDF/DOCX
- Biên bản bàn giao (Handover Record): tạo, xác nhận, hủy
- Thanh toán (Payment Report): tạm ứng, thanh toán cuối, bỏ qua tạm ứng
- Quản lý khách hàng, cửa hàng, người dùng theo công ty
- Phân quyền 3 cấp: `company_admin`, `store_admin`, `user`
- Xuất tài liệu DOCX/PDF từ template
- Quản lý mẫu tài liệu (Document Templates)
- Bảng điều khiển (Dashboard) tổng quan

### Fixed
- `abort(403)` NameError khi `abort` chưa được import ở top-level
- `UnboundLocalError` trong `approve_quotation` / `cancel_quotation` khi exception xảy ra trước khi gán biến `quotation`
- `cancel_payment`: lifecycle `advance_paid` không được reset khi hủy toàn bộ tạm ứng đã xác nhận
- Path traversal trong route phục vụ ảnh sản phẩm
- Giá trị debug mặc định `True` trong `wsgi.py` gây bật Werkzeug debugger trên production
- Role không đúng (`'admin'` → `'company_admin'`) khi đăng ký công ty mới

---

<!-- Links — cập nhật khi release -->
[Unreleased]: https://github.com/tranquanguit/sofa-flow/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/tranquanguit/sofa-flow/releases/tag/v1.0.0
