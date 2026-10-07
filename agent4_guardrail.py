import json
import time
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

def get_user_health_profile(user_id=1):
    """Fetches allergies and medical conditions from normalized SQL tables."""
    conn = get_sql_connection()
    cursor = conn.cursor()
    
    health_profile = {"allergies": [], "medical_conditions": []}
    
    # Query 1: Get all allergies for this user
    cursor.execute('SELECT allergy_name FROM user_allergies WHERE user_id = ?', (user_id,))
    allergy_rows = cursor.fetchall()
    health_profile["allergies"] = [row[0].lower() for row in allergy_rows]
    
    # Query 2: Get all medical conditions for this user
    cursor.execute('SELECT condition_name FROM user_conditions WHERE user_id = ?', (user_id,))
    condition_rows = cursor.fetchall()
    health_profile["medical_conditions"] = [row[0].lower() for row in condition_rows]
    
    conn.close()
    return health_profile

def run_safety_checks(agent3_json_string):
    """Agent 4: Compares meal data against user health profile."""
    start_time = time.time()
    data = json.loads(agent3_json_string)
    
    # --- NEGATIVE CASE HANDLER ---
    if "error" in data:
        print("\n--- AGENT 4: ERROR PASSTHROUGH ---")
        print("Action: Passing error directly to Agent 5.")
        return json.dumps(data)

    user_id = data.get("User_ID", 1)
    health_profile = get_user_health_profile(user_id)
    
    food_allergens = [a.lower() for a in data.get("Allergens", [])]
    ingredients = [i.lower() for i in data.get("Ingredients_Breakdown", [])]
    
    # Use Consumed_Nutrients instead of Consumed_Macros (backward compatible)
    nutrients = data.get("Consumed_Nutrients", {})
    if not nutrients:
        # Fallback to old format for backward compatibility
        old_macros = data.get("Consumed_Macros", {})
        nutrients = old_macros
    
    safety_flags = []

    # --- TOOL 1: Allergen Checker ---
    for allergy in health_profile["allergies"]:
        if allergy in food_allergens or allergy in ingredients:
            safety_flags.append(f"ALLERGY WARNING: This contains {allergy.upper()}.")

    # --- TOOL 2: Medical Rule Engine ---
    conditions = health_profile["medical_conditions"]
    
    if "diabetes" in conditions:
        carbs = nutrients.get("carbs", 0)
        if carbs > 50:
            safety_flags.append("MEDICAL FLAG (Diabetes): This meal is very high in carbohydrates (>50g).")
    
    # Example: Check sodium for hypertension
    if "hypertension" in conditions:
        sodium = nutrients.get("sodium", 0)
        if sodium > 500:  # mg
            safety_flags.append("MEDICAL FLAG (Hypertension): This meal is very high in sodium (>500mg).")
    
    # Example: Check potassium for kidney conditions
    if "kidney_disease" in conditions or "kidney disease" in conditions or "ckd" in conditions:
        potassium = nutrients.get("potassium", 0)
        if potassium > 200:  # mg per meal
            safety_flags.append("MEDICAL FLAG (Kidney Health): This meal is high in potassium (>200mg).")

    # Compile the final payload
    data["Safety_Flags"] = safety_flags
    data["Is_Safe"] = len(safety_flags) == 0
    
    execution_time = round((time.time() - start_time) * 1000, 2)
    
    print("\n--- AGENT 4: SAFETY GUARDRAIL ---")
    print(f"Execution Speed : {execution_time} ms")
    print(f"Flags Triggered : {len(safety_flags)}")
    print(f"JSON Payload    : {json.dumps(data, indent=2)}")
    print("---------------------------------\n")
    
    return json.dumps(data)

# --- Console Testing Loop ---
if __name__ == "__main__":
    print("\nAgent 4 is Online. Guardrails active.")
    print("Type 'quit' to exit.")
    
    while True:
        print("\n" + "-"*40)
        user_in = input("Paste Agent 3 JSON: ").strip()
        
        if user_in.lower() in ['quit', 'exit']:
            break
        if not user_in:
            continue
            
        try:
            run_safety_checks(user_in)
        except json.JSONDecodeError:
            print("ERROR: Invalid JSON.")
        except Exception as e:
            print(f"System Error: {e}")