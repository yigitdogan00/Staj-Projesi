from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from app.models import User
from flask_login import current_user

class UpdateAccountForm(FlaskForm):
    username = StringField('Kullanıcı Adı', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('E-Posta', validators=[DataRequired(), Email()])
    picture = FileField('Profil Fotoğrafını Güncelle', validators=[FileAllowed(['jpg', 'png', 'jpeg'])])
    submit = SubmitField('Güncelle')
    


    def validate_email(self, email):
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('Bu e-posta adresi zaten kullanımda.')

class RegistrationForm(FlaskForm):
    username = StringField('Kullanıcı Adı', validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('E-posta', validators=[DataRequired(), Email()])
    password = PasswordField('Şifre', validators=[DataRequired()])
    confirm_password = PasswordField('Şifreyi Onayla', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Kayıt Ol')



    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Bu e-posta adresi zaten kullanımda.')

class LoginForm(FlaskForm):
    email = StringField('E-posta', validators=[DataRequired(), Email()])
    password = PasswordField('Şifre', validators=[DataRequired()])
    remember = BooleanField('Beni Hatırla')
    submit = SubmitField('Giriş Yap')

class RequestResetForm(FlaskForm):
    email = StringField('E-Posta', validators=[DataRequired(), Email()])
    submit = SubmitField('Şifre Sıfırlama Bağlantısı Gönder')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError('Bu e-posta adresiyle kayıtlı bir hesap bulunamadı. Lütfen kayıt olun.')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Yeni Şifre', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Yeni Şifreyi Onayla', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Şifreyi Güncelle')

class RoomForm(FlaskForm):
    name = StringField('Oda İsmi', validators=[DataRequired(), Length(min=2, max=50)])
    capacity = StringField('Kişi Sayısı (Kapasite)', validators=[DataRequired()])
    description = StringField('Özellikler / Açıklama', validators=[Length(max=200)])
    submit = SubmitField('Oda Ekle')

