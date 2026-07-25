# GIAI ĐOẠN 0 — Baseline & Thiết lập an toàn

**Ngày:** 2026-07-25 · **Nhánh:** `refactor/full-audit` (tách từ `main` @ `22fb9eb`)

---

## 1. Tech stack (đã dò)

| Layer | Công nghệ | Ghi chú |
|-------|-----------|---------|
| Backend | Python 3.11, Flask 2.3.3, Werkzeug 2.3.7 | App factory `app/__init__.py::create_app` |
| ORM | SQLAlchemy 2.0 + Flask-SQLAlchemy 3.1 | `app/config/database.py` |
| DB (prod/dev) | PostgreSQL 16 (Docker, port host 5433) | UUID PK, JSON columns, Numeric tiền |
| DB (test) | SQLite in-memory (`TestingConfig`) | ✅ `create_all()` dựng 18 bảng OK |
| Frontend | Jinja2 + Bootstrap 5.3 + Vanilla JS | Không build step |
| Documents | python-docx, docxtpl, reportlab (PDF) | Template DOCX theo công ty |
| WSGI | Gunicorn (prod), `wsgi.py` dev | |
| Container | Docker + docker-compose (dev + prod) | Adminer UI ở :8080 |

**Không có:** test framework, linter/formatter config, Alembic/migration tool, CI.

## 2. Lệnh chạy / cài (đã xác minh)

```bash
# Môi trường ảo đã tồn tại tại ./venv (Python 3.11)
venv/Scripts/python.exe -c "from app import create_app; print('ok')"   # import OK

# Chạy full stack qua Docker (KHI có Docker):
docker compose up            # app :5000, adminer :8080, db :5433

# Chạy trực tiếp (cần DATABASE_URL trỏ tới Postgres đang chạy):
venv/Scripts/python.exe wsgi.py
```

> ⚠️ Trên máy audit hiện tại **Docker không chạy** và **không có Postgres cục bộ**. Vì vậy harness test (GĐ2) sẽ chạy trên **SQLite** qua `create_app('testing')`.

## 3. Trạng thái test hiện có

**Không có test tự động nào** (`find` không thấy `test_*.py` ngoài venv). Mốc baseline: **0 test**. Đây là rủi ro lớn cho refactor → GĐ2 sẽ dựng lưới an toàn.

## 4. Database & backup

- Dev DB nằm trong Docker volume `postgres_dev_data` — **hiện không chạy**, không có dữ liệu sống cần backup trên máy này.
- **Production DB:** cần credential của chủ dự án; agent **không** truy cập được và **không** đụng vào. Mọi thay đổi schema sẽ đi kèm **migration có rollback** để chủ dự án tự áp dụng sau khi backup prod.
- Dữ liệu mẫu tái tạo được bằng `scripts/create_sample_data.py` + `scripts/create_master_admin.py`.

## 5. Cấu trúc thư mục (rút gọn)

```
app/
  config/        config.py (Config/Dev/Testing/Prod), database.py (db init)
  models/        models.py — 18 ORM models (752 dòng)
  repositories/  repository.py — data access (577 dòng)
  services/      services.py — business logic (1548 dòng)
  routes/        auth_routes.py (115) · admin_routes.py (256) · dashboard_routes.py (2838 ⚠️)
  utils/         auth_utils.py · i18n.py (668) · template_engine.py (719)
  templates/     ~60 Jinja2 templates
  static/        css/style.css · js/main.js
  uploads/       templates/ (DOCX) · documents/ (output) · items/
scripts/         seed / migration tay / deploy.ps1 / rollback.ps1
```

## 6. Baseline hành vi (mô tả)

Ứng dụng multi-tenant: `MasterAdmin` tạo `Company` → mỗi công ty có `Store`, `User` (3 vai trò). Nghiệp vụ chính = vòng đời đơn hàng: **Customer → Order → Quotation → Contract → HandoverRecord → PaymentReport**, mỗi bước sinh tài liệu DOCX/PDF. `LifecycleStatus` theo dõi tiến độ (quotation_created → … → completed). Có module **Vật tư** (Material + Category/Unit/Supplier/Stock). UI song ngữ EN/VI (`app/utils/i18n.py`, mặc định `vi`).

## 7. Quan sát sơ bộ (chưa chính thức — sẽ xác minh & phân loại ở GĐ2/GĐ3)

| # | Quan sát | Loại | Mức (dự kiến) |
|---|----------|------|---------------|
| P1 | Không có CSRF protection cho form POST (Flask-WTF không có trong deps) | Security | High |
| P2 | `quotation_number` / `contract_number` / `report_number` unique **toàn cục** thay vì theo company | DB / Multi-tenant | High |
| P3 | `dashboard_routes.py` 2838 dòng — god controller, logic nghiệp vụ lẫn trong route | Architecture | High |
| P4 | Không có migration tool (Alembic); schema đổi bằng script tay | DB / Reliability | Medium |
| P5 | Line-items lưu JSON lồng (`items`) — dữ liệu tiền denormalized, khó ràng buộc toàn vẹn | DB | Medium |
| P6 | `SECRET_KEY` default hardcode; prod phải override qua env | Security | Medium |
| P7 | Chưa rõ kiểm soát truy cập chéo store/tenant (IDOR) khi mở tài nguyên theo id | Security | High (cần test) |
| P8 | Không có test → không lưới an toàn | Reliability | High |

## 8. Definition of Done (nhắc lại — mục tiêu cuối)

Hết bug Critical/High · E2E các luồng chính chạy đúng gồm edge case · không lỗ hổng OWASP nghiêm trọng · schema chuẩn hóa + ràng buộc toàn vẹn + tiền decimal + index query nóng · UX phản hồi rõ, chống lỗi, mobile OK, accessibility cơ bản · backend phân tầng, business logic tách khỏi controller · có test tự động xanh · README + FINAL-REPORT đầy đủ; commit sạch, revert được.
