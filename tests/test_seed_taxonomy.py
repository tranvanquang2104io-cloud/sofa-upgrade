"""Sofa-industry material taxonomy seed."""
import os
import sys


def test_seed_sofa_taxonomy_idempotent(app, seed):
    sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))
    from seed_sofa_taxonomy import seed_taxonomy, CATEGORIES, UNITS
    from app.models.models import MaterialCategory, MaterialUnit
    cid = seed["company_id"]
    with app.app_context():
        nc, nu = seed_taxonomy(cid)
        assert nc == len(CATEGORIES) and nu == len(UNITS)
        # second run adds nothing
        assert seed_taxonomy(cid) == (0, 0)
        assert MaterialCategory.query.filter_by(company_id=cid).count() == len(CATEGORIES)
        assert MaterialUnit.query.filter_by(company_id=cid).count() == len(UNITS)
