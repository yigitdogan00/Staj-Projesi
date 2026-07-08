from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_babel import Babel

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
bcrypt = Bcrypt()
babel = Babel()

from flask_apscheduler import APScheduler
scheduler = APScheduler()

from authlib.integrations.flask_client import OAuth
oauth = OAuth()
