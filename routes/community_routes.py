import hmac
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from routes.main_routes import login_required
from services.community_service import (
    create_community, join_community_by_code, get_community,
    get_communities_for_user, get_community_members, is_member,
    is_community_admin, get_community_stats, get_community_loans,
    get_community_activity, leave_community, update_community,
    transfer_community_admin, remove_community_member,
    regenerate_community_invite_code
)
from database import get_db
from services.loan_service import sync_overdue_loans

community_bp = Blueprint('community', __name__)

@community_bp.route('/communities')
@login_required
def index():
    user_id = session['user_id']
    communities = get_communities_for_user(user_id)
    return render_template('communities/index.html', communities=communities)

@community_bp.route('/communities/create', methods=['GET', 'POST'])
@login_required
def create():
    token = session.get('community_create_token')
    if not token:
        token = secrets.token_urlsafe(24)
        session['community_create_token'] = token

    if request.method == 'POST':
        submitted_token = request.form.get('submission_token', '')
        if not submitted_token or not hmac.compare_digest(
            submitted_token, session.get('community_create_token', '')
        ):
            flash("This community form was already submitted or has expired. Please try again.", 'warning')
            return redirect(url_for('community.create'))

        name = request.form.get('name', '')
        description = request.form.get('description', '')
        user_id = session['user_id']

        comm_id, error = create_community(name, description, user_id)
        if error:
            flash(error, 'danger')
        else:
            session.pop('community_create_token', None)
            flash("Community created successfully! You are now the community administrator.", 'success')
            return redirect(url_for('community.detail', community_id=comm_id))

    return render_template(
        'communities/create.html',
        form_data=request.form if request.method == 'POST' else {},
        submission_token=token
    )

@community_bp.route('/communities/join', methods=['GET', 'POST'])
@login_required
def join():
    if request.method == 'POST':
        invite_code = request.form.get('invite_code', '')
        user_id = session['user_id']

        comm_id, error = join_community_by_code(invite_code, user_id)
        if error:
            flash(error, 'info' if comm_id else 'warning')
            if comm_id and error == "You are already a member of this community.":
                return redirect(url_for('community.detail', community_id=comm_id))
            return redirect(url_for('community.join'))
        else:
            flash("Successfully joined the community! Welcome aboard.", 'success')
            return redirect(url_for('community.detail', community_id=comm_id))

    return render_template('communities/join.html')

@community_bp.route('/communities/<int:community_id>')
@login_required
def detail(community_id):
    user_id = session['user_id']
    community = get_community(community_id)
    if not community:
        abort(404)

    has_membership = is_member(community_id, user_id)
    is_admin = is_community_admin(community_id, user_id)
    if not has_membership:
        return render_template(
            'communities/detail.html',
            community=community,
            is_member=False,
            is_admin=False
        )

    sync_overdue_loans()
    conn = get_db()
    community = dict(community)
    community['invite_code'] = conn.execute(
        "SELECT invite_code FROM communities WHERE id = ?", (community_id,)
    ).fetchone()['invite_code']
    members = get_community_members(community_id)
    stats = get_community_stats(community_id)
    activity = get_community_loans(community_id)
    recent_events = get_community_activity(community_id)

    return render_template(
        'communities/detail.html',
        community=community,
        is_member=True,
        members=members,
        stats=stats,
        is_admin=is_admin,
        activity=activity,
        recent_events=recent_events,
        current_user_id=user_id,
        other_members=[member for member in members if member['id'] != user_id]
    )

@community_bp.route('/communities/<int:community_id>/edit', methods=['POST'])
@login_required
def edit(community_id):
    success, error = update_community(
        community_id,
        session['user_id'],
        request.form.get('name', ''),
        request.form.get('description', '')
    )
    flash("Community details updated." if success else error, 'success' if success else 'danger')
    return redirect(url_for('community.detail', community_id=community_id))

@community_bp.route('/communities/<int:community_id>/leave', methods=['POST'])
@login_required
def leave(community_id):
    success, error = leave_community(community_id, session['user_id'])
    flash("You have left the community." if success else error, 'success' if success else 'danger')
    return redirect(url_for('community.index'))

@community_bp.route('/communities/<int:community_id>/members/<int:member_id>/remove', methods=['POST'])
@login_required
def remove_member(community_id, member_id):
    success, error = remove_community_member(community_id, session['user_id'], member_id)
    flash("Member removed from the community." if success else error, 'success' if success else 'danger')
    return redirect(url_for('community.detail', community_id=community_id))

@community_bp.route('/communities/<int:community_id>/admin/transfer', methods=['POST'])
@login_required
def transfer_admin(community_id):
    new_admin_id = request.form.get('new_admin_id', type=int)
    success, error = transfer_community_admin(community_id, session['user_id'], new_admin_id)
    flash("Administrator privileges transferred." if success else error, 'success' if success else 'danger')
    return redirect(url_for('community.detail', community_id=community_id))

@community_bp.route('/communities/<int:community_id>/invite-code/regenerate', methods=['POST'])
@login_required
def regenerate_invite_code(community_id):
    invite_code, error = regenerate_community_invite_code(community_id, session['user_id'])
    flash(
        "A new invitation code has been generated." if invite_code else error,
        'success' if invite_code else 'danger'
    )
    return redirect(url_for('community.detail', community_id=community_id))
