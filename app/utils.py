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

COMMON_TURKISH_NAMES = {
    'yigit': 'Yiğit', 'ahmet': 'Ahmet', 'mehmet': 'Mehmet', 'ali': 'Ali', 'can': 'Can',
    'burak': 'Burak', 'emre': 'Emre', 'oguz': 'Oğuz', 'murat': 'Murat', 'mustafa': 'Mustafa',
    'selin': 'Selin', 'ayse': 'Ayşe', 'fatma': 'Fatma', 'zeynep': 'Zeynep', 'elif': 'Elif',
    'deniz': 'Deniz', 'eren': 'Eren', 'mert': 'Mert', 'berk': 'Berk', 'serkan': 'Serkan',
    'hakan': 'Hakan', 'erhan': 'Erhan', 'onur': 'Onur', 'volkan': 'Volkan', 'semih': 'Semih',
    'metin': 'Metin', 'tarik': 'Tarık', 'cem': 'Cem', 'kerem': 'Kerem', 'koray': 'Koray',
    'kaan': 'Kaan', 'baris': 'Barış', 'boran': 'Boran', 'tolga': 'Tolga', 'ufuk': 'Ufuk',
    'utku': 'Utku', 'yasin': 'Yasin', 'yusuf': 'Yusuf', 'zafer': 'Zafer', 'bulent': 'Bülent',
    'cihat': 'Cihat', 'cenk': 'Cenk', 'ferhat': 'Ferhat', 'furkan': 'Furkan', 'gokhan': 'Gökhan',
    'gurkan': 'Gürkan', 'huseyin': 'Hüseyin', 'ismail': 'İsmail', 'kadir': 'Kadir', 'levent': 'Levent',
    'mahmut': 'Mahmut', 'orhan': 'Orhan', 'osman': 'Osman', 'ramazan': 'Ramazan', 'samet': 'Samet',
    'sedat': 'Sedat', 'sinan': 'Sinan', 'suat': 'Suat', 'tayfun': 'Tayfun', 'tuncay': 'Tuncay',
    'vural': 'Vural', 'yavuz': 'Yavuz', 'mesut': 'Mesut', 'bugra': 'Buğra', 'alp': 'Alp',
    'alper': 'Alper', 'batuhan': 'Batuhan', 'dogukan': 'Doğukan', 'berkay': 'Berkay', 'gokce': 'Gökçe',
    'irem': 'İrem', 'hazal': 'Hazal', 'ezgi': 'Ezgi', 'gizem': 'Gizem', 'hilal': 'Hilal',
    'simge': 'Simge', 'tuba': 'Tuğba', 'tugba': 'Tuğba', 'duygu': 'Duygu', 'hande': 'Hande',
    'pinar': 'Pınar', 'seda': 'Seda', 'sibel': 'Sibel', 'sevil': 'Sevil', 'buse': 'Buse',
    'bensu': 'Bensu', 'ece': 'Ece', 'eda': 'Eda', 'esra': 'Esra', 'gamze': 'Gamze'
}

COMMON_TURKISH_SURNAMES = {
    'dogan': 'Doğan', 'demir': 'Demir', 'kaya': 'Kaya', 'celik': 'Çelik', 'sahin': 'Şahin',
    'yildiz': 'Yıldız', 'yildirim': 'Yıldırım', 'ozturk': 'Öztürk', 'aydin': 'Aydın',
    'ozkan': 'Özkan', 'arslan': 'Arslan', 'aslan': 'Aslan', 'polat': 'Polat', 'koc': 'Koç',
    'erdogan': 'Erdoğan', 'yilmaz': 'Yılmaz', 'kurt': 'Kurt', 'ozdemir': 'Özdemir',
    'simsek': 'Şimşek', 'korkmaz': 'Korkmaz', 'cevik': 'Çevik', 'vural': 'Vural', 'sen': 'Şen'
}

def format_word(w):
    w_lower = w.lower()
    if w_lower in COMMON_TURKISH_NAMES:
        return COMMON_TURKISH_NAMES[w_lower]
    if w_lower in COMMON_TURKISH_SURNAMES:
        return COMMON_TURKISH_SURNAMES[w_lower]
    return w.capitalize()

def parse_name_from_email(email, user_info=None):
    import re
    given_name = None
    family_name = None

    if user_info and isinstance(user_info, dict):
        given_name = user_info.get('given_name')
        family_name = user_info.get('family_name')
        if not given_name or not family_name:
            full_name = user_info.get('name', '').strip()
            if full_name and ' ' in full_name:
                parts = full_name.split()
                if not given_name and len(parts) > 0:
                    given_name = parts[0]
                if not family_name and len(parts) > 1:
                    family_name = ' '.join(parts[1:])

    if not given_name or not family_name:
        if email and '@' in email:
            prefix = email.split('@')[0]
            clean_prefix = re.sub(r'\d+$', '', prefix).strip().lower()
            if not clean_prefix:
                clean_prefix = prefix.lower()
            
            parts = re.split(r'[._\-]', clean_prefix)
            parts = [p for p in parts if p]
            
            if len(parts) >= 2:
                if not given_name:
                    given_name = format_word(parts[0])
                if not family_name:
                    family_name = ' '.join(format_word(p) for p in parts[1:])
            elif len(parts) == 1:
                single_str = parts[0]
                matched = False
                for fname in sorted(COMMON_TURKISH_NAMES.keys(), key=len, reverse=True):
                    if single_str.startswith(fname) and len(single_str) > len(fname):
                        if not given_name:
                            given_name = COMMON_TURKISH_NAMES[fname]
                        rem = single_str[len(fname):]
                        if not family_name:
                            family_name = format_word(rem)
                        matched = True
                        break
                
                if not matched:
                    if not given_name:
                        given_name = format_word(single_str)

    return given_name or "", family_name or ""

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
