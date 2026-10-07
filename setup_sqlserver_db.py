import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()
def get_sql_connection():
    # 1. Pull variables from the environment
    # Use os.getenv() so it doesn't crash if a variable is missing
    server = os.getenv("SQL_SERVER_NAME")
    database = os.getenv("SQL_DATABASE_NAME")
    username = os.getenv("SQL_USERNAME")
    password = os.getenv("SQL_PASSWORD")
    
    # Use 'ODBC Driver 17 for SQL Server' as it is the most stable for SSMS 2026
    driver = "{ODBC Driver 17 for SQL Server}" 

    # 2. Build the connection string
    # We use 'Trusted_Connection=yes' if you use Windows Auth, 
    # OR UID/PWD if you use SQL Server Auth.
    print(server, database, username, "******")  # Debug print to verify env variables (hide password)
    if username and password:
        # SQL Server Authentication
        conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};"
    else:
        # Windows Authentication (Standard for local SSMS)
        conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
    
    try:
        return pyodbc.connect(conn_str)
    except Exception as e:
        print(f"CRITICAL: Could not connect to SQL Server: {e}")
        return None

def setup_database():
    print("Connecting to SQL Server...")
    conn = get_sql_connection()
    cursor = conn.cursor()

    print("Creating Tables...")
    # Table 1: User Profiles
    cursor.execute('''
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='users' AND xtype='U')
    CREATE TABLE users (
        user_id INT PRIMARY KEY,
        username NVARCHAR(50),
        limit_calories INT,
        limit_protein FLOAT,
        limit_carbs FLOAT,
        limit_fat FLOAT
    )
    ''')


    # Table 2: Unit Conversions
    cursor.execute('''
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='unit_conversions' AND xtype='U')
    CREATE TABLE unit_conversions (
        unit_name NVARCHAR(50) PRIMARY KEY,
        gram_multiplier FLOAT
    )
    ''')

    print("Clearing old data to prevent duplicates...")
    

    cursor.execute('DELETE FROM users')
    

    cursor.execute('DELETE FROM unit_conversions')


    print("Inserting Mock User (User ID: 1)...")
    cursor.execute('''
    INSERT INTO users (user_id, username, limit_calories, limit_protein, limit_carbs, limit_fat)
    VALUES (1, 'TestUser', 2000, 150.0, 250.0, 70.0)
    ''')

    print("Inserting Mock User (User ID: 2)...")
    cursor.execute('''
    INSERT INTO users (user_id, username, limit_calories, limit_protein, limit_carbs, limit_fat)
    VALUES (2, 'TestUser2', 1800, 120.0, 200.0, 60.0)
    ''')



    print("Inserting Unit Conversions...")
    units = [
        ("g", 1), ("grams", 1), ("ml", 1), 
        ("kg", 1000), ("oz", 28.35), ("lb", 453.59),
        ("cup", 240), ("cups", 240),
        ("tbsp", 15), ("tablespoon", 15),
        ("tsp", 5), ("teaspoon", 5),
        ("slice", 120), ("slices", 120),
        ("piece", 100), ("pieces", 100),
        ("bowl", 300), ("bowls", 300),
        ("handful", 30), ("dozen", 1200)
    ]
    

    cursor.executemany('''
    INSERT INTO unit_conversions (unit_name, gram_multiplier) 
    VALUES (?, ?)
    ''', units)
    conn.commit()
    conn.close()
    print("Database Setup Complete! Data successfully seeded into SQL Server.\n")

if __name__ == "__main__":
    setup_database()