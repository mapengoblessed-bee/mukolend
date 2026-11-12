from decimal import Decimal, InvalidOperation
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from routes.main_routes import login_required
from services.community_service import get_user_communities, is_member
from services.loan_service import (
    create_loan_request, cancel_loan_request, accept_loan_request,
    decline_loan_request, get_community_eligible_requests
)
from database import get_db

loan_request_bp = Blueprint('loan_request', __name__)

@loan_request_bp.route('/requests')
@login_required
def index():
    user_id = session['user_id']
    eligible_requests = get_community_eligible_requests(user_id)
    return render_template('requests/index.html', requests=eligible_requests)

@loan_request_bp.route('/requests/create', methods=['GET', 'POST'])
@login_required
def create():
    user_id = session['user_id']
    user_communities = get_user_communities(user_id)

    if not user_communities:
        flash("You must join or establish a community before submitting a loan request.", "warning")
        return redirect(url_for('community.create'))

    if request.method == 'POST':
        community_id = request.form.get('community_id', type=int)
        amount_raw = request.form.get('amount', '').strip()
        currency = request.form.get('currency', 'USD').strip().upper()
        reason = request.form.get('reason', '').strip()
        proposed_due_date = request.form.get('proposed_due_date', '').strip()

        # Money validation: ensure positive, max 2 decimals, convert to minor units
        try:
            dec_amount = Decimal(amount_raw)
            if not dec_amount.is_finite() or dec_amount <= 0:
                raise ValueError("Amount must be a positive, finite number.")
            if dec_amount.as_tuple().exponent < -2:
                raise ValueError("Amount cannot have more than 2 decimal places.")
            if dec_amount > Decimal("10000"):
                raise ValueError("Amount cannot exceed $10,000.00.")
            amount_cents = int(dec_amount * 100)
        except (InvalidOperation, ValueError, TypeError) as e:
            flash(f"Invalid loan amount: {str(e)}", "danger")
            return render_template('requests/create.html', communities=user_communities, form_data=request.form)

        req_id, error = create_loan_request(
            community_id=community_id,
            borrower_id=user_id,
            amount_cents=amount_cents,
            currency=currency,
            reason=reason,
            proposed_due_date=proposed_due_date
        )

        if error:
            flash(error, "danger")
            return render_template('requests/create.html', communities=user_communities, form_data=request.form)
        else:
            flash("Loan request submitted successfully to your community members!", "success")
            return redirect(url_for('loan_request.detail', request_id=req_id))

    return render_template('requests/create.html', communities=user_communities, form_data={})

@loan_request_bp.route('/requests/<int:request_id>')
@login_required
def detail(request_id):
    user_id = session['user_id']
    conn = get_db()
    req = conn.execute("""
        SELECT lr.*, c.name as community_name, u.full_name as borrower_name, u.email as borrower_email
        FROM loan_requests lr
        JOIN communities c ON lr.community_id = c.id
        JOIN users u ON lr.borrower_id = u.id
        WHERE lr.id = ?
    """, (request_id,)).fetchone()

    if not req:
        abort(404)

    # User must belong to this community or be admin
    member = is_member(req['community_id'], user_id)
    is_global_admin = session.get('user_role') == 'admin'
    if not member and not is_global_admin:
        flash("You do not have permission to view this loan request.", "warning")
        return redirect(url_for('loan_request.index'))

    # Check if this request has already been converted to a loan
    loan = conn.execute("SELECT id FROM loans WHERE request_id = ?", (request_id,)).fetchone()

    community_admin = conn.execute(
        "SELECT 1 FROM community_members WHERE community_id = ? AND user_id = ? AND role = 'admin'",
        (req['community_id'], user_id)
    ).fetchone() is not None

    return render_template(
        'requests/detail.html',
        req=req,
        associated_loan=loan,
        can_accept=req['status'] == 'pending' and member and req['borrower_id'] != user_id,
        can_cancel=req['status'] == 'pending' and req['borrower_id'] == user_id,
        can_decline=req['status'] == 'pending' and community_admin and req['borrower_id'] != user_id
    )

@loan_request_bp.route('/requests/<int:request_id>/accept', methods=['POST'])
@login_required
def accept(request_id):
    lender_id = session['user_id']
    fee_raw = request.form.get('agreed_fee', '0').strip()
    try:
        fee = Decimal(fee_raw)
        if not fee.is_finite() or fee < 0:
            raise ValueError("Agreed fee must be zero or greater.")
        if fee.as_tuple().exponent < -2:
            raise ValueError("Agreed fee cannot have more than 2 decimal places.")
        if fee > Decimal("92233720368547758.07"):
            raise ValueError("Agreed fee is too large.")
        fee_minor = int(fee * 100)
    except (InvalidOperation, ValueError, TypeError, OverflowError) as e:
        flash(f"Invalid agreed fee: {str(e)}", "danger")
        return redirect(url_for('loan_request.detail', request_id=request_id))

    loan_id, error = accept_loan_request(request_id, lender_id, fee_minor=fee_minor)

    if error:
        flash(error, "danger")
        return redirect(url_for('loan_request.detail', request_id=request_id))

    flash("Loan offer accepted! Please proceed to review and acknowledge the formal loan agreement.", "success")
    return redirect(url_for('loan.agreement', loan_id=loan_id))

@loan_request_bp.route('/requests/<int:request_id>/decline', methods=['POST'])
@login_required
def decline(request_id):
    user_id = session['user_id']
    success, error = decline_loan_request(request_id, user_id)
    if error:
        flash(error, "danger")
    else:
        flash("Loan request has been declined.", "info")
    return redirect(url_for('loan_request.detail', request_id=request_id))

@loan_request_bp.route('/requests/<int:request_id>/cancel', methods=['POST'])
@login_required
def cancel(request_id):
    user_id = session['user_id']
    success, error = cancel_loan_request(request_id, user_id)
    if error:
        flash(error, "danger")
    else:
        flash("Your loan request has been cancelled.", "info")
    return redirect(url_for('loan_request.index'))
