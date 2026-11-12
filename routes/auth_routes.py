from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from services.auth_service import register_user, authenticate_user, get_user_by_id, get_all_demo_users

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '')
        password = request.form.get('password', '')

        user, error = authenticate_user(email, password)
        if error:
            flash(error, 'danger')
        else:
            session.clear()
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']
            session['user_role'] = user['role']
            session.permanent = True
            flash(f"Welcome back, {user['full_name']}!", 'success')
            next_url = request.args.get('next')
            return redirect(next_url or url_for('main.dashboard'))

    demo_users = get_all_demo_users()
    return render_template('auth/login.html', demo_users=demo_users)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '')
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        user_id, errors = register_user(full_name, email, password, confirm_password)
        if errors:
            for err in errors:
                flash(err, 'danger')
        else:
            user = get_user_by_id(user_id)
            session.clear()
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']
            session['user_role'] = user['role']
            session.permanent = True
            flash("Your MukoLend account has been established successfully! Welcome to community lending.", 'success')
            return redirect(url_for('main.dashboard'))

    return render_template('auth/register.html')

@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for('main.index'))

@auth_bp.route('/switch-user/<int:user_id>', methods=['POST', 'GET'])
def switch_user(user_id):
    """
    Hackathon prototype switcher: instantly switch persona to evaluate different roles.
    """
    user = get_user_by_id(user_id)
    if user:
        session.clear()
        session['user_id'] = user['id']
        session['user_name'] = user['full_name']
        session['user_role'] = user['role']
        flash(f"Switched persona to {user['full_name']} ({user['email']}).", "info")
    else:
        flash("User persona not found.", "warning")

    next_url = request.args.get('next')
    return redirect(next_url or url_for('main.dashboard'))
