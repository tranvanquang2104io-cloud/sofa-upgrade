# QAS — Luồng kiểm thử tự động mỗi giờ

Tài khoản: mật khẩu chung `Qas@2026!` (xem `scripts/create_qas_test_accounts.py`).
Dữ liệu tạo ra khi test đều đặt tiền tố `AUTOTEST` để dễ nhận ra và dọn.

| # | Luồng | Tài khoản | Kỳ vọng |
|---|---|---|---|
| 1 | Đăng nhập app | qa_admin@sofaflow.test | Vào được trang chủ |
| 2 | Đăng nhập admin | qa_master | Vào được /admin/companies |
| 3 | Tài khoản bị khoá | qa_disabled@sofaflow.test | Bị từ chối |
| 4 | Tạo khách hàng | qa_admin | Lưu được, hiện trong danh sách |
| 5 | Tạo đơn hàng cho khách vừa tạo | qa_admin | Lưu được, tổng tiền khớp với dòng hàng |
| 6 | Tạo báo giá từ đơn hàng | qa_admin | Số báo giá sinh ra, tổng tiền khớp |
| 7 | Sinh file chứng từ báo giá (DOCX + PDF) | qa_admin | Tải được file, không lỗi |
| 8 | Tạo hợp đồng từ báo giá | qa_admin | Trạng thái vòng đời chuyển đúng |
| 9 | Biên bản bàn giao + phiếu thanh toán | qa_admin | Sinh được chứng từ |
| 10 | Kho / vật tư: xem danh sách, nhập kho | qa_kho | Tồn kho thay đổi đúng |
| 11 | Mua hàng: đề nghị mua → PO → nhận hàng | qa_kho | Tồn kho tăng sau khi nhận |
| 12 | Báo cáo | qa_report | Xem được báo cáo |
| 13 | Phân quyền: qa_report mở màn hình đơn hàng | qa_report | Bị chặn |
| 14 | Cô lập dữ liệu: mở đơn hàng của NGOCHAN bằng link trực tiếp | qa_other_user (QATEST) | Bị chặn, không thấy dữ liệu |
| 15 | Dọn dẹp | qa_admin | Xoá/huỷ dữ liệu AUTOTEST vừa tạo |

Ghi chú: bước 14 là kiểm tra bảo mật quan trọng nhất (lộ dữ liệu giữa các công ty).
