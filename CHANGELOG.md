# Changelog

All notable changes to SofaFlow will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [1.1.0] - 2026-03-09

### Added
- **Module Quản lý Nguyên Vật Liệu (Material Management)** — đầy đủ CRUD + tồn kho
  - 4 bảng DB mới: `material_units`, `material_categories`, `materials`, `material_stock`
  - Quản lý đơn vị tính (Units of Measure) — scoped theo công ty, quick-seed 8 đơn vị phổ biến
  - Quản lý danh mục (Categories) — có thứ tự sắp xếp
  - Catalog NVL toàn công ty: mã, tên, màu, đơn giá, nhà cung cấp, thông số kỹ thuật (JSON), ảnh
  - Tồn kho theo địa điểm: kho công ty + từng cửa hàng (store), cập nhật qua modal
  - Cảnh báo tồn kho thấp (low stock) trực quan trên giao diện
  - Soft-delete (vô hiệu hóa) cho NVL, danh mục, đơn vị
  - Phân quyền: `user` xem, `store_admin` CRUD, `company_admin` xóa/quản lý đơn vị
  - 6 giao diện mới: danh sách, tạo, xem chi tiết, chỉnh sửa, danh mục, đơn vị
  - Scripts migration: `scripts/migrate_materials.py`
  - Thêm translations tiếng Việt cho toàn bộ chuỗi giao diện mới

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
[Unreleased]: https://github.com/tranquanguit/sofa-flow/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/tranquanguit/sofa-flow/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/tranquanguit/sofa-flow/releases/tag/v1.0.0
