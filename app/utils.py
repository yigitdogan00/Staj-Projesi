from functools import wraps
from flask import abort
from flask_login import current_user

# send_email removed

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# send_booking_email removed

def generate_google_calendar_url(room_name, date, start_time, end_time):
    from urllib.parse import urlencode
    
    # Format dates to YYYYMMDDTHHMMSSZ
    start_dt = date.replace('-', '') + 'T' + start_time.replace(':', '') + '00Z'
    end_dt = date.replace('-', '') + 'T' + end_time.replace(':', '') + '00Z'
    
    params = {
        'action': 'TEMPLATE',
        'text': f"{room_name} - Toplantı",
        'dates': f"{start_dt}/{end_dt}",
        'details': f"{room_name} odasında planlanan toplantı.",
        'location': f"RND E-Ticaret - {room_name}"
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)

def log_action(user_id, action, details=None):
    from app.models import AuditLog
    from app.extensions import db
    log = AuditLog(user_id=user_id, action=action, details=details)
    db.session.add(log)
    db.session.commit()
    
    # Artık kayıtlar logs.db'de sonsuza kadar kalacak, silinmeyecek.


# email functions removed


def generate_qr_token(reservation_id, user_id):
    from itsdangerous import URLSafeSerializer
    from flask import current_app
    s = URLSafeSerializer(current_app.config['SECRET_KEY'], salt='qr-token')
    return s.dumps({'reservation_id': reservation_id, 'user_id': user_id})

def verify_qr_token(token):
    from itsdangerous import URLSafeSerializer
    from flask import current_app
    s = URLSafeSerializer(current_app.config['SECRET_KEY'], salt='qr-token')
    try:
        data = s.loads(token)
        return data.get('reservation_id'), data.get('user_id')
    except:
        return None, None

def generate_exit_qr_token(reservation_id, user_id):
    from itsdangerous import URLSafeSerializer
    from flask import current_app
    s = URLSafeSerializer(current_app.config['SECRET_KEY'], salt='exit-qr-token')
    return s.dumps({'reservation_id': reservation_id, 'user_id': user_id})

def verify_exit_qr_token(token):
    from itsdangerous import URLSafeSerializer
    from flask import current_app
    s = URLSafeSerializer(current_app.config['SECRET_KEY'], salt='exit-qr-token')
    try:
        data = s.loads(token)
        return data.get('reservation_id'), data.get('user_id')
    except:
        return None, None
