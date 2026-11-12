import random
import sqlite3
from datetime import datetime, date
from database import get_db, db_transaction
from services.audit_service import log_action

def generate_simulated_reference(prefix="SIM-MUKO"):
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    rand_suffix = random.randint(1000, 9999)
    return f"{prefix}-{timestamp}-{rand_suffix}"

def calculate_outstanding_balance(loan_id, conn=None):
    if conn is None:
        conn = get_db()
    loan = conn.execute("SELECT principal_minor, fee_minor FROM loans WHERE id = ?", (loan_id,)).fetchone()
    if not loan:
        return 0, 0, 0, 0, 0

    principal = loan['principal_minor']
    fee = loan['fee_minor'] or 0
    total_due = principal + fee

    repaid_row = conn.execute(
        "SELECT COALESCE(SUM(amount_minor), 0) as total FROM repayments WHERE loan_id = ? AND amount_minor > 0",
        (loan_id,)
    ).fetchone()
    total_repaid = repaid_row['total'] if repaid_row else 0
    outstanding = max(0, total_due - total_repaid)

    return principal, fee, total_due, total_repaid, outstanding

def record_repayment(loan_id, amount_minor, reference, user_id, payment_date=None):
    """
    Records a simulated repayment and updates loan status if settled in full.
    """
    if type(loan_id) is not int or loan_id <= 0 or type(user_id) is not int or user_id <= 0:
        return False, "Invalid loan or user."

    if type(amount_minor) is not int or amount_minor <= 0:
        return False, "Repayment amount must be positive."

    conn = get_db()
    clean_ref = reference.strip() if reference else generate_simulated_reference()
    if len(clean_ref) > 100:
        return False, "Repayment reference cannot exceed 100 characters."

    pay_date = payment_date or date.today().isoformat()
    try:
        parsed_pay_date = datetime.strptime(pay_date, "%Y-%m-%d").date()
        if parsed_pay_date.isoformat() != pay_date or parsed_pay_date > date.today():
            return False, "Invalid repayment date. Please use YYYY-MM-DD."
    except (ValueError, TypeError):
        return False, "Invalid repayment date. Please use YYYY-MM-DD."

    try:
        with db_transaction(conn):
            conn.execute("BEGIN IMMEDIATE")
            loan = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
            if not loan:
                return False, "Loan record not found."

            # Global administrators may record a payment on behalf of a borrower.
            actor = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
            if loan['borrower_id'] != user_id and (not actor or actor['role'] != 'admin'):
                return False, "Only the borrower or a global administrator may record payments on this loan."

            if loan['status'] not in ('active', 'overdue'):
                return False, f"Loan is not eligible for repayments (Current status: {loan['status'].replace('_', ' ').title()})."

            _, _, total_due, _, outstanding = calculate_outstanding_balance(loan_id, conn=conn)
            if amount_minor > outstanding:
                amount_text = f"${outstanding // 100}.{outstanding % 100:02d}"
                return False, f"Repayment amount cannot exceed the outstanding balance of {amount_text}."

            existing_ref = conn.execute(
                "SELECT id FROM repayments WHERE reference = ?", (clean_ref,)
            ).fetchone()
            if existing_ref:
                return False, "That repayment reference has already been recorded."

            cursor = conn.execute("""
                INSERT INTO repayments (loan_id, amount_minor, reference, recorded_by, payment_date)
                VALUES (?, ?, ?, ?, ?)
            """, (loan_id, amount_minor, clean_ref, user_id, pay_date))
            repayment_id = cursor.lastrowid
            new_outstanding = outstanding - amount_minor
            is_fully_repaid = new_outstanding == 0

            if is_fully_repaid:
                conn.execute("UPDATE loans SET status = 'repaid' WHERE id = ?", (loan_id,))

            action_name = 'REPAYMENT_SETTLED_FULL' if is_fully_repaid else 'REPAYMENT_RECORDED_PARTIAL'
            log_action(user_id, action_name, 'repayment', repayment_id, conn=conn)
    except sqlite3.IntegrityError:
        existing_ref = conn.execute(
            "SELECT id FROM repayments WHERE reference = ?", (clean_ref,)
        ).fetchone()
        if existing_ref:
            return False, "That repayment reference has already been recorded."
        raise

    return True, {
        'repayment_id': repayment_id,
        'reference': clean_ref,
        'amount_minor': amount_minor,
        'remaining_minor': new_outstanding,
        'is_fully_repaid': is_fully_repaid
    }

def get_loan_repayments(loan_id):
    conn = get_db()
    return conn.execute("""
        SELECT r.*, u.full_name as recorder_name
        FROM repayments r
        JOIN users u ON r.recorded_by = u.id
        WHERE r.loan_id = ?
        ORDER BY r.payment_date DESC, r.created_at DESC
    """, (loan_id,)).fetchall()

def get_user_repayments(user_id):
    conn = get_db()
    return conn.execute("""
        SELECT r.*, l.id as loan_id, l.currency, l.principal_minor,
               l.borrower_id,
               b.full_name as borrower_name, ln.full_name as lender_name,
               c.name as community_name
        FROM repayments r
        JOIN loans l ON r.loan_id = l.id
        JOIN loan_requests lr ON l.request_id = lr.id
        JOIN communities c ON lr.community_id = c.id
        JOIN users b ON l.borrower_id = b.id
        JOIN users ln ON l.lender_id = ln.id
        WHERE l.borrower_id = ? OR l.lender_id = ?
        ORDER BY r.payment_date DESC, r.created_at DESC
    """, (user_id, user_id)).fetchall()
