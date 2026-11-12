import secrets
import sqlite3
import string
from database import db_transaction, get_db
from services.audit_service import log_action

def generate_invite_code():
    chars = ''.join(c for c in string.ascii_uppercase + string.digits if c not in ('0', 'O', '1', 'I'))
    suffix = ''.join(secrets.choice(chars) for _ in range(10))
    return f"MUKO-{suffix}"

def create_community(name, description, creator_id):
    clean_name = name.strip() if isinstance(name, str) else ""
    clean_desc = description.strip() if isinstance(description, str) else ""
    if len(clean_name) < 3:
        return None, "Community name must be at least 3 characters."

    if len(clean_name) > 100:
        return None, "Community name cannot exceed 100 characters."
    if len(clean_desc) > 500:
        return None, "Community description cannot exceed 500 characters."
    if type(creator_id) is not int or creator_id <= 0:
        return None, "A valid community administrator is required."

    conn = get_db()

    try:
        with db_transaction(conn):
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute("SELECT 1 FROM users WHERE id = ?", (creator_id,)).fetchone():
                return None, "The signed-in account could not be found."

            for _ in range(5):
                invite_code = generate_invite_code()
                try:
                    cursor = conn.execute(
                        "INSERT INTO communities (name, description, invite_code, created_by) VALUES (?, ?, ?, ?)",
                        (clean_name, clean_desc, invite_code, creator_id)
                    )
                    community_id = cursor.lastrowid
                    conn.execute(
                        "INSERT INTO community_members (community_id, user_id, role) VALUES (?, ?, 'admin')",
                        (community_id, creator_id)
                    )
                    log_action(creator_id, 'COMMUNITY_CREATED', 'community', community_id, conn=conn)
                    break
                except sqlite3.IntegrityError as error:
                    if "invite_code" not in str(error).lower():
                        raise
            else:
                return None, "Unable to generate a unique invite code. Please try again."
    except sqlite3.IntegrityError:
        return None, "Unable to create the community. Please check the supplied details."

    return community_id, None

def join_community_by_code(invite_code, user_id):
    if not isinstance(invite_code, str) or not invite_code.strip():
        return None, "Please enter an invitation code."
    if type(user_id) is not int or user_id <= 0:
        return None, "A valid signed-in account is required."

    clean_code = invite_code.strip().upper()
    if len(clean_code) > 20:
        return None, "Invalid invitation code."
    conn = get_db()
    try:
        with db_transaction(conn):
            conn.execute("BEGIN IMMEDIATE")
            comm = conn.execute(
                "SELECT id FROM communities WHERE invite_code = ?", (clean_code,)
            ).fetchone()
            if not comm:
                return None, "No community was found for that invitation code."

            community_id = comm['id']
            existing = conn.execute(
                "SELECT 1 FROM community_members WHERE community_id = ? AND user_id = ?",
                (community_id, user_id)
            ).fetchone()
            if existing:
                return community_id, "You are already a member of this community."

            conn.execute(
                "INSERT INTO community_members (community_id, user_id, role) VALUES (?, ?, 'member')",
                (community_id, user_id)
            )
            log_action(user_id, 'COMMUNITY_JOINED', 'community', community_id, conn=conn)
    except sqlite3.IntegrityError:
        return None, "Unable to join this community. Please check your account and try again."

    return community_id, None

def get_community(community_id):
    conn = get_db()
    return conn.execute("""
        SELECT c.id, c.name, c.description, c.created_by, c.created_at,
               u.full_name as creator_name,
               (SELECT COUNT(*) FROM community_members WHERE community_id = c.id) as member_count
        FROM communities c
        JOIN users u ON c.created_by = u.id
        WHERE c.id = ?
    """, (community_id,)).fetchone()

def get_communities_for_user(user_id):
    conn = get_db()
    return conn.execute("""
        SELECT c.id, c.name, c.description, c.created_at,
               creator.full_name as creator_name,
               member.role as membership_role,
               CASE WHEN member.user_id IS NOT NULL THEN c.invite_code END as invite_code,
               (SELECT COUNT(*) FROM community_members cm WHERE cm.community_id = c.id) as member_count
        FROM communities c
        JOIN users creator ON creator.id = c.created_by
        LEFT JOIN community_members member
          ON member.community_id = c.id AND member.user_id = ?
        ORDER BY CASE WHEN member.user_id IS NOT NULL THEN 0 ELSE 1 END,
                 c.created_at DESC, c.id DESC
    """, (user_id,)).fetchall()

def get_user_communities(user_id):
    conn = get_db()
    return conn.execute("""
        SELECT c.*, cm.role as user_role, cm.joined_at,
               (SELECT COUNT(*) FROM community_members WHERE community_id = c.id) as member_count
        FROM communities c
        JOIN community_members cm ON c.id = cm.community_id
        WHERE cm.user_id = ?
        ORDER BY c.created_at DESC
    """, (user_id,)).fetchall()

def get_community_members(community_id):
    conn = get_db()
    return conn.execute("""
        SELECT u.id, u.full_name, cm.role, cm.joined_at
        FROM community_members cm
        JOIN users u ON cm.user_id = u.id
        WHERE cm.community_id = ?
        ORDER BY cm.role DESC, cm.joined_at ASC
    """, (community_id,)).fetchall()

def is_member(community_id, user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT role FROM community_members WHERE community_id = ? AND user_id = ?",
        (community_id, user_id)
    ).fetchone()
    return row is not None

def is_community_admin(community_id, user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT role FROM community_members WHERE community_id = ? AND user_id = ? AND role = 'admin'",
        (community_id, user_id)
    ).fetchone()
    return row is not None

def get_community_stats(community_id):
    conn = get_db()
    loans = conn.execute("""
        SELECT l.id, l.status, l.principal_minor, l.fee_minor
        FROM loans l
        JOIN loan_requests lr ON lr.id = l.request_id
        WHERE lr.community_id = ? AND l.status != 'cancelled'
    """, (community_id,)).fetchall()

    total_volume_minor = 0
    total_due_minor = 0
    repaid_volume_minor = 0
    outstanding_minor = 0
    active_loans = 0
    overdue_loans = 0
    repaid_loans = 0
    for loan in loans:
        if loan['status'] in ('active', 'overdue', 'repaid'):
            total_volume_minor += loan['principal_minor']
            total_due_minor += loan['principal_minor'] + (loan['fee_minor'] or 0)
            repayments = conn.execute(
                "SELECT COALESCE(SUM(amount_minor), 0) FROM repayments WHERE loan_id = ? AND amount_minor > 0",
                (loan['id'],)
            ).fetchone()[0]
            repaid_volume_minor += repayments
            outstanding_minor += max(
                0, loan['principal_minor'] + (loan['fee_minor'] or 0) - repayments
            )
        if loan['status'] == 'active':
            active_loans += 1
        elif loan['status'] == 'overdue':
            overdue_loans += 1
        elif loan['status'] == 'repaid':
            repaid_loans += 1

    stats = {
        'total_members': conn.execute(
            "SELECT COUNT(*) FROM community_members WHERE community_id = ?", (community_id,)
        ).fetchone()[0],
        'total_requests': conn.execute("SELECT COUNT(*) as c FROM loan_requests WHERE community_id = ?", (community_id,)).fetchone()['c'],
        'pending_requests': conn.execute("SELECT COUNT(*) as c FROM loan_requests WHERE community_id = ? AND status = 'pending'", (community_id,)).fetchone()['c'],
        'total_loans': len(loans),
        'active_loans': active_loans,
        'overdue_loans': overdue_loans,
        'repaid_loans': repaid_loans,
        'total_volume_minor': total_volume_minor,
        'outstanding_minor': outstanding_minor,
        'repaid_volume_minor': repaid_volume_minor,
        'repayment_rate': round(repaid_volume_minor / total_due_minor * 100, 1) if total_due_minor else 0
    }
    return stats

def get_community_loans(community_id, limit=10):
    conn = get_db()
    loans = conn.execute("""
        SELECT l.id, l.borrower_id, l.lender_id, l.principal_minor, l.fee_minor,
               l.currency, l.due_date, l.status, l.created_at,
               borrower.full_name as borrower_name, lender.full_name as lender_name
        FROM loans l
        JOIN loan_requests lr ON lr.id = l.request_id
        JOIN users borrower ON borrower.id = l.borrower_id
        JOIN users lender ON lender.id = l.lender_id
        WHERE lr.community_id = ?
        ORDER BY l.created_at DESC LIMIT ?
    """, (community_id, limit)).fetchall()

    result = []
    for loan in loans:
        item = dict(loan)
        item['outstanding_minor'] = max(
            0,
            loan['principal_minor'] + (loan['fee_minor'] or 0) -
            conn.execute(
                "SELECT COALESCE(SUM(amount_minor), 0) FROM repayments WHERE loan_id = ? AND amount_minor > 0",
                (loan['id'],)
            ).fetchone()[0]
        )
        result.append(item)
    return result

def get_community_activity(community_id, limit=10):
    return get_db().execute("""
        SELECT a.action, a.created_at, u.full_name as actor_name
        FROM audit_log a
        LEFT JOIN users u ON u.id = a.actor_id
        WHERE a.entity_type = 'community' AND a.entity_id = ?
        ORDER BY a.created_at DESC, a.id DESC LIMIT ?
    """, (community_id, limit)).fetchall()

def _has_unsettled_community_activity(conn, community_id, user_id):
    pending = conn.execute("""
        SELECT 1 FROM loan_requests
        WHERE community_id = ? AND borrower_id = ? AND status = 'pending'
        LIMIT 1
    """, (community_id, user_id)).fetchone()
    if pending:
        return True
    return conn.execute("""
        SELECT 1 FROM loans l
        JOIN loan_requests lr ON lr.id = l.request_id
        WHERE lr.community_id = ? AND l.status IN ('awaiting_agreement', 'active', 'overdue')
          AND (l.borrower_id = ? OR l.lender_id = ?)
        LIMIT 1
    """, (community_id, user_id, user_id)).fetchone() is not None

def leave_community(community_id, user_id):
    conn = get_db()
    with db_transaction(conn):
        conn.execute("BEGIN IMMEDIATE")
        member = conn.execute(
            "SELECT role FROM community_members WHERE community_id = ? AND user_id = ?",
            (community_id, user_id)
        ).fetchone()
        if not member:
            return False, "You are not a member of this community."
        if member['role'] == 'admin':
            other_admin = conn.execute(
                "SELECT 1 FROM community_members WHERE community_id = ? AND role = 'admin' AND user_id != ? LIMIT 1",
                (community_id, user_id)
            ).fetchone()
            if not other_admin:
                return False, "The last administrator cannot leave. Transfer administrator privileges first."
        if _has_unsettled_community_activity(conn, community_id, user_id):
            return False, "You cannot leave while you have pending requests or unsettled loans in this community."
        conn.execute(
            "DELETE FROM community_members WHERE community_id = ? AND user_id = ?",
            (community_id, user_id)
        )
        log_action(user_id, 'COMMUNITY_LEFT', 'community', community_id, conn=conn)
    return True, None

def update_community(community_id, admin_id, name, description):
    clean_name = name.strip() if isinstance(name, str) else ""
    clean_description = description.strip() if isinstance(description, str) else ""
    if len(clean_name) < 3 or len(clean_name) > 100:
        return False, "Community name must be between 3 and 100 characters."
    if len(clean_description) > 500:
        return False, "Community description cannot exceed 500 characters."

    conn = get_db()
    with db_transaction(conn):
        conn.execute("BEGIN IMMEDIATE")
        if not is_community_admin(community_id, admin_id):
            return False, "Only a community administrator can edit group details."
        conn.execute(
            "UPDATE communities SET name = ?, description = ? WHERE id = ?",
            (clean_name, clean_description, community_id)
        )
        log_action(admin_id, 'COMMUNITY_UPDATED', 'community', community_id, conn=conn)
    return True, None

def transfer_community_admin(community_id, admin_id, new_admin_id):
    if type(new_admin_id) is not int or new_admin_id <= 0 or new_admin_id == admin_id:
        return False, "Select another community member to become administrator."
    conn = get_db()
    with db_transaction(conn):
        conn.execute("BEGIN IMMEDIATE")
        if not is_community_admin(community_id, admin_id):
            return False, "Only a community administrator can transfer administrator privileges."
        target = conn.execute(
            "SELECT role FROM community_members WHERE community_id = ? AND user_id = ?",
            (community_id, new_admin_id)
        ).fetchone()
        if not target:
            return False, "The selected user is not a member of this community."
        conn.execute(
            "UPDATE community_members SET role = 'member' WHERE community_id = ? AND user_id = ?",
            (community_id, admin_id)
        )
        conn.execute(
            "UPDATE community_members SET role = 'admin' WHERE community_id = ? AND user_id = ?",
            (community_id, new_admin_id)
        )
        log_action(admin_id, 'COMMUNITY_ADMIN_TRANSFERRED', 'community', community_id, conn=conn)
    return True, None

def remove_community_member(community_id, admin_id, member_id):
    if type(member_id) is not int or member_id <= 0 or member_id == admin_id:
        return False, "Select another member to remove. Use Leave Community to remove yourself."
    conn = get_db()
    with db_transaction(conn):
        conn.execute("BEGIN IMMEDIATE")
        if not is_community_admin(community_id, admin_id):
            return False, "Only a community administrator can remove members."
        target = conn.execute(
            "SELECT role FROM community_members WHERE community_id = ? AND user_id = ?",
            (community_id, member_id)
        ).fetchone()
        if not target:
            return False, "That user is not a member of this community."
        if target['role'] == 'admin':
            return False, "Transfer administrator privileges before removing an administrator."
        if _has_unsettled_community_activity(conn, community_id, member_id):
            return False, "This member has pending requests or unsettled loans and cannot be removed."
        conn.execute(
            "DELETE FROM community_members WHERE community_id = ? AND user_id = ?",
            (community_id, member_id)
        )
        log_action(admin_id, 'COMMUNITY_MEMBER_REMOVED', 'community', community_id, conn=conn)
    return True, None

def regenerate_community_invite_code(community_id, admin_id):
    conn = get_db()
    with db_transaction(conn):
        conn.execute("BEGIN IMMEDIATE")
        if not is_community_admin(community_id, admin_id):
            return None, "Only a community administrator can regenerate the invitation code."
        for _ in range(5):
            invite_code = generate_invite_code()
            try:
                updated = conn.execute(
                    "UPDATE communities SET invite_code = ? WHERE id = ?",
                    (invite_code, community_id)
                ).rowcount
                if updated:
                    log_action(admin_id, 'COMMUNITY_INVITE_REGENERATED', 'community', community_id, conn=conn)
                    return invite_code, None
            except sqlite3.IntegrityError:
                continue
        return None, "Unable to generate a unique invitation code. Please try again."
