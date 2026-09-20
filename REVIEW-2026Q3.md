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

**3.1 A signed contract cannot be cancelled anywhere.**
`Contract.can_cancel()` requires `not is_signed`. In bespoke furniture a
customer backing out after signing is a normal event, and today it has no home
in the system: cancelling the *order* leaves the signed contract dangling.
Options: allow cancelling a signed contract with a mandatory reason, or have
"Huỷ đơn hàng" cascade to its contract. **Which matches how you actually
handle this?**

**3.2 Bàn giao + Thanh toán cuối are one checkbox.**
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
