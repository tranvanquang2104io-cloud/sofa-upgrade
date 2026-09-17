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
| F7 | — | ~~Handover total ignores accepted quantities~~ — **NOT A DEFECT.** Verified: both the create and edit paths price each line as `accepted_qty * unit_price` | `dashboard_routes.py:1410`, `:1600` | ❌ Withdrawn |
| F8 | S1 | **No workflow engine.** Sequencing split 3 ways: `LifecycleStatus` booleans, per-document `can_*` guards that can't see other documents, and hardcoded `if/raise` inside individual services | `models.py:264`, `services.py:745`, `:875-880` | Open — **Phase 2A** |
| F9 | S1 | `skip_advance_payment` is a **second, parallel** lifecycle-mutation path that bypasses `PaymentReportService` entirely | `dashboard_routes.py:1765-1799` | Open — Phase 2A |
| F10 | S2 | **P2P dead-ends at goods receipt.** No supplier invoice, no AP, no payment-to-supplier entity | no such model | ✅ **FIXED** (2D) |
| F11 | S2 | `MaterialNorm.product_key` matches products by **lowercased name string**, not FK — no product master exists. Rename a product → norms silently stop matching | `models.py:1009` | Open — Phase 2C |
| F12 | S2 | ~~No unique constraint on MaterialStock~~ — **misdiagnosed.** The constraint EXISTS. The real gap: `store_id` is NULLable and SQL treats NULLs as DISTINCT, so it never covered **company-level** rows. Proven empirically: 2 duplicate main-warehouse rows accepted. `receive()` uses `.first()` → stock silently disagrees with itself | `models.py:832`, probe | ✅ **FIXED** (T6) — partial unique index + duplicate-merging migration |
| F13 | S2 | `PurchaseOrder.supplier_id` nullable → a PO could be SENT with no supplier (and could never be invoiced) | `models.py:1120` | ✅ **FIXED** (T7) — guarded at the `submit` transition rather than made NOT NULL, so drafting before choosing a supplier still works |
| F14 | S3 | `BaseRepository.get_by_id` is unscoped `query.get(id)`; a scoped variant exists for `Customer` only. Tenant safety depends entirely on every caller remembering | `repository.py:31-33` vs `:159` | Open — T8 |
| F15 | S4 | Copy-pasted front-end helpers. **Measured:** `fmtNum` ×7, `numberToWordsVi` ×4, `parseRawFee` ×4 — all byte-identical (the two `parseRawFee` 'variants' differed only in a parameter name) | measured | ✅ **FIXED** (T9) — 15 inline copies removed |
| F16 | S4 | Status badges rendered two different ways: inline `if/elif` chains (sales screens) vs a `colors.get()` dict from the view (procurement) | both | ✅ **FIXED** (T17) — one token map + macros |
| F17 | S4 | Procurement lists returned `.all()` — every PO/PR/GR ever created on one page, no search | `procurement_service.py:232`, `requisition_service.py:118` | ✅ **FIXED** (T11) for PO/PR/GR; materials/documents/stores still open |
| F18 | S4 | Tables with no `table-responsive` wrapper → horizontal overflow on phones. **Audit list was inaccurate** — `po_list`/`pr_list`/`gr_list`/`materials/list` already had it; `customers/list`, `customers/view`, `documents/list`, `dashboard/index`, `admin/admins`, 4× materials pages and `production/plan` did not (11 files, re-measured) | measured | ✅ **FIXED** (T12) + guard test |
| F19 | S4 | Procurement/production bypassed i18n entirely | templates | ✅ **Labels FIXED** (T13). ⬜ Remaining: `status_labels`/`action_labels` dicts passed from views, JS `confirm()` strings, and prose fragments split across inline tags — see T13-remainder |
| F20 | S4 | `payment/` (singular) and `payments/` (plural) template directories both exist for the same concept | dirs | Open — T14 |
| F23 | S4 | `skip_advance_payment` sets `lifecycle.advance_paid = True` when no money was received. **Scope corrected 2026-09-18:** money reports sum confirmed `PaymentReport` rows, NOT this flag, so financial figures were never wrong. The real defect is **display only** — the order timeline shows a green "advance paid ✓" for a skipped advance | `report_service.py:133-145` (correct), `orders/view.html:315`, `orders/list.html:46` | Open — T16 |
| F24 | S2 | **Unreachable status badges.** `orders/list.html` tested `advance_paid` before `handover_confirmed`; every delivered order also has `advance_paid`, so the "Delivered" and "Contract Signed" branches were dead code — an order showed "Advance Paid" from delivery until fully paid | `orders/list.html:44-53` | ✅ **FIXED** (T17) |
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

**T13-remainder (open):** three classes of Vietnamese string are still not
translated, and each needs a judgement rather than a mechanical wrap:
`status_labels`/`action_labels` dicts built in `production/plan.html` and in
view functions; JavaScript `confirm()` messages; and prose split across inline
tags, where translating a fragment like "và bấm" alone would be nonsense
because word order differs between the languages — those sentences must be
rewritten to hold a single `t()` call, which is a copy decision.


One task = one coherent unit, each ending green. **Phase 1 first — no Phase 2 feature lands on an unstable base.**

### Phase 1 — Refactor the existing app

| T | Task | Files | Test | Status |
|---|---|---|---|---|
| T1 | Scope `get_next_code` to the company + make it backend-portable | `dashboard_routes.py` | `test_next_code_tenant_scope.py` (3) | ✅ Done |
| T2 | Scope `check_code` to the company | `dashboard_routes.py` | same file (2) | ✅ Done |
| T3 | Extract `services/money.py`; wire all 7 call sites; honour `Company.vat_rate` | `money.py`, `dashboard_routes.py`, `auth_utils.py` | `test_money.py` (12) | ✅ Done |
| T4 | Re-derive totals from copied items + restore single-active-contract invariant (F6, F22) | `dashboard_routes.py` | `test_contract_integrity.py` (2) | ✅ Done |
| T5 | ~~Handover accepted-qty total~~ — withdrawn, verified already correct | — | — | ❌ N/A |
| T6 | Partial unique index for company-level stock + duplicate-merging migration `a1b2c3d4e5f6` (F12) | model + migration | `test_stock_uniqueness.py` (3) | ✅ Done |
| T7 | PO cannot be submitted without a supplier (F13) | `procurement_service.py` | same file (2) | ✅ Done |
| T8 | Make tenant-scoped lookup the default in `BaseRepository` (F14) | `repository.py` | extend isolation tests | |
| T9 | Extract `static/js/sofa-doc-utils.js` (fmtNum · parseRawFee · numberToWordsVi); remove 15 inline copies; load in `<head>` to kill the ordering hazard (F15). `recalcAll` deliberately NOT extracted — its body genuinely differs per document type | 8 templates + js | `test_ui_consistency.py` (20) | ✅ Done |
| T17 | Shared status vocabulary + UI macro library; orders list converted (F16, F24, F23-display) | `status_tokens.py`, `macros/ui.html`, `style.css` | `test_status_tokens.py` (29) | ✅ Done |
| T11 | Pagination + search on PO/PR/GR (F17): service-level `page`/`search`, shared `search_bar` macro, `_pagination.html`. Search on PO covers number **and supplier name**; verified still tenant-scoped | services + routes + templates | `test_procurement_lists.py` (8) | 🟡 PO/PR/GR done; materials/documents/stores remain |
| T12 | Responsive wrapper on the 11 tables actually missing it + lint test so no new screen can opt out (F18) | 11 templates | `test_ui_consistency.py` (7) | ✅ Done |
| T13 | i18n pass on procurement/production (F19): **53 keys added, 99 strings wrapped**; one sentence split across `<strong>`/`<em>` rewritten as a single key. Guard test scans every template for bare Vietnamese labels | 10 templates + `i18n.py` | `test_ui_consistency.py` (22) | ✅ Labels done |
| T14 | Merge `payment/` into `payments/` (F20) | templates | render tests | |
| T15 | Triage missing screens (F21) — add only what the entity's lifecycle justifies | various | per screen | |
| D1 | Refresh `CLAUDE.md` — CSRF/Alembic corrected, plus the new house rules (money module, status tokens, workflow engine, normalization chokepoint), real test commands, current data model and branch | `CLAUDE.md` | — | ✅ Done |

### Phase 2 — Product enhancements

| T | Task | Depends on |
|---|---|---|
| **2A** | **Workflow engine** (DA) — ✅ **engine + rules + waivers + migration + 11 tests DONE**; service guards migrated; `skip_advance_payment` now records an audited waiver. ✅ **admin screen DONE** (`/settings/workflow` — relax/waive/disable per rule). ⬜ Remaining: order-view surfacing of warnings | T8 |
| **2B** | **Data standardization** (4.1) — ✅ **DONE**: Vietnamese-aware primitives (`text_normalize.py`), per-company rules + suggestions (migration `d8e9f0a1b2c3`), applied at the **ORM boundary** so routes/services/scripts are all covered, auto vs confirm modes, identifier fields hard-protected. ✅ **admin screen DONE** (`/settings/standardization`, with live preview of what a rule does to a sample). ⬜ Remaining: suggestion inbox for confirm-mode | T3 |
| **2C** | **HĐNT + Đơn đặt hàng** (DB) — ✅ **model + service + migration `e9f0a1b2c3d4` + 18 tests DONE**: `master_agreements` (validity, open-ended support, suspend/terminate, penalty ≤8% per LTM 2005 Đ.301 noted as *breached portion*, not total), `master_agreement_price_lines` (line-level validity so a revision never rewrites a past order), `order_confirmations` (ĐĐH, occupies the Contract slot, snapshots the cited agreement + prices). Routing: no agreement ⇒ ordinary Contract, so **zero migration for historical orders**. ✅ **UI screens DONE** (`/agreements` list · create · view with price-list management and activate/suspend/terminate). ✅ **order-side action DONE** — an order covered by an active HĐNT now offers *Issue Order Confirmation* instead of *Create Contract*, and names the covering agreement. ✅ **document variable collectors DONE** (`collect_master_agreement_variables`, `collect_order_confirmation_variables`) — citation fields read the stored snapshot, so a reprint shows what was cited at issue. ⬜ Remaining: the .docx template FILES themselves (need the customer's letterhead/wording) | 2A |
| **2D** | **P2P close-the-loop** (DC) — ✅ **DONE**: `supplier_invoices` (+lines), `supplier_payments`, `supplier_payment_allocations`, `purchase_order_lines.quantity_invoiced`; line-level 3-way match (ordered/received/invoiced + price variance) that **warns, never blocks**; PO invoice/payment status; migration `f0a1b2c3d4e5`; 23 tests. ✅ **UI screens DONE** (`/supplier-invoices` list · record-from-PO · view with match verdict, confirm and pay). ⬜ Remaining: F11 (product master) still open | T6, T7 |
| **2E** | **SME gap analysis** (4.5) — ✅ **DONE**, written up in [`SME-GAPS.md`](SME-GAPS.md): 10 gaps, each with the evidence it is missing, classified REQUIRED/USEFUL/LATER, plus an explicit list of standard ERP modules deliberately NOT proposed. Headline: **G2 product master** (norms match on a name string), **G1 repair jobs not modelled** despite being a revenue line, **G3 no costing**, **G4 customer debt is one company-wide number** |

---

## 5. Working rules for this program

1. **Understand before changing** — every task cites file:line evidence in this ledger before code is touched.
2. **Each task ends green** — full suite run, no new failures, committed separately.
3. **Characterization tests first** where behaviour is being moved rather than changed (T3 did this: 12 tests pin the arithmetic *before* the 7 call sites were rewritten).
4. **Preserve the product** — no feature removed without a stated reason.
5. **Config over hardcoding**, but only where a real second case exists or is imminent.
6. Schema changes are **reversible Alembic migrations**, Postgres-compatible, verified round-trip on SQLite.


---

## 6. F23 — corrected scope

My first pass claimed skipped advances inflated the advance-payment reports.
**That was wrong, and the correction matters**: every money figure in
`report_service.py` is summed from confirmed, non-canceled `PaymentReport`
rows — `cash_in`, `advance_collected`, `final_collected`, `booked_value` all
join real payment documents, never `LifecycleStatus`. The financial reporting
is correct as written.

What `advance_paid = True` actually corrupts is the **timeline display**: an
order whose advance was skipped shows the same green completed marker as one
that was actually paid (`orders/view.html:315`, `orders/list.html:46`). A user
looking at the order cannot tell "paid" from "skipped".

Fix (T16, no business decision needed): render a distinct state for a skipped
advance, driven by `advance_skipped` and the new waiver record — so the
timeline tells the truth and the waiver's reason is visible on hover. The
lifecycle flag keeps its gating role untouched.

