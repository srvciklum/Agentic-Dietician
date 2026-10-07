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

def build_meal_logs_table():
    print("Connecting to SQL Server to add 'meal_logs' table...")
    conn = get_sql_connection()
    cursor = conn.cursor()

    # Drop the table if you need to run this script multiple times
    cursor.execute("IF OBJECT_ID('meal_logs', 'U') IS NOT NULL DROP TABLE meal_logs")

    print("Creating the 'meal_logs' table...")
    cursor.execute('''
    CREATE TABLE meal_logs (
        log_id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT FOREIGN KEY REFERENCES users(user_id),
        food_name NVARCHAR(100),
        calories FLOAT,
        protein FLOAT,
        carbs FLOAT,
        fat FLOAT,
        log_time DATETIME DEFAULT GETDATE()
    )
    ''')

    print("Table created successfully! Ready to store user meals.\n")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    build_meal_logs_table()