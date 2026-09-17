# What SofaFlow still needs to run the whole business

> Requirement 4.5. Written for the business owner and the tech lead deciding
> what to build next — not a feature wish-list, and not a generic ERP checklist.
>
> Every gap below is stated with the evidence that it is actually missing, and
> each is classified as **REQUIRED** (the business cannot run correctly without
> it), **USEFUL** (real value, can wait), or **LATER** (only when the business
> grows into it). Where I am inferring rather than observing, I say so.

---

## The business, as the system currently models it

Three revenue activities were described: **selling sofas**, **manufacturing
them**, and **repairing/servicing them**.

The system covers the common lifecycle well:

| Process | Covered by | State |
|---|---|---|
| Quote → agree → deliver → collect | Order · Quotation · Contract/ĐĐH · HandoverRecord · PaymentReport | Solid |
| Framework relationships | MasterAgreement + OrderConfirmation | New, complete |
| Buy materials → receive → pay | PurchaseRequisition · PurchaseOrder · GoodsReceipt · SupplierInvoice · SupplierPayment | Complete as of this refactor |
| Plan production, issue materials | ProductionPlan · ProductionMaterialLine · MaterialNorm | Works, but see G1/G2 |
| Stock on hand | MaterialStock, low-stock, purchase suggestions | Works |
| Who may do what | RBAC per feature, multi-store | Works |

---

## G1 — Repair jobs are not modelled at all · **REQUIRED**

**Evidence:** `Order` has no type field. Its columns are `order_code`,
`title`, `description`, `total_amount`, `advance_amount`, `final_amount`,
`notes` and the lifecycle flags — nothing distinguishes a new sofa sale from a
manufacturing job from a repair. A repair is an `Order` whose `title` happens
to say so.

**Why this matters more than it looks.** A repair is not a small sale; it has
different facts:

* it concerns an **existing item**, often one this company originally sold;
* it has a **fault description** and a **diagnosis**, which the quote depends on;
* it may be **under warranty**, in which case the customer pays nothing — but
  the job still consumes materials and labour that the business pays for;
* it usually skips the deposit step entirely.

Today none of that can be recorded, reported or searched. "How many repairs
did we do last month, and how many were warranty jobs we absorbed?" is
currently unanswerable — and for a business with a repair line, that is one of
the two or three numbers that decide whether the line is profitable.

**Minimum:** `Order.order_type` (`sale` / `production` / `repair`), plus a
small repair block (item description, reported fault, under-warranty flag,
link to the originating order when known). The workflow engine built in this
refactor can already give repairs a different step sequence without code
changes — that part is free.

---

## G2 — No product master; material norms match on a name string · **REQUIRED**

**Evidence:** `MaterialNorm.product_key` is a lowercased product **name**
(`models.py`). There is no product/item entity anywhere in the schema.
Quotation, contract and handover line items are free-text JSON.

**The failure is silent.** Rename "Sofa 3 chỗ" to "Sofa 3 chỗ da bò" on a new
quotation and its material norms stop matching. Nothing errors. The production
plan simply generates no material requirement, and the shortfall is discovered
on the workshop floor.

It also makes ordinary questions impossible: "what do we sell most of", "what
does this model cost us", "which customers bought this model" — none can be
answered, because there is no thing called a product to group by.

**Minimum:** a `Product` master (code, name, unit, category, default price),
with line items referencing it while keeping the free-text name for one-off
custom work. Norms then key on the product id. This is the single highest-value
structural fix remaining, and it unblocks G3 and G5.

---

## G3 — Nothing knows what anything costs · **REQUIRED**

**Evidence:** no cost field exists on `Material` — no `avg_cost`,
`cost_price`, `unit_cost` or `standard_cost` anywhere in the schema. Goods
receipts increase quantity only.

So the business can see revenue, and can see what it paid suppliers in total,
but cannot answer **"did we make money on this order?"** A sofa's cost is the
materials issued to it plus labour, and neither is valued.

**Minimum:** moving-average cost on `Material`, updated on each goods receipt
(`new_avg = (old_qty × old_cost + received_qty × po_price) / new_qty`). That
alone makes material cost per production plan computable. It is a small
addition — deliberately not a full valuation layer, and explicitly not FIFO or
standard costing, which this business does not need.

Labour cost is a bigger question and belongs in G6.

---

## G4 — Customer debt is a single company-wide number · **REQUIRED**

**Evidence:** `report_service.py:155` computes `receivable` as
`booked_value − collected` across the whole company. There is no per-customer
receivable anywhere.

The business can therefore see that it is owed money, but not **by whom**,
**how long overdue**, or **who to chase this week**. For an SME selling on
terms, chasing debt is a weekly operational task, not a reporting nicety.

Note this is now asymmetric: after this refactor the **supplier** side can
answer "what do we owe this supplier" (`outstanding_for_supplier`), while the
**customer** side cannot answer the mirror question.

**Minimum:** receivable per customer = confirmed contract/ĐĐH value minus
confirmed payments, with an age bucket and a list view sorted by oldest.

---

## G5 — Warranty is recorded but never tracked · **USEFUL**

**Evidence:** `Contract.warranty_months` exists (`models.py:447`). Nothing
reads it. There is no warranty expiry, no claim record, and no link from a
repair back to the order that is under warranty.

So when a customer calls, the office cannot tell from the system whether the
sofa is still covered. In practice this gets resolved by looking through paper
or by guessing — and guessing generously is a direct cost.

**Minimum (after G1):** derive expiry from handover date + warranty months,
show "under warranty until …" on the order, and let a repair cite the original
order. Cheap once G1 exists, which is why it is USEFUL rather than REQUIRED.

---

## G6 — Production tracks material but not labour or progress · **USEFUL**

**Evidence:** `ProductionPlan` has a status machine and
`ProductionMaterialLine`, but no worker assignment, no time recorded and no
per-stage progress.

For a workshop, "which jobs are late and who is on them" is a daily question.
The status field answers it coarsely (`processing`) but not usefully.

Deliberately **not** proposing a full MES or work-order routing here — that
would be over-engineering for this size of business. A worker assignment and a
promised-date-vs-actual comparison would cover most of the real need.

---

## G7 — No record of money that is not an order or a purchase · **USEFUL**

**Evidence:** the only money flows modelled are customer payments against
orders and supplier payments against purchase orders.

Rent, electricity, wages, transport, tools — the ordinary running costs — are
invisible. That means the profit figure the system can produce is a **gross**
margin, and the owner still needs a separate book to know whether the month was
actually profitable.

**Minimum:** a simple expense record (date, category, amount, payment method,
note, optional supplier). Not a general ledger, not double-entry — a cash-out
book with categories.

---

## G8 — No document numbering configuration · **USEFUL**

**Evidence:** prefixes are hardcoded in two different places and in two
different styles (`QT-`/`CT-`/`PR-`/`HR-` in the route layer,
`BaoGia`/`HopDong`/`BanGiao` in the service layer), and the padding is fixed at
three digits.

Vietnamese businesses commonly want year or month in the number
(`BG-2026/001`). Today that needs a code change. Given this refactor has
already made VAT rate, workflow and data-standardization configurable, document
numbering is the conspicuous remaining hardcoded convention.

---

## G9 — Nothing to hand to the accountant · **LATER**

The system holds everything an accountant needs but exposes no export. A
period-based export of sales documents, supplier invoices and payments (CSV or
XLSX) would remove a recurring manual copy-out.

Marked LATER because the shape depends entirely on what the accountant's own
software accepts — worth asking them before building anything.

---

## G10 — Single-currency, single-tax-rate assumptions · **LATER**

Amounts carry no currency and VAT is one rate per document. Correct for a
domestic sofa business today. Only worth revisiting on export sales or a
mixed-rate product range.

---

## Suggested order

| # | Gap | Class | Why this position |
|---|---|---|---|
| 1 | **G2** Product master | REQUIRED | Unblocks G3 and G5; every day without it adds more free-text data to migrate later |
| 2 | **G1** Repair jobs | REQUIRED | A whole revenue line is currently invisible |
| 3 | **G4** Customer debt | REQUIRED | Weekly operational need; small build |
| 4 | **G3** Material costing | REQUIRED | Needs G2 to be meaningful per product |
| 5 | **G5** Warranty tracking | USEFUL | Cheap once G1 lands |
| 6 | **G7** Expenses | USEFUL | Turns gross margin into something the owner can trust |
| 7 | **G6** Production labour | USEFUL | Daily workshop visibility |
| 8 | **G8** Numbering config | USEFUL | Small, visible, frequently requested |
| 9 | G9, G10 | LATER | Depend on facts we do not have yet |

**G2 first** is the one recommendation I would argue for hardest: it is the
only item on this list that gets *more expensive every week it is deferred*,
because the volume of free-text product names that must eventually be
reconciled keeps growing.

---

## What I deliberately did NOT propose

CRM pipelines and lead management · marketing automation · e-commerce or a
customer portal · barcode/RFID warehousing · full double-entry accounting ·
HR/payroll · multi-warehouse transfers · demand forecasting · a mobile app.

Each is a standard ERP module and none of them addresses an observed gap in
how this business actually operates. Adding them would make the product larger
without making it more complete.
