import sqlite3
import os
from contextlib import contextmanager
from flask import g, current_app
from config import Config

def get_db_path():
    try:
        return current_app.config.get('DATABASE_PATH', Config.DATABASE_PATH)
    except RuntimeError:
        return Config.DATABASE_PATH

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(get_db_path(), timeout=20.0)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def get_standalone_connection(db_path=None):
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def db_transaction(conn=None):
    should_close = False
    if conn is None:
        conn = get_standalone_connection()
        should_close = True
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()

def init_db(db_path=None):
    conn = get_standalone_connection(db_path)
    cursor = conn.cursor()

    cursor.executescript('''
    -- Users Table
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user', -- 'user' or 'admin'
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- Communities Table (Mukando Groups & Savings Clubs)
    CREATE TABLE IF NOT EXISTS communities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        invite_code TEXT UNIQUE NOT NULL,
        created_by INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
    );

    -- Community Members Table
    CREATE TABLE IF NOT EXISTS community_members (
        community_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL DEFAULT 'member', -- 'admin' or 'member'
        joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (community_id, user_id),
        FOREIGN KEY (community_id) REFERENCES communities(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- Loan Requests Table (Stored in integer minor units - cents)
    CREATE TABLE IF NOT EXISTS loan_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        community_id INTEGER NOT NULL,
        borrower_id INTEGER NOT NULL,
        amount_minor INTEGER NOT NULL,
        currency TEXT NOT NULL DEFAULT 'USD',
        reason TEXT NOT NULL,
        proposed_due_date DATE NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'accepted', 'declined', 'cancelled', 'converted'
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (community_id) REFERENCES communities(id) ON DELETE CASCADE,
        FOREIGN KEY (borrower_id) REFERENCES users(id) ON DELETE CASCADE
    );

    -- Loans Table
    CREATE TABLE IF NOT EXISTS loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER UNIQUE NOT NULL,
        lender_id INTEGER NOT NULL,
        borrower_id INTEGER NOT NULL,
        principal_minor INTEGER NOT NULL,
        fee_minor INTEGER NOT NULL DEFAULT 0,
        currency TEXT NOT NULL DEFAULT 'USD',
        due_date DATE NOT NULL,
        borrower_accepted BOOLEAN NOT NULL DEFAULT 0,
        lender_accepted BOOLEAN NOT NULL DEFAULT 0,
        borrower_accepted_at DATETIME,
        lender_accepted_at DATETIME,
        status TEXT NOT NULL DEFAULT 'awaiting_agreement', -- 'awaiting_agreement', 'active', 'repaid', 'overdue', 'cancelled'
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (request_id) REFERENCES loan_requests(id) ON DELETE RESTRICT,
        FOREIGN KEY (lender_id) REFERENCES users(id) ON DELETE RESTRICT,
        FOREIGN KEY (borrower_id) REFERENCES users(id) ON DELETE RESTRICT
    );

    -- Repayments Table
    CREATE TABLE IF NOT EXISTS repayments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        loan_id INTEGER NOT NULL,
        amount_minor INTEGER NOT NULL,
        reference TEXT UNIQUE NOT NULL,
        recorded_by INTEGER NOT NULL,
        payment_date DATE NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (loan_id) REFERENCES loans(id) ON DELETE RESTRICT,
        FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE RESTRICT
    );

    -- Audit Log Table
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_id INTEGER,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL
    );

    -- Indexes for High Performance and Filtering
    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    CREATE INDEX IF NOT EXISTS idx_comm_members_user ON community_members(user_id);
    CREATE INDEX IF NOT EXISTS idx_comm_members_comm ON community_members(community_id);
    CREATE INDEX IF NOT EXISTS idx_requests_comm ON loan_requests(community_id);
    CREATE INDEX IF NOT EXISTS idx_requests_borrower ON loan_requests(borrower_id);
    CREATE INDEX IF NOT EXISTS idx_requests_status ON loan_requests(status);
    CREATE INDEX IF NOT EXISTS idx_loans_request ON loans(request_id);
    CREATE INDEX IF NOT EXISTS idx_loans_borrower ON loans(borrower_id);
    CREATE INDEX IF NOT EXISTS idx_loans_lender ON loans(lender_id);
    CREATE INDEX IF NOT EXISTS idx_loans_status ON loans(status);
    CREATE INDEX IF NOT EXISTS idx_loans_due ON loans(due_date);
    CREATE INDEX IF NOT EXISTS idx_repayments_loan ON repayments(loan_id);
    CREATE INDEX IF NOT EXISTS idx_repayments_ref ON repayments(reference);
    CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor_id);
    CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("MukoLend database initialized with complete Master Schema.")
