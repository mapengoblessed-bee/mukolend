import csv
import io
from datetime import datetime, date
from database import get_db
from services.loan_service import sync_overdue_loans
from services.repayment_service import calculate_outstanding_balance

def get_analytics_data(community_id=None, start_date=None, end_date=None, status_filter=None):
    sync_overdue_loans()
    conn = get_db()

    # Base WHERE clauses for filtering
    loan_where = ["l.status != 'cancelled'"]
    loan_params = []
    req_where = ["1=1"]
    req_params = []

    if community_id:
        loan_where.append("lr.community_id = ?")
        loan_params.append(community_id)
        req_where.append("lr.community_id = ?")
        req_params.append(community_id)

    if start_date:
        loan_where.append("DATE(l.created_at) >= ?")
        loan_params.append(start_date)
        req_where.append("DATE(lr.created_at) >= ?")
        req_params.append(start_date)

    if end_date:
        loan_where.append("DATE(l.created_at) <= ?")
        loan_params.append(end_date)
        req_where.append("DATE(lr.created_at) <= ?")
        req_params.append(end_date)

    if status_filter:
        loan_where.append("l.status = ?")
        loan_params.append(status_filter)

    loan_where_str = " AND ".join(loan_where)
    req_where_str = " AND ".join(req_where)

    # 1. 11 KPI Cards
    registered_members = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()['c']
    active_communities = conn.execute("SELECT COUNT(*) as c FROM communities").fetchone()['c']
    
    total_loan_requests = conn.execute(f"SELECT COUNT(*) as c FROM loan_requests lr WHERE {req_where_str}", req_params).fetchone()['c']
    total_requested_minor = conn.execute(
        f"SELECT COALESCE(SUM(lr.amount_minor), 0) as total FROM loan_requests lr WHERE {req_where_str}",
        req_params
    ).fetchone()['total']
    pending_requests = conn.execute(f"SELECT COUNT(*) as c FROM loan_requests lr WHERE lr.status = 'pending' AND {req_where_str}", req_params).fetchone()['c']
    pending_requested_minor = conn.execute(
        f"""SELECT COALESCE(SUM(lr.amount_minor), 0) as total
            FROM loan_requests lr WHERE lr.status = 'pending' AND {req_where_str}""",
        req_params
    ).fetchone()['total']
    accepted_requests = conn.execute(f"SELECT COUNT(*) as c FROM loan_requests lr WHERE lr.status = 'accepted' AND {req_where_str}", req_params).fetchone()['c']

    # Approved loans & financial sums
    approved_loans_rows = conn.execute(f"""
        SELECT l.id, l.principal_minor, l.fee_minor, l.status
        FROM loans l
        JOIN loan_requests lr ON l.request_id = lr.id
        WHERE {loan_where_str}
    """, loan_params).fetchall()

    total_approved_principal_minor = 0
    total_repayments_minor = 0
    total_outstanding_minor = 0
    total_due_minor = 0
    active_loans_count = 0
    overdue_loans_count = 0

    for l in approved_loans_rows:
        if l['status'] not in ('active', 'overdue', 'repaid'):
            continue
        total_approved_principal_minor += l['principal_minor']
        principal, fee, due, repaid, out = calculate_outstanding_balance(l['id'], conn=conn)
        total_repayments_minor += repaid
        total_outstanding_minor += out
        total_due_minor += due
        if l['status'] == 'active':
            active_loans_count += 1
        elif l['status'] == 'overdue':
            overdue_loans_count += 1

    repayment_rate = round((total_repayments_minor / total_due_minor * 100), 1) if total_due_minor > 0 else 100.0

    kpis = {
        'registered_members': registered_members,
        'active_communities': active_communities,
        'total_loan_requests': total_loan_requests,
        'total_requested_minor': total_requested_minor,
        'pending_requests': pending_requests,
        'pending_requested_minor': pending_requested_minor,
        'accepted_requests': accepted_requests,
        'total_approved_principal_minor': total_approved_principal_minor,
        'total_repayments_minor': total_repayments_minor,
        'total_outstanding_minor': total_outstanding_minor,
        'active_loans_count': active_loans_count,
        'overdue_loans_count': overdue_loans_count,
        'repayment_performance_rate': repayment_rate
    }

    # 2. Chart 1: Loan Requests Over Time (Daily / Monthly)
    requests_over_time = conn.execute(f"""
        SELECT SUBSTR(lr.created_at, 1, 10) as req_date, COUNT(*) as count,
               COALESCE(SUM(lr.amount_minor), 0) / 100.0 as amount_total
        FROM loan_requests lr
        WHERE {req_where_str}
        GROUP BY SUBSTR(lr.created_at, 1, 10)
        ORDER BY req_date ASC
    """, req_params).fetchall()

    # 3. Chart 2: Loan Status Distribution
    status_distribution = conn.execute(f"""
        SELECT l.status, COUNT(*) as count
        FROM loans l
        JOIN loan_requests lr ON l.request_id = lr.id
        WHERE {loan_where_str}
        GROUP BY l.status
    """, loan_params).fetchall()

    # 4. Chart 3: Loan Value by Community
    value_by_community = conn.execute("""
        SELECT c.name as community_name,
               COALESCE(SUM(l.principal_minor), 0) / 100.0 as total_principal
        FROM communities c
        LEFT JOIN loan_requests lr ON c.id = lr.community_id
        LEFT JOIN loans l ON lr.id = l.request_id AND l.status IN ('active', 'overdue', 'repaid')
        GROUP BY c.id, c.name
        ORDER BY total_principal DESC
    """).fetchall()

    # 5. Chart 4: Repayments Over Time
    repayments_over_time = conn.execute("""
        SELECT SUBSTR(r.payment_date, 1, 10) as p_date,
               COALESCE(SUM(r.amount_minor), 0) / 100.0 as amount_total,
               COUNT(*) as count
        FROM repayments r
        GROUP BY SUBSTR(r.payment_date, 1, 10)
        ORDER BY p_date ASC
    """).fetchall()

    # 6. Chart 5: Outstanding Balance by Community
    comms = conn.execute("SELECT id, name FROM communities").fetchall()
    comm_outstanding_data = []
    for c in comms:
        c_loans = conn.execute("""
            SELECT l.id FROM loans l
            JOIN loan_requests lr ON l.request_id = lr.id
            WHERE lr.community_id = ? AND l.status IN ('active', 'overdue')
        """, (c['id'],)).fetchall()
        c_out = sum(calculate_outstanding_balance(cl['id'], conn=conn)[4] for cl in c_loans)
        comm_outstanding_data.append({
            'name': c['name'],
            'outstanding': c_out / 100.0
        })

    # 7. Chart 6: Loan Due-Date Overview
    due_overview = {'not_due': 0, 'due_soon': 0, 'overdue': 0, 'repaid': 0}
    for l in approved_loans_rows:
        _, _, _, _, out = calculate_outstanding_balance(l['id'], conn=conn)
        row = conn.execute("SELECT due_date, status FROM loans WHERE id = ?", (l['id'],)).fetchone()
        ind = conn.execute("SELECT due_date FROM loans WHERE id = ?", (l['id'],)).fetchone()
        if l['status'] == 'repaid' or out == 0:
            due_overview['repaid'] += 1
        elif l['status'] == 'overdue':
            due_overview['overdue'] += 1
        else:
            try:
                due_d = datetime.strptime(row['due_date'], "%Y-%m-%d").date()
                diff = (due_d - date.today()).days
                if diff < 0:
                    due_overview['overdue'] += 1
                elif diff <= 3:
                    due_overview['due_soon'] += 1
                else:
                    due_overview['not_due'] += 1
            except Exception:
                due_overview['not_due'] += 1

    # 8. Chart 7: Membership Growth Over Time
    member_growth = conn.execute("""
        SELECT SUBSTR(created_at, 1, 10) as reg_date, COUNT(*) as daily_count
        FROM users
        GROUP BY SUBSTR(created_at, 1, 10)
        ORDER BY reg_date ASC
    """).fetchall()

    # Cumulative summation
    cumulative_members = []
    running_total = 0
    for mg in member_growth:
        running_total += mg['daily_count']
        cumulative_members.append({'date': mg['reg_date'], 'total': running_total})

    charts = {
        'requests_over_time': [dict(r) for r in requests_over_time],
        'status_distribution': [dict(s) for s in status_distribution],
        'value_by_community': [dict(v) for v in value_by_community],
        'repayments_over_time': [dict(ro) for ro in repayments_over_time],
        'outstanding_by_community': comm_outstanding_data,
        'due_overview': due_overview,
        'member_growth': cumulative_members
    }

    all_communities = conn.execute("SELECT id, name FROM communities ORDER BY name").fetchall()

    return kpis, charts, all_communities

def export_table_to_csv(table_name):
    """
    Exports clean, un-nested flat data for Power BI ingestion.
    """
    conn = get_db()
    allowed_tables = ['users', 'communities', 'loan_requests', 'loans', 'repayments', 'audit_log']
    if table_name not in allowed_tables:
        return None

    if table_name == 'users':
        query = "SELECT id, full_name, email, role, created_at FROM users"
    elif table_name == 'communities':
        query = "SELECT id, name, description, invite_code, created_by, created_at FROM communities"
    elif table_name == 'loan_requests':
        query = """
            SELECT id, community_id, borrower_id, amount_minor, amount_minor / 100.0 as amount_usd,
                   currency, reason, proposed_due_date, status, created_at
            FROM loan_requests
        """
    elif table_name == 'loans':
        query = """
            SELECT l.id, l.request_id, l.lender_id, l.borrower_id,
                   l.principal_minor, l.principal_minor / 100.0 as principal_usd,
                   l.fee_minor, l.fee_minor / 100.0 as fee_usd,
                   (l.principal_minor + l.fee_minor) / 100.0 as total_due_usd,
                   l.currency, l.due_date, l.borrower_accepted, l.lender_accepted,
                   l.borrower_accepted_at, l.lender_accepted_at, l.status, l.created_at
            FROM loans l
        """
    elif table_name == 'repayments':
        query = """
            SELECT id, loan_id, amount_minor, amount_minor / 100.0 as amount_usd,
                   reference, recorded_by, payment_date, created_at
            FROM repayments
        """
    elif table_name == 'audit_log':
        query = "SELECT id, actor_id, action, entity_type, entity_id, created_at FROM audit_log"

    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()

    output = io.StringIO()
    if rows:
        headers = [description[0] for description in cursor.description]
        writer = csv.writer(output)
        writer.writerow(headers)
        for r in rows:
            writer.writerow(list(r))
    else:
        writer = csv.writer(output)
        writer.writerow(["id", "created_at"])

    return output.getvalue()
