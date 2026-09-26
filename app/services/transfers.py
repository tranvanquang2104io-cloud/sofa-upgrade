"""Move material from one warehouse to another, with a document behind it.

Correcting misplaced stock by editing two quantities by hand is two chances to
mistype and no record of why. This makes it one action with one reason written
on it.

Both sides move or neither does. A transfer that debits the source and then
fails destroys stock, which is worse than the problem it exists to solve — so
every line is checked before any line is touched.
"""
from decimal import Decimal

from app.config import db


def _dec(value):
    return Decimal(str(value or 0))


def _warehouse(company_id, warehouse_id, label):
    from app.models.models import Warehouse

    warehouse = Warehouse.query.get(warehouse_id) if warehouse_id else None
    if warehouse is None or str(warehouse.company_id) != str(company_id):
        # Refused, not substituted — the same rule as receiving and issuing.
        # Quietly using this company's default would move stock somewhere
        # nobody named.
        raise ValueError(f'{label} không thuộc công ty này')
    return warehouse


def _next_number(company_id):
    from app.models.models import StockTransfer

    count = StockTransfer.query.filter_by(company_id=company_id).count()
    return f'DC-{count + 1:04d}'


def _stock_row(company_id, material_id, store_id, create=False):
    from app.models.models import MaterialStock

    row = MaterialStock.query.filter_by(material_id=material_id,
                                        store_id=store_id).first()
    if row is None and create:
        row = MaterialStock(company_id=company_id, material_id=material_id,
                            store_id=store_id, current_quantity=Decimal('0'))
        db.session.add(row)
    return row


def transfer_stock(company_id, from_warehouse_id, to_warehouse_id, lines,
                   transfer_date, notes=None, transfer_number=None):
    """Move `lines` between two warehouses and record why.

    `lines` is a list of ``{material_id, quantity, unit}``.

    Raises ValueError — and touches nothing — if a warehouse is not this
    company's, if the two are the same, if a quantity is not positive, or if
    any line asks for more than the source holds.
    """
    from app.models.models import StockTransfer, StockTransferLine

    source = _warehouse(company_id, from_warehouse_id, 'Kho xuất')
    destination = _warehouse(company_id, to_warehouse_id, 'Kho nhận')
    if str(source.id) == str(destination.id):
        # Not pedantry: it would look like work and change nothing, and the
        # person would go on believing the stock had moved.
        raise ValueError('Kho xuất và kho nhận phải khác nhau')
    if not lines:
        raise ValueError('Chưa chọn vật tư nào để điều chuyển')

    # Check EVERY line before touching any of them. Checking as we go would
    # leave the first lines moved and the rest not, which is the failure this
    # is meant to prevent.
    planned = []
    for line in lines:
        quantity = _dec(line.get('quantity'))
        if quantity <= 0:
            raise ValueError('Số lượng điều chuyển phải lớn hơn 0')
        row = _stock_row(company_id, line['material_id'], source.store_id)
        held = _dec(row.current_quantity) if row else Decimal('0')
        if held < quantity:
            from app.models.models import Material
            material = Material.query.get(line['material_id'])
            name = material.name if material else line['material_id']
            raise ValueError(
                f'{name}: kho xuất chỉ còn {held}, không đủ {quantity}')
        planned.append((line, quantity, row))

    transfer = StockTransfer(
        company_id=company_id, from_warehouse_id=source.id,
        to_warehouse_id=destination.id,
        transfer_number=transfer_number or _next_number(company_id),
        transfer_date=transfer_date, notes=notes)
    db.session.add(transfer)
    db.session.flush()

    for line, quantity, row in planned:
        row.current_quantity = _dec(row.current_quantity) - quantity
        arriving = _stock_row(company_id, line['material_id'],
                              destination.store_id, create=True)
        arriving.current_quantity = _dec(arriving.current_quantity) + quantity
        # The destination now physically holds it; say so on the row, the same
        # way receiving does.
        arriving.warehouse_id = destination.id
        db.session.add(StockTransferLine(
            transfer_id=transfer.id, material_id=line['material_id'],
            quantity=quantity, unit=line.get('unit')))

    db.session.commit()
    return transfer
