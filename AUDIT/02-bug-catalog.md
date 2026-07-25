# GIAI ĐOẠN 2 — Bug Catalog (QA Lead)

**Persona:** QA Lead cố tình phá sản phẩm. **Trạng thái:** đang chạy (v1, 2026-07-25).
Harness: `pytest` trên SQLite (xem `tests/`). Chạy: `venv/Scripts/python.exe -m pytest`.

**Test hiện có:** 9 test PASS (`test_smoke.py` ×5, `test_tenant_isolation.py` ×4).

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
