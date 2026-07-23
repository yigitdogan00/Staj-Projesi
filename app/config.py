import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '..', '.env'), override=True)
if os.path.exists('/etc/secrets/.env'):
    load_dotenv('/etc/secrets/.env', override=True)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super-secret-key-for-booking-system'
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'https')
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    # Database Configuration (PostgreSQL when DATABASE_URL is set, SQLite fallback)
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = db_url
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')

    logs_db_url = os.environ.get('LOGS_DATABASE_URL') or SQLALCHEMY_DATABASE_URI
    if logs_db_url.startswith("postgres://"):
        logs_db_url = logs_db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_BINDS = {'logs': logs_db_url}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    
    # APScheduler
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = "Europe/Istanbul"
    
    # File Uploads
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads', 'documents')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024 # 10 MB limit
    
    # Web Push
    VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY')
    VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY')
    VAPID_CLAIM_EMAIL = os.environ.get('VAPID_CLAIM_EMAIL')
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

    # Google Gemini
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

    # Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    BREVO_API_KEY = os.environ.get('BREVO_API_KEY')
