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
7. [Docker — Chạy đa nền tảng](#7-docker--chạy-đa-nền-tảng-windows--linux--mac)
8. [Các lệnh vận hành thường dùng](#8-các-lệnh-vận-hành-thường-dùng)

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

### 3.1 Dùng script tự động (khuyến nghị)

`scripts/deploy.ps1` tự động thực hiện toàn bộ pipeline:
**Backup DB → Cập nhật version → Git commit + tag → Push GitHub → Docker rebuild → Health check**

```powershell
# Đảm bảo branch main đã merge đầy đủ code muốn release
git checkout main
git pull origin main

# Chạy deploy — nhập version theo SemVer
.\scripts\deploy.ps1 -Version "1.2.0"

# Tuỳ chọn thêm:
.\scripts\deploy.ps1 -Version "1.2.0" -Message "Thêm tính năng phân tích kho"
.\scripts\deploy.ps1 -Version "1.2.0" -DryRun     # xem trước, không làm gì
.\scripts\deploy.ps1 -Version "1.2.0" -NoPush     # chỉ commit local, không push
.\scripts\deploy.ps1 -Version "1.2.0" -NoDocker   # bỏ qua Docker rebuild
```

Script sẽ tự hỏi nếu thiếu thông tin (release message) — chỉ cần trả lời tương tác.

**Luồng script thực hiện:**
```
[0] Kiểm tra git status + version hiện tại
[1] Backup database → backups/before_v1.2.0_YYYYMMDD.sql
[2] Hỏi mô tả release (nếu không truyền -Message)
[3] Cập nhật VERSION file + CHANGELOG.md
[4] git add -A  →  git commit  →  git tag v1.2.0
[5] git push origin main --tags
[6] docker compose up --build -d
[7] Health check http://localhost:5000/auth/login
```

### 3.2 Thủ công (fallback)

```powershell
git checkout main && git pull origin main
# Sửa file VERSION thủ công, cập nhật CHANGELOG.md
git add -A
git commit -m "release: v1.2.0"
git tag v1.2.0
git push origin main --tags
docker compose up --build -d
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

### 5.1 Dùng script tự động (khuyến nghị)

`scripts/rollback.ps1` tự động thực hiện:
**Backup DB hiện tại (an toàn) → Khôi phục code về version cũ → Docker rebuild → Health check**

```powershell
# Cách 1: menu tương tác — hiện danh sách tất cả version, chọn số thứ tự
.\scripts\rollback.ps1

# Cách 2: chỉ định version thẳng
.\scripts\rollback.ps1 -ToVersion "1.0.0"

# Cách 3: rollback code + khôi phục database backup
.\scripts\rollback.ps1 -ToVersion "1.0.0" -RestoreDB

# Preview — xem các bước mà không thực sự thay đổi gì
.\scripts\rollback.ps1 -DryRun
```

**Luồng script thực hiện:**
```
[0] Hiện danh sách git tags → chọn version muốn quay về
[1] Xác nhận (phải gõ 'yes' chính xác)
[2] Backup DB hiện tại → backups/pre_rollback_vCURRENT_to_vOLD_YYYYMMDD.sql
[3] git checkout <tag> -- .  (khôi phục tất cả files về version cũ)
    git commit -m "rollback: restore code to vX.Y.Z"
[4] (--RestoreDB) chọn file backup SQL → restore DB
[5] docker compose up --build -d
[6] Health check
```

> **Lưu ý về database:** Khi rollback code, database giữ nguyên mặc định.  
> Điều này **an toàn** khi upgrade chỉ **thêm** tables mới (như Material module).  
> Chỉ dùng `--RestoreDB` khi upgrade **xóa hoặc đổi cấu trúc** tables cũ.

### 5.2 Thủ công (fallback khi script không chạy được)

```powershell
# Backup DB trước
docker compose exec -T db pg_dump -U sofa_user sofa_flow_dev > backups/manual_backup.sql

# Khôi phục code
git fetch --tags
git checkout v1.0.0 -- .
git add -A
git commit -m "rollback: restore code to v1.0.0"

# Rebuild
docker compose up --build -d
```

### 5.3 Sau khi rollback thành công

```powershell
# Xác nhận app đang chạy đúng version
Invoke-WebRequest http://localhost:5000 | Select-String 'v[0-9]\.[0-9]\.[0-9]'

# Xem logs nếu cần debug
docker compose logs app --tail=50
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

## 7. Docker — Chạy đa nền tảng (Windows / Linux / Mac)

Docker đóng gói toàn bộ app + Python + dependencies vào một **container** — chạy giống hệt nhau trên mọi hệ điều hành, không cần cài Python hay PostgreSQL thủ công.

### So sánh

| | Không Docker | Có Docker |
|---|---|---|
| Windows local | ✅ | ✅ |
| Deploy lên Ubuntu | ⚠️ cài lại tất cả | ✅ 1 lệnh |
| Dev = Production | ❌ khác OS, khác lib | ✅ giống hệt |
| Developer mới onboard | ❌ setup phức tạp | ✅ `docker compose up` |

### Yêu cầu

- **Windows/Mac**: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **Ubuntu/Linux**: Docker Engine + Compose plugin

```bash
# Cài Docker trên Ubuntu (1 lần duy nhất)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker
```

### 7.1 Chạy local bằng Docker (thay thế `python wsgi.py`)

```bash
# Lần đầu — build image và khởi động
docker compose up --build

# Các lần sau
docker compose up

# Chạy nền
docker compose up -d

# Truy cập: http://localhost:5000
# Code thay đổi → Flask tự reload (hot-reload được bật)
```

> **Không cần cài Python hay PostgreSQL** trên máy — Docker lo hết.

### 7.2 Deploy lên Ubuntu server bằng Docker

```bash
# Trên server Ubuntu
git clone https://github.com/tranquanguit/sofa-flow.git
cd sofa-flow
git checkout v1.0.0      # luôn checkout tag cụ thể, không dùng HEAD

# Tạo file secret production
cp .env.prod.example .env.prod
nano .env.prod           # điền SECRET_KEY, POSTGRES_PASSWORD, APP_VERSION

# Build và chạy toàn bộ stack: Nginx + Gunicorn + PostgreSQL
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# Kiểm tra
docker compose -f docker-compose.prod.yml ps
curl -s -o /dev/null -w "%{http_code}" http://localhost
# → 200
```

### 7.3 Update phiên bản mới lên server

```bash
git fetch --tags
git checkout v1.0.1

# Chỉ rebuild app (PostgreSQL không bị ảnh hưởng)
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build app
```

### 7.4 Backup & Restore database trong Docker

```bash
# Backup
docker compose -f docker-compose.prod.yml exec db \
    pg_dump -U sofa_user sofa_flow | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore
gunzip -c backup_20260310.sql.gz | \
    docker compose -f docker-compose.prod.yml exec -T db \
    psql -U sofa_user sofa_flow
```

### 7.5 Các lệnh Docker hay dùng

| Mục đích | Lệnh |
|---|---|
| Xem log app | `docker compose logs -f app` |
| Xem log nginx | `docker compose -f docker-compose.prod.yml logs -f nginx` |
| Vào shell container | `docker compose exec app bash` |
| Vào psql | `docker compose exec db psql -U sofa_user sofa_flow` |
| Xem CPU/RAM mỗi container | `docker stats` |
| Dừng toàn bộ | `docker compose down` |
| Dừng + xóa toàn bộ data | `docker compose down -v` |

---

## 8. Các lệnh vận hành thường dùng

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
| **Deploy version mới** | `.\scripts\deploy.ps1 -Version "1.2.0"` |
| Deploy (preview, không làm gì) | `.\scripts\deploy.ps1 -Version "1.2.0" -DryRun` |
| **Rollback về version cũ** | `.\scripts\rollback.ps1` (menu tương tác) |
| Rollback thẳng về version cụ thể | `.\scripts\rollback.ps1 -ToVersion "1.0.0"` |
| Rollback + khôi phục DB | `.\scripts\rollback.ps1 -ToVersion "1.0.0" -RestoreDB` |
| Xem toàn bộ git tags | `git tag -l` |
| Xem log commit | `git log --oneline -10` |
| Xem backups DB | `Get-ChildItem backups\` |

### Database

```bash
# Đếm tổng số đơn hàng
psql -U sofa_user -d sofa_flow -c "SELECT COUNT(*) FROM orders WHERE is_active = true;"

# Đếm user theo công ty
psql -U sofa_user -d sofa_flow -c "SELECT company_id, COUNT(*) FROM users GROUP BY company_id;"

# Kiểm tra kết nối
psql -U sofa_user -d sofa_flow -c "\conninfo"
```
