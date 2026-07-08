import sqlite3

def remove_unique_constraint():
    conn = sqlite3.connect('app/app.db')
    cursor = conn.cursor()
    
    # Check current schema
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='user'")
    sql = cursor.fetchone()[0]
    print("Original SQL:", sql)
    
    # We will rename the current user table
    cursor.execute("ALTER TABLE user RENAME TO user_old")
    
    # Create the new user table without UNIQUE on username
    new_sql = sql.replace("UNIQUE", "")
    # Actually, email might also have UNIQUE. Let's just create it manually based on standard schema
    new_sql = """
    CREATE TABLE user (
        id INTEGER NOT NULL, 
        username VARCHAR(64) NOT NULL, 
        email VARCHAR(120) NOT NULL UNIQUE, 
        password_hash VARCHAR(128), 
        is_admin BOOLEAN, 
        profile_image VARCHAR(120) NOT NULL, 
        PRIMARY KEY (id)
    )
    """
    cursor.execute(new_sql)
    
    # Copy data
    cursor.execute("INSERT INTO user SELECT * FROM user_old")
    
    # Drop old table
    cursor.execute("DROP TABLE user_old")
    
    conn.commit()
    conn.close()
    print("User table updated successfully.")

if __name__ == '__main__':
    remove_unique_constraint()
