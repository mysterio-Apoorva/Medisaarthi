"""Explicit local administrator/doctor provisioning, without synthetic patients."""
import argparse
from getpass import getpass
import os
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--role', choices=['ADMIN', 'DOCTOR'], required=True)
    args = parser.parse_args()
    os.environ['SEED_DEMO_DATA'] = 'false'
    from backend.app.security import LoginInput
    from backend.app.store import Store, now, store
    password = getpass('New password (at least 10 characters): ')
    if password != getpass('Confirm password: '):
        parser.error('Passwords do not match')
    credentials = LoginInput(email=args.email, password=password)
    name = args.name.strip()
    if not 2 <= len(name) <= 150:
        parser.error('Name must contain 2–150 characters')
    store.initialize()
    with store.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM users WHERE email=?', (credentials.email,)).fetchone():
            parser.error('This email already exists; no account was changed')
        identifier = f'USR_{uuid4().hex}'
        db.execute('INSERT INTO users(user_id,email,password_hash,role,display_name,created_at) VALUES(?,?,?,?,?,?)', (identifier, credentials.email, Store.hash_password(credentials.password), args.role, name, now()))
        store.audit(db, identifier, 'STAFF_PROVISIONED_LOCALLY', 'USER', identifier, {'role': args.role})
    print(f'Created {args.role} account {identifier} in {store.path.resolve()}')


if __name__ == '__main__':
    main()
