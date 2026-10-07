# Flexible Nutrient Tracking System - Design Document

## Overview
This document outlines the design changes required to support user-configurable nutrient tracking, allowing each user to track their own custom set of nutrients (e.g., calories, protein, carbs, fat, potassium, sodium, fiber, etc.) instead of the current fixed set of 4 nutrients.

---

## 1. Database Schema Changes

### 1.1 New Tables

#### Table: `nutrients` (Master Table)
**Purpose**: Stores all available nutrients that can be tracked in the system.

```sql
CREATE TABLE nutrients (
    nutrient_id INT IDENTITY(1,1) PRIMARY KEY,
    nutrient_name NVARCHAR(50) UNIQUE NOT NULL,  -- e.g., 'calories', 'protein', 'potassium', 'sodium'
    display_name NVARCHAR(100) NOT NULL,         -- e.g., 'Calories', 'Protein (g)', 'Potassium (mg)'
    unit NVARCHAR(20) NOT NULL,                  -- e.g., 'kcal', 'g', 'mg', 'mcg'
    is_default BIT DEFAULT 0                    -- Mark common nutrients (calories, protein, carbs, fat)
)
```

**Sample Data**:
```sql
INSERT INTO nutrients (nutrient_name, display_name, unit, is_default) VALUES
('calories', 'Calories', 'kcal', 1),
('protein', 'Protein', 'g', 1),
('carbs', 'Carbohydrates', 'g', 1),
('fat', 'Fat', 'g', 1),
('fiber', 'Fiber', 'g', 0),
('sodium', 'Sodium', 'mg', 0),
('potassium', 'Potassium', 'mg', 0),
('calcium', 'Calcium', 'mg', 0),
('iron', 'Iron', 'mg', 0),
('vitamin_c', 'Vitamin C', 'mg', 0);
```

#### Table: `user_nutrient_preferences`
**Purpose**: Stores which nutrients each user wants to track and their daily limits.

```sql
CREATE TABLE user_nutrient_preferences (
    preference_id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT NOT NULL FOREIGN KEY REFERENCES users(user_id),
    nutrient_id INT NOT NULL FOREIGN KEY REFERENCES nutrients(nutrient_id),
    daily_limit FLOAT NOT NULL,
    is_active BIT DEFAULT 1,  -- Allow users to temporarily disable tracking
    created_at DATETIME DEFAULT GETDATE(),
    UNIQUE(user_id, nutrient_id)  -- One limit per nutrient per user
)
```

#### Table: `meal_log_nutrients`
**Purpose**: Stores nutritional values for each logged meal (normalized approach).

```sql
CREATE TABLE meal_log_nutrients (
    log_nutrient_id INT IDENTITY(1,1) PRIMARY KEY,
    log_id INT NOT NULL FOREIGN KEY REFERENCES meal_logs(log_id) ON DELETE CASCADE,
    nutrient_id INT NOT NULL FOREIGN KEY REFERENCES nutrients(nutrient_id),
    value FLOAT NOT NULL,
    UNIQUE(log_id, nutrient_id)  -- One value per nutrient per meal log
)
```

### 1.2 Modified Tables

#### Table: `users` (Modifications)
**Changes**: Remove fixed nutrient limit columns, keep only user profile data.

```sql
-- REMOVE these columns (migrate data first!):
-- limit_calories, limit_protein, limit_carbs, limit_fat

-- KEEP:
ALTER TABLE users
    DROP COLUMN limit_calories,
    DROP COLUMN limit_protein,
    DROP COLUMN limit_carbs,
    DROP COLUMN limit_fat;

-- Users table becomes simpler:
-- user_id (PK), username
```

#### Table: `meal_logs` (Modifications)
**Changes**: Remove fixed nutrient columns, keep only meal metadata.

```sql
-- REMOVE these columns (migrate data first!):
-- calories, protein, carbs, fat

-- KEEP:
ALTER TABLE meal_logs
    DROP COLUMN calories,
    DROP COLUMN protein,
    DROP COLUMN carbs,
    DROP COLUMN fat;

-- meal_logs becomes:
-- log_id (PK), user_id (FK), food_name, log_time
```

---

## 2. Database Relationships

```
┌─────────────┐
│   users     │
│─────────────│
│ user_id (PK)│
│ username    │
└──────┬──────┘
       │
       │ 1:N
       │
       ├─────────────────────────────────────┐
       │                                     │
       │                                     │
┌──────▼──────────────────┐    ┌────────────▼──────────────┐
│ user_nutrient_preferences│    │      meal_logs            │
│──────────────────────────│    │───────────────────────────│
│ preference_id (PK)       │    │ log_id (PK)               │
│ user_id (FK)             │    │ user_id (FK)              │
│ nutrient_id (FK)         │    │ food_name                 │
│ daily_limit              │    │ log_time                  │
│ is_active                │    └──────┬───────────────────┘
└──────┬───────────────────┘           │
       │                               │ 1:N
       │ N:1                           │
       │                               │
┌──────▼───────────────────┐    ┌─────▼────────────────────┐
│      nutrients           │    │ meal_log_nutrients        │
│──────────────────────────│    │──────────────────────────│
│ nutrient_id (PK)         │    │ log_nutrient_id (PK)      │
│ nutrient_name            │    │ log_id (FK)              │
│ display_name             │    │ nutrient_id (FK)         │
│ unit                     │    │ value                     │
│ is_default               │    └──────────────────────────┘
└──────────────────────────┘
```

**Key Relationships**:
- `users` → `user_nutrient_preferences` (1:N) - Each user can track multiple nutrients
- `users` → `meal_logs` (1:N) - Each user can have multiple meal logs
- `nutrients` → `user_nutrient_preferences` (1:N) - Each nutrient can be tracked by multiple users
- `nutrients` → `meal_log_nutrients` (1:N) - Each nutrient can appear in multiple meal logs
- `meal_logs` → `meal_log_nutrients` (1:N) - Each meal log can have multiple nutrient values

---

## 3. Migration Strategy

### Phase 1: Add New Tables (Non-Breaking)
1. Create `nutrients` table and populate with common nutrients
2. Create `user_nutrient_preferences` table
3. Create `meal_log_nutrients` table
4. **Keep old columns in `users` and `meal_logs` during transition**

### Phase 2: Data Migration
1. Migrate existing user limits from `users` table to `user_nutrient_preferences`:
   ```sql
   INSERT INTO user_nutrient_preferences (user_id, nutrient_id, daily_limit)
   SELECT 
       user_id,
       (SELECT nutrient_id FROM nutrients WHERE nutrient_name = 'calories'),
       limit_calories
   FROM users WHERE limit_calories IS NOT NULL;
   -- Repeat for protein, carbs, fat
   ```

2. Migrate existing meal log data from `meal_logs` to `meal_log_nutrients`:
   ```sql
   INSERT INTO meal_log_nutrients (log_id, nutrient_id, value)
   SELECT 
       log_id,
       (SELECT nutrient_id FROM nutrients WHERE nutrient_name = 'calories'),
       calories
   FROM meal_logs WHERE calories IS NOT NULL;
   -- Repeat for protein, carbs, fat
   ```

### Phase 3: Code Updates
1. Update all agent code to use new schema
2. Test thoroughly
3. Remove old columns from `users` and `meal_logs` tables

---

## 4. Code Changes Required

### 4.1 Agent 3 Calculator (`agent3_calculator.py`)

#### Function: `get_user_limits(user_id)`
**Current**: Returns fixed dict with 4 nutrients
**New**: Returns dict with user's configured nutrients

```python
def get_user_limits(user_id=0):
    """Fetches the daily limits for a specific user's configured nutrients."""
    conn = get_sql_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT n.nutrient_name, unp.daily_limit, n.unit
        FROM user_nutrient_preferences unp
        JOIN nutrients n ON unp.nutrient_id = n.nutrient_id
        WHERE unp.user_id = ? AND unp.is_active = 1
    ''', (user_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    limits = {}
    for row in rows:
        limits[row[0]] = {
            "limit": row[1],
            "unit": row[2]
        }
    
    # Default fallback if no preferences set
    if not limits:
        cursor.execute('SELECT nutrient_name, unit FROM nutrients WHERE is_default = 1')
        default_nutrients = cursor.fetchall()
        limits = {nutrient[0]: {"limit": 0, "unit": nutrient[1]} for nutrient in default_nutrients}
    
    return limits
```

#### Function: `calculate_final_macros(agent2_json_string, user_id)`
**Major Changes**:
1. Get user's tracked nutrients dynamically
2. Calculate consumed values for ALL nutrients in food (not just 4)
3. Insert into `meal_log_nutrients` instead of fixed columns
4. Calculate today's totals for user's tracked nutrients only
5. Return flexible JSON structure

```python
def calculate_final_macros(agent2_json_string, user_id=0):
    start_time = time.time()
    data = json.loads(agent2_json_string)
    
    food_name = data.get("Matched_Food")
    intent = data.get("Intent", "log")
    qty_str = data.get("User_Requested_Qty", "1")
    
    try:
        qty_multiplier = float(qty_str)
    except ValueError:
        qty_multiplier = 1.0
    
    # Get base nutrition - now can have ANY nutrients
    base_nutrition = data.get("Base_Nutrition_Per_100g", {})
    
    # Get user's tracked nutrients
    user_limits = get_user_limits(user_id)
    tracked_nutrient_names = list(user_limits.keys())
    
    # Calculate consumed values for all nutrients in food
    consumed_nutrients = {}
    for nutrient_name, base_value in base_nutrition.items():
        if nutrient_name != "allergens":  # Skip non-nutrient fields
            consumed_nutrients[nutrient_name] = base_value * qty_multiplier
    
    conn = get_sql_connection()
    cursor = conn.cursor()
    
    # Insert meal log
    if intent == "log":
        cursor.execute('''
            INSERT INTO meal_logs (user_id, food_name)
            VALUES (?, ?)
        ''', (user_id, food_name))
        
        # Get the log_id
        cursor.execute('SELECT @@IDENTITY')
        log_id = cursor.fetchone()[0]
        
        # Insert nutrient values
        for nutrient_name, value in consumed_nutrients.items():
            # Get nutrient_id
            cursor.execute('SELECT nutrient_id FROM nutrients WHERE nutrient_name = ?', (nutrient_name,))
            nutrient_row = cursor.fetchone()
            
            if nutrient_row:
                nutrient_id = nutrient_row[0]
                cursor.execute('''
                    INSERT INTO meal_log_nutrients (log_id, nutrient_id, value)
                    VALUES (?, ?, ?)
                ''', (log_id, nutrient_id, value))
        
        conn.commit()
        action_log = f"Logged '{food_name}' to DB."
    else:
        action_log = f"Simulated '{food_name}' (Inquiry Only - DB bypassed)."
        log_id = None
    
    # Get today's totals for user's tracked nutrients
    today_totals = {}
    if log_id or intent == "inquire":
        for nutrient_name in tracked_nutrient_names:
            if intent == "log":
                cursor.execute('''
                    SELECT COALESCE(SUM(mln.value), 0)
                    FROM meal_log_nutrients mln
                    JOIN meal_logs ml ON mln.log_id = ml.log_id
                    JOIN nutrients n ON mln.nutrient_id = n.nutrient_id
                    WHERE ml.user_id = ? 
                      AND n.nutrient_name = ?
                      AND CAST(ml.log_time AS DATE) = CAST(GETDATE() AS DATE)
                ''', (user_id, nutrient_name))
            else:
                # For inquiries, we'll calculate manually below
                cursor.execute('''
                    SELECT COALESCE(SUM(mln.value), 0)
                    FROM meal_log_nutrients mln
                    JOIN meal_logs ml ON mln.log_id = ml.log_id
                    JOIN nutrients n ON mln.nutrient_id = n.nutrient_id
                    WHERE ml.user_id = ? 
                      AND n.nutrient_name = ?
                      AND CAST(ml.log_time AS DATE) = CAST(GETDATE() AS DATE)
                ''', (user_id, nutrient_name))
            
            row = cursor.fetchone()
            today_totals[nutrient_name] = row[0] if row else 0
            
            # Add current meal if inquiry
            if intent == "inquire" and nutrient_name in consumed_nutrients:
                today_totals[nutrient_name] += consumed_nutrients[nutrient_name]
    
    conn.close()
    
    # Calculate remaining limits
    remaining_limits = {}
    for nutrient_name, limit_info in user_limits.items():
        consumed = today_totals.get(nutrient_name, 0)
        remaining_limits[nutrient_name] = limit_info["limit"] - consumed
    
    # Build flexible payload
    agent3_payload = {
        "User_ID": user_id,
        "Food_Eaten": food_name,
        "Amount_Logged": qty_multiplier,
        "Intent": intent,
        "Consumed_Nutrients": {k: round(v, 2) for k, v in consumed_nutrients.items()},
        "Today_Total_Consumed": {k: round(v, 2) for k, v in today_totals.items()},
        "Remaining_Daily_Limits": {k: round(v, 2) for k, v in remaining_limits.items()},
        "Tracked_Nutrients": tracked_nutrient_names,
        "Ingredients_Breakdown": data.get("Ingredients_Breakdown", []),
        "Allergens": base_nutrition.get("allergens", [])
    }
    
    execution_time = round((time.time() - start_time) * 1000, 2)
    print("\n--- AGENT 3: FLEXIBLE NUTRIENT CALCULATOR ---")
    print(f"Execution Speed : {execution_time} ms")
    print(f"Action          : {action_log}")
    print(f"Tracked Nutrients: {', '.join(tracked_nutrient_names)}")
    print(f"JSON Payload    : {json.dumps(agent3_payload, indent=2)}")
    print("--------------------------------------------\n")
    
    return json.dumps(agent3_payload)
```

### 4.2 Agent 2 Resolver (`agent2_resolver.py`)

**Changes**: The food database (Qdrant) should store ALL available nutrients, not just 4.

```python
# In resolve_nutrition function, return ALL nutrients from food metadata
agent2_payload = {
    "Matched_Food": top_match.metadata["food_name"],
    "User_Requested_Qty": extracted_data.get("Qty"),
    "Ingredients_Breakdown": top_match.metadata["ingredients"],
    "Base_Nutrition_Per_100g": {
        # Return ALL nutrients available in the food item
        **{k: v for k, v in top_match.metadata.items() 
           if k not in ["food_name", "description", "ingredients", "allergens"]},
        "allergens": top_match.metadata["allergens"]
    },
    "DB_Match_Confidence": round(top_match.score, 2)
}
```

### 4.3 Agent 4 Guardrail (`agent4_guardrail.py`)

**Changes**: Update medical rule engine to work with flexible nutrients.

```python
# In run_safety_checks function:
macros = data.get("Consumed_Nutrients", {})  # Changed from Consumed_Macros

# Medical rules can now check any nutrient
if "diabetes" in conditions:
    carbs = macros.get("carbs", 0)
    if carbs > 50:
        safety_flags.append("MEDICAL FLAG (Diabetes): This meal is very high in carbohydrates (>50g).")

# Example: Check sodium for hypertension
if "hypertension" in conditions:
    sodium = macros.get("sodium", 0)
    if sodium > 500:  # mg
        safety_flags.append("MEDICAL FLAG (Hypertension): This meal is very high in sodium (>500mg).")
```

### 4.4 Agent 5 Synthesizer (`agent5_synthesizer.py`)

**Changes**: Update to handle flexible nutrient names in response generation.

```python
# In synthesize_response function:
limits = data.get("Remaining_Daily_Limits", {})
consumed = data.get("Consumed_Nutrients", {})

# Build a summary of tracked nutrients
nutrient_summary = []
for nutrient_name, remaining in limits.items():
    consumed_val = consumed.get(nutrient_name, 0)
    nutrient_summary.append(f"{nutrient_name}: {consumed_val} consumed, {remaining} remaining")

user_prompt = (
    f"The user just logged a meal. "
    f"Politely confirm that {qty} {food} was saved, "
    f"and summarize their remaining daily limits: {', '.join(nutrient_summary[:3])}."  # Show top 3
)
```

### 4.5 Agent 6 LLM Fallback (`agent6_llm_fallback.py`)

**Changes**: Update to estimate ALL nutrients, not just 4.

```python
def estimate_nutrition(food_name, qty, tracked_nutrients=None):
    # If tracked_nutrients provided, only estimate those
    # Otherwise, estimate common nutrients
    
    if tracked_nutrients:
        nutrient_list = ", ".join(tracked_nutrients)
    else:
        nutrient_list = "calories, protein, carbs, fat, fiber, sodium, potassium"
    
    system_prompt = (
        f"You are an expert nutritional database. Estimate nutritional values for: {nutrient_list}. "
        "Respond ONLY with valid JSON. Format: {{\"calories\": 100, \"protein\": 5, ...}}"
    )
    # ... rest of function
```

### 4.6 Setup Scripts

#### New: `setup_flexible_nutrients.py`
Create a script to:
1. Create `nutrients` table
2. Populate with common nutrients
3. Create `user_nutrient_preferences` table
4. Create `meal_log_nutrients` table
5. Migrate existing data (optional)

---

## 5. Implementation Checklist

### Database Layer
- [ ] Create `nutrients` master table
- [ ] Populate `nutrients` with initial data
- [ ] Create `user_nutrient_preferences` table
- [ ] Create `meal_log_nutrients` table
- [ ] Migrate existing user limits to `user_nutrient_preferences`
- [ ] Migrate existing meal log data to `meal_log_nutrients`
- [ ] Remove old columns from `users` table (after migration)
- [ ] Remove old columns from `meal_logs` table (after migration)

### Code Layer
- [ ] Update `agent3_calculator.py` - `get_user_limits()` function
- [ ] Update `agent3_calculator.py` - `calculate_final_macros()` function
- [ ] Update `agent2_resolver.py` - Return all nutrients from food DB
- [ ] Update `agent4_guardrail.py` - Use flexible nutrient structure
- [ ] Update `agent5_synthesizer.py` - Handle flexible nutrients in responses
- [ ] Update `agent6_llm_fallback.py` - Estimate all nutrients
- [ ] Update `agentic_main.py` - Tool functions to handle flexible nutrients
- [ ] Create `setup_flexible_nutrients.py` migration script

### Testing
- [ ] Test with user tracking only default 4 nutrients
- [ ] Test with user tracking custom nutrients (e.g., potassium, sodium)
- [ ] Test with user tracking all available nutrients
- [ ] Test meal logging with flexible nutrients
- [ ] Test today's totals calculation
- [ ] Test remaining limits calculation
- [ ] Test inquiry/simulation mode
- [ ] Test guardrail checks with custom nutrients

---

## 6. Example Usage Scenarios

### Scenario 1: User tracks only calories and protein
```python
# User preferences:
user_nutrient_preferences = [
    {"nutrient_name": "calories", "daily_limit": 2000},
    {"nutrient_name": "protein", "daily_limit": 150}
]

# Meal log will only track and calculate these 2 nutrients
```

### Scenario 2: User tracks potassium for kidney health
```python
# User preferences:
user_nutrient_preferences = [
    {"nutrient_name": "calories", "daily_limit": 2000},
    {"nutrient_name": "protein", "daily_limit": 150},
    {"nutrient_name": "potassium", "daily_limit": 3500}  # mg
]

# System tracks potassium intake and remaining limits
```

### Scenario 3: User tracks comprehensive nutrition
```python
# User preferences:
user_nutrient_preferences = [
    {"nutrient_name": "calories", "daily_limit": 2000},
    {"nutrient_name": "protein", "daily_limit": 150},
    {"nutrient_name": "carbs", "daily_limit": 250},
    {"nutrient_name": "fat", "daily_limit": 70},
    {"nutrient_name": "fiber", "daily_limit": 25},
    {"nutrient_name": "sodium", "daily_limit": 2300},
    {"nutrient_name": "potassium", "daily_limit": 3500},
    {"nutrient_name": "calcium", "daily_limit": 1000}
]

# System tracks all 8 nutrients
```

---

## 7. Benefits of This Design

1. **Flexibility**: Users can track any combination of nutrients
2. **Scalability**: Easy to add new nutrients without schema changes
3. **Normalization**: Proper database design, no data duplication
4. **User-Centric**: Each user has personalized tracking
5. **Extensibility**: Medical conditions can check any nutrient
6. **Future-Proof**: Can add features like nutrient goals, trends, etc.

---

## 8. Potential Challenges & Solutions

### Challenge 1: Food database may not have all nutrients
**Solution**: 
- Agent 6 (LLM fallback) can estimate missing nutrients
- Store NULL/0 for unavailable nutrients
- Clearly indicate which nutrients are estimated vs. from database

### Challenge 2: Performance with many nutrients
**Solution**:
- Index `meal_log_nutrients` on `(log_id, nutrient_id)`
- Index `user_nutrient_preferences` on `(user_id, nutrient_id)`
- Consider caching user preferences

### Challenge 3: Backward compatibility during migration
**Solution**:
- Keep old columns during transition period
- Run both old and new code paths
- Migrate data gradually
- Remove old code only after full migration

---

## 9. Next Steps

1. Review and approve this design
2. Create database migration scripts
3. Implement code changes incrementally
4. Test with sample data
5. Deploy to staging environment
6. Migrate production data
7. Monitor and optimize

---

**End of Design Document**
