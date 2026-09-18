# What SofaFlow still needs to run the whole business

> Requirement 4.5. Written for the business owner and the tech lead deciding
> what to build next — not a feature wish-list, and not a generic ERP checklist.
>
> **Revised 2026-09-18 after the owner corrected a wrong premise.** See
> §0 first: the largest item in the original version has been withdrawn, and
> three others were overstated. Everything below has been re-verified against
> the code.

---

## 0. Correction: how this business actually works

My first version treated the free-text line items on quotations and contracts
as a data-quality problem and proposed a product master to fix it. **That was
wrong, and it inverted the design.**

The real flow, confirmed in the code:

1. A quotation or contract line is a **detailed, negotiated description** —
   "Đóng mới ghế sofa đơn chất liệu da bò thật". Every order is bespoke. The
   free text is the agreement with that customer, not sloppy data entry.
2. When the contract is signed, `ProductionPlanService.create_from_contract`
   copies each line verbatim into `ProductionPlanItem.source_name`.
3. **Kế hoạch sản xuất is where the decomposition happens**: the user adds
   `ProductionMaterialLine` rows — this is the "phân rã đơn hàng thành các
   cấu phần" step.
4. Approving and issuing the plan checks stock and deducts it
   (`issue_materials`), refusing and reporting a shortage rather than
   deducting when stock is short.

`MaterialNorm` is an **optional accelerator**, not load-bearing. If a past
plan for a similarly-named item was saved as a norm, the material lines are
pre-filled. If nothing matches, the material list is simply **empty on the
screen** and the user fills it in — which is the normal path for bespoke work
anyway.

So my claim that "renaming a product silently breaks its norms, the plan
generates no requirement and the shortfall appears on the workshop floor" was
wrong in its consequence. Nothing is silent: the empty material list is
visible, and issuing is guarded by a stock check.

**Withdrawn as a result:** the product master (was G2, and was ranked the #1
REQUIRED item). The code written for it has been reverted. Forcing bespoke
descriptions into a fixed product catalogue would fight the business model
rather than serve it.

---

## The business, as the system currently models it

| Process | Covered by | State |
|---|---|---|
| Quote → agree → deliver → collect | Order · Quotation · Contract/ĐĐH · HandoverRecord · PaymentReport | Solid |
| Framework relationships | MasterAgreement + OrderConfirmation | Complete |
| Buy materials → receive → pay | PurchaseRequisition · PurchaseOrder · GoodsReceipt · SupplierInvoice · SupplierPayment | Complete |
| **Decompose an order into materials, issue, deduct stock** | ProductionPlan · ProductionPlanItem · ProductionMaterialLine · MaterialNorm | **Works, and is the heart of the product** |
| Stock on hand | MaterialStock, low-stock, purchase suggestions | Works |
| Who may do what | RBAC per feature, multi-store | Works |

---

## G3 — Nothing knows what anything costs · ✅ **SERVICE DONE**

**Evidence:** no cost field exists on `Material` — no `avg_cost`,
`cost_price`, `unit_cost` or `standard_cost` anywhere in the schema. Goods
receipts increase quantity only.

**Why this is now the most valuable gap.** In a bespoke business there is no
catalogue price to compare against, so the *only* way to know whether a job
made money is: what it sold for, minus the materials actually issued to it.
The system already tracks exactly that — `ProductionMaterialLine.quantity_issued`
per plan — and then cannot value it, because materials have no cost.

Every piece of this is already in place except the cost number.

**Done:** `Material.avg_cost` is blended on every goods receipt, and
`ProductionPlanService.material_cost(plan)` / `.order_margin(plan)` value what
was **issued** to a job and compare it with what the job sold for — following
whichever document the order was agreed on, contract or ĐĐH.

Three deliberate refusals, each pinned by a test:
* a receipt with **no price** is skipped, never averaged in as zero, which
  would quietly understate every cost afterwards;
* cost follows what was **issued**, not what was required — the business has
  only spent the issued part;
* an **unpriced** material is counted and reported, not treated as free. A
  total that silently omits a line is worse than one that admits it.

The margin is explicitly labelled as excluding labour. Presenting a
material-only figure as profit would flatter every job.

⬜ Remaining: put it on screen (the plan page is the natural home), and
labour — see G6, which is the other half.

---

## G4 — Customer debt is a single company-wide number · ✅ **DONE**

**Evidence:** `report_service.py:155` computes `receivable` as
`booked_value − collected` across the whole company. There is no per-customer
receivable anywhere.

The business can see that it is owed money, but not **by whom**, **how long
overdue**, or **who to chase this week**. For an SME selling on terms that is
a weekly operational task.

This is now asymmetric: after this refactor the **supplier** side answers
"what do we owe this supplier" (`outstanding_for_supplier`), while the
**customer** side cannot answer the mirror question.

**Done:** `ReportService.customer_receivables()` returns booked, collected
and outstanding per customer, largest debt first — a work queue rather than a
number, on screen at **`/reports/receivables`** with a "still owing" filter
and the total owed as the headline. ⬜ Remaining: age buckets (how overdue),
which need an agreed due-date rule first.

**A regression was found while building this.** When the HĐNT path was added,
`sales()`, `top_customers` and `accounting()` each carried their OWN copy of
"booked revenue = signed contracts". None was updated, so every order agreed
via an **ĐƠN ĐẶT HÀNG counted as zero** — the business under-reported what it
was owed by the full value of all framework-agreement orders. The definition
now lives in one place (`_booked_rows`), which is the actual fix: three copies
of a rule is why adding a fourth document type broke it silently.

---

## G6 — Production tracks material but not labour or progress · **USEFUL**

**Evidence:** `ProductionPlan` has a status machine and
`ProductionMaterialLine`, but no worker assignment, no time recorded and no
per-stage progress (verified: no `worker`, `assigned_to`, `hours` or
equivalent field exists).

Two consequences. Operationally, "which jobs are late and who is on them" is a
daily workshop question the status field answers only coarsely. Financially,
labour is the missing half of G3 — material cost alone understates what a
bespoke sofa cost to make.

Deliberately **not** proposing a full MES or work-order routing. A worker
assignment plus promised-date-vs-actual would cover the real need.

---

## G1 — Repair jobs are not distinguishable from new orders · **USEFUL**
*(downgraded from REQUIRED — see the reasoning)*

**Evidence:** `Order` has no type or category field. A repair is an `Order`
whose line description happens to describe a repair.

**Why this is not REQUIRED.** Under the bespoke model a repair *works* fine:
it is described in the line, decomposed in the production plan, and consumes
materials like any other job. Nothing is broken.

**Why it is still worth doing.** The gap is in **reporting**, not operation.
"How many repairs did we do last month, and how many were warranty jobs we
absorbed?" cannot be answered, because nothing separates a repair from a new
build. For a business with a repair line that is a number worth having — but
whether it matters enough to build is a judgement about how the owner runs the
business, and I am inferring the need rather than observing it.

**Minimum if wanted:** `Order.order_type` (`sale` / `production` / `repair`)
plus an under-warranty flag. The workflow engine can already give repairs a
different step sequence with no code change.

---

## G5 — Warranty is printed but never tracked · **USEFUL**

**Evidence:** `Contract.warranty_months` exists and **is** read — it is
rendered onto the contract document (`template_engine.py:597`).
*(My first version said nothing reads it. That was wrong.)*

What does not exist is any **tracking**: no expiry date derived from it, no
claim record, and no link from a later repair back to the order under
warranty. So when a customer calls, the office cannot tell from the system
whether the sofa is still covered; in practice that gets resolved from paper
or by guessing, and guessing generously is a direct cost.

**Minimum:** derive expiry from handover date + warranty months and show
"under warranty until …" on the order. Cheap. More useful once G1 exists.

---

## G7 — No record of money that is not an order or a purchase · **USEFUL**

**Evidence:** the only money flows modelled are customer payments against
orders and supplier payments against purchase orders (verified: no expense or
cash-book entity exists).

Rent, electricity, wages, transport, tools are invisible, so the best figure
the system can produce is a **gross** margin and the owner still needs a
separate book to know whether the month was profitable.

**Minimum:** a simple expense record (date, category, amount, payment method,
note, optional supplier). Not a general ledger, not double-entry.

---

## G8 — Document numbering is not configurable · **USEFUL**
*(scope corrected)*

**Evidence:** the prefixes `QT-`, `CT-`, `PR-`, `HR-`, `CUST-`, `ORD-` are
hardcoded in the route layer and the padding is fixed at three digits.

**Correction to my first version.** I also claimed a second, competing
numbering scheme existed in the service layer (`BaoGia_`, `HopDong_`,
`BanGiao_`). That was wrong: `_build_doc_basename` builds the **download file
name**, and embeds the document number inside it. It is a deliberate file
naming convention, not a rival numbering scheme.

So the real gap is narrower: Vietnamese businesses commonly want the year or
month inside the number (`BG-2026/001`), and today that needs a code change.
Given VAT rate, workflow and data standardization are all now configurable,
numbering is the conspicuous remaining hardcoded convention.

---

## G9 — Nothing to hand to the accountant · **LATER**

The system holds what an accountant needs but exposes no period export. Worth
asking them what their software accepts before building anything.

## G10 — Single-currency, single-tax-rate assumptions · **LATER**

Correct for a domestic sofa business today. Revisit only on export sales or a
mixed-rate range.

---

## Suggested order

| # | Gap | Class | Why this position |
|---|---|---|---|
| ~~1~~ | ~~**G3** Material costing~~ | ✅ SERVICE DONE | Screen still to come |
| ~~2~~ | ~~**G4** Customer debt~~ | ✅ DONE | Shipped, plus the DDH revenue regression it uncovered |
| 3 | **G6** Labour on production | USEFUL | Completes job costing with G3, and answers the daily workshop question |
| 4 | **G7** Expenses | USEFUL | Turns gross margin into something the owner can trust |
| 5 | **G5** Warranty tracking | USEFUL | Cheap; stops the office guessing |
| 6 | **G1** Repair job type | USEFUL | Reporting only — build it if that report is actually wanted |
| 7 | **G8** Numbering config | USEFUL | Small, visible, frequently requested |
| 8 | G9, G10 | LATER | Depend on facts not yet known |

**G3 first.** Unlike the item it replaces at the top of this list, it does not
propose a new way of working — it puts a price on data the system already
collects.

---

## What I deliberately did NOT propose

A product master or catalogue (**withdrawn — see §0**) · CRM pipelines and
lead management · marketing automation · e-commerce or a customer portal ·
barcode/RFID warehousing · full double-entry accounting · HR/payroll ·
multi-warehouse transfers · demand forecasting · a mobile app.

Each is a standard ERP module and none addresses an observed gap in how this
business operates.
