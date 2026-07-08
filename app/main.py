import os
import secrets
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import Room, Reservation, User, AuditLog, Notification, Document
from app.extensions import db
from datetime import datetime, date
from app.utils import admin_required, send_booking_email, log_action, send_invitation_email
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
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        log_action(current_user.id, "PROFİL_GÜNCELLEME", f"{current_user.username} profilini güncelledi.")
        flash('Hesabınız başarıyla güncellendi!', 'success')
        return redirect(url_for('main.profile'))
    elif request.method == 'GET':
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
                notif.message = gettext("Geçmiş (veya iptal edilmiş) bir toplantı davetiniz vardı.")
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
                    
    return dict(trans=gettext, current_lang=lang, unread_notifications=unread_notifications, active_meeting=active_meeting, upcoming_accepted_meetings=upcoming_accepted_meetings, starting_soon_meeting=starting_soon_meeting, today_meetings_list=today_meetings_list if current_user.is_authenticated else [])

@bp.route('/lang/<lang_code>')
def change_language(lang_code):
    if lang_code in ['tr', 'en']:
        session['lang'] = lang_code
    return redirect(request.referrer or url_for('main.index'))

import re
@bp.route('/api/ai/command', methods=['POST'])
@login_required
def ai_command():
    data = request.get_json()
    command_text = data.get('command', '').lower()
    
    def normalize(t):
        return t.lower().replace('ı','i').replace('ş','s').replace('ç','c').replace('ğ','g').replace('ö','o').replace('ü','u')
        
    norm_cmd = normalize(command_text)
    
    # 1. Parse Date
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
            return jsonify({'success': False, 'message': 'Lütfen tarih formatını doğru girin (örn: 02.07.2026)'})
            
    # 2. Find Room
    rooms = Room.query.all()
    found_room = None
    for r in rooms:
        if normalize(r.name) in norm_cmd:
            found_room = r
            break
            
    if not found_room:
        return jsonify({'success': False, 'message': 'Sistemde böyle bir oda bulunamadı. Lütfen oda adını kontrol edin (örn: Sarı Enerji)'})
        
    def time_to_minutes(t_str):
        h, m = map(int, t_str.split(':'))
        return h * 60 + m
        
    # 3. Check Existing Reservations
    existing = Reservation.query.filter_by(room_id=found_room.id, date=date_str).all()
    
    # 4. Parse Time OR Auto-pick
    time_match = re.search(r'(\d{1,2})[.:](\d{2})\s*-\s*(\d{1,2})[.:](\d{2})', command_text)
    start_time = None
    end_time = None
    
    if time_match:
        sh, sm, eh, em = time_match.groups()
        start_time = f"{sh.zfill(2)}:{sm}"
        end_time = f"{eh.zfill(2)}:{em}"
        
        req_start = time_to_minutes(start_time)
        req_end = time_to_minutes(end_time)
        
        if req_start >= req_end:
            return jsonify({'success': False, 'message': 'Bitiş saati başlangıç saatinden önce olamaz.'})
            
        for res in existing:
            res_s = time_to_minutes(res.start_time)
            res_e = time_to_minutes(res.end_time)
            if not (req_end <= res_s or req_start >= res_e):
                return jsonify({'success': False, 'message': f'{found_room.name} odası bu saatlerde maalesef dolu.'})
    else:
        # Auto-pick first available 60 min slot
        from app.models import get_turkey_time
        now = get_turkey_time()
        today_str = now.strftime('%Y-%m-%d')
        current_mins = now.hour * 60 + now.minute if date_str == today_str else 0
        
        possible_starts = [f"{h:02d}:00" for h in range(9, 18)]
        found_slot = False
        
        for p_start in possible_starts:
            req_start = time_to_minutes(p_start)
            req_end = req_start + 60
            
            # Geçmiş saatleri atla
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
                start_time = p_start
                end_time = f"{req_end // 60:02d}:00"
                found_slot = True
                break
                
        if not found_slot:
            return jsonify({'success': False, 'message': f'{date_str} tarihinde {found_room.name} odasında uygun 1 saatlik boşluk bulunamadı.'})
            
    # 5. Create Reservation
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
        return jsonify({'success': True, 'message': f'Harika! {found_room.name} odası {date_str} tarihinde {start_time}-{end_time} arası sizin için rezerve edildi.'})
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
    
    rooms = Room.query.all()
    now = get_turkey_time()
    today_str = now.strftime('%Y-%m-%d')
    current_minutes_since_midnight = now.hour * 60 + now.minute
    
    possible_slots = []
    for h in range(9, 18):
        possible_slots.extend([f"{h:02d}:00", f"{h:02d}:30"])
    
    room_stats = []
    for r in rooms:
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
            label = 'Dolu'
            color = '#ef4444' # Red
        elif available_slots == 18:
            status = 'empty'
            label = 'Boş'
            color = '#10b981' # Green
        elif available_slots < 6:
            status = 'partial'
            label = 'Çoğunluğu Dolu'
            color = '#f59e0b' # Yellow
        else:
            status = 'partial'
            label = 'Kısmen Dolu'
            color = '#f59e0b' # Yellow
            
        room_stats.append({
            'room': r,
            'status': status,
            'label': label,
            'color': color,
            'booked_minutes': actual_booked_minutes
        })
        
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
            capacity=form.capacity.data,
            description=form.description.data
        )
        db.session.add(new_room)
        db.session.commit()
        log_action(current_user.id, "ODA_EKLENDİ", f"{form.name.data} odası eklendi.")
        flash(gettext('Yeni oda başarıyla eklendi!'), 'success')
        return redirect(url_for('main.rooms'))
    return render_template('rooms/add.html', title='Oda Ekle', form=form)

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
        
        # Send mock emails
        send_booking_email(current_user.email, current_user.username, room.name, req_date, start_time, end_time)
        
        for user in invited_users:
            send_invitation_email(current_user.username, user.email, user.username, room.name, req_date, start_time, end_time)
        
        # Log the action
        log_msg = f"{room.name} odası için {req_date} {start_time}-{end_time} rezervasyonu yapıldı."
        if invited_users:
            invited_names = ", ".join([u.username for u in invited_users])
            log_msg += f" Davetliler: {invited_names}"
        log_action(current_user.id, "REZERVASYON_OLUŞTURULDU", log_msg)
        
        flash(f"{room.name} için rezervasyonunuz onaylandı!", "success")
        return redirect(url_for('main.dashboard'))

    return render_template('rooms/book.html', room=room, title=f'{room.name} Rezervasyon', all_users=all_users, today=today, current_hour=current_hour, selected_date=selected_date, selected_time=selected_time)

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
    
    flash('Rezervasyon başarıyla iptal edildi.', 'success')
    
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
        flash('Toplantıdan başarıyla ayrıldınız.', 'success')
    else:
        flash('Bu toplantıya zaten katılmıyorsunuz.', 'danger')
        
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
            
    users = User.query.all()
    rooms = Room.query.all()
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(50).all()
    
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
        'total_users': len(users),
        'total_rooms': len(rooms),
        'total_reservations': len(all_reservations),
        'today_reservations': len(today_res)
    }
    
    return render_template('admin_panel.html', title='Admin Paneli', reservations=reservations, users=users, rooms=rooms, metrics=metrics, logs=logs, active_meetings=active_meetings)

@bp.route('/admin/logs/clear', methods=['POST'])
@admin_required
def clear_logs():
    from app.models import AuditLog
    # Sadece en son 50 kaydı sil (kullanıcının gördüğü kadarı)
    logs_to_delete = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(50).all()
    for log in logs_to_delete:
        db.session.delete(log)
    db.session.commit()
    
    log_action(current_user.id, "SİSTEM", "Sistem logları temizlendi (Son 50 kayıt).")
    flash('Son 50 sistem logu başarıyla temizlendi.', 'success')
    return redirect(url_for('main.admin_panel'))

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

@bp.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Kendinizi silemezsiniz!', 'danger')
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
