from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from routes.main_routes import login_required
from services.loan_service import (
    get_categorized_user_loans, get_loan_details,
    acknowledge_loan_agreement
)
from services.repayment_service import get_loan_repayments

loan_bp = Blueprint('loan', __name__)

@loan_bp.route('/loans')
@login_required
def index():
    user_id = session['user_id']
    active_tab = request.args.get('tab', 'borrowed')
    loan_cats = get_categorized_user_loans(user_id)

    return render_template('loans/index.html', loan_cats=loan_cats, active_tab=active_tab)

@loan_bp.route('/loans/<int:loan_id>')
@login_required
def detail(loan_id):
    user_id = session['user_id']
    loan = get_loan_details(loan_id)
    if not loan:
        abort(404)

    # Permission check: must be borrower, lender, or admin
    is_participant = (user_id in (loan['borrower_id'], loan['lender_id']))
    is_admin = (session.get('user_role') == 'admin')
    if not is_participant and not is_admin:
        flash("You do not have permission to view this loan.", "danger")
        return redirect(url_for('loan.index'))

    repayments = get_loan_repayments(loan_id)
    return render_template(
        'loans/detail.html',
        loan=loan,
        repayments=repayments,
        is_borrower=user_id == loan['borrower_id'],
        is_lender=user_id == loan['lender_id']
    )

@loan_bp.route('/loans/<int:loan_id>/agreement')
@login_required
def agreement(loan_id):
    user_id = session['user_id']
    loan = get_loan_details(loan_id)
    if not loan:
        abort(404)

    is_participant = (user_id in (loan['borrower_id'], loan['lender_id']))
    is_admin = (session.get('user_role') == 'admin')
    if not is_participant and not is_admin:
        flash("You do not have permission to access this loan agreement.", "danger")
        return redirect(url_for('loan.index'))

    is_borrower = (user_id == loan['borrower_id'])
    is_lender = (user_id == loan['lender_id'])
    has_user_acknowledged = (loan['borrower_accepted'] if is_borrower else loan['lender_accepted'])

    return render_template(
        'loans/agreement.html',
        loan=loan,
        is_borrower=is_borrower,
        is_lender=is_lender,
        has_user_acknowledged=has_user_acknowledged,
        can_acknowledge=loan['status'] == 'awaiting_agreement' and not has_user_acknowledged and (is_borrower or is_lender)
    )

@loan_bp.route('/loans/<int:loan_id>/acknowledge', methods=['POST'])
@login_required
def acknowledge(loan_id):
    user_id = session['user_id']
    success, res = acknowledge_loan_agreement(loan_id, user_id)

    if not success:
        flash(res, "danger")
        return redirect(url_for('loan.agreement', loan_id=loan_id))

    if res['both_accepted']:
        flash("Both parties have acknowledged the agreement! The loan is now ACTIVE.", "success")
        return redirect(url_for('loan.detail', loan_id=loan_id))
    else:
        flash("Your acknowledgement has been recorded. Waiting for the counterparty to acknowledge.", "info")
        return redirect(url_for('loan.agreement', loan_id=loan_id))
