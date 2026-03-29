# Kế hoạch triển khai (yêu cầu 1-3)

**Bối cảnh nhanh**
- Flask + SQLAlchemy, templates Jinja ở Q:\Projects\sofa-flow\app\templates, services tại pp/services/services.py, sinh docx/pdf qua DocumentService + DocxTemplateEngine, mẫu lưu trong pp/uploads/templates và output trong uploads/documents.
- Chứng từ hiện có: báo giá (quotation), hợp đồng (contract), bàn giao (handover/delivery), thanh toán (payment_advance, payment_final). Totals: subtotal → VAT → grand total.
- i18n: helper 	() + dict ở pp/utils/i18n.py, session lang mặc định en, nhiều UI vẫn hardcode EN.

## Phạm vi & giả định (đã chốt)
- Tất cả chứng từ trên đều cần shipping_fee và nother_fee.
- VAT **không** áp trên 2 khoản phí này; hiển thị sau dòng VAT, nhưng cộng vào tổng cuối.
- Dòng tiền:
  - Báo giá: nhập tay 2 phí.
  - Hợp đồng: auto-fill 2 phí từ báo giá tham chiếu, cho phép chỉnh.
  - Bàn giao & thanh toán (advance/final): lấy 2 phí từ hợp đồng, **không cho chỉnh**.
- “Đề nghị thanh toán”: hiển thị khi final payment chưa confirm; ẩn sau khi confirm. Nếu đã tạo báo cáo final nhưng chưa confirm, nút vẫn hiện.
- Số tiền hiển thị trên “Đề nghị thanh toán”: tổng phải thu (hợp đồng), các đợt tạm ứng đã thu (1..n), còn lại phải thu (contract value − confirmed advance payments).

## Kế hoạch theo yêu cầu
### 1) Thêm Chi phí vận chuyển & Chi phí khác
- **Schema/migration**: thêm cột shipping_fee, nother_fee (Numeric(15,2), default 0) cho quotations, contracts, handover_records, payment_reports; cập nhật models. Tạo script migration mới trong scripts/.
- **Service layer**: mở rộng create/update của Quotation/Contract/Handover/Payment để nhận & lưu 2 phí; với handover/payment lấy từ hợp đồng và không ghi đè nếu gửi khác. Điều chỉnh tính tổng: grand_total = subtotal + vat_amount + shipping_fee + another_fee (VAT giữ nguyên từ subtotal).
- **UI**: thêm 2 input/field sau khu vực VAT ở các màn hình create/edit/view tương ứng; với handover/payment disable/readonly lấy từ hợp đồng; tự bind vào hidden fields để submit.
- **Tính toán JS**: cập nhật hàm ecalcAll (quotation/payment/handover/contract) cộng thêm 2 phí vào tổng hiển thị và hidden grand_total.
- **Document generation**: mở rộng DocumentVariableCollector để xuất shipping_fee, nother_fee, grand_total cho tất cả loại doc; chỉnh Docx placeholders demo và ghi chú biến mới.
- **Dữ liệu cũ**: default 0 bảo toàn hiển thị; kiểm tra view với bản ghi chưa có cột.
- **Test**: flow đầy đủ từ báo giá → hợp đồng → bàn giao → thanh toán advance/final, verify số tổng và docx/pdf.

### 2) Quick Action “Đề nghị thanh toán”
- **Hiển thị**: trong Quick Actions của order view, khi lifecycle.advance_paid true và lifecycle.fully_paid false (tức final payment chưa confirm).
- **Endpoint**: GET tạo document type payment_request, không đổi lifecycle/payment. Dùng context: hợp đồng active, danh sách payments đã confirm (đặc biệt advance), tính remaining = contract value − sum(confirmed advance). 
- **DocumentService**: thêm hỗ trợ payment_request (template lookup, context collector tái dùng payment collector + flag is_request, bổ sung breakdown các đợt tạm ứng).
- **Template**: thêm type “Payment Request” vào settings/templates.html + upload flow; tạo mẫu pp/uploads/templates/payment_request_template.docx (demo) với placeholders: total_contract, advances list, remaining_due, customer info, bank info.
- **UI/UX**: nút mở modal chọn docx/pdf rồi tải; ghi log flash và lưu Document record.
- **Test**: cases có nhiều advance, không advance, remaining=0 (nút ẩn vì fully_paid), final payment created-not-confirmed (nút còn hiện).

### 3) Song ngữ, mặc định Tiếng Việt
- **Mặc định ngôn ngữ**: set session['lang'] mặc định i (context processor) và html lang theo current_lang; login/register cũng dùng i.
- **Rà soát i18n**: quét template/JS/flash còn hardcode, bọc 	(), bổ sung key vào pp/utils/i18n.py; ưu tiên Dashboard, Orders view/Quick Actions, create/edit forms, modals.
- **Test**: chuyển EN/VI trên các màn hình chính; đảm bảo doc generation không phụ thuộc lang.

## Rủi ro & kiểm soát
- Migration prod: cần backup + chạy trước trên staging.
- Thay đổi công thức tổng dễ lệch số: viết unit test nhỏ cho tính tổng, đối chiếu docx/pdf.
- Template mới cần QA thủ công trước khi gửi khách.

## Trạng thái câu hỏi
- Đã được trả lời đầy đủ; không còn khúc mắc. Sẽ triển khai theo kế hoạch trên.

---

### 4) Định dạng số tiền trên ô nhập tay & Preview ảnh đính kèm

#### Bối cảnh kỹ thuật (đã phân tích code)

**Vấn đề 1 – Số tiền không được định dạng:**
- Các ô `shipping_fee` và `another_fee` đều dùng `type="number"` → trình duyệt hiển thị số thô (vd: `100000` thay vì `100.000`).
- Hàm `recalcAll()` trong tất cả `create.html` đọc giá trị bằng `parseFloat()` rồi ghi thẳng số nguyên trở lại (`element.value = shippingFee`) — không qua `fmtNum()`.
- Trong khi đó `subtotal_display`, `vat_amount_display`, `total_display` đã được format đúng qua `fmtNum()` vì dùng `type="text"` readonly.
- Ô `Unit Price` (`.price-input`) cũng dùng `type="number"` → cũng hiển thị số thô khi có giá trị lớn.

**Vấn đề 2 – Thiếu preview ảnh:**
- Màn hình **create**: ô Image chỉ có `<input type="file">`, không có JS nào gắn `onchange` để show preview tức thì.
- Màn hình **view** (quotations, handover, contracts, payments): item table không có cột Image / không render `image_path` từ dữ liệu đã lưu.
- Màn hình **edit** (quotations/edit.html): **đã có** pattern đúng — render `<img src="...">` cho ảnh đã lưu, sau đó mới show `<input type="file">`.
- Các `edit.html` khác (contracts, handover, payments): cũng chưa có preview.

#### Phạm vi thay đổi

| Template | Formatting phí | Preview ảnh (create/live) | Hiển thị ảnh (view) |
|---|---|---|---|
| `quotations/create.html` | ✅ Cần sửa shipping+another+unit price | ✅ Cần thêm JS preview | — |
| `quotations/edit.html` | ✅ Cần sửa shipping+another | ✅ Đã có preview cho ảnh saved; cần thêm live preview khi chọn file mới | — |
| `quotations/view.html` | Đã format bằng `{:,.0f}` ✓ | — | ✅ Cần thêm cột Image + render ảnh item |
| `contracts/create.html` | ✅ Cần sửa shipping+another+unit price | Không có cột Image | — |
| `contracts/edit.html` | ✅ Cần sửa shipping+another | Không có cột Image | — |
| `contracts/view.html` | Đã format ✓ | — | Không có cột Image (bỏ qua) |
| `handover/create.html` | ✅ Cần sửa shipping+another+unit price | ✅ Cần thêm JS preview | — |
| `handover/edit.html` | ✅ Cần sửa shipping+another | ✅ Cần thêm live preview | — |
| `handover/view.html` | Đã format ✓ | — | ✅ Cần thêm cột Image + render ảnh item |
| `payment/create.html` | ✅ Cần sửa shipping+another+unit price | Không có cột Image | — |
| `payments/edit.html` | ✅ Cần sửa shipping+another | Không có cột Image | — |
| `payments/view.html` | Đã format ✓ | — | Không có cột Image (bỏ qua) |

> **Ghi chú:** Contracts và Payments không có cột Image trong bảng hàng hoá (chỉ báo giá và bàn giao mới có), nên không cần xử lý preview/hiển thị ảnh cho 2 loại này.

#### Chi tiết thay đổi kỹ thuật

**A. Định dạng số tiền cho fee inputs (tất cả `create.html` và `edit.html` bị ảnh hưởng):**

1. **Thay `type="number"` bằng `type="text" inputmode="numeric"`** cho `shipping_fee` và `another_fee`:
   - Dùng `type="text"` để có thể kiểm soát format hiển thị.
   - Thêm `inputmode="numeric"` để mobile vẫn bật bàn phím số.
   - Thêm `data-raw` attribute (hoặc hidden input riêng) để lưu giá trị số thuần trước khi submit.

2. **Cập nhật `recalcAll()` trong từng template:**
   - Khi đọc giá trị: strip dấu `.` và `,` trước khi `parseFloat()`, ví dụ:
     ```js
     const raw = el.value.replace(/\./g, '').replace(/,/g, '');
     const shippingFee = parseFloat(raw) || 0;
     ```
   - Khi ghi lại vào display: dùng `fmtNum(shippingFee)` thay vì `shippingFee`.
   - Đảm bảo hidden field (nếu có) nhận giá trị số thuần, không format.

3. **Thêm event listener `input` cho fee inputs** để format ngay khi user nhập:
   ```js
   feeInput.addEventListener('input', function() {
       const raw = parseInt(this.value.replace(/\D/g, '')) || 0;
       this.value = fmtNum(raw); // show formatted
       recalcAll();
   });
   ```
   - Lưu ý: cần `setAttribute('data-raw', raw)` hoặc dùng hidden field để submit đúng.

4. **Với `Unit Price` (`.price-input`):** Giữ nguyên `type="number"` vì đây là ô nhập trong bảng items, submitted qua form array; chỉ cần đảm bảo `row-total` (readonly text) luôn hiển thị qua `fmtNum()` — hiện tại đã đúng.

**B. Preview ảnh trên màn hình create (quotations, handover):**

1. Trong HTML template của hàng đầu tiên (static row) và trong `addRow()` / `addItemRow()` (dynamic rows), cell Image thay từ:
   ```html
   <td><input type="file" class="form-control form-control-sm" name="item_image[]" accept="image/*"></td>
   ```
   thành:
   ```html
   <td>
     <input type="file" class="form-control form-control-sm img-file-input" name="item_image[]" accept="image/*">
     <img class="img-preview img-thumbnail mt-1" style="max-height:50px; display:none;" alt="">
   </td>
   ```

2. Thêm JS helper (một lần, dùng chung):
   ```js
   function attachImagePreview(row) {
       const fileInput = row.querySelector('.img-file-input');
       if (!fileInput) return;
       fileInput.addEventListener('change', function() {
           const preview = this.closest('td').querySelector('.img-preview');
           if (!preview) return;
           if (this.files && this.files[0]) {
               const reader = new FileReader();
               reader.onload = e => { preview.src = e.target.result; preview.style.display = ''; };
               reader.readAsDataURL(this.files[0]);
           } else {
               preview.src = ''; preview.style.display = 'none';
           }
       });
   }
   ```

3. Gọi `attachImagePreview(row)` trong `addRow()` / `addItemRow()` và trên static rows khi `DOMContentLoaded`.

**C. Hiển thị ảnh đã lưu trên màn hình view (`quotations/view.html`, `handover/view.html`):**

1. Thêm cột `Image` vào `<thead>`.
2. Trong vòng lặp item, thêm cell:
   ```jinja
   <td>
     {% if item.get('image_path') %}
     <img src="{{ url_for('dashboard.serve_item_image', filename=item.image_path[6:]) }}"
          class="img-thumbnail" style="max-height:50px;" alt="">
     {% else %}—{% endif %}
   </td>
   ```
3. Điều chỉnh `colspan` của các dòng footer (subtotal, VAT, ...) tăng thêm 1.

**D. Preview ảnh trên màn hình edit (quotations/edit.html, handover/edit.html):**
- `quotations/edit.html` đã có `<img>` cho ảnh saved. Chỉ cần gắn thêm `change` listener để show preview tức thì khi chọn file mới (dùng `attachImagePreview()`).
- `handover/edit.html` cần bổ sung cả 2: hiển thị ảnh saved (pattern từ `quotations/edit.html`) + live preview.

#### Thứ tự triển khai an toàn

1. Sửa `quotations/create.html` (fee formatting + image preview) → test kỹ nhất vì nhiều logic.
2. Sửa `quotations/edit.html` (fee formatting + live preview).
3. Sửa `quotations/view.html` (thêm cột Image).
4. Sửa `contracts/create.html` và `contracts/edit.html` (fee formatting chỉ, không có Image).
5. Sửa `handover/create.html` (fee formatting + image preview).
6. Sửa `handover/edit.html` (fee formatting + saved image + live preview).
7. Sửa `handover/view.html` (thêm cột Image).
8. Sửa `payment/create.html` và `payments/edit.html` (fee formatting chỉ, không có Image).

#### Rủi ro & kiểm soát

- **Form submit sai giá trị phí:** Nếu dùng `type="text"` mà gửi giá trị đã format (`100.000`), server sẽ parse thành 100 (bỏ phần sau dấu `.`). Giải pháp: dùng hidden input song song hoặc strip format bằng JS trước `submit`.
- **Mất ảnh khi edit không chọn lại file:** Đã có `item_existing_image[]` hidden field trong `quotations/edit.html` — cần đảm bảo pattern này được duy trì ở `handover/edit.html`.
- **`colspan` sai trong footer table:** Khi thêm cột Image vào view, cần cập nhật cẩn thận tất cả `colspan` của `<tfoot>`.
- **Không có backend thay đổi:** Toàn bộ sửa đổi là frontend (HTML + inline JS trong template), không đụng service/model/migration — rủi ro thấp.

#### Kiểm thử

**Tự kiểm tra thủ công (Manual):**
1. Vào màn hình **Create Quotation** → nhập `shipping_fee = 100000` → xác nhận hiển thị `100.000` sau khi rời ô.
2. Tại bảng items, chọn ảnh cho 1 dòng → xác nhận ảnh thumbnail xuất hiện ngay dưới input file.
3. Submit form → vào **View Quotation** → xác nhận cột Image hiển thị ảnh đúng.
4. Vào **Edit Quotation** → xác nhận ảnh cũ hiển thị, chọn ảnh mới → xác nhận preview cập nhật.
5. Lặp tương tự cho **Contract Create/Edit** (chỉ kiểm tra fee formatting).
6. Lặp tương tự cho **Handover Create/Edit/View** (cả fee + ảnh).
7. Lặp cho **Payment Create/Edit** (chỉ fee formatting).
8. Kiểm tra giá trị thực sự lưu vào DB: sau khi tạo, reload trang View → các con số phải khớp với những gì nhập.
