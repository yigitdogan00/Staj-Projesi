import sys
sys.path.append('.')
from app import create_app
from app.models import Reservation
from app.extensions import db
app = create_app()
with app.app_context():
    # Insert a 15:00-16:00 reservation for room 1 (Sinerji) and user 1 (Admin)
    new_res = Reservation(user_id=1, room_id=1, date="2026-07-01", start_time="15:00", end_time="16:00")
    db.session.add(new_res)
    db.session.commit()
    print("Inserted mock reservation for 15:00-16:00")
