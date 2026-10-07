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


def build_normalized_database():
    print("Connecting to SQL Server to build Normalized Schema...")
    conn = get_sql_connection()
    cursor = conn.cursor()

    # Drop old tables if they exist to start fresh
    cursor.execute("IF OBJECT_ID('user_allergies', 'U') IS NOT NULL DROP TABLE user_allergies")
    cursor.execute("IF OBJECT_ID('user_conditions', 'U') IS NOT NULL DROP TABLE user_conditions")
    



    print("Creating the 'user_allergies' table (One-to-Many)...")
    cursor.execute('''
    CREATE TABLE user_allergies (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT FOREIGN KEY REFERENCES users(user_id),
        allergy_name NVARCHAR(50)
    )
    ''')

    print("Creating the 'user_conditions' table (One-to-Many)...")
    cursor.execute('''
    CREATE TABLE user_conditions (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT FOREIGN KEY REFERENCES users(user_id),
        condition_name NVARCHAR(50)
    )
    ''')

    # --- SEEDING THE DATA ---

    # Insert MULTIPLE allergies on separate rows!
    cursor.execute("INSERT INTO user_allergies (user_id, allergy_name) VALUES (1, 'dairy')")
    cursor.execute("INSERT INTO user_allergies (user_id, allergy_name) VALUES (1, 'peanuts')")
    cursor.execute("INSERT INTO user_allergies (user_id, allergy_name) VALUES (1, 'shellfish')")
    cursor.execute("INSERT INTO user_allergies (user_id, allergy_name) VALUES (2, 'gluten')")
    cursor.execute("INSERT INTO user_allergies (user_id, allergy_name) VALUES (2, 'tree nuts')")

    # Insert MULTIPLE medical conditions on separate rows!
    cursor.execute("INSERT INTO user_conditions (user_id, condition_name) VALUES (1, 'diabetes')")
    cursor.execute("INSERT INTO user_conditions (user_id, condition_name) VALUES (1, 'hypertension')")
    cursor.execute("INSERT INTO user_conditions (user_id, condition_name) VALUES (2, 'kidney disease')")
    cursor.execute("INSERT INTO user_conditions (user_id, condition_name) VALUES (2, 'hypertension')")

    print("Database Normalization Complete!\n")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    build_normalized_database()