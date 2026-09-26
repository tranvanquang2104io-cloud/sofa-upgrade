"""Record what changed a stock figure, and why.

One function, called from the four places that move stock: receiving, issuing,
transferring, and the hand adjustment. Keeping it in one place is the point —
a fifth caller that forgets to record is a gap in the history, and a history
with gaps is worse than none because it invites trust it cannot carry.

It never changes stock itself. The caller does that and then says what it did;
mixing the two would mean a movement that writes a balance, and there would be
no way to tell the account from the thing it accounts for.
"""
from decimal import Decimal

from app.config import db


def record(company_id, material_id, store_id, quantity, movement_type,
           ref_type=None, ref_id=None, warehouse_id=None, notes=None,
           user_id=None):
    """Write one movement. `quantity` is the CHANGE — signed, never the total.

    Returns None for a zero change: a line saying nothing happened is noise in
    the one place that has to stay readable.
    """
    from app.models.models import StockMovement

    change = Decimal(str(quantity or 0))
    if change == 0:
        return None

    if user_id is None:
        # Best effort: the session is not available in every caller (a script,
        # a migration), and a movement without a name is still worth far more
        # than no movement.
        try:
            from flask import session
            user_id = session.get('user_id')
        except Exception:
            user_id = None

    movement = StockMovement(
        company_id=company_id, material_id=material_id, store_id=store_id,
        warehouse_id=warehouse_id, quantity=change,
        movement_type=movement_type, ref_type=ref_type, ref_id=ref_id,
        notes=notes, created_by_id=user_id)
    db.session.add(movement)
    return movement
