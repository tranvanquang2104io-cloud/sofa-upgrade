# CLAUDE.md — Hướng dẫn cho AI coding agent làm việc trên SofaFlow

> Đọc file này trước khi sửa code. Mục tiêu: giúp agent thay đổi đúng chỗ, đúng tầng, không phá multi-tenant và không làm hỏng luồng chứng từ.

## 1. SofaFlow là gì
SaaS multi-tenant quản lý vòng đời khách hàng + tự động sinh chứng từ (DOCX/PDF) cho cơ sở sửa chữa & sản xuất sofa. UI song ngữ EN/VI (mặc định `vi`). Version tại `VERSION`.

## 2. Tech stack
- **Backend:** Python 3.11, Flask 2.3, SQLAlchemy 2.0 (Flask-SQLAlchemy 3.1), Werkzeug auth.
- **DB:** PostgreSQL 16 (prod/dev, Docker, host port **5433**). Test: SQLite in-memory (`TestingConfig`).
- **Frontend:** Jinja2 + Bootstrap 5.3 + Vanilla JS (không có build step).
- **Docs:** python-docx / docxtpl / reportlab.
- **Chạy:** `wsgi.py` (dev) / Gunicorn (prod); Docker compose (`docker compose up` → app :5000, adminer :8080).

## 3. Kiến trúc & quy tắc phân tầng (QUAN TRỌNG)
```
routes/ (HTTP)  →  services/ (business logic)  →  repositories/ (truy vấn DB)  →  models/
utils/auth_utils.py  = session, phân quyền, nạp g.user & g.company_id
utils/template_engine.py = sinh tài liệu; utils/i18n.py = dịch EN/VI
```
**Nguyên tắc khi thêm/sửa tính năng:**
- Logic nghiệp vụ đặt ở `services/`, KHÔNG viết thẳng trong route. (`dashboard_routes.py` hiện đang vi phạm điều này — đừng bắt chước; nếu đụng vào, kéo logic ra service.)
- Truy vấn DB đi qua `repositories/` khi có thể.
- **Luôn filter theo tenant:** mọi query dữ liệu công ty PHẢI ràng theo `g.company_id` (và `store_id` nếu vai trò là store-scoped). Không bao giờ tra cứu tài nguyên chỉ bằng `id` mà không kiểm quyền sở hữu → tránh IDOR.

## 4. Mô hình dữ liệu (xem chi tiết `AUDIT/01-architecture.md`)
18 bảng, UUID PK. Trục chính: **Company → Store → User/Customer → Order → {Quotation → Contract → HandoverRecord → PaymentReport} → Document**, `LifecycleStatus` 1-1 với Order. Module Vật tư: Material + Category/Unit/Supplier/Stock.
- **Tiền:** dùng `Numeric` (decimal) — không dùng float.
- **Line-items:** lưu trong cột JSON `items` + cột tổng (subtotal/vat/total). Khi sửa items PHẢI tính lại tổng cho khớp.
- **Trạng thái chứng từ:** dùng các method `can_edit/can_approve/can_sign/can_confirm/can_cancel` trên model — tôn trọng chúng, đừng bỏ qua.

## 5. Chạy & test
```bash
# Import kiểm tra nhanh
venv/Scripts/python.exe -c "from app import create_app; print('ok')"

# Chạy test trên SQLite (không cần Postgres/Docker)
venv/Scripts/python.exe -c "import os; os.environ['FLASK_ENV']='testing'; from app import create_app; from app.config import db; a=create_app('testing'); [db.create_all() for _ in [0]] if a.app_context().push() else None"
# (Harness pytest chính thức đang được dựng ở nhánh refactor/full-audit — xem AUDIT/)

# Seed dữ liệu mẫu (cần DB thật đang chạy)
venv/Scripts/python.exe scripts/create_master_admin.py
venv/Scripts/python.exe scripts/create_sample_data.py
```

## 6. Quy ước & cạm bẫy
- **i18n:** chuỗi hiển thị cho người dùng nên đi qua `t(key)` (xem `app/utils/i18n.py`), thêm cả EN và VI.
- **Không CSRF (hiện tại):** app chưa có CSRF protection — nếu thêm form POST, phối hợp với công việc bảo mật đang làm ở nhánh audit (đừng tự thêm nửa vời).
- **Migration:** CHƯA có Alembic; thay đổi schema hiện làm bằng script tay trong `scripts/`. Mọi thay đổi schema PHẢI kèm cách rollback và backup dữ liệu.
- **Secrets:** không hardcode; đọc từ env. `.env` đã gitignore — không commit. `SECRET_KEY` prod phải set qua env.
- **Uploads:** file sinh ra nằm dưới `app/uploads/documents/` (đã gitignore) — đừng commit.
- **Windows/PowerShell:** dev trên Windows; dùng `venv/Scripts/python.exe`.

## 7. Git & quy trình
- Nhánh audit/refactor: `refactor/full-audit`. Commit nhỏ, Conventional Commits (`fix(order): ...`, `refactor(services): ...`), mỗi commit để app chạy được.
- Tài liệu audit sống trong `AUDIT/` (baseline, architecture, bug catalog, backlog, changelog, final report). Đọc `AUDIT/PROGRESS.md` để biết trạng thái hiện tại.

## 8. Definition of Done cho thay đổi
Có test bảo vệ vùng sửa · không regression luồng khác · tôn trọng tenant isolation & state machine chứng từ · tiền khớp giữa items và tổng · cập nhật i18n · commit sạch, message rõ.
