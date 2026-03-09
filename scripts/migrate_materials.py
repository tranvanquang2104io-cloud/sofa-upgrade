"""
Migration: Add Material Management tables
Adds: material_units, material_categories, materials, material_stock
Run once against a live database (dev or prod).
"""
import os
import sys

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config.database import db

CREATE_MATERIAL_UNITS = """
CREATE TABLE IF NOT EXISTS material_units (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name        VARCHAR(50) NOT NULL,
    abbreviation VARCHAR(20),
    description VARCHAR(255),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_company_unit_name UNIQUE (company_id, name)
);
CREATE INDEX IF NOT EXISTS ix_material_units_company_id ON material_units(company_id);
CREATE INDEX IF NOT EXISTS ix_material_units_is_active  ON material_units(is_active);
"""

CREATE_MATERIAL_CATEGORIES = """
CREATE TABLE IF NOT EXISTS material_categories (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id  UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_company_category_name UNIQUE (company_id, name)
);
CREATE INDEX IF NOT EXISTS ix_material_categories_company_id ON material_categories(company_id);
CREATE INDEX IF NOT EXISTS ix_material_categories_is_active  ON material_categories(is_active);
"""

CREATE_MATERIALS = """
CREATE TABLE IF NOT EXISTS materials (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id       UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    category_id      UUID REFERENCES material_categories(id) ON DELETE SET NULL,
    unit_id          UUID REFERENCES material_units(id) ON DELETE SET NULL,
    material_code    VARCHAR(50) NOT NULL,
    name             VARCHAR(255) NOT NULL,
    description      TEXT,
    color            VARCHAR(100),
    specifications   JSONB NOT NULL DEFAULT '{}',
    unit_price       NUMERIC(15,2) NOT NULL DEFAULT 0,
    supplier_name    VARCHAR(255),
    supplier_contact VARCHAR(100),
    min_stock_level  NUMERIC(10,2) NOT NULL DEFAULT 0,
    image_path       VARCHAR(500),
    notes            TEXT,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_company_material_code UNIQUE (company_id, material_code)
);
CREATE INDEX IF NOT EXISTS ix_materials_company_id  ON materials(company_id);
CREATE INDEX IF NOT EXISTS ix_materials_category_id ON materials(category_id);
CREATE INDEX IF NOT EXISTS ix_materials_unit_id     ON materials(unit_id);
CREATE INDEX IF NOT EXISTS ix_materials_name        ON materials(name);
CREATE INDEX IF NOT EXISTS ix_materials_is_active   ON materials(is_active);
"""

CREATE_MATERIAL_STOCK = """
CREATE TABLE IF NOT EXISTS material_stock (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    material_id      UUID NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    company_id       UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    store_id         UUID REFERENCES stores(id) ON DELETE CASCADE,
    current_quantity NUMERIC(10,2) NOT NULL DEFAULT 0,
    notes            TEXT,
    last_updated     TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at       TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_material_store_stock UNIQUE (material_id, store_id)
);
CREATE INDEX IF NOT EXISTS ix_material_stock_material_id ON material_stock(material_id);
CREATE INDEX IF NOT EXISTS ix_material_stock_company_id  ON material_stock(company_id);
CREATE INDEX IF NOT EXISTS ix_material_stock_store_id    ON material_stock(store_id);
"""


def run_migration():
    env = os.environ.get('FLASK_ENV', 'development')
    app = create_app(env)
    with app.app_context():
        conn = db.engine.raw_connection()
        cur  = conn.cursor()
        try:
            steps = [
                ('material_units',      CREATE_MATERIAL_UNITS),
                ('material_categories', CREATE_MATERIAL_CATEGORIES),
                ('materials',           CREATE_MATERIALS),
                ('material_stock',      CREATE_MATERIAL_STOCK),
            ]
            for table_name, sql in steps:
                print(f'  → Creating {table_name} ...', end=' ')
                cur.execute(sql)
                conn.commit()
                print('OK')
            print('\n✅  Migration complete — 4 tables created/verified.')
        except Exception as e:
            conn.rollback()
            print(f'\n❌  Migration failed: {e}')
            raise
        finally:
            cur.close()
            conn.close()


if __name__ == '__main__':
    run_migration()
