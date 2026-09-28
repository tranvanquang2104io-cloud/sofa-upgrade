# Task Plan — 27/09/2026

Nguồn: `AUDIT-2026Q4.md` (bốn agent rà độc lập, mọi phát hiện có `file:dòng`).

Quy tắc trạng thái: `DONE` **chỉ** khi Acceptance Criteria đã pass, không phải
khi code chạy. `NEEDS REVIEW` khi code xong nhưng chưa ai kiểm độc lập.

Thứ tự ưu tiên có một chỗ **lệch khỏi P0→P4 vì phụ thuộc thật**, giải thích ở
cuối tài liệu.

---

## P0 — Kiến trúc / Bảo mật / Toàn vẹn dữ liệu

### T-01 · Chặn rò dữ liệu giữa các chi nhánh trên chứng từ con

**Priority:** P0 · **Type:** Security · **Dependencies:** không · **Status:** `DONE`

> **Kết quả.** Chặn ở **repository**, không phải ở service như dự kiến ban đầu.
> Lý do đổi: nhiều route gọi thẳng `ContractRepository().get_by_id()` chứ
> không đi qua service — `sign_contract`, `edit_contract`, `confirm_payment`,
> `delete_document` đều thế. Vá ở service sẽ bỏ sót đúng những cửa đang hở.
> `OrderScopedRepository` (`repository.py:301`) phủ cả 5 loại chứng từ con và
> **không call site nào phải sửa**: chứng từ ngoài phạm vi trả về `None`, đúng
> thứ các route đã xử lý sẵn là "không tìm thấy hoặc không có quyền".
>
> **Hai test xanh vì lý do sai, bắt được lúc viết test.** `confirm_payment` và
> `cancel_payment` xanh ngay trên code CHƯA sửa — không phải vì bị chặn, mà vì
> nhân viên không phải vai duyệt nên `request_or_do` chỉ *ghi đề nghị* chứ
> không thực hiện. Cờ `is_confirmed` đứng yên vì hàng đợi duyệt, không vì phạm
> vi. Test đã siết thêm: phải không có **ApprovalRequest** nào được tạo. Tự nó
> là lỗ rò — một đề nghị chéo chi nhánh rơi vào hàng đợi của quản lý không có
> phận sự với chứng từ đó.

1. **Nội dung.** Khoảng 15 endpoint chỉ kiểm `company_id`, không kiểm `store_id`.
2. **Mục đích.** Người của chi nhánh A không đọc, sửa, ký hay xác nhận tiền của
   chi nhánh B.
3. **Vấn đề hiện tại.** `view_order` chặn (`services.py:391`), nhưng
   `sign_contract` (`dashboard_routes.py:1597`), `confirm_payment` (`:2278`),
   `cancel_payment` (`:2434`), `edit_contract` (`:1512`), `confirm_handover`
   (`:1895`), `delete_document` (`:2653`) và 9 endpoint khác thì không. Chặn
   được cửa trước, cửa sau mở. `ensure_store_access` (`auth_utils.py:223`) tồn
   tại và **được gọi đúng 1 lần** trong 5438 dòng route.
4. **Giải pháp đề xuất.** Kiểm ở **getter của service/repository**, theo đúng
   mẫu `OrderService.get_order` đã làm — **không** vá 15 route. Một chứng từ con
   thừa kế phạm vi cửa hàng từ order của nó.
   *Đánh đổi:* vá từng route rẻ hơn một lần nhưng là 15 chỗ phải nhớ; vá ở
   getter đắt hơn lúc đầu và đúng cho mọi lối vào sau này, kể cả lối chưa viết.
5. **Chức năng ảnh hưởng.** Toàn bộ chứng từ bán hàng + tài liệu in.
6. **Database.** Không đổi.
7. **Backend.** `services.py` (các getter), `auth_utils.py` (dùng lại helper sẵn có).
8. **Frontend.** Không đổi.
9. **API.** Không đổi hình dạng; thêm 403 cho trường hợp vượt phạm vi.
10. **Permission/Security.** Đây chính là nội dung task.
11. **UI/UX.** Trang lỗi phải nói "chứng từ này thuộc chi nhánh khác", không
    phải "Forbidden".
12. **Test.** Một **sweep** theo cửa hàng giống `test_tenant_isolation_sweep.py`,
    phủ đủ 15 endpoint, **có đối chứng dương** (cùng hành động ở đúng chi nhánh
    phải thành công) — vì sweep hiện tại chấp nhận `302` và có thể xanh khi
    login hỏng.
13. **Acceptance.** Staff chi nhánh A nhận 403 trên cả 15 endpoint với id của
    chi nhánh B; đúng 15 endpoint đó trả 200/302-thành-công với id chi nhánh A.
14. **Kỳ vọng.** Không còn đường nào đọc/ghi chéo chi nhánh trong nhóm này.
15. **Trạng thái.** `TODO`

---

### T-02 · Người duyệt bị ràng buộc theo chi nhánh, và không tự duyệt

**Priority:** P0 · **Type:** Security · **Dependencies:** T-01 · **Status:** `DONE`

> **Kết quả.** Thêm `approval_requests.store_id` (migration `f3a4b5c6d7e8`,
> backfill từ `order.store_id` của phiếu thu), đóng dấu chi nhánh lúc *tạo* đề
> nghị, lọc hàng đợi + màn quyết định theo phạm vi cửa hàng, chặn tự duyệt, và
> cho hai performer đi qua repository thay vì `PaymentReport.query.get()`.
>
> **Phần nhọn nhất HOÁ RA T-01 đã đóng sẵn — nói rõ để không nhận công.** Test
> "quản lý chi nhánh A không duyệt được đề nghị của chi nhánh B" **xanh ngay
> trước khi sửa gì**: `_confirm_payment` nạp lại phiếu qua
> `PaymentReportService`, mà service này đi qua repository đã bị chặn ở T-01,
> nên phiếu của chi nhánh kia đọc ra là "không tìm thấy". Tiền vốn đã an toàn.
> Cái còn thiếu là *khác*: đề nghị vẫn **hiện trong hàng đợi sai người**, và
> bấm duyệt thì nhận một câu báo lỗi vô nghĩa thay vì đừng bao giờ thấy nó.
> Và sự an toàn đó đang tựa vào việc một service tình cờ nạp lại qua
> repository — performer viết thêm ngày mai mà thao tác thẳng trên row được
> truyền vào thì không có lớp đó.
>
> **`store_id` NULL có nghĩa.** Dòng cũ không truy được chi nhánh (phiếu đã bị
> xoá) không rơi vào hàng đợi chi nhánh nào, mà về company admin — người đứng
> trên các chi nhánh. Có test riêng cho trường hợp này; backfill đã chạy thử
> trên dữ liệu thật (1 dòng truy được, 1 dòng mồ côi) chứ không chỉ chạy lệnh.
>
> **Tự duyệt: bẫy, không phải lỗ đang hở.** `store_admin` hỏi thì không bao
> giờ sinh ra dòng nào — `request_or_do` làm luôn. Chỉ hở khi ai đó đổi vai
> giữa lúc hỏi và lúc quyết, hoặc khi `DECIDING_ROLES` mở rộng. Test ghi đúng
> như vậy thay vì khoe đã tìm ra lỗ.

1. **Nội dung.** `ApprovalRequest` không có `store_id`; `pending_for()` trả về
   toàn công ty.
2. **Mục đích.** Quản lý chi nhánh duyệt việc của chi nhánh mình — đúng điều
   chủ sản phẩm nói: *"người duyệt phải là admin của chi nhánh/store"*.
3. **Vấn đề hiện tại.** `models.py:963` thiếu cột; `approvals.py:125`
   `pending_for(company_id)`; `dashboard_routes.py:2972` lọc theo company. Nên
   quản lý chi nhánh A duyệt đề nghị chi nhánh B. Và `approve()` (`:88`) không
   so `user_id` với `requested_by_id` — chưa khai thác được nhưng là bẫy.
4. **Giải pháp.** Thêm `approval_requests.store_id` (lấy từ chứng từ lúc tạo);
   lọc hàng đợi theo phạm vi cửa hàng của người duyệt; chặn tự duyệt.
   **Phát hiện thêm khi làm T-01:** `approvals.py:30,40` nạp phiếu thu bằng
   `PaymentReport.query.get()` thẳng từ model, **không qua repository**, nên
   nó nằm ngoài lớp chặn chi nhánh vừa dựng ở `OrderScopedRepository`. Hiện
   chưa khai thác được — T-01 đã chặn ngay ở khâu *tạo* đề nghị nên không có
   đề nghị chéo chi nhánh nào để duyệt — nhưng đây là cánh cửa thứ hai vào
   cùng một chứng từ, và nó phải đi qua repository.
5. **Ảnh hưởng.** Hàng đợi duyệt, màn hình `/approvals`.
6. **Database.** Migration thêm 1 cột, backfill từ `order.store_id` của chứng từ.
7. **Backend.** `approvals.py`, `dashboard_routes.py:2940-3000`.
8. **Frontend.** `approvals/list.html` — không đổi hình dạng.
9. **API.** Không đổi.
10. **Permission.** Nội dung task.
11. **UI/UX.** Hàng đợi ngắn lại và đúng người; không cần đổi bố cục.
12. **Test.** Quản lý chi nhánh A **không thấy** và **không duyệt được** đề nghị
    của B; người đề nghị không tự duyệt được.
13. **Acceptance.** Cả ba khẳng định trên pass qua HTTP.
14. **Kỳ vọng.** Workflow duyệt có ý nghĩa thật thay vì hình thức.
15. **Trạng thái.** `TODO`

---

### T-03 · Sửa số sinh phiếu điều chuyển kho (`COUNT(*) + 1`)

**Priority:** P0 · **Type:** Data integrity · **Dependencies:** không · **Status:** `DONE`

> **Kết quả.** Gộp về một chỗ: `app/services/numbering.py`. `transfers.py` và
> endpoint `next_code` cùng gọi nó. Bản `COUNT(*) + 1` là **do tôi viết trong
> đợt refactor này**, bị xoá chứ không vá tại chỗ, vì bản đúng đã có sẵn.
>
> **Test tự sửa lại lời tôi viết.** Docstring đầu tiên của tôi nói trùng số thì
> "dòng thứ hai cứ thế lưu, không báo lỗi gì". Sai: `stock_transfers` có
> `UniqueConstraint(company_id, transfer_number)`, nên nó **ném
> IntegrityError**. Hậu quả thật không phải là hai chứng từ trùng số âm thầm,
> mà là **nhân viên không ghi được một lần chuyển kho có thật**, kèm màn hình
> lỗi không giải thích vì sao hôm qua vẫn làm được. Hai chuyện đó cần hai cách
> sửa khác nhau nên phải nói đúng cái nào.
>
> **Đã chứng minh test bắt được lỗi**, không chỉ xanh: khôi phục tạm bản
> `COUNT(*) + 1` và chạy lại — đỏ đúng chỗ. Không FAKE PASS.
>
> **Chưa làm, nói rõ:** hai người bấm lưu cùng lúc vẫn đọc ra cùng một số; ràng
> buộc unique giữ cho dữ liệu đúng, nhưng người thua nhận lỗi thay vì được cấp
> số kế tiếp. Thiếu phần *retry khi đụng*, ghi thành task riêng.

1. **Nội dung.** `transfers.py:32-36` sinh số bằng `COUNT(*) + 1`.
2. **Mục đích.** Không bao giờ cấp lại một số chứng từ đã dùng.
3. **Vấn đề hiện tại.** Đây đúng là lỗi mà docstring của
   `procurement_service.py:20` viết ra để cảnh báo: *"A count is not a sequence:
   delete any row and the next number repeats one already used"*. Và
   `StockTransfer` **có** unique constraint đó (`models.py:1101`). Lỗi này do
   chính lượt refactor này tạo ra.
4. **Giải pháp.** Dùng lại thuật toán MAX-của-dãy ở `procurement_service.py:15`
   — và gộp ba bản sinh số (`procurement_service.py:15`,
   `dashboard_routes.py:2818`, `transfers.py:32`) về một.
5. **Ảnh hưởng.** Điều chuyển kho.
6. **Database.** Không đổi.
7. **Backend.** `transfers.py`, và một module `numbering` dùng chung.
8. **Frontend.** Không đổi.
9. **API.** Không đổi.
10. **Permission.** Không đổi.
11. **UI/UX.** Không đổi.
12. **Test.** Tạo 3 phiếu, xoá phiếu giữa, tạo phiếu thứ 4 → số không trùng.
13. **Acceptance.** Test trên pass; ba bản sinh số còn một.
14. **Kỳ vọng.** Không còn IntegrityError bí ẩn khi xoá phiếu.
15. **Trạng thái.** `TODO`

---

### T-04 · Hai ô chọn kho trên màn hình nhận hàng, chú thích nói sai

**Priority:** P0 · **Type:** Data integrity + UX · **Dependencies:** không · **Status:** `DONE`

> **Kết quả.** Một ô duy nhất: chọn **kho**, chi nhánh suy ra từ kho
> (`procurement_service.receive`). Ô "Into Store" chỉ còn hiện với công ty
> **chưa có kho nào** — code và database lên khác thời điểm, nhập hàng không
> được dừng. Chú thích *"Tồn kho sẽ tăng ở kho này"* bây giờ mới đúng.

1. **Nội dung.** `po_view.html:111` (`warehouse_id`, chú thích *"Tồn kho sẽ tăng
   ở kho này"*) và `:139` (`store_id`) — hai ô cho cùng một câu hỏi.
2. **Mục đích.** Thủ kho chọn một chỗ, và hàng vào đúng chỗ đó.
3. **Vấn đề hiện tại.** Tồn kho tăng theo **`store_id`**
   (`procurement_service.py:171,201,211`); `warehouse_id` chỉ **dán nhãn**
   (`:217`). Chú thích là của tôi và nó **mô tả sai hành vi thật**. Hai ô cách
   nhau cả một bảng nhập số lượng nên khó nhận ra chúng cùng nói một chuyện.
4. **Giải pháp.** Một ô duy nhất. Vì `MaterialStock` còn khoá theo `store_id`
   (§8.15), ô đó phải là kho và hệ thống tự suy chi nhánh từ kho — không phải
   ngược lại.
   *Đánh đổi:* gộp ngay thì đúng ngữ nghĩa nhưng phụ thuộc T-10 (khoá tồn theo
   kho); gộp tạm bằng cách suy `store_id` từ `warehouse_id` thì đúng **ngay**
   và không chặn T-10.
5. **Ảnh hưởng.** Nhận hàng, tồn kho.
6. **Database.** Không đổi (bản tạm).
7. **Backend.** `procurement_service.py:163`, `dashboard_routes.py:5231`.
8. **Frontend.** `po_view.html:111-145`.
9. **API.** Bỏ `store_id` khỏi form nhận hàng.
10. **Permission.** Kèm T-05 (`store_id` thô từ form).
11. **UI/UX.** Một ô, một chú thích đúng.
12. **Test.** Chọn kho X → dòng tồn của **chi nhánh chứa X** tăng, và
    `GoodsReceipt.warehouse_id = X`.
13. **Acceptance.** Test trên pass; không còn hai ô.
14. **Kỳ vọng.** Không còn ghi tăng tồn sai địa điểm trong khi tin là đã chọn đúng.
15. **Trạng thái.** `TODO`

---

### T-05 · `store_id` thô từ form không được kiểm

**Priority:** P0 · **Type:** Security · **Dependencies:** không · **Status:** `DONE`

> **Kết quả.** `usable_store()` trong `app/utils/scope.py`: **từ chối**, không
> thay bằng mặc định. Áp cho cả `receive` lẫn `MaterialService.update_stock`.
>
> **Suýt để lọt, ghi lại vì đúng dạng lỗi lặp lại cả tuần này.** Bản đầu tôi
> viết `order_is_within_reach(store)` cho gọn. Hàm đó đọc `.store_id`, mà
> `Store` chỉ có `.id` → `AttributeError` → rơi vào `except` fail-open của
> chính hàm đó → **kiểm tra luôn luôn pass cho mọi chi nhánh**, dưới một dòng
> comment do tôi viết khẳng định dùng lại như thế là hợp lý. Viết tường minh
> ra, kèm lý do vì sao không dùng lại.

1. **Nội dung.** `receive_purchase_order` (`dashboard_routes.py:5231`) và
   `update_material_stock` (`:3869`) nhận `store_id` thẳng từ form.
2. **Mục đích.** Không ai ghi tồn kho vào một chi nhánh họ không thuộc về.
3. **Vấn đề hiện tại.** `MaterialService.update_stock` (`services.py:1981`)
   chỉ kiểm company của **vật tư**, không kiểm store. `@store_admin_required`
   chỉ xác nhận "là admin của **một** cửa hàng nào đó". Đối chiếu:
   `create_warehouse` (`:3087`) và `create_order` (`:966`) **có** kiểm.
4. **Giải pháp.** Kiểm store thuộc company **và** nằm trong phạm vi của người
   dùng, ở service.
5. **Ảnh hưởng.** Nhận hàng, điều chỉnh tồn kho tay.
6. **Database.** Không đổi.
7. **Backend.** `services.py`, `procurement_service.py`.
8. **Frontend.** Không đổi.
9. **API.** Thêm 403/ValueError.
10. **Permission.** Nội dung task.
11. **UI/UX.** Thông báo nói rõ chi nhánh không hợp lệ.
12. **Test.** POST `store_id` của chi nhánh khác → từ chối, tồn kho không đổi.
13. **Acceptance.** Test trên pass cho cả hai endpoint.
14. **Kỳ vọng.** Không còn ghi tồn kho vào chi nhánh tuỳ ý.
15. **Trạng thái.** `TODO`

---

### T-06 · Huỷ hợp đồng và huỷ đơn không đi qua service

**Priority:** P0 · **Type:** Data integrity · **Dependencies:** không · **Status:** `DONE`

> **Kết quả.** Route gọi service. `ContractService.cancel_contract` **đã có
> sẵn và đúng** — chỉ là route không bao giờ gọi nó, nên đoạn gỡ lifecycle
> trong đó chỉ chạy trong test. Đây là **lần thứ sáu** trong repo này có phần
> việc hoàn chỉnh mà không lối nào chạm tới, và là **lần đầu bản không ai chạm
> tới lại là bản ĐÚNG**, còn bản đang chạy thật mới là bản hỏng.
>
> Thêm `OrderService.cancel_order` (trước không có hàm huỷ nào).
>
> **Cố ý không làm cascade sang chứng từ con.** Quy tắc của chủ sản phẩm khi
> sửa sai là *huỷ có lý do rồi tạo lại*, từng chứng từ một, mỗi cái để lại dấu
> vết riêng — không phải một dây chuyền âm thầm viết lại giấy tờ khách đã cầm.
> Cũng đúng tinh thần Luật Kế toán 2015 Đ.27. Nếu muốn cascade thì đó là quyết
> định nghiệp vụ, phải ghi vào plan, không quyết lén trong hàm này. Docstring
> nói thẳng như vậy.

1. **Nội dung.** `cancel_contract` (`dashboard_routes.py:1629-1663`) sửa model
   thẳng trong route.
2. **Mục đích.** Huỷ một chứng từ phải gỡ đúng mọi thứ nó đã bật lên.
3. **Vấn đề hiện tại.** Route **không gọi** `ContractService.cancel_contract`
   (`services.py:731`), là hàm CÓ rollback `lifecycle.contract_created`. Đường
   service ấy chỉ còn test gọi — **chết trong production**. Huỷ hợp đồng qua UI
   để lại `contract_created=True` vĩnh viễn. `cancel_order` (`:1692`) cùng
   hình dạng; `OrderService` không có phương thức huỷ nào.
4. **Giải pháp.** Route gọi service; service **tính lại** lifecycle từ dữ liệu
   thay vì gỡ từng cờ — theo đúng mẫu `_resync_payment_lifecycle` đã làm.
5. **Ảnh hưởng.** Huỷ hợp đồng, huỷ đơn, mọi màn hình đọc lifecycle.
6. **Database.** Không đổi.
7. **Backend.** `dashboard_routes.py`, `services.py`.
8. **Frontend.** Không đổi.
9. **API.** Không đổi.
10. **Permission.** Không đổi.
11. **UI/UX.** Không đổi.
12. **Test.** Huỷ hợp đồng qua **HTTP** → `lifecycle.contract_created` False;
    và đường service cũ có test dương tính.
13. **Acceptance.** Test trên pass; không còn `db.session.commit()` cho việc
    huỷ trong route.
14. **Kỳ vọng.** Một đường huỷ, không phải hai.
15. **Trạng thái.** `TODO`

---

## P1 — Vòng đời chứng từ

### T-07 · State machine cho sáu chứng từ đang dùng cờ boolean

**Priority:** P1 · **Type:** Architecture · **Dependencies:** T-06 · **Status:** `TODO`

1. **Nội dung.** Order, Quotation, Contract, HandoverRecord, PaymentReport,
   GoodsReceipt, StockTransfer không có state machine.
2. **Mục đích.** Trạng thái là dữ liệu, không phải thứ suy ra ở tầng hiển thị.
3. **Vấn đề hiện tại.** `status_tokens.py:147` quyết định trạng thái bằng
   **object có thuộc tính nào**; `books.py:116` suy ra "đã vào sổ" theo cách
   thứ ba; 23 phương thức `can_*` dùng **hai quy ước ngược nhau** (danh sách
   trắng ở mua hàng, danh sách đen ở bán hàng), và `Quotation.can_edit()`
   (`:419`) **quên `is_canceled`** — báo giá đã huỷ vẫn sửa được.
4. **Giải pháp.** `StateMachineMixin` (status + TRANSITIONS + can/allowed);
   migration thêm cột `status` + backfill từ tổ hợp cờ; giữ cờ cũ một release.
   *Đánh đổi:* làm từng chứng từ một thì an toàn và lâu; làm cả bảy cùng lúc
   thì rẻ hơn và một migration sai là sai trên toàn sản phẩm. **Chọn từng cái
   một, bắt đầu từ Quotation** (ít quan hệ nhất, và đang có lỗi `can_edit`).
5–15. *(chi tiết mở khi bắt đầu; phụ thuộc T-06 vì huỷ phải sạch trước khi mô
   hình hoá lại trạng thái)*
15. **Trạng thái.** `TODO`

---

### T-08 · Audit trail: ai làm gì

**Priority:** P1 · **Type:** Architecture · **Dependencies:** không (xem ghi chú) · **Status:** `DONE`

> **Kết quả.** Bảng `document_transitions` + `app/services/transitions.py`,
> ghi tại 7 chỗ nghẽn service mà chính đợt refactor này đã gom lại.
>
> **Đảo phụ thuộc, nói rõ lý do.** Plan ghi T-08 phụ thuộc T-07. Không đúng:
> ghi *ai làm gì, lúc nào, vì sao* chỉ cần mỗi hành động có một chỗ nghẽn — và
> bảy chỗ đó đã gom xong trong phiên này. State machine là thay đổi lớn hơn và
> rủi ro hơn; không có lý do gì bắt nền móng maker–checker chờ nó.
>
> **Một bảng, không phải mỗi chứng từ một cặp cột.** (a) 5 loại chứng từ × 8
> hành động = 16 migration và 16 chỗ để quên; (b) một chứng từ có **nhiều** sự
> kiện — `signed_by` chỉ giữ chữ ký cuối và **mất** việc nó từng bị huỷ rồi ký
> lại; (c) Luật Kế toán 2015 Đ.27 mô tả một **lịch sử**, không phải một giá trị
> hiện tại.
>
> **Ba quyết định:**
> 1. **Sổ không bao giờ chặn việc nó đang ghi.** Lỗi ghi sử → log rồi nuốt.
>    Từ chối xác nhận tiền khách vì không chèn được một dòng audit là kết cục
>    tệ hơn một lỗ hổng trong lịch sử: lỗ hổng thấy được về sau, còn phiếu thu
>    kẹt ở quầy là sự cố ngay lúc đó. Có test bắn lỗi vào nó và khẳng định
>    phiếu thu vẫn xác nhận được.
> 2. **Không bịa người.** Ngoài request (migration, seed, job) → `user_id`
>    NULL. Lịch sử ghi sai tên làm **mọi dòng** đáng ngờ, kể cả dòng đúng.
> 3. **Không backfill.** Dữ liệu cũ không nói ai làm gì; bịa ra là gán tên
>    người vào việc họ có thể chưa từng làm. Lịch sử bắt đầu từ rỗng, từ hôm nay.
>
> **Đọc được trên màn hình đơn hàng, có test khẳng định.** Repo này đã có sáu
> lần làm xong mà không lối nào chạm tới — sổ tồn kho ghi-mà-không-đọc là một
> trong số đó. Một audit trail là thứ dễ thành cái thứ bảy nhất.

1. **Nội dung.** Toàn schema có đúng 3 cột `*_by_id`.
2. **Mục đích.** Duyệt mà không ghi ai duyệt thì không phải kiểm soát.
3. **Vấn đề hiện tại.** Không chứng từ nào ghi ai tạo, ai duyệt, **ai ký**, ai
   xác nhận tiền, ai huỷ. `Quotation` không có cả `approved_at`
   (`models.py:400`). Chủ sản phẩm vừa yêu cầu maker–checker — đây là nền
   móng còn thiếu của chính yêu cầu đó.
4. **Giải pháp.** Bảng `document_transitions` (chứng từ, từ trạng thái, tới
   trạng thái, ai, khi nào, lý do) thay cho việc rải thêm cặp cờ + `_at`.
15. **Trạng thái.** `TODO`

---

### T-09 · Gỡ trạng thái chết và luật không thi hành

**Priority:** P1 · **Type:** Correctness · **Dependencies:** T-07 · **Status:** `TODO`

`MasterAgreement.EXPIRED` (không dòng gán nào), `SupplierPayment.CANCELED`
(**phiếu chi NCC không bao giờ huỷ được**), `Document.SIGNED` (chỉ được đọc —
và là chỗ ký số sẽ bám vào), `PO.PARTIAL/RECEIVED` và `PR.CONVERTED` (tới được
bằng gán tắt, bỏ qua `TRANSITIONS`), và hai action workflow
(`quotation.approve`, `handover.confirm`) **hiện trên lưới cấu hình cho admin
đặt luật mà không nơi nào thi hành**.

Mỗi mục: hoặc nối đường tới, hoặc xoá. **Không để nguyên** — một trạng thái
khai báo mà không tới được là một lời hứa với người đọc code.

> **Phần đã xong (2026-09-27): hai action workflow không ai thi hành.**
> `quotation.approve` và `handover.confirm` giờ gọi `WorkflowService.require`
> trong `QuotationService.approve_quotation` và
> `HandoverRecordService.confirm_handover`.
>
> Đây là "nút ẩn" **ngược dấu, và nặng hơn**: nút ẩn lừa người đang nhìn màn
> hình, còn ở đây người bị lừa là **chủ công ty** — họ đặt một luật, được màn
> hình xác nhận là đã đặt, và tin rằng nhân viên không thể duyệt báo giá trước
> điều kiện họ yêu cầu. Không ai phát hiện ra được, vì **không bị từ chối**
> trông y hệt **luật đã thoả mãn**.
>
> **Nói rõ về phạm vi:** `DEFAULT_RULES` không có dòng nào cho hai action này,
> nên mặc định `require()` không tìm thấy luật và cho qua — không đổi hành vi
> với ai chưa đặt luật, và làm cho ô cấu hình có tác dụng với ai đã đặt. Không
> test cũ nào đỏ là vì vậy, **không phải** vì thay đổi này không được kiểm.
>
> **Test canh cho tương lai**: đọc `ALL_ACTIONS` rồi khẳng định mọi action đều
> xuất hiện ở đâu đó ngoài `workflow_service.py`. Test hành vi không thể thấy
> một action chưa ai viết đường tới — đúng cách hai cái này ẩn mình bấy lâu.
> Action thứ tám thêm vào năm sau không lặp lại được chuyện này trong im lặng.

15. **Trạng thái.** Phần action workflow: `DONE`. Các trạng thái chết còn lại:
    `TODO` (phụ thuộc T-07).

---

## P2 — UI/UX

### T-11 · Tách phần Nhận hàng khỏi màn hình đơn mua

**Priority:** P2 · **Type:** UX · **Dependencies:** T-04 · **Status:** `TODO`

1. **Nội dung.** `po_view.html:100-153` — form GR luôn mở sẵn, đã điền đủ số
   lượng, một cú bấm là ghi tăng tồn cả đơn.
2. **Vấn đề hiện tại.** "Vật tư đặt mua" là `<h5>` trần (`:69`), "Nhận hàng" là
   card-header **xanh lá** (`:103`) — hai mức nổi bật cho hai phần ngang cấp,
   và màu xanh đó **duy nhất trong toàn sản phẩm**, đang bù cho việc thiếu
   phân cấp thật. Hai bảng liền nhau **cùng có cột "Outstanding"**.
   `can_receive()` đúng với phần lớn vòng đời một PO, nên "luôn hiện" nghĩa là
   trang xem đơn và trang ghi nghiệp vụ kho bị hợp nhất.
3. **Giải pháp.** Modal, mở từ hàng hành động ở `:17-44`.
   *Đánh đổi:* trang riêng mất ngữ cảnh đơn hàng đúng lúc cần đối chiếu với
   phiếu giao của tài xế, và phải thêm route GET mới; drawer là mẫu thứ ba
   chưa từng có trong 86 template. Modal đã là ngôn ngữ chuẩn của sản phẩm cho
   hành động nghiêm trọng.
15. **Trạng thái.** `TODO`

---

### T-12 · "Điền từ đề xuất" xoá trắng form đang nhập

**Priority:** P2 · **Type:** Data loss · **Dependencies:** không · **Status:** `DONE`

> **Kết quả.** Đổi `<a href>` thành **nút submit**, và server **gộp** gợi ý vào
> những gì đang gõ dở thay vì vẽ lại từ đầu. Tiêu đề, chi nhánh, ngày, ghi chú
> và mọi dòng gõ tay đều còn nguyên — nhãn "điền thêm vào" giờ mới đúng.
>
> **Một quyết định hành vi cũ không phải trả lời:** vật tư người dùng **tự gõ**
> mà gợi ý cũng đề xuất thì giữ **số của người dùng** và chỉ hiện **một dòng**.
> Họ nhìn kho thật, còn gợi ý chỉ là phép tính. Hai dòng cùng một vật tư là một
> đề nghị đặt hàng nhà cung cấp hai lần.
>
> **Lỗi của tôi, lần thứ ba cùng một dạng trong phiên này:** test đầu tiên post
> `material_id[]`/`quantity[]`, trong khi form gửi `line_material_id[]`. Tức là
> **không có dòng nào được đọc là "đã gõ"**, hai assert xanh vì lý do sai và một
> assert đỏ vì lý do đúng — chính cái đỏ đó lộ ra chuyện này. Post dữ liệu mà
> form không bao giờ gửi là đang kiểm tra **trí nhớ của tôi về tên trường**,
> không phải kiểm tra sản phẩm.

`pr_form.html:48` là `<a href>` nằm **bên trong `<form>`** (mở ở `:16`). Bấm =
điều hướng đi, **không cảnh báo**; tiêu đề, cửa hàng, ngày cần, ghi chú và mọi
dòng đã nhập tay **mất sạch**. Cơ chế khôi phục (`base.html:246`) chỉ chạy sau
POST thất bại. Nhãn nói "điền thêm vào", hành vi là "bỏ hết làm lại".

15. **Trạng thái.** `TODO`

---

### T-13 · Bỏ nút trùng và hộp xác nhận hai lần trên màn hình đơn hàng

**Priority:** P2 · **Type:** UX · **Dependencies:** không · **Status:** `MỘT PHẦN DONE` — phần còn lại **CẦN CHỦ SẢN PHẨM QUYẾT**

> **Đã làm (an toàn, không đổi diện mạo):** bỏ hộp xác nhận **trùng** ở 3 hành
> động — duyệt báo giá, ký hợp đồng, xác nhận bàn giao. Mỗi chỗ có `confirm()`
> trên *form* **và** một cái nữa trên *nút*, một cú bấm hai hộp thoại, **hai câu
> chữ khác nhau**. Câu đầy đủ (câu nói rõ hậu quả — *"duyệt rồi thì không sửa
> được nữa"*) lại là câu **thứ hai**, sau khi người ta vừa bấm OK cho câu mơ hồ
> hơn. Lúc đó họ đang bấm cho hộp thoại biến mất — đúng thói quen mà xác nhận
> sinh ra để ngăn. Với người không rành công nghệ còn tệ hơn: bị hỏi hai lần
> dạy cho họ rằng câu hỏi đầu **không tính**, và người đã học điều đó thì thôi
> đọc luôn câu thứ hai. Giữ lại hộp trên form vì nó có câu nói rõ hậu quả.
>
> **CẦN QUYẾT ĐỊNH — chưa làm:** hai phần còn lại **là cùng một thay đổi**, và
> nó **đổi diện mạo màn hình chính**:
> - Màn hình vẽ tiến trình **hai lần**: timeline viết tay (9 `timeline-marker`)
>   và macro `process_list()` (dùng 1 lần) — macro vốn sinh ra để **thay thế**
>   bản viết tay.
> - Năm hành động, mười nút. Nhưng **một nửa số nút nằm ngay trong timeline
>   viết tay đó**. Bỏ timeline = bỏ luôn nút trùng; hai việc là một.
>
> Đây là gỡ khoảng một nửa của `orders/view.html` (762 dòng). Chủ sản phẩm đã
> dặn *"Đồng bộ cấu trúc, **giữ diện mạo**"* — nên tôi **không tự ý** gỡ. Hai
> phương án:
> **(a)** giữ timeline viết tay, bỏ `process_list()` → màn hình y như cũ, hết
> trùng lặp trong code, nhưng macro dùng chung ở các màn khác sẽ không áp ở đây;
> **(b)** bỏ timeline viết tay, dùng macro → hết trùng cả code lẫn nút, đồng bộ
> với các màn khác, **nhưng màn hình chính trông khác đi rõ rệt**.

`orders/view.html`: **năm hành động, mười nút** (timeline `:200,257,343,402,483`
và Quick Actions `:504,532,570,579,585`), kích cỡ khác nhau nên trông như hai
việc khác nhau. Trạng thái quy trình vẽ hai lần: timeline viết tay (`:138`) và
`process_list()` (`:627`) — mà macro ấy sinh ra đúng để **thay thế** bản viết
tay. Và `:179-182` hỏi xác nhận **hai lần** với hai câu chữ khác nhau.

15. **Trạng thái.** `TODO`

---

### T-14 · Nút bị chặn phải giải thích, không biến mất

**Priority:** P2 · **Type:** UX · **Dependencies:** không cho PO (xem ghi chú) · **Status:** `DONE` (phần Đơn mua hàng)

> **Kết quả.** Khối nhận hàng **không biến mất nữa**: nó ở lại, màu xám, và nói
> rõ bước kế tiếp — *"Đơn đang ở trạng thái Nháp — cần bấm Gửi NCC trước"*. Kèm
> hai trạng thái chặn khác (đã nhận đủ, đã huỷ), vì "bấm không thấy gì xảy ra
> và không biết vì sao" là cùng một thất bại ở cả ba.
>
> **Bỏ phụ thuộc T-07 sau khi đọc code.** Plan ghi task này chờ state machine
> vì câu giải thích phải lấy từ đâu đó. Với đơn mua hàng thì không cần:
> `PurchaseOrder.status` và `can_receive()` đã nói sẵn *đang ở đâu* và *cần làm
> gì tiếp*. Phụ thuộc trong plan là phỏng đoán, không phải sự thật — cái này
> không trụ được khi đối chiếu với code.
>
> **Vì sao đây là việc quan trọng chứ không phải làm đẹp:** với người dùng
> không rành công nghệ, nút *biến mất* tệ hơn nút *xám*. Họ không biết nó từng
> có, nên không hỏi "sao lại tắt?", mà kết luận **"phần mềm không làm được"** —
> và đó là lúc người ta quay lại ghi sổ tay song song.
>
> **Còn lại:** các màn hình khác vẫn ẩn nút khi bị chặn (grep `disabled`: 7 chỗ,
> không chỗ nào là "chặn kèm lý do"). Làm tiếp theo cùng T-07.

Grep `disabled` trên toàn bộ template: 7 kết quả, **không cái nào là "chặn nút
để giải thích lý do"**. Với người dùng không giỏi công nghệ, biến mất tệ hơn
nút xám: họ không biết nút **từng tồn tại**. Ví dụ thật: PO ở `draft` thì
`po_view.html:101` ẩn toàn bộ phần nhận hàng, và không gì nói "phải bấm Gửi NCC
trước".

Phụ thuộc T-07 vì câu giải thích đến từ state machine ("đang ở Nháp, cần Gửi
NCC trước").

15. **Trạng thái.** `TODO`

---

## P3 — Dọn dẹp

### T-15 · Xoá `/materials/low-stock`, thay bằng bộ lọc

**Priority:** P3 · **Type:** Cleanup · **Dependencies:** không · **Status:** `DONE`

> **Kết quả.** Thêm bộ lọc `?low_stock=1` vào `/materials/` **trước**, rồi mới
> xoá màn hình riêng. Bỏ một khả năng rồi gọi đó là dọn dẹp thì dọn dẹp thành
> lỗi thoái lui — "chỉ xem thứ sắp hết" là lý do người ta bấm vào menu đó.
>
> **Giữ lại `ProductionPlanService.low_stock_materials`** — đó là phép tính mà
> `purchase_suggestions` dựa vào. Xoá màn hình không phải lý do để xoá phép
> tính, và nếu chỉ grep theo tên route thì sẽ tưởng là xoá được (đúng cái bẫy
> "chọn theo tên" đã gặp 9 lần trong repo này).
>
> **Xoá xong lộ ra một lỗi đáng giá hơn cả việc dọn dẹp.** `/materials/low-stock`
> rơi xuống khớp với `/materials/<material_id>`, đưa chuỗi `"low-stock"` xuống
> DB như UUID → `ValueError: badly formed hexadecimal UUID string` → **500**.
> Nghĩa là **bất kỳ link hỏng/cũ nào tới bất kỳ bản ghi nào cũng làm sập màn
> hình** thay vì báo "không tìm thấy" — mọi model, mọi route chi tiết. Một
> bookmark tới đơn đã xoá, một URL bị cắt trong email, một lỗi gõ. Sửa ở
> `BaseRepository.get_by_id`: id sai định dạng là yêu cầu một thứ không tồn
> tại, tức `None`, đúng thứ mọi caller đã xử lý sẵn. Test phủ cả `/orders/`
> chứ không chỉ vật tư, vì lỗi này chưa bao giờ là của riêng vật tư.

Đã kiểm: `low_stock_materials` (`services.py:2379`) chỉ là
`Material.query.filter_by(is_active=True)` rồi lọc Python bằng `is_low_stock`.
Và `materials/list.html` **đã hiển thị đủ**: tô `table-warning` (`:80`), badge
`Low Stock` (`:85`), `total_stock / min_stock_level` (`:91`) — đúng 4 cột mà
`low_stock.html` có, cộng 5 cột nữa. Màn hình riêng không thêm thông tin nào,
chỉ **ẩn bớt dòng**.

**Phải xoá theo:** route `dashboard_routes.py:5043`, template
`materials/low_stock.html`, link menu `base.html:92`, dòng quyền
`permission_map.py:92`, ba test (`test_permission_map.py:110`,
`test_production_plan.py:113`, `test_empty_states.py:40`), đường dẫn trong
`scripts/qc_audit.py:436`.

**PHẢI GIỮ:** service `low_stock_materials` — `purchase_suggestions`
(`services.py:2437`) dùng lại nó. Xoá service sẽ phá đề xuất mua hàng.

15. **Trạng thái.** `TODO`

---

### T-16 · `/materials/purchase-suggestions` — KHÔNG xoá, và đây là lý do

**Priority:** P3 · **Type:** Cleanup · **Dependencies:** không · **Status:** `NEEDS REVIEW`

Chủ sản phẩm yêu cầu xoá vì trùng với "Điền từ đề xuất tự động" trong
`/requisitions/create`. **Đã kiểm bằng code, và chúng không trùng.**

Cả hai trỏ cùng một URL (`purchase_suggestions.html:20` và `pr_form.html:48`)
và gọi cùng service (`requisition_service.py:26` và `dashboard_routes.py:5058`).
Nhưng `requisition_service.py:30` **chỉ giữ 3 trường** — `material_id`,
`quantity`, `unit` — và **vứt bỏ** `required`, `available`, `min_level`,
`unit_price`, `est_cost`, cùng **toàn bộ phần gộp theo nhà cung cấp**.

Tức trang đề xuất trả lời **"tại sao cần mua và tốn bao nhiêu"**; nút trong form
chỉ làm việc **"điền số vào"**. Quản đốc cần con số ước tính chi phí để xin
duyệt, và dữ liệu đó không có trong form PR.

**Đề xuất:** giữ cả hai, sửa T-12 (link xoá trắng form) và thống nhất tên gọi —
hiện màn hình này có **ba tên** (`base.html:104`, `pr_list.html:17`,
`purchase_suggestions.html:3`).

**Cần chủ sản phẩm xác nhận** trước khi xoá, vì xoá sẽ mất phần ước tính chi phí.

15. **Trạng thái.** `NEEDS REVIEW` — chờ quyết định.

---

## P4 — Test / Hardening

### T-17 · Một hành trình HTTP vai nhân viên

**Priority:** P4 · **Type:** Test · **Dependencies:** T-01, T-02 · **Status:** `DONE`

> **Kết quả.** Một hành trình liên tục của nhân viên: lập báo giá → khách mặc
> cả, sửa lại → ký hợp đồng → ghi nhận tạm ứng → **xác nhận tiền không phải
> việc của nhân viên**, đẩy lên hàng đợi → quản lý duyệt, và **lúc đó tiền mới
> tính** → nhân viên sửa lại phiếu đã xác nhận thì bị chặn.
>
> Đo trước khi viết: suite `login("admin")` **319 lần**, `login("staff")` **25
> lần**. Phần maker–checker vừa dựng lại đúng là phần **chạy khác nhau** giữa
> hai vai — tức là test mù đúng chỗ hành vi mới nằm.
>
> **Sản phẩm sửa lại kịch bản của tôi.** Bản đầu đi thẳng báo giá → thu tiền và
> bị từ chối: `payment.advance` cần `contract_signed`. Tôi đã viết một hành
> trình **không tồn tại trong nghiệp vụ này**. Thêm bước hợp đồng vừa đúng vừa
> làm test phủ thêm cả tạo và ký hợp đồng.
>
> **Đã chứng minh test bắt được lỗi — và suýt bị chính phép thử đó lừa.** Thêm
> vai của nhân viên vào `DECIDING_ROLES` (đúng kiểu sửa ẩu biến maker–checker
> thành hình thức) → test phải đỏ. Lần đầu tôi thêm `'staff'` và test **vẫn
> xanh**, trông như test mù. Thật ra người dùng tên `staff` có role là
> **`user`** — phép phá của tôi không phá gì cả. Bài học ngược với cả phiên
> này: **khi phá code mà test không đỏ, khả năng "phá sai" cao ngang "test
> sai"** — tin ngay vế sau thì đã đi sửa một test vốn đã đúng.

918 test, **đúng một** test đổi vai giữa hành trình. `login("admin")` gần như
khắp nơi — sản phẩm chưa từng được kiểm cho vai không phải admin.

Một test: nhân viên tạo → sửa → gửi duyệt → (đổi vai) quản lý duyệt → nhân
viên cố sửa lại → bị từ chối. Test này phủ đồng thời bốn dòng trống trong
audit.

15. **Trạng thái.** `TODO`

---

### T-18 · Gọi thẳng API những endpoint mà UI đã ẩn nút

**Priority:** P4 · **Type:** Security test · **Dependencies:** không · **Status:** `DONE`

> **Kết quả.** 5 test gọi thẳng URL với tư cách người dùng hợp lệ, đã đăng nhập,
> có quyền: ký lại hợp đồng đã ký, duyệt lại báo giá đã duyệt, nhập kho cho PO
> còn Nháp, xoá tài liệu hai lần, huỷ hợp đồng hai lần.
>
> **Cả 5 đều xanh — sản phẩm đã chặn sẵn.** Đây là tin tốt thật, nhưng chỉ đáng
> tin vì đã **kiểm lại**: xoá chốt `can_receive()` trong
> `ProcurementService.receive` thì test PO-nháp **phải đỏ**.
>
> **Lần đầu thử thì nó vẫn xanh — và lỗi là của tôi.** Test đó post mỗi ngày
> tháng, **không có số lượng**, nên chẳng có gì được nhập dù có chốt hay không.
> Một request rỗng không phải là phép thử một lời từ chối. Post số lượng thật
> vào thì xoá chốt là đỏ ngay, đúng câu *"tạo phiếu nhập cho đơn chưa từng gửi
> NCC"*.
>
> Đây là **lần thứ tư trong phiên** cùng một dạng lỗi ở test do tôi viết:
> fixture tự bịa dữ liệu, URL tôi đoán, tên trường tôi nhớ nhầm, và giờ là
> request rỗng quá nên không chạm tới thứ cần kiểm. Cùng một hình dạng: **kiểm
> tra hình dung của tôi về hệ thống, thay vì kiểm tra hệ thống.**

Đúng **một** test làm điều này (`test_a_voided_payment_stays_voided.py:74`) —
và nó tìm ra một lỗ hổng thật ngay lần đầu. 23 endpoint còn lại trong
`DESTRUCTIVE` (`test_confirmations.py:24`) chưa có test bypass nào: `sign_contract`
trên hợp đồng đã ký, `approve_quotation` trên báo giá đã duyệt,
`receive_purchase_order` trên PO chưa gửi, `delete_document`.

15. **Trạng thái.** `TODO`

---

### T-19 · 29 route POST chưa từng nhận một POST nào

**Priority:** P4 · **Type:** Test · **Dependencies:** không · **Status:** `TODO`

Gồm `create_material`, `create_store`, `edit_user`, `update_material_stock`,
`create_supplier_invoice`, `delete_document`, `cancel_payment`,
`edit_quotation`, `edit_contract`, `edit_handover`.

Ba route (`cancel_contract`, `cancel_quotation`, `deactivate_material`) chỉ
được kiểm bởi probe **âm tính** khẳng định "dữ liệu không đổi" — **xoá hẳn
route đi, suite vẫn xanh**.

15. **Trạng thái.** `TODO`

---

### T-20 · Siết các test xanh-vì-lý-do-sai đã xác định

**Priority:** P4 · **Type:** Test · **Dependencies:** không · **Status:** `IN PROGRESS`

> **Kết quả.** Siết 4 chỗ, **đo trước rồi mới siết**, không đoán.
>
> **Hàng rào `login()` không bắt được lỗi nào — nói thẳng.** Fixture `login()`
> post thông tin đăng nhập rồi **không kiểm gì cả**, 344 lời gọi phụ thuộc vào
> nó. Nếu đăng nhập âm thầm hỏng thì mọi test kiểu "người này không được làm X"
> biến thành "khách vãng lai không được làm X" — vẫn xanh, vẫn vô nghĩa. Rủi ro
> là thật về nguyên tắc, nhưng **thực tế không dính**: cả suite đang đăng nhập
> đúng. Giờ nó là lưới an toàn cho tương lai, **không phải** một lỗi tôi tìm ra.
> (Cũng rút lại nghi ngờ của tôi về `badmin` — user đó dùng đúng mật khẩu mặc
> định.)
>
> **Ba chỗ còn lại là điểm yếu thật:**
> - `in (302, 403)` ở 2 màn settings: đo ra **luôn luôn 403**, không bao giờ
>   302. Nhận thêm 302 chẳng được gì, mà lại **vẫn xanh** nếu chốt chặn thoái
>   hoá thành "đá về trang login" — nhìn từ test thì giống hệt, nhìn từ người
>   dùng **đang đăng nhập** thì khác hẳn.
> - `in (403, 302, 404)` ở test cách ly chi nhánh: đo ra **302 → `/orders`**.
>   Giờ ghim đúng mã **và ghim cả nơi người dùng bị đưa tới** — phần mà người
>   dùng thực sự nhìn thấy.
> - Test cảnh báo "không hoàn tác được" quét **toàn trang** tìm bất kỳ cụm từ
>   nào, nên không phân biệt được *"hành động này có cảnh báo"* với *"trang này
>   có chữ vĩnh viễn ở đâu đó"*. File đã có sẵn `_says_it_is_final(body,
>   action_url)` neo vào đúng hộp thoại — test đó chỉ là không dùng.
>
> **Điểm chung:** một assert nhận **nhiều kết quả** thì không cho biết kết quả
> nào đã xảy ra. Mọi chỗ như vậy trong suite đều do ai đó **không đo trước** —
> kể cả tôi, **bốn lần** trong phiên này.

Đã xong: hai test phân trang (`test_order_search.py:100`,
`test_orders_list_filters.py:144`) — `assert` nằm trong `if 'page=2' in body:`
trên fixture 3 bản ghi với trang 20 dòng, nên **chưa từng chạy**. Viết lại cho
thật: tính năng hoá ra **đúng**, nhưng suốt thời gian qua không ai biết.

Còn lại: `login()` trong `conftest.py:136` không khẳng định đăng nhập thành
công (nên `in (302, 403)` có thể xanh vì khách vãng lai); `_guarded()` trong
`test_confirmations.py:41` trả `True` khi **không tìm thấy form nào**;
`test_suggestions_say_which_stock.py:34` khớp `inspect.getsource` nên trúng cả
chú thích; `test_untested_routes.py:20` xanh vì `vi` đã là mặc định.

15. **Trạng thái.** `IN PROGRESS`

---

## Lệch khỏi thứ tự P0→P4, và lý do

**T-20 làm trước một phần**, dù là P4. Lý do: các task P0 sẽ được kiểm bằng
chính bộ test này. Sửa bảo mật rồi khẳng định "test xanh" trong khi biết có
test xanh-vì-lý-do-sai là xây trên nền không đo được. Phần đã làm là hai test
rẻ nhất và đang che một lỗi kinh điển.

**T-04 (P0) chặn T-11 (P2)** — không tách được phần Nhận hàng ra modal khi còn
chưa rõ ô nào quyết định hàng vào đâu.

**T-07 chặn T-14** — câu giải thích cho một nút bị chặn phải đến từ state
machine, không phải từ một chuỗi viết tay ở mỗi template.

---

## THIẾU SÓT CỦA BẢN KẾ HOẠCH NÀY — §8.2 IN ẤN (ghi ngày 2026-09-28)

Bản kế hoạch 20 task ở trên **bỏ sót hoàn toàn** yêu cầu §8.2 mà chủ sản phẩm
đã trả lời rất cụ thể:

> *"Cách A, và mọi loại form in hay chứng từ được in đều phải dùng loại A, nó
> là quy chuẩn của app ngay từ đầu rồi, nên mới nói phải làm đồng bộ tất cả các
> feature xung quanh cái chức năng in này giống nhau ở mọi loại màn hình (nút
> nhấn in, màn hình lịch sử file đã in, popup, ...), và chức năng quản lý form
> in cũng cần khoa học và đầy đủ CRUD - vì sau này mở rộng thì sẽ rất nhiều
> form in của rất nhiều loại chứng từ, phải làm sao để nó quản lý khoa học và
> gọn gàng."*

Đây là **lỗi của tôi khi lập kế hoạch**, không phải yêu cầu mới phát sinh. Ghi
lại ở đây thay vì lặng lẽ thêm task, vì bản kế hoạch được duyệt dựa trên giả
định nó đã phủ hết những gì chủ sản phẩm đã chốt.

### Hiện trạng đã khảo sát (2026-09-28, có trích dẫn dòng)

**9 loại chứng từ in được. 7 loại đi qua template (Cách A), 2 loại KHÔNG.**
Đơn mua hàng (`procurement_doc.py:22`) và Lệnh sản xuất (`production_doc.py:58`)
dựng bằng Python cứng, `send_file` thẳng, **không tạo dòng `Document` nào** —
nên không có lịch sử file in, không sửa được mẫu, không đổi được bố cục nếu
không sửa code.

**Nút in / lịch sử / popup không đồng bộ.** Macro `generate_document_modal`
(`macros/ui.html:352`) được 5 file dùng; 4 màn hình in **không** qua macro:
`agreements/view.html:20`, `orders/view.html:558` (ĐĐH — cùng file đã dùng
macro 6 lần), `procurement/po_view.html:28`, `production/plan.html:36`.
Partial lịch sử `_generated_documents.html` chỉ được **4** màn hình include;
HĐNT, ĐĐH, đơn mua, lệnh sản xuất **không có** lịch sử file in.

**Quản lý mẫu in thiếu CRUD và không có phiên bản.** Có: list
(`dashboard_routes.py:421`), upload (`:444`), activate (`:575`), deactivate
(`:511`), delete có điều kiện (`:527`). **Không có**: sửa (đổi tên/mô tả/thay
file tại chỗ), xem trước, tải mẫu về. **Không có cột `version`**, không có lịch
sử, không quay lại bản cũ được: upload trùng loại thì tắt bản cũ rồi chèn dòng
mới (`:486-499`). Chứng từ đã in xong **không giữ lại bản mẫu đã dùng** — chỉ
giữ `variables_used` (dữ liệu), không giữ bố cục.

**Dropdown upload chỉ có 7 loại** (`settings/templates.html:150-157`), thiếu
`agreement`, `order_confirmation`, `delivery` — trong khi code lại **bắt buộc**
phải có mẫu các loại đó (`services.py:1822`, `:1857`). Nên hai nút in đó **không
thể thành công** trừ khi tạo dòng mẫu ngoài giao diện.

### Ba nhóm việc

- **T-22a** ✅ `DONE`: hai bản in dựng bằng Python giờ **có để lại dấu vết** —
  lưu file, tạo dòng `Document`, và hai màn hình đó hiện lịch sử file đã in.
  **Chưa phải Cách A** (xem T-22b).
- **T-22b** `TODO` (P1): soạn mẫu `.docx` cho Đơn mua hàng và Lệnh sản xuất rồi
  chuyển hẳn sang template. Không gộp vào T-22a được vì bố cục PO có vòng lặp
  dòng (`{%tr for %}`), **không thể suy ngược ra từ code Python đang dựng nó** —
  đây là việc soạn nội dung, không phải việc code.
- **T-23a** ✅ `DONE`: HĐNT và ĐĐH đã vào chuẩn chung (nút, popup, chọn định
  dạng, và HĐNT lần đầu có lịch sử file in). Thêm `EMBEDDED_CONTROLS` cho nút in
  **nằm lẫn bên trong** một màn hình đã chuẩn — ĐĐH trước đây không nằm trong
  danh sách nào nên không test nào soi. Và thêm một test **quét mọi template**
  để không màn hình in nào đứng ngoài cả ba danh sách.
- **T-23b** `TODO` (P1): Đơn mua hàng + Lệnh sản xuất vào chuẩn chung — chặn bởi
  T-22b.
- **T-24** ✅ `DONE`: có `version` (migration `b5c6d7e8f9a0`), tải bản mới thành
  N+1 và **giữ nguyên bản N**, sửa được tên/mô tả nhưng **không thay được tệp**
  của mẫu đã in ra chứng từ, tải mẫu về xem được, và quay lại bản cũ được.
  Năm hàng rào do chính đợt refactor này dựng đã bắt lỗi tôi khi làm task này —
  trong đó có luật "template không tự dựng bảng nhãn", và đi theo luật đó ra
  code sạch hơn bản tôi viết ban đầu.

> **Đã sửa ngay trong lúc khảo sát (không chờ):** `Document.source_type` /
> `source_id` **chưa từng được ghi bởi bất kỳ đường code nào** — cột do tôi
> thêm, migration do tôi viết có cả backfill, hàm đọc do tôi viết, test do tôi
> viết và **xanh**, vì mỗi fixture tự tay gán `source_type`. Backfill làm dòng
> cũ có dữ liệu nên nhìn bảng tưởng lành; mọi chứng từ in ra **sau đó** đều
> NULL. Đây là lần thứ **bảy** trong repo có phần việc hoàn chỉnh mà không lối
> nào chạm tới, và là lần duy nhất **test che mất lỗi**. Đã sửa tại
> `_save_document`, thêm test đi qua đường in thật.

---

### T-21 · Cấp số chứng từ khi hai người lưu cùng lúc

**Priority:** P2 · **Type:** Bug · **Dependencies:** T-03 · **Status:** `DONE`

> **Kết quả.** `retry_if_the_number_was_taken` trong `app/services/numbering.py`,
> áp cho `transfer_stock`. **Chỉ số tự sinh mới thử lại** — số người dùng tự gõ
> vẫn để lỗi, vì âm thầm lưu DC-0007 của họ thành DC-0008 là ghi lên chứng từ
> một số khác với số trên tờ giấy họ đang cầm.
>
> **Hai lần tôi sai, ghi lại cả hai:**
> 1. *Test đầu không tái hiện được tranh chấp.* Tôi chèn số đã bị chiếm rồi mới
>    lưu — nhưng lượt lưu **tính lại** số nên tự động né, và test **xanh dù chưa
>    có retry nào**. Tranh chấp thật là **cả hai cùng tính ra một số trước khi
>    ai kịp ghi**; giờ mô phỏng bằng cách cho bộ cấp số trả về một số cũ đúng
>    một lần.
> 2. *Bản retry đầu tiên sai theo kiểu test không bắt được.* Tôi rollback rồi
>    gán số mới vào chính dòng đó. Nhưng `rollback()` xoá **mọi thứ** — cả trừ
>    cộng tồn kho, cả các dòng, cả sổ movement — nên nó sẽ commit một phiếu
>    điều chuyển **không dòng nào và không ảnh hưởng tồn kho**, tệ hơn lỗi nó
>    thay thế. Phải thử lại **toàn bộ thao tác**, an toàn vì thao tác đọc lại
>    dữ liệu từ DB mỗi lần.
>
> **Không hứa:** số liên tục không nhảy. Transaction rollback vì lý do khác vẫn
> ăn mất một số — đúng như hoá đơn giấy hỏng vẫn mất số.

1. **Nội dung.** `next_document_number` đọc số lớn nhất rồi +1. Hai người bấm
   lưu cùng lúc đọc ra cùng một số.
2. **Mục đích.** Người thứ hai được cấp số kế tiếp, thay vì nhận màn hình lỗi.
3. **Vấn đề hiện tại.** Các bảng có số đều có `UniqueConstraint(company_id,
   <số>)` — **dữ liệu vẫn đúng**, đây không phải lỗi trùng số âm thầm. Nhưng
   `INSERT` thứ hai ném `IntegrityError` và người dùng thấy lỗi 500 không giải
   thích được. Phát hiện khi làm T-03; ghi lại thay vì vá vội.
4. **Giải pháp.** Bắt `IntegrityError` ở chỗ lưu, tính lại số, thử lại có giới
   hạn (3 lần). Không dùng khoá bảng: mỗi công ty mỗi loại chứng từ một dãy số,
   tranh chấp thật sự rất hiếm, khoá sẽ đắt hơn lỗi nó tránh.
   *Đánh đổi:* dãy số vẫn có thể thủng khi transaction bị rollback vì lý do
   khác — chấp nhận được, và đúng như hoá đơn giấy vẫn huỷ số.
5. **Chức năng ảnh hưởng.** Mọi màn hình tạo chứng từ có số tự sinh.
6. **Database.** Không đổi — ràng buộc đã có.
7. **Backend.** `app/services/numbering.py` + các chỗ gọi khi lưu.
8. **Frontend.** Không đổi.
9. **API.** Không đổi.
10. **Permission.** Không liên quan.
11. **UI/UX.** Người dùng không thấy gì khác, đó là mục tiêu.
12. **Kiểm thử.** Test mô phỏng đụng độ: chèn sẵn số sắp được cấp rồi lưu, phải
    ra số kế tiếp chứ không ném lỗi.
13. **Rủi ro.** Retry lồng trong transaction đang mở — phải kiểm chỗ gọi.
14. **Ước lượng.** Nhỏ.
15. **Ghi chú.** Không gộp vào T-03: T-03 là gộp hai bản cài đặt về một, còn
    đây là hành vi mới. Trộn hai thứ vào một commit thì không rà lại được.
