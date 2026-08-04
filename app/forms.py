from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from app.models import User
from flask_login import current_user
from flask_babel import lazy_gettext as _

class UpdateAccountForm(FlaskForm):
    first_name = StringField(_('Ad'), validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField(_('Soyad'), validators=[DataRequired(), Length(min=2, max=50)])
    username = StringField(_('Kullanıcı Adı'), validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField(_('E-Posta'), validators=[DataRequired(), Email()])
    picture = FileField(_('Profil Fotoğrafını Güncelle'), validators=[FileAllowed(['jpg', 'png', 'jpeg'])])
    submit = SubmitField(_('Güncelle'))
    

    def validate_email(self, email):
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('Bu e-posta adresi zaten kullanımda.')

class RegistrationForm(FlaskForm):
    first_name = StringField(_('Ad'), validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField(_('Soyad'), validators=[DataRequired(), Length(min=2, max=50)])
    username = StringField(_('Kullanıcı Adı'), validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField(_('E-posta'), validators=[DataRequired(), Email()])
    password = PasswordField(_('Şifre'), validators=[DataRequired()])
    confirm_password = PasswordField(_('Şifreyi Onayla'), validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField(_('Kayıt Ol'))



    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Bu e-posta adresi zaten kullanımda.')

class LoginForm(FlaskForm):
    email = StringField(_('E-posta'), validators=[DataRequired(), Email()])
    password = PasswordField(_('Şifre'), validators=[DataRequired()])
    remember = BooleanField(_('Beni Hatırla'))
    submit = SubmitField(_('Giriş Yap'))

class RequestResetForm(FlaskForm):
    email = StringField(_('E-Posta'), validators=[DataRequired(), Email()])
    submit = SubmitField(_('Şifre Sıfırlama Bağlantısı Gönder'))

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            from flask_babel import gettext
            raise ValidationError(gettext('Bu e-posta adresiyle kayıtlı bir hesap bulunamadı. Lütfen kayıt olun.'))

class ResetPasswordForm(FlaskForm):
    password = PasswordField(_('Yeni Şifre'), validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(_('Yeni Şifreyi Onayla'), validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField(_('Şifreyi Güncelle'))

class RoomForm(FlaskForm):
    name = StringField(_('Oda İsmi'), validators=[DataRequired(), Length(min=2, max=50)])
    english_name = StringField(_('İngilizce Oda İsmi'), validators=[Length(max=50)])
    capacity = StringField(_('Kişi Sayısı (Kapasite)'), validators=[DataRequired()])
    description = StringField(_('Özellikler / Açıklama'), validators=[Length(max=200)])
    english_description = StringField(_('İngilizce Özellikler / Açıklama'), validators=[Length(max=200)])
    submit = SubmitField(_('Oda Ekle'))

class EditRoomForm(FlaskForm):
    name = StringField(_('Oda İsmi'), validators=[DataRequired(), Length(min=2, max=50)])
    english_name = StringField(_('İngilizce Oda İsmi'), validators=[Length(max=50)])
    capacity = StringField(_('Kişi Sayısı (Kapasite)'), validators=[DataRequired()])
    description = StringField(_('Özellikler / Açıklama'), validators=[Length(max=200)])
    english_description = StringField(_('İngilizce Özellikler / Açıklama'), validators=[Length(max=200)])
    submit = SubmitField(_('Değişiklikleri Kaydet'))
