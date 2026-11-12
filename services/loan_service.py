from datetime import datetime, date, timedelta
from database import get_db, db_transaction
from services.audit_service import log_action
from services.repayment_service import calculate_outstanding_balance

def create_loan_request(community_id, borrower_id, amount_cents, currency, reason, proposed_due_date):
    if type(community_id) is not int or community_id <= 0:
        return None, "Select a valid community."

    if type(borrower_id) is not int or borrower_id <= 0:
        return None, "A valid borrower account is required."

    if type(amount_cents) is not int or amount_cents <= 0:
        return None, "Loan amount must be a positive number."

    if amount_cents > 1_000_000:
        return None, "Loan amount cannot exceed $10,000.00."

    clean_currency = (currency or "USD").strip().upper()
    if clean_currency != "USD":
        return None, "Only USD loan requests are currently supported."

    if not reason or len(reason.strip()) < 5:
        return None, "Please provide a clear reason for borrowing (at least 5 characters)."

    if len(reason.strip()) > 500:
        return None, "Reason description cannot exceed 500 characters."

    # Validate due date
    try:
        due = datetime.strptime(proposed_due_date, "%Y-%m-%d").date()
        if due <= date.today():
            return None, "Proposed repayment due date must be in the future."
    except (ValueError, TypeError):
        return None, "Invalid date format. Please use YYYY-MM-DD."

    conn = get_db()
    # Check community membership
    membership = conn.execute(
        "SELECT role FROM community_members WHERE community_id = ? AND user_id = ?",
        (community_id, borrower_id)
    ).fetchone()
    if not membership:
        return None, "You must be an active member of this community to request a loan."

    with db_transaction(conn):
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO loan_requests (community_id, borrower_id, amount_minor, currency, reason, proposed_due_date, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, (community_id, borrower_id, amount_cents, clean_currency, reason.strip(), proposed_due_date))
        request_id = cursor.lastrowid
        log_action(borrower_id, 'REQUEST_CREATED', 'loan_request', request_id, conn=conn)

    return request_id, None

def cancel_loan_request(request_id, user_id):
    conn = get_db()
    with db_transaction(conn):
        conn.execute("BEGIN IMMEDIATE")
        req = conn.execute("SELECT * FROM loan_requests WHERE id = ?", (request_id,)).fetchone()
        if not req:
            return False, "Loan request not found."

        if req['borrower_id'] != user_id:
            return False, "Only the borrower may cancel this loan request."

        if req['status'] != 'pending':
            return False, f"Cannot cancel request in '{req['status']}' state."

        updated = conn.execute(
            "UPDATE loan_requests SET status = 'cancelled' WHERE id = ? AND status = 'pending'",
            (request_id,)
        ).rowcount
        if not updated:
            return False, "This request has already changed status."

        log_action(user_id, 'REQUEST_CANCELLED', 'loan_request', request_id, conn=conn)
    return True, None

def accept_loan_request(request_id, lender_id, fee_minor=0):
    if type(request_id) is not int or request_id <= 0 or type(lender_id) is not int or lender_id <= 0:
        return None, "Invalid request or lender."

    if type(fee_minor) is not int or fee_minor < 0:
        return None, "Agreed fee must be a non-negative amount in cents."

    conn = get_db()
    with db_transaction(conn):
        conn.execute("BEGIN IMMEDIATE")
        req = conn.execute("""
            SELECT lr.*
            FROM loan_requests lr
            WHERE lr.id = ?
        """, (request_id,)).fetchone()

        if not req:
            return None, "Loan request not found."

        if req['borrower_id'] == lender_id:
            return None, "You cannot fund your own loan request."

        if req['status'] != 'pending':
            return None, "This loan request is no longer available for acceptance."

        membership = conn.execute(
            "SELECT 1 FROM community_members WHERE community_id = ? AND user_id = ?",
            (req['community_id'], lender_id)
        ).fetchone()
        if not membership:
            return None, "You must be a member of this community to fund this loan."

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updated = conn.execute(
            "UPDATE loan_requests SET status = 'accepted' WHERE id = ? AND status = 'pending'",
            (request_id,)
        ).rowcount

        if updated == 0:
            return None, "This request was just accepted by another member or has changed status."

        cursor = conn.execute("""
            INSERT INTO loans (
                request_id, lender_id, borrower_id, principal_minor, fee_minor,
                currency, due_date, borrower_accepted, lender_accepted,
                lender_accepted_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, ?, 'awaiting_agreement')
        """, (
            request_id, lender_id, req['borrower_id'], req['amount_minor'],
            fee_minor, req['currency'], req['proposed_due_date'], now_str
        ))
        loan_id = cursor.lastrowid

        log_action(lender_id, 'REQUEST_ACCEPTED', 'loan_request', request_id, conn=conn)
        log_action(lender_id, 'LOAN_INITIALIZED', 'loan', loan_id, conn=conn)

    return loan_id, None

def decline_loan_request(request_id, user_id):
    # Only community admin can decline request, or borrower can cancel
    conn = get_db()
    with db_transaction(conn):
        conn.execute("BEGIN IMMEDIATE")
        req = conn.execute("SELECT * FROM loan_requests WHERE id = ?", (request_id,)).fetchone()
        if not req:
            return False, "Request not found."

        admin_row = conn.execute(
            "SELECT role FROM community_members WHERE community_id = ? AND user_id = ? AND role = 'admin'",
            (req['community_id'], user_id)
        ).fetchone()
        if not admin_row:
            return False, "Only community administrators can decline a request."

        if req['status'] != 'pending':
            return False, "Only pending requests can be declined."

        updated = conn.execute(
            "UPDATE loan_requests SET status = 'declined' WHERE id = ? AND status = 'pending'",
            (request_id,)
        ).rowcount
        if not updated:
            return False, "This request has already changed status."

        log_action(user_id, 'REQUEST_DECLINED', 'loan_request', request_id, conn=conn)
    return True, None

def acknowledge_loan_agreement(loan_id, user_id):
    conn = get_db()
    with db_transaction(conn):
        conn.execute("BEGIN IMMEDIATE")
        loan = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
        if not loan:
            return False, "Loan agreement not found."

        if loan['status'] != 'awaiting_agreement':
            return False, f"Agreement cannot be modified in '{loan['status'].replace('_', ' ').title()}' state."

        is_borrower = user_id == loan['borrower_id']
        is_lender = user_id == loan['lender_id']
        if not is_borrower and not is_lender:
            return False, "You are not a participant in this loan agreement."

        if (is_borrower and loan['borrower_accepted']) or (is_lender and loan['lender_accepted']):
            return False, "You have already acknowledged this loan agreement."

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if is_borrower:
            conn.execute(
                "UPDATE loans SET borrower_accepted = 1, borrower_accepted_at = ? WHERE id = ?",
                (now_str, loan_id)
            )
        if is_lender:
            conn.execute(
                "UPDATE loans SET lender_accepted = 1, lender_accepted_at = ? WHERE id = ?",
                (now_str, loan_id)
            )

        both_accepted = (
            (is_borrower or loan['borrower_accepted'] == 1)
            and (is_lender or loan['lender_accepted'] == 1)
        )
        if both_accepted:
            conn.execute("UPDATE loans SET status = 'active' WHERE id = ?", (loan_id,))

        log_action(user_id, 'AGREEMENT_ACKNOWLEDGED', 'loan', loan_id, conn=conn)
        if both_accepted:
            log_action(None, 'LOAN_ACTIVATED', 'loan', loan_id, conn=conn)

    return True, {
        'both_accepted': both_accepted,
        'status': 'active' if both_accepted else 'awaiting_agreement'
    }

def get_due_date_indicator(due_date_str, outstanding_cents, status):
    if status == 'repaid' or outstanding_cents == 0:
        return {'label': 'Fully Repaid', 'color': 'emerald', 'code': 'repaid'}
    if status == 'cancelled':
        return {'label': 'Cancelled', 'color': 'slate', 'code': 'cancelled'}
    if status == 'awaiting_agreement':
        return {'label': 'Awaiting Agreement', 'color': 'amber', 'code': 'awaiting'}

    try:
        due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        today = date.today()
        days_left = (due - today).days

        if days_left < 0:
            return {'label': f'Overdue ({abs(days_left)}d)', 'color': 'rose', 'code': 'overdue', 'days': days_left}
        elif days_left <= 3:
            return {'label': f'Due Soon ({days_left}d)', 'color': 'amber', 'code': 'due_soon', 'days': days_left}
        else:
            return {'label': f'Due in {days_left}d', 'color': 'slate', 'code': 'not_yet_due', 'days': days_left}
    except Exception:
        return {'label': 'Scheduled', 'color': 'slate', 'code': 'scheduled'}

def sync_overdue_loans():
    """
    Scans active loans whose due date has passed with outstanding balance > 0
    and updates status to 'overdue'.
    """
    conn = get_db()
    today_str = date.today().strftime("%Y-%m-%d")
    loans = conn.execute("""
        SELECT id FROM loans
        WHERE status = 'active' AND due_date < ?
    """, (today_str,)).fetchall()

    count = 0
    for l in loans:
        _, _, _, _, outstanding = calculate_outstanding_balance(l['id'], conn=conn)
        if outstanding > 0:
            conn.execute("UPDATE loans SET status = 'overdue' WHERE id = ?", (l['id'],))
            log_action(None, 'LOAN_MARKED_OVERDUE', 'loan', l['id'], conn=conn)
            count += 1
    conn.commit()
    return count

def get_loan_details(loan_id):
    sync_overdue_loans()
    conn = get_db()
    loan_row = conn.execute("""
        SELECT l.*,
               lr.reason, lr.community_id,
               c.name as community_name,
               b.full_name as borrower_name, b.email as borrower_email,
               ln.full_name as lender_name, ln.email as lender_email
        FROM loans l
        JOIN loan_requests lr ON l.request_id = lr.id
        JOIN communities c ON lr.community_id = c.id
        JOIN users b ON l.borrower_id = b.id
        JOIN users ln ON l.lender_id = ln.id
        WHERE l.id = ?
    """, (loan_id,)).fetchone()

    if not loan_row:
        return None

    loan = dict(loan_row)
    principal, fee, total_due, total_repaid, outstanding = calculate_outstanding_balance(loan_id, conn=conn)
    loan['total_due_minor'] = total_due
    loan['total_repaid_minor'] = total_repaid
    loan['outstanding_minor'] = outstanding
    loan['repayment_percentage'] = round((total_repaid / total_due * 100), 1) if total_due > 0 else 100.0
    loan['indicator'] = get_due_date_indicator(loan['due_date'], outstanding, loan['status'])

    return loan

def get_categorized_user_loans(user_id):
    sync_overdue_loans()
    conn = get_db()
    all_loans = conn.execute("""
        SELECT l.*,
               lr.reason, lr.community_id,
               c.name as community_name,
               b.full_name as borrower_name,
               ln.full_name as lender_name
        FROM loans l
        JOIN loan_requests lr ON l.request_id = lr.id
        JOIN communities c ON lr.community_id = c.id
        JOIN users b ON l.borrower_id = b.id
        JOIN users ln ON l.lender_id = ln.id
        WHERE l.borrower_id = ? OR l.lender_id = ?
        ORDER BY l.created_at DESC
    """, (user_id, user_id)).fetchall()

    enriched = []
    for row in all_loans:
        item = dict(row)
        principal, fee, total_due, total_repaid, outstanding = calculate_outstanding_balance(item['id'], conn=conn)
        item['total_due_minor'] = total_due
        item['total_repaid_minor'] = total_repaid
        item['outstanding_minor'] = outstanding
        item['repayment_percentage'] = round((total_repaid / total_due * 100), 1) if total_due > 0 else 100.0
        item['indicator'] = get_due_date_indicator(item['due_date'], outstanding, item['status'])
        enriched.append(item)

    categories = {
        'borrowed': [l for l in enriched if l['borrower_id'] == user_id and l['status'] in ('active', 'overdue')],
        'provided': [l for l in enriched if l['lender_id'] == user_id and l['status'] in ('active', 'overdue')],
        'awaiting_agreement': [l for l in enriched if l['status'] == 'awaiting_agreement'],
        'repaid': [l for l in enriched if l['status'] == 'repaid'],
        'overdue': [l for l in enriched if l['status'] == 'overdue'],
        'all': enriched
    }
    return categories

def get_community_eligible_requests(user_id):
    conn = get_db()
    # Get all communities user is a member of
    user_comms = conn.execute("SELECT community_id FROM community_members WHERE user_id = ?", (user_id,)).fetchall()
    comm_ids = [r['community_id'] for r in user_comms]
    if not comm_ids:
        return []

    placeholders = ','.join('?' for _ in comm_ids)
    requests = conn.execute(f"""
        SELECT lr.*, c.name as community_name, u.full_name as borrower_name
        FROM loan_requests lr
        JOIN communities c ON lr.community_id = c.id
        JOIN users u ON lr.borrower_id = u.id
        WHERE lr.community_id IN ({placeholders})
        ORDER BY lr.created_at DESC
    """, comm_ids).fetchall()

    return requests
