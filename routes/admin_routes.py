from functools import wraps
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, abort
from routes.main_routes import login_required
from database import get_db
from services.audit_service import get_recent_logs

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in with administrative privileges.", "warning")
            return redirect(url_for('auth.login'))
        if session.get('user_role') != 'admin':
            flash("Access denied. Global administrative privileges required.", "danger")
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/admin')
@admin_required
def index():
    conn = get_db()
    
    # 1. System Overview
    total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
    total_communities = conn.execute("SELECT COUNT(*) as c FROM communities").fetchone()['c']
    total_loans = conn.execute("SELECT COUNT(*) as c FROM loans").fetchone()['c']
    total_requests = conn.execute("SELECT COUNT(*) as c FROM loan_requests").fetchone()['c']
    total_repayments = conn.execute("SELECT COUNT(*) as c FROM repayments").fetchone()['c']

    # 2. Community Health Table
    community_stats = conn.execute("""
        SELECT c.*, u.full_name as creator_name,
               (SELECT COUNT(*) FROM community_members WHERE community_id = c.id) as member_count,
               (SELECT COUNT(*) FROM loan_requests WHERE community_id = c.id) as request_count,
               (SELECT COUNT(*) FROM loans l JOIN loan_requests lr ON l.request_id = lr.id WHERE lr.community_id = c.id AND l.status = 'active') as active_loans_count,
               (SELECT COALESCE(SUM(principal_minor), 0) FROM loans l JOIN loan_requests lr ON l.request_id = lr.id WHERE lr.community_id = c.id AND l.status != 'cancelled') as volume_minor
        FROM communities c
        JOIN users u ON c.created_by = u.id
        ORDER BY c.created_at DESC
    """).fetchall()

    # 3. Data Quality & Integrity Indicators
    orphaned_repayments = conn.execute("SELECT COUNT(*) as c FROM repayments WHERE loan_id NOT IN (SELECT id FROM loans)").fetchone()['c']
    orphaned_loans = conn.execute("SELECT COUNT(*) as c FROM loans WHERE request_id NOT IN (SELECT id FROM loan_requests)").fetchone()['c']
    invalid_status_loans = conn.execute("SELECT COUNT(*) as c FROM loans WHERE status NOT IN ('awaiting_agreement', 'active', 'repaid', 'overdue', 'cancelled')").fetchone()['c']

    quality_indicators = {
        'orphaned_repayments': orphaned_repayments,
        'orphaned_loans': orphaned_loans,
        'invalid_status_loans': invalid_status_loans,
        'all_clean': (orphaned_repayments == 0 and orphaned_loans == 0 and invalid_status_loans == 0)
    }

    recent_logs = get_recent_logs(limit=10)

    return render_template(
        'admin/index.html',
        total_users=total_users,
        total_communities=total_communities,
        total_loans=total_loans,
        total_requests=total_requests,
        total_repayments=total_repayments,
        community_stats=community_stats,
        quality=quality_indicators,
        recent_logs=recent_logs
    )

@admin_bp.route('/admin/audit-log')
@admin_required
def audit_log_view():
    entity_type = request.args.get('entity_type')
    limit = request.args.get('limit', 100, type=int)
    logs = get_recent_logs(limit=limit, entity_type=entity_type)

    return render_template('admin/audit_log.html', logs=logs, selected_entity=entity_type)
