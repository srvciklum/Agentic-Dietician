import json
import re
import time
import pyodbc
import os
from dotenv import load_dotenv
from nutrient_utils import (
    get_user_tracked_nutrients,
    get_today_nutrient_totals,
    insert_meal_log_nutrients,
    calculate_remaining_limits,
    get_nutrient_id
)

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

def get_user_limits(user_id=0):
    """Fetches the daily limits for a specific user's configured nutrients."""
    tracked = get_user_tracked_nutrients(user_id)
    
    # Convert to simple dict format for backward compatibility
    limits = {}
    for nutrient_name, info in tracked.items():
        limits[nutrient_name] = info['limit']
    
    # Default fallback if no preferences set
    if not limits:
        limits = {"calories": 2000, "protein": 150, "carbs": 250, "fat": 70}
    
    return limits

def parse_quantity_from_db(qty_string):
    """Parses the text and fetches the unit multiplier from SQL Server."""
    match = re.match(r"([\d\.]+)\s*([a-zA-Z]*)", str(qty_string).lower().strip())
    
    if not match:
        return 100 
        
    amount = float(match.group(1))
    unit = match.group(2)
    if not unit:
        unit = "piece"
        
    conn = get_sql_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT gram_multiplier FROM unit_conversions WHERE unit_name = ?', (unit,))
    row = cursor.fetchone()
    conn.close()
    
    multiplier = row[0] if row else 100 
    return amount * multiplier

def calculate_final_macros(agent2_json_string, user_id=0):
    start_time = time.time()
    data = json.loads(agent2_json_string)
    
    food_name = data.get("Matched_Food")
    intent = data.get("Intent", "log")
    
    qty_str = str(data.get("User_Requested_Qty", "1")).strip()
    display_qty = str(data.get("Display_Qty") or qty_str).strip()
    nutrition_is_total = bool(data.get("Nutrition_Is_Total", False))

    # Scaling: agent6 estimates are already for the full quantity; agent2 is per 100g
    if nutrition_is_total:
        qty_multiplier = 1.0
    else:
        try:
            qty_multiplier = float(qty_str)
        except ValueError:
            # e.g. "1000 ml" / "2 cups" -> grams equivalent, then per-100g scale
            grams = parse_quantity_from_db(qty_str)
            qty_multiplier = grams / 100.0
        
    # Get base nutrition - now can have ANY nutrients
    base_nutrition = data.get("Base_Nutrition_Per_100g", {})
    
    # Get user's tracked nutrients
    tracked_nutrients = get_user_tracked_nutrients(user_id)
    tracked_nutrient_names = list(tracked_nutrients.keys())
    
    # If user has no tracked nutrients, use default 4
    if not tracked_nutrient_names:
        tracked_nutrient_names = ["calories", "protein", "carbs", "fat"]
    
    # Calculate consumed values for all nutrients in food
    consumed_nutrients = {}
    for nutrient_name, base_value in base_nutrition.items():
        if nutrient_name != "allergens":  # Skip non-nutrient fields
            if isinstance(base_value, (int, float)):
                consumed_nutrients[nutrient_name] = base_value * qty_multiplier

    # Database Operations
    log_id = None

    # --- CONDITIONAL SQL INSERT based on Intent ---
    if intent == "log":
        try:
            conn = get_sql_connection()
            if not conn:
                print("ERROR: Could not connect to database for logging")
                action_log = f"Failed to log '{food_name}' - database connection error."
            else:
                cursor = conn.cursor()
                # Insert meal log (without nutrient columns)
                cursor.execute('''
                    INSERT INTO meal_logs (user_id, food_name)
                    VALUES (?, ?)
                ''', (user_id, (food_name or "meal")[:180]))
                
                # Get the log_id
                cursor.execute('SELECT @@IDENTITY')
                row = cursor.fetchone()
                log_id = row[0] if row else None
                
                conn.commit()
                conn.close()
                
                # Insert nutrient values into meal_log_nutrients (uses its own connection)
                if log_id:
                    insert_meal_log_nutrients(log_id, consumed_nutrients)
                    action_log = f"Logged '{food_name}' to DB."
                else:
                    action_log = f"Failed to log '{food_name}' - could not get log_id."
        except Exception as e:
            print(f"ERROR in database operations: {e}")
            action_log = f"Error logging '{food_name}': {str(e)}"
    else:
        action_log = f"Simulated '{food_name}' (Inquiry Only - DB bypassed)."

    # Get today's totals for user's tracked nutrients (ACTUAL consumption from DB)
    today_totals = get_today_nutrient_totals(user_id, tracked_nutrient_names)
    
    # Calculate remaining limits based on ACTUAL consumption (not hypothetical)
    remaining_limits = calculate_remaining_limits(user_id, None)  # Always use actual DB data
    
    # For inquiry mode, calculate PROJECTED values separately (what WOULD happen if they eat this)
    # But don't modify the actual totals - keep them as-is
    projected_remaining = {}
    if intent == "inquire":
        tracked = get_user_tracked_nutrients(user_id)
        for nutrient_name in tracked_nutrient_names:
            if nutrient_name in tracked:
                actual_consumed = today_totals.get(nutrient_name, 0)
                meal_consumed = consumed_nutrients.get(nutrient_name, 0)
                projected_consumed = actual_consumed + meal_consumed
                limit = tracked[nutrient_name]['limit']
                projected_remaining[nutrient_name] = limit - projected_consumed
    
    # Build flexible payload
    agent3_payload = {
        "User_ID": user_id,
        "Food_Eaten": food_name,
        "Amount_Logged": display_qty,
        "Intent": intent,
        "Consumed_Nutrients": {k: round(v, 2) for k, v in consumed_nutrients.items()},
        "Today_Total_Consumed": {k: round(v, 2) for k, v in today_totals.items()},  # ACTUAL consumption (never modified)
        "Remaining_Daily_Limits": {k: round(v, 2) for k, v in remaining_limits.items()},  # ACTUAL remaining (never modified)
        "Tracked_Nutrients": tracked_nutrient_names,
        "Ingredients_Breakdown": data.get("Ingredients_Breakdown", []),
        "Allergens": base_nutrition.get("allergens", []) if isinstance(base_nutrition, dict) else []
    }
    
    # For inquiries, add projected values separately (what WOULD happen)
    if intent == "inquire" and projected_remaining:
        agent3_payload["Projected_Remaining_Limits"] = {k: round(v, 2) for k, v in projected_remaining.items()}
    
    execution_time = round((time.time() - start_time) * 1000, 2)
    
    print("\n--- AGENT 3: FLEXIBLE NUTRIENT CALCULATOR ---")
    print(f"Execution Speed : {execution_time} ms")
    print(f"Action          : {action_log}")
    print(f"Tracked Nutrients: {', '.join(tracked_nutrient_names)}")
    print(f"JSON Payload    : {json.dumps(agent3_payload, indent=2)}")
    print("--------------------------------------------\n")
    
    return json.dumps(agent3_payload)

# --- Console Testing Loop ---
if __name__ == "__main__":
    print("\nAgent 3 is Online. Connected to SQL Server.")
    
    test_agent2_output = """
    {
      "Matched_Food": "Chocolate Lava Cake",
      "User_Requested_Qty": "2 slices",
      "Ingredients_Breakdown": ["dark chocolate", "butter", "sugar", "eggs", "wheat flour", "cocoa powder"],
      "Base_Nutrition_Per_100g": {
        "calories": 410, "protein": 5, "carbs": 42, "fat": 26,
        "allergens": ["dairy", "eggs", "gluten"]
      }
    }
    """
    print("\nProcessing '2 slices' of Lava Cake for User 1...")
    calculate_final_macros(test_agent2_output, user_id=1)