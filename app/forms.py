from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from app.models import User
from flask_login import current_user
from flask_babel import lazy_gettext as _l

class UpdateAccountForm(FlaskForm):
    first_name = StringField(_l('Ad'), validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField(_l('Soyad'), validators=[DataRequired(), Length(min=2, max=50)])
    username = StringField(_l('Kullanıcı Adı'), validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField(_l('E-Posta'), validators=[DataRequired(), Email()])
    picture = FileField(_l('Profil Fotoğrafını Güncelle'), validators=[FileAllowed(['jpg', 'png', 'jpeg'])])
    submit = SubmitField(_l('Güncelle'))
    


    def validate_email(self, email):
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('Bu e-posta adresi zaten kullanımda.')

class RegistrationForm(FlaskForm):
    first_name = StringField(_l('Ad'), validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField(_l('Soyad'), validators=[DataRequired(), Length(min=2, max=50)])
    username = StringField(_l('Kullanıcı Adı'), validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField(_l('E-posta'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Şifre'), validators=[DataRequired()])
    confirm_password = PasswordField(_l('Şifreyi Onayla'), validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField(_l('Kayıt Ol'))



    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Bu e-posta adresi zaten kullanımda.')

class LoginForm(FlaskForm):
    email = StringField(_l('E-posta'), validators=[DataRequired(), Email()])
    password = PasswordField(_l('Şifre'), validators=[DataRequired()])
    remember = BooleanField(_l('Beni Hatırla'))
    submit = SubmitField(_l('Giriş Yap'))

class RequestResetForm(FlaskForm):
    email = StringField(_l('E-Posta'), validators=[DataRequired(), Email()])
    submit = SubmitField(_l('Şifre Sıfırlama Bağlantısı Gönder'))

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            from flask_babel import gettext
            raise ValidationError(gettext('Bu e-posta adresiyle kayıtlı bir hesap bulunamadı. Lütfen kayıt olun.'))

class ResetPasswordForm(FlaskForm):
    password = PasswordField(_l('Yeni Şifre'), validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(_l('Yeni Şifreyi Onayla'), validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField(_l('Şifreyi Güncelle'))

class RoomForm(FlaskForm):
    name = StringField(_l('Oda İsmi'), validators=[DataRequired(), Length(min=2, max=50)])
    english_name = StringField(_l('İngilizce Oda İsmi'), validators=[Length(max=50)])
    capacity = StringField(_l('Kişi Sayısı (Kapasite)'), validators=[DataRequired()])
    description = StringField(_l('Özellikler / Açıklama'), validators=[Length(max=200)])
    submit = SubmitField(_l('Oda Ekle'))

class EditRoomForm(FlaskForm):
    name = StringField(_l('Oda İsmi'), validators=[DataRequired(), Length(min=2, max=50)])
    english_name = StringField(_l('İngilizce Oda İsmi'), validators=[Length(max=50)])
    capacity = StringField(_l('Kişi Sayısı (Kapasite)'), validators=[DataRequired()])
    description = StringField(_l('Özellikler / Açıklama'), validators=[Length(max=200)])
    submit = SubmitField(_l('Değişiklikleri Kaydet'))
