"""Every endpoint's permission, written down.

`feature_for_endpoint` decides by matching SUBSTRINGS of the endpoint name, and
in a single review pass that produced three live defects:

* `list_supplier_invoices` matched the `supplier` rule, meant for the supplier
  master, and landed under Kho — so granting stock access granted the ability
  to record and confirm money owed.
* `customer_receivables` matched `customer` before `report`, so who owes the
  company money was readable by anyone granted Khách hàng and not by someone
  granted Báo cáo.
* `list_agreements` matched nothing at all and was behind no permission.

None of those is visible from the user form: the tick boxes look complete
whatever the map does. So the map is pinned here in full. Adding an endpoint
fails this test until somebody writes down where it belongs, which is the point
— the failure is the question being asked.

SETTLED (§8.7). Three production actions used to sit behind Kho because their
names contain "material". Editing a job's material list is production work, so
`add_plan_material` and `delete_plan_material` now sit with **orders**;
`issue_plan_materials` genuinely deducts stock and stays with **inventory**.

`save_plan_norm` is the fourth of that shape and nobody had seen it: its name
contains no area's word, so it matched nothing and was gated by nothing. It is
on the same screen as the three above and now sits with them.

The map is no longer inferred from names at all — see
`app/utils/permission_map.py`. An endpoint absent from it raises rather than
passing, so the next route of this shape cannot be quietly ungated.
"""
import pytest

from app.utils.auth_utils import feature_for_endpoint

EXPECTED = {
    'activate_template': None,
    'add_agreement_price': 'orders',
    'add_plan_material': 'orders',
    'approve_quotation': 'orders',
    'cancel_contract': 'orders',
    'cancel_handover': 'orders',
    'cancel_order': 'orders',
    'cancel_order_confirmation': 'orders',
    'cancel_payment': 'orders',
    'cancel_quotation': 'orders',
    'change_agreement_status': 'orders',
    'check_code': None,
    'company_settings': None,
    'confirm_handover': 'orders',
    'confirm_payment': 'orders',
    'confirm_supplier_invoice': 'purchasing',
    'convert_requisition': 'purchasing',
    'create_agreement': 'orders',
    'create_contract': 'orders',
    'create_customer': 'customers',
    'create_handover': 'orders',
    'create_material': 'inventory',
    'create_order': 'orders',
    'create_payment': 'orders',
    'create_purchase_order': 'purchasing',
    'create_quotation': 'orders',
    'create_requisition': 'purchasing',
    'create_store': None,
    'create_supplier_invoice': 'purchasing',
    'create_user': None,
    'customer_receivables': 'reports',
    'deactivate_customer': 'customers',
    'deactivate_material': 'inventory',
    'deactivate_store': None,
    'deactivate_template': None,
    'deactivate_user': None,
    'delete_document': 'orders',
    'delete_plan_material': 'orders',
    'delete_template': None,
    'download_document': 'orders',
    'edit_agreement': 'orders',
    'edit_contract': 'orders',
    'edit_customer': 'customers',
    'edit_handover': 'orders',
    'edit_material': 'inventory',
    'edit_order': 'orders',
    'edit_payment': 'orders',
    'edit_purchase_order': 'purchasing',
    'edit_quotation': 'orders',
    'edit_requisition': 'purchasing',
    'edit_store': None,
    'edit_user': None,
    'extension_fields_settings': None,
    'generate_document': 'orders',
    'get_contract_api': 'orders',
    'get_next_code': None,
    'get_quotation_detail': 'orders',
    'index': None,
    'issue_order_confirmation': 'orders',
    'issue_plan_materials': 'inventory',
    'list_agreements': 'orders',
    'list_customers': 'customers',
    'list_documents': 'orders',
    'list_goods_receipts': 'purchasing',
    'list_materials': 'inventory',
    'list_orders': 'orders',
    'list_production_plans': 'orders',
    'list_purchase_orders': 'purchasing',
    'list_requisitions': 'purchasing',
    'list_stores': None,
    'list_supplier_invoices': 'purchasing',
    'list_templates': None,
    'list_users': None,
    'low_stock_materials': 'inventory',
    'material_categories': 'inventory',
    'material_suppliers': 'inventory',
    'material_units': 'inventory',
    'pay_supplier_invoice': 'purchasing',
    'print_production_plan': 'orders',
    'print_purchase_order': 'purchasing',
    'production_plan_delay': 'orders',
    'production_plan_status': 'orders',
    'purchase_order_status': 'purchasing',
    'purchase_suggestions': 'purchasing',
    'receive_purchase_order': 'purchasing',
    'reports': 'reports',
    'requisition_status': 'purchasing',
    'save_plan_norm': 'orders',
    'list_approvals': None,
    'decide_approval': None,
    'list_stock_transfers': None,
    'create_stock_transfer': None,
    'set_plan_material_warehouse': 'orders',
    'create_warehouse': None,
    'deactivate_warehouse': None,
    'edit_warehouse': None,
    'list_warehouses': None,
    'serve_item_image': None,
    'set_language': None,
    'sign_contract': 'orders',
    'skip_advance_payment': 'orders',
    'standardization_settings': None,
    'update_material_stock': 'inventory',
    'upload_template': None,
    'view_agreement': 'orders',
    'view_contract': 'orders',
    'view_customer': 'customers',
    'view_goods_receipt': 'purchasing',
    'view_handover': 'orders',
    'view_material': 'inventory',
    'view_order': 'orders',
    'view_payment': 'orders',
    'view_production_plan': 'orders',
    'view_purchase_order': 'purchasing',
    'view_quotation': 'orders',
    'view_requisition': 'purchasing',
    'view_supplier_invoice': 'purchasing',
    'workflow_settings': None,
}


def test_the_permission_map_is_complete(app):
    """A new endpoint must be given a home, not inherit one by accident."""
    live = {rule.endpoint.split('.', 1)[1]
            for rule in app.url_map.iter_rules()
            if rule.endpoint.startswith('dashboard.')}

    unlisted = sorted(live - set(EXPECTED))
    assert unlisted == [], (
        'these endpoints are new and nobody has said which permission guards '
        f'them: {unlisted}')

    stale = sorted(set(EXPECTED) - live)
    assert stale == [], f'these endpoints no longer exist: {stale}'


@pytest.mark.parametrize('endpoint', sorted(EXPECTED))
def test_each_endpoint_resolves_to_the_permission_it_was_given(endpoint):
    assert feature_for_endpoint('dashboard.' + endpoint) == EXPECTED[endpoint]
