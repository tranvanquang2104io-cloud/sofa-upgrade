"""
Bootstrap script: creates the master_admins table and the first master admin account.

Usage:
    python create_master_admin.py
    python create_master_admin.py --username admin --password secret123 --name "Quản Trị Viên"
"""
import sys
import argparse

from app import create_app
from app.config.database import db
from app.models.models import MasterAdmin


def main():
    parser = argparse.ArgumentParser(description='Create master admin account')
    parser.add_argument('--username', default='masteradmin')
    parser.add_argument('--password', default='Admin@2024!')
    parser.add_argument('--name',     default='Master Administrator')
    parser.add_argument('--email',    default='admin@sofaflow.local')
    args = parser.parse_args()

    import os
    env = os.environ.get('FLASK_ENV', 'development')
    app = create_app(env)
    with app.app_context():
        # Create table if not exists
        db.create_all()

        existing = MasterAdmin.query.filter_by(username=args.username).first()
        if existing:
            print(f"Master admin '{args.username}' already exists.")
            return

        admin = MasterAdmin(
            username=args.username,
            email=args.email,
            full_name=args.name,
        )
        admin.set_password(args.password)
        db.session.add(admin)
        db.session.commit()
        print(f"✓ Master admin created!")
        print(f"  Username : {args.username}")
        print(f"  Password : {args.password}")
        print(f"  Login at : http://localhost:5000/admin/login")


if __name__ == '__main__':
    main()
