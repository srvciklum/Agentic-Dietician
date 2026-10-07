# SQL Queries for Flexible Nutrient Tracking System

Use these queries to check and verify your database data.

---

## 1. Check User Nutrient Preferences

### View all nutrients a user is tracking:
```sql
SELECT 
    u.user_id,
    u.username,
    n.nutrient_name,
    n.display_name,
    n.unit,
    unp.daily_limit,
    unp.is_active,
    unp.created_at
FROM user_nutrient_preferences unp
JOIN users u ON unp.user_id = u.user_id
JOIN nutrients n ON unp.nutrient_id = n.nutrient_id
WHERE u.user_id = 1  -- Change user_id as needed
ORDER BY n.nutrient_name;
```

### Count nutrients per user:
```sql
SELECT 
    u.user_id,
    u.username,
    COUNT(unp.nutrient_id) as nutrients_tracked
FROM users u
LEFT JOIN user_nutrient_preferences unp ON u.user_id = unp.user_id AND unp.is_active = 1
GROUP BY u.user_id, u.username;
```

---

## 2. Check Meal Logs

### View all meal logs for a user:
```sql
SELECT 
    ml.log_id,
    ml.user_id,
    ml.food_name,
    ml.log_time,
    CAST(ml.log_time AS DATE) as log_date
FROM meal_logs ml
WHERE ml.user_id = 1  -- Change user_id as needed
ORDER BY ml.log_time DESC;
```

### View today's meal logs:
```sql
SELECT 
    ml.log_id,
    ml.user_id,
    ml.food_name,
    ml.log_time
FROM meal_logs ml
WHERE ml.user_id = 1
  AND CAST(ml.log_time AS DATE) = CAST(GETDATE() AS DATE)
ORDER BY ml.log_time DESC;
```

---

## 3. Check Meal Log Nutrients

### View nutrient values for all meals:
```sql
SELECT 
    ml.log_id,
    ml.user_id,
    ml.food_name,
    ml.log_time,
    n.nutrient_name,
    n.display_name,
    n.unit,
    mln.value
FROM meal_log_nutrients mln
JOIN meal_logs ml ON mln.log_id = ml.log_id
JOIN nutrients n ON mln.nutrient_id = n.nutrient_id
WHERE ml.user_id = 1  -- Change user_id as needed
ORDER BY ml.log_time DESC, n.nutrient_name;
```

### View nutrient values for a specific meal:
```sql
SELECT 
    n.nutrient_name,
    n.display_name,
    n.unit,
    mln.value
FROM meal_log_nutrients mln
JOIN nutrients n ON mln.nutrient_id = n.nutrient_id
WHERE mln.log_id = 1  -- Change log_id as needed
ORDER BY n.nutrient_name;
```

---

## 4. Calculate Today's Totals

### Today's total consumed nutrients for a user:
```sql
SELECT 
    n.nutrient_name,
    n.display_name,
    n.unit,
    COALESCE(SUM(mln.value), 0) as total_consumed
FROM nutrients n
LEFT JOIN meal_log_nutrients mln ON n.nutrient_id = mln.nutrient_id
LEFT JOIN meal_logs ml ON mln.log_id = ml.log_id 
    AND ml.user_id = 1  -- Change user_id as needed
    AND CAST(ml.log_time AS DATE) = CAST(GETDATE() AS DATE)
WHERE n.nutrient_id IN (
    SELECT nutrient_id 
    FROM user_nutrient_preferences 
    WHERE user_id = 1 AND is_active = 1
)
GROUP BY n.nutrient_id, n.nutrient_name, n.display_name, n.unit
ORDER BY n.nutrient_name;
```

---

## 5. Calculate Remaining Limits

### Remaining daily limits (can be negative if exceeded):
```sql
SELECT 
    n.nutrient_name,
    n.display_name,
    n.unit,
    unp.daily_limit,
    COALESCE(SUM(mln.value), 0) as total_consumed_today,
    unp.daily_limit - COALESCE(SUM(mln.value), 0) as remaining
FROM user_nutrient_preferences unp
JOIN nutrients n ON unp.nutrient_id = n.nutrient_id
LEFT JOIN meal_log_nutrients mln ON n.nutrient_id = mln.nutrient_id
LEFT JOIN meal_logs ml ON mln.log_id = ml.log_id 
    AND ml.user_id = unp.user_id
    AND CAST(ml.log_time AS DATE) = CAST(GETDATE() AS DATE)
WHERE unp.user_id = 1  -- Change user_id as needed
  AND unp.is_active = 1
GROUP BY n.nutrient_id, n.nutrient_name, n.display_name, n.unit, unp.daily_limit
ORDER BY n.nutrient_name;
```

---

## 6. Check for Exceeded Limits

### Find nutrients where user has exceeded daily limits:
```sql
SELECT 
    n.nutrient_name,
    n.display_name,
    n.unit,
    unp.daily_limit,
    COALESCE(SUM(mln.value), 0) as total_consumed_today,
    unp.daily_limit - COALESCE(SUM(mln.value), 0) as remaining,
    CASE 
        WHEN COALESCE(SUM(mln.value), 0) > unp.daily_limit 
        THEN COALESCE(SUM(mln.value), 0) - unp.daily_limit 
        ELSE 0 
    END as exceeded_by
FROM user_nutrient_preferences unp
JOIN nutrients n ON unp.nutrient_id = n.nutrient_id
LEFT JOIN meal_log_nutrients mln ON n.nutrient_id = mln.nutrient_id
LEFT JOIN meal_logs ml ON mln.log_id = ml.log_id 
    AND ml.user_id = unp.user_id
    AND CAST(ml.log_time AS DATE) = CAST(GETDATE() AS DATE)
WHERE unp.user_id = 1  -- Change user_id as needed
  AND unp.is_active = 1
GROUP BY n.nutrient_id, n.nutrient_name, n.display_name, n.unit, unp.daily_limit
HAVING COALESCE(SUM(mln.value), 0) > unp.daily_limit
ORDER BY exceeded_by DESC;
```

---

## 7. View All Available Nutrients

### List all nutrients in the system:
```sql
SELECT 
    nutrient_id,
    nutrient_name,
    display_name,
    unit,
    is_default
FROM nutrients
ORDER BY is_default DESC, display_name ASC;
```

---

## 8. Daily Summary Report

### Complete daily summary for a user:
```sql
SELECT 
    u.user_id,
    u.username,
    n.nutrient_name,
    n.display_name,
    n.unit,
    unp.daily_limit as daily_limit,
    COALESCE(SUM(mln.value), 0) as consumed_today,
    unp.daily_limit - COALESCE(SUM(mln.value), 0) as remaining,
    CASE 
        WHEN COALESCE(SUM(mln.value), 0) > unp.daily_limit THEN 'EXCEEDED'
        WHEN COALESCE(SUM(mln.value), 0) = unp.daily_limit THEN 'REACHED'
        ELSE 'UNDER'
    END as status
FROM users u
JOIN user_nutrient_preferences unp ON u.user_id = unp.user_id
JOIN nutrients n ON unp.nutrient_id = n.nutrient_id
LEFT JOIN meal_log_nutrients mln ON n.nutrient_id = mln.nutrient_id
LEFT JOIN meal_logs ml ON mln.log_id = ml.log_id 
    AND ml.user_id = u.user_id
    AND CAST(ml.log_time AS DATE) = CAST(GETDATE() AS DATE)
WHERE u.user_id = 1  -- Change user_id as needed
  AND unp.is_active = 1
GROUP BY u.user_id, u.username, n.nutrient_id, n.nutrient_name, n.display_name, n.unit, unp.daily_limit
ORDER BY n.nutrient_name;
```

---

## 9. Meal History with Nutrients

### View meal history with all nutrient values:
```sql
SELECT 
    ml.log_id,
    ml.user_id,
    ml.food_name,
    ml.log_time,
    STRING_AGG(
        CONCAT(n.nutrient_name, ': ', CAST(mln.value AS VARCHAR), ' ', n.unit), 
        ', '
    ) WITHIN GROUP (ORDER BY n.nutrient_name) as nutrients
FROM meal_logs ml
LEFT JOIN meal_log_nutrients mln ON ml.log_id = mln.log_id
LEFT JOIN nutrients n ON mln.nutrient_id = n.nutrient_id
WHERE ml.user_id = 1  -- Change user_id as needed
GROUP BY ml.log_id, ml.user_id, ml.food_name, ml.log_time
ORDER BY ml.log_time DESC;
```

---

## 10. Verify Data Integrity

### Check for orphaned records:
```sql
-- Check for meal_log_nutrients without corresponding meal_logs
SELECT mln.log_id, COUNT(*) as orphaned_count
FROM meal_log_nutrients mln
LEFT JOIN meal_logs ml ON mln.log_id = ml.log_id
WHERE ml.log_id IS NULL
GROUP BY mln.log_id;

-- Check for user_nutrient_preferences with invalid nutrient_id
SELECT unp.preference_id, unp.user_id, unp.nutrient_id
FROM user_nutrient_preferences unp
LEFT JOIN nutrients n ON unp.nutrient_id = n.nutrient_id
WHERE n.nutrient_id IS NULL;
```

---

## Quick Test Queries

### Test User 1's current status:
```sql
-- Quick status check
SELECT 
    n.nutrient_name,
    unp.daily_limit,
    COALESCE(SUM(mln.value), 0) as consumed,
    unp.daily_limit - COALESCE(SUM(mln.value), 0) as remaining
FROM user_nutrient_preferences unp
JOIN nutrients n ON unp.nutrient_id = n.nutrient_id
LEFT JOIN meal_log_nutrients mln ON n.nutrient_id = mln.nutrient_id
LEFT JOIN meal_logs ml ON mln.log_id = ml.log_id 
    AND ml.user_id = 1
    AND CAST(ml.log_time AS DATE) = CAST(GETDATE() AS DATE)
WHERE unp.user_id = 1 AND unp.is_active = 1
GROUP BY n.nutrient_name, unp.daily_limit;
```

---

## Notes

- Replace `user_id = 1` with the user ID you want to check
- Replace `log_id = 1` with the specific meal log ID
- `CAST(GETDATE() AS DATE)` gets today's date in SQL Server
- Negative `remaining` values mean the user exceeded their limit
- Use these queries to debug and verify your system is working correctly
