# GIAI ĐOẠN 2 — Bug Catalog (QA Lead)

**Persona:** QA Lead cố tình phá sản phẩm. **Trạng thái:** đang chạy (v1, 2026-07-25).
Harness: `pytest` trên SQLite (xem `tests/`). Chạy: `venv/Scripts/python.exe -m pytest`.

**Test hiện có:** 13 test (11 PASS, 2 xfail có chủ đích): `test_smoke.py` ×5, `test_tenant_isolation.py` ×4, `test_quotation_money.py` ×4 (2 xfail = B2, B3).

---

## Đã xác minh — an toàn (không phải bug)
| Mã | Vùng | Kết quả kiểm thử |
|----|------|------------------|
| OK1 | Tenant isolation (GET views) | `GET /customers/<id>` và `/orders/<id>` với id của **công ty khác** → **302 về trang list** (không lộ dữ liệu). ID không tồn tại cũng 302 giống hệt → không phân biệt được sự tồn tại (tốt, chống enumeration). ⇒ **P7 IDOR không dính** ở các GET view này. |
| OK2 | Auth guard | Truy cập `/` khi chưa đăng nhập → 302 về `/auth/login`. Sai mật khẩu → vẫn chưa đăng nhập. |

## Bug đã tìm được
| Mã | Mức | Mô tả | Vị trí | Tái hiện | Mong đợi vs Thực tế |
|----|-----|-------|--------|----------|---------------------|
| B1 | Low | Route `/api/quotations/<quotation_id>` được đăng ký **2 lần** (decorator trùng) | `app/routes/dashboard_routes.py:2000-2001` | Xem `app.url_map` → endpoint `dashboard.get_quotation_detail` xuất hiện 2 lần | Chỉ nên đăng ký 1 lần. Thực tế: 2 decorator `@route` giống hệt liên tiếp (copy-paste). Không crash nhưng là dead duplication → xóa 1 dòng. |
| B2 | Medium | **Số lượng/đơn giá âm không bị chặn** khi tạo/sửa chứng từ → subtotal/total âm | `dashboard_routes.py:605-620` (create_quotation), `707-723` (edit_quotation); mẫu lặp ở contract/handover/payment | Test `test_negative_quantity_is_rejected` (xfail): POST quotation với `item_quantity[]=-2` → quotation được tạo với subtotal âm | Mong đợi: từ chối hoặc chặn giá trị âm. Thực tế: chấp nhận, lưu subtotal/total âm. Cần validate `qty>=0`, `price>=0` tập trung. |
| B3 | **High** | **Số hiệu chứng từ unique TOÀN CỤC thay vì theo tenant** (xác nhận P2) — chặn ở cả model lẫn route | Model `models.py` (`unique=True`); route `dashboard_routes.py:591` (`filter_by(quotation_number=...)` không lọc company) | Test `test_same_quotation_number_allowed_across_tenants` (xfail): công ty A dùng `Q-DUP`, công ty B KHÔNG dùng lại được | Mong đợi: unique theo `(company_id, number)` → B dùng lại được. Thực tế: bị chặn toàn cục → rò rỉ/đụng độ giữa tenant. Sửa ở GĐ5 theo D1 (migration rollback được, tương thích Postgres). |
| B4 | Low | Tính tiền dùng `float` rồi lưu `Numeric` → rủi ro sai số/làm tròn với số lớn | `dashboard_routes.py` (mọi handler create/edit chứng từ) | Đọc code: `float(...)` cho qty/price/subtotal/vat | Nên tính bằng `Decimal` để khớp cột `Numeric(15,2)`. Chưa thấy lệch ở test hiện tại nhưng là rủi ro. |

## Đang chờ kiểm thử (các pass tiếp theo của GĐ2)
- [ ] Luồng tạo end-to-end: Order → Quotation → approve → Contract → sign → Handover → confirm → Payment(advance/final) → Order completed. (cần đọc shape POST của `dashboard_routes.py`)
- [ ] **Tính tiền/VAT:** subtotal + VAT + shipping_fee + another_fee = total; làm tròn; khớp giữa JSON `items` và cột tổng; số âm/0; số lượng âm.
- [ ] **State machine:** chặn bước nhảy sai (tạo Contract khi Quotation chưa duyệt; Payment `final` khi chưa handover). Dùng `can_*()` đúng chưa.
- [ ] **IDOR trên POST/state-changing:** cancel/confirm/sign/approve/edit với id công ty khác (đây là nơi IDOR hay dính, chưa test).
- [ ] **Phân quyền vai trò:** `user`/`store_admin` gọi endpoint company-admin (tạo store/user, settings) → phải 403.
- [ ] Input xấu: chuỗi rất dài, ký tự đặc biệt/emoji, Unicode tiếng Việt, ngày quá khứ/tương lai, trùng `customer_code`/`order_code`.
- [ ] Xóa thứ đang được tham chiếu / cascade delete cảnh báo.
- [ ] `advance_skipped`: suy luận & ghi luật (KHÔNG đổi logic — theo D1).

## Ghi chú
- Mọi finding sẽ được xác minh bằng test (đỏ trước) trước khi kết luận, theo đúng quy trình.
- Bug sẽ được phân mức Critical/High/Medium/Low và đưa vào backlog GĐ4.
