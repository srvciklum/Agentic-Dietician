# Flexible Nutrient Tracking - Implementation Guide

## Quick Start

This guide will help you implement flexible nutrient tracking step-by-step.

---

## 📋 Overview

Your system currently tracks 4 fixed nutrients (calories, protein, carbs, fat). This implementation allows each user to configure their own set of nutrients to track.

---

## 🗂️ Files Created

1. **`FLEXIBLE_NUTRIENT_TRACKING_DESIGN.md`** - Complete design document with schema, relationships, and code changes
2. **`setup_flexible_nutrients.py`** - Database migration script
3. **`nutrient_utils.py`** - Helper utility functions for working with nutrients

---

## 🚀 Implementation Steps

### Step 1: Review the Design
Read `FLEXIBLE_NUTRIENT_TRACKING_DESIGN.md` to understand:
- Database schema changes
- Relationships between tables
- Code changes required

### Step 2: Backup Your Database
**CRITICAL**: Before making any changes, backup your database!

```sql
-- In SQL Server Management Studio:
-- Right-click your database → Tasks → Back Up Database
```

### Step 3: Run Database Migration
Execute the migration script to create new tables:

```bash
python setup_flexible_nutrients.py
```

This will:
- ✅ Create `nutrients` master table
- ✅ Create `user_nutrient_preferences` table
- ✅ Create `meal_log_nutrients` table
- ✅ Optionally migrate existing data

### Step 4: Verify Database Schema
Check that the new tables were created:

```sql
-- In SQL Server Management Studio, run:
SELECT * FROM nutrients;
SELECT * FROM user_nutrient_preferences;
SELECT * FROM meal_log_nutrients;
```

### Step 5: Set Up User Preferences
For each user, configure which nutrients they want to track:

**Option A: Using SQL**
```sql
-- Example: User 1 wants to track calories, protein, and potassium
INSERT INTO user_nutrient_preferences (user_id, nutrient_id, daily_limit)
SELECT 1, nutrient_id, 
    CASE nutrient_name
        WHEN 'calories' THEN 2000
        WHEN 'protein' THEN 150
        WHEN 'potassium' THEN 3500
    END
FROM nutrients
WHERE nutrient_name IN ('calories', 'protein', 'potassium');
```

**Option B: Using Python**
```python
from nutrient_utils import set_user_nutrient_preference

# Set user 1's preferences
set_user_nutrient_preference(1, 'calories', 2000)
set_user_nutrient_preference(1, 'protein', 150)
set_user_nutrient_preference(1, 'potassium', 3500)
```

### Step 6: Update Agent Code

#### 6.1 Update `agent3_calculator.py`

Replace the `get_user_limits()` function:

```python
from nutrient_utils import get_user_tracked_nutrients

def get_user_limits(user_id=0):
    """Fetches the daily limits for a specific user's configured nutrients."""
    tracked = get_user_tracked_nutrients(user_id)
    
    # Convert to old format for backward compatibility (if needed)
    limits = {}
    for nutrient_name, info in tracked.items():
        limits[nutrient_name] = info['limit']
    
    # Default fallback
    if not limits:
        limits = {"calories": 2000, "protein": 150, "carbs": 250, "fat": 70}
    
    return limits
```

Update `calculate_final_macros()` function to:
- Use `nutrient_utils.get_user_tracked_nutrients()` to get user's nutrients
- Use `nutrient_utils.insert_meal_log_nutrients()` to save nutrient values
- Use `nutrient_utils.get_today_nutrient_totals()` to get today's totals
- Use `nutrient_utils.calculate_remaining_limits()` to calculate remaining

See `FLEXIBLE_NUTRIENT_TRACKING_DESIGN.md` Section 4.1 for complete code.

#### 6.2 Update `agent2_resolver.py`

Ensure the food database returns ALL available nutrients, not just 4. The Qdrant metadata should include all nutrients from the food item.

#### 6.3 Update `agent4_guardrail.py`

Change `Consumed_Macros` to `Consumed_Nutrients`:

```python
macros = data.get("Consumed_Nutrients", {})  # Changed from Consumed_Macros
```

Update medical rules to work with flexible nutrients (see design doc Section 4.3).

#### 6.4 Update `agent5_synthesizer.py`

Update to handle flexible nutrient structure (see design doc Section 4.4).

#### 6.5 Update `agent6_llm_fallback.py`

Update to estimate all nutrients, not just 4 (see design doc Section 4.5).

### Step 7: Test the Changes

1. **Test with default nutrients** (calories, protein, carbs, fat):
   ```python
   # Set up user with default nutrients
   set_user_nutrient_preference(1, 'calories', 2000)
   set_user_nutrient_preference(1, 'protein', 150)
   set_user_nutrient_preference(1, 'carbs', 250)
   set_user_nutrient_preference(1, 'fat', 70)
   
   # Test meal logging
   # ... run your agent pipeline
   ```

2. **Test with custom nutrients**:
   ```python
   # Add potassium tracking
   set_user_nutrient_preference(1, 'potassium', 3500)
   
   # Test meal logging
   # ... run your agent pipeline
   ```

3. **Verify data in database**:
   ```sql
   -- Check user preferences
   SELECT u.username, n.nutrient_name, unp.daily_limit
   FROM user_nutrient_preferences unp
   JOIN users u ON unp.user_id = u.user_id
   JOIN nutrients n ON unp.nutrient_id = n.nutrient_id
   WHERE u.user_id = 1;
   
   -- Check meal log nutrients
   SELECT ml.food_name, n.nutrient_name, mln.value
   FROM meal_log_nutrients mln
   JOIN meal_logs ml ON mln.log_id = ml.log_id
   JOIN nutrients n ON mln.nutrient_id = n.nutrient_id
   WHERE ml.user_id = 1
   ORDER BY ml.log_time DESC;
   ```

### Step 8: Remove Old Columns (After Testing)

**⚠️ ONLY DO THIS AFTER CONFIRMING EVERYTHING WORKS!**

Once you've verified the new system works correctly:

```sql
-- Remove old columns from users table
ALTER TABLE users
    DROP COLUMN limit_calories,
    DROP COLUMN limit_protein,
    DROP COLUMN limit_carbs,
    DROP COLUMN limit_fat;

-- Remove old columns from meal_logs table
ALTER TABLE meal_logs
    DROP COLUMN calories,
    DROP COLUMN protein,
    DROP COLUMN carbs,
    DROP COLUMN fat;
```

---

## 📊 Database Schema Summary

### New Tables

1. **`nutrients`** - Master list of all available nutrients
2. **`user_nutrient_preferences`** - Which nutrients each user tracks + their limits
3. **`meal_log_nutrients`** - Actual nutrient values for each meal log

### Modified Tables

1. **`users`** - Remove `limit_*` columns (after migration)
2. **`meal_logs`** - Remove `calories`, `protein`, `carbs`, `fat` columns (after migration)

---

## 🔧 Utility Functions Reference

The `nutrient_utils.py` module provides these helper functions:

| Function | Purpose |
|----------|---------|
| `get_user_tracked_nutrients(user_id)` | Get all nutrients a user is tracking |
| `set_user_nutrient_preference(user_id, nutrient_name, daily_limit)` | Set/update user's nutrient preference |
| `get_today_nutrient_totals(user_id, nutrient_names=None)` | Get today's consumed totals |
| `insert_meal_log_nutrients(log_id, nutrient_values)` | Save nutrient values for a meal |
| `calculate_remaining_limits(user_id, consumed_nutrients=None)` | Calculate remaining daily limits |
| `get_all_available_nutrients()` | Get list of all available nutrients |
| `get_nutrient_id(nutrient_name)` | Get nutrient_id from nutrient_name |
| `get_nutrient_name(nutrient_id)` | Get nutrient_name from nutrient_id |

---

## 🧪 Testing Checklist

- [ ] Database migration script runs successfully
- [ ] New tables created correctly
- [ ] Existing data migrated (if applicable)
- [ ] User can set nutrient preferences
- [ ] Meal logging works with flexible nutrients
- [ ] Today's totals calculated correctly
- [ ] Remaining limits calculated correctly
- [ ] Inquiry/simulation mode works
- [ ] Guardrail checks work with custom nutrients
- [ ] Agent 5 synthesizer handles flexible nutrients
- [ ] Agent 6 LLM fallback estimates all nutrients
- [ ] Old columns removed (after testing)

---

## 🐛 Troubleshooting

### Issue: "Nutrient not found" errors
**Solution**: Make sure the nutrient exists in the `nutrients` table. Run:
```sql
SELECT * FROM nutrients WHERE nutrient_name = 'your_nutrient_name';
```

### Issue: User has no tracked nutrients
**Solution**: Set up user preferences:
```python
from nutrient_utils import set_user_nutrient_preference
set_user_nutrient_preference(user_id, 'calories', 2000)
```

### Issue: Migration fails
**Solution**: 
- Check database connection settings in `.env`
- Ensure old tables exist before migrating
- Run migration in steps (see script comments)

### Issue: Performance issues
**Solution**:
- Check that indexes were created (see `setup_flexible_nutrients.py`)
- Consider caching user preferences
- Optimize queries if needed

---

## 📝 Next Steps After Implementation

1. **Add UI/API** for users to configure their nutrient preferences
2. **Add validation** to ensure nutrient values are reasonable
3. **Add reporting** to show nutrient trends over time
4. **Add notifications** when users exceed limits
5. **Add nutrient goals** (minimums, not just maximums)
6. **Add nutrient recommendations** based on user profile

---

## 📚 Additional Resources

- **Design Document**: `FLEXIBLE_NUTRIENT_TRACKING_DESIGN.md` - Complete technical design
- **Migration Script**: `setup_flexible_nutrients.py` - Database setup
- **Utilities**: `nutrient_utils.py` - Helper functions

---

## ✅ Success Criteria

Your implementation is successful when:
1. ✅ Users can track any combination of nutrients
2. ✅ Meal logs store nutrient values dynamically
3. ✅ Today's totals and remaining limits work correctly
4. ✅ All agents work with the flexible system
5. ✅ No data loss during migration
6. ✅ System performs well with multiple users and nutrients

---

**Good luck with your implementation!** 🚀

If you encounter issues, refer to the design document or check the troubleshooting section above.
