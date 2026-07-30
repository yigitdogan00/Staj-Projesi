import random
from datetime import timedelta
from flask import Blueprint, render_template, url_for, flash, redirect, request, session, current_app, g
from flask_login import login_user, current_user, logout_user
from app.extensions import db, bcrypt
from app.models import User, get_turkey_time
from app.forms import RegistrationForm, LoginForm
from flask_babel import gettext
from app.utils import send_verification_code_email, log_action

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        code = f"{random.randint(100000, 999999)}"
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=hashed_password,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            is_verified=False,
            verification_code=code,
            verification_code_expires_at=get_turkey_time() + timedelta(minutes=15)
        )
        try:
            db.session.add(user)
            db.session.commit()
            send_verification_code_email(user, code)
            session['unverified_user_id'] = user.id
            flash(gettext('Kayıt başarılı! Lütfen e-posta adresinize gönderilen 6 haneli doğrulama kodunu girin.'), 'info')
            return redirect(url_for('auth.verify_email'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Registration Error: {e}", exc_info=True)
            flash(gettext('Kayıt işlemi sırasında bir hata oluştu. Bu e-posta zaten kayıtlı olabilir veya butona çift tıklamış olabilirsiniz.'), 'danger')
            return render_template('auth/register.html', title='Kayıt Ol', form=form)
    return render_template('auth/register.html', title='Kayıt Ol', form=form)

@bp.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    user_id = session.get('unverified_user_id')
    if not user_id:
        flash(gettext('Lütfen önce kayıt olun veya giriş yapın.'), 'warning')
        return redirect(url_for('auth.login'))
    
    user = User.query.get_or_404(user_id)
    if user.is_verified:
        session.pop('unverified_user_id', None)
        flash(gettext('Hesabınız zaten doğrulanmış. Giriş yapabilirsiniz.'), 'info')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        input_code = str(request.form.get('code', '')).strip()
        now = get_turkey_time()
        if user.verification_code and user.verification_code == input_code and user.verification_code_expires_at and now <= user.verification_code_expires_at:
            user.is_verified = True
            user.verification_code = None
            user.verification_code_expires_at = None
            db.session.commit()
            session.pop('unverified_user_id', None)
            log_action(user.id, "YENİ_HESAP", f"{user.username} e-posta doğrulamasını tamamlayıp hesabını aktifleştirdi.")
            flash(gettext('E-posta adresiniz başarıyla doğrulandı! Şimdi giriş yapabilirsiniz.'), 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(gettext('Girdiğiniz doğrulama kodu hatalı veya süresi dolmuş.'), 'danger')

    return render_template('auth/verify_email.html', title='E-posta Doğrulama', user=user)

@bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    user_id = session.get('unverified_user_id')
    if not user_id:
        flash(gettext('Kullanıcı oturumu bulunamadı.'), 'warning')
        return redirect(url_for('auth.login'))
    
    user = User.query.get_or_404(user_id)
    if user.is_verified:
        return redirect(url_for('auth.login'))

    code = f"{random.randint(100000, 999999)}"
    user.verification_code = code
    user.verification_code_expires_at = get_turkey_time() + timedelta(minutes=15)
    db.session.commit()

    send_verification_code_email(user, code)
    flash(gettext('Yeni doğrulama kodu e-posta adresinize gönderildi.'), 'success')
    return redirect(url_for('auth.verify_email'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    
    if request.method == 'GET':
        remembered_email = request.cookies.get('remembered_email')
        if remembered_email:
            form.email.data = remembered_email
            form.remember.data = True
            
    # Brute-Force Rate Limiting Protection
    import time
    failed_count = session.get('failed_login_count', 0)
    last_failed_time = session.get('failed_login_time', 0)
    now_ts = time.time()

    if last_failed_time and (now_ts - last_failed_time > 120):
        failed_count = 0
        session.pop('failed_login_count', None)
        session.pop('failed_login_time', None)

    if failed_count >= 5:
        remaining_secs = max(1, int(120 - (now_ts - last_failed_time)))
        if g.get('current_lang') == 'en':
            msg_text = f"Too many failed login attempts. Please wait {remaining_secs} seconds before trying again."
        else:
            msg_text = f"Çok fazla hatalı giriş denemesi yapıldı. Güvenliğiniz için lütfen {remaining_secs} saniye bekleyip tekrar deneyin."
        flash(msg_text, 'danger')
        return render_template('auth/login.html', title='Giriş Yap', form=form)

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            if not user.is_verified:
                session['unverified_user_id'] = user.id
                flash(gettext('Hesabınız henüz doğrulanmamış. Lütfen e-posta adresinize gönderilen doğrulama kodunu girin.'), 'warning')
                return redirect(url_for('auth.verify_email'))

            session.pop('failed_login_count', None)
            session.pop('failed_login_time', None)
            login_user(user, remember=False)
            session.pop('interactive_booking_state', None)
            session.pop('last_queried_room_id', None)
            session.pop('last_queried_date', None)
            session.pop('awaiting_random_booking', None)
            
            log_action(user.id, "SİSTEME_GİRİŞ", f"{user.username} sisteme giriş yaptı.")
            
            next_page = request.args.get('next')
            flash(gettext('Giriş başarılı!'), 'success')
            resp = redirect(next_page) if next_page else redirect(url_for('main.index'))
            
            if form.remember.data:
                resp.set_cookie('remembered_email', user.email, max_age=30*24*60*60) # 30 days
            else:
                resp.set_cookie('remembered_email', '', expires=0)
                
            return resp
        else:
            session['failed_login_count'] = failed_count + 1
            session['failed_login_time'] = time.time()
            log_action(user.id if user else None, "HATALI_GİRİŞ_DENEMESİ", f"{form.email.data} adresiyle hatalı şifre denemesi yapıldı (Deneme: {failed_count + 1}).")
            flash(gettext('Giriş başarısız. Lütfen e-posta ve şifrenizi kontrol edin.'), 'danger')
    return render_template('auth/login.html', title='Giriş Yap', form=form)

@bp.route('/login/google')
def login_google():
    from app.extensions import oauth
    # Dynamic scheme: HTTP for local dev (127.0.0.1/localhost), HTTPS for production/Render
    is_local = request.host.startswith('127.0.0.1') or request.host.startswith('localhost')
    scheme = 'http' if is_local else current_app.config.get('PREFERRED_URL_SCHEME', 'https')
    redirect_uri = url_for('auth.authorize_google', _external=True, _scheme=scheme)
    return oauth.google.authorize_redirect(redirect_uri, prompt='select_account')

@bp.route('/callback')
def authorize_google():
    from app.extensions import oauth
    from app.utils import log_action
    from flask import current_app
    
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')
        if not user_info:
            user_info = oauth.google.userinfo()
            
        if not user_info or not user_info.get('email'):
            flash(gettext('Google ile giriş başarısız oldu: Kullanıcı bilgileri veya e-posta adresi alınamadı.'), 'danger')
            return redirect(url_for('auth.login'))
            
        email = user_info.get('email')
        from app.utils import parse_name_from_email
        parsed_fn, parsed_ln = parse_name_from_email(email, user_info)

        given_name = user_info.get('given_name') or parsed_fn
        family_name = user_info.get('family_name') or parsed_ln
        username = user_info.get('name') or user_info.get('given_name') or email.split('@')[0]

        user = User.query.filter_by(email=email).first()

        if not user:
            user = User(
                username=username,
                email=email,
                first_name=given_name,
                last_name=family_name,
                is_verified=True
            )
            db.session.add(user)
            db.session.commit()
            log_action(user.id, "KULLANICI_KAYIT", f"{user.username} Google Login ile otomatik kayıt oldu.")
        else:
            updated = False
            if not user.is_verified:
                user.is_verified = True
                updated = True
            if given_name and (not user.first_name or user.first_name == ""):
                user.first_name = given_name
                updated = True
            if family_name and (not user.last_name or user.last_name == ""):
                user.last_name = family_name
                updated = True
            if updated:
                db.session.commit()

        login_user(user, remember=False)
        log_action(user.id, "SİSTEME_GİRİŞ", f"{user.username} Google Login ile sisteme giriş yaptı.")
        
        next_page = request.args.get('next')
        flash(gettext('Google ile giriş başarılı! Hoş geldiniz %(name)s', name=user.username), 'success')
        return redirect(next_page) if next_page else redirect(url_for('main.rooms'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Google OAuth Callback Error: {e}", exc_info=True)
        flash(gettext('Google ile giriş yapılırken bir hata oluştu: %(error)s', error=str(e)), 'danger')
        return redirect(url_for('auth.login'))

@bp.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('main.index'))

@bp.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    from app.forms import RequestResetForm
    from app.utils import log_action, send_reset_email
    form = RequestResetForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data).first()
            if user:
                send_reset_email(user)
                try:
                    log_action(user.id, "ŞİFRE_SIFIRLAMA_TALEBİ", f"{form.email.data} için sıfırlama linki e-posta ile gönderildi.")
                except Exception:
                    pass
        except Exception as e:
            current_app.logger.error(f"Error in reset_request: {e}")

        flash(gettext('Eğer sistemimizde böyle bir kayıt varsa, şifre sıfırlama bağlantısı e-posta adresinize gönderildi.'), 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_request.html', title='Şifreyi Sıfırla', form=form)
 
@bp.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    user = User.verify_reset_token(token)
    if user is None:
        flash(gettext('Sıfırlama bağlantısı geçersiz veya süresi dolmuş.'), 'danger')
        return redirect(url_for('auth.reset_request'))
    from app.forms import ResetPasswordForm
    from app.utils import log_action
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password_hash = hashed_password
        db.session.commit()
        log_action(user.id, "ŞİFRE_GÜNCELLENDİ", f"{user.username} şifresini başarıyla sıfırladı.")
        # Mail sending removed
        flash(gettext('Şifreniz başarıyla güncellendi! Artık yeni şifrenizle giriş yapabilirsiniz.'), 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_token.html', title='Yeni Şifre Belirle', form=form)
