from functools import wraps
from flask import Blueprint, render_template, session, redirect, url_for, flash
from database import get_db
from services.community_service import get_user_communities
from services.loan_service import get_categorized_user_loans, sync_overdue_loans
from services.repayment_service import calculate_outstanding_balance

main_bp = Blueprint('main', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@main_bp.route('/')
def index():
    conn = get_db()
    # High-level aggregated impact metrics for landing page
    active_comms = conn.execute("SELECT COUNT(*) as c FROM communities").fetchone()['c']
    total_loans = conn.execute("SELECT COUNT(*) as c FROM loans WHERE status != 'cancelled'").fetchone()['c']
    total_vol = conn.execute("SELECT COALESCE(SUM(principal_minor), 0) as v FROM loans WHERE status != 'cancelled'").fetchone()['v']
    repaid_loans = conn.execute("SELECT COUNT(*) as c FROM loans WHERE status = 'repaid'").fetchone()['c']

    return render_template('index.html',
        active_comms=active_comms,
        total_loans=total_loans,
        total_volume_minor=total_vol,
        repaid_loans=repaid_loans
    )

@main_bp.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    sync_overdue_loans()
    conn = get_db()

    # Request metrics are based on requests made by this borrower, not accepted loans.
    request_metrics = conn.execute("""
        SELECT COUNT(*) as request_count,
               COALESCE(SUM(amount_minor), 0) as requested_minor,
               COALESCE(SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END), 0) as pending_count,
               COALESCE(SUM(CASE WHEN status = 'pending' THEN amount_minor ELSE 0 END), 0) as pending_minor
        FROM loan_requests
        WHERE borrower_id = ?
    """, (user_id,)).fetchone()

    # 2. Categorized loans
    loan_cats = get_categorized_user_loans(user_id)

    loans_awaiting_agreement_count = len(loan_cats['awaiting_agreement'])
    active_borrowed_count = len([l for l in loan_cats['borrowed'] if l['status'] == 'active'])
    active_provided_count = len([l for l in loan_cats['provided'] if l['status'] == 'active'])
    overdue_loans_count = len(loan_cats['overdue'])

    completed_or_active_loans = [
        loan for loan in loan_cats['all']
        if loan['status'] in ('active', 'overdue', 'repaid')
    ]
    borrowed_principal_minor = sum(
        loan['principal_minor'] for loan in completed_or_active_loans
        if loan['borrower_id'] == user_id
    )
    lent_principal_minor = sum(
        loan['principal_minor'] for loan in completed_or_active_loans
        if loan['lender_id'] == user_id
    )

    # 3. Outstanding amount owed (as borrower)
    outstanding_owed_minor = sum(l['outstanding_minor'] for l in loan_cats['borrowed'])

    # 4. Amount currently owed to the user (as lender)
    outstanding_to_receive_minor = sum(l['outstanding_minor'] for l in loan_cats['provided'])

    # Repayment totals follow the user's role in each loan, not the recording account.
    repaid_by_user_minor = conn.execute(
        """SELECT COALESCE(SUM(r.amount_minor), 0) as total
           FROM repayments r JOIN loans l ON r.loan_id = l.id
           WHERE l.borrower_id = ? AND r.amount_minor > 0""",
        (user_id,)
    ).fetchone()['total']
    received_by_user_minor = conn.execute(
        """SELECT COALESCE(SUM(r.amount_minor), 0) as total
           FROM repayments r JOIN loans l ON r.loan_id = l.id
           WHERE l.lender_id = ? AND r.amount_minor > 0""",
        (user_id,)
    ).fetchone()['total']

    # 6. User's communities
    user_communities = get_user_communities(user_id)

    # 7. Urgent / Due soon & Overdue alert lists
    urgent_loans = [
        l for l in loan_cats['all']
        if l['indicator']['code'] in ('overdue', 'due_soon') and l['borrower_id'] == user_id
    ]

    cards = {
        'total_requests': request_metrics['request_count'],
        'total_requested_minor': request_metrics['requested_minor'],
        'pending_requests': request_metrics['pending_count'],
        'pending_requested_minor': request_metrics['pending_minor'],
        'loans_awaiting_agreement': loans_awaiting_agreement_count,
        'active_borrowed': active_borrowed_count,
        'active_provided': active_provided_count,
        'borrowed_principal_minor': borrowed_principal_minor,
        'lent_principal_minor': lent_principal_minor,
        'outstanding_owed_minor': outstanding_owed_minor,
        'outstanding_to_receive_minor': outstanding_to_receive_minor,
        'total_repayments_made_minor': repaid_by_user_minor,
        'total_repayments_received_minor': received_by_user_minor,
        'overdue_loans': overdue_loans_count
    }

    return render_template(
        'dashboard.html',
        cards=cards,
        loan_cats=loan_cats,
        communities=user_communities,
        urgent_loans=urgent_loans
    )
