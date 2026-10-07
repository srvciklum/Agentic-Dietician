from qdrant_client import QdrantClient, models
import time
import json
import os
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="qdrant_client")


print("Connecting to Local Qdrant Database...")
client = QdrantClient(url="http://localhost:6333", check_compatibility=False)
COLLECTION_NAME = "food_nutrition_db_v0" # Changed name to force a fresh upload
client.set_model("sentence-transformers/all-MiniLM-L6-v2")

def seed_database_from_json():
    """Reads the JSON file and injects the items into the Vector DB."""
   
    
    if client.collection_exists(COLLECTION_NAME):
        print("Database already seeded. Skipping setup.")
        return

    print("Reading food_database.json and seeding Database...")
    
    # Load the 100+ items from the JSON file
    if not os.path.exists("food_database.json"):
        print("ERROR: food_database.json not found!")
        return
        
    with open("food_database.json", "r") as file:
        food_data = json.load(file)
        
    documents = []
    metadata = []
    
    for item in food_data:
        # We combine the name, description, and ingredients so the AI can search all of them!
        searchable_text = f"{item['food_name']}. {item['description']} Ingredients: {', '.join(item['ingredients'])}"
        documents.append(searchable_text)
        metadata.append(item)
    
    client.add(
        collection_name=COLLECTION_NAME,
        documents=documents,
        metadata=metadata
    )
    print(f"Successfully seeded {len(documents)} items into the Database!\n")

# Auto-seed when collection is missing (e.g. fresh Qdrant container)
seed_database_from_json()

def resolve_nutrition(agent1_json_string):
    """
    Agent 2: Searches the DB for the food and returns the nutritional profile AND ingredients.
    """
    start_time = time.time()
    if not client.collection_exists(COLLECTION_NAME):
        seed_database_from_json()
    extracted_data = json.loads(agent1_json_string)
    search_food = extracted_data.get("Food")
    
    # Back to the rock-solid, stable query method!
    search_results = client.query(
        collection_name=COLLECTION_NAME,
        query_text=search_food,
        limit=1 
    )
    
    if not search_results:
        return json.dumps({"error": f"Food '{search_food}' not found in Database."})
        
    top_match = search_results[0]
    
    # --- THE CONFIDENCE GUARDRAIL ---
    if top_match.score < 0.50:
        error_payload = {"error": f"Food '{search_food}' not found. Confidence too low ({round(top_match.score, 2)})."}
        
        print("\n--- AGENT 2: REJECTED MATCH ---")
        print("Action          : Refused to guess due to low similarity score.")
        print(f"JSON Payload    : {json.dumps(error_payload)}")
        print("-------------------------------\n")
        
        return json.dumps(error_payload)
    
    # Build nutrition dict - include ALL nutrients from metadata, not just 4
    base_nutrition = {}
    excluded_keys = ["food_name", "description", "ingredients", "allergens"]
    
    # Add all nutrient fields from metadata
    for key, value in top_match.metadata.items():
        if key not in excluded_keys and isinstance(value, (int, float)):
            base_nutrition[key] = value
    
    # Ensure allergens are included
    base_nutrition["allergens"] = top_match.metadata.get("allergens", [])
    
    # Stable payload using .metadata
    agent2_payload = {
        "Matched_Food": top_match.metadata["food_name"],
        "User_Requested_Qty": extracted_data.get("Qty"),
        "Ingredients_Breakdown": top_match.metadata.get("ingredients", []),
        "Base_Nutrition_Per_100g": base_nutrition,
        "DB_Match_Confidence": round(top_match.score, 2)
    }
    
    execution_time = round((time.time() - start_time) * 1000, 2)
    
    print("\n--- AGENT 2: NUTRITIONAL RESOLVER ---")
    print(f"Execution Speed : {execution_time} ms")
    print(f"JSON Payload    : {json.dumps(agent2_payload, indent=2)}")
    print("-------------------------------------\n")
    
    return json.dumps(agent2_payload)

# --- Console Testing Loop ---
if __name__ == "__main__":
    print("\n=== AGENT 2 SYSTEM STARTUP ===")
    
    # Boolean check to decide if we should seed
    seed_choice = input("Do you want to seed/update the database? (y/n): ").strip().lower()
    if seed_choice == 'y':
        seed_database_from_json()
    else:
        print("Skipping database seed. Connecting to existing data...")
        
    print("\nAgent 2 is Online. Type 'quit' to exit.")
    
    # Continuous testing loop
    while True:
        print("\n" + "-"*40)
        food_in = input("Simulated Agent 2 [Food]: ")
        if food_in.lower() in ['quit', 'exit']:
            break
            
        qty_in = input("Simulated Agent 2 [Qty] : ")
        
        # We dynamically build the JSON that Agent 1 normally passes to Agent 2
        simulated_agent1_json = json.dumps({
            "Food": food_in,
            "Qty": qty_in
        })
        
        print(f"-> Receiving Payload: {simulated_agent1_json}")
        resolve_nutrition(simulated_agent1_json)