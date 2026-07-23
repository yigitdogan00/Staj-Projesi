import os
import secrets
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import Room, Reservation, User, AuditLog, Notification, Document
from app.extensions import db
from datetime import datetime, date
from app.utils import admin_required, log_action
from app.forms import UpdateAccountForm

bp = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in ['tr', 'en']:
        session['lang'] = lang
    return redirect(request.referrer or url_for('main.dashboard'))

def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(current_app.root_path, 'static/profile_pics', picture_fn)
    
    # Normally we would resize here with Pillow, but for simplicity we just save
    form_picture.save(picture_path)
    return picture_fn

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.profile_image = picture_file
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        log_action(current_user.id, "PROFİL_GÜNCELLEME", f"{current_user.username} profilini güncelledi.")
        flash(gettext('Hesabınız başarıyla güncellendi!'), 'success')
        return redirect(url_for('main.profile'))
    elif request.method == 'GET':
        from app.utils import parse_name_from_email
        fn, ln = parse_name_from_email(current_user.email)
        if fn and ln:
            if not current_user.first_name or not current_user.last_name or 'dogan' in current_user.first_name.lower() or current_user.first_name.lower() == 'yigitdogan':
                current_user.first_name = fn
                current_user.last_name = ln
                db.session.commit()

        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.username.data = current_user.username
        form.email.data = current_user.email
    
    image_file = url_for('static', filename='profile_pics/' + current_user.profile_image) if current_user.profile_image != 'default.jpg' else None
    return render_template('profile.html', title='Profilim', form=form, image_file=image_file)

from flask_babel import gettext

@bp.app_context_processor
def inject_lang():
    lang = session.get('lang', 'tr')
    
    unread_notifications = []
    active_meeting = None
    upcoming_accepted_meetings = []
    starting_soon_meeting = None
    
    if current_user.is_authenticated:
        from app.models import get_turkey_time
        now = get_turkey_time()
        today_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M')

        raw_notifications = Notification.query.filter_by(user_id=current_user.id, status='pending', is_read=False).order_by(Notification.created_at.desc()).all()
        
        db_changed = False
        for notif in raw_notifications:
            is_old_or_deleted = False
            
            # Eğer bu bir davetse, geçmişte mi diye veya silinmiş mi diye kontrol et
            if notif.type == 'invitation':
                if notif.reservation_id:
                    if notif.reservation:
                        res = notif.reservation
                        if res.date < today_str or (res.date == today_str and res.end_time <= time_str):
                            is_old_or_deleted = True
                    else:
                        # Rezervasyon silinmiş ama bildirimi kalmış
                        is_old_or_deleted = True
            
            if is_old_or_deleted:
                notif.type = 'info'
                notif.message = "Geçmiş (veya iptal edilmiş) bir toplantı davetiniz vardı."
                db_changed = True
                
            unread_notifications.append(notif)
            
        if db_changed:
            from app.extensions import db
            db.session.commit()
        
        # Check for active meeting
        
        # Find if user is in any meeting right now (as creator or attendee)
        # We need to check all user's reservations and invited_reservations for today
        all_today_res = Reservation.query.filter_by(date=today_str).all()
        for res in all_today_res:
            if res.user_id == current_user.id or current_user in res.attendees:
                if res.start_time <= time_str < res.end_time:
                    if current_user in res.active_users:
                        active_meeting = res
                    
                # Check for meeting starting within 1 minute
                from datetime import timedelta
                start_dt = datetime.strptime(f"{res.date} {res.start_time}", "%Y-%m-%d %H:%M")
                diff = start_dt - now.replace(tzinfo=None)
                if timedelta(seconds=0) < diff <= timedelta(minutes=1):
                    starting_soon_meeting = res
                    
        # Find upcoming accepted meetings
        accepted_notifs = Notification.query.filter_by(user_id=current_user.id, type='invitation', status='accepted').all()
        for notif in accepted_notifs:
            if notif.reservation and notif.reservation.date >= today_str:
                if notif.reservation not in upcoming_accepted_meetings:
                    upcoming_accepted_meetings.append(notif.reservation)
        upcoming_accepted_meetings.sort(key=lambda x: (x.date, x.start_time))
        
        # Prepare list of today's meetings for frontend timers
        today_meetings_list = []
        for res in all_today_res:
            if res.user_id == current_user.id or current_user in res.attendees:
                today_meetings_list.append({
                    'id': res.id,
                    'room_name': res.room.name,
                    'start_time': res.start_time,
                    'date': res.date
                })
                    
    def translate_log_details(text):
        if lang == 'tr':
            return text
        import re
        m = re.match(r"(.+) sisteme giriş yaptı\.", text)
        if m: return f"{m.group(1)} logged into the system."
        m = re.match(r"(.+) Google Login ile sisteme giriş yaptı\.", text)
        if m: return f"{m.group(1)} logged in via Google Login."
        m = re.match(r"(.+) Google Login ile hesap oluşturdu\.", text)
        if m: return f"{m.group(1)} created an account via Google Login."
        m = re.match(r"(.+) odası güncellendi\.", text)
        if m: return f"Room '{m.group(1)}' updated."
        m = re.match(r"(.+) odası eklendi\.", text)
        if m: return f"Room '{m.group(1)}' added."
        m = re.match(r"(.+) \(ID: (\d+)\) odası silindi\.", text)
        if m: return f"Room '{m.group(1)}' (ID: {m.group(2)}) deleted."
        m = re.match(r"(.+) \(ID: (\d+)\) kullanıcısı silindi\.", text)
        if m: return f"User '{m.group(1)}' (ID: {m.group(2)}) deleted."
        m = re.match(r"(.+) profilini güncelledi\.", text)
        if m: return f"{m.group(1)} updated their profile."
        m = re.match(r"(.+) odası için (.+) (.+)-(.+) rezervasyonu yapıldı\.( Davetliler: (.+))?", text)
        if m: 
            base = f"Reservation made for room '{m.group(1)}' on {m.group(2)} {m.group(3)}-{m.group(4)}."
            if m.group(6): base += f" Invitees: {m.group(6)}"
            return base
        m = re.match(r"Rezervasyon ID (\d+) \((.+), (.+) (.+)-(.+)\) iptal edildi\.", text)
        if m: return f"Reservation ID {m.group(1)} ({m.group(2)}, {m.group(3)} {m.group(4)}-{m.group(5)}) cancelled."
        m = re.match(r"(.+) tarihindeki (.+) log kalıcı olarak silindi\.", text)
        if m: return f"{m.group(2)} logs from {m.group(1)} were permanently deleted."
        m = re.match(r"Admin tarafından (.+) adet log manuel olarak silindi\.", text)
        if m: return f"{m.group(1)} logs were manually deleted by Admin."
        if text == "Admin panelinden son 50 log kaydı gizlendi.":
            return "Last 50 log records were hidden from admin panel."
        if text == "Sistem logları temizlendi (Son 50 kayıt).":
            return "System logs cleared (Last 50 records)."
        m = re.match(r"(\d+) adet eski rezervasyon kalıcı olarak silindi\.", text)
        if m: return f"{m.group(1)} old reservations permanently deleted."
        m = re.match(r"(.+) için sıfırlama linki oluşturuldu\.", text)
        if m: return f"Reset link created for {m.group(1)}."
        m = re.match(r"(.+) mail adresi sistemde bulunamadı\.", text)
        if m: return f"Email address {m.group(1)} not found in the system."
        m = re.match(r"(.+) şifresini başarıyla sıfırladı\.", text)
        if m: return f"{m.group(1)} successfully reset their password."
        m = re.match(r"Kullanıcı (.+) admin yetkisi (verildi|alındı)\.", text)
        if m: 
            return f"Admin privileges {'granted to' if m.group(2) == 'verildi' else 'revoked from'} user {m.group(1)}."
        return text

    def translate_log_action(action):
        if lang == 'tr':
            return action
        translations = {
            "SİSTEME_GİRİŞ": "LOGIN",
            "LOGIN": "LOGIN",
            "ODA_GÜNCELLENDİ": "ROOM_UPDATED",
            "ODA_EKLENDİ": "ROOM_ADDED",
            "ODA_SİLİNDİ": "ROOM_DELETED",
            "KULLANICI_SİLİNDİ": "USER_DELETED",
            "PROFİL_GÜNCELLEME": "PROFILE_UPDATED",
            "REZERVASYON_OLUŞTURULDU": "RESERVATION_CREATED",
            "REZERVASYON_İPTALİ": "RESERVATION_CANCELLED",
            "SİSTEM": "SYSTEM",
            "ŞİFRE_SIFIRLAMA_TALEBİ": "PASSWORD_RESET_REQUEST",
            "ŞİFRE_SIFIRLAMA_TALEBİ_BAŞARISIZ": "PASSWORD_RESET_FAILED",
            "ŞİFRE_GÜNCELLENDİ": "PASSWORD_UPDATED",
            "ŞİFRE_SIFIRLANDI": "PASSWORD_RESET",
            "YENİ_HESAP": "NEW_ACCOUNT",
            "ADMIN_YAPILDI": "ADMIN_GRANTED",
            "ADMINLIK_ALINDI": "ADMIN_REVOKED"
        }
        return translations.get(action, action)

    import re
    def translate_notification(msg):
        if msg == "Geçmiş (veya iptal edilmiş) bir toplantı davetiniz vardı.":
            return gettext("Geçmiş (veya iptal edilmiş) bir toplantı davetiniz vardı.")
        match = re.match(r"'(.*?)' odasındaki toplantınız (\d+) dakika içinde başlıyor\. Lütfen odaya geçin\.", msg)
        if match:
            return gettext("'%(room)s' odasındaki toplantınız %(mins)s dakika içinde başlıyor. Lütfen odaya geçin.", room=match.group(1), mins=match.group(2))
        match = re.match(r"(.*?) sizi (.*?) tarihinde (.*?)-(.*?) saatleri arasında (.*?) odasındaki toplantıya davet etti\.", msg)
        if match:
            return gettext("%(user)s sizi %(date)s tarihinde %(start)s-%(end)s saatleri arasında %(room)s odasındaki toplantıya davet etti.", user=match.group(1), date=match.group(2), start=match.group(3), end=match.group(4), room=match.group(5))
        match = re.match(r"(.*?), (.*?) tarihindeki (.*?)-(.*?) toplantı davetini reddetti\.", msg)
        if match:
            return gettext("%(user)s, %(date)s tarihindeki %(start)s-%(end)s toplantı davetini reddetti.", user=match.group(1), date=match.group(2), start=match.group(3), end=match.group(4))
        match = re.match(r"'(.*?)' odasındaki toplantınız için zaman doldu\.", msg)
        if match:
            return gettext("'%(room)s' odasındaki toplantınız için zaman doldu.", room=match.group(1))
        match = re.match(r"'(.*?)' odasındaki toplantınız başlamak üzere\.", msg)
        if match:
            return gettext("'%(room)s' odasındaki toplantınız başlamak üzere.", room=match.group(1))
        match = re.match(r"Yönetici tarafından (.*?) tarihindeki (.*?)-(.*?) saatleri arasındaki (.*?) odası rezervasyonunuz iptal edildi\.", msg)
        if match:
            return gettext("Yönetici tarafından %(date)s tarihindeki %(start)s-%(end)s saatleri arasındaki %(room)s odası rezervasyonunuz iptal edildi.", date=match.group(1), start=match.group(2), end=match.group(3), room=match.group(4))
        return gettext(msg)

    def format_tr_datetime(dt):
        if not dt:
            return ""
        if lang == 'en':
            return dt.strftime('%B %d, %Y')
        aylar = {
            1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
            7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
        }
        return f"{dt.day} {aylar[dt.month]} {dt.year}"

    return dict(trans=gettext, translate_notification=translate_notification, current_lang=lang, unread_notifications=unread_notifications, active_meeting=active_meeting, upcoming_accepted_meetings=upcoming_accepted_meetings, starting_soon_meeting=starting_soon_meeting, today_meetings_list=today_meetings_list if current_user.is_authenticated else [], translate_log_details=translate_log_details, translate_log_action=translate_log_action, format_tr_datetime=format_tr_datetime)

@bp.route('/lang/<lang_code>')
def change_language(lang_code):
    if lang_code in ['tr', 'en']:
        session['lang'] = lang_code
    return redirect(request.referrer or url_for('main.index'))

import re
@bp.route('/api/ai/command', methods=['POST'])
def ai_command():
    from app.models import get_turkey_time, Reservation, Room
    from app.extensions import db
    import random
    lang = session.get('lang', 'tr')
    def msg(tr, en):
        return en if lang == 'en' else tr
        
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'reload': False, 'message': msg('Bu özelliği kullanabilmek için lütfen önce giriş yapın.', 'Please log in to use this feature.')})
        
    data = request.get_json()
    command_text = data.get('command', '').lower()
    
    def normalize(t):
        return t.lower().replace('ı','i').replace('ş','s').replace('ç','c').replace('ğ','g').replace('ö','o').replace('ü','u')
        
    norm_cmd = normalize(command_text)
    
    if session.get('awaiting_random_booking'):
        state = session.pop('awaiting_random_booking', None)
        if norm_cmd in ["evet", "yes", "olur", "tamam", "onayla"]:
            now = get_turkey_time()
            today_str = now.strftime('%Y-%m-%d')
            current_mins = now.hour * 60 + now.minute
            
            possible_starts = [f"{h:02d}:00" for h in range(9, 18)]
            random.shuffle(possible_starts)
            
            if isinstance(state, dict):
                date_str = state.get('date', today_str)
                room_id = state.get('room_id')
                rooms = [Room.query.get(room_id)] if room_id else Room.query.all()
                min_mins = current_mins if date_str == today_str else 0
            else:
                date_str = today_str
                rooms = Room.query.all()
                random.shuffle(rooms)
                min_mins = current_mins
            
            booked = False
            for r in rooms:
                if not r: continue
                existing = Reservation.query.filter_by(room_id=r.id, date=date_str).all()
                for p_start in possible_starts:
                    req_start = int(p_start.split(':')[0]) * 60
                    req_end = req_start + 60
                    if req_start <= min_mins:
                        continue
                    conflict = False
                    for res in existing:
                        h, m = map(int, res.start_time.split(':'))
                        res_s = h * 60 + m
                        h, m = map(int, res.end_time.split(':'))
                        res_e = h * 60 + m
                        if not (req_end <= res_s or req_start >= res_e):
                            conflict = True
                            break
                    if not conflict:
                        try:
                            end_time_str = f"{req_end // 60:02d}:00"
                            new_res = Reservation(
                                user_id=current_user.id,
                                room_id=r.id,
                                date=date_str,
                                start_time=p_start,
                                end_time=end_time_str
                            )
                            db.session.add(new_res)
                            db.session.commit()
                            booked = True
                            msg_tr = f"Harika! Rastgele seçilen <b>{r.name}</b> odası <b>{date_str}</b> tarihinde <b>{p_start}-{end_time_str}</b> arası sizin için rezerve edildi.<br><br>📌 <b>Hatırlatmalar:</b><br>• Gerekli belgeleri yüklemeyi unutmayın.<br>• QR ile giriş yapmayı unutmayın."
                            msg_en = f"Great! The randomly selected <b>{r.name}</b> room has been booked for you on <b>{date_str}</b> between <b>{p_start}-{end_time_str}</b>.<br><br>📌 <b>Reminders:</b><br>• Do not forget to upload the necessary documents.<br>• Do not forget to log in with QR."
                            return jsonify({'success': True, 'reload': False, 'message': msg(msg_tr, msg_en)})
                        except Exception as e:
                            db.session.rollback()
                        break
                if booked:
                    break
            if not booked:
                return jsonify({'success': False, 'message': msg(f'Maalesef {date_str} için boş bir oda/saat bulamadım.', f'Unfortunately, I could not find an available room/time for {date_str}.')})
        elif norm_cmd in ["hayır", "hayir", "no", "istemiyorum"]:
            session.pop('awaiting_random_booking', None)
            return jsonify({'success': True, 'reload': False, 'message': msg('Tamamdır, lütfen saat seçimi yapınız.', 'Alright, please select a time.')})
        else:
            session.pop('awaiting_random_booking', None)
            
    if any(k in norm_cmd for k in ["bana bir saati rezerve et", "bana bir saat rezerve et", "rastgele rezervasyon yap", "bana yer ayirt", "bana yer ayırt"]):
        session['awaiting_random_booking'] = True
        return jsonify({'success': True, 'reload': False, 'message': msg('Sizin adınıza rastgele bir saat seçmemi ister misiniz? (Evet/Hayır)', 'Would you like me to pick a random time for you? (Yes/No)')})

    # 0. Check conversational phrases first
    if norm_cmd in ["merhaba", "selam", "merhabalar", "hey", "hello", "hi", "günaydın", "gunaydin", "good morning"]:
        now = get_turkey_time()
        today_str = now.strftime('%Y-%m-%d')
        
        from app.models import Notification
        notifs = Notification.query.filter_by(user_id=current_user.id, type='invitation', status='pending').all()
        today_invites = [n for n in notifs if n.reservation and n.reservation.date == today_str]
        
        invitations_text_tr = ""
        invitations_text_en = ""
        if today_invites:
            for n in today_invites:
                inviter = n.reservation.user.username
                room = n.reservation.room.name
                time = n.reservation.start_time
                invitations_text_tr += f"<br><br>🔔 Bugün {inviter} kişisinden saat {time}'da {room} odası için toplantı davetin var, hatırlatmak istedim."
                invitations_text_en += f"<br><br>🔔 You have a meeting invitation from {inviter} today at {time} for the {room} room, just wanted to remind you."
                
        if norm_cmd in ["günaydın", "gunaydin", "good morning"]:
            base_msg_tr = f'Günaydın {current_user.username}! Harika bir gün olması dileğiyle, sana nasıl yardımcı olabilirim?'
            base_msg_en = f'Good morning {current_user.username}! Wishing you a great day, how can I help you?'
        else:
            base_msg_tr = f'Merhaba {current_user.username}, nasıl yardımcı olabilirim, bugün nasılsın?'
            base_msg_en = f'Hello {current_user.username}, how can I help you, how are you today?'

        return jsonify({'success': True, 'reload': False, 'message': msg(base_msg_tr + invitations_text_tr, base_msg_en + invitations_text_en)})
    elif any(k in norm_cmd for k in ["iyiyim", "iyi sen", "iyiyim sen", "iyi, sen", "fine", "good", "iyiyim sen nasılsın", "iyiyim sen nasilsin"]):
        return jsonify({'success': True, 'reload': False, 'message': msg(
            'Ben harika hissediyorum, tıkır tıkır çalışıyorum! Sorduğun için çok teşekkür ederim ❤️<br><br>Hangi işlemi yapmak istersin?<br><br>1 - Oda rezervasyonu yap<br>2 - Oda iptal et<br>3 - Oda durumunu sorgula<br>4 - QR ile giriş bilgisi<br>5 - Sohbeti kapat<br><br>Lütfen seçim yapınız (1, 2, 3, 4 veya 5 yazın).',
            'I am doing perfectly and running smoothly! Thank you so much for asking ❤️<br><br>What would you like to do?<br><br>1 - Book a room<br>2 - Cancel a reservation<br>3 - Check room availability<br>4 - QR login info<br>5 - Close chat<br><br>Please select an option (type 1, 2, 3, 4, or 5).'
        )})
    elif "nasılsın" in norm_cmd or "nasilsin" in norm_cmd or "naber" in norm_cmd or "how are you" in norm_cmd:
        return jsonify({'success': True, 'reload': False, 'message': msg(
            'Harikayım! Sana nasıl yardımcı olabilirim?<br><br>1 - Oda rezervasyonu yap<br>2 - Oda iptal et<br>3 - Oda durumunu sorgula<br>4 - QR ile giriş bilgisi<br>5 - Sohbeti kapat<br><br>Lütfen seçim yapınız (1, 2, 3, 4 veya 5 yazın).',
            'I am doing great! How can I help you?<br><br>1 - Book a room<br>2 - Cancel a reservation<br>3 - Check room availability<br>4 - QR login info<br>5 - Close chat<br><br>Please select an option (type 1, 2, 3, 4, or 5).'
        )})
    elif norm_cmd in ["teşekkürler", "tesekkurler", "teşekkür ederim", "tesekkur ederim", "sağol", "sagol", "thanks", "thank you"]:
        return jsonify({'success': True, 'reload': False, 'message': msg(
            'Rica ederim! Sana nasıl yardımcı olabilirim?<br><br>1 - Oda rezervasyonu yap<br>2 - Oda iptal et<br>3 - Oda durumunu sorgula<br>4 - QR ile giriş bilgisi<br>5 - Sohbeti kapat<br><br>Lütfen seçim yapınız (1, 2, 3, 4 veya 5 yazın).',
            'You\'re welcome! How can I help you?<br><br>1 - Book a room<br>2 - Cancel a reservation<br>3 - Check room availability<br>4 - QR login info<br>5 - Close chat<br><br>Please select an option (type 1, 2, 3, 4, or 5).'
        )})
    elif norm_cmd in ["tamam", "ok", "okay", "tamamdır", "tamamdir", "iyi günler", "iyi gunler", "iyi çalışmalar", "iyi calismalar"]:
        return jsonify({'success': True, 'reload': False, 'message': msg(
            'Tamamdır! Sana nasıl yardımcı olabilirim?<br><br>1 - Oda rezervasyonu yap<br>2 - Oda iptal et<br>3 - Oda durumunu sorgula<br>4 - QR ile giriş bilgisi<br>5 - Sohbeti kapat<br><br>Lütfen seçim yapınız (1, 2, 3, 4 veya 5 yazın).',
            'Alright! How can I help you?<br><br>1 - Book a room<br>2 - Cancel a reservation<br>3 - Check room availability<br>4 - QR login info<br>5 - Close chat<br><br>Please select an option (type 1, 2, 3, 4, or 5).'
        )})
    elif norm_cmd == "1":
        return jsonify({'success': True, 'reload': False, 'message': msg('Oda rezervasyonu yapmak için bana bir tarih, saat ve oda adı söyleyebilirsin. Örn: "İnovasyon odasını 21.07.2026 saat 10:00-11:00 arası ayır"', 'To book a room, you can tell me the date, time, and room name. e.g., "Book Synergy room on 21.07.2026 from 10:00 to 11:00"')})
    elif norm_cmd == "2":
        return jsonify({'success': True, 'reload': False, 'message': msg('Rezervasyon iptal etmek için takvim veya genel bakış sayfasına gidip kendi dolu (kırmızı) randevunuza tıklayarak iptal işlemini gerçekleştirebilirsiniz.', 'To cancel a reservation, you can click on your booked slot (red) on the calendar or overview page.')})
    elif norm_cmd == "3":
        return jsonify({'success': True, 'reload': False, 'message': msg('Oda durumlarını sorgulamak için yukarıdaki veya yandaki menüden "Genel Bakış" (Takvim) sekmesine tıklayarak tüm boş odaları görebilirsiniz.', 'To check room availability, you can use the "Overview" tab from the menu above to see all available rooms.')})
    elif norm_cmd == "4":
        return jsonify({'success': True, 'reload': False, 'message': msg('Giriş için elde edilen QR\'ı kapıya okutarak giriş yapınız.', 'Please scan the obtained QR code at the door to enter.')})
    elif any(k in norm_cmd for k in ["qr nerede", "qr kod nerede", "karekod nerede", "qr'i nereden", "qr ı nereden", "qr'ı nereden", "qr i nereden", "qr a nasil", "qr'a nasil", "qr'a nasıl", "qr kodu nerede", "qra nasil", "qra nasıl"]):
        return jsonify({'success': True, 'reload': False, 'message': msg(
            'Giriş için kullanacağınız QR kodunu, rezervasyon işleminizi tamamladıktan sonra "Genel Bakış" (Takvim) sayfasındaki kendi randevunuzun detaylarına tıklayarak görüntüleyebilirsiniz.',
            'You can view your login QR code by clicking on your reservation details on the "Overview" (Calendar) page after completing your booking.'
        )})
    elif norm_cmd == "5" or "kendini kapat" in norm_cmd or "close yourself" in norm_cmd or "kapat" in norm_cmd:
        return jsonify({'success': True, 'reload': False, 'close_chat': True, 'message': msg('Görüşmek üzere, sohbeti kapatıyorum!', 'See you later, closing chat!')})
    
    # 1. Ajanda kontrolü
    if any(k in norm_cmd for k in ["toplantim var mi", "toplantim varmi", "ajandam", "toplantilarim"]):
        from app.models import Notification
        now = get_turkey_time()
        today_str = now.strftime('%Y-%m-%d')
        my_res = Reservation.query.filter_by(user_id=current_user.id, date=today_str).all()
        
        # Add invitations (both pending and accepted)
        invitations = Notification.query.filter_by(user_id=current_user.id, type='invitation').all()
        for notif in invitations:
            if getattr(notif, 'reservation', None) and notif.reservation.date == today_str and notif.status in ['pending', 'accepted']:
                if notif.reservation not in my_res:
                    my_res.append(notif.reservation)
                    
        my_res.sort(key=lambda x: x.start_time)
        
        if my_res:
            res_texts = []
            for r in my_res:
                # Check if it is a pending invitation
                pending_note_tr = ""
                pending_note_en = ""
                if r.user_id != current_user.id:
                    # check status
                    notif = Notification.query.filter_by(user_id=current_user.id, reservation_id=r.id, type='invitation').first()
                    if notif and getattr(notif, 'status', '') == 'pending':
                        pending_note_tr = " <span style=\"color: #fbbf24; font-weight: bold;\">[BEKLEYEN DAVET]</span>"
                        pending_note_en = " <span style=\"color: #fbbf24; font-weight: bold;\">[PENDING INVITATION]</span>"
                        
                res_texts_tr = f"Saat <b>{r.start_time} - {r.end_time}</b> arasında <b>{r.room.name}</b> odasında{pending_note_tr}"
                res_texts_en = f"From <b>{r.start_time} - {r.end_time}</b> in <b>{r.room.name}</b>{pending_note_en}"
                res_texts.append((res_texts_tr, res_texts_en))
                
            msg_tr = "Bugün için ajandanızda şu toplantılar bulunuyor:<br><br>" + "<br>".join([t[0] for t in res_texts])
            msg_en = "You have the following meetings on your agenda today:<br><br>" + "<br>".join([t[1] for t in res_texts])
            return jsonify({'success': True, 'reload': False, 'message': msg(msg_tr, msg_en)})
        else:
            return jsonify({'success': True, 'reload': False, 'message': msg("Bugün için planlanmış herhangi bir toplantınız bulunmuyor. Harika bir gün geçirin!", "You don't have any meetings scheduled for today. Have a great day!")})
            
    # 2. İptal etme özelliği
    if any(k in norm_cmd for k in ["iptal et", "toplantimi iptal", "rezervasyonu iptal"]):
        now = get_turkey_time()
        today_str = now.strftime('%Y-%m-%d')
        # Find active future/current reservations
        my_res = Reservation.query.filter(
            Reservation.user_id == current_user.id,
            Reservation.date >= today_str
        ).order_by(Reservation.date, Reservation.start_time).all()
        
        # Filter out past ones if today
        valid_res = []
        current_mins = now.hour * 60 + now.minute
        for r in my_res:
            if r.date == today_str:
                h, m = map(int, r.start_time.split(':'))
                if h * 60 + m >= current_mins:
                    valid_res.append(r)
            else:
                valid_res.append(r)
                
        if len(valid_res) == 0:
            return jsonify({'success': True, 'reload': False, 'message': msg("İptal edilebilecek aktif bir rezervasyonunuz bulunmuyor.", "You don't have any active reservations that can be canceled.")})
        elif len(valid_res) == 1:
            r = valid_res[0]
            r_date = r.date
            r_start_time = r.start_time
            r_room_name = r.room.name
            db.session.delete(r)
            db.session.commit()
            return jsonify({'success': True, 'reload': True, 'message': msg(f"<b>{r_date}</b> tarihindeki <b>{r_start_time}</b> saatli <b>{r_room_name}</b> odası rezervasyonunuz başarıyla iptal edildi.", f"Your reservation for <b>{r_room_name}</b> on <b>{r_date}</b> at <b>{r_start_time}</b> has been successfully canceled.")})
        else:
            # Too many to automatically delete
            res_texts = []
            for r in valid_res:
                res_texts.append(f"{r.date} | {r.start_time}-{r.end_time} | {r.room.name}")
            msg_tr = "Birden fazla aktif rezervasyonunuz var. Lütfen takvim üzerinden iptal etmek istediğinizi seçin:<br><br>" + "<br>".join(res_texts)
            return jsonify({'success': True, 'reload': False, 'message': msg(msg_tr, msg_tr)})
            
    # 2.5 Davetleri kabul veya reddetme
    if any(k in norm_cmd for k in ["kabul", "onayla", "accept", "daveti kabul"]):
        from app.models import Notification
        pending_notifs = Notification.query.filter_by(user_id=current_user.id, type='invitation', status='pending').all()
        if not pending_notifs:
            return jsonify({'success': True, 'reload': False, 'message': msg("Şu anda bekleyen bir davetiniz bulunmuyor.", "You don't have any pending invitations right now.")})
        elif len(pending_notifs) == 1:
            n = pending_notifs[0]
            n.status = 'accepted'
            n.is_read = True
            db.session.commit()
            return jsonify({'success': True, 'reload': True, 'message': msg(f"Daveti başarıyla kabul ettiniz. Toplantı ajandanıza eklendi.", f"You have successfully accepted the invitation. It has been added to your agenda.")})
        else:
            return jsonify({'success': True, 'reload': False, 'message': msg("Birden fazla bekleyen davetiniz var. Lütfen bildirimler menüsünden ilgili daveti onaylayın.", "You have multiple pending invitations. Please accept the specific one from your notifications menu.")})

    if any(k in norm_cmd for k in ["reddet", "red et", "reject", "decline", "daveti red"]):
        from app.models import Notification
        pending_notifs = Notification.query.filter_by(user_id=current_user.id, type='invitation', status='pending').all()
        if not pending_notifs:
            return jsonify({'success': True, 'reload': False, 'message': msg("Şu anda bekleyen bir davetiniz bulunmuyor.", "You don't have any pending invitations right now.")})
        elif len(pending_notifs) == 1:
            n = pending_notifs[0]
            n.status = 'rejected'
            n.is_read = True
            if n.reservation and current_user in n.reservation.attendees:
                n.reservation.attendees.remove(current_user)
            db.session.commit()
            return jsonify({'success': True, 'reload': True, 'message': msg(f"Daveti reddettiniz. Toplantı ajandanızdan çıkarıldı.", f"You have rejected the invitation. It has been removed from your agenda.")})
        else:
            return jsonify({'success': True, 'reload': False, 'message': msg("Birden fazla bekleyen davetiniz var. Lütfen bildirimler menüsünden ilgili daveti reddedin.", "You have multiple pending invitations. Please reject the specific one from your notifications menu.")})
            
    # 3. Anlık Boş Oda Taraması
    if any(k in norm_cmd for k in ["bos oda", "uygun oda", "su an bos", "hangi oda", "bos yer"]):
        now = get_turkey_time()
        today_str = now.strftime('%Y-%m-%d')
        start_h = now.hour
        
        if start_h >= 23:
             return jsonify({'success': True, 'reload': False, 'message': msg("Şu an saat çok geç, odalar boş.", "It's too late right now, rooms are empty.")})
             
        end_h = start_h + 1
        start_time_str = f"{str(start_h).zfill(2)}:00"
        end_time_str = f"{str(end_h).zfill(2)}:00"
        
        active_res = Reservation.query.filter_by(date=today_str).all()
        occupied_room_ids = []
        for r in active_res:
            if r.start_time == start_time_str or (r.start_time < end_time_str and r.end_time > start_time_str):
                occupied_room_ids.append(r.room_id)
                
        all_rooms = Room.query.all()
        empty_rooms = [rm.name for rm in all_rooms if rm.id not in occupied_room_ids]
        
        if empty_rooms:
            rooms_txt = ", ".join(empty_rooms)
            return jsonify({'success': True, 'reload': False, 'message': msg(f"Şu an ({start_time_str} - {end_time_str}) saatleri arasında şu odalar <b>MÜSAİT</b>:<br><br>{rooms_txt}<br><br>Hemen 'bugün {empty_rooms[0]} saat {start_time_str}' diyerek ayırabilirsiniz.", f"Currently ({start_time_str} - {end_time_str}) the following rooms are <b>AVAILABLE</b>:<br><br>{rooms_txt}")})
        else:
            return jsonify({'success': True, 'reload': False, 'message': msg(f"Şu an ({start_time_str} - {end_time_str}) saatleri arasında tüm odalarımız dolu maalesef.", f"Unfortunately, all rooms are fully booked right now ({start_time_str} - {end_time_str}).")})

    # 1. Parse Date
    date_str = None
    date_match = re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', command_text)
    if date_match:
        d, m, y = date_match.groups()
        date_str = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    else:
        date_match2 = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', command_text)
        if date_match2:
            y, m, d = date_match2.groups()
            date_str = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        else:
            now = get_turkey_time()
            import datetime
            if any(word in norm_cmd for word in ["bugun", "bugün", "today"]):
                date_str = now.strftime('%Y-%m-%d')
            elif any(word in norm_cmd for word in ["yarin", "yarın", "tomorrow"]):
                tomorrow = now + datetime.timedelta(days=1)
                date_str = tomorrow.strftime('%Y-%m-%d')
            
    # 2. Find Room
    rooms = Room.query.all()
    found_room = None
    for r in rooms:
        # Check Turkish name
        if normalize(r.name) in norm_cmd:
            found_room = r
            break
        # Check English name if available
        if r.english_name and normalize(r.english_name) in norm_cmd:
            found_room = r
            break

    # 3. Parse Time
    time_match = re.search(r'(\d{1,2})[.:](\d{2})\s*(?:-|ile|ve|to|and)?\s*(\d{1,2})[.:](\d{2})', command_text, re.IGNORECASE)
    
    # Check Intent and Missing Fields
    is_booking_intent = any(k in norm_cmd for k in ["ayir", "ayırt", "ayır", "rezerv", "rezerve", "randevu"]) or found_room or time_match or date_str

    if not date_str:
        if is_booking_intent:
            return jsonify({'success': False, 'message': msg('Lütfen tarih aralığını belirtin.', 'Please specify the date range.')})
        else:
            return jsonify({
                'success': False, 
                'reload': False,
                'message': msg(
                    'Maalesef anlayamadım şunu mu demek istediniz?<br><br>1 - Oda rezervasyonu yap<br>2 - Oda iptal et<br>3 - Oda durumunu sorgula<br>4 - QR ile giriş bilgisi<br>5 - Sohbeti kapat<br><br>Lütfen seçim yapınız (1, 2, 3, 4 veya 5 yazın).',
                    'Sorry, I couldn\'t understand. Did you mean?<br><br>1 - Book a room<br>2 - Cancel a reservation<br>3 - Check room availability<br>4 - QR login info<br>5 - Close chat<br><br>Please select an option (type 1, 2, 3, 4, or 5).'
                )
            })

    if not found_room:
        if is_booking_intent:
            return jsonify({'success': False, 'message': msg('Lütfen hangi odayı rezerve etmek istediğinizi belirtin.', 'Please specify which room you want to book.')})
        else:
            return jsonify({'success': False, 'message': msg('Sistemde böyle bir oda bulunamadı. Lütfen oda adını kontrol edin.', 'No such room was found in the system. Please check the room name.')})
        
    def time_to_minutes(t_str):
        h, m = map(int, t_str.split(':'))
        return h * 60 + m
        
    # 4. Check Existing Reservations
    existing = Reservation.query.filter_by(room_id=found_room.id, date=date_str).all()
    
    start_time = None
    end_time = None
    
    if time_match:
        sh, sm, eh, em = time_match.groups()
        start_time = f"{sh.zfill(2)}:{sm}"
        end_time = f"{eh.zfill(2)}:{em}"
        
        req_start = time_to_minutes(start_time)
        req_end = time_to_minutes(end_time)
        
        if req_start >= req_end:
            return jsonify({'success': False, 'message': msg('Bitiş saati başlangıç saatinden önce olamaz.', 'End time cannot be earlier than start time.')})
            
        from app.models import get_turkey_time
        now = get_turkey_time()
        today_str = now.strftime('%Y-%m-%d')
        current_mins = now.hour * 60 + now.minute
        
        if date_str < today_str or (date_str == today_str and req_start <= current_mins):
            return jsonify({'success': False, 'message': msg('Zamanı geçti, lütfen ileri bir zaman veya başka bir saat giriniz.', 'The time has passed, please enter a future time.')})
            
        for res in existing:
            res_s = time_to_minutes(res.start_time)
            res_e = time_to_minutes(res.end_time)
            if not (req_end <= res_s or req_start >= res_e):
                # ODA DOLU. Alternatif odaları bul:
                available_rooms = []
                for other_room in rooms:
                    if other_room.id == found_room.id:
                        continue
                    other_existing = Reservation.query.filter_by(room_id=other_room.id, date=date_str).all()
                    is_free = True
                    for o_res in other_existing:
                        o_res_s = time_to_minutes(o_res.start_time)
                        o_res_e = time_to_minutes(o_res.end_time)
                        if not (req_end <= o_res_s or req_start >= o_res_e):
                            is_free = False
                            break
                    if is_free:
                        available_rooms.append(other_room.name)
                
                m_tr = f"{found_room.name} odası bu saatlerde maalesef dolu."
                m_en = f"Unfortunately, {found_room.name} room is occupied at these hours."
                if available_rooms:
                    m_tr += " Fakat şu odalar aynı saatlerde boş: " + ", ".join(available_rooms)
                    m_en += " However, these rooms are available: " + ", ".join(available_rooms)
                else:
                    m_tr += " Üstelik bu saatlerde başka boş oda da bulunmuyor."
                    m_en += " Moreover, there are no other available rooms at this time."
                
                return jsonify({'success': False, 'message': msg(m_tr, m_en)})
    else:
        from app.models import get_turkey_time
        now = get_turkey_time()
        today_str = now.strftime('%Y-%m-%d')
        current_mins = now.hour * 60 + now.minute if date_str == today_str else 0
        
        possible_starts = [f"{h:02d}:00" for h in range(9, 18)]

        if any(w in norm_cmd for w in ["boş mu", "bos mu", "müsait mi", "musait mi", "boşluk", "bosluk", "durumu", "var mi", "var mı"]):
            available_slots = []
            for p_start in possible_starts:
                req_start = time_to_minutes(p_start)
                req_end = req_start + 60
                
                if date_str < today_str or (date_str == today_str and req_start <= current_mins):
                    continue
                    
                conflict = False
                for res in existing:
                    res_s = time_to_minutes(res.start_time)
                    res_e = time_to_minutes(res.end_time)
                    if not (req_end <= res_s or req_start >= res_e):
                        conflict = True
                        break
                
                if not conflict:
                    available_slots.append(p_start)
            
            if available_slots:
                slots_str = ", ".join(available_slots)
                m_tr = f"{date_str} tarihinde <b>{found_room.name}</b> odasında şu saatlerde başlangıç için uygunluk var: <b>{slots_str}</b>.<br>Rezervasyon yapmak isterseniz lütfen saati belirtin (Örn: 10:00 - 11:00 arası)."
                m_en = f"On {date_str}, <b>{found_room.name}</b> has availability starting at: <b>{slots_str}</b>.<br>Please specify the exact time to book."
                return jsonify({'success': True, 'reload': False, 'message': msg(m_tr, m_en)})
            else:
                return jsonify({'success': False, 'message': msg(f'{date_str} tarihinde {found_room.name} odasında boş yer yok.', f'No available slots found for {found_room.name} on {date_str}.')})

        return jsonify({'success': False, 'message': msg('Lütfen saat aralığını belirtin.', 'Please specify the time range.')})
            
    # 5. Check overlapping invitations
    from app.models import Notification
    my_invitations = Notification.query.filter_by(user_id=current_user.id, type='invitation', status='pending').all()
    for notif in my_invitations:
        r = getattr(notif, 'reservation', None)
        if r and r.date == date_str:
            res_s = time_to_minutes(r.start_time)
            res_e = time_to_minutes(r.end_time)
            # Check overlap
            if not (req_end <= res_s or req_start >= res_e):
                m_tr = f"Sizin bu saatlerde (<b>{r.start_time}-{r.end_time}</b>) <b>{r.room.name}</b> odasında zaten bekleyen bir davetiniz var. Lütfen önce bildirimlerinizden bu daveti yanıtlayın."
                m_en = f"You already have a pending invitation for <b>{r.room.name}</b> at these hours (<b>{r.start_time}-{r.end_time}</b>). Please respond to your invitation in notifications first."
                return jsonify({'success': False, 'message': msg(m_tr, m_en)})

    # 6. Create Reservation
    try:
        new_res = Reservation(
            user_id=current_user.id,
            room_id=found_room.id,
            date=date_str,
            start_time=start_time,
            end_time=end_time
        )
        db.session.add(new_res)
        db.session.commit()
        msg_tr = f"Harika! <b>{found_room.name}</b> odası <b>{date_str}</b> tarihinde <b>{start_time}-{end_time}</b> arası sizin için rezerve edildi.<br><br>📌 <b>Hatırlatmalar:</b><br>• Gerekli belgeleri yüklemeyi unutmayın.<br>• QR ile giriş yapmayı unutmayın."
        msg_en = f"Great! <b>{found_room.name}</b> has been booked for you on <b>{date_str}</b> between <b>{start_time}-{end_time}</b>.<br><br>📌 <b>Reminders:</b><br>• Do not forget to upload the necessary documents.<br>• Do not forget to log in with QR."
        return jsonify({'success': True, 'reload': False, 'message': msg(msg_tr, msg_en)})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Bir hata oluştu: ' + str(e)})

@bp.route('/')
def index():
    return render_template('index.html', title='Ana Sayfa')

@bp.route('/rooms')
@login_required
def rooms():
    from app.models import Room, Reservation, get_turkey_time
    from datetime import datetime
    from flask_babel import gettext
    
    room_stats = []
    now = get_turkey_time()
    today_str = now.strftime('%Y-%m-%d')
    
    try:
        rooms_list = Room.query.all()
        current_minutes_since_midnight = now.hour * 60 + now.minute
        
        possible_slots = []
        for h in range(9, 18):
            possible_slots.extend([f"{h:02d}:00", f"{h:02d}:30"])
        
        for r in rooms_list:
            reservations = Reservation.query.filter_by(room_id=r.id, date=today_str).all()
            
            actual_booked_minutes = 0
            for res in reservations:
                fmt = '%H:%M'
                res_start_dt = datetime.strptime(res.start_time, fmt)
                res_end_dt = datetime.strptime(res.end_time, fmt)
                actual_booked_minutes += (res_end_dt - res_start_dt).seconds // 60
                
            available_slots = 0
            for slot in possible_slots:
                slot_h, slot_m = map(int, slot.split(':'))
                slot_start_mins = slot_h * 60 + slot_m
                slot_end_mins = slot_start_mins + 30
                
                # Geçmiş zaman kontrolü
                if slot_start_mins < current_minutes_since_midnight:
                    continue
                    
                conflict = False
                for res in reservations:
                    res_s_h, res_s_m = map(int, res.start_time.split(':'))
                    res_e_h, res_e_m = map(int, res.end_time.split(':'))
                    res_start_mins = res_s_h * 60 + res_s_m
                    res_end_mins = res_e_h * 60 + res_e_m
                    
                    if not (slot_end_mins <= res_start_mins or slot_start_mins >= res_end_mins):
                        conflict = True
                        break
                        
                if not conflict:
                    available_slots += 1
                    
            if available_slots == 0:
                status = 'full'
                label = gettext('Dolu')
                color = '#ef4444' # Red
            elif available_slots == 18:
                status = 'empty'
                label = gettext('Boş')
                color = '#10b981' # Green
            elif available_slots < 6:
                status = 'partial'
                label = gettext('Çoğunluğu Dolu')
                color = '#f59e0b' # Yellow
            else:
                status = 'partial'
                label = gettext('Kısmen Dolu')
                color = '#f59e0b' # Yellow
                
            room_stats.append({
                'room': r,
                'status': status,
                'label': label,
                'color': color,
                'booked_minutes': actual_booked_minutes
            })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error loading rooms in /rooms: {e}", exc_info=True)
        flash(gettext('Oda verileri yüklenirken bir veritabanı hatası oluştu. Lütfen sayfayı yenileyin.'), 'warning')
        
    return render_template('rooms/list.html', title='Odalar', room_stats=room_stats, today_date=today_str)


@bp.route('/rooms/add', methods=['GET', 'POST'])
@admin_required
def add_room():
    from app.forms import RoomForm
    from app.models import Room
    form = RoomForm()
    if form.validate_on_submit():
        new_room = Room(
            name=form.name.data,
            english_name=form.english_name.data,
            capacity=form.capacity.data,
            description=form.description.data
        )
        db.session.add(new_room)
        db.session.commit()
        log_action(current_user.id, "ODA_EKLENDİ", f"{form.name.data} odası eklendi.")
        from flask_babel import gettext
        flash(gettext('Yeni oda başarıyla eklendi!'), 'success')
        return redirect(url_for('main.rooms'))
    return render_template('rooms/add.html', title='Oda Ekle', form=form)

@bp.route('/rooms/edit/<int:room_id>', methods=['GET', 'POST'])
@admin_required
def edit_room(room_id):
    from app.forms import EditRoomForm
    from app.models import Room
    room = Room.query.get_or_404(room_id)
    form = EditRoomForm()
    if form.validate_on_submit():
        existing = Room.query.filter_by(name=form.name.data).first()
        if existing and existing.id != room.id:
            from flask_babel import gettext
            flash(gettext('Bu isimde başka bir oda zaten var.'), 'danger')
        else:
            room.name = form.name.data
            room.english_name = form.english_name.data
            room.capacity = form.capacity.data
            room.description = form.description.data
            db.session.commit()
            log_action(current_user.id, "ODA_GÜNCELLENDİ", f"{room.name} odası güncellendi.")
            from flask_babel import gettext
            flash(gettext('Oda başarıyla güncellendi!'), 'success')
            return redirect(url_for('main.rooms'))
    elif request.method == 'GET':
        form.name.data = room.name
        form.english_name.data = room.english_name
        form.capacity.data = room.capacity
        form.description.data = room.description
    return render_template('rooms/edit.html', title='Odayı Düzenle', form=form, room=room)

@bp.route('/api/reservations/<int:room_id>/<date_str>')
@login_required
def api_reservations(room_id, date_str):
    reservations = Reservation.query.filter_by(room_id=room_id, date=date_str).all()
    from datetime import datetime, timedelta
    from app.models import get_turkey_time
    
    now = get_turkey_time()
    today_str = now.strftime('%Y-%m-%d')
    current_time_str = now.strftime('%H:%M')
    
    booked_slots = []
    for res in reservations:
        # Ignore reservations that have already completely ended before the current time
        if date_str == today_str and res.end_time <= current_time_str:
            continue
            
        start_dt = datetime.strptime(res.start_time, '%H:%M')
        end_dt = datetime.strptime(res.end_time, '%H:%M')
        curr = start_dt
        while curr < end_dt:
            booked_slots.append(curr.strftime('%H:%M'))
            curr += timedelta(minutes=30)
    return jsonify({'booked_slots': booked_slots})

@bp.route('/overview')
@login_required
def overview():
    from app.models import get_turkey_time
    rooms = Room.query.all()
    today = get_turkey_time().strftime('%Y-%m-%d')
    current_hour = get_turkey_time().strftime('%H:%M')
    return render_template('overview.html', title='Günlük Durum', rooms=rooms, today=today, current_hour=current_hour)

@bp.route('/api/overview/<date_str>')
@login_required
def api_overview(date_str):
    rooms = Room.query.all()
    reservations = Reservation.query.filter_by(date=date_str).all()
    
    # Structure: { room_id: { "09:00": {"id": 1, "username": "Admin"} } }
    data = {}
    for r in rooms:
        data[r.id] = {}
        
    from datetime import datetime, timedelta
    
    for res in reservations:
        if res.room_id in data:
            start_dt = datetime.strptime(res.start_time, '%H:%M')
            end_dt = datetime.strptime(res.end_time, '%H:%M')
            curr = start_dt
            while curr < end_dt:
                slot_str = curr.strftime('%H:%M')
                data[res.room_id][slot_str] = {
                    "id": res.id,
                    "username": res.user.username
                }
                curr += timedelta(minutes=30)
            
    return jsonify(data)

@bp.route('/api/calendar/<int:room_id>/<int:year>/<int:month>')
@login_required
def api_room_calendar(room_id, year, month):
    import calendar
    from app.models import get_turkey_time
    
    month_str = f"{year}-{month:02d}-"
    reservations = Reservation.query.filter_by(room_id=room_id).filter(Reservation.date.like(f"{month_str}%")).all()
    
    now = get_turkey_time()
    today_str = now.strftime('%Y-%m-%d')
    current_minutes_since_midnight = now.hour * 60 + now.minute
        
    result = {}
    _, num_days = calendar.monthrange(year, month)
    
    possible_slots = []
    for h in range(9, 18):
        possible_slots.extend([f"{h:02d}:00", f"{h:02d}:30"])
    
    for day in range(1, num_days + 1):
        date_str = f"{month_str}{day:02d}"
        
        if date_str < today_str:
            result[date_str] = "full"
            continue
            
        day_reservations = [r for r in reservations if r.date == date_str]
        available_slots = 0
        
        for slot in possible_slots:
            slot_h, slot_m = map(int, slot.split(':'))
            slot_start_mins = slot_h * 60 + slot_m
            slot_end_mins = slot_start_mins + 30
            
            # Geçi time check
            if date_str == today_str and slot_start_mins < current_minutes_since_midnight:
                continue
                
            conflict = False
            for res in day_reservations:
                res_s_h, res_s_m = map(int, res.start_time.split(':'))
                res_e_h, res_e_m = map(int, res.end_time.split(':'))
                res_start_mins = res_s_h * 60 + res_s_m
                res_end_mins = res_e_h * 60 + res_e_m
                
                if not (slot_end_mins <= res_start_mins or slot_start_mins >= res_end_mins):
                    conflict = True
                    break
                    
            if not conflict:
                available_slots += 1
                
        if available_slots == 0:
            result[date_str] = "full"
        elif available_slots == 18:
            result[date_str] = "empty"
        else:
            result[date_str] = "partial"
            
    return jsonify(result)

@bp.route('/api/calendar/<int:year>/<int:month>')
@login_required
def api_calendar(year, month):
    import calendar
    rooms_count = Room.query.count()
    total_slots_per_day = rooms_count * 9 # 09:00 to 17:00 is 9 slots
    
    month_str = f"{year}-{month:02d}-"
    reservations = Reservation.query.filter(Reservation.date.like(f"{month_str}%")).all()
    
    daily_counts = {}
    for res in reservations:
        if res.date not in daily_counts:
            daily_counts[res.date] = 0
        daily_counts[res.date] += 1
        
    result = {}
    _, num_days = calendar.monthrange(year, month)
    
    for day in range(1, num_days + 1):
        date_str = f"{month_str}{day:02d}"
        count = daily_counts.get(date_str, 0)
        
        from app.models import get_turkey_time
        now = get_turkey_time()
        today_str = now.strftime('%Y-%m-%d')
        
        if date_str < today_str:
            result[date_str] = "full"    # Kırmızı
        elif date_str == today_str and now.hour >= 18:
            result[date_str] = "full"
        elif count == 0:
            result[date_str] = "empty"   # Yeşil
        elif count >= total_slots_per_day:
            result[date_str] = "full"    # Kırmızı
        else:
            result[date_str] = "partial" # Sarı
            
    return jsonify(result)

@bp.route('/rooms/<int:room_id>/book', methods=['GET', 'POST'])
@login_required
def book_room(room_id):
    from app.models import get_turkey_time
    room = Room.query.get_or_404(room_id)
    all_users = User.query.filter(User.id != current_user.id).all()
    today = get_turkey_time().strftime('%Y-%m-%d')
    current_hour = get_turkey_time().strftime('%H:%M')
    
    selected_date = request.args.get('date', today)
    selected_time = request.args.get('time', '')
    
    if request.method == 'POST':
        req_date = request.form.get('date')
        start_time = request.form.get('start_time')
        
        if not req_date or not start_time:
            flash('Lütfen geçerli bir tarih ve saat seçin.', 'danger')
            return redirect(url_for('main.book_room', room_id=room.id))

        # Past time check
        today_str = get_turkey_time().strftime('%Y-%m-%d')
        current_hour_str = get_turkey_time().strftime('%H:%M')
        
        if req_date < today_str:
            flash('Geçmiş bir tarihe rezervasyon yapamazsınız.', 'danger')
            return redirect(url_for('main.book_room', room_id=room.id))
            
        # Instead of checking start_time < current_hour_str, we check if the entire slot has passed
        # e.g., if booking 13:30-14:00 at 13:35, it's allowed because end_time (14:00) > 13:35
        # We calculate end_time first
        duration = request.form.get('duration')
        try:
            duration = int(duration)
            if duration not in [30, 60]:
                duration = 60
        except:
            duration = 60

        from datetime import datetime, timedelta
        start_dt = datetime.strptime(start_time, '%H:%M')
        end_dt = start_dt + timedelta(minutes=duration)
        end_time = end_dt.strftime('%H:%M')

        if req_date == today_str and end_time <= current_hour_str:
            flash('Bu saatin süresi dolmuş, geçmiş bir saate rezervasyon yapamazsınız.', 'danger')
            return redirect(url_for('main.book_room', room_id=room.id))



        # OVERLAP PREVENTION: Check if already booked
        all_day_res = Reservation.query.filter_by(room_id=room.id, date=req_date).all()
        overlap = False
        for r in all_day_res:
            # If the existing reservation ended early (before now), it shouldn't block the slot
            if req_date == today_str and r.end_time <= current_hour_str:
                continue
                
            # İki zaman aralığının kesişip kesişmediğini kontrol et
            if max(start_time, r.start_time) < min(end_time, r.end_time):
                overlap = True
                break
                
        if overlap:
            # Kullanıcıya boş olan diğer odaları öner
            other_rooms = Room.query.filter(Room.id != room.id).all()
            available_rooms = []
            
            for o_room in other_rooms:
                o_reservations = Reservation.query.filter_by(room_id=o_room.id, date=req_date).all()
                o_overlap = False
                for r in o_reservations:
                    if req_date == today_str and r.end_time <= current_hour_str:
                        continue
                    if max(start_time, r.start_time) < min(end_time, r.end_time):
                        o_overlap = True
                        break
                if not o_overlap:
                    available_rooms.append(o_room.name)
            
            if available_rooms:
                suggestion = ", ".join(available_rooms)
                flash(f'Üzgünüz, bu saat dilimi dolu. Ancak aynı saatler için şu odalarımız müsaittir: {suggestion}', 'warning')
            else:
                flash('Üzgünüz, bu saat dilimi az önce başkası tarafından rezerve edildi veya çakışıyor. Lütfen süreyi veya saati değiştirin.', 'danger')
                
            return redirect(url_for('main.book_room', room_id=room.id))
        
        # Parse attendees
        attendee_ids = request.form.getlist('attendees')
        invited_users = User.query.filter(User.id.in_(attendee_ids)).all() if attendee_ids else []

        new_reservation = Reservation(
            user_id=current_user.id,
            room_id=room.id,
            date=req_date,
            start_time=start_time,
            end_time=end_time
        )
        
        for user in invited_users:
            new_reservation.attendees.append(user)
            
            # Create a notification for the invited user
            msg = f"{current_user.username} sizi {req_date} tarihinde {start_time}-{end_time} saatleri arasında {room.name} odasındaki toplantıya davet etti."
            notif = Notification(user_id=user.id, message=msg, type='invitation', status='pending')
            # Assign reservation after new_reservation gets an ID (we'll flush first)
            
        db.session.add(new_reservation)
        db.session.flush() # To get new_reservation.id
        
        # Now update notifications with reservation_id
        for user in invited_users:
            notif = Notification(user_id=user.id, reservation_id=new_reservation.id, message=f"{current_user.username} sizi {req_date} tarihinde {start_time}-{end_time} saatleri arasında {room.name} odasındaki toplantıya davet etti.", type='invitation', status='pending')
            db.session.add(notif)
            
        db.session.commit()
        
        # Mail sending removed
        
        # Log the action
        log_msg = f"{room.name} odası için {req_date} {start_time}-{end_time} rezervasyonu yapıldı."
        if invited_users:
            invited_names = ", ".join([u.username for u in invited_users])
            log_msg += f" Davetliler: {invited_names}"
        log_action(current_user.id, "REZERVASYON_OLUŞTURULDU", log_msg)
        
        flash(gettext("%(room)s için rezervasyonunuz onaylandı!", room=room.name), "success")
        return redirect(url_for('main.dashboard'))

    return render_template('rooms/book.html', room=room, title=gettext('%(room_name)s Rezervasyon', room_name=room.name), all_users=all_users, today=today, current_hour=current_hour, selected_date=selected_date, selected_time=selected_time)

@bp.route('/dashboard')
@login_required
def dashboard():
    from app.utils import generate_google_calendar_url
    from app.models import get_turkey_time
    
    now = get_turkey_time()
    today_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M')
    
    all_reservations = Reservation.query.filter_by(user_id=current_user.id).order_by(Reservation.date.desc(), Reservation.start_time.desc()).all()
    
    reservations = []
    for res in all_reservations:
        if res.date < today_str or (res.date == today_str and res.end_time <= time_str):
            continue
        res.cal_url = generate_google_calendar_url(res.room.name, res.date, res.start_time, res.end_time)
        reservations.append(res)
        
    all_invited = current_user.invited_reservations
    all_invited.sort(key=lambda x: (x.date, x.start_time), reverse=True)
    
    invited_reservations = []
    for res in all_invited:
        if res.date < today_str or (res.date == today_str and res.end_time <= time_str):
            continue
        res.cal_url = generate_google_calendar_url(res.room.name, res.date, res.start_time, res.end_time)
        invited_reservations.append(res)
        
    return render_template('dashboard.html', title='Dashboard', reservations=reservations, invited_reservations=invited_reservations)

@bp.route('/reservation/<int:res_id>/delete', methods=['POST'])
@login_required
def delete_reservation(res_id):
    reservation = Reservation.query.get_or_404(res_id)
    
    if not current_user.is_admin and reservation.user_id != current_user.id:
        flash('Bu işlemi yapmaya yetkiniz yok.', 'danger')
        return redirect(url_for('main.dashboard'))
        
    room_name = reservation.room.name
    res_date = reservation.date


    start_time = reservation.start_time
    end_time = reservation.end_time
    creator_id = reservation.user_id
    
    # If someone else (admin) is cancelling it, notify the creator
    if current_user.id != creator_id:
        msg = f"Yönetici tarafından {res_date} tarihindeki {start_time}-{end_time} saatleri arasındaki {room_name} odası rezervasyonunuz iptal edildi."
        # We don't set reservation_id because the reservation is about to be deleted
        cancel_notif = Notification(user_id=creator_id, message=msg, type='info')
        db.session.add(cancel_notif)
        
    # First, delete all notifications related to this reservation (like pending invites)
    Notification.query.filter_by(reservation_id=res_id).delete()
    
    # Remove attendees to clean up the association table
    reservation.attendees.clear()
        
    db.session.delete(reservation)
    db.session.commit()
    
    log_action(current_user.id, "REZERVASYON_İPTALİ", f"Rezervasyon ID {res_id} ({room_name}, {res_date} {start_time}-{end_time}) iptal edildi.")
    
    flash(gettext('Rezervasyon başarıyla iptal edildi.'), 'success')
    
    if current_user.is_admin and reservation.user_id != current_user.id:
        return redirect(url_for('main.admin_panel'))
    return redirect(request.referrer or url_for('main.dashboard'))

@bp.route('/reservation/<int:res_id>/leave', methods=['POST'])
@login_required
def leave_reservation(res_id):
    reservation = Reservation.query.get_or_404(res_id)
    
    if current_user in reservation.attendees:
        reservation.attendees.remove(current_user)
        db.session.commit()
        flash(gettext('Toplantıdan başarıyla ayrıldınız.'), 'success')
    else:
        flash(gettext('Bu toplantıya zaten katılmıyorsunuz.'), 'danger')
        
    return redirect(url_for('main.dashboard'))

@bp.route('/admin')
@admin_required
def admin_panel():
    from app.models import User, AuditLog, get_turkey_time
    now = get_turkey_time()
    today_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M')
    
    # Sadece bugünkü ve gelecekteki rezervasyonları getir
    all_reservations = Reservation.query.order_by(Reservation.date.desc(), Reservation.start_time.desc()).all()
    reservations = []
    for res in all_reservations:
        if res.date > today_str or (res.date == today_str and res.end_time > time_str):
            reservations.append(res)
            
    user_page = request.args.get('user_page', 1, type=int)
    users = User.query.paginate(page=user_page, per_page=10, error_out=False)
    rooms = Room.query.all()
    
    # Loglar artık özel bir sayfaya taşındı, ana panele logları göndermiyoruz.
    
    # Active Meetings
    now = get_turkey_time()
    today_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M')
    
    active_meetings = []
    today_res = Reservation.query.filter_by(date=today_str).all()
    for res in today_res:
        if res.start_time <= time_str < res.end_time:
            active_meetings.append(res)
    
    # Metrics
    metrics = {
        'total_users': users.total,
        'total_rooms': len(rooms),
        'total_reservations': len(all_reservations),
        'today_reservations': len(today_res)
    }
    
    return render_template('admin_panel.html', title='Admin Paneli', reservations=reservations, users=users, rooms=rooms, metrics=metrics, active_meetings=active_meetings)

@bp.route('/admin/logs', methods=['GET'])
@admin_required
def admin_logs():
    from app.models import AuditLog
    from datetime import datetime, time
    
    page = request.args.get('page', 1, type=int)
    date_filter = request.args.get('date', '')
    
    query = AuditLog.query
    
    if date_filter:
        try:
            # Parse YYYY-MM-DD
            target_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            start_datetime = datetime.combine(target_date, time.min)
            end_datetime = datetime.combine(target_date, time.max)
            query = query.filter(AuditLog.timestamp >= start_datetime, AuditLog.timestamp <= end_datetime)
        except ValueError:
            pass
            
    # Always sort descending
    logs = query.order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=20, error_out=False)
    
    return render_template('admin_logs.html', title='Log Yönetimi', logs=logs, date_filter=date_filter)

@bp.route('/admin/logs/export', methods=['GET'])
@admin_required
def export_admin_logs():
    from app.models import AuditLog
    from datetime import datetime, time
    from flask_babel import gettext
    import csv
    import io
    from flask import Response

    date_filter = request.args.get('date', '')
    query = AuditLog.query

    if date_filter:
        try:
            target_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            start_datetime = datetime.combine(target_date, time.min)
            end_datetime = datetime.combine(target_date, time.max)
            query = query.filter(AuditLog.timestamp >= start_datetime, AuditLog.timestamp <= end_datetime)
        except ValueError:
            pass
            
    logs = query.order_by(AuditLog.timestamp.desc()).all()

    output = io.StringIO()
    # Write BOM for Excel UTF-8 compatibility
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    
    # Headers
    writer.writerow([
        gettext('Tarih'), 
        gettext('İşlem Türü'), 
        gettext('Kullanıcı'), 
        gettext('Detaylar')
    ])
    
    ctx = inject_lang()
    
    for log in logs:
        # Format Date
        date_str = log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        # Translate action
        action_str = ctx['translate_log_action'](log.action)
        
        # User details
        if log.user:
            user_str = f"{log.user.full_name} (@{log.user.username})"
        else:
            user_str = gettext('Sistem')
            
        # Translate details
        details_str = ctx['translate_log_details'](log.details)
        
        writer.writerow([date_str, action_str, user_str, details_str])
        
    response = Response(output.getvalue(), mimetype='text/csv')
    
    # Determine filename
    if date_filter:
        filename = f"sistem_loglari_{date_filter}.csv"
    else:
        filename = f"sistem_loglari_tum.csv"
        
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@bp.route('/admin/logs/delete-by-date', methods=['POST'])
@admin_required
def delete_logs_by_date():
    from app.models import AuditLog
    from app.utils import log_action
    from datetime import datetime, time
    from flask_babel import gettext
    
    date_to_delete = request.form.get('date')
    if not date_to_delete:
        flash(gettext('Silinecek tarihi seçmeniz gerekiyor.'), 'danger')
        return redirect(url_for('main.admin_logs'))
        
    try:
        target_date = datetime.strptime(date_to_delete, '%Y-%m-%d').date()
        start_datetime = datetime.combine(target_date, time.min)
        end_datetime = datetime.combine(target_date, time.max)
        
        logs_to_delete = AuditLog.query.filter(AuditLog.timestamp >= start_datetime, AuditLog.timestamp <= end_datetime).all()
        
        count = len(logs_to_delete)
        if count == 0:
            flash(gettext('%(date)s tarihi için silinecek log bulunamadı.', date=date_to_delete), 'info')
        else:
            for log in logs_to_delete:
                db.session.delete(log)
            db.session.commit()
            
            log_action(current_user.id, "SİSTEM", f"{date_to_delete} tarihindeki {count} log kalıcı olarak silindi.")
            flash(gettext('%(date)s tarihine ait %(count)s log kaydı veritabanından kalıcı olarak silindi.', date=date_to_delete, count=count), 'success')
            
    except ValueError:
        flash(gettext('Geçersiz tarih formatı.'), 'danger')
        
    return redirect(url_for('main.admin_logs', date=date_to_delete))

@bp.route('/admin/logs/delete-selected', methods=['POST'])
@admin_required
def delete_selected_logs():
    from app.models import AuditLog
    from app.utils import log_action
    from flask_babel import gettext
    
    log_ids = request.form.getlist('log_ids')
    if not log_ids:
        flash(gettext('Silmek için hiçbir log seçmediniz.'), 'warning')
        return redirect(url_for('main.admin_logs'))
        
    try:
        # Prevent SQL injection or type errors
        log_ids = [int(i) for i in log_ids]
        logs_to_delete = AuditLog.query.filter(AuditLog.id.in_(log_ids)).all()
        
        count = len(logs_to_delete)
        if count > 0:
            for log in logs_to_delete:
                db.session.delete(log)
            db.session.commit()
            
            log_action(current_user.id, "SİSTEM", f"Admin tarafından {count} adet log manuel olarak silindi.")
            flash(gettext('Seçilen %(count)s adet log başarıyla silindi.', count=count), 'success')
        else:
            flash(gettext('Seçilen loglar bulunamadı.'), 'info')
    except Exception as e:
        flash(gettext('Loglar silinirken bir hata oluştu.'), 'danger')
        
    # Maintain pagination/filters if passed, otherwise default redirect
    page = request.args.get('page', 1, type=int)
    date_filter = request.args.get('date', '')
    return redirect(url_for('main.admin_logs', page=page, date=date_filter))

@bp.route('/admin/reservations/clear_old', methods=['POST'])
@admin_required
def clear_old_reservations():
    from app.models import Reservation, Notification, get_turkey_time
    now = get_turkey_time()
    today_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M')
    
    all_res = Reservation.query.all()
    count = 0
    for res in all_res:
        if res.date < today_str or (res.date == today_str and res.end_time <= time_str):
            Notification.query.filter_by(reservation_id=res.id).update({'reservation_id': None})
            db.session.delete(res)
            count += 1
            
    db.session.commit()
    log_action(current_user.id, "SİSTEM", f"{count} adet eski rezervasyon kalıcı olarak silindi.")
    flash(f'{count} adet geçmiş rezervasyon veritabanından kalıcı olarak silindi.', 'success')
    return redirect(url_for('main.admin_panel'))

@bp.route('/admin/user/<int:user_id>/toggle_admin', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Kendi yetkinizi değiştiremezsiniz!', 'danger')
        return redirect(url_for('main.admin_panel'))
        
    if user.email == 'admin@sirket.com':
        flash('Ana yöneticinin yetkisi alınamaz!', 'danger')
        return redirect(url_for('main.admin_panel'))
        
    user.is_admin = not user.is_admin
    db.session.commit()
    
    action = 'ADMIN_YAPILDI' if user.is_admin else 'ADMINLIK_ALINDI'
    log_action(current_user.id, action, f"Kullanıcı {user.username} admin yetkisi {'verildi' if user.is_admin else 'alındı'}.")
    
    if user.is_admin:
        flash(f'{user.username} kullanıcısına admin yetkisi verildi.', 'success')
    else:
        flash(f'{user.username} kullanıcısının admin yetkisi alındı.', 'success')
        
    return redirect(url_for('main.admin_panel'))

@bp.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Kendinizi silemezsiniz!', 'danger')
        return redirect(url_for('main.admin_panel'))
        
    if user.email == 'admin@sirket.com':
        flash('Ana yönetici hesabı silinemez!', 'danger')
        return redirect(url_for('main.admin_panel'))
        
    username = user.username
    
    # Clean up dependent records to avoid IntegrityError
    # 1. Nullify user_id in logs to keep the history
    AuditLog.query.filter_by(user_id=user.id).update({'user_id': None})
    
    # 2. Delete user's notifications, subscriptions, and documents
    Notification.query.filter_by(user_id=user.id).delete()
    from app.models import PushSubscription, Document
    PushSubscription.query.filter_by(user_id=user.id).delete()
    
    # Delete documents uploaded by this user
    documents = Document.query.filter_by(user_id=user.id).all()
    import os
    for doc in documents:
        if os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except:
                pass
        db.session.delete(doc)
    
    # 3. Remove user from any meetings they were invited to or active in
    user.invited_reservations.clear()
    user.active_in_reservations.clear()
    
    # 4. Handle reservations created by the user
    user_reservations = Reservation.query.filter_by(user_id=user.id).all()
    for res in user_reservations:
        # Delete notifications tied to these reservations
        Notification.query.filter_by(reservation_id=res.id).delete()
        # Remove attendees
        res.attendees.clear()
        db.session.delete(res)
    
    db.session.delete(user)
    db.session.commit()
    
    log_action(current_user.id, "KULLANICI_SİLİNDİ", f"{username} (ID: {user_id}) kullanıcısı silindi.")
    
    flash(f'{username} kullanıcısı silindi.', 'success')
    return redirect(url_for('main.admin_panel'))

@bp.route('/admin/room/<int:room_id>/delete', methods=['POST'])
@admin_required
def delete_room(room_id):
    room = Room.query.get_or_404(room_id)
    Reservation.query.filter_by(room_id=room.id).delete()
    room_name = room.name
    db.session.delete(room)
    db.session.commit()
    
    log_action(current_user.id, "ODA_SİLİNDİ", f"{room_name} (ID: {room_id}) odası silindi.")
    
    flash(f'{room_name} odası silindi.', 'success')
    return redirect(url_for('main.admin_panel'))

@bp.route('/notification/<int:notif_id>/accept', methods=['POST'])
@login_required
def accept_invitation(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
        flash(gettext('Bu işlemi yapmaya yetkiniz yok.'), 'danger')
        return redirect(request.referrer or url_for('main.dashboard'))
        
    notif.status = 'accepted'
    notif.is_read = True
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"status": "success", "message": gettext("Daveti kabul ettiniz.")})
    
    flash(gettext('Daveti kabul ettiniz.'), 'success')
    return redirect(request.referrer or url_for('main.dashboard'))

@bp.route('/notification/<int:notif_id>/reject', methods=['POST'])
@login_required
def reject_invitation(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != current_user.id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
        flash(gettext('Bu işlemi yapmaya yetkiniz yok.'), 'danger')
        return redirect(request.referrer or url_for('main.dashboard'))
        
    notif.status = 'rejected'
    notif.is_read = True
    
    # Remove user from reservation attendees
    if notif.reservation and current_user in notif.reservation.attendees:
        notif.reservation.attendees.remove(current_user)
        
    # Create info notification for creator
    if notif.reservation:
        creator = notif.reservation.user
        reject_msg = f"{current_user.username}, {notif.reservation.date} tarihindeki {notif.reservation.room.name} odası davetinizi reddetti."
        info_notif = Notification(user_id=creator.id, reservation_id=notif.reservation.id, message=reject_msg, type='info')
        db.session.add(info_notif)
        
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"status": "success", "message": gettext("Daveti reddettiniz.")})
        
    flash(gettext('Daveti reddettiniz.'), 'success')
    return redirect(request.referrer or url_for('main.dashboard'))

@bp.route('/reservation/<int:res_id>/qr')
@login_required
def generate_qr(res_id):
    from app.utils import generate_qr_token
    from flask import redirect
    from urllib.parse import quote
    
    reservation = Reservation.query.get_or_404(res_id)
    
    if current_user.id != reservation.user_id and current_user not in reservation.attendees:
        return jsonify({'error': 'Unauthorized'}), 403
        
    token = generate_qr_token(res_id, current_user.id)
    google_qr_url = f"https://quickchart.io/qr?text={quote(token)}&size=300"
    return redirect(google_qr_url)

@bp.route('/reservation/<int:res_id>/qr/exit')
@login_required
def generate_exit_qr(res_id):
    from app.utils import generate_exit_qr_token
    from flask import redirect
    from urllib.parse import quote
    
    reservation = Reservation.query.get_or_404(res_id)
    
    if current_user.id != reservation.user_id and current_user not in reservation.attendees:
        return jsonify({'error': 'Unauthorized'}), 403
        
    token = generate_exit_qr_token(res_id, current_user.id)
    google_qr_url = f"https://quickchart.io/qr?text={quote(token)}&size=300"
    return redirect(google_qr_url)

@bp.route('/api/door/scan_exit', methods=['POST'])
def door_scan_exit():
    from app.utils import verify_exit_qr_token
    data = request.get_json()
    if not data or 'token' not in data:
        return jsonify({'status': 'error', 'message': 'Token bulunamadı.'}), 400
    token = data['token']
    res_id = verify_exit_qr_token(token)
    if not res_id:
        return jsonify({'status': 'error', 'message': 'Geçersiz veya süresi dolmuş Çıkış QR kodu.'}), 400
    
    reservation = Reservation.query.get(res_id)
    if not reservation:
        return jsonify({'status': 'error', 'message': 'Rezervasyon bulunamadı.'}), 404
        
    from app.models import get_turkey_time
    now = get_turkey_time()
    today_str = now.strftime('%Y-%m-%d')
    current_time_str = now.strftime('%H:%M')
    
    if reservation.date != today_str:
        return jsonify({'status': 'error', 'message': 'Bu rezervasyon bugün için değil.'}), 400
        
    if current_time_str >= reservation.start_time and current_time_str < reservation.end_time:
        reservation.end_time = current_time_str
        db.session.commit()
        return jsonify({
            'status': 'success', 
            'message': f'Çıkış yapıldı. {reservation.room.name} odası kullanıma açıldı.'
        })
    elif current_time_str >= reservation.end_time:
        return jsonify({'status': 'error', 'message': 'Rezervasyon zaten sona ermiş.'}), 400
    else:
        return jsonify({'status': 'error', 'message': 'Rezervasyon henüz başlamamış.'}), 400


@bp.route('/api/door/scan', methods=['POST'])
def door_scan():
    from app.utils import verify_qr_token, verify_exit_qr_token
    from app.models import User
    data = request.get_json()
    if not data or 'token' not in data:
        return jsonify({'status': 'error', 'message': 'Token bulunamadı.'}), 400
    token = data['token']
    
    # --- Try Exit QR First ---
    exit_res_id, exit_user_id = verify_exit_qr_token(token)
    if exit_res_id and exit_user_id:
        reservation = Reservation.query.get(exit_res_id)
        user = User.query.get(exit_user_id)
        if not reservation or not user:
            return jsonify({'status': 'error', 'message': 'Rezervasyon bulunamadı.'}), 404
        
        from app.models import get_turkey_time
        now = get_turkey_time()
        today_str = now.strftime('%Y-%m-%d')
        current_time_str = now.strftime('%H:%M')
        
        if reservation.date != today_str:
            return jsonify({'status': 'error', 'message': 'Bu çıkış rezervasyonu bugün için değil.'}), 400
            
        if current_time_str >= reservation.start_time and current_time_str < reservation.end_time:
            if user in reservation.active_users:
                reservation.active_users.remove(user)
                msg = f'Çıkış yapıldı. ({user.username})'
                
                if len(reservation.active_users) == 0:
                    reservation.end_time = current_time_str
                    msg += f' Odada kimse kalmadığı için {reservation.room.name} odası boşa çıkarıldı.'
                
                db.session.commit()
                return jsonify({'status': 'success', 'message': msg})
            else:
                return jsonify({'status': 'error', 'message': 'Kullanıcı odada değil.'}), 400
                
        elif current_time_str >= reservation.end_time:
            return jsonify({'status': 'error', 'message': 'Rezervasyon zaten sona ermiş.'}), 400
        else:
            return jsonify({'status': 'error', 'message': 'Rezervasyon henüz başlamamış.'}), 400
            
    # --- Try Entry QR ---
    res_id, entry_user_id = verify_qr_token(token)
    if not res_id or not entry_user_id:
        return jsonify({'status': 'error', 'message': 'Geçersiz veya süresi dolmuş QR kod.'}), 400
        
    reservation = Reservation.query.get(res_id)
    user = User.query.get(entry_user_id)
    if not reservation or not user:
        return jsonify({'status': 'error', 'message': 'Rezervasyon bulunamadı.'}), 404
        
    from app.models import get_turkey_time
    now = get_turkey_time()
    today_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M')
    
    if reservation.date != today_str:
        return jsonify({'status': 'error', 'message': f'Bu QR kod {reservation.date} tarihi için geçerlidir.'}), 403
    if not (reservation.start_time <= time_str <= reservation.end_time):
        return jsonify({'status': 'error', 'message': f'Bu QR kod sadece {reservation.start_time}-{reservation.end_time} saatleri arasında geçerlidir.'}), 403
        
    reservation.checked_in = True
    if user not in reservation.active_users:
        reservation.active_users.append(user)
    db.session.commit()
        
    return jsonify({'status': 'success', 'message': f'Kapı açıldı. {reservation.room.name} odasına hoş geldiniz, {user.username}!'})


@bp.route('/door-scanner')
@login_required
def door_scanner():
    from app.utils import generate_qr_token, generate_exit_qr_token
    # Gather reservations for manual testing
    my_res = Reservation.query.filter_by(user_id=current_user.id).all()
    invited_res = current_user.invited_reservations
    
    all_res = list(my_res) + list(invited_res)
    
    test_options = []
    for r in all_res:
        test_options.append({
            'name': f"[Giriş] {r.room.name} ({r.date} {r.start_time}-{r.end_time})",
            'token': generate_qr_token(r.id, current_user.id)
        })
        test_options.append({
            'name': f"[Çıkış] {r.room.name} ({r.date} {r.start_time}-{r.end_time})",
            'token': generate_exit_qr_token(r.id, current_user.id)
        })
        
    return render_template('door_scanner.html', title='Sanal Kapı Okuyucu', test_options=test_options)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/reservation/<int:res_id>/upload_document', methods=['POST'])
@login_required
def upload_document(res_id):
    reservation = Reservation.query.get_or_404(res_id)
    
    # Only creator or attendee can upload
    if current_user.id != reservation.user_id and current_user not in reservation.attendees:
        flash("Bu toplantıya belge yükleme yetkiniz yok.", "danger")
        return redirect(url_for('main.dashboard'))
        
    if 'document' not in request.files:
        flash("Dosya seçilmedi.", "danger")
        return redirect(url_for('main.dashboard'))
        
    file = request.files['document']
    if file.filename == '':
        flash("Dosya seçilmedi.", "danger")
        return redirect(url_for('main.dashboard'))
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Create a unique filename to prevent overwriting
        import uuid
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        
        # Ensure directory exists
        upload_folder = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder, exist_ok=True)
            
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        doc = Document(filename=filename, file_path=unique_filename, reservation_id=res_id, user_id=current_user.id)
        db.session.add(doc)
        db.session.commit()
        
        flash("Belge başarıyla yüklendi.", "success")
    else:
        flash("İzin verilmeyen dosya türü.", "danger")
        
    return redirect(url_for('main.dashboard'))

@bp.route('/document/<int:doc_id>/download')
@login_required
def download_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    reservation = doc.reservation
    
    # Only creator or attendee can download
    if current_user.id != reservation.user_id and current_user not in reservation.attendees:
        flash("Bu belgeyi indirme yetkiniz yok.", "danger")
        return redirect(url_for('main.dashboard'))
        
    upload_folder = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_folder, doc.file_path, as_attachment=True, download_name=doc.filename)

@bp.route('/document/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    reservation = doc.reservation
    
    # Only uploader or reservation creator or admin can delete
    if current_user.id != doc.user_id and current_user.id != reservation.user_id and not current_user.is_admin:
        flash("Bu belgeyi silme yetkiniz yok.", "danger")
        return redirect(url_for('main.dashboard'))
        
    # Delete from file system
    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(upload_folder, doc.file_path)
    if os.path.exists(file_path):
        os.remove(file_path)
        
    # Delete from db
    db.session.delete(doc)
    db.session.commit()
    
    flash("Belge silindi.", "success")
    return redirect(url_for('main.dashboard'))

@bp.route('/api/push/vapid_public_key')
def vapid_public_key():
    return jsonify({'publicKey': current_app.config.get('VAPID_PUBLIC_KEY')})

@bp.route('/api/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    subscription_info = request.get_json()
    if not subscription_info:
        return jsonify({'status': 'error', 'message': 'Invalid subscription info'}), 400
        
    from app.models import PushSubscription
    import json
    
    endpoint = subscription_info.get('endpoint')
    if endpoint:
        # Eski hesap çıkış yapmadan aynı tarayıcıda yeni hesaba girilirse
        # eski hesaba giden bildirimleri engellemek için, 
        # bu tarayıcının endpoint'ine sahip TÜM eski abonelikleri siliyoruz.
        subs = PushSubscription.query.filter(PushSubscription.subscription_json.like(f"%{endpoint}%")).all()
        for s in subs:
            db.session.delete(s)
            
    sub_str = json.dumps(subscription_info)
    sub = PushSubscription(user_id=current_user.id, subscription_json=sub_str)
    db.session.add(sub)
    db.session.commit()
        
    return jsonify({'status': 'success', 'message': 'Subscribed to push notifications'})
