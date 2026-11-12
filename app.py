import os
from datetime import datetime
from flask import Flask, render_template, session
from flask_wtf.csrf import CSRFProtect
from config import Config
from database import close_db, init_db, get_db
from services.auth_service import get_user_by_id, get_all_demo_users

csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    if isinstance(config_class, dict):
        app.config.from_object(Config)
        app.config.update(config_class)
    else:
        app.config.from_object(config_class)

    # Initialize extensions
    csrf.init_app(app)

    # Teardown database connection
    app.teardown_appcontext(close_db)

    # Register Jinja Template Filters
    @app.template_filter('currency')
    def currency_filter(amount_minor, currency="USD"):
        if amount_minor is None:
            amount_minor = 0
        dollars = amount_minor / 100.0
        symbol = "$" if currency == "USD" else currency + " "
        return f"{symbol}{dollars:,.2f}"

    @app.template_filter('format_date')
    def format_date_filter(date_str):
        if not date_str:
            return "—"
        try:
            if ' ' in str(date_str):
                dt = datetime.strptime(str(date_str)[:19], "%Y-%m-%d %H:%M:%S")
            else:
                dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
            return dt.strftime("%d %b %Y")
        except Exception:
            return str(date_str)

    # Context Processors for Templates
    @app.context_processor
    def inject_globals():
        current_user = None
        user_id = session.get('user_id')
        if user_id:
            current_user = get_user_by_id(user_id)

        demo_users = get_all_demo_users()
        return {
            'current_user': current_user,
            'demo_users': demo_users,
            'now': datetime.now()
        }

    # Register Blueprints
    from routes.auth_routes import auth_bp
    from routes.main_routes import main_bp
    from routes.community_routes import community_bp
    from routes.loan_request_routes import loan_request_bp
    from routes.loan_routes import loan_bp
    from routes.repayment_routes import repayment_bp
    from routes.analytics_routes import analytics_bp
    from routes.profile_routes import profile_bp
    from routes.admin_routes import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(community_bp)
    app.register_blueprint(loan_request_bp)
    app.register_blueprint(loan_bp)
    app.register_blueprint(repayment_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(admin_bp)

    # Error Handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"MukoLend Fintech MVP running on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)

