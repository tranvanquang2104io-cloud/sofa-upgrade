# SofaFlow — Refactor & Product Enhancement (2026 Q3)

> Master plan + task ledger for the refactor/enhancement program.
> Branch: `refactor/sofa-upgrade-2026q3`. Baseline: v1.8.0, suite **107 passed / 1 xfailed**.
> Prior work in `AUDIT/` (security, CSRF, Alembic, per-tenant numbering) is **done and preserved** — this program builds on it, it does not redo it.

---

## 0. Baseline facts (measured, not assumed)

| Fact | Value | Source |
|---|---|---|
| Python LOC | 10,507 | `wc -l app/**/*.py` |
| Largest file | `routes/dashboard_routes.py` — 3,575 lines | god controller |
| Templates | 67 | `app/templates/` |
| Tests | 108 (107 pass, 1 xfail) | `pytest -q` |
| Migrations | 10 Alembic revisions | `migrations/versions/` |
| Tables | 30 models | `models/models.py` |

**Stale documentation found:** `CLAUDE.md` §6 states "CHƯA có Alembic" and "Không có CSRF" — both are now false (Alembic since `2ede8fb2868b`, CSRF site-wide via Flask-WTF). Corrected in Task D1.

---

## 1. The three-subsystem problem (root cause of the "incoherent product" feeling)

The app is not one product; it is three, under a shared `base.html`:

| Subsystem | Screens | Traits |
|---|---|---|
| **A. Sales documents** | orders, quotations, contracts, handover, payments | Good `t()` discipline; shared `parse_line_items`; but `recalcAll()` copy-pasted ×7 |
| **B. Master data** | materials, customers | Most complete CRUD; **the only screens with search + pagination** |
| **C. Procurement / production** | PR, PO, GR, production plans | Dict-driven status colors, shared form templates, **no pagination, no search, no `t()`, Vietnamese-only strings, no `table-responsive`** |

Any UI consistency work must converge these three on one set of patterns. This is the organising principle for Phase 1 UI tasks.

---

## 2. Findings register

Severity: **S1** = correctness/security, **S2** = data integrity, **S3** = maintainability, **S4** = UX.

| # | Sev | Finding | Evidence | Status |
|---|---|---|---|---|
| F1 | S1 | `get_next_code` computed the next document number across **all tenants** — `company_id` loaded then never applied | `dashboard_routes.py:2196` vs `:2248-2259` | ✅ **FIXED** (T1) |
| F2 | S1 | Same endpoint used `regexp_replace` (PostgreSQL-only) → 500 on any other backend, and untestable on the SQLite suite | same block | ✅ **FIXED** (T1) |
| F3 | S1 | `check_code` reported a number as taken when **another company** used it — leaks existence + wrongly blocks legitimate numbers | `dashboard_routes.py:2330` | ✅ **FIXED** (T2) |
| F4 | S3 | Money formula `subtotal + vat + shipping + another` re-derived in **7** route handlers, each hardcoding `or 8` | 7 sites | ✅ **FIXED** (T3) |
| F5 | S2 | `Company.vat_rate` exists in the schema but **no code ever read it** — the literal `8` shadowed it | `models.py:97` | ✅ **FIXED** (T3) |
| F6 | S2 | Contract created from a quotation with no form items stored the quotation's items but **`contract_value` 0.00** — proven by test | `dashboard_routes.py:1036` | ✅ **FIXED** (T4) |
| F22 | S2 | The create-contract route **bypasses `ContractService`** and writes via the repository, skipping the documented **single-active-contract invariant** → two active contracts on one order; downstream fee lookups then pick an arbitrary one | `dashboard_routes.py:979` vs `services.py:591-601` | ✅ **FIXED** (T4) |
| F7 | S2 | Handover `total_amount` is never recalculated from **accepted** quantities, so item-level rejections don't change the total | `models.py:508` | Open — T5 |
| F8 | S1 | **No workflow engine.** Sequencing split 3 ways: `LifecycleStatus` booleans, per-document `can_*` guards that can't see other documents, and hardcoded `if/raise` inside individual services | `models.py:264`, `services.py:745`, `:875-880` | Open — **Phase 2A** |
| F9 | S1 | `skip_advance_payment` is a **second, parallel** lifecycle-mutation path that bypasses `PaymentReportService` entirely | `dashboard_routes.py:1765-1799` | Open — Phase 2A |
| F10 | S2 | **P2P dead-ends at goods receipt.** No supplier invoice, no AP, no payment-to-supplier entity. `PurchaseOrder` has no `paid_amount`/payment status | no such model | Open — **Phase 2C** |
| F11 | S2 | `MaterialNorm.product_key` matches products by **lowercased name string**, not FK — no product master exists. Rename a product → norms silently stop matching | `models.py:1009` | Open — Phase 2C |
| F12 | S2 | `MaterialStock` has **no unique constraint** on `(material_id, store_id)`; code relies on `.first()` → duplicate rows would silently corrupt stock | `models.py:815-831` | Open — T6 |
| F13 | S2 | `PurchaseOrder.supplier_id` and `GoodsReceipt.po_id` are nullable → a PO with no supplier, a GR attached to nothing (bypasses the audit trail) | `models.py:1120`, `:1210` | Open — T7 |
| F14 | S3 | `BaseRepository.get_by_id` is unscoped `query.get(id)`; a scoped variant exists for `Customer` only. Tenant safety depends entirely on every caller remembering | `repository.py:31-33` vs `:159` | Open — T8 |
| F15 | S4 | `recalcAll()` copy-pasted across 7 templates; image-preview logic across 6; 3 separate line-editor implementations. `static/js/main.js` is 25 lines and effectively unused | templates | Open — T9 |
| F16 | S4 | Status badges rendered two different ways: inline `if/elif` chains (sales screens) vs a `colors.get()` dict from the view (procurement) | both | Open — T10 |
| F17 | S4 | No pagination on materials, PO, PR, GR, documents, stores lists; no search on orders, procurement, stores | templates | Open — T11 |
| F18 | S4 | No `table-responsive` on materials, PO, PR, GR, production lists → horizontal overflow on mobile with no scroll affordance | templates | Open — T12 |
| F19 | S4 | 264 template lines carry un-`t()`-wrapped Vietnamese; whole procurement/production modules bypass i18n | templates | Open — T13 |
| F20 | S4 | `payment/` (singular) and `payments/` (plural) template directories both exist for the same concept | dirs | Open — T14 |
| F21 | S4 | Missing screens: Orders has no edit; quotations/contracts/handover/payments have no list; GR has no create/edit form; stores/users have no view | inventory | Open — T15 (triage, not blanket CRUD) |

---

## 3. Decisions taken (owner-confirmed 2026-09-18)

| # | Decision | Rationale |
|---|---|---|
| **DA** | **Workflow = DB-backed rules table + a single `WorkflowService`** | Replaces scattered `if/raise`. Admin-editable, per-company, supports a future second customer without a deploy. |
| **DB** | **HĐNT + Đơn đặt hàng** (not phụ lục) | BLDS 2015 Đ.386+393: an accepted order **is** the contract for that transaction. Decisive constraint is **NĐ 123/2020 Đ.9** — invoices must be substantiated per delivery, which a bare HĐNT cannot do. Chain: HĐNT → đơn hàng → biên bản giao nhận → hóa đơn. |
| **DC** | **P2P: close the loop minimally** — supplier invoice + payment vs PO, with 3-way match (PO/GR/invoice) | Makes "Pay" real without importing a full AP ledger into a module not yet used in production. |

### Research basis for DB (HỢP ĐỒNG NGUYÊN TẮC)

- A HĐNT is **not a named contract type** in Vietnamese law; it is a framework agreement built on freedom of contract (BLDS 2015 Đ.385, 398, 401-403). It binds the *principles of cooperation*, not any single delivery — it deliberately omits quantity, spec, price and delivery date.
- **Phụ lục** (Đ.403) is for *detailing or amending a term of one contract* — correct for a price-list refresh, strained as a repeating per-order artifact.
- **Đơn đặt hàng accepted by the seller** is both the most common VN B2B practice and legally self-sufficient (offer + acceptance = contract), citing the HĐNT number/date for the general terms.
- **Tax is the binding constraint**: NĐ 123/2020 Đ.9 ties invoice timing to a specific delivery and requires an invoice per delivery for repeated/partial shipments. Issuing a hóa đơn GTGT against only "theo HĐNT số X" risks rejection for lacking chứng từ substantiating quantity/price/date.

---

## 4. Task ledger

One task = one coherent unit, each ending green. **Phase 1 first — no Phase 2 feature lands on an unstable base.**

### Phase 1 — Refactor the existing app

| T | Task | Files | Test | Status |
|---|---|---|---|---|
| T1 | Scope `get_next_code` to the company + make it backend-portable | `dashboard_routes.py` | `test_next_code_tenant_scope.py` (3) | ✅ Done |
| T2 | Scope `check_code` to the company | `dashboard_routes.py` | same file (2) | ✅ Done |
| T3 | Extract `services/money.py`; wire all 7 call sites; honour `Company.vat_rate` | `money.py`, `dashboard_routes.py`, `auth_utils.py` | `test_money.py` (12) | ✅ Done |
| T4 | Re-derive totals from copied items + restore single-active-contract invariant (F6, F22) | `dashboard_routes.py` | `test_contract_integrity.py` (2) | ✅ Done |
| T5 | Recalculate handover total from **accepted** qty (F7) | `services.py` | new | Next |
| T6 | Unique constraint on `MaterialStock(material_id, store_id)` + migration (F12) | model + migration | new | |
| T7 | Tighten nullable FKs: PO→supplier, GR→PO (F13) | model + migration | new | |
| T8 | Make tenant-scoped lookup the default in `BaseRepository` (F14) | `repository.py` | extend isolation tests | |
| T9 | Extract shared `static/js/sofa-lineitems.js` (recalc + line rows + image preview); delete 7 copies (F15) | templates + js | render tests | |
| T10 | One `_status_badge.html` macro + one status→colour map (F16) | templates | render tests | |
| T11 | Pagination + search on the 6 lists that lack them (F17) | templates + routes | list tests | |
| T12 | `table-responsive` on the 5 overflowing tables (F18) | templates | — | |
| T13 | i18n pass on procurement/production (F19) | templates + `i18n.py` | — | |
| T14 | Merge `payment/` into `payments/` (F20) | templates | render tests | |
| T15 | Triage missing screens (F21) — add only what the entity's lifecycle justifies | various | per screen | |
| D1 | Refresh `CLAUDE.md` (Alembic + CSRF now exist) | `CLAUDE.md` | — | |

### Phase 2 — Product enhancements

| T | Task | Depends on |
|---|---|---|
| **2A** | **Workflow engine** (DA): `workflow_rules` table (per company: doc type, prerequisite, REQUIRED/OPTIONAL/WAIVABLE), `WorkflowService.can(order, action)`, migrate every scattered guard onto it, fold `skip_advance_payment` into an audited waiver, admin config screen | T8 |
| **2B** | **Data standardization** (4.1): `standardization_rules` per company/entity/field (UPPERCASE, Title Case, sentence case, trim, collapse spaces, phone/tax format); applied at the service boundary so every write path is covered; auto-apply vs confirm-on-apply flag | T3 |
| **2C** | **HĐNT + Đơn đặt hàng** (DB): `master_agreements` table (validity, price list, payment terms, penalty cap ≤8% per LTM 2005 Đ.301, dispute clause, renewal), order→agreement reference, covered orders emit an Đơn đặt hàng citing the HĐNT instead of a full contract, DOCX template | 2A |
| **2D** | **P2P close-the-loop** (DC): `supplier_invoices` + `supplier_payments`, 3-way match PO/GR/invoice, PO payment status, plus the F11/F13 integrity fixes | T6, T7 |
| **2E** | **SME gap analysis** (4.5): evidence-based proposal, no speculative features |

---

## 5. Working rules for this program

1. **Understand before changing** — every task cites file:line evidence in this ledger before code is touched.
2. **Each task ends green** — full suite run, no new failures, committed separately.
3. **Characterization tests first** where behaviour is being moved rather than changed (T3 did this: 12 tests pin the arithmetic *before* the 7 call sites were rewritten).
4. **Preserve the product** — no feature removed without a stated reason.
5. **Config over hardcoding**, but only where a real second case exists or is imminent.
6. Schema changes are **reversible Alembic migrations**, Postgres-compatible, verified round-trip on SQLite.
