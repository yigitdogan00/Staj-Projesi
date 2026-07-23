from flask import Blueprint, render_template, url_for, flash, redirect, request
from flask_login import login_user, current_user, logout_user, login_required
from app.extensions import db, bcrypt
from app.models import User
from app.forms import RegistrationForm, LoginForm
from flask_babel import gettext

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password_hash=hashed_password, first_name=form.first_name.data, last_name=form.last_name.data)
        try:
            db.session.add(user)
            db.session.commit()
            flash(gettext('Hesabınız başarıyla oluşturuldu! Şimdi giriş yapabilirsiniz.'), 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(gettext('Kayıt işlemi sırasında bir hata oluştu. Bu e-posta zaten kayıtlı olabilir veya butona çift tıklamış olabilirsiniz.'), 'danger')
            return render_template('auth/register.html', title='Kayıt Ol', form=form)
    return render_template('auth/register.html', title='Kayıt Ol', form=form)

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
            
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            
            from app.utils import log_action
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
            flash(gettext('Giriş başarısız. Lütfen e-posta ve şifrenizi kontrol edin.'), 'danger')
    return render_template('auth/login.html', title='Giriş Yap', form=form)

@bp.route('/login/google')
def login_google():
    from app.extensions import oauth
    redirect_uri = url_for('auth.authorize_google', _external=True)
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
        username = user_info.get('name') or user_info.get('given_name') or email.split('@')[0]
        given_name = user_info.get('given_name')
        family_name = user_info.get('family_name')
        
        if not given_name or not family_name:
            full_name = user_info.get('name', '').strip()
            if full_name:
                parts = full_name.split()
                if not given_name and len(parts) > 0:
                    given_name = parts[0]
                if not family_name and len(parts) > 1:
                    family_name = ' '.join(parts[1:])
        
        user = User.query.filter_by(email=email).first()
        
        if not user:
            user = User(
                username=username,
                email=email,
                first_name=given_name,
                last_name=family_name
            )
            db.session.add(user)
            db.session.commit()
            log_action(user.id, "KULLANICI_KAYIT", f"{user.username} Google Login ile otomatik kayıt oldu.")
        else:
            updated = False
            if given_name and not user.first_name:
                user.first_name = given_name
                updated = True
            if family_name and not user.last_name:
                user.last_name = family_name
                updated = True
            if updated:
                db.session.commit()

        login_user(user, remember=True)
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
    return redirect(url_for('main.index'))

@bp.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    from app.forms import RequestResetForm
    from app.utils import log_action
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            from datetime import datetime, timedelta
            from app.models import AuditLog
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_requests = AuditLog.query.filter(
                AuditLog.user_id == user.id,
                AuditLog.action == "ŞİFRE_SIFIRLAMA_TALEBİ",
                AuditLog.timestamp >= one_hour_ago
            ).count()

            if recent_requests >= 3 and not user.is_admin:
                flash(gettext('Güvenlik uyarısı: Son 1 saat içinde çok fazla şifre sıfırlama talebinde bulundunuz. Lütfen hesabınızın güvenliği için daha sonra tekrar deneyin.'), 'danger')
                return redirect(url_for('auth.login'))
                
            # Mail sending removed
            log_action(user.id, "ŞİFRE_SIFIRLAMA_TALEBİ", f"{form.email.data} için sıfırlama linki oluşturuldu.")
        else:
            log_action(None, "ŞİFRE_SIFIRLAMA_TALEBİ_BAŞARISIZ", f"{form.email.data} mail adresi sistemde bulunamadı.")
        
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
