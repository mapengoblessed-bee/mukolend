import re
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db
from services.audit_service import log_action

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def validate_registration(full_name, email, password, confirm_password):
    errors = []
    if not full_name or len(full_name.strip()) < 2:
        errors.append("Full name must be at least 2 characters.")
    if not email or not EMAIL_REGEX.match(email.strip()):
        errors.append("Please enter a valid email address.")
    if not password or len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if password != confirm_password:
        errors.append("Passwords do not match.")
    return errors

def register_user(full_name, email, password, confirm_password, role='user'):
    errors = validate_registration(full_name, email, password, confirm_password)
    if errors:
        return None, errors

    clean_email = email.strip().lower()
    clean_name = full_name.strip()
    conn = get_db()

    existing = conn.execute("SELECT id FROM users WHERE LOWER(email) = ?", (clean_email,)).fetchone()
    if existing:
        return None, ["An account with this email address already exists."]

    pwd_hash = generate_password_hash(password)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (clean_name, clean_email, pwd_hash, role)
    )
    user_id = cursor.lastrowid
    conn.commit()

    log_action(user_id, 'USER_REGISTERED', 'user', user_id, conn=conn)
    return user_id, []

def authenticate_user(email, password):
    clean_email = email.strip().lower()
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE LOWER(email) = ?", (clean_email,)).fetchone()
    if not user:
        return None, "Invalid email or password."

    if not check_password_hash(user['password_hash'], password):
        return None, "Invalid email or password."

    return user, None

def get_user_by_id(user_id):
    conn = get_db()
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

def get_user_by_email(email):
    conn = get_db()
    return conn.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email.strip().lower(),)).fetchone()

def update_user_profile(user_id, full_name, email):
    errors = []
    if not full_name or len(full_name.strip()) < 2:
        errors.append("Full name must be at least 2 characters.")
    if not email or not EMAIL_REGEX.match(email.strip()):
        errors.append("Please enter a valid email address.")
    if errors:
        return False, errors

    clean_email = email.strip().lower()
    clean_name = full_name.strip()
    conn = get_db()

    existing = conn.execute("SELECT id FROM users WHERE LOWER(email) = ? AND id != ?", (clean_email, user_id)).fetchone()
    if existing:
        return False, ["Email address is already in use by another account."]

    conn.execute(
        "UPDATE users SET full_name = ?, email = ? WHERE id = ?",
        (clean_name, clean_email, user_id)
    )
    conn.commit()
    log_action(user_id, 'PROFILE_UPDATED', 'user', user_id, conn=conn)
    return True, []

def get_all_demo_users():
    conn = get_db()
    return conn.execute("SELECT id, full_name, email, role, created_at FROM users ORDER BY id ASC").fetchall()
