from decimal import Decimal, InvalidOperation
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from routes.main_routes import login_required
from services.loan_service import get_loan_details
from services.repayment_service import (
    record_repayment, generate_simulated_reference, get_user_repayments
)

repayment_bp = Blueprint('repayment', __name__)

def render_repayment_form(loan, reference=None, amount='', payment_date=None):
    return render_template(
        'repayments/create.html',
        loan=loan,
        outstanding_balance_minor=loan['outstanding_minor'],
        default_ref=reference or generate_simulated_reference(),
        amount=amount,
        payment_date=payment_date or date.today().isoformat(),
        today=date.today()
    )

@repayment_bp.route('/repayments')
@login_required
def index():
    user_id = session['user_id']
    repayments = get_user_repayments(user_id)
    return render_template('repayments/index.html', repayments=repayments)

@repayment_bp.route('/loans/<int:loan_id>/repay', methods=['GET', 'POST'])
@login_required
def create(loan_id):
    user_id = session['user_id']
    loan = get_loan_details(loan_id)
    if not loan:
        abort(404)

    # Only borrower can record repayment on their borrowed loan
    if loan['borrower_id'] != user_id and session.get('user_role') != 'admin':
        flash("Only the borrower is authorized to record payments on this loan.", "danger")
        return redirect(url_for('loan.detail', loan_id=loan_id))

    if loan['status'] not in ('active', 'overdue'):
        flash(f"This loan is not currently active for repayment (Status: {loan['status'].replace('_', ' ').title()}).", "warning")
        return redirect(url_for('loan.detail', loan_id=loan_id))

    if request.method == 'POST':
        amount_raw = request.form.get('amount', '').strip()
        reference = request.form.get('simulated_reference', '').strip()
        payment_date = request.form.get('repayment_date', '').strip() or date.today().isoformat()

        try:
            dec_amount = Decimal(amount_raw)
            if not dec_amount.is_finite() or dec_amount <= 0:
                raise ValueError("Amount must be greater than zero.")
            if dec_amount.as_tuple().exponent < -2:
                raise ValueError("Amount cannot have more than 2 decimal places.")
            if dec_amount > Decimal(loan['outstanding_minor']) / 100:
                raise ValueError("Amount cannot exceed the outstanding balance.")
            amount_cents = int(dec_amount * 100)
        except (InvalidOperation, ValueError, TypeError, OverflowError) as e:
            flash(f"Invalid payment amount: {str(e)}", "danger")
            return render_repayment_form(loan, reference, amount_raw, payment_date)

        success, res = record_repayment(
            loan_id=loan_id,
            amount_minor=amount_cents,
            reference=reference,
            user_id=user_id,
            payment_date=payment_date
        )

        if not success:
            flash(res, "danger")
            return render_repayment_form(loan, reference, amount_raw, payment_date)

        if res['is_fully_repaid']:
            flash(f"Success! Final payment of ${amount_cents // 100}.{amount_cents % 100:02d} recorded (Ref: {res['reference']}). The loan is now FULLY REPAID!", "success")
        else:
            rem = res['remaining_minor']
            flash(f"Partial payment of ${amount_cents // 100}.{amount_cents % 100:02d} recorded (Ref: {res['reference']}). Remaining balance: ${rem // 100}.{rem % 100:02d}.", "info")

        return redirect(url_for('loan.detail', loan_id=loan_id))

    return render_repayment_form(loan)
