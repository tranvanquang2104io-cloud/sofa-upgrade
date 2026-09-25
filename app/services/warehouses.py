"""Which warehouse a document means, and whether to ask the user at all.

The rule that keeps this from making the product worse for the people who have
one address:

    **Ask which warehouse only when the company has more than one.**

Not a setting. A switch in Settings would be a question put to somebody who
does not yet have the problem, and — worse — it can disagree with the data:
create a second warehouse, forget to turn the switch on, and every receipt
keeps landing in the first one while the screens say nothing. The act of
creating a second warehouse IS the thing that turns the choice on, and it means
something in the business, which a checkbox does not.

So a workshop with one location sees no new field anywhere. The day it opens a
second store, the fields appear, already filled in with the warehouse it has
been using.

Resolution is a cascade, and the order matters:

    1. what the user chose on this document
    2. the default warehouse of the location the document belongs to
    3. the company's default warehouse

There is deliberately no step 4 saying "or any warehouse with stock in it".
That was the old `_stock_for` fallback in another costume: taking material from
a warehouse nobody named is an undocumented transfer, and an inventory with
undocumented transfers in it stops being worth reading.
"""


def warehouses_of(company_id):
    """Every active warehouse a company has, cheapest query first."""
    from app.models.models import Warehouse

    return (Warehouse.query
            .filter_by(company_id=company_id, is_active=True)
            .order_by(Warehouse.warehouse_code)
            .all())


def must_choose(company_id):
    """True when the company has more than one warehouse to choose between.

    The screens use this to decide whether to render a warehouse field at all.
    One warehouse means there is nothing to ask about, and asking anyway is how
    a simple product becomes a form nobody finishes.
    """
    return len(warehouses_of(company_id)) > 1


def default_for_store(store_id, company_id=None):
    """The warehouse a document at this location reaches for when nobody chose.

    Falls back to the company's own default when the location has none of its
    own — a branch that sells but stores nothing still has to receive goods
    somewhere, and refusing would block the work rather than protect anything.
    """
    from app.models.models import Warehouse

    if store_id is not None:
        own = (Warehouse.query
               .filter_by(store_id=store_id, is_active=True)
               .order_by(Warehouse.is_default.desc(),
                         Warehouse.warehouse_code)
               .first())
        if own is not None:
            return own
    if company_id is None:
        return None
    return default_for_company(company_id)


def default_for_company(company_id):
    """The company's default warehouse, or its only one, or nothing.

    Returns None rather than guessing when a company has several and none is
    marked default. The caller then has to ask — which is right: picking one
    for them would put stock somewhere nobody chose, and that is the whole
    failure this module exists to prevent.
    """
    from app.models.models import Warehouse

    marked = (Warehouse.query
              .filter_by(company_id=company_id, is_active=True,
                         is_default=True)
              .first())
    if marked is not None:
        return marked

    all_of_them = warehouses_of(company_id)
    return all_of_them[0] if len(all_of_them) == 1 else None


def resolve(company_id, chosen_id=None, store_id=None):
    """The warehouse a document means: chosen > the location's > the company's.

    `chosen_id` is what the user picked, and it wins whenever it is given —
    including over a location's default, because a person who names a warehouse
    has said something the defaults cannot know.
    """
    from app.models.models import Warehouse

    if chosen_id:
        chosen = Warehouse.query.get(chosen_id)
        if chosen is not None and str(chosen.company_id) == str(company_id):
            return chosen
        # A warehouse id from another company is not a fallback case; it is
        # either a mistake or an attempt, and either way silently substituting
        # this company's default would put the stock somewhere nobody asked for.
        raise ValueError('Kho không thuộc công ty này')

    return default_for_store(store_id, company_id)
