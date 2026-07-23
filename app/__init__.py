from flask import Flask, request, session
from app.config import Config
from app.extensions import db, login_manager, bcrypt, babel, scheduler

def get_locale():
    if 'lang' in session:
        return session['lang']
    return request.accept_languages.best_match(['tr', 'en']) or 'tr'

def compile_translations(app):
    import os
    import polib
    try:
        po_path = os.path.join(app.root_path, 'translations', 'en', 'LC_MESSAGES', 'messages.po')
        mo_path = os.path.join(app.root_path, 'translations', 'en', 'LC_MESSAGES', 'messages.mo')
        if os.path.exists(po_path):
            po = polib.pofile(po_path)
            po.save_as_mofile(mo_path)
            app.logger.info("Translations successfully compiled programmatically.")
    except Exception as e:
        app.logger.error(f"Error compiling translations: {e}")

from werkzeug.middleware.proxy_fix import ProxyFix

def create_app(config_class=Config):
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    app.config.from_object(config_class)
    
    # Compile translations on startup
    compile_translations(app)
    
    app.config['BABEL_DEFAULT_LOCALE'] = 'tr'
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    # Initialize Extensions
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    babel.init_app(app, locale_selector=get_locale)
    
    scheduler.init_app(app)
    
    from app.extensions import oauth
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=app.config.get('GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )    
    from app.jobs import check_upcoming_reservations, check_short_term_reminders
    try:
        # Schedule the job to run daily at 08:00 AM
        scheduler.add_job(id='Daily Reservation Check', func=check_upcoming_reservations, args=[app], trigger='cron', hour=8, minute=0, replace_existing=True)
        
        # Schedule short-term reminders to run exactly at the 0th second of every minute
        scheduler.add_job(id='Short Term Reminder Check', func=check_short_term_reminders, args=[app], trigger='cron', second=0, replace_existing=True)
        
        if not scheduler.running:
            scheduler.start()
    except Exception as e:
        app.logger.error(f"APScheduler Startup Error: {e}")

    # Register Blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    @app.route('/health')
    def health_check():
        return {'status': 'healthy'}

    with app.app_context():
        from sqlalchemy import inspect, text
        db.create_all()
        try:
            inspector = inspect(db.engine)
            if inspector.has_table('user'):
                columns = [c['name'] for c in inspector.get_columns('user')]
                with db.engine.begin() as conn:
                    if 'is_admin' not in columns:
                        conn.execute(text('ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT FALSE'))
                    if 'first_name' not in columns:
                        conn.execute(text('ALTER TABLE user ADD COLUMN first_name VARCHAR(50)'))
                    if 'last_name' not in columns:
                        conn.execute(text('ALTER TABLE user ADD COLUMN last_name VARCHAR(50)'))
        except Exception as e:
            app.logger.error(f"Migration error: {e}")

    return app
