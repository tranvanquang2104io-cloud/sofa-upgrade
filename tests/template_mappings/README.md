# Bản đồ dữ liệu chứng từ (template data mapping)

Mỗi file JSON ở đây là **toàn bộ biến (context) mà hệ thống bơm vào file mẫu `.docx`** khi
sinh chứng từ, kèm **giá trị mẫu** để dễ hình dung. Dùng để thiết kế/sửa file mẫu cho khớp
dữ liệu. Nguồn sinh ra 100% từ code thật (`DocumentVariableCollector` trong
`app/utils/template_engine.py`) qua script `scripts/dump_template_mappings.py` — chạy lại
script này bất cứ lúc nào để cập nhật.

## File ↔ chứng từ ↔ file mẫu đang chạy trên server

| JSON | Loại chứng từ | `document_type` | File mẫu ĐANG CHẠY (active) |
|------|---------------|-----------------|------------------------------|
| `quotation.json` | Báo giá | `quotation` | `quotation_2d1aefda.docx` |
| `contract.json` | Hợp đồng | `contract` | `contract_ac649e49.docx` |
| `delivery.json` | Biên bản bàn giao & nghiệm thu | `delivery` | `delivery_45babaf8.docx` |
| `payment_advance.json` | Đề nghị tạm ứng | `payment_advance` | `payment_advance_template.docx` |
| `payment_final.json` | Đề nghị thanh toán (cuối) | `payment_final` | `payment_final_template.docx` |

> Mẫu thanh toán "chung" `payment_f0a26b1f.docx` (`document_type = payment`) chỉ dùng khi
> KHÔNG tìm thấy mẫu `payment_advance`/`payment_final`. Nó dùng **cùng bộ biến** với
> `payment_advance.json` / `payment_final.json` (khác nhau ở `payment_type`).

Các file mẫu đã được copy về: `app/uploads/templates/SOFA-NGOCHAN/`.

## Cú pháp token trong file `.docx` (docxtpl / Jinja2)

- Biến đơn: `{{ ten_bien }}` — ví dụ `{{ customer_name }}`, `{{ total_amount }}`.
- Vòng lặp bảng hạng mục: đặt trong 1 hàng của bảng
  `{%tr for item in items %}` … `{{ item.name }}` … `{%tr endfor %}`.
  Các cột của `item`: `stt, name, unit, quantity, unit_price, total, notes`
  (riêng bàn giao có thêm `delivered_qty, accepted_qty, accepted, rejection_reason`).
- Danh sách tài khoản NH: `{% for b in company_bank_accounts %}{{ b.bank_name }} …{% endfor %}`.

## Extend fields (extend01 … extend10)

- Hệ thống có **10** ô mở rộng cho MỖI loại chứng từ (không phải 20): `extend01`..`extend10`
  — lưu dạng text. In ra bằng `{{ extend01 }}` … `{{ extend10 }}`.
- **Quan trọng:** trước bản vá này các token `extendNN` KHÔNG được bơm vào file mẫu (sẽ ra
  rỗng). Đã sửa để `extend01`..`extend10` của chính chứng từ được đưa vào context — cần
  **deploy bản mới** thì token mới hoạt động trên server.
- Nhãn (label) hiển thị trên form nhập của từng ô được cấu hình tại
  **Quản trị → Extension Fields**; bật/đặt tên rồi mới nhập được dữ liệu cho ô đó.

## Ghi chú

- Tiền tệ đã được format sẵn có dấu phẩy ngăn cách nghìn (ví dụ `"23,180,000"`), KHÔNG kèm
  "₫". Ngày ở dạng `dd/mm/yyyy`; có thêm token tách phần ngày/tháng/năm
  (`*_day`, `*_month`, `*_year`) để đặt vào ô "ngày … tháng … năm …".
- `city` luôn lấy theo tỉnh/thành của **cửa hàng** tạo chứng từ (fallback field trên chứng từ).
- Giá trị trong JSON chỉ là **mẫu**; khi chạy thật sẽ thay bằng dữ liệu đơn hàng tương ứng.
