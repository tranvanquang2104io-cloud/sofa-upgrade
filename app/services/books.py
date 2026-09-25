"""Whether a document's period is already closed, and what to say if it is.

A workshop this size files VAT quarterly and corporate tax annually. Once a
return is filed, the figures in it are a statement to the tax office; editing
or cancelling a document dated inside that period makes what the system says
permanently differ from what was declared, and at an inspection there is
nothing to reconcile the two with. Luật Kế toán 2015 Đ.27 puts it the other
way round: a record may be corrected, never erased, and every lawful
correction — a correcting entry, a negative entry, an additional one — points
forward rather than rewriting the past.

One date does the work: ``Company.books_closed_through``. It is empty until
somebody sets it, so a company that has not asked for this notices nothing.

Deliberately NOT in this module:

* any notion of a period longer than "up to this date". Quarterly, monthly and
  annual filing all reduce to the same question — is this document older than
  the last thing I declared — and a calendar of periods would be a second
  model of the same fact;
* automatic closing. The system does not know when a return was filed, and
  guessing would lock people out of their own records on a date nobody chose.
"""


def is_in_a_closed_period(document_date, company):
    """True when `document_date` falls in a period already declared.

    A missing date is NOT in a closed period. `None < some_date` raises in
    Python 3 rather than quietly answering, but a caller that reaches here with
    None should get a straight answer instead of an exception at the point of
    use — and the safe answer is "not locked", because locking a record on the
    strength of a date nobody recorded would be refusing without a reason.
    """
    if document_date is None:
        return False
    closed_through = getattr(company, 'books_closed_through', None)
    if closed_through is None:
        return False
    return document_date <= closed_through


def _document_date(document):
    """The date the books care about.

    A payment carries two — `report_date` is when the document was raised and
    `payment_date` is when the money moved — and it is the second that a return
    reports. Anything else uses whichever single date it has.
    """
    for attribute in ('payment_date', 'report_date', 'receipt_date',
                      'invoice_date', 'handover_date', 'contract_date',
                      'quotation_date', 'order_date'):
        value = getattr(document, attribute, None)
        if value is not None:
            return value
    return None


def may_change(document, company=None):
    """``(allowed, reason)`` for editing or cancelling ``document``.

    Returns a reason a person can act on, not just a refusal: naming the date
    and where to change it is the difference between a user who asks the
    bookkeeper and a user who asks somebody to edit the database.

    A draft is always allowed. It is not in the books — the same distinction
    `PaymentReport.can_edit()` already draws between confirmed and not — so
    closing a period must not freeze work in progress that was never declared.
    """
    from app.utils.i18n import t

    if not _is_posted(document):
        return True, ''

    if company is None:
        company = _company_of(document)
    if company is None:
        # Reaching here means the document has no company_id, which the schema
        # forbids. Allowing the change is the only safe answer — refusing on a
        # company nobody can name gives a message nobody can act on — but the
        # first version of this reached here for EVERY payment, because it read
        # a `company` relationship that PaymentReport does not have. The lock
        # then silently never applied: a compliance control that fails open is
        # worse than one that is absent, because it looks present.
        return True, ''

    date = _document_date(document)
    if not is_in_a_closed_period(date, company):
        return True, ''

    closed = company.books_closed_through
    # Two short keys, not one long one split across source lines. An implicit
    # concatenation gives the translation scanner only its FIRST fragment as
    # the key, while `t()` receives the whole joined string at runtime — so the
    # entry would never match and the message would come out untranslated.
    return False, '{locked} {what}'.format(
        locked=t('Sổ sách đã khoá đến ngày {date}.').format(
            date=closed.strftime('%d/%m/%Y')),
        what=t('Kỳ này đã kê khai nên chứng từ không sửa hay huỷ trực tiếp được. Hãy lập chứng từ điều chỉnh mang ngày hôm nay, hoặc nhờ người phụ trách kê khai đổi ngày khoá sổ ở Thiết lập công ty.'))


def _company_of(document):
    """Resolve the owning company from `company_id`, not from a relationship.

    Every document table carries `company_id` (NOT NULL); only some declare a
    `company` relationship, and reading one that is not there returns None
    rather than raising — which is how the check above silently passed.
    """
    company_id = getattr(document, 'company_id', None)
    if company_id is None:
        return None
    from app.models import Company
    return Company.query.get(company_id)


def _is_posted(document):
    """Has this document entered the books?

    Each kind says so differently — a payment by `is_confirmed`, a goods
    receipt by `is_posted`, a supplier invoice by a status. Asking each in its
    own words beats inventing a shared flag nothing sets.
    """
    if getattr(document, 'is_confirmed', None) is not None:
        return bool(document.is_confirmed)
    if getattr(document, 'is_posted', None) is not None:
        return bool(document.is_posted)
    status = getattr(document, 'status', None)
    if status is not None:
        return status not in ('draft', 'canceled')
    # Nothing marks it either way: treat it as posted. A document whose state
    # cannot be read is the one worth being careful with.
    return True
