# -*- coding: utf-8 -*-
"""Seed sofa-industry material Categories + Units of measure for a company.

Based on typical sofa manufacturing / gia công (upholstery, foam, frame, springs,
legs, adhesives, hardware, thread, webbing, packaging).

Usage:
    venv/Scripts/python.exe scripts/seed_sofa_taxonomy.py [COMPANY_CODE]
Without a code, seeds all active companies. Idempotent (matches by name).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# (name, description)
CATEGORIES = [
    ('Vải bọc',             'Vải bọc sofa: nỉ, bố, nhung, canvas…'),
    ('Da (thật & simili)',  'Da bò thật, da công nghiệp PU/simili'),
    ('Mút & Gòn',           'Mút cao su, mút PU (foam), gòn bông'),
    ('Khung gỗ',            'Gỗ tự nhiên, gỗ dán (plywood), MDF'),
    ('Lò xo',               'Lò xo túi, lò xo zigzag/dây rằng'),
    ('Chân sofa',           'Chân gỗ, kim loại, nhựa'),
    ('Keo & Hóa chất',      'Keo dán, dung môi, sơn hoàn thiện'),
    ('Phụ kiện kim khí',    'Ốc vít, bản lề, ray trượt, ke góc'),
    ('Chỉ may & Khóa kéo',  'Chỉ may bọc, dây kéo (zipper)'),
    ('Dây đai & Thun',      'Dây đai (webbing), dây thun co giãn'),
    ('Bao bì đóng gói',     'Thùng carton, màng PE, xốp bọc'),
]

# (name, abbreviation, description)
UNITS = [
    ('m²',        'm2',  'Mét vuông (vải, da, mút tấm)'),
    ('Mét dài',   'm',   'Mét dài (vải, dây đai)'),
    ('Kg',        'kg',  'Ki-lô-gam (mút, gòn, keo)'),
    ('Cái',       '',    'Đơn vị cái'),
    ('Bộ',        '',    'Bộ (khung, chân)'),
    ('Cuộn',      '',    'Cuộn (chỉ, dây đai, màng PE)'),
    ('Tấm',       '',    'Tấm (ván ép, mút tấm)'),
    ('Lít',       'L',   'Lít (keo, sơn lỏng)'),
    ('Thùng',     '',    'Thùng (bao bì)'),
    ('Hộp',       '',    'Hộp (ốc vít, phụ kiện)'),
    ('Con',       '',    'Con (lò xo, đơn vị lẻ)'),
]


def seed_taxonomy(company_id):
    """Idempotently add the sofa categories + units to one company. Returns
    (n_categories_added, n_units_added). Caller commits."""
    from app.models.models import MaterialCategory, MaterialUnit
    from app.config import db
    nc = nu = 0
    for i, (name, desc) in enumerate(CATEGORIES):
        if not MaterialCategory.query.filter_by(company_id=company_id, name=name).first():
            db.session.add(MaterialCategory(company_id=company_id, name=name,
                                            description=desc, sort_order=i))
            nc += 1
    for name, abbr, desc in UNITS:
        if not MaterialUnit.query.filter_by(company_id=company_id, name=name).first():
            db.session.add(MaterialUnit(company_id=company_id, name=name,
                                        abbreviation=abbr or None, description=desc))
            nu += 1
    db.session.commit()
    return nc, nu


def main():
    from app import create_app
    from app.models.models import Company
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        code = sys.argv[1] if len(sys.argv) > 1 else None
        q = Company.query
        companies = [q.filter_by(company_code=code).first()] if code else q.filter_by(is_active=True).all()
        for co in filter(None, companies):
            nc, nu = seed_taxonomy(co.id)
            print(f'{co.company_code}: +{nc} categories, +{nu} units')


if __name__ == '__main__':
    main()
