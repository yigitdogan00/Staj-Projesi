from app import create_app
from app.extensions import db
from app.models import Reservation, get_turkey_time, Notification, Document

app = create_app()
with app.app_context():
    now = get_turkey_time()
    today_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M')
    
    # Tüm rezervasyonları çek
    all_res = Reservation.query.all()
    count = 0
    for res in all_res:
        if res.date < today_str or (res.date == today_str and res.end_time <= time_str):
            # İlgili bildirimlerin reservation_id'sini temizle (hata vermemesi için)
            Notification.query.filter_by(reservation_id=res.id).update({'reservation_id': None})
            
            # Rezervasyonu sil
            db.session.delete(res)
            count += 1
            
    db.session.commit()
    print(f"Başarıyla {count} adet eski rezervasyon veritabanından kalıcı olarak silindi.")
