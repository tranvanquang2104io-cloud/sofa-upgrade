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

**Chữ ký số (digital signature).** There is no document-lifecycle service to
hook into: generation logic is split between `template_engine.py` and the
route file, with no `draft → generated → signed` state on a document. A
signing step would have to be threaded through route handlers.

**Chatbot AI.** It needs stable functions to ask ("trạng thái đơn này", "còn
nợ bao nhiêu"). Today `dashboard_routes.py` is ~4,400 lines and holds more
logic than the entire `app/services/` directory combined (~3,600 lines), and
there are only 3 JSON endpoints in the whole app.

**The same small change unblocks both:** extract a thin `DocumentService` with
an explicit status, and expose a handful of JSON endpoints over the existing
services. Worth doing *before* either feature, not during.

---

## 6. UI consistency — measured, not guessed

| Pattern | Adoption |
|---|---|
| `page_header()` | 12 of 77 templates |
| `status_badge()` | 10 templates, while ~30 still hand-build badges |
| `process_stepper()` | **0 — built and never used** |

The stepper is the clearest single win available: it shows a non-technical
user exactly where their order is, in one glance, and the component already
exists.

Long forms needing sectioning and a sticky save button: `contracts/create.html`
(446 lines) and `handover/create.html` (406) — on a laptop the save button is
below the fold after a long scroll.
