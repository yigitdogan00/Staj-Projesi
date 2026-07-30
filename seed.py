from app import create_app
from app.extensions import db, bcrypt
from app.models import User, Room

app = create_app()

def seed_data():
    with app.app_context():
        # Create all tables
        db.create_all()

        # Create Admin User
        admin_email = "admin@sirket.com"
        admin = User.query.filter_by(email=admin_email).first()
        if not admin:
            hashed_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
            admin = User(username='Admin', email=admin_email, password_hash=hashed_password, is_admin=True, is_verified=True)
            db.session.add(admin)
            print("Admin user created.")

        # Create Test User
        test_email = "test@sirket.com"
        test_user = User.query.filter_by(email=test_email).first()
        if not test_user:
            hashed_password = bcrypt.generate_password_hash('test1234').decode('utf-8')
            test_user = User(username='TestUser', email=test_email, password_hash=hashed_password, is_admin=False, is_verified=True)
            db.session.add(test_user)
            print("Test user created (test@sirket.com / test1234)")

        # Create 5 distinct meeting rooms
        rooms_data = [
            {"name": "İnovasyon", "capacity": 12, "description": "TV, Klima, Kablosuz Yansıtma Özelliği, Beyaz Tahta ve Video Konferans Sistemi."},
            {"name": "Sinerji", "capacity": 12, "description": "TV, Klima, HDMI Yansıtma, Toplantı Masası ve Ergonomik Koltuklar."},
            {"name": "Vizyon", "capacity": 12, "description": "Akıllı Tahta, Klima, Projeksiyon ile Yansıtma Özelliği ve Apple TV."},
            {"name": "Strateji", "capacity": 12, "description": "Çift TV Ekranı, Klima, Yansıtma Özelliği ve Ses Yalıtımı."},
            {"name": "Dinamik", "capacity": 12, "description": "Geniş Ekran TV, Klima, Yansıtma Özelliği ve Dinlenme Alanı."}
        ]

        for r_data in rooms_data:
            room = Room.query.filter_by(name=r_data["name"]).first()
            if not room:
                new_room = Room(name=r_data["name"], capacity=r_data["capacity"], description=r_data["description"])
                db.session.add(new_room)
                print(f"Room '{new_room.name}' created.")

        db.session.commit()
        print("Database seeding completed.")

if __name__ == '__main__':
    seed_data()
