# QAS — Nhật ký kiểm thử tự động

Mỗi giờ, phiên Claude Code trên máy dev sẽ: lấy code mới nhất từ `main` → deploy lên
https://qas-sofaflow.quangtv.com → chạy thử luồng chính bằng trình duyệt → ghi kết quả vào file này.
Chỉ deploy khi `main` có commit mới; nếu không có thì chỉ kiểm tra app còn sống.

Mục mới nhất nằm trên cùng. Trạng thái: PASS (chạy đúng) · FAIL (lỗi) · BLOCKED (không test tiếp được) · SKIP (bỏ qua).

<!-- LOG-START -->

## 2026-09-18 02:20 — commit 8330ce4 — 10 PASS, 3 FAIL, 2 SKIP

Lượt chạy đầu tiên. Deploy `1.8.0-qas-8330ce4` OK, app trả 200.

- PASS — B1 đăng nhập app (qa_admin), B2 đăng nhập admin (qa_master), B3 tài khoản khoá bị từ chối,
  B4 tạo khách hàng CUST-030, B5 tạo đơn ORD-032, B6 tạo báo giá QT-032 (tổng 10.800.000 đ tính đúng
  ở phía server), B7 sinh PDF báo giá (101 KB, font Times New Roman đầy đủ), B8 duyệt báo giá +
  tạo hợp đồng CT-013, B12 báo cáo (qa_report vào được), B13 phân quyền (qa_report và qa_noperm bị
  chặn 403 ở /orders, /customers), B14 cô lập dữ liệu (qa_other_user của QATEST không mở được
  ORD-032/QT-032/tài liệu của NGOCHAN — bị đẩy đi, không lộ dữ liệu), B15 dọn dữ liệu AUTOTEST.

- **FAIL — B6/B7 Số tiền bằng chữ trên báo giá lưu sai "Không đồng"** (nghiêm trọng, ảnh hưởng chứng từ gửi khách)
  - Màn hình: `/quotations/<order_id>/create`, tài khoản qa_admin.
  - Cách lặp lại: mở form tạo báo giá → chỉ điền tên hàng, ĐVT, SL, đơn giá ở **dòng đầu tiên** (dòng có sẵn) → bấm Tạo Báo Giá.
  - Thực tế: cột "Thành tiền", "Cộng tiền hàng", "Tổng cộng" trên form đứng yên ở 0; ô "Số tiền bằng chữ" giữ nguyên
    "Không đồng" và **được lưu vào DB**. PDF in ra ghi `TỔNG CỘNG: 10,800,000` nhưng `(Bằng chữ: Không đồng)`.
  - Nguyên nhân: `app/templates/quotations/create.html` chỉ gắn sự kiện `input` cho `.qty-input`/`.price-input`
    bên trong `addRow()` (dòng ~337-338). Dòng đầu tiên render sẵn từ server không được gắn, nên `recalcAll()`
    không chạy. Chỉ cần đổi VAT, phí vận chuyển hoặc bấm "Thêm Dòng" là tổng nhảy đúng ngay.
  - Ghi chú: tổng tiền lưu trong DB vẫn ĐÚNG (server tự tính lại trong `parse_line_items`), chỉ số tiền bằng chữ sai.
  - Cần kiểm tra thêm: các form hợp đồng / bàn giao / thanh toán có cùng lỗi gắn sự kiện này không.

- **FAIL — B8 Hợp đồng không kế thừa ĐVT từ báo giá** (nhẹ)
  - `/contracts/<order_id>/create`: dòng hàng lấy sang đủ tên, SL, đơn giá nhưng ô ĐVT để trống,
    dù danh sách có sẵn giá trị "Cái" của báo giá. Người dùng phải chọn lại, quên thì hợp đồng in ra mất ĐVT.

- **FAIL — B4 URL sai gây lỗi 500 thay vì 404** (nhẹ)
  - Mở `/customers/new` (đường dẫn không tồn tại, bị route `/customers/<id>` bắt) → trang lỗi 500,
    log ghi `ValueError: badly formed hexadecimal UUID string`. Nên trả 404. Khả năng các route `<uuid>` khác cũng vậy.

- SKIP — B9 bàn giao + thanh toán, B10/B11 kho và mua hàng: chưa chạy ở lượt này do hết thời gian; sẽ chạy ở lượt sau.

- Ghi chú khác: một số nút còn tiếng Anh khi đang ở giao diện tiếng Việt: "Create Customer",
  "Create Quotation", "Create Contract", "Get new code".

