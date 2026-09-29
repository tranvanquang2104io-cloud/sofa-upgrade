"""Five order-level actions, offered twice each, in two different sizes.

`orders/view.html` put "Record advance payment", "Create handover" and
"Record final payment" both inside the timeline AND in the Quick Actions
panel — at `btn-sm` in one place and full size in the other, so they read as
two different things rather than one thing twice. The audit counted five
actions and ten buttons.

For somebody who is not technical, that is worse than clutter. Two buttons
that do the same thing invite the question "what is the difference?", and
there is no answer. Clicking the wrong one is impossible, but not knowing that
is its own tax.

THE SPLIT, and the reason for it:

  * the TIMELINE keeps actions that belong to a document shown in it —
    approve THIS quotation, sign THIS contract, print THIS payment. Those are
    about a specific record, and they belong beside it.
  * QUICK ACTIONS keeps order-level "what do I do next" — record the advance,
    create the handover, take the final payment. Those are about the ORDER,
    not about any row, and a panel that answers "what now?" is exactly what a
    person opens an order to find out.

Neither element disappears, so the screen still looks like itself. That is
what "đồng bộ cấu trúc, giữ diện mạo" asks for: one source per action, same
appearance.

Also removed: the `process_list(order)` call. The screen drew its progress
twice — the timeline and a sidebar badge list from the shared macro. The
macro's docstring says it exists because the hand-written copy had drifted and
"had no notion of a skipped advance". That is no longer true: the timeline has
handled `advance_skipped` since an earlier fix, in three places. So the reason
for the second rendering is gone, and the richer one — the one with the dates,
the documents and the context — is the one that stays.
"""
import io
import pathlib
import re

ORDER_SCREEN = (pathlib.Path(__file__).resolve().parents[1] / 'app'
                / 'templates' / 'orders' / 'view.html')

#: Order-level actions: about the order, not about any one document.
ORDER_LEVEL = {
    'create_payment': 'record a payment',
    'create_handover': 'create the handover',
}


def _text():
    return io.open(ORDER_SCREEN, encoding='utf-8').read()


def test_each_order_level_action_is_offered_once():
    """Two buttons for one action ask a question with no answer."""
    text = _text()

    offered = {}
    for endpoint in ORDER_LEVEL:
        # `?type=final` makes the final payment a distinct action from the
        # advance, so they are counted separately rather than lumped together.
        advance = len(re.findall(
            rf"dashboard\.{endpoint}', order_id=order\.id\) \}}\}}\"", text))
        final = len(re.findall(
            rf"dashboard\.{endpoint}', order_id=order\.id\) \}}\}}\?type=final",
            text))
        offered[endpoint] = advance
        if final:
            offered[f'{endpoint} (final)'] = final

    duplicated = {name: count for name, count in offered.items() if count > 1}
    assert not duplicated, (
        f'these actions are offered more than once on one screen: '
        f'{duplicated}. Two buttons that do the same thing invite "what is '
        f'the difference?", and there is no answer.')


def test_the_progress_is_drawn_once():
    """The timeline or the sidebar list — not both."""
    text = _text()
    # The CALL, not the word: the comment explaining the removal names the
    # macro, and a test that cannot tell an invocation from a mention would
    # forbid documenting the decision.
    assert '{{ process_list(' not in text, (
        'the order screen still draws its progress twice: the hand-written '
        'timeline and the shared sidebar macro')


def test_the_timeline_survives():
    """The richer rendering is the one that stays; the screen keeps its face."""
    text = _text()
    assert text.count('timeline-marker') >= 5, (
        'the timeline was removed — that is a different change from removing '
        'the duplicate, and it is not the one that was decided')


def test_document_specific_actions_stay_in_the_timeline():
    """Approving THIS quotation belongs beside this quotation."""
    text = _text()
    for endpoint in ('approve_quotation', 'sign_contract'):
        assert endpoint in text, (
            f'{endpoint} disappeared from the order screen; the split was '
            f'meant to move order-level actions, not document ones')


def test_the_screen_still_renders(client, login, app, seed):
    """The whole point is that nothing broke while tidying."""
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-ONEHOME',
                      title='Sofa goc L', total_amount=10_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       contract_created=True,
                                       contract_signed=True))
        db.session.commit()
        order_id = str(order.id)

    login('admin')
    response = client.get(f'/orders/{order_id}')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'DH-ONEHOME' in body
    # The order-level action is still reachable — moved, not deleted.
    assert 'create_payment' in body or 'payments/create' in body or \
        '/payment/' in body, 'recording a payment is no longer offered at all'
