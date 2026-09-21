# SofaFlow — Refactor & Product Enhancement (2026 Q3)

## STATUS: Phase 1 and Phase 2 complete. F11 WITHDRAWN — the premise was wrong (see §7).

| | |
|---|---|
| Branch | `refactor/sofa-upgrade-2026q3` — 24 commits, not merged |
| Tests | **108 → 409**, 0 failures at every commit |
| Migrations | 6 added (19 total); a fresh database builds all 42 tables from empty |
| Code | 95 files, +10,783 / −400 |

**Verified, not assumed** (re-checked against the code after the work, not from
these notes): the two tenant filters are present, zero hardcoded VAT rates
remain in the routes, zero inline `fmtNum` copies remain in templates, zero
local status-colour maps remain, the duplicate `payment/` directory is gone,
and `alembic upgrade head` on an empty database produces the full schema.

### Requirements

| # | Requirement | State |
|---|---|---|
| 4.1 | Configurable data standardization | ✅ engine + rules + admin screen with live preview |
| 4.2 | Flexible / configurable workflow | ✅ per-company rules table + audited waivers + admin screen |
| 4.3 | HỢP ĐỒNG NGUYÊN TẮC | ✅ agreement + price list + ĐƠN ĐẶT HÀNG, reachable from the order |
| 4.4 | P2P review & completion | ✅ supplier invoice + payment + 3-way match + screens |
| 4.5 | Other SME capabilities | ✅ [`SME-GAPS.md`](SME-GAPS.md) — 10 gaps, evidence-based |

### Defects found and fixed (each reproduced by a failing test first)

1. **Cross-tenant document numbering** — `/api/next-code` computed the next number across *all* companies; `/api/check-code` reported a number taken when another company used it.
2. **PostgreSQL-only SQL** in the same endpoint — 500 on any other backend, and untestable on the SQLite suite.
3. **Contract value 0.00** against items worth 10,000,000 when created from a quotation with no form items.
4. **Single-active-contract invariant bypassed** — the route wrote via the repository, so an order could hold two active contracts and fee lookups picked an arbitrary one.
5. **Unreachable status badges** — `advance_paid` tested before `handover_confirmed`, so "Delivered" and "Contract Signed" were dead branches.
6. **Duplicate company-level stock rows** — the unique constraint never covered `store_id IS NULL`; proven with a live probe.
7. **A purchase order could be sent with no supplier**, and could then never be invoiced.
8. **`Company.vat_rate` was dead configuration** — every call site hardcoded `or 8`.

### Corrections I made to my own earlier claims

* **F23** — I reported that skipped advances inflated the payment reports. Wrong: every money figure sums confirmed `PaymentReport` rows and never reads the lifecycle flag. The defect was display-only.
* **F12** — the audit said `MaterialStock` had no unique constraint. It has one; the real gap was that SQL treats NULLs as distinct.
* **F14** — the audit implied active IDOR. A sweep of all 14 detail routes found **zero leaks**; it is a latent hazard, so I added the safe lookup and a permanent sweep instead of a risky mass refactor.
* **F18** — the reported list of tables missing `table-responsive` was wrong in both directions; I re-measured.
* **F7** — withdrawn entirely; handover totals already price by accepted quantity.

### Conventions now enforced by tests, not documentation

No template may define its own status colour map or status label dict · every
table must sit in a responsive wrapper · every template must import the UI
macros it calls, `with context` · no `confirm()` may hold bare Vietnamese · no
template may redefine a shared JS helper · no singular/plural duplicate
directories · no detail route may leak another tenant's record.

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
| F11 | — | ~~No product master; norms match on a name string~~ — **WITHDRAWN 2026-09-18.** Premise wrong: line items are bespoke descriptions BY DESIGN and `MaterialNorm` is an optional pre-fill, not load-bearing. A non-matching norm leaves the plan's material list visibly empty and the user enters lines manually, as they would anyway. Code reverted | owner correction + `services.py:1685-1718` | ❌ Withdrawn |
| F12 | S2 | ~~No unique constraint on MaterialStock~~ — **misdiagnosed.** The constraint EXISTS. The real gap: `store_id` is NULLable and SQL treats NULLs as DISTINCT, so it never covered **company-level** rows. Proven empirically: 2 duplicate main-warehouse rows accepted. `receive()` uses `.first()` → stock silently disagrees with itself | `models.py:832`, probe | ✅ **FIXED** (T6) — partial unique index + duplicate-merging migration |
| F13 | S2 | `PurchaseOrder.supplier_id` nullable → a PO could be SENT with no supplier (and could never be invoiced) | `models.py:1120` | ✅ **FIXED** (T7) — guarded at the `submit` transition rather than made NOT NULL, so drafting before choosing a supplier still works |
| F14 | S3 | `BaseRepository.get_by_id` is unscoped. **Measured, not assumed:** a sweep of all 14 detail routes with a foreign id found **ZERO leaks** — every current route does check ownership. So this is a *latent* hazard (the next forgetful route leaks), not an active defect | `repository.py:31`, `test_tenant_isolation_sweep.py` | ✅ **ADDRESSED** (T8) — scoped `get_for_company` on every repository + a permanent 28-probe sweep |
| F15 | S4 | Copy-pasted front-end helpers. **Measured:** `fmtNum` ×7, `numberToWordsVi` ×4, `parseRawFee` ×4 — all byte-identical (the two `parseRawFee` 'variants' differed only in a parameter name) | measured | ✅ **FIXED** (T9) — 15 inline copies removed |
| F16 | S4 | Status badges rendered two different ways: inline `if/elif` chains (sales screens) vs a `colors.get()` dict from the view (procurement) | both | ✅ **FIXED** (T17) — one token map + macros |
| F17 | S4 | Procurement lists returned `.all()` — every PO/PR/GR ever created on one page, no search | `procurement_service.py:232`, `requisition_service.py:118` | ✅ **FIXED** (T11) for PO/PR/GR; materials/documents/stores still open |
| F18 | S4 | Tables with no `table-responsive` wrapper → horizontal overflow on phones. **Audit list was inaccurate** — `po_list`/`pr_list`/`gr_list`/`materials/list` already had it; `customers/list`, `customers/view`, `documents/list`, `dashboard/index`, `admin/admins`, 4× materials pages and `production/plan` did not (11 files, re-measured) | measured | ✅ **FIXED** (T12) + guard test |
| F19 | S4 | Procurement/production bypassed i18n entirely | templates | ✅ **Labels FIXED** (T13). ⬜ Remaining: `status_labels`/`action_labels` dicts passed from views, JS `confirm()` strings, and prose fragments split across inline tags — see T13-remainder |
| F20 | S4 | `payment/` and `payments/` template directories both existed for the same concept | dirs | ✅ **FIXED** (T14) — merged onto plural + guard test |
| F23 | S4 | `skip_advance_payment` sets `lifecycle.advance_paid = True` when no money was received. **Scope corrected 2026-09-18:** money reports sum confirmed `PaymentReport` rows, NOT this flag, so financial figures were never wrong. The real defect is **display only** — the order timeline shows a green "advance paid ✓" for a skipped advance | `report_service.py:133-145` (correct), `orders/view.html:315`, `orders/list.html:46` | Open — T16 |
| F24 | S2 | **Unreachable status badges.** `orders/list.html` tested `advance_paid` before `handover_confirmed`; every delivered order also has `advance_paid`, so the "Delivered" and "Contract Signed" branches were dead code — an order showed "Advance Paid" from delivery until fully paid | `orders/list.html:44-53` | ✅ **FIXED** (T17) |
| F21 | S4 | Missing screens. **Triaged, not filled in:** Orders had **no edit route at all** (a title typo was permanent and printed on every document) and the HĐNT I shipped had no edit (a draft that could not be corrected). Both built. `stores`/`users` need no separate view — edit already shows everything; per-document-type lists deferred with a reason | inventory | ✅ **TRIAGED** (T15) |

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

**Screens deliberately NOT added (T15 triage).** The brief asked not to add
CRUD everywhere, so each absence was judged on the entity's lifecycle:
`stores` and `users` need no separate *view* — their edit form already shows
every field, and a read-only twin would be two screens to keep in sync for no
gain. Per-document-type **lists** (quotations, contracts, handover, payments)
are a real gap but a larger one: the useful version is a single cross-document
search, not four near-identical lists, and that is worth designing rather than
generating. `GoodsReceipt` has no create form on purpose — a receipt only
exists as the result of receiving against a purchase order, and a free-standing
one would bypass the 3-way match.


**T13-remainder: ✅ DONE.** The label dicts are gone — status labels now come
from `status_meta()` like the colours do, and action labels (`Gửi duyệt`,
`Duyệt`, `Từ chối (làm lại)`…) have their own keys. Every JavaScript
`confirm()` message goes through `t()`. Two more guard tests: no template may
define a status→label dict, and no `confirm()` may hold bare Vietnamese.

Still open by design: prose split across inline tags (`… <strong>và bấm</strong> …`).
Translating a fragment like "và bấm" alone is nonsense because word order
differs between the languages; those sentences need rewriting to hold one
`t()` call, which is a copy decision for whoever owns the wording.


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
| T8 | Measure the real exposure first, then add `BaseRepository.get_for_company` + a permanent cross-tenant sweep (F14). **No mass refactor of `get_by_id`** — the evidence did not justify the risk | `repository.py` | `test_tenant_isolation_sweep.py` (31) | ✅ Done |
| T9 | Extract `static/js/sofa-doc-utils.js` (fmtNum · parseRawFee · numberToWordsVi); remove 15 inline copies; load in `<head>` to kill the ordering hazard (F15). `recalcAll` deliberately NOT extracted — its body genuinely differs per document type | 8 templates + js | `test_ui_consistency.py` (20) | ✅ Done |
| T17 | Shared status vocabulary + UI macro library; orders list converted (F16, F24, F23-display) | `status_tokens.py`, `macros/ui.html`, `style.css` | `test_status_tokens.py` (29) | ✅ Done |
| T11 | Pagination + search on PO/PR/GR (F17): service-level `page`/`search`, shared `search_bar` macro, `_pagination.html`. Search on PO covers number **and supplier name**; verified still tenant-scoped | services + routes + templates | `test_procurement_lists.py` (8) | 🟡 PO/PR/GR done; materials/documents/stores remain |
| T12 | Responsive wrapper on the 11 tables actually missing it + lint test so no new screen can opt out (F18) | 11 templates | `test_ui_consistency.py` (7) | ✅ Done |
| T13 | i18n pass on procurement/production (F19): **74 keys added, 114 strings wrapped**; one sentence split across `<strong>`/`<em>` rewritten as a single key. Guard test scans every template for bare Vietnamese labels | 10 templates + `i18n.py` | `test_ui_consistency.py` (28) | ✅ Labels, actions, confirms done |
| T14 | Merge `payment/` into `payments/` via `git mv` (history preserved); guard test fails if any singular/plural directory pair reappears (F20) | templates + routes | `test_ui_consistency.py` (26) | ✅ Done |
| T15 | Triage missing screens (F21): built **order edit** (descriptive fields only — money is derived from documents, customer/store would invalidate them) and **agreement edit** (draft/active only — terminated is history that orders cite). Everything else deliberately NOT added | routes + 2 templates | `test_edit_screens.py` (11) | ✅ Done |
| D1 | Refresh `CLAUDE.md` — CSRF/Alembic corrected, plus the new house rules (money module, status tokens, workflow engine, normalization chokepoint), real test commands, current data model and branch | `CLAUDE.md` | — | ✅ Done |

### Phase 2 — Product enhancements

| T | Task | Depends on |
|---|---|---|
| **2A** | **Workflow engine** (DA) — ✅ **engine + rules + waivers + migration + 11 tests DONE**; service guards migrated; `skip_advance_payment` now records an audited waiver. ✅ **admin screen DONE** (`/settings/workflow` — relax/waive/disable per rule). ✅ **order-view surfacing DONE** — `advisories()` + a muted line in the status card. Doing it found that OPTIONAL had never been surfaced anywhere (so the mode was inert), that unticking a rule restored the shipped default instead of switching it off, and that the messages were reaching Vietnamese users in English | T8 |
| **2B** | **Data standardization** (4.1) — ✅ **DONE**: Vietnamese-aware primitives (`text_normalize.py`), per-company rules + suggestions (migration `d8e9f0a1b2c3`), applied at the **ORM boundary** so routes/services/scripts are all covered, auto vs confirm modes, identifier fields hard-protected. ✅ **admin screen DONE** (`/settings/standardization`, with live preview of what a rule does to a sample). ✅ **confirm-mode suggestions DONE** — surfaced after saving via one `after_request` hook (no table, no inbox: a queue you must remember to visit is the wrong shape here). Found that `confirm` had been a silent no-op — the listener discarded what `normalize_instance()` returned | T3 |
| **2C** | **HĐNT + Đơn đặt hàng** (DB) — ✅ **model + service + migration `e9f0a1b2c3d4` + 18 tests DONE**: `master_agreements` (validity, open-ended support, suspend/terminate, penalty ≤8% per LTM 2005 Đ.301 noted as *breached portion*, not total), `master_agreement_price_lines` (line-level validity so a revision never rewrites a past order), `order_confirmations` (ĐĐH, occupies the Contract slot, snapshots the cited agreement + prices). Routing: no agreement ⇒ ordinary Contract, so **zero migration for historical orders**. ✅ **UI screens DONE** (`/agreements` list · create · view with price-list management and activate/suspend/terminate). ✅ **order-side action DONE** — an order covered by an active HĐNT now offers *Issue Order Confirmation* instead of *Create Contract*, and names the covering agreement. ✅ **document variable collectors DONE** (`collect_master_agreement_variables`, `collect_order_confirmation_variables`) — citation fields read the stored snapshot, so a reprint shows what was cited at issue. ⬜ Remaining: the .docx template FILES themselves (need the customer's letterhead/wording) | 2A |
| **2D** | **P2P close-the-loop** (DC) — ✅ **DONE**: `supplier_invoices` (+lines), `supplier_payments`, `supplier_payment_allocations`, `purchase_order_lines.quantity_invoiced`; line-level 3-way match (ordered/received/invoiced + price variance) that **warns, never blocks**; PO invoice/payment status; migration `f0a1b2c3d4e5`; 23 tests. ✅ **UI screens DONE** (`/supplier-invoices` list · record-from-PO · view with match verdict, confirm and pay). F11 withdrawn (see §7) | T6, T7 |
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

