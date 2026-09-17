# QAS — Nhật ký kiểm thử tự động

Mỗi giờ, phiên Claude Code trên máy dev sẽ: lấy code mới nhất từ `main` → deploy lên
https://qas-sofaflow.quangtv.com → chạy thử luồng chính bằng trình duyệt → ghi kết quả vào file này.
Chỉ deploy khi `main` có commit mới; nếu không có thì chỉ kiểm tra app còn sống.

Mục mới nhất nằm trên cùng. Trạng thái: PASS (chạy đúng) · FAIL (lỗi) · BLOCKED (không test tiếp được) · SKIP (bỏ qua).

<!-- LOG-START -->
