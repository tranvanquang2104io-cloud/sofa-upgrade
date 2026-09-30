# QAS — Quy trình chạy tự động mỗi giờ (dành cho Claude Code)

Thư mục làm việc: `Q:\Projects\sofa-upgrade` (KHÔNG dùng `Q:\Projects\sofa-flow` — đó là prod).

1. **Deploy**: `bash scripts/deploy_qas.sh`
   - exit 10 = `main` không có commit mới → BỎ QUA bước test đầy đủ; chỉ kiểm tra
     `curl -o /dev/null -w "%{http_code}" https://qas-sofaflow.quangtv.com/auth/login` và ghi 1 dòng SKIP.
   - exit 0 = deploy xong → chạy tiếp bước 2.
   - exit khác = deploy lỗi → ghi FAIL kèm log, dừng lại.
2. **Test bằng trình duyệt** theo `AUDIT/QAS_TEST_PLAN.md`, dùng công cụ `mcp__Claude_Browser__*`
   trên https://qas-sofaflow.quangtv.com. Dữ liệu tạo ra đặt tiền tố `AUTOTEST`.
   Gặp lỗi ở một bước thì ghi nhận rồi đi tiếp bước khác, đừng dừng cả lượt.
3. **Ghi log**: chèn mục mới NGAY SAU dòng `<!-- LOG-START -->` trong `AUDIT/QAS_ISSUES.md`
   (mục mới nhất nằm trên cùng), theo mẫu:

   ```
   ## 2026-09-18 03:00 — commit abc1234 — 12/15 PASS, 2 FAIL, 1 SKIP
   - PASS 1-6, 10-12, 15
   - **FAIL — B7 Sinh PDF báo giá**: mô tả lỗi, thông báo lỗi, ảnh/log nếu có, cách lặp lại.
   - **BLOCKED — B8**: phụ thuộc B7.
   ```
   Mô tả lỗi viết đủ để lập trình viên tái hiện: URL, tài khoản, thao tác, kết quả thực tế.
4. **Commit & push**: `git add AUDIT/QAS_ISSUES.md && git commit -m "chore(qas): ket qua test tu dong <ngày giờ>" && git push origin main`
   Nếu push bị từ chối do có commit mới: `git pull --rebase origin main` rồi push lại.
5. **Dọn dẹp**: xoá/huỷ dữ liệu `AUTOTEST` vừa tạo trên QAS.

Nguyên tắc: KHÔNG đụng vào production (server dir `/opt/apps/sofa-flow`, container `sofa-flow-prod-*`,
repo `sofa-flow`, domain sofangochan.mochacosmetic.com).
