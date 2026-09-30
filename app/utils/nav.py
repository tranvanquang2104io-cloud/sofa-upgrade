"""Which top-menu item a screen belongs to.

The menu used to decide this with substring tests on the endpoint name —
`'order' in request.endpoint` and so on. Words inside other words made that
wrong in both directions, measured over all 77 screens:

* every purchase-order screen lit up Orders AND Purchasing (`purchase_order`
  contains `order`), and Customer Debt lit up Customers AND Reports;
* nine screens lit up nothing — warehouses, stock transfers, approvals, supplier
  invoices, an order's documents — so the user could not see where they were.

Written out by hand instead, the way `permission_map.py` is: a new screen has
to be placed on purpose, and `test_nav_sections.py` fails until it is.
"""

_SECTIONS = {
    'home': (
        'index',
    ),
    # Bán hàng: orders, their customers, and framework agreements share one menu.
    'sales': (
        'list_customers', 'create_customer', 'view_customer', 'edit_customer',
        'list_orders', 'create_order', 'view_order', 'edit_order',
        'create_quotation', 'view_quotation', 'edit_quotation',
        'create_contract', 'view_contract', 'edit_contract',
        'create_handover', 'view_handover', 'edit_handover',
        'create_payment', 'view_payment', 'edit_payment',
        'list_documents',
        'list_agreements', 'create_agreement', 'view_agreement', 'edit_agreement',
    ),
    'production': (
        'list_production_plans', 'view_production_plan',
    ),
    'inventory': (
        'list_materials', 'create_material', 'view_material', 'edit_material',
        'material_categories', 'material_units', 'material_suppliers',
        'list_warehouses', 'create_warehouse', 'edit_warehouse',
        'list_stock_transfers', 'create_stock_transfer',
    ),
    'purchasing': (
        'purchase_suggestions',
        'list_requisitions', 'create_requisition', 'view_requisition', 'edit_requisition',
        'list_purchase_orders', 'create_purchase_order', 'view_purchase_order',
        'edit_purchase_order',
        'list_goods_receipts', 'view_goods_receipt',
        'list_supplier_invoices', 'create_supplier_invoice', 'view_supplier_invoice',
    ),
    'reports': (
        'reports', 'customer_receivables',
    ),
    'approvals': (
        'list_approvals',
    ),
    'admin': (
        'list_stores', 'create_store', 'edit_store',
        'list_users', 'create_user', 'edit_user',
        'list_templates', 'company_settings', 'extension_fields_settings',
        'workflow_settings', 'standardization_settings',
    ),
}

# GET endpoints that are not screens a person stands on: files, JSON, prints,
# the language switch. They belong to no menu item, and saying so is the point.
NOT_A_SCREEN = frozenset({
    'download_document', 'download_template', 'serve_item_image',
    'print_production_plan', 'print_purchase_order',
    'get_contract_api', 'get_next_code', 'get_quotation_detail',
    'set_language',
})

SECTION_OF = {endpoint: section
              for section, endpoints in _SECTIONS.items()
              for endpoint in endpoints}


def nav_section(endpoint):
    """The menu item for a `dashboard.*` endpoint, or None."""
    if not endpoint or not endpoint.startswith('dashboard.'):
        return None
    return SECTION_OF.get(endpoint.split('.', 1)[1])
