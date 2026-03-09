# SofaFlow — Runbook Vận Hành

Tài liệu này dành cho người **phát triển và vận hành** — bao gồm cách chạy local,
kiểm thử trước khi release, và quy trình deploy/rollback lên server production.

> Cài đặt server lần đầu → xem [DEPLOYMENT.md](DEPLOYMENT.md)  
> Quy tắc version, CHANGELOG, git tag → xem [CHANGELOG.md](CHANGELOG.md)

---

## Mục lục

1. [Chạy môi trường local](#1-chạy-môi-trường-local)
2. [Checklist kiểm thử trước release](#2-checklist-kiểm-thử-trước-release)
3. [Quy trình release](#3-quy-trình-release)
4. [Deploy lên server production](#4-deploy-lên-server-production)
5. [Rollback khi có sự cố](#5-rollback-khi-có-sự-cố)
6. [Kiểm tra sau deploy](#6-kiểm-tra-sau-deploy)
7. [Các lệnh vận hành thường dùng](#7-các-lệnh-vận-hành-thường-dùng)

---

## 1. Chạy môi trường local

### Yêu cầu
- Python 3.11+
- PostgreSQL 14+ đang chạy
- Git

### Lần đầu tiên

```powershell
# 1. Clone và tạo virtualenv
git clone https://github.com/tranquanguit/sofa-flow.git
cd sofa-flow
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Tạo database local
psql -U postgres -c "CREATE DATABASE sofa_flow_dev;"
psql -U postgres -c "CREATE USER sofa_user WITH PASSWORD 'sofa_password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE sofa_flow_dev TO sofa_user;"
psql -U postgres -d sofa_flow_dev -c "GRANT USAGE, CREATE ON SCHEMA public TO sofa_user;"

# 4. Tạo file .env (copy từ mẫu)
cp .env.example .env
# Mở .env, điền DATABASE_URL và SECRET_KEY

# 5. Khởi tạo schema
python -c "from app import create_app; from app.config.database import db; app = create_app('development'); app.app_context().push(); db.create_all(); print('DB tables created')"
```

### Chạy server dev

```powershell
.\venv\Scripts\Activate.ps1
python wsgi.py
# Truy cập: http://localhost:5000
```

### File .env.example

```ini
FLASK_ENV=development
FLASK_DEBUG=true
SECRET_KEY=dev-only-secret-key-change-in-prod
DATABASE_URL=postgresql+psycopg://sofa_user:sofa_password@localhost:5432/sofa_flow_dev
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
```

> **Không bao giờ commit file `.env` thật** — file này đã có trong `.gitignore`

---

## 2. Checklist kiểm thử trước release

Thực hiện toàn bộ các kiểm tra này **trên môi trường local** trước khi chạy `release.ps1`.

### 2.1 Xác thực & Phân quyền

- [ ] Đăng ký công ty mới → tạo được tài khoản `company_admin`
- [ ] Đăng nhập / đăng xuất hoạt động đúng
- [ ] `company_admin` tạo được `store_admin` và `user`
- [ ] `user` không thấy menu quản lý cửa hàng / người dùng
- [ ] Truy cập URL của công ty khác → bị chặn (403)

### 2.2 Vòng đời đơn hàng (Order Workflow)

Tạo 1 đơn test và đi qua toàn bộ các bước:

- [ ] Tạo khách hàng → tạo đơn hàng
- [ ] **Báo giá**: tạo → duyệt → kiểm tra lifecycle chuyển sang `quotation_approved`
- [ ] **Hợp đồng**: tạo từ báo giá → ký → kiểm tra lifecycle `contract_signed`
- [ ] **Tạm ứng (advance)**: tạo phiếu → xác nhận → lifecycle `advance_paid`
- [ ] **Bỏ qua tạm ứng**: hủy advance → dùng "Bỏ qua tạm ứng" → vẫn mở khóa bàn giao
- [ ] **Bàn giao**: tạo → xác nhận → lifecycle `handover_confirmed`
- [ ] **Thanh toán cuối**: tạo → xác nhận → lifecycle `final_payment_confirmed`
- [ ] **Hủy đơn**: đơn có thể hủy ở các bước phù hợp, không hủy được ở bước không cho phép

### 2.3 Tài liệu

- [ ] Xuất báo giá → tải file được (PDF hoặc DOCX)
- [ ] Xuất hợp đồng → tải file được
- [ ] Xuất biên bản bàn giao → tải file được
- [ ] Xuất phiếu thanh toán → tải file được
- [ ] Upload mẫu DOCX mới → xác nhận là mẫu active
- [ ] Xóa tài liệu đã tạo → file biến mất khỏi danh sách

### 2.4 Giao diện & Dữ liệu

- [ ] Số tiền hiển thị đúng định dạng VND (dấu phân cách hàng nghìn)
- [ ] Tổng cộng (Subtotal / VAT / Total) tính đúng trên mọi form
- [ ] Tạm ứng (advance_amount) đúng trên phiếu thanh toán cuối
- [ ] Mã báo giá/hợp đồng/phiếu trùng → hiển thị lỗi rõ ràng
- [ ] Footer hiển thị đúng version (ví dụ `v1.0.1`)

### 2.5 Kiểm tra nhanh bảo mật

- [ ] Truy cập `/uploads/items/../../../etc/passwd` → nhận 403
- [ ] Đăng nhập bằng sai mật khẩu 5 lần → vẫn hoạt động (không crash)
- [ ] `FLASK_DEBUG` không được bật trên production (kiểm tra: không thấy Werkzeug debugger page khi có lỗi 500)

---

## 3. Quy trình release

Sau khi toàn bộ checklist kiểm thử ở mục 2 đã pass:

```powershell
# Trên máy dev, đảm bảo branch main đã được merge đầy đủ
git checkout main
git pull origin main

# Bump version (chọn patch / minor / major)
.\scripts\release.ps1 -Bump patch        # bug fix: 1.0.0 → 1.0.1
.\scripts\release.ps1 -Bump minor        # tính năng mới: 1.0.1 → 1.1.0
.\scripts\release.ps1 -Bump major        # breaking change: 1.x → 2.0.0

# Mở CHANGELOG.md, điền nội dung thay đổi vào section [x.y.z] vừa tạo
# Sau đó amend commit để lưu nội dung CHANGELOG
git add CHANGELOG.md
git commit --amend --no-edit

# Push lên GitHub kèm tag
git push origin main --tags
```

---

## 4. Deploy lên server production

> Thực hiện sau khi đã push tag lên GitHub.

### 4.1 Kết nối server và backup trước

```bash
ssh sofaflow@your-server-ip

# Backup database trước khi deploy
/home/sofaflow/backup_db.sh
```

### 4.2 Pull code mới

```bash
cd /home/sofaflow/sofaflow
source venv/bin/activate

# Pull tag version cụ thể (an toàn hơn pull HEAD)
git fetch --tags
git checkout v1.0.1          # thay bằng version muốn deploy
```

### 4.3 Cập nhật dependencies (nếu requirements.txt thay đổi)

```bash
pip install -r requirements.txt
```

### 4.4 Chạy database migration (nếu có schema mới)

Mỗi khi có thay đổi schema, tạo script migration trong `scripts/` và ghi rõ trong CHANGELOG.
Chạy script tương ứng:

```bash
# Ví dụ:
python scripts/migrate_xxx.py
```

> **Không dùng** `db.create_all()` trên production — chỉ dùng ALTER TABLE có kiểm soát.

### 4.5 Restart ứng dụng

```bash
sudo supervisorctl restart sofaflow
sudo supervisorctl status sofaflow    # phải thấy RUNNING
```

### 4.6 Kiểm tra nhanh

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/auth/login
# Phải trả về: 200
```

---

## 5. Rollback khi có sự cố

### 5.1 Rollback code

```bash
cd /home/sofaflow/sofaflow
git fetch --tags

# Quay về tag trước đó, ví dụ v1.0.0
git checkout v1.0.0

pip install -r requirements.txt      # về đúng dependencies của version cũ
sudo supervisorctl restart sofaflow
```

### 5.2 Rollback database (nếu migration gây lỗi)

```bash
# Khôi phục từ backup gần nhất
ls -lth /home/sofaflow/backups/       # tìm file backup trước khi deploy

sudo -u postgres dropdb sofa_flow
sudo -u postgres createdb sofa_flow
sudo -u postgres psql sofa_flow -c "GRANT ALL ON SCHEMA public TO sofa_user;"

gunzip -c /home/sofaflow/backups/sofa_flow_YYYYMMDD_HHMMSS.sql.gz \
    | psql -U sofa_user sofa_flow

sudo supervisorctl restart sofaflow
```

---

## 6. Kiểm tra sau deploy

Sau mỗi lần deploy production, kiểm tra nhanh:

```bash
# 1. Kiểm tra app đang chạy
sudo supervisorctl status sofaflow

# 2. Kiểm tra không có lỗi 500 mới trong log
sudo tail -50 /var/log/sofaflow.log | grep -i "error\|exception\|traceback"

# 3. Kiểm tra Nginx
sudo tail -20 /var/log/nginx/sofaflow_error.log

# 4. Kiểm tra version đúng trên UI
curl -s https://your-domain.com | grep -o 'v[0-9]\+\.[0-9]\+\.[0-9]\+'
```

Nếu mọi thứ ổn, ghi nhận vào CHANGELOG. Nếu có vấn đề → thực hiện rollback ngay (mục 5).

---

## 7. Các lệnh vận hành thường dùng

### Server

| Mục đích | Lệnh |
|---|---|
| Xem trạng thái app | `sudo supervisorctl status sofaflow` |
| Restart app | `sudo supervisorctl restart sofaflow` |
| Xem log app realtime | `sudo tail -f /var/log/sofaflow.log` |
| Xem log Nginx | `sudo tail -f /var/log/nginx/sofaflow_error.log` |
| Test config Nginx | `sudo nginx -t` |
| Restart Nginx | `sudo systemctl restart nginx` |
| Backup DB thủ công | `/home/sofaflow/backup_db.sh` |
| Vào psql | `psql -U sofa_user -d sofa_flow` |

### Local (Windows PowerShell)

| Mục đích | Lệnh |
|---|---|
| Bật virtualenv | `.\venv\Scripts\Activate.ps1` |
| Chạy server dev | `python wsgi.py` |
| Preview release (không thay đổi) | `.\scripts\release.ps1 -Bump patch -DryRun` |
| Tạo release patch | `.\scripts\release.ps1 -Bump patch` |
| Xem toàn bộ git tags | `git tag -l` |
| Xem log commit | `git log --oneline -10` |

### Database

```bash
# Đếm tổng số đơn hàng
psql -U sofa_user -d sofa_flow -c "SELECT COUNT(*) FROM orders WHERE is_active = true;"

# Đếm user theo công ty
psql -U sofa_user -d sofa_flow -c "SELECT company_id, COUNT(*) FROM users GROUP BY company_id;"

# Kiểm tra kết nối
psql -U sofa_user -d sofa_flow -c "\conninfo"
```
