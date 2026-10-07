"""
Database Migration Script: Flexible Nutrient Tracking System

This script creates the new normalized schema for flexible nutrient tracking:
1. Creates 'nutrients' master table
2. Creates 'user_nutrient_preferences' table
3. Creates 'meal_log_nutrients' table
4. Optionally migrates existing data from old schema

IMPORTANT: Run this AFTER reviewing the design document!
"""

import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

def get_sql_connection():
    """Establishes connection to SQL Server."""
    server = os.getenv("SQL_SERVER_NAME")
    database = os.getenv("SQL_DATABASE_NAME")
    username = os.getenv("SQL_USERNAME")
    password = os.getenv("SQL_PASSWORD")
    
    driver = "{ODBC Driver 17 for SQL Server}"
    
    print(f"Connecting to {server}/{database}...")
    if username and password:
        conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};"
    else:
        conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
    
    try:
        return pyodbc.connect(conn_str)
    except Exception as e:
        print(f"CRITICAL: Could not connect to SQL Server: {e}")
        return None

def create_nutrients_table():
    """Creates the nutrients master table and populates with initial data."""
    conn = get_sql_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    print("\n=== Step 1: Creating 'nutrients' master table ===")
    
    # Drop if exists (for testing/re-running)
    cursor.execute("IF OBJECT_ID('nutrients', 'U') IS NOT NULL DROP TABLE nutrients")
    
    # Create table
    cursor.execute('''
        CREATE TABLE nutrients (
            nutrient_id INT IDENTITY(1,1) PRIMARY KEY,
            nutrient_name NVARCHAR(50) UNIQUE NOT NULL,
            display_name NVARCHAR(100) NOT NULL,
            unit NVARCHAR(20) NOT NULL,
            is_default BIT DEFAULT 0
        )
    ''')
    
    print("✓ Table 'nutrients' created successfully")
    
    # Populate with initial nutrients
    print("\nPopulating nutrients table with initial data...")
    
    initial_nutrients = [
        # Default nutrients (is_default = 1)
        ('calories', 'Calories', 'kcal', 1),
        ('protein', 'Protein', 'g', 1),
        ('carbs', 'Carbohydrates', 'g', 1),
        ('fat', 'Fat', 'g', 1),
        
        # Additional common nutrients
        ('fiber', 'Fiber', 'g', 0),
        ('sugar', 'Sugar', 'g', 0),
        ('sodium', 'Sodium', 'mg', 0),
        ('potassium', 'Potassium', 'mg', 0),
        ('calcium', 'Calcium', 'mg', 0),
        ('iron', 'Iron', 'mg', 0),
        ('magnesium', 'Magnesium', 'mg', 0),
        ('phosphorus', 'Phosphorus', 'mg', 0),
        ('zinc', 'Zinc', 'mg', 0),
        ('vitamin_a', 'Vitamin A', 'mcg', 0),
        ('vitamin_c', 'Vitamin C', 'mg', 0),
        ('vitamin_d', 'Vitamin D', 'mcg', 0),
        ('vitamin_e', 'Vitamin E', 'mg', 0),
        ('vitamin_k', 'Vitamin K', 'mcg', 0),
        ('thiamin', 'Thiamin (B1)', 'mg', 0),
        ('riboflavin', 'Riboflavin (B2)', 'mg', 0),
        ('niacin', 'Niacin (B3)', 'mg', 0),
        ('vitamin_b6', 'Vitamin B6', 'mg', 0),
        ('folate', 'Folate', 'mcg', 0),
        ('vitamin_b12', 'Vitamin B12', 'mcg', 0),
        ('cholesterol', 'Cholesterol', 'mg', 0),
        ('saturated_fat', 'Saturated Fat', 'g', 0),
        ('trans_fat', 'Trans Fat', 'g', 0),
        ('monounsaturated_fat', 'Monounsaturated Fat', 'g', 0),
        ('polyunsaturated_fat', 'Polyunsaturated Fat', 'g', 0),
    ]
    
    cursor.executemany('''
        INSERT INTO nutrients (nutrient_name, display_name, unit, is_default)
        VALUES (?, ?, ?, ?)
    ''', initial_nutrients)
    
    print(f"✓ Inserted {len(initial_nutrients)} nutrients")
    
    conn.commit()
    conn.close()
    return True

def create_user_nutrient_preferences_table():
    """Creates the user_nutrient_preferences table."""
    conn = get_sql_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    print("\n=== Step 2: Creating 'user_nutrient_preferences' table ===")
    
    # Drop if exists
    cursor.execute("IF OBJECT_ID('user_nutrient_preferences', 'U') IS NOT NULL DROP TABLE user_nutrient_preferences")
    
    # Create table
    cursor.execute('''
        CREATE TABLE user_nutrient_preferences (
            preference_id INT IDENTITY(1,1) PRIMARY KEY,
            user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id) ON DELETE CASCADE,
            nutrient_id INT NOT NULL FOREIGN KEY REFERENCES nutrients(nutrient_id) ON DELETE CASCADE,
            daily_limit FLOAT NOT NULL,
            is_active BIT DEFAULT 1,
            created_at DATETIME DEFAULT GETDATE(),
            UNIQUE(user_id, nutrient_id)
        )
    ''')
    
    print("✓ Table 'user_nutrient_preferences' created successfully")
    
    conn.commit()
    conn.close()
    return True

def create_meal_log_nutrients_table():
    """Creates the meal_log_nutrients table."""
    conn = get_sql_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    print("\n=== Step 3: Creating 'meal_log_nutrients' table ===")
    
    # Drop if exists
    cursor.execute("IF OBJECT_ID('meal_log_nutrients', 'U') IS NOT NULL DROP TABLE meal_log_nutrients")
    
    # Create table
    cursor.execute('''
        CREATE TABLE meal_log_nutrients (
            log_nutrient_id INT IDENTITY(1,1) PRIMARY KEY,
            log_id INT NOT NULL FOREIGN KEY REFERENCES meal_logs(log_id) ON DELETE CASCADE,
            nutrient_id INT NOT NULL FOREIGN KEY REFERENCES nutrients(nutrient_id) ON DELETE CASCADE,
            value FLOAT NOT NULL,
            UNIQUE(log_id, nutrient_id)
        )
    ''')
    
    print("✓ Table 'meal_log_nutrients' created successfully")
    
    # Create indexes for performance
    print("Creating indexes...")
    cursor.execute('''
        CREATE INDEX idx_meal_log_nutrients_log_id ON meal_log_nutrients(log_id)
    ''')
    cursor.execute('''
        CREATE INDEX idx_meal_log_nutrients_nutrient_id ON meal_log_nutrients(nutrient_id)
    ''')
    print("✓ Indexes created")
    
    conn.commit()
    conn.close()
    return True

def migrate_existing_user_limits():
    """Migrates existing user limits from 'users' table to 'user_nutrient_preferences'."""
    conn = get_sql_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    print("\n=== Step 4: Migrating existing user limits ===")
    
    # Check if old columns exist
    try:
        cursor.execute('''
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'users' 
            AND COLUMN_NAME IN ('limit_calories', 'limit_protein', 'limit_carbs', 'limit_fat')
        ''')
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        if not existing_columns:
            print("⚠ No old limit columns found. Skipping migration.")
            conn.close()
            return True
        
        print(f"Found old columns: {existing_columns}")
        
        # Get nutrient IDs
        nutrient_map = {}
        for nutrient_name in ['calories', 'protein', 'carbs', 'fat']:
            cursor.execute('SELECT nutrient_id FROM nutrients WHERE nutrient_name = ?', (nutrient_name,))
            row = cursor.fetchone()
            if row:
                nutrient_map[nutrient_name] = row[0]
        
        # Migrate data
        migration_map = {
            'limit_calories': 'calories',
            'limit_protein': 'protein',
            'limit_carbs': 'carbs',
            'limit_fat': 'fat'
        }
        
        migrated_count = 0
        cursor.execute('SELECT user_id, limit_calories, limit_protein, limit_carbs, limit_fat FROM users')
        users = cursor.fetchall()
        
        for user_row in users:
            user_id = user_row[0]
            for old_col, nutrient_name in migration_map.items():
                limit_value = getattr(user_row, old_col.replace('limit_', ''), None)
                if limit_value is not None and nutrient_name in nutrient_map:
                    try:
                        cursor.execute('''
                            INSERT INTO user_nutrient_preferences (user_id, nutrient_id, daily_limit)
                            VALUES (?, ?, ?)
                        ''', (user_id, nutrient_map[nutrient_name], limit_value))
                        migrated_count += 1
                    except pyodbc.IntegrityError:
                        # Already exists, skip
                        pass
        
        conn.commit()
        print(f"✓ Migrated {migrated_count} user nutrient preferences")
        
    except Exception as e:
        print(f"⚠ Migration error (this is OK if columns don't exist): {e}")
    
    conn.close()
    return True

def migrate_existing_meal_logs():
    """Migrates existing meal log nutrient data to 'meal_log_nutrients' table."""
    conn = get_sql_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    print("\n=== Step 5: Migrating existing meal log data ===")
    
    # Check if old columns exist
    try:
        cursor.execute('''
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'meal_logs' 
            AND COLUMN_NAME IN ('calories', 'protein', 'carbs', 'fat')
        ''')
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        if not existing_columns:
            print("⚠ No old nutrient columns found. Skipping migration.")
            conn.close()
            return True
        
        print(f"Found old columns: {existing_columns}")
        
        # Get nutrient IDs
        nutrient_map = {}
        for nutrient_name in ['calories', 'protein', 'carbs', 'fat']:
            cursor.execute('SELECT nutrient_id FROM nutrients WHERE nutrient_name = ?', (nutrient_name,))
            row = cursor.fetchone()
            if row:
                nutrient_map[nutrient_name] = row[0]
        
        # Migrate data
        migrated_count = 0
        cursor.execute('SELECT log_id, calories, protein, carbs, fat FROM meal_logs')
        meal_logs = cursor.fetchall()
        
        for log_row in meal_logs:
            log_id = log_row[0]
            for nutrient_name, nutrient_id in nutrient_map.items():
                value = getattr(log_row, nutrient_name, None)
                if value is not None:
                    try:
                        cursor.execute('''
                            INSERT INTO meal_log_nutrients (log_id, nutrient_id, value)
                            VALUES (?, ?, ?)
                        ''', (log_id, nutrient_id, value))
                        migrated_count += 1
                    except pyodbc.IntegrityError:
                        # Already exists, skip
                        pass
        
        conn.commit()
        print(f"✓ Migrated {migrated_count} meal log nutrient entries")
        
    except Exception as e:
        print(f"⚠ Migration error (this is OK if columns don't exist): {e}")
    
    conn.close()
    return True

def setup_flexible_nutrients_schema(migrate_data=True):
    """Main function to set up the flexible nutrient tracking schema."""
    print("=" * 60)
    print("FLEXIBLE NUTRIENT TRACKING - DATABASE SETUP")
    print("=" * 60)
    
    success = True
    
    # Step 1: Create nutrients table
    if not create_nutrients_table():
        print("❌ Failed to create nutrients table")
        success = False
        return success
    
    # Step 2: Create user_nutrient_preferences table
    if not create_user_nutrient_preferences_table():
        print("❌ Failed to create user_nutrient_preferences table")
        success = False
        return success
    
    # Step 3: Create meal_log_nutrients table
    if not create_meal_log_nutrients_table():
        print("❌ Failed to create meal_log_nutrients table")
        success = False
        return success
    
    # Step 4 & 5: Migrate existing data (optional)
    if migrate_data:
        migrate_existing_user_limits()
        migrate_existing_meal_logs()
    
    print("\n" + "=" * 60)
    print("✓ FLEXIBLE NUTRIENT TRACKING SCHEMA SETUP COMPLETE!")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. Review the new tables in SQL Server Management Studio")
    print("2. Update your agent code to use the new schema")
    print("3. Test with sample data")
    print("4. After confirming everything works, you can remove old columns:")
    print("   - ALTER TABLE users DROP COLUMN limit_calories, limit_protein, limit_carbs, limit_fat")
    print("   - ALTER TABLE meal_logs DROP COLUMN calories, protein, carbs, fat")
    print("\n⚠ IMPORTANT: Only remove old columns after confirming new code works!")
    
    return success

if __name__ == "__main__":
    # Ask user if they want to migrate existing data
    migrate_choice = input("\nDo you want to migrate existing data from old schema? (y/n): ").strip().lower()
    migrate_data = migrate_choice == 'y'
    
    setup_flexible_nutrients_schema(migrate_data=migrate_data)
