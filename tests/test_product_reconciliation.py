"""F11 phase 1: the product master and the reconciliation report.

The report is the point. Introducing master data over years of free text is
where this kind of migration goes wrong, so nothing is created automatically —
the tool shows what is in the data and a human decides.
"""
import datetime as dt

import pytest

from app.models.models import Product
from app.services import product_service as ps


def _items(*names_with_qty):
    return [{'name': n, 'unit': u, 'quantity': 1, 'unit_price': p,
             'total': p} for n, u, p in names_with_qty]


@pytest.fixture()
def documents(app, seed):
    """Quotations/contracts carrying the same product spelled several ways."""
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, Quotation

    with app.app_context():
        order = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                      customer_id=seed["customer_id"], order_code="ORD-P1",
                      title="Recon order")
        db.session.add(order)
        db.session.flush()

        db.session.add(Quotation(
            company_id=seed["company_id"], order_id=order.id,
            quotation_number="QT-P1", quotation_date=dt.date(2026, 1, 1),
            total_amount=0,
            items=_items(('Sofa 3 chỗ', 'bộ', 10_000_000),
                         ('Ghế đơn', 'cái', 2_000_000))))
        db.session.add(Quotation(
            company_id=seed["company_id"], order_id=order.id,
            quotation_number="QT-P2", quotation_date=dt.date(2026, 2, 1),
            total_amount=0,
            # same product, different spelling and a different price
            items=_items(('sofa 3 cho', 'bộ', 11_000_000))))
        db.session.add(Contract(
            company_id=seed["company_id"], order_id=order.id,
            contract_number="CT-P1", contract_date=dt.date(2026, 1, 5),
            contract_value=0,
            items=_items(('Sofa 3 chỗ', 'bộ', 10_000_000))))
        db.session.commit()
        return seed


# --- the report -----------------------------------------------------------

def test_reconcile_finds_the_distinct_products(app, documents):
    with app.app_context():
        report = ps.reconcile(documents["company_id"])
        names = {g['name'] for g in report}
        assert 'Sofa 3 chỗ' in names
        assert 'Ghế đơn' in names
        assert len(report) == 2, "the two spellings of the sofa are one product"


def test_spelling_variants_are_grouped_and_flagged_for_review(app, documents):
    """"Sofa 3 chỗ" and "sofa 3 cho" are the same thing typed twice."""
    with app.app_context():
        report = ps.reconcile(documents["company_id"])
        sofa = next(g for g in report if 'ofa' in g['name'])

        assert sofa['needs_review'] is True
        variants = {v['name'] for v in sofa['variants']}
        assert variants == {'Sofa 3 chỗ', 'sofa 3 cho'}


def test_the_most_used_spelling_becomes_the_suggested_name(app, documents):
    with app.app_context():
        report = ps.reconcile(documents["company_id"])
        sofa = next(g for g in report if 'ofa' in g['name'])
        assert sofa['name'] == 'Sofa 3 chỗ', "used twice vs once"


def test_report_counts_usage_across_document_types(app, documents):
    with app.app_context():
        report = ps.reconcile(documents["company_id"])
        sofa = next(g for g in report if 'ofa' in g['name'])
        assert sofa['total_count'] == 3
        assert sofa['sources']['quotation'] == 2
        assert sofa['sources']['contract'] == 1


def test_report_surfaces_a_price_spread(app, documents):
    """Two prices for one product is exactly what an owner needs to see."""
    with app.app_context():
        report = ps.reconcile(documents["company_id"])
        sofa = next(g for g in report if 'ofa' in g['name'])
        assert sofa['prices']['min'] == 10_000_000
        assert sofa['prices']['max'] == 11_000_000


def test_a_single_spelling_is_not_flagged_for_review(app, documents):
    with app.app_context():
        report = ps.reconcile(documents["company_id"])
        chair = next(g for g in report if g['name'] == 'Ghế đơn')
        assert chair['needs_review'] is False


def test_material_norms_appear_in_the_report(app, seed):
    """A norm whose product no longer exists is the silent failure F11 is about."""
    from app.config import db
    from app.models.models import (
        Material, MaterialCategory, MaterialNorm, MaterialUnit,
    )

    with app.app_context():
        unit = MaterialUnit(company_id=seed["company_id"], name="m")
        cat = MaterialCategory(company_id=seed["company_id"], name="v")
        db.session.add_all([unit, cat])
        db.session.flush()
        mat = Material(company_id=seed["company_id"], material_code="M-N1",
                       name="Vai", unit_id=unit.id, category_id=cat.id)
        db.session.add(mat)
        db.session.flush()
        db.session.add(MaterialNorm(company_id=seed["company_id"],
                                    product_key="sofa 3 cho",
                                    material_id=mat.id, quantity_per_unit=2))
        db.session.commit()

        report = ps.reconcile(seed["company_id"])
        keys = {g['match_key'] for g in report}
        assert 'sofa 3 cho' in keys


def test_reconcile_is_read_only(app, documents):
    """Phase 1 must not create anything by itself."""
    with app.app_context():
        ps.reconcile(documents["company_id"])
        assert Product.query.count() == 0


def test_reconcile_is_tenant_scoped(app, documents, seed):
    from app.config import db
    from app.models import Company

    with app.app_context():
        other = Company(company_code="PRD2", name="Other", email="o@p.test")
        db.session.add(other)
        db.session.commit()
        assert ps.reconcile(other.id) == []


def test_summary_numbers(app, documents):
    with app.app_context():
        summary = ps.summarize(ps.reconcile(documents["company_id"]))
        assert summary['distinct_products'] == 2
        assert summary['needing_review'] == 1
        assert summary['already_created'] == 0
        assert summary['price_spread'] == 1


# --- creating a product on request ---------------------------------------

def test_creating_a_product_from_a_group(app, documents):
    with app.app_context():
        report = ps.reconcile(documents["company_id"])
        sofa = next(g for g in report if 'ofa' in g['name'])

        product = ps.create_from_group(documents["company_id"], sofa)
        assert product.name == 'Sofa 3 chỗ'
        assert product.match_key == 'sofa 3 chỗ'
        assert product.unit == 'bộ'
        assert product.source == 'reconciled'
        assert product.product_code.startswith('SP-')


def test_creating_the_same_group_twice_is_idempotent(app, documents):
    with app.app_context():
        report = ps.reconcile(documents["company_id"])
        sofa = next(g for g in report if 'ofa' in g['name'])
        first = ps.create_from_group(documents["company_id"], sofa)
        second = ps.create_from_group(documents["company_id"], sofa)
        assert first.id == second.id
        assert Product.query.count() == 1


def test_an_already_created_product_is_marked_in_the_next_report(app, documents):
    with app.app_context():
        report = ps.reconcile(documents["company_id"])
        sofa = next(g for g in report if 'ofa' in g['name'])
        ps.create_from_group(documents["company_id"], sofa)

        again = ps.reconcile(documents["company_id"])
        sofa_again = next(g for g in again if 'ofa' in g['name'])
        assert sofa_again['existing_product_id'] is not None


# --- the matching keys ----------------------------------------------------

def test_match_key_mirrors_the_existing_material_norm_rule(app):
    assert ps.match_key('  Sofa 3 Chỗ ') == 'sofa 3 chỗ'


def test_fuzzy_key_groups_diacritics_and_punctuation(app):
    assert ps.fuzzy_key('Sofa 3 chỗ.') == ps.fuzzy_key('sofa  3 cho')


def test_fuzzy_key_does_not_merge_genuinely_different_products(app):
    """The reason merging stays a human decision."""
    assert ps.fuzzy_key('Sofa 3 chỗ') != ps.fuzzy_key('Sofa 3 chỗ da bò')
