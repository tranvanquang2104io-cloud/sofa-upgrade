"""Product master + reconciliation of the free-text names already in use.

F11, phase 1. The app has never had a product entity: every quotation,
contract, handover and order-confirmation line carries a typed product NAME,
and `MaterialNorm.product_key` matches on a lowercased version of it.

Introducing a master data table over years of free text is where this kind of
migration usually goes wrong, so the order here is deliberate:

    1. scan what names are ACTUALLY in the data and report them, grouped,
       with near-duplicates flagged — change nothing;
    2. let the owner look at that list and correct it;
    3. only then create products and point the documents at them.

This module does 1 and 2. It deliberately does NOT rewrite any document.
"""
import logging
import re
from collections import defaultdict

from app.config.database import db
from app.models.models import (
    Contract,
    HandoverRecord,
    MaterialNorm,
    OrderConfirmation,
    Product,
    Quotation,
)
from app.utils.text_normalize import strip_diacritics, to_nfc

logger = logging.getLogger(__name__)

# Documents whose `items` JSON holds free-text product names.
ITEM_SOURCES = (
    ('quotation', Quotation),
    ('contract', Contract),
    ('handover', HandoverRecord),
    ('order_confirmation', OrderConfirmation),
)


def match_key(name):
    """Normalized key for matching a free-text name to a product.

    Mirrors ``MaterialNorm.product_key`` (lowercase + strip) so phase 2 can
    link existing norms without inventing a second rule.
    """
    return to_nfc(name or '').strip().lower()


def fuzzy_key(name):
    """A looser key used ONLY to spot near-duplicates for human review.

    Diacritics removed, punctuation dropped, whitespace collapsed — so
    "Sofa 3 chỗ", "sofa 3 cho" and "Sofa  3  chỗ." group together. This is a
    review aid, never an automatic merge: only a person can tell whether
    "Sofa 3 chỗ" and "Sofa 3 chỗ da bò" are the same product.
    """
    text = strip_diacritics(to_nfc(name or '')).lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()



def _merge_counts(dicts):
    """Sum per-source counts across a group's spelling variants."""
    merged = defaultdict(int)
    for d in dicts:
        for key, value in d.items():
            merged[key] += value
    return dict(merged)


def _iter_document_names(company_id):
    """Yield (source, name, unit, unit_price) for every line item on file."""
    for label, model in ITEM_SOURCES:
        rows = model.query.filter_by(company_id=company_id).all()
        for row in rows:
            for item in (row.items or []):
                name = (item.get('name') or '').strip()
                if not name:
                    continue
                yield label, name, item.get('unit'), item.get('unit_price')


def reconcile(company_id):
    """Report the distinct product names in use. Creates nothing.

    Returns a list of groups, most-used first::

        {
          'match_key':   canonical key of the most common spelling,
          'name':        the most common spelling itself,
          'variants':    [{'name', 'count'}, ...]   # all spellings in the group
          'total_count': how many document lines use any spelling
          'sources':     {'quotation': 3, 'contract': 1, ...}
          'units':       ['bộ', 'cái']              # units seen
          'prices':      {'min': .., 'max': ..}     # price spread
          'needs_review': True when the group has more than one spelling
          'existing_product_id': set when a Product already matches
        }
    """
    counts = defaultdict(int)
    sources = defaultdict(lambda: defaultdict(int))
    units = defaultdict(set)
    prices = defaultdict(list)

    for source, name, unit, price in _iter_document_names(company_id):
        counts[name] += 1
        sources[name][source] += 1
        if unit:
            units[name].add(str(unit))
        try:
            if price is not None:
                prices[name].append(float(price))
        except (TypeError, ValueError):
            pass

    # Material norms reference product names too, and a norm that matches
    # nothing is precisely the silent failure this feature exists to stop.
    for norm in MaterialNorm.query.filter_by(company_id=company_id).all():
        key = (norm.product_key or '').strip()
        if key:
            counts[key] += 0          # register without inflating usage
            sources[key]['material_norm'] += 1

    groups = defaultdict(list)
    for name in counts:
        groups[fuzzy_key(name)].append(name)

    existing = {p.match_key: str(p.id)
                for p in Product.query.filter_by(company_id=company_id).all()}

    report = []
    for _fkey, names in groups.items():
        names.sort(key=lambda n: (-counts[n], n))
        primary = names[0]
        all_prices = [p for n in names for p in prices.get(n, [])]
        report.append({
            'match_key': match_key(primary),
            'name': primary,
            'variants': [{'name': n, 'count': counts[n]} for n in names],
            'total_count': sum(counts[n] for n in names),
            # Counts must be SUMMED across the spelling variants. A dict
            # comprehension here silently kept only the last variant's count,
            # so a product spelled two ways reported half its real usage.
            'sources': _merge_counts(sources.get(n, {}) for n in names),
            'units': sorted({u for n in names for u in units.get(n, set())}),
            'prices': ({'min': min(all_prices), 'max': max(all_prices)}
                       if all_prices else None),
            'needs_review': len(names) > 1,
            'existing_product_id': existing.get(match_key(primary)),
        })

    report.sort(key=lambda g: (-g['total_count'], g['name']))
    return report


def summarize(report):
    """Headline numbers for the reconciliation screen."""
    return {
        'distinct_products': len(report),
        'needing_review': sum(1 for g in report if g['needs_review']),
        'already_created': sum(1 for g in report if g['existing_product_id']),
        'total_lines': sum(g['total_count'] for g in report),
        'price_spread': sum(
            1 for g in report
            if g['prices'] and g['prices']['max'] > g['prices']['min']),
    }


def create_from_group(company_id, group, product_code=None):
    """Create ONE product from a reconciliation group, on explicit request.

    Never called in bulk automatically: a wrong merge here would quietly
    combine two real products, and un-merging afterwards means editing
    historical documents.
    """
    key = group['match_key']
    existing = Product.query.filter_by(company_id=company_id,
                                       match_key=key).first()
    if existing:
        return existing

    if not product_code:
        seq = Product.query.filter_by(company_id=company_id).count() + 1
        product_code = f'SP-{seq:04d}'

    product = Product(
        company_id=company_id,
        product_code=product_code,
        name=group['name'],
        match_key=key,
        unit=(group['units'][0] if group.get('units') else None),
        default_price=(group['prices']['max'] if group.get('prices') else None),
        source='reconciled',
    )
    db.session.add(product)
    db.session.commit()
    logger.info("Product %s created from reconciliation (%s lines)",
                product_code, group['total_count'])
    return product
