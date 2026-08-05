import os
from flask import Flask, request, session, render_template, redirect, url_for, flash
from flask_login import current_user
from flask_babel import gettext
from app.config import Config
from app.extensions import db, login_manager, bcrypt, babel, scheduler

def get_locale():
    if 'lang' in session:
        return session['lang']
    return request.accept_languages.best_match(['tr', 'en']) or 'tr'

def compile_translations(app):
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
    
    # 1. Non-blocking Asynchronous Logging (QueueHandler + QueueListener)
    from app.async_logger import init_async_logging
    init_async_logging(app)
    
    # 2. Antigravity Self-Healing Monkey Patching
    from app.antigravity_healer import init_antigravity_healer
    init_antigravity_healer(app)
    
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
    
    # 2. Single-Worker Flask-APScheduler Initialization (Cross-process Lock)
    from app.scheduler_utils import init_single_worker_scheduler
    init_single_worker_scheduler(app, scheduler)
    
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

    # 3. Teardown Database Session Cleanup After Every Request
    @app.teardown_appcontext
    def teardown_db_session(exception=None):
        if exception:
            db.session.rollback()
        db.session.remove()

    @app.errorhandler(403)
    def forbidden_error(error):
        if not current_user.is_authenticated:
            flash(gettext('Lütfen bu sayfaya erişmek için önce giriş yapın.'), 'warning')
            return redirect(url_for('auth.login', next=request.url))
        flash(gettext('Bu sayfaya erişim yetkiniz bulunmamaktadır.'), 'danger')
        return redirect(url_for('main.dashboard'))

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
                ('room', 'english_description', 'VARCHAR(200)'),
                ('reservation', 'checked_in', 'BOOLEAN DEFAULT FALSE'),
                ('audit_log', 'is_hidden', 'BOOLEAN DEFAULT FALSE')
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
                admin = User(username='Admin', email=admin_email, password_hash=hashed_password, is_admin=True, is_verified=True)
                db.session.add(admin)

            # Seed Test User if missing
            test_email = "test@sirket.com"
            test_user = User.query.filter_by(email=test_email).first()
            if not test_user:
                hashed_password = bcrypt.generate_password_hash('test1234').decode('utf-8')
                test_user = User(username='TestUser', email=test_email, password_hash=hashed_password, is_admin=False, is_verified=True)
                db.session.add(test_user)

            # Seed Default Meeting Rooms if no rooms exist
            room_en_desc_map = {
                "İnovasyon": ("Innovation", "TV, AC, Wireless Mirroring, Whiteboard and Video Conference System."),
                "Sinerji": ("Synergy", "TV, AC, HDMI Screen Projection, Meeting Table and Ergonomic Chairs."),
                "Vizyon": ("Vision", "Smart Board, AC, Projection Screen Feature and Apple TV."),
                "Strateji": ("Strategy", "Dual TV Display, AC, Screen Mirroring and Sound Insulation."),
                "Dinamik": ("Dynamic", "Large Screen TV, AC, Screen Mirroring and Lounge Area.")
            }

            if Room.query.count() == 0:
                rooms_data = [
                    {"name": "İnovasyon", "english_name": "Innovation", "capacity": 12, "description": "TV, Klima, Kablosuz Yansıtma Özelliği, Beyaz Tahta ve Video Konferans Sistemi.", "english_description": "TV, AC, Wireless Mirroring, Whiteboard and Video Conference System."},
                    {"name": "Sinerji", "english_name": "Synergy", "capacity": 12, "description": "TV, Klima, HDMI Yansıtma, Toplantı Masası ve Ergonomik Koltuklar.", "english_description": "TV, AC, HDMI Screen Projection, Meeting Table and Ergonomic Chairs."},
                    {"name": "Vizyon", "english_name": "Vision", "capacity": 12, "description": "Akıllı Tahta, Klima, Projeksiyon ile Yansıtma Özelliği ve Apple TV.", "english_description": "Smart Board, AC, Projection Screen Feature and Apple TV."},
                    {"name": "Strateji", "english_name": "Strategy", "capacity": 12, "description": "Çift TV Ekranı, Klima, Yansıtma Özelliği ve Ses Yalıtımı.", "english_description": "Dual TV Display, AC, Screen Mirroring and Sound Insulation."},
                    {"name": "Dinamik", "english_name": "Dynamic", "capacity": 12, "description": "Geniş Ekran TV, Klima, Yansıtma Özelliği ve Dinlenme Alanı.", "english_description": "Large Screen TV, AC, Screen Mirroring and Lounge Area."}
                ]
                for r_data in rooms_data:
                    new_room = Room(name=r_data["name"], english_name=r_data["english_name"], capacity=r_data["capacity"], description=r_data["description"], english_description=r_data["english_description"])
                    db.session.add(new_room)
            else:
                for r in Room.query.all():
                    if r.name in room_en_desc_map:
                        en_name, en_desc = room_en_desc_map[r.name]
                        if not r.english_name:
                            r.english_name = en_name
                        if not r.english_description:
                            r.english_description = en_desc

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Auto-seed error: {e}")

    return app
