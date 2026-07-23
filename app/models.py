from app.extensions import db, login_manager
from flask_login import UserMixin
from datetime import datetime, timedelta


from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app

def get_turkey_time():
    return datetime.utcnow() + timedelta(hours=3)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=False, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    profile_image = db.Column(db.String(120), nullable=False, default='default.jpg')
    
    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    # Relationship to reservations
    reservations = db.relationship('Reservation', backref='user', lazy=True)

    def get_reset_token(self):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=expires_sec)['user_id']
        except:
            return None
        return User.query.get(user_id)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}')"

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    english_name = db.Column(db.String(50), nullable=True)
    capacity = db.Column(db.Integer, nullable=False, default=10)
    description = db.Column(db.String(200), nullable=True)
    reservations = db.relationship('Reservation', backref='room', lazy=True)
    
    @property
    def display_name(self):
        from flask import session, has_request_context
        lang = 'tr'
        if has_request_context():
            lang = session.get('lang', 'tr')
        if lang == 'en' and self.english_name:
            return self.english_name
        from flask_babel import gettext
        return gettext(self.name)

    def __repr__(self):
        return f"Room('{self.name}')"

reservation_attendees = db.Table('reservation_attendees',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('reservation_id', db.Integer, db.ForeignKey('reservation.id'), primary_key=True)
)

reservation_active_attendees = db.Table('reservation_active_attendees',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('reservation_id', db.Integer, db.ForeignKey('reservation.id'), primary_key=True)
)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    
    # Using String for simplicity in storing date/times for exact hour slot matching
    date = db.Column(db.String(10), nullable=False) # Format: YYYY-MM-DD
    start_time = db.Column(db.String(5), nullable=False) # Format: HH:MM
    end_time = db.Column(db.String(5), nullable=False) # Format: HH:MM
    
    created_at = db.Column(db.DateTime, nullable=False, default=get_turkey_time)
    checked_in = db.Column(db.Boolean, default=False)

    # Relationships
    attendees = db.relationship('User', secondary=reservation_attendees, lazy='subquery', backref=db.backref('invited_reservations', lazy=True))
    active_users = db.relationship('User', secondary=reservation_active_attendees, lazy='subquery', backref=db.backref('active_in_reservations', lazy=True))

    def __repr__(self):
        return f"Reservation('{self.room.name}', '{self.date}' '{self.start_time}-{self.end_time}')"

class AuditLog(db.Model):
    __bind_key__ = 'logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True, nullable=True) # Null for system actions or anonymous
    action = db.Column(db.String(50), nullable=False) # e.g. LOGIN, BOOKING, DELETE_USER
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, index=True, default=get_turkey_time)
    is_hidden = db.Column(db.Boolean, default=False, index=True)
    
    @property
    def user(self):
        from app.models import User
        if self.user_id:
            return User.query.get(self.user_id)
        return None

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reservation_id = db.Column(db.Integer, db.ForeignKey('reservation.id'), nullable=True)
    message = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), default='invitation') # invitation, info
    status = db.Column(db.String(20), default='pending') # pending, accepted, rejected
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_turkey_time)
    
    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic'))
    reservation = db.relationship('Reservation')

    def __repr__(self):
        return f"Notification('{self.type}', '{self.status}')"

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    reservation_id = db.Column(db.Integer, db.ForeignKey('reservation.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=get_turkey_time)

    reservation = db.relationship('Reservation', backref=db.backref('documents', lazy=True, cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('uploaded_documents', lazy=True))

    def __repr__(self):
        return f"Document('{self.filename}')"

class PushSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subscription_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=get_turkey_time)

    user = db.relationship('User', backref=db.backref('push_subscriptions', lazy='dynamic'))

    def __repr__(self):
        return f"PushSubscription(user_id='{self.user_id}')"
