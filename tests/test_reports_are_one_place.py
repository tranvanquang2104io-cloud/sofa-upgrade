"""Reports belong under Reports — behind the Reports permission.

The owner's ask: "Dashboard, Báo cáo, Công nợ khách hàng … bản chất đang là
những Báo cáo, vậy nên hãy gom về thành 1 chức năng thôi."

Three things were wrong, and the third is a permission hole:

1. **The Reports page linked to no report.** `/reports` showed three cards of
   figures and no way through to anything. The one real report the product has
   was not on it.
2. **Customer debt was filed under Administration**, in the dropdown beside
   Stores, Users and Company Settings — so a report sat among the settings, and
   the Reports menu did not know about it.
3. **It was guarded by the wrong permission.** `feature_for_endpoint` matches
   substrings of the endpoint name, and `customer_receivables` hits the
   `customer` rule before anything else — so who owes the company money was
   readable by anyone granted Khách hàng, and NOT by someone granted Báo cáo.
   Exactly the trap that put supplier invoices under the inventory permission.

The dashboard is deliberately NOT folded in here: it is also the landing page
after login, and what should happen to it is the owner's call, not mine.
"""
import pytest

from app.utils.auth_utils import feature_for_endpoint


def test_the_debt_report_is_behind_the_reports_permission():
    assert feature_for_endpoint('dashboard.customer_receivables') == 'reports', (
        'who owes the company money is readable by anyone granted Khách hàng'
    )


def test_the_customers_screen_keeps_its_own_permission():
    """Narrowing one endpoint must not move a whole area."""
    assert feature_for_endpoint('dashboard.list_customers') == 'customers'
    assert feature_for_endpoint('dashboard.view_customer') == 'customers'


def test_a_user_with_only_customers_cannot_read_the_debt_report(app, client,
                                                                login, seed):
    from app.config import db
    from app.models.models import User

    with app.app_context():
        user = User.query.filter_by(username='staff').first()
        user.allowed_features = ['customers']
        db.session.commit()

    login('staff')
    assert client.get('/reports/receivables').status_code == 403


def test_a_user_granted_reports_can_read_it(app, client, login, seed):
    from app.config import db
    from app.models.models import User

    with app.app_context():
        user = User.query.filter_by(username='staff').first()
        user.allowed_features = ['reports']
        db.session.commit()

    login('staff')
    assert client.get('/reports/receivables').status_code == 200


def test_the_reports_page_leads_to_the_reports(client, login, seed):
    """A hub that leads nowhere is a page of numbers, not a hub."""
    login('admin')
    body = client.get('/reports').get_data(as_text=True)
    assert '/reports/receivables' in body, (
        'the Reports page does not link to the debt report'
    )


def test_the_debt_report_is_not_filed_under_administration(client, login,
                                                           seed):
    """It was in the dropdown beside Stores, Users and Company Settings."""
    import re

    login('admin')
    body = client.get('/').get_data(as_text=True)
    # Anchored on the RENDERED href, not on the url_for that produced it —
    # the first version of this searched the page for template source.
    admin_menu = re.search(r'href="/stores".*?</ul>', body, re.S)
    assert admin_menu, 'the administration menu did not render'
    assert '/reports/receivables' not in admin_menu.group(0), (
        'a report is still filed among the settings'
    )
