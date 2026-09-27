"""Which branch's paperwork the person in front of us may act on.

`BaseRepository.get_by_id` carries a docstring that predicted this exactly:

    Tenant safety is therefore the caller's responsibility. ... this default is
    a standing hazard: the next route that forgets leaks another company's
    data, and nothing in the type signature warns about it.

It was right about the shape and understated the reach. Every detail route does
check the COMPANY -- the sweep in `tests/test_tenant_isolation_sweep.py`
confirms it, and that sweep cannot see any more than that, because it builds one
store per company. With a single store, scoping to the company and scoping to
the store are the same assertion.

`OrderService.get_order` closed the order itself. It could not close the child
documents, because they are not reached through the order: `/contracts/<id>/
sign` takes a contract id, loads it with `ContractRepository().get_by_id`, and
never touches the order at all.

So the check goes here, at the one place all of them pass through. Not on the
thirteen routes: several of those routes call the repository directly rather
than the service, so a fix in the service layer would have left them open --
and the next route added would be open again.

The rule: a child document whose order belongs to a branch this user is not in
READS AS ABSENT. Not an exception, not a 403 from deep inside a query -- the
callers already handle `None` as "not found or access denied", which is also
the right thing to tell someone: an id they may not have is an id that, as far
as they are concerned, does not exist.

Outside a request there is no user, so nothing is refused. Seeds, migrations,
Alembic and the test fixtures act on nobody's behalf.
"""
import logging

logger = logging.getLogger(__name__)


def order_is_within_reach(order) -> bool:
    """Whether the current user may act on this order and its paperwork."""
    if order is None:
        return True
    try:
        from flask import has_request_context, session
        if not has_request_context() or 'user_id' not in session:
            return True

        company_id = session.get('company_id')
        if company_id and str(order.company_id) != str(company_id):
            return False

        from app.utils.auth_utils import get_accessible_store_ids
        allowed = get_accessible_store_ids(order.company_id)
    except Exception:
        # An access check must never become a 500. The routes keep their own
        # company guard, so failing open here lands on the behaviour that was
        # in place before this module existed rather than on a blank screen.
        logger.exception('Could not resolve store scope; letting the route '
                         'guard decide')
        return True

    return (order.store_id in allowed
            or str(order.store_id) in {str(s) for s in allowed})


def within_branch(row):
    """Return ``row``, or ``None`` if its order belongs to another branch.

    A row with no order -- a company-level document, a template -- is returned
    untouched: its scope is the company, which the callers already check.
    """
    if row is None:
        return None
    if not hasattr(row, 'order_id'):
        return row
    order = getattr(row, 'order', None)
    if order is None:
        return row
    return row if order_is_within_reach(order) else None


def usable_store(company_id, store_id):
    """The branch a document may be written to, or ValueError.

    `store_id` arrives raw from a form. `@store_admin_required` establishes
    only that somebody is an admin of SOME branch, so without this a branch
    manager could post another branch's id and have stock written there.

    Refused rather than quietly replaced with a default: receiving into
    somewhere nobody named is how stock ends up in a place that cannot be
    explained afterwards. The caller decides what to do with no answer at all
    (`None` in, `None` out) -- usually falling back to the document's own
    branch, which is a stated default rather than a silent substitution.
    """
    if store_id is None:
        return None

    from app.models.models import Store

    store = Store.query.get(store_id)
    if store is None or str(store.company_id) != str(company_id):
        raise ValueError('Chi nhánh không thuộc công ty này')

    # NOT `order_is_within_reach(store)`. That reads `.store_id`, which a
    # Store does not have -- it has `.id`. The AttributeError would be caught
    # by that function's fail-open `except`, and this check would silently
    # pass for every branch. Written out instead.
    try:
        from flask import has_request_context, session
        if not has_request_context() or 'user_id' not in session:
            return store
        from app.utils.auth_utils import get_accessible_store_ids
        allowed = get_accessible_store_ids(company_id)
    except Exception:
        logger.exception('Could not resolve store scope for %s', store_id)
        return store

    if not (store.id in allowed or str(store.id) in {str(s) for s in allowed}):
        raise ValueError('Bạn không có quyền với chi nhánh này')
    return store
