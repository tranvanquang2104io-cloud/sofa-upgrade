# Audit toàn hệ thống — 27/09/2026

Bốn agent chuyên trách rà độc lập (kiến trúc, bảo mật, UI/UX, QA), mọi khẳng
định có `file:dòng`. Tài liệu này là **kết quả đo**, không phải kế hoạch; kế
hoạch nằm ở phần cuối.

Nguyên tắc dùng khi đọc tài liệu này: **một khẳng định không có `file:dòng` là
một giả thuyết chưa kiểm.** Trong chương trình này đã ba lần có kết luận rút ra
từ việc đọc một tầng rồi suy ra cả hệ thống, hai lần lọt vào sổ. Mọi mục dưới
đây đều đã được kiểm lại trên code.

---

## A. Bốn nợ cấu trúc

### A.1 Sáu chứng từ không có state machine

Chỉ **3/14** loại chứng từ có `TRANSITIONS` thật: `ProductionPlan`
(`models.py:1241`), `PurchaseRequisition` (`:1379`), `PurchaseOrder` (`:1463`).

Không có gì: `Order` (`:318`, **không có cả cột `status`**), `Quotation`
(`:374`), `Contract` (`:429`), `HandoverRecord` (`:496`), `PaymentReport`
(`:562`), `GoodsReceipt` (`:1562`, đúng một cờ `is_posted`), `StockTransfer`
(`:1060`, không cờ nào và không status nào).

Trạng thái của sáu loại này được **suy ra ở tầng hiển thị**:
`status_tokens.py:147 document_state()` chạy chuỗi
`is_canceled → is_approved → is_signed → is_confirmed → status → hasattr`.
Nghĩa là "chứng từ này đang ở đâu" phụ thuộc vào **object có thuộc tính nào**.

Và một nơi thứ ba suy ra "đã vào sổ" theo cách khác nữa: `books.py:116
_is_posted()`.

### A.2 `LifecycleStatus` là state machine thứ hai chạy song song

`models.py:276-312` — 8 cờ boolean nhân bản trạng thái chứng từ:
`quotation_approved` ↔ `Quotation.is_approved`, `contract_signed` ↔
`Contract.is_signed`, `handover_confirmed` ↔ `HandoverRecord.is_confirmed`.

Hai nguồn sự thật, **và chúng đã lệch nhau**:

- `cancel_contract` (`dashboard_routes.py:1629-1663`) sửa model thẳng trong
  route và **không gọi** `ContractService.cancel_contract` (`services.py:731`),
  là hàm CÓ rollback `lifecycle.contract_created`. Đường service ấy chỉ còn
  test gọi — **chết trong production**. Huỷ hợp đồng qua UI để lại
  `contract_created=True` vĩnh viễn.
- `skip_advance_payment` (`:2222`) ghi `lifecycle.advance_paid = True` dù
  **không có đồng nào nhận**; chính chú thích ở `:2262` thừa nhận "It
  overstates reality".

Không thể bỏ `LifecycleStatus` ngay: `WorkflowService.check()`
(`workflow_service.py:227`) đọc **duy nhất** `getattr(lifecycle, prerequisite)`
— toàn bộ engine workflow chỉ biết nói chuyện với các cờ của bảng này.

### A.3 Không có audit trail

Toàn schema có đúng **3 cột `*_by_id`**: `approval_requests.requested_by_id`,
`decided_by_id` (`models.py:984,986`), `stock_movements.created_by_id`
(`:1051`), `workflow_waivers.waived_by_user_id` (`:1696`).

**Không một chứng từ nào** ghi ai tạo, ai duyệt, **ai ký**, ai xác nhận tiền,
ai huỷ. `Quotation` không có cả `approved_at` (`:400-407`).

Với một sản phẩm mà chủ doanh nghiệp vừa yêu cầu maker–checker, đây là nền
móng còn thiếu: duyệt mà không ghi ai duyệt thì không phải kiểm soát.

### A.4 Trạng thái chết và luật không thi hành

| Thứ | Khai báo | Bằng chứng chết |
|---|---|---|
| `MasterAgreement.STATUS_EXPIRED` | `models.py:1825` | không có dòng gán nào; model có `effective_to` nhưng không job nào đọc |
| `SupplierPayment.STATUS_CANCELED` | `:2178` | 0 lần gán — **phiếu chi NCC không bao giờ huỷ được** |
| `Document.STATUS_SIGNED` | `:717` | chỉ được đọc, không nơi nào gán — và đây là chỗ ký số sẽ bám vào |
| `PurchaseOrder.STATUS_PARTIAL/RECEIVED` | `:1458-1459` | không phải target của `TRANSITIONS`; tới được bằng gán tắt `sync_receipt_status()` |
| `PurchaseRequisition.STATUS_CONVERTED` | `:1376` | không phải target của `TRANSITIONS`; `requisition_service.py:116` gán tắt, bỏ qua chính `transition()` |
| Action `quotation.approve`, `handover.confirm` | `workflow_service.py:40,45` | **hiện trên lưới cấu hình cho admin đặt luật** (`dashboard_routes.py:4028`) nhưng không `require()` nào gọi — admin cấu hình được, hệ thống không thi hành |

---

## B. Bảo mật — ba lớp hổng

### B.1 Mười bốn hành động hệ trọng chỉ sau `@login_required`

Ký hợp đồng (`:1597`), duyệt báo giá (`:1274`), xác nhận/huỷ tiền
(`:2278`, `:2434`), huỷ đơn/hợp đồng/báo giá/bàn giao, xác nhận bàn giao
(`:1895`), xoá tài liệu (`:2653`), xác nhận + trả hoá đơn NCC
(`:4479`, `:4497`), **nhận hàng vào kho** (`:5214`), đổi trạng thái đơn mua
(`:5197`).

Một nhân viên được tick ô "Đơn hàng" **ký được hợp đồng**. Không có bậc nào
giữa "xem đơn hàng" và "ký cam kết pháp lý".

Tầng "vùng chức năng" thì chắc: map viết tay, fail-closed, có test đóng kín
(`permission_map.py:189`, `test_permission_map_is_closed.py`). Điểm yếu **không**
ở đó — nó ở tầng **hành động** và tầng **trạng thái**.

### B.2 Quyền không xét trạng thái chứng từ

`current_user_can(feature)` (`auth_utils.py:54`) chỉ đọc session; không nhận
object, nên **không thể hỏi** "user này có được huỷ phiếu thu **đã xác nhận**
không". Trạng thái được xét riêng rẽ bằng `can_*()` trên model, hoàn toàn
không liên quan tới danh tính người gọi.

23 phương thức `can_*` rải trên các model, và chúng dùng **hai quy ước ngược
nhau**: danh sách trắng (`status == DRAFT`) ở phía mua hàng, danh sách đen
(`not X and not is_canceled`) ở phía bán hàng. `Quotation.can_edit()`
(`:419`) **quên hẳn `is_canceled`** — báo giá đã huỷ vẫn sửa được.

### B.3 Rò cách ly cửa hàng — khoảng 15 endpoint

`company_id` thì kín. `store_id` thì không.

Chỉ **hai** loại được kiểm cửa hàng: `Order` (`services.py:391`) và
`ProductionPlan` (`dashboard_routes.py:4726`).

Không kiểm: `sign_contract`, `cancel_contract`, `edit_contract`,
`approve_quotation`, `cancel_quotation`, `confirm_payment`, `cancel_payment`,
`edit_payment`, `confirm_handover`, `cancel_handover`, `edit_handover`,
`download_document`, `delete_document`, `get_contract_api`.

Nghịch lý cụ thể: `view_order` chặn người cửa hàng B, nhưng `sign_contract`
cho qua — chặn được cửa trước, cửa sau mở, vì mọi chứng từ con chỉ so
`.order.company_id`.

Hạ tầng để vá đã có: `ensure_store_access` (`auth_utils.py:223`) — **được gọi
đúng 1 lần** trong 5438 dòng route (`:662`).

### B.4 Hai lỗ hổng trong chính workflow duyệt vừa xây

1. **Người duyệt không bị ràng buộc chi nhánh.** `ApprovalRequest` không có cột
   `store_id` (`models.py:963`); `pending_for(company_id)` (`approvals.py:125`)
   trả về toàn công ty. Quản lý chi nhánh A duyệt đề nghị của chi nhánh B.
2. **Không chặn tự duyệt.** `approve()` (`:88`) không so `user_id` với
   `requested_by_id`. Chưa khai thác được vì người có quyền duyệt thì đã "làm
   luôn" — nhưng là bẫy: thêm một role vừa đề nghị vừa duyệt là gate biến mất
   trong im lặng.

---

## C. Hai lỗi do chính lượt refactor này gây ra

### C.1 Xác nhận được phiếu đã huỷ — ĐÃ VÁ

`PaymentReport.can_confirm()` (`models.py:621`) kiểm hai điều kiện: chưa xác
nhận **và chưa huỷ**. `payments/view.html:243` dùng nó để ẩn nút.
`mark_confirmed` (`services.py:1145`) chỉ kiểm điều kiện thứ nhất.

Điều kiện thứ hai sống **hoàn toàn trong một template**. Ẩn một cái nút là tiện
ích cho người đang nhìn màn hình; nó chưa bao giờ là một luật, và một POST
thẳng tới URL chưa bao giờ chịu ràng buộc đó.

Việc mở huỷ-phiếu-đã-xác-nhận (§3.2) làm chuỗi *xác nhận → huỷ → POST xác nhận
lại* **chạm tới được**. Một luật chỉ được thi hành ở nơi nó tình cờ không tới
được thì chưa bao giờ hoạt động — nó chỉ chưa ai thử.

Thứ tự kiểm phải là **"đã huỷ" trước**: huỷ cố ý không gỡ `is_confirmed` (đó
là dấu vết kiểm toán), nên nhánh trả-về-sớm trên cờ ấy báo **thành công**.

### C.2 Hai ô chọn kho trên màn hình nhận hàng, và chú thích nói sai

`po_view.html:111-123` (`warehouse_id`, nhãn "Nhập vào kho", chú thích *"Tồn
kho sẽ tăng ở kho này"*) và `:139-145` (`store_id`, nhãn "Into Store", chưa
dịch). Cách nhau cả một bảng nhập số lượng.

Sự thật theo `procurement_service.py:171,201,211`: tồn kho tăng theo
**`store_id`**. `warehouse_id` chỉ được **dán nhãn** lên dòng tồn ở `:217`.

Chú thích là của tôi, viết khi thêm ô chọn kho. Thủ kho có thể ghi tăng tồn
sai địa điểm mà tin là đã chọn đúng.

---

## D. UI/UX

### D.1 Màn hình đơn mua — đúng chỗ chủ sản phẩm chỉ ra

| Phần | Dòng | Bọc trong | Tiêu đề |
|---|---|---|---|
| Vật tư đặt mua | `po_view.html:69` | **không có card** | `<h5>` trần |
| Nhận hàng & nhập kho | `:100` | `.card.border-success` | card-header **xanh lá đậm** |

Hai mức nổi bật khác nhau cho hai phần ngang cấp. Màu xanh đó là **duy nhất
trong toàn sản phẩm** — nó không mang nghĩa gì (nhập kho không phải trạng thái
"thành công"), nó đang bù cho việc thiếu phân cấp thật. Macro `card_open()`
(`macros/ui.html:287`) tồn tại đúng để giải quyết việc này và màn hình không
dùng.

Hai bảng liền nhau, **cùng có cột "Outstanding"** (`:74` và `:125`), số dòng
khác nhau vì bảng dưới lọc bỏ dòng đã nhận đủ — người dùng dễ hiểu là đơn có
hai bộ vật tư.

Form GR **luôn mở sẵn** với `{% if po.can_receive() %}` (`:101`) — tức với mọi
đơn đã gửi NCC chưa nhận đủ, tức phần lớn vòng đời một PO — và **đã điền sẵn
toàn bộ số lượng còn lại** (`:132`). Một cú bấm là ghi tăng tồn cả đơn.

### D.2 Mất dữ liệu: "Điền từ đề xuất" xoá trắng form

`pr_form.html:48` là một `<a href>` nằm **bên trong `<form>`** (mở ở `:16`).
Bấm = điều hướng đi, **không cảnh báo**. Tiêu đề, cửa hàng, ngày cần, ghi chú
và mọi dòng vật tư đã nhập tay **mất sạch**. Cơ chế khôi phục form
(`base.html:246`) chỉ chạy sau khi POST thất bại, không cứu được ca này.

Nhãn ghi "Điền từ đề xuất" (gợi ý thêm vào) nhưng hành vi là "bỏ hết và bắt
đầu lại".

### D.3 Trùng lặp hành động

`orders/view.html`: **năm hành động, mười nút** — mỗi hành động xuất hiện cả
trong timeline (`:200,257,343,402,483`) lẫn trong Quick Actions
(`:504,532,570,579,585`), với kích cỡ khác nhau nên trông như hai việc khác
nhau. Trạng thái quy trình cũng vẽ hai lần: timeline viết tay (`:138`) và
`process_list()` (`:627`) — mà macro ấy sinh ra đúng để **thay thế** bản viết
tay.

`orders/view.html:179-182`: hỏi xác nhận **hai lần** khi duyệt báo giá, với
hai câu chữ khác nhau.

### D.4 Nút bị chặn thì biến mất, không giải thích

Mẫu `{% if điều_kiện %}<nút>{% endif %}` khắp nơi. Grep `disabled` trên toàn
bộ template: 7 kết quả, **không cái nào là "chặn nút để giải thích lý do"**.

Với người dùng không giỏi công nghệ, điều này tệ hơn nút xám: họ không biết
nút **từng tồn tại**. Ví dụ thật: PO ở trạng thái `draft` thì `:101` ẩn toàn
bộ phần nhận hàng — người nhận hàng mở đơn, không thấy chỗ nhập, và không gì
nói "phải bấm Gửi NCC trước".

---

## E. Trùng lặp đo được

| Thứ | Số bản | Nơi |
|---|---|---|
| `transition()` | 3 | `procurement_service.py:146`, `requisition_service.py:78`, `services.py:2490` |
| `can()` + `allowed_actions()` | 3 | `models.py:1290`, `:1424`, `:1504` |
| Thuật toán sinh số chứng từ | 3 | `procurement_service.py:15`, `dashboard_routes.py:2818`, `transfers.py:32` |
| Suy ra trạng thái chứng từ | 3 | `status_tokens.py:147`, `books.py:116`, 23 phương thức `can_*` |
| `product_key()` | 2 | `services.py:2087`, `agreement_service.py:55` |
| Kiểm tenant viết tay | 36 | `dashboard_routes.py` |
| Helper `_owned_*` | 5 | cùng một ý tưởng, 5 bản |

**`transfers.py:34` dùng `COUNT(*) + 1` để sinh số phiếu** — đúng cái lỗi mà
docstring của `procurement_service.py:20` viết ra để cảnh báo: *"A count is not
a sequence: delete any row and the next number repeats one already used"*. Và
`StockTransfer` **có** unique constraint đó (`models.py:1101`). Đây là lỗi của
lượt refactor này.

**`books.may_change` (khoá sổ) chỉ phủ 3 trong khoảng 15 hành động ghi sổ.**
Không phủ: ký hợp đồng, xác nhận bàn giao, nhập kho, xuất vật tư, điều chuyển
kho, xác nhận phiếu chi NCC.

---

## F. Điều một suite xanh KHÔNG chứng minh

Ghi lại để không ai đọc "1100 test xanh" thành "hệ thống đúng":

- Không có test nào đi trọn một hành trình nhiều bước có đổi vai (nhân viên
  tạo → gửi duyệt → quản lý duyệt).
- Không có test gọi thẳng API một endpoint mà UI đã ẩn nút — chính là lớp lỗ
  hổng ở §B.
- Không có test truy cập dữ liệu cửa hàng khác — §B.3 nằm ngoài tầm nhìn của
  suite hiện tại.
- Migration được chạy, nhưng chỉ vài cái có dữ liệu thật trong đó.

§C.1 là bằng chứng sống: lỗ hổng ấy tồn tại **trong lúc toàn bộ suite xanh**,
và chỉ lộ ra khi một agent đọc code với câu hỏi "điều kiện này được thi hành ở
đâu".
