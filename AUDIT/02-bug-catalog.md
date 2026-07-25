# GIAI ĐOẠN 2 — Bug Catalog (QA Lead)

**Persona:** QA Lead cố tình phá sản phẩm. **Trạng thái:** đang chạy (v1, 2026-07-25).
Harness: `pytest` trên SQLite (xem `tests/`). Chạy: `venv/Scripts/python.exe -m pytest`.

**Test hiện có:** 17 test (13 PASS, 4 xfail có chủ đích): `test_smoke.py` ×5, `test_tenant_isolation.py` ×4, `test_quotation_money.py` ×4 (xfail B2,B3), `test_access_control_post.py` ×4 (xfail B5,B6).

---

## Đã xác minh — an toàn (không phải bug)
| Mã | Vùng | Kết quả kiểm thử |
|----|------|------------------|
| OK1 | Tenant isolation (GET views) | `GET /customers/<id>` và `/orders/<id>` với id của **công ty khác** → **302 về trang list** (không lộ dữ liệu). ID không tồn tại cũng 302 giống hệt → không phân biệt được sự tồn tại (tốt, chống enumeration). ⇒ **P7 IDOR không dính** ở các GET view này. |
| OK2 | Auth guard | Truy cập `/` khi chưa đăng nhập → 302 về `/auth/login`. Sai mật khẩu → vẫn chưa đăng nhập. |
| OK3 | RBAC (company-admin endpoints) | `staff` (role `user`) GET `/settings/company` và `/stores/create` → **403** (đúng). `@company_admin_required` hoạt động. |
| OK4 | Payment sequencing | `create_payment` chặn: advance phải sau khi contract **signed**; final phải sau khi handover **confirmed** (`dashboard_routes.py:1533,1543`). ✅ enforced. |
| OK5 | Approve quotation state | `QuotationService.approve_quotation` gọi `can_approve()` → chặn re-approve/approve khi đã canceled (`services.py:453`). ✅ enforced. |

## Bug đã tìm được
| Mã | Mức | Mô tả | Vị trí | Tái hiện | Mong đợi vs Thực tế |
|----|-----|-------|--------|----------|---------------------|
| B1 | Low | Route `/api/quotations/<quotation_id>` được đăng ký **2 lần** (decorator trùng) | `app/routes/dashboard_routes.py:2000-2001` | Xem `app.url_map` → endpoint `dashboard.get_quotation_detail` xuất hiện 2 lần | Chỉ nên đăng ký 1 lần. Thực tế: 2 decorator `@route` giống hệt liên tiếp (copy-paste). Không crash nhưng là dead duplication → xóa 1 dòng. |
| B2 | Medium | **Số lượng/đơn giá âm không bị chặn** khi tạo/sửa chứng từ → subtotal/total âm | `dashboard_routes.py:605-620` (create_quotation), `707-723` (edit_quotation); mẫu lặp ở contract/handover/payment | Test `test_negative_quantity_is_rejected` (xfail): POST quotation với `item_quantity[]=-2` → quotation được tạo với subtotal âm | Mong đợi: từ chối hoặc chặn giá trị âm. Thực tế: chấp nhận, lưu subtotal/total âm. Cần validate `qty>=0`, `price>=0` tập trung. |
| B3 | **High** | **Số hiệu chứng từ unique TOÀN CỤC thay vì theo tenant** (xác nhận P2) — chặn ở cả model lẫn route | Model `models.py` (`unique=True`); route `dashboard_routes.py:591` (`filter_by(quotation_number=...)` không lọc company) | Test `test_same_quotation_number_allowed_across_tenants` (xfail): công ty A dùng `Q-DUP`, công ty B KHÔNG dùng lại được | Mong đợi: unique theo `(company_id, number)` → B dùng lại được. Thực tế: bị chặn toàn cục → rò rỉ/đụng độ giữa tenant. Sửa ở GĐ5 theo D1 (migration rollback được, tương thích Postgres). |
| B4 | Low | Tính tiền dùng `float` rồi lưu `Numeric` → rủi ro sai số/làm tròn với số lớn | `dashboard_routes.py` (mọi handler create/edit chứng từ) | Đọc code: `float(...)` cho qty/price/subtotal/vat | Nên tính bằng `Decimal` để khớp cột `Numeric(15,2)`. Chưa thấy lệch ở test hiện tại nhưng là rủi ro. |
| B5 | **High** | **Tạo Order xuyên tenant (POST IDOR).** `create_order` dùng `customer_repo.get_by_id` (không lọc company) và chỉ kiểm `customer.store_id == store_id`, KHÔNG kiểm `customer.company_id == current` | `dashboard_routes.py:510`; root: `repository.py:30 BaseRepository.get_by_id` (unscoped `query.get(id)`) | Test `test_create_order_rejects_cross_tenant_customer` (xfail): admin cty A POST store_id/customer_id của cty B → Order được tạo với `company_id=A` nhưng store/customer của B | Mong đợi: 403/từ chối. Thực tế: tạo được order lai tenant → hỏng cách ly dữ liệu & FK chéo. Sửa: kiểm `company_id` (hoặc dùng repo có scope) ở GĐ5. |
| B6 | Medium | **Contract tạo được KHÔNG cần quotation đã duyệt.** `quotation_id` optional, không kiểm `is_approved` | `dashboard_routes.py:816-919` | Test `test_create_contract_requires_approved_quotation` (xfail): order chưa có quotation nào vẫn tạo được contract | Mong đợi: chặn khi chưa có quotation approved (theo luồng nghiệp vụ). Thực tế: tạo tự do → phá state machine. |
| B7 | (root) | **`BaseRepository.get_by_id` không scope theo tenant** — nhiều route bù lại bằng kiểm `x.order.company_id` thủ công (không nhất quán); nơi quên kiểm → IDOR (xem B5) | `repository.py:30` | Đọc code: `return self.model.query.get(id)` | Đây là nguyên nhân gốc kiến trúc. Đề xuất GĐ3/GĐ5: thêm helper scoped (`get_by_id_for_company`) hoặc guard tập trung. |

## Tiến độ kiểm thử GĐ2
- [x] **Tính tiền/VAT:** đúng cho input dương (OK). Số âm KHÔNG chặn → **B2**.
- [x] **State machine:** approve (OK5) & payment sequencing (OK4) enforced; contract-cần-quotation-duyệt KHÔNG enforced → **B6**.
- [x] **IDOR:** GET views an toàn (OK1); POST create_order xuyên tenant → **B5** (root **B7**).
- [x] **Phân quyền vai trò:** company-admin endpoints chặn `user` đúng (OK3).
- [x] **Số hiệu chứng từ:** unique toàn cục → **B3** (quotation + contract + payment cùng mẫu).
- [ ] *(Residual — GĐ3/GĐ5)* Input fuzz (chuỗi dài, emoji, ngày tương lai, trùng code); cascade-delete cảnh báo UX; `advance_skipped` ghi luật (D1); IDOR POST cho cancel/sign/confirm (đa số có kiểm `x.order.company_id` thủ công — xác suất thấp, verify khi refactor B7).

## Kết luận GĐ2
Harness vững (17 test). Đã lập bug catalog với **7 bug** (1 High-security B5, 1 High-data B3, 1 root B7, còn lại Medium/Low) + xác nhận nhiều hành vi **đúng** (RBAC, payment sequencing, approve state, tenant GET). Đủ tín hiệu để sang **GĐ3 (hội đồng chuyên gia)** rồi **GĐ4 (backlog ưu tiên)**. Các bug đã có test (đỏ/xfail) làm lưới an toàn cho GĐ5.

## Ghi chú
- Mọi finding sẽ được xác minh bằng test (đỏ trước) trước khi kết luận, theo đúng quy trình.
- Bug sẽ được phân mức Critical/High/Medium/Low và đưa vào backlog GĐ4.
