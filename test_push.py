from app import create_app
from app.extensions import db
from app.models import PushSubscription, User
import json
from pywebpush import webpush, WebPushException

app = create_app()

with app.app_context():
    subscriptions = PushSubscription.query.all()
    if not subscriptions:
        print("Veritabanında hiç bildirim aboneliği bulunamadı. Lütfen önce tarayıcıdan giriş yapıp izin verin.")
    else:
        print(f"{len(subscriptions)} abonelik bulundu. Test bildirimi gönderiliyor...")
        for sub in subscriptions:
            user = User.query.get(sub.user_id)
            try:
                subscription_info = json.loads(sub.subscription_json)
                webpush(
                    subscription_info=subscription_info,
                    data=json.dumps({
                        "title": "Test Bildirimi", 
                        "body": f"Merhaba {user.username}, bildirim sisteminiz başarıyla çalışıyor!", 
                        "url": "/dashboard"
                    }),
                    vapid_private_key=app.config.get('VAPID_PRIVATE_KEY'),
                    vapid_claims={"sub": app.config.get('VAPID_CLAIM_EMAIL', 'mailto:admin@example.com')}
                )
                print(f"-> {user.username} kullanıcısına bildirim gönderildi.")
            except WebPushException as ex:
                print(f"Hata ({user.username}):", repr(ex))
            except Exception as e:
                print("Genel Hata:", repr(e))
