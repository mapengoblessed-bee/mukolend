from database import get_db, get_standalone_connection

def log_action(actor_id, action, entity_type, entity_id, conn=None):
    """
    Records an immutable audit log entry.
    actor_id: user id or None for system
    action: e.g. 'USER_REGISTERED', 'COMMUNITY_CREATED', 'REQUEST_CREATED', 'AGREEMENT_ACKNOWLEDGED', 'REPAYMENT_RECORDED'
    entity_type: 'user', 'community', 'loan_request', 'loan', 'repayment'
    entity_id: primary key of the entity
    """
    should_close = False
    if conn is None:
        try:
            conn = get_db()
        except RuntimeError:
            conn = get_standalone_connection()
            should_close = True

    conn.execute(
        "INSERT INTO audit_log (actor_id, action, entity_type, entity_id) VALUES (?, ?, ?, ?)",
        (actor_id, action, entity_type, entity_id)
    )
    if should_close:
        conn.commit()
        conn.close()

def get_recent_logs(limit=50, entity_type=None):
    conn = get_db()
    query = """
        SELECT a.*, u.full_name as actor_name, u.email as actor_email
        FROM audit_log a
        LEFT JOIN users u ON a.actor_id = u.id
    """
    params = []
    if entity_type:
        query += " WHERE a.entity_type = ?"
        params.append(entity_type)
    query += " ORDER BY a.created_at DESC LIMIT ?"
    params.append(limit)
    return conn.execute(query, params).fetchall()
