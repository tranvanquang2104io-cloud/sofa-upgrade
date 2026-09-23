# Đánh giá toàn hệ thống — UI và logic

> Written for: chủ doanh nghiệp + tech lead. Reviewed by three lenses (BA,
> QA tester, fullstack dev) then **verified by me before anything was acted
> on** — three of their findings turned out to be wrong and are listed as
> rejected, because acting on an unverified report is how the withdrawn
> product master happened.
>
> Guiding constraint throughout: **the people using this are not confident
> with computers.** Every judgement below is "what would a careful but
> non-technical staff member experience", not "what would a developer prefer".

---

## 0. Verdict in one paragraph

The business logic is sound and the process is complete end to end — quote →
agree → produce → deliver → collect, plus purchasing and framework agreements.
What is weak is **the safety net around it**. Actions that commit money, send
something to a supplier, or cannot be undone were firing on a single click,
and one document could be issued but never voided. Those are the changes made
first, because for this audience a mis-click is more likely than a wrong
decision. The second weakness is **losing typed work**: a validation error on
a long bespoke order discards everything the user typed.

---

## 1. Fixed in this pass

| # | Problem | Why it matters here |
|---|---|---|
| 1 | **"Phát hành Đơn đặt hàng" had no confirmation and could never be undone** | The worst combination in the system: one click issued a commercial document recording agreed prices, and nothing could void it. Both halves fixed — it now asks first, and there is a cancel route requiring a reason. |
| 2 | **Duyệt báo giá / Ký hợp đồng / Xác nhận bàn giao fired on one click from the order page** | The same three actions *are* modal-protected on each document's own page. The order page carried unguarded copies — same consequence, no warning. |
| 3 | **Xác nhận hóa đơn NCC and Ghi nhận thanh toán had no confirmation** | Both commit money to a supplier. My own code, shipped without a guard. |
| 4 | **"Gửi NCC" on a purchase order had no confirmation** | Sending a PO is a real commitment to buy. Only *cancel* warned; *send* did not. |
| 5 | **Đổi trạng thái HĐNT had no confirmation** | Suspending or terminating changes whether new orders can be placed at all. |
| 6 | **The timeline drew a waived advance exactly like a received one** | Same green tick for "khách đã trả" and "mình đồng ý bỏ qua". The status badge had been fixed earlier; the timeline had not. It now shows a distinct marker and says no money was received. |
| 7 | **A zero-quantity material line was accepted** | It looks planned, issues nothing, and quietly under-states what the job needs. |

A **lint test now scans every template**: any form posting to a state-changing
endpoint must be guarded by a confirmation or a modal, or the build fails. The
convention is enforced, not just written down.

---

## 2. Rejected findings — checked and found wrong

Recording these because a review that only lists problems teaches nothing
about which reports to trust.

* **"Contract creation is not blocked server-side on an approved quotation."**
  It is deliberately optional. `AUDIT/DECISIONS.md` D6 decided this follows
  standard quote-to-cash practice, and the workflow engine seeds that rule as
  `optional` on purpose. Enforcing it would break walk-in and verbally-agreed
  orders.
* **"Material deactivation has no confirmation."** It does —
  `materials/view.html` wraps it in a confirm. The reviewer looked at the list
  screen, where the button is not.
* **"Signing a contract and approving a quotation have no confirmation."** On
  their own pages they are inside modals. My own first grep missed the modal
  pattern and would have reported this too; I checked before acting.

---

## 3. Open — needs your decision, not code

**3.0 Who may sign a contract or confirm that money arrived?**

Measured, not assumed: **16** consequential actions are protected by
`@login_required` alone — approve and cancel a quotation, sign and cancel a
contract, cancel an order, confirm and cancel a handover, confirm and cancel a
payment, delete a document, confirm a supplier invoice, receive a purchase
order, convert a requisition.

That sits oddly against the rest of the same system: adding a material needs
`store_admin`, deactivating one needs `company_admin`. So a staff account
cannot add a fabric to the catalogue, but can sign a contract and record that
a customer paid.

**Deliberately not changed.** Who may do what is a business decision, and
guessing wrong in the tightening direction is the worse failure: it locks
people out of their daily work with no warning. Three shapes to choose from:

1. leave it — everyone in a small shop is trusted, and the audit trail already
   records who did what;
2. money-and-signature actions require `store_admin` (sign, confirm payment,
   confirm handover, confirm supplier invoice), the rest stay open;
3. per-feature permissions per user, which the `feature_labels` plumbing on the
   user form already hints at.

Evidence: `dashboard_routes.py` — decorator census 1 route with none
(`set_language`, correct: the login page needs it), 82 `login_required`, 13
`company_admin_required`, 11 `store_admin_required`.


**3.2 A payment confirmed by mistake can never be corrected.**

`PaymentReport.can_cancel()` and `can_edit()` both require `not is_confirmed`,
and there is no unconfirm or reopen route anywhere in the product. Once
someone presses *Xác nhận*, that record is permanent.

What that costs, concretely: a 9,703,200 advance confirmed against the wrong
order, or the same receipt entered and confirmed twice, leaves the customer
showing as having paid, understates the receivable by that amount, and can be
put right only by editing the database. For the person using this product
there is no way back at all.

This is more consequential than §3.1 — a contract that cannot be cancelled is
awkward, money recorded that never arrived is wrong. But **how** an accounting
mistake gets corrected is a business and audit policy, so the current
behaviour is pinned in `tests/test_cancellation_arithmetic.py` and left as it
is until you choose:

1. **Void with a reason** — mark the payment cancelled, restoring the
   receivable, keeping the row and the reason for the audit trail. Simplest,
   and matches how cancellation already works everywhere else here.
2. **Reversing entry** — leave the original untouched and post an opposite
   record. What an accountant expects, and what survives an inspection best,
   but it doubles the rows a shop owner reads on the payment list.
3. **Unconfirm, then edit** — reopen to draft, correct it, confirm again. The
   gentlest for a non-technical user, and the weakest audit trail of the three.

Recommendation: **(1)**, restricted to the same role that may confirm, with the
reason mandatory. It restores the correct figure, leaves evidence of what
happened, and reuses a pattern the product already has.


**3.1 A signed contract cannot be cancelled anywhere.**
`Contract.can_cancel()` requires `not is_signed`. In bespoke furniture a
customer backing out after signing is a normal event, and today it has no home
in the system: cancelling the *order* leaves the signed contract dangling.
Options: allow cancelling a signed contract with a mandatory reason, or have
"Huỷ đơn hàng" cascade to its contract. **Which matches how you actually
handle this?**

**3.3 Bàn giao + Thanh toán cuối are one checkbox.**
Ticking it confirms the handover *and* creates the final payment in one
action, with no review of the amount in between. They are two different
business events. Split them, or show a summary before committing both?

**3.3 Replacing a contract happens silently.**
Creating a second contract deactivates the first with no warning — only
"Contract created successfully". Since advance amounts were computed from the
old one, this is money-affecting. I would add a confirmation naming the
contract being replaced; confirm that is the behaviour you want rather than
blocking a second contract outright.

---

## 4. Biggest usability problem — FIXED

**A validation error used to throw away everything the user typed.** On a
failed save the create screens re-rendered empty: line items, descriptions,
amounts, all gone. For a bespoke order with many hand-typed lines, hitting
that after ten minutes of work was the single most punishing thing the product
did to a non-technical user — and it made people distrust the whole system,
not just that screen.

Fixed in **one place, with no route changes**. Flask already exposes the
submitted form to the template, so the base layout hands it back on any POST
that re-renders, and a small script restores every field — including the
dynamically-added line-item rows, which it rebuilds before filling.

The one thing it cannot restore is **file inputs**: a browser will not let a
page re-select a file the user chose. Rather than dropping them silently, the
page now says so ("Your text was restored. Please choose any images again.").

Because it lives in the layout it covers every form in the app at once,
including the most common real failure — a document number already in use.

---

## 5. Readiness for what you want to add later

**Chữ ký số (digital signature) — the seam now exists.**
*Correction to the first review: a `DocumentService` DOES exist (in
`services.py`, not its own file) and already funnels every generated document
through one `_save_document`. What was missing was a lifecycle state.*

`Document.status` is now explicit: `current` / `superseded` / `signed`. A
signing step has somewhere to live, and the rule that matters is already
enforced — **a signed document is never superseded by a regeneration**,
because it is evidence, not a draft.

That change earned its place on its own: regenerating writes a NEW file each
time (the name carries a timestamp), so one contract could own three files
with nothing saying which to send the customer. The screen marked only the
single newest row as "Latest", but that list mixes document *types*, so the
current contract could sit unmarked next to a newer payment file.

**Chatbot AI.** It needs stable functions to ask ("trạng thái đơn này", "còn
nợ bao nhiêu"). Today `dashboard_routes.py` is ~4,400 lines and holds more
logic than the entire `app/services/` directory combined (~3,600 lines), and
there are only 3 JSON endpoints in the whole app.

**The same small change unblocks both:** extract a thin `DocumentService` with
an explicit status, and expose a handful of JSON endpoints over the existing
services. Worth doing *before* either feature, not during.

---

## 4d. Two figures that disagreed, and five that could collide

**The dashboard counted customers the list would not show.** It used
`filter_by(company_id=...)` with no `is_active` filter while every customer
list and lookup filters it. Measured on a real page: the card said **4**, the
list showed **3**. Two screens answering the same question differently is what
stops a user believing either one.

**Document numbers were generated by counting rows.** PO, GR, PR, supplier
code and production plan number were all `count() + 1`. A count is not a
sequence — delete any document and the next one repeats a number already used,
which the unique constraint on (company, number) then rejects. Not silent
corruption, but an unexplained crash on an action that worked a minute
earlier, and **retrying cannot help** because the count does not change.

All five now read the highest number already issued. A deleted document leaves
a gap — normal and auditable — instead of a collision.

Worth noting how these were found: both came from scanning for one idiom
(`.count()`) after the first instance turned up, rather than from reading
screens one at a time. The dashboard gave the mild version, the numbering the
severe one.


## 4e. Front-end convergence and dynamic CRUD

**The screen contract.** Measured first: **12 of 73** screens used
`page_header()`. The macro library existed and almost nothing called it, which
is why the product read as several products. The contract is now a test
(`tests/test_screen_contract.py`) with a NOT_YET list that may only shrink —
progress was a number, not a feeling, and converged screens could not drift
back while the rest was in flight. **44/44 now.**

Four ways of going back existed in one product: a top-right *Back*, a *Back to
Order*, an icon-only arrow left of the title, and the breadcrumb. All four are
the breadcrumb now. Labelled facts had three renderings (`<dl><dt>`, grid
columns with `<strong>Label:</strong>`, bare divs); all go through
`detail_row()`. *Create* was `btn-success` in procurement and `btn-primary`
everywhere else.

**Reasoned exceptions** (recorded, not skipped): the three master-admin screens
serve the platform operator, extend their own base, navigate by sidebar and
call `t()` nowhere.

**One change that went against "keep the look"**: `stores/list` was the only
list built as a card grid. Consistency was the explicit instruction and store
data has the same shape as user data, so it is a table. Reversible if cards
are preferred.

### Dynamic configuration

Two settings screens could edit only what had been seeded, so anything nobody
anticipated could never be configured. Both are now grids where every possible
row already exists:

| Screen | Rows | Columns | Cell |
|---|---|---|---|
| Standardization | every text field, discovered from the data model | every primitive | tick = apply |
| Workflow | every action in `ALL_ACTIONS` | every prerequisite | mode, blank = no rule |

Setting a cell creates the rule; clearing it deletes the rule. There is no
create form and no delete button because the row is already there — which is
the answer to "how does the system know which field I mean".

The workflow grid also expresses what the old form could not: **one step
carrying several prerequisites**. And `quotation.approve` and
`handover.confirm` were declared in `ALL_ACTIONS` but unreachable — seven steps
reached the screen as five.

### CRUD audit, and the exceptions

Measured from the route table:

| Deliberately absent | Why |
|---|---|
| Goods receipt: create / edit | A receipt exists only as the result of receiving against a purchase order. A free-standing one bypasses the 3-way match and corrupts the moving-average cost. |
| Template delete, when it has printed | `Document.template_id` records what each document came out of. Deactivate instead — the screen shows the count and a padlock. |
| Customer delete | Orders, quotations and contracts carry the name. Deactivate keeps the history. |
| Supplier invoice edit / delete | Confirmed invoices are accounting records; see §3.2 on correcting a mistake. |

**Still open, and worth your call:** per-document-type lists (quotations,
contracts, handover, payments have create/view/edit but no list of their own),
and read-only *view* screens for stores and users. The second is two screens to
keep in sync for no new information — the edit form already shows every field.


## 4a. Every chain validated to the đồng

Five processes walked end to end with **57 figures** asserted against
hand-computed values rather than against whatever the code returns. All
correct today; the point is that any drift now fails loudly.

| Chain | Checks | Headline numbers |
|---|---|---|
| O2C via contract | 10 | 29,300,000 + VAT 2,344,000 + fees 700,000 = **32,344,000**; advance 30% = 9,703,200; balance 22,640,800 |
| O2C via HĐNT/ĐĐH | 11 | agreed list 11,000,000 / 3,800,000 → **28,264,000**; a later price revision does not move an issued order |
| P2P | 15 | 100m @ 250,000; receive 60 then 40 @ 300,000 → average **270,000**; invoice 16,200,000; pay 10,000,000 → owe 6,200,000 |
| Production | 9 | issue 40m + 15m = **12,250,000** cost; margin 20,094,000, labour excluded |
| P2P front end | 12 | suggest = need − on hand + minimum: 40 − 15 + 5 = **30**; three lines across two suppliers → **two** orders |

Three checks exist to catch a plausible mistake rather than to record a total:

* charging VAT on the shipping and other fees would add exactly **56,000** to
  the sample order — the fees are added after tax;
* a **shortage issues nothing at all**, because issuing what happens to be in
  stock and leaving the rest makes the stock figures lie about a job that was
  never started;
* the **second receipt at a different price** is the only place a costing bug
  hides in plain sight, so the blend is pinned at 270,000.

The 3-way match is checked in both failing directions — invoicing more than
arrived, and a price 4% over the 2% tolerance — and both **warn while still
recording the invoice**, which is the deliberate SME choice.


## 4a-bis. The advance now follows the contract

The owner's rule: a contract with an advance percentage other than zero must
have its advance; a contract at 0% does not, and the handover and payment go
ahead without one.

Built as a **fourth rule mode** (`required` · `waivable` · `optional` ·
`contract`) rather than a hardcoded branch, so the same engine can carry other
rules of this shape later. `contract` mode still honours a recorded waiver;
`required` still refuses to be waived.

The half that mattered most was the screen. `orders/view` read
`lifecycle.advance_paid` directly, so a 0% contract never showed *Create
Handover* or *Record Final Payment* at all — the order could not be finished
from its own page — and it ignored the workflow engine entirely, so relaxing a
rule in settings changed nothing. The page now asks `WorkflowService.can()`,
the same question the service answers when the form arrives.


## 4b. Screens that grow, and screens nobody had opened

**Lists.** Of the 8 screens whose row count grows with business volume, two
were broken: the orders list — the busiest screen, and the only table that
grows forever since orders are never archived — had no search at all, and the
goods-receipt list was stuck on page 1 because the route paginated but never
passed `pagination` to the template, so the nav rendered as nothing. The
customer search took a different code path from browsing, capped at 20, with
no next-page link to suggest there were more.

`materials/list` has search and no paging and is **left that way on purpose**:
it returns every row, and for a few hundred materials one page with a search
and a category filter beats paging.

**Coverage.** 6 of 107 dashboard routes had never been opened by any test. The
two that serve files were checked first and were sound; the document download
led to `redirect(request.referrer)` in twelve places (see §4c).

**Cross-tenant writes.** The isolation sweep only asked whether another
company's records could be READ, while 35 POST routes take a record id. Nine
write probes added; no cross-tenant write is possible. Two corrections were
needed before that sentence was worth anything: the probes first passed
because a workflow rule blocked the action before tenancy was consulted, and
the check that the sweep bites first patched the wrong one of seven identical
guards. Only after the rival's contract was actually signed, and the sweep
failed on that probe, was the result a finding.

### Checked and NOT a defect

* `create_handover` computes line totals in `float` while the shared parser
  uses `Decimal`. On realistic VND values the difference is 1.5e-08 — invisible
  after formatting, and no line case differed. A consistency wart, not a bug.
  Recorded so it is not re-litigated.
* The three material POST routes looked unguarded to a crude scan; all three
  check ownership via `get_material(id, company_id)`.

## 4c. Redirects

`redirect(request.referrer)` in 12 places. Absent referrer → `Location: None`
→ a 404 page called "None" right after a failed action. And the header is set
by whoever sent the user in, so another site could bounce them back out.
`_is_safe_redirect_url` could not be reused — it requires a relative path and a
referrer is absolute — so `_safe_back_url()` does a same-origin test instead.


## 5a. Configuration that could not do anything

`contract.sign` and `contract.create` are seeded into every company and listed
on the workflow settings screen, where a company admin can change their mode.
**Nothing ever called `WorkflowService.require()` for either.** Only handover
creation and the two payment actions were gated. An admin could set "signing
requires an approved quotation", save it, see it on the screen, and have it do
nothing at all.

Both are now enforced. Default behaviour is unchanged by construction: the
shipped rule for `contract.sign` is `contract_created`, satisfied by the
contract existing, and `contract.create` ships as OPTIONAL, i.e. advisory.

**And when a rule did refuse, the reason was discarded.** `WorkflowBlocked`
carries the sentence that explains the refusal, but six POST handlers caught
broad `Exception` and flashed "Error signing contract". The user pressed Sign,
got a red bar saying "Error", and had no way to learn that the quotation needed
approving. Those six now catch `ValueError` first and show its message, keeping
the generic handler underneath for genuinely unexpected failures.

Held by `test_every_seeded_rule_is_enforced_somewhere`. Scoped to
`DEFAULT_RULES`, not `ALL_ACTIONS`: `quotation.approve` and `handover.confirm`
are declared constants with no seeded rule, and the settings screen renders
only rules that exist, so they are not reachable by an admin today. My first
version of that lint flagged them and would have had me build enforcement for
a setting nobody can set.

Also removed `actions=ALL_ACTIONS` from the settings context — passed to the
template, never used by it. It is what makes the screen look as if new rules
can be added.


## 5b. Confirmation — measured, and one defect behind it

The product rule is that a change must always confirm. Measured: **18** actions
a user cannot undo by pressing the same button again; **16** already asked.

A first pass reported 69 of 95 POST forms unconfirmed. That number was wrong —
it looked only inside the `<form>` tag and missed that most of these forms sit
*inside a modal*, which IS the confirmation (and the better one: it can show
what is about to change and collect a reason). Recorded because the wrong
number would have led to 60-odd pointless dialogs.

The two genuine gaps:

* `activate_template` — its twin `deactivate_template` asked, it did not.
  Pulling that thread found a real defect: activation was not exclusive, so
  several templates of one type could be Active, and `get_default_for_type()`
  resolved that with `.first()` and no `ORDER BY`. A user could upload a
  corrected contract template, activate it, and keep printing the old one.
  Fixed: exclusive activation + deterministic lookup + the flash says what was
  retired.
* the behind-schedule toggle — now asks only when SETTING the flag. Clearing
  it is the undo; confirming both directions is clutter.

Held by `test_every_irreversible_action_asks_first`, over 13 named actions —
deliberately not every POST, since a create form is the user's own deliberate
submission.


## 6. UI consistency — measured, not guessed

| Pattern | Adoption |
|---|---|
| `page_header()` | 12 of 77 templates |
| `status_badge()` / `doc_badge()` | document screens converted; the boolean→status derivation now lives in one place |
| `process_stepper()` | ✅ now on the order page (was built and never used) |

**Status colour is now enforced, not agreed.** A lint test fails the build if a
status word appears inside a hardcoded `badge bg-*` outside `macros/ui.html`.
It found 19 remaining offenders, two of them real defects: the dashboard's
order chain had no `advance_paid` branch (a deposited order still read
"Contract Signed"), and `orders/view` kept a second hand-written copy of the
process stages in its sidebar whose colours had already drifted from the
stepper at the top of the same page. That sidebar is now `process_list()`,
reading the same `order_process_steps()`.

Two vocabularies were deliberately kept OUT of `DOCUMENT_STATUS`, because the
same word means something else:

* `document_file` — the lifecycle of a printed file is not the lifecycle of the
  document it prints. A quotation can be approved while a PDF of it is
  superseded by a reprint.
* `handover_item` — `partial` on an acceptance line is *partially accepted*.
  Under the document map it would have read "Partially Paid".

Caveat on the lint itself: its first version contained a stray character that
made it match nothing, and it passed while catching nothing. Any lint added
here must be proved against a known-bad string before it is trusted.


The stepper now sits directly under the order title, so "which step is my
order on" is answered before any reading. The detailed timeline below still
carries the documents and the actions; the stepper just answers the question
first. A waived advance is drawn distinctly there too, consistent with the
timeline fix.

**Long forms — save button fixed.** 14 data-entry screens are long enough to
push Save below the fold (`payments/create.html` 592 lines, `contracts/create`
446, `handover/create` 406, down to `materials/create` 269). Their action row
is now pinned to the bottom of the viewport while there is still form below,
so Save is always reachable — a user who scrolls and loses the button cannot
tell whether their work was saved at all.

A lint test keeps this true: any create/edit template over 250 lines must pin
its actions. The test deliberately ignores *view* pages — their buttons sit
next to the thing they act on, and pinning those would be wrong.

Still open on these screens: grouping the fields into labelled sections. The
save button was the part that actually blocked people; sectioning is polish.
