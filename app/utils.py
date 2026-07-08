from functools import wraps
from flask import abort
from flask_login import current_user

def send_email(to_email, subject, body):
    from flask import current_app
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import requests

    brevo_api_key = current_app.config.get('BREVO_API_KEY')
    sender_email = current_app.config.get('MAIL_USERNAME') or current_app.config.get('MAIL_DEFAULT_SENDER')
    
    # 1) API Yöntemi (Brevo API)
    if brevo_api_key:
        if not sender_email:
            print("E-posta gönderilemedi: Gönderici adresi (MAIL_USERNAME) eksik.", flush=True)
            return False
            
        print(f"[{to_email}] adresine Brevo API üzerinden e-posta gönderimi başlatılıyor...", flush=True)
        try:
            url = "https://api.brevo.com/v3/smtp/email"
            headers = {
                "accept": "application/json",
                "api-key": brevo_api_key,
                "content-type": "application/json"
            }
            data = {
                "sender": {"email": sender_email},
                "to": [{"email": to_email}],
                "subject": subject,
                "textContent": body
            }
            response = requests.post(url, headers=headers, json=data)
            if response.status_code in [200, 201, 202]:
                print(f"[{to_email}] adresine e-posta başarıyla gönderildi (API)!", flush=True)
                return True
            else:
                print(f"E-posta API hatası ({to_email}):", response.text, flush=True)
                return False
        except Exception as e:
            print(f"E-posta API bağlantı hatası ({to_email}):", str(e), flush=True)
            return False

    # 2) Klasik SMTP Yöntemi (Lokal İçin)
    sender_password = current_app.config.get('MAIL_PASSWORD')
    smtp_server = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    smtp_port = current_app.config.get('MAIL_PORT', 587)
    use_tls = current_app.config.get('MAIL_USE_TLS', True)
    
    if not sender_email or not sender_password:
        print("E-posta ayarları eksik. E-posta gönderilemedi:", subject, flush=True)
        return False
        
    msg = MIMEMultipart()
    msg['From'] = current_app.config.get('MAIL_DEFAULT_SENDER') or sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    print(f"[{to_email}] adresine SMTP üzerinden e-posta gönderimi başlatılıyor...", flush=True)
    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(msg['From'], to_email, text)
        server.quit()
        print(f"[{to_email}] adresine e-posta başarıyla gönderildi!", flush=True)
        return True
    except Exception as e:
        print(f"E-posta gönderme hatası ({to_email}):", str(e), flush=True)
        return False

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def send_booking_email(user_email, user_name, room_name, date, start_time, end_time):
    # Dummy email sender
    print("="*50)
    print(f"E-POSTA GÖNDERİLDİ:")
    print(f"Kime: {user_email}")
    print(f"Konu: {room_name} Rezervasyon Onayı")
    print(f"İçerik: Merhaba {user_name}, {date} tarihinde {start_time}-{end_time} saatleri arasında {room_name} odası için rezervasyonunuz onaylanmıştır.")
    print("="*50)

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

def send_reset_email(user):
    from flask import url_for
    token = user.get_reset_token()
    reset_url = url_for('auth.reset_token', token=token, _external=True)
    subject = "Şifre Sıfırlama Talebi"
    body = f"""Merhaba {user.username},

Şifrenizi sıfırlamak için aşağıdaki bağlantıya tıklayın:
{reset_url}

Eğer bu talebi siz yapmadıysanız lütfen bu e-postayı dikkate almayın."""
    
    send_email(user.email, subject, body)

def send_password_changed_email(user):
    subject = "Güvenlik Uyarısı: Şifreniz Değiştirildi"
    body = f"""Merhaba {user.username},

Hesabınızın şifresi az önce başarıyla değiştirildi.

Eğer bu işlemi siz yaptıysanız bu e-postayı görmezden gelebilirsiniz.
Ancak bu değişikliği SİZ YAPMADIYSANIZ, hesabınızın güvenliği tehlikede olabilir. Lütfen derhal sistem yöneticisiyle iletişime geçin.

İyi çalışmalar,
Rezervasyon Sistemi
"""
    send_email(user.email, subject, body)

def send_invitation_email(host_username, guest_email, guest_username, room_name, date, start_time, end_time):
    print("\n" + "="*50)
    print("MOCK EMAIL SENDER (Sistem Logu)")
    print(f"Kime: {guest_email}")
    print(f"Konu: Yeni Bir Toplantıya Davet Edildiniz!")
    print(f"İçerik: Merhaba {guest_username},\n")
    print(f"{host_username} sizi bir toplantıya davet etti.")
    print(f"Yer: {room_name}")
    print(f"Tarih: {date}")
    print(f"Saat: {start_time} - {end_time}")
    print("\nLütfen ajandanızı kontrol edip katılım durumunuzu ayarlayın.")
    print("="*50 + "\n")


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
