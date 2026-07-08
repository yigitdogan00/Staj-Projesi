import sqlite3
import os
basedir = os.path.abspath('app')
db_path = os.path.join(basedir, 'app.db')
print('Connecting to DB at:', db_path)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS reservation_active_attendees (
        user_id INTEGER NOT NULL,
        reservation_id INTEGER NOT NULL,
        PRIMARY KEY (user_id, reservation_id),
        FOREIGN KEY(user_id) REFERENCES user (id),
        FOREIGN KEY(reservation_id) REFERENCES reservation (id)
    )
''')
conn.commit()
print('Table created or already exists')
cursor.execute('SELECT name FROM sqlite_master WHERE type=\"table\"')
print(cursor.fetchall())
conn.close()
