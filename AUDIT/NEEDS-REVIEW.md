# AUDIT — NEEDS REVIEW (cần chủ dự án xử lý khi dậy)

> Những mục KHÔNG thể làm an toàn/không đảo ngược được khi chạy tự chủ, hoặc cần credential/secret. Agent bỏ qua và làm tiếp việc khác.

## Quyết định nghiệp vụ (agent KHÔNG tự đổi — chờ chủ dự án)

| # | Vấn đề | Vì sao không tự quyết | Phương án mặc định nếu bạn không trả lời |
|---|--------|----------------------|------------------------------------------|
| NR1 | **B6 — Contract có bắt buộc Quotation đã duyệt?** Hiện tạo contract tự do không cần quotation approved. | Enforce hard-block có thể **phá luồng đang chạy** mà bạn cố ý cho phép (linh hoạt nghiệp vụ). Không rõ từ code. | **Giữ nguyên** hành vi; chỉ thêm cảnh báo mềm (không chặn) ở UI. Không đổi logic. |
| NR2 | **DB5 — Cascade delete vs soft-delete** cho Company/Order. Hiện xóa cứng, cuốn theo mọi chứng từ. | Quyết định nghiệp vụ/pháp lý (lưu trữ hồ sơ tài chính). | **Không đổi schema xóa**; chỉ thêm confirm + cảnh báo hậu quả ở UI; đề xuất soft-delete để bạn duyệt sau. |

*(Chưa có blocker kỹ thuật/secret. Nếu gặp migration nguy cơ mất dữ liệu hoặc cần secret prod, sẽ thêm vào đây.)*
