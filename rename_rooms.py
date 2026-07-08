from app import create_app
from app.extensions import db
from app.models import Room

app = create_app()

with app.app_context():
    vizyon = Room.query.filter_by(name='Vizyon').first()
    if vizyon:
        vizyon.name = 'Yeşil Enerji'
    
    dinamik = Room.query.filter_by(name='Dinamik').first()
    if dinamik:
        dinamik.name = 'Sarı Enerji'
        
    db.session.commit()
    print("Rooms renamed successfully.")
