"""
Utility functions for flexible nutrient tracking system.

This module provides helper functions to work with the new normalized nutrient schema.
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
    
    if username and password:
        conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};"
    else:
        conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
    
    try:
        return pyodbc.connect(conn_str)
    except Exception as e:
        print(f"CRITICAL: Could not connect to SQL Server: {e}")
        return None

def get_nutrient_id(nutrient_name):
    """Gets the nutrient_id for a given nutrient_name."""
    conn = get_sql_connection()
    if not conn:
        return None
    
    cursor = conn.cursor()
    cursor.execute('SELECT nutrient_id FROM nutrients WHERE nutrient_name = ?', (nutrient_name,))
    row = cursor.fetchone()
    conn.close()
    
    return row[0] if row else None

def get_nutrient_name(nutrient_id):
    """Gets the nutrient_name for a given nutrient_id."""
    conn = get_sql_connection()
    if not conn:
        return None
    
    cursor = conn.cursor()
    cursor.execute('SELECT nutrient_name FROM nutrients WHERE nutrient_id = ?', (nutrient_id,))
    row = cursor.fetchone()
    conn.close()
    
    return row[0] if row else None

def get_user_tracked_nutrients(user_id):
    """
    Returns a dictionary of nutrients that a user is tracking.
    
    Returns:
        {
            'calories': {'limit': 2000, 'unit': 'kcal', 'nutrient_id': 1},
            'protein': {'limit': 150, 'unit': 'g', 'nutrient_id': 2},
            ...
        }
    """
    conn = get_sql_connection()
    if not conn:
        return {}
    
    cursor = conn.cursor()
    cursor.execute('''
        SELECT n.nutrient_name, n.nutrient_id, n.unit, unp.daily_limit
        FROM user_nutrient_preferences unp
        JOIN nutrients n ON unp.nutrient_id = n.nutrient_id
        WHERE unp.user_id = ? AND unp.is_active = 1
    ''', (user_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    tracked = {}
    for row in rows:
        tracked[row[0]] = {
            'nutrient_id': row[1],
            'unit': row[2],
            'limit': row[3]
        }
    
    return tracked

def set_user_nutrient_preference(user_id, nutrient_name, daily_limit, is_active=True):
    """
    Sets or updates a user's nutrient tracking preference.
    
    Args:
        user_id: User ID
        nutrient_name: Name of the nutrient (e.g., 'calories', 'potassium')
        daily_limit: Daily limit value
        is_active: Whether this nutrient is actively tracked
    
    Returns:
        True if successful, False otherwise
    """
    conn = get_sql_connection()
    if not conn:
        return False
    
    nutrient_id = get_nutrient_id(nutrient_name)
    if not nutrient_id:
        print(f"Error: Nutrient '{nutrient_name}' not found in nutrients table")
        conn.close()
        return False
    
    cursor = conn.cursor()
    try:
        # Try to update first
        cursor.execute('''
            UPDATE user_nutrient_preferences
            SET daily_limit = ?, is_active = ?
            WHERE user_id = ? AND nutrient_id = ?
        ''', (daily_limit, is_active, user_id, nutrient_id))
        
        # If no rows updated, insert new
        if cursor.rowcount == 0:
            cursor.execute('''
                INSERT INTO user_nutrient_preferences (user_id, nutrient_id, daily_limit, is_active)
                VALUES (?, ?, ?, ?)
            ''', (user_id, nutrient_id, daily_limit, is_active))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error setting user nutrient preference: {e}")
        conn.close()
        return False

def get_today_nutrient_totals(user_id, nutrient_names=None):
    """
    Gets today's total consumed values for specified nutrients (or all tracked nutrients).
    
    Args:
        user_id: User ID
        nutrient_names: List of nutrient names to get totals for. If None, gets all tracked nutrients.
    
    Returns:
        Dictionary: {nutrient_name: total_value}
    """
    conn = get_sql_connection()
    if not conn:
        print("ERROR: Could not get database connection in get_today_nutrient_totals")
        return {}
    
    cursor = conn.cursor()
    
    try:
        if nutrient_names is None:
            # Get all tracked nutrients for this user
            tracked = get_user_tracked_nutrients(user_id)
            nutrient_names = list(tracked.keys())
        
        if not nutrient_names:
            conn.close()
            return {}
        
        # Build query with placeholders - use parameterized query properly
        placeholders = ','.join(['?' for _ in nutrient_names])
        
        # Direct query - get totals from meal_log_nutrients joined with meal_logs filtered by today
        # This ensures we only count meals from today
        params = [user_id] + nutrient_names
        cursor.execute(f'''
            SELECT n.nutrient_name, COALESCE(SUM(today_meals.nutrient_value), 0) as total
            FROM nutrients n
            LEFT JOIN (
                SELECT mln.nutrient_id, mln.value as nutrient_value
                FROM meal_log_nutrients mln
                INNER JOIN meal_logs ml ON mln.log_id = ml.log_id
                WHERE ml.user_id = ?
                  AND CAST(ml.log_time AS DATE) = CAST(GETDATE() AS DATE)
            ) as today_meals ON n.nutrient_id = today_meals.nutrient_id
            WHERE n.nutrient_name IN ({placeholders})
            GROUP BY n.nutrient_id, n.nutrient_name
        ''', params)
        
        rows = cursor.fetchall()
        
        totals = {}
        for row in rows:
            nutrient_name = row[0]
            total_value = float(row[1])
            totals[nutrient_name] = total_value
        
        # Ensure all requested nutrients are in the result (with 0 if no data)
        for nutrient_name in nutrient_names:
            if nutrient_name not in totals:
                totals[nutrient_name] = 0.0
        
        # Debug: Print what we found (can remove later)
        if totals and any(v > 0 for v in totals.values()):
            print(f"[DEBUG] Today's totals from DB: {totals}")
        else:
            print(f"[DEBUG] Today's totals from DB: All zeros (no meals found for today)")
        
        return totals
    except Exception as e:
        print(f"ERROR in get_today_nutrient_totals: {e}")
        return {}
    finally:
        conn.close()

def insert_meal_log_nutrients(log_id, nutrient_values):
    """
    Inserts nutrient values for a meal log.
    
    Args:
        log_id: The meal log ID
        nutrient_values: Dictionary of {nutrient_name: value}
    
    Returns:
        Number of nutrients inserted
    """
    if not nutrient_values or not log_id:
        return 0
    
    conn = get_sql_connection()
    if not conn:
        print("ERROR: Could not get database connection in insert_meal_log_nutrients")
        return 0
    
    cursor = conn.cursor()
    inserted_count = 0
    
    try:
        # Get all nutrient IDs in one query to avoid multiple connections
        nutrient_names_list = list(nutrient_values.keys())
        if not nutrient_names_list:
            conn.close()
            return 0
        
        # Build a single query to get all nutrient IDs
        placeholders = ','.join(['?' for _ in nutrient_names_list])
        cursor.execute(f'''
            SELECT nutrient_id, nutrient_name 
            FROM nutrients 
            WHERE nutrient_name IN ({placeholders})
        ''', nutrient_names_list)
        
        nutrient_id_map = {row[1]: row[0] for row in cursor.fetchall()}
        
        # Now insert all nutrients
        for nutrient_name, value in nutrient_values.items():
            if nutrient_name == "allergens" or value is None:
                continue
                
            nutrient_id = nutrient_id_map.get(nutrient_name)
            if nutrient_id:
                try:
                    cursor.execute('''
                        INSERT INTO meal_log_nutrients (log_id, nutrient_id, value)
                        VALUES (?, ?, ?)
                    ''', (log_id, nutrient_id, value))
                    inserted_count += 1
                except pyodbc.IntegrityError:
                    # Already exists, update instead
                    try:
                        cursor.execute('''
                            UPDATE meal_log_nutrients
                            SET value = ?
                            WHERE log_id = ? AND nutrient_id = ?
                        ''', (value, log_id, nutrient_id))
                        inserted_count += 1
                    except Exception as e:
                        print(f"Error updating nutrient {nutrient_name}: {e}")
                except Exception as e:
                    print(f"Error inserting nutrient {nutrient_name}: {e}")
        
        conn.commit()
    except Exception as e:
        print(f"ERROR in insert_meal_log_nutrients: {e}")
        conn.rollback()
    finally:
        conn.close()
    
    return inserted_count

def get_all_available_nutrients():
    """
    Returns a list of all available nutrients in the system.
    
    Returns:
        List of dictionaries: [{'nutrient_id': 1, 'nutrient_name': 'calories', 'display_name': 'Calories', 'unit': 'kcal', 'is_default': True}, ...]
    """
    conn = get_sql_connection()
    if not conn:
        return []
    
    cursor = conn.cursor()
    cursor.execute('''
        SELECT nutrient_id, nutrient_name, display_name, unit, is_default
        FROM nutrients
        ORDER BY is_default DESC, display_name ASC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    nutrients = []
    for row in rows:
        nutrients.append({
            'nutrient_id': row[0],
            'nutrient_name': row[1],
            'display_name': row[2],
            'unit': row[3],
            'is_default': bool(row[4])
        })
    
    return nutrients

def calculate_remaining_limits(user_id, consumed_nutrients=None):
    """
    Calculates remaining daily limits for a user's tracked nutrients.
    
    Args:
        user_id: User ID
        consumed_nutrients: Optional dict of {nutrient_name: consumed_value} to add to today's totals
    
    Returns:
        Dictionary: {nutrient_name: remaining_value}
    """
    tracked = get_user_tracked_nutrients(user_id)
    today_totals = get_today_nutrient_totals(user_id, list(tracked.keys()))
    
    # Debug: Show what we got from DB
    if today_totals and any(v > 0 for v in today_totals.values()):
        print(f"[DEBUG] calculate_remaining_limits - today_totals from DB: {today_totals}")
    
    # Add any additional consumed nutrients (for inquiry/simulation mode)
    if consumed_nutrients:
        for nutrient_name, value in consumed_nutrients.items():
            if nutrient_name in today_totals:
                today_totals[nutrient_name] += value
            else:
                today_totals[nutrient_name] = value
        print(f"[DEBUG] calculate_remaining_limits - after adding consumed_nutrients: {today_totals}")
    
    # Calculate remaining (can be negative if exceeded)
    remaining = {}
    for nutrient_name, nutrient_info in tracked.items():
        consumed = today_totals.get(nutrient_name, 0)
        limit = nutrient_info['limit']
        remaining[nutrient_name] = limit - consumed  # Can be negative if exceeded
    
    return remaining

# Example usage and testing
if __name__ == "__main__":
    print("Nutrient Utilities - Testing Functions")
    print("=" * 50)
    
    # Test: Get all available nutrients
    print("\n1. Available Nutrients:")
    nutrients = get_all_available_nutrients()
    for nut in nutrients[:5]:  # Show first 5
        print(f"   - {nut['display_name']} ({nut['nutrient_name']}) - {nut['unit']}")
    
    # Test: Get user tracked nutrients
    print("\n2. User 1 Tracked Nutrients:")
    tracked = get_user_tracked_nutrients(1)
    if tracked:
        for name, info in tracked.items():
            print(f"   - {name}: limit={info['limit']} {info['unit']}")
    else:
        print("   No tracked nutrients found for user 1")
    
    # Test: Get today's totals
    print("\n3. Today's Totals for User 1:")
    totals = get_today_nutrient_totals(1)
    if totals:
        for name, total in totals.items():
            print(f"   - {name}: {total}")
    else:
        print("   No meal logs found for today")
    
    print("\n" + "=" * 50)
