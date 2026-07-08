from app import create_app
from app.extensions import db
from app.models import Room

app = create_app()

new_rooms = [
    {"name": "İnovasyon", "capacity": 12, "description": "TV, Klima, Kablosuz Yansıtma Özelliği, Beyaz Tahta ve Video Konferans Sistemi."},
    {"name": "Sinerji", "capacity": 12, "description": "TV, Klima, HDMI Yansıtma, Toplantı Masası ve Ergonomik Koltuklar."},
    {"name": "Vizyon", "capacity": 12, "description": "Akıllı Tahta, Klima, Projeksiyon ile Yansıtma Özelliği ve Apple TV."},
    {"name": "Strateji", "capacity": 12, "description": "Çift TV Ekranı, Klima, Yansıtma Özelliği ve Ses Yalıtımı."},
    {"name": "Dinamik", "capacity": 12, "description": "Geniş Ekran TV, Klima, Yansıtma Özelliği ve Dinlenme Alanı."}
]

with app.app_context():
    rooms = Room.query.all()
    for i, room in enumerate(rooms):
        if i < len(new_rooms):
            room.name = new_rooms[i]["name"]
            room.capacity = new_rooms[i]["capacity"]
            room.description = new_rooms[i]["description"]
    db.session.commit()
    print("Mevcut odalar veritabanında güncellendi.")
