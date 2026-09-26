"""Which permission area every endpoint belongs to, written out by hand.

This replaces a resolver that matched SUBSTRINGS of the endpoint name. That
mechanism produced three live defects in a single review pass — supplier
invoices under Kho, customer receivables under Khách hàng, framework agreements
behind nothing at all — and each fix made the next one more fragile, because
the cure was to order the rules so that `supplier_invoice` was tested before
`supplier` and `receivable` before `customer`. A rule list whose correctness
depends on its order is a rule list that the next endpoint breaks.

The deeper problem is that a name is not a fact about where something belongs.
`list_supplier_invoices` is about money owed and merely *contains* the word for
the stock area; `save_plan_norm` contains no area's word at all and so was
gated by nothing. Selection by name misses whatever is named differently — the
same shape that made a screen audit report 44 of 66 screens, and a
reachability check count a form's own action as a link.

So: no inference. One line per endpoint, and an endpoint that is not on the
list does not run. `UnmappedEndpoint` is the question being asked — a new route
cannot reach a user until somebody has said which area it belongs to.

`None` means the endpoint is not feature-gated: either it is pre-login or the
dashboard home, or it is an admin screen carrying its own role decorator
(`@company_admin_required` / `@store_admin_required`). That is a claim about
each row, not a fallback — `ADMIN_SCREENS` below records which of them are
admin screens so the test can check the decorator is really there.
"""


class UnmappedEndpoint(Exception):
    """A dashboard endpoint nobody has assigned to a permission area."""


ENDPOINT_FEATURE = {
    # --- gated by a permission area ---------------------------------
    'add_agreement_price':             'orders',
    'add_plan_material':               'orders',
    'approve_quotation':               'orders',
    'cancel_contract':                 'orders',
    'cancel_handover':                 'orders',
    'cancel_order':                    'orders',
    'cancel_order_confirmation':       'orders',
    'cancel_payment':                  'orders',
    'cancel_quotation':                'orders',
    'change_agreement_status':         'orders',
    'confirm_handover':                'orders',
    'confirm_payment':                 'orders',
    'confirm_supplier_invoice':        'purchasing',
    'convert_requisition':             'purchasing',
    'create_agreement':                'orders',
    'create_contract':                 'orders',
    'create_customer':                 'customers',
    'create_handover':                 'orders',
    'create_material':                 'inventory',
    'create_order':                    'orders',
    'create_payment':                  'orders',
    'create_purchase_order':           'purchasing',
    'create_quotation':                'orders',
    'create_requisition':              'purchasing',
    'create_supplier_invoice':         'purchasing',
    'customer_receivables':            'reports',
    'deactivate_customer':             'customers',
    'deactivate_material':             'inventory',
    'delete_document':                 'orders',
    'delete_plan_material':            'orders',
    'download_document':               'orders',
    'edit_agreement':                  'orders',
    'edit_contract':                   'orders',
    'edit_customer':                   'customers',
    'edit_handover':                   'orders',
    'edit_material':                   'inventory',
    'edit_order':                      'orders',
    'edit_payment':                    'orders',
    'edit_purchase_order':             'purchasing',
    'edit_quotation':                  'orders',
    'edit_requisition':                'purchasing',
    'generate_document':               'orders',
    'get_contract_api':                'orders',
    'get_quotation_detail':            'orders',
    'issue_order_confirmation':        'orders',
    'issue_plan_materials':            'inventory',
    'list_agreements':                 'orders',
    'list_customers':                  'customers',
    'list_documents':                  'orders',
    'list_goods_receipts':             'purchasing',
    'list_materials':                  'inventory',
    'list_orders':                     'orders',
    'list_production_plans':           'orders',
    'list_purchase_orders':            'purchasing',
    'list_requisitions':               'purchasing',
    'list_supplier_invoices':          'purchasing',
    'low_stock_materials':             'inventory',
    'material_categories':             'inventory',
    'material_suppliers':              'inventory',
    'material_units':                  'inventory',
    'pay_supplier_invoice':            'purchasing',
    'print_production_plan':           'orders',
    'print_purchase_order':            'purchasing',
    'production_plan_delay':           'orders',
    'production_plan_status':          'orders',
    'purchase_order_status':           'purchasing',
    'purchase_suggestions':            'purchasing',
    'receive_purchase_order':          'purchasing',
    'reports':                         'reports',
    'requisition_status':              'purchasing',
    'save_plan_norm':                  'orders',
    'set_plan_material_warehouse':     'orders',
    'sign_contract':                   'orders',
    'skip_advance_payment':            'orders',
    'update_material_stock':           'inventory',
    'view_agreement':                  'orders',
    'view_contract':                   'orders',
    'view_customer':                   'customers',
    'view_goods_receipt':              'purchasing',
    'view_handover':                   'orders',
    'view_material':                   'inventory',
    'view_order':                      'orders',
    'view_payment':                    'orders',
    'view_production_plan':            'orders',
    'view_purchase_order':             'purchasing',
    'view_quotation':                  'orders',
    'view_requisition':                'purchasing',
    'view_supplier_invoice':           'purchasing',

    # --- not feature-gated (see the module docstring) ----------------
    'list_stock_transfers':            None,
    'create_stock_transfer':           None,
    'create_warehouse':                None,
    'deactivate_warehouse':            None,
    'edit_warehouse':                  None,
    'list_warehouses':                 None,
    'activate_template':               None,
    'check_code':                      None,
    'company_settings':                None,
    'create_store':                    None,
    'create_user':                     None,
    'deactivate_store':                None,
    'deactivate_template':             None,
    'deactivate_user':                 None,
    'delete_template':                 None,
    'edit_store':                      None,
    'edit_user':                       None,
    'extension_fields_settings':       None,
    'get_next_code':                   None,
    'index':                           None,
    'list_stores':                     None,
    'list_templates':                  None,
    'list_users':                      None,
    'serve_item_image':                None,
    'set_language':                    None,
    'standardization_settings':        None,
    'upload_template':                 None,
    'workflow_settings':               None,
}

#: The subset of the `None` rows that are admin screens. They are ungated
#: HERE because a role decorator gates them THERE; the test checks it exists.
ADMIN_SCREENS = frozenset({
    'list_stock_transfers',
    'create_stock_transfer',
    'create_warehouse',
    'deactivate_warehouse',
    'edit_warehouse',
    'list_warehouses',
    'activate_template',
    'company_settings',
    'create_store',
    'create_user',
    'deactivate_store',
    'deactivate_template',
    'deactivate_user',
    'delete_template',
    'edit_store',
    'edit_user',
    'extension_fields_settings',
    'list_stores',
    'list_templates',
    'list_users',
    'standardization_settings',
    'upload_template',
    'workflow_settings',
})


def feature_for_endpoint(endpoint):
    """The permission area gating `endpoint`, or None if it is not gated.

    Raises `UnmappedEndpoint` for a dashboard endpoint nobody has written down.
    Fail closed: the caller turns that into a refusal, so a route that was
    forgotten is unreachable rather than open.
    """
    if not endpoint or not endpoint.startswith('dashboard.'):
        return None
    name = endpoint.split('.', 1)[1]
    try:
        return ENDPOINT_FEATURE[name]
    except KeyError:
        raise UnmappedEndpoint(name)
