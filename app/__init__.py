import os
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

    # Ensure static directories exist
    os.makedirs(app.config.get('UPLOAD_FOLDER', os.path.join(app.root_path, 'static', 'uploads', 'documents')), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'static', 'profile_pics'), exist_ok=True)

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f"Internal Server Error: {error}", exc_info=True)
        return render_template('errors/500.html'), 500

    with app.app_context():
        from sqlalchemy import inspect, text
        from app.models import User, Room
        
        # 1. Automatic table creation for main DB and logs DB
        try:
            db.create_all()
        except Exception as e:
            app.logger.error(f"db.create_all error: {e}")
        
        # 2. Safe schema column migrations (each in isolated block)
        try:
            inspector = inspect(db.engine)
            migrations = [
                ('user', 'is_admin', 'BOOLEAN DEFAULT FALSE'),
                ('user', 'first_name', 'VARCHAR(50)'),
                ('user', 'last_name', 'VARCHAR(50)'),
                ('room', 'english_name', 'VARCHAR(50)'),
                ('reservation', 'checked_in', 'BOOLEAN DEFAULT FALSE')
            ]
            for tbl, col, col_type in migrations:
                try:
                    if inspector.has_table(tbl):
                        cols = [c['name'] for c in inspector.get_columns(tbl)]
                        if col not in cols:
                            with db.engine.begin() as conn:
                                conn.execute(text(f'ALTER TABLE "{tbl}" ADD COLUMN {col} {col_type}'))
                except Exception as m_err:
                    app.logger.warning(f"Migration error for {tbl}.{col}: {m_err}")
        except Exception as e:
            app.logger.error(f"Migration check error: {e}")

        # 3. Non-destructive Seed (Only adds data if missing)
        try:
            # Seed Admin User if missing
            admin_email = "admin@sirket.com"
            admin = User.query.filter_by(email=admin_email).first()
            if not admin:
                hashed_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
                admin = User(username='Admin', email=admin_email, password_hash=hashed_password, is_admin=True)
                db.session.add(admin)

            # Seed Test User if missing
            test_email = "test@sirket.com"
            test_user = User.query.filter_by(email=test_email).first()
            if not test_user:
                hashed_password = bcrypt.generate_password_hash('test1234').decode('utf-8')
                test_user = User(username='TestUser', email=test_email, password_hash=hashed_password, is_admin=False)
                db.session.add(test_user)

            # Seed Default Meeting Rooms if no rooms exist
            if Room.query.count() == 0:
                rooms_data = [
                    {"name": "İnovasyon", "capacity": 12, "description": "TV, Klima, Kablosuz Yansıtma Özelliği, Beyaz Tahta ve Video Konferans Sistemi."},
                    {"name": "Sinerji", "capacity": 12, "description": "TV, Klima, HDMI Yansıtma, Toplantı Masası ve Ergonomik Koltuklar."},
                    {"name": "Vizyon", "capacity": 12, "description": "Akıllı Tahta, Klima, Projeksiyon ile Yansıtma Özelliği ve Apple TV."},
                    {"name": "Strateji", "capacity": 12, "description": "Çift TV Ekranı, Klima, Yansıtma Özelliği ve Ses Yalıtımı."},
                    {"name": "Dinamik", "capacity": 12, "description": "Geniş Ekran TV, Klima, Yansıtma Özelliği ve Dinlenme Alanı."}
                ]
                for r_data in rooms_data:
                    new_room = Room(name=r_data["name"], capacity=r_data["capacity"], description=r_data["description"])
                    db.session.add(new_room)

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Auto-seed error: {e}")

    return app
