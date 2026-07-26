# Feature 2 — Kế hoạch sản xuất (Production Planning) — SPEC ĐỂ BUILD

> Chủ dự án đã **duyệt mô hình** (2026-07-26). Approach = **Hybrid định mức**;
> scope đợt 1 = **Kế hoạch SX + trừ kho + cảnh báo tồn** (PO để sau).
> Build trên nhánh `refactor/full-audit`, mỗi bước PLAN→TEST→FIX→VERIFY(pytest xanh)→COMMIT→LOG. Sau đó deploy như quy trình đã làm (build image 1.4.0 → migrate prod có backup → restart app).

## 1. Models mới (app/models/models.py, dùng GUID + before_insert nếu cần company_id)
- **ProductionPlan** — 1 KH / order (gắn contract): `id, company_id(FK, auto từ order qua before_insert), order_id(FK, unique — 1 plan/order), contract_id(FK, nullable), plan_number(unique per company), status ∈ {draft, in_progress, completed, canceled}, notes, created_at, updated_at`. Method `can_edit/can_confirm/can_complete`.
- **ProductionPlanItem** — `id, plan_id(FK), source_name (copy từ contract item), quantity(Numeric), unit(str), notes`. (Mirror item hợp đồng để đội SX biết làm gì.)
- **ProductionMaterialLine** — vật tư cần: `id, plan_id(FK), plan_item_id(FK nullable → cho phép "overall"), material_id(FK), quantity_required(Numeric), quantity_issued(Numeric default 0), unit(str), notes`.
- **MaterialNorm** (định mức tái sử dụng) — `id, company_id(FK), product_key(str, chuẩn hóa = lower/strip tên SP), material_id(FK), quantity_per_unit(Numeric), unit(str)`, unique `(company_id, product_key, material_id)`.
- Cân nhắc thêm cờ `production_plan_created(_at)` vào LifecycleStatus (không bắt buộc — có thể suy từ quan hệ order.production_plan).

## 2. Migration (Alembic, dialect-aware, reversible, Postgres-compat)
- Autogenerate sau khi thêm models → 4 bảng mới + index (company_id, order_id...). Test round-trip trên SQLite. Không backfill (bảng mới).

## 3. Services (app/services/services.py) — `ProductionPlanService`
- `create_from_contract(contract)` → tạo ProductionPlan(status=draft) + ProductionPlanItem copy từ contract.items. **Gợi ý vật tư**: với mỗi item, tra MaterialNorm theo product_key(item.name) → sinh ProductionMaterialLine (qty_required = norm.quantity_per_unit × item.quantity). Idempotent (không tạo trùng nếu order đã có plan).
- `add/update/remove_material_line(...)`, `issue_materials(plan)` → với mỗi line: trừ `MaterialStock.current_quantity` theo store của order (giao dịch an toàn, không cho âm → raise nếu thiếu, hoặc cho phép + cảnh báo — CHỌN: chặn nếu tồn < cần, trả danh sách thiếu). Set quantity_issued.
- `save_as_norm(plan_item)` → upsert MaterialNorm từ các material line của 1 item (product_key = tên item) để tái sử dụng.
- `low_stock_materials(company_id)` → list material có `is_low_stock` (đã có property).

## 4. Auto-create hook
- Trong `ContractService.mark_signed` (services.py ~610) **và/hoặc** khi approve — sau khi set `lifecycle.contract_signed=True`, gọi `ProductionPlanService().create_from_contract(contract)` (bọc try/except, không chặn luồng ký nếu lỗi tạo plan → log). Quyết định: tạo khi **ký** (mark_signed). Ghi DECISIONS.

## 5. Routes (blueprint dashboard) + repo
- `/orders/<order_id>/production-plan` (GET) xem/sửa plan; `/production-plan/<plan_id>/materials` (POST add/edit line); `/production-plan/<plan_id>/issue` (POST cấp phát → trừ kho); `/production-plan/<plan_id>/save-norm/<item_id>` (POST lưu định mức); `/materials/low-stock` (GET cảnh báo). RBAC: user/store_admin của store đó. Tenant-scope theo company_id. CSRF token trong form.
- ProductionPlanRepository + MaterialNormRepository (repositories/repository.py).

## 6. UI (templates + i18n EN/VI)
- `production/plan.html` (xem plan + items + material lines, nút cấp phát, badge tồn thấp), link từ `orders/view.html` (mục vòng đời — hiện khi contract signed). `materials/low_stock.html` hoặc badge ở materials list. Nav link. Dùng partial `_pagination.html` nếu list dài.
- Hiển thị cảnh báo khi cấp phát vượt tồn.

## 7. Tests (tests/) — pytest trên SQLite
- `test_production_plan.py`: (a) contract signed → tự tạo plan + items (E2E qua route sign); (b) gợi ý vật tư từ MaterialNorm; (c) issue_materials trừ đúng MaterialStock + chặn khi thiếu; (d) save_as_norm rồi tạo plan mới → tự gợi ý; (e) low_stock_materials; (f) tenant isolation (không thấy plan/norm cty khác); (g) RBAC.
- Cập nhật E2E `test_e2e_orders.py`: sau sign contract → assert order có production_plan.

## 8. Deploy (sau khi xanh + push)
- Bump VERSION → 1.4.0. tar-sync code lên server (`git` server không auth GitHub — dùng tar-over-ssh như lần trước, exclude .env.prod + app/uploads). Build image `sofa-flow:1.4.0`. **Backup DB** → chạy migration mới trên prod (temp container, `--entrypoint sh`, `python -m alembic upgrade head`; đã có alembic_version=head hiện tại). Recreate app. Verify.
- Server: 103.57.220.46, key `Q:/SERVERS/iNet/CS-Linux-...pem` (copy ra scratchpad chmod 600). Caddy đã route sofangochan → sofa-flow-prod-app-1:5000 (không cần đụng). NGOCHAN company_id=`59c96399-838f-4ae6-a07c-6d13baccdc1c`.

## Hàng đợi khác (sau Feature 2)
- Đổi login email+password (thay/song song — hỏi lại).
- Bổ sung field DB template (Số ĐKKD, warranty…) — migration nhỏ.
