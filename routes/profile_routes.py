from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from routes.main_routes import login_required
from services.auth_service import get_user_by_id, update_user_profile
from services.community_service import get_user_communities
from services.loan_service import get_categorized_user_loans
from database import get_db

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def view():
    user_id = session['user_id']
    user = get_user_by_id(user_id)

    if request.method == 'POST':
        full_name = request.form.get('full_name', '')
        email = request.form.get('email', '')

        success, errors = update_user_profile(user_id, full_name, email)
        if errors:
            for err in errors:
                flash(err, 'danger')
        else:
            session['user_name'] = full_name.strip()
            flash("Profile details updated successfully.", "success")
            return redirect(url_for('profile.view'))

    communities = get_user_communities(user_id)
    loan_cats = get_categorized_user_loans(user_id)

    # Activity summary
    conn = get_db()
    total_repayments_made = conn.execute(
        "SELECT COUNT(*) as c, COALESCE(SUM(amount_minor), 0) as total FROM repayments WHERE recorded_by = ?",
        (user_id,)
    ).fetchone()

    activity = {
        'total_requests': conn.execute("SELECT COUNT(*) as c FROM loan_requests WHERE borrower_id = ?", (user_id,)).fetchone()['c'],
        'borrowed_count': len(loan_cats['borrowed']) + len(loan_cats['repaid']),
        'lent_count': len(loan_cats['provided']),
        'repaid_loans_count': len(loan_cats['repaid']),
        'repayments_count': total_repayments_made['c'],
        'repayments_volume_minor': total_repayments_made['total']
    }

    return render_template(
        'profile/view.html',
        user=user,
        communities=communities,
        activity=activity
    )
