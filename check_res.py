import sys
sys.path.append('.')
from app import create_app
from app.models import Reservation
app = create_app()
with app.app_context():
    for r in Reservation.query.all():
        print(f"ID: {r.id}, Date: {r.date}, Start: {r.start_time}, End: {r.end_time}, Room: {r.room.name}")
