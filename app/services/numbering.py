"""One way to work out the next document number.

There were two. The one in the `next_code` API endpoint reads the highest
suffix actually in use; the one in `transfers.py` counted rows and added one.
The second is wrong as soon as anything is deleted: void one of three
transfers and the next one is numbered DC-0003, which already exists. On
`stock_transfers` that hits a unique constraint, so it is not a silent
duplicate -- it is a clerk who cannot record a real movement of stock, with no
explanation of why the same action worked yesterday.

The counting version was mine, written during this refactor. It is deleted
rather than fixed in place, because the right version was already here.

The endpoint's version had itself been fixed twice, and both fixes are kept:

1. The company filter was loaded but never applied, so numbers were computed
   across every tenant in the database.
2. `regexp_replace` is PostgreSQL-only, so the endpoint raised 500 on any
   other backend -- and could not be covered by the test suite, which runs on
   SQLite. The suffix is therefore parsed in Python.

Parsing in Python also handles what real data looks like: a table whose first
few hundred rows came out of a spreadsheet has numbers like `DC-CU/2024` in
it. Those are skipped, not crashed on.

WHAT THIS DOES NOT DO: make concurrent saves safe. Two people can read the
same highest number at the same instant; the numbered tables carry unique
constraints, so the data stays correct and the loser gets an IntegrityError
rather than a duplicate. The missing piece is a retry on conflict, recorded as
its own task. Not claimed here, because a comment claiming safety that is not
there is worse than the gap itself.
"""


def next_document_number(model, field_name, prefix, company_id, width=3):
    """The next unused number for `model`, within one company.

    `width` is the zero-padding: `DC-0001` (4) for transfers, `ORD-001` (3)
    for the screens that were already using three.
    """
    from app.config.database import db

    column = getattr(model, field_name)
    rows = db.session.query(column).filter(
        model.company_id == company_id,
        column.like(f'{prefix}%'),
    ).all()

    highest = 0
    for (value,) in rows:
        suffix = (value or '')[len(prefix):]
        if suffix.isdigit():
            highest = max(highest, int(suffix))

    return f'{prefix}{highest + 1:0{width}d}'
