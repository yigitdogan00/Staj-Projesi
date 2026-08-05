from app.extensions import db
from app.models import Reservation, Notification, AuditLog, get_turkey_time
from datetime import timedelta

def check_upcoming_reservations(app):
    with app.app_context():
        now = get_turkey_time()
        target_date = now.date() + timedelta(days=2)
        target_date_str = target_date.strftime('%Y-%m-%d')
        
        reservations = Reservation.query.filter_by(date=target_date_str).all()
        
        for res in reservations:
            message = f"Hatırlatma: '{res.room.name}' odasında 2 gün sonra ({res.date}) saat {res.start_time}-{res.end_time} arasında yaklaşan bir toplantınız var."
            
            # Creator
            notif = Notification(user_id=res.user_id, type='info', message=message)
            db.session.add(notif)
            
            # Attendees
            for attendee in res.attendees:
                # Avoid duplicate if creator is somehow in attendees
                if attendee.id != res.user_id:
                    notif = Notification(user_id=attendee.id, type='info', message=message)
                    db.session.add(notif)
        
        db.session.commit()
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Checked upcoming reservations for {target_date_str}. Sent reminders for {len(reservations)} reservations.")

import json
from pywebpush import webpush, WebPushException

def check_short_term_reminders(app):
    with app.app_context():
        now = get_turkey_time()
        
        # Check for 30 minutes before
        target_time_30 = now + timedelta(minutes=30)
        target_time_30 = target_time_30.replace(second=0, microsecond=0)
        date_30_str = target_time_30.strftime('%Y-%m-%d')
        hour_30_str = target_time_30.strftime('%H:%M')

        # Check for 60 minutes before
        target_time_60 = now + timedelta(minutes=60)
        target_time_60 = target_time_60.replace(second=0, microsecond=0)
        date_60_str = target_time_60.strftime('%Y-%m-%d')
        hour_60_str = target_time_60.strftime('%H:%M')
        
        # Check for 1 minute before
        target_time_1 = now + timedelta(minutes=1)
        target_time_1 = target_time_1.replace(second=0, microsecond=0)
        date_1_str = target_time_1.strftime('%Y-%m-%d')
        hour_1_str = target_time_1.strftime('%H:%M')
        
        def notify_users(res, title, body):
            users_to_notify = [res.user_id] + [a.id for a in res.attendees if a.id != res.user_id]
            for uid in users_to_notify:
                notif = Notification(user_id=uid, type='info', message=body)
                db.session.add(notif)
                    
            send_push_to_reservation_users(app, res, title, body)
            
        # --- Process 60 min reminders ---
        res_60 = Reservation.query.filter_by(date=date_60_str, start_time=hour_60_str).all()
        for res in res_60:
            title = f"Toplantıya Son 1 Saat: {res.room.name}"
            body = f"1 saat sonra ({res.start_time}) '{res.room.name}' odasında toplantınız var."
            notify_users(res, title, body)
            
        # --- Process 30 min reminders ---
        res_30 = Reservation.query.filter_by(date=date_30_str, start_time=hour_30_str).all()
        for res in res_30:
            title = f"Toplantı Yaklaşıyor: {res.room.name}"
            body = f"Yarım saat sonra ({res.start_time}) '{res.room.name}' odasında toplantınız var."
            notify_users(res, title, body)
            
        # Check for 10 minutes before
        target_time_10 = now + timedelta(minutes=10)
        target_time_10 = target_time_10.replace(second=0, microsecond=0)
        date_10_str = target_time_10.strftime('%Y-%m-%d')
        hour_10_str = target_time_10.strftime('%H:%M')
            
        # --- Process 10 min reminders ---
        res_10 = Reservation.query.filter_by(date=date_10_str, start_time=hour_10_str).all()
        for res in res_10:
            title = f"Toplantı Başlamak Üzere: {res.room.name}"
            body = f"10 dakika sonra ({res.start_time}) '{res.room.name}' odasında toplantınız var. Lütfen hazırlıklarınızı tamamlayın."
            notify_users(res, title, body)

        # --- Process 1 min reminders ---
        res_1 = Reservation.query.filter_by(date=date_1_str, start_time=hour_1_str).all()
        for res in res_1:
            title = f"Toplantı Başlıyor!"
            body = f"'{res.room.name}' odasındaki toplantınız 1 dakika içinde başlıyor. Lütfen odaya geçin."
            notify_users(res, title, body)
            
        db.session.commit()
        if res_30 or res_60 or res_1:
            print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Sent reminders: {len(res_60)} (60min), {len(res_30)} (30min), {len(res_1)} (1min).")

def send_push_to_reservation_users(app, res, title, body):
    from app.models import PushSubscription
    users_to_notify = [res.user_id] + [a.id for a in res.attendees if a.id != res.user_id]
    subscriptions = PushSubscription.query.filter(PushSubscription.user_id.in_(users_to_notify)).all()
    
    for sub in subscriptions:
        try:
            subscription_info = json.loads(sub.subscription_json)
            webpush(
                subscription_info=subscription_info,
                data=json.dumps({"title": title, "body": body, "url": "/dashboard"}),
                vapid_private_key=app.config.get('VAPID_PRIVATE_KEY'),
                vapid_claims={"sub": app.config.get('VAPID_CLAIM_EMAIL', 'mailto:admin@example.com')}
            )
        except WebPushException as ex:
            print("WebPushException:", repr(ex))
            if ex.response and ex.response.status_code in [404, 410]:
                db.session.delete(sub)
        except Exception as e:
            print("Push Notification Error:", repr(e))

def cleanup_old_audit_logs(app, days=365):
    with app.app_context():
        now = get_turkey_time()
        cutoff_date = now - timedelta(days=days)
        deleted_count = AuditLog.query.filter(AuditLog.timestamp < cutoff_date).delete()
        db.session.commit()
        app.logger.info(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Cleaned up {deleted_count} audit logs older than {days} days (before {cutoff_date}).")

