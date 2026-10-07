-- Diagnostic Query: Check what meal logs exist for User 1 today
-- Run this to verify if data was actually cleared

-- 1. Check all meal logs for User 1 today
SELECT 
    ml.log_id,
    ml.user_id,
    ml.food_name,
    ml.log_time,
    CAST(ml.log_time AS DATE) as log_date,
    CAST(GETDATE() AS DATE) as today_date,
    CASE 
        WHEN CAST(ml.log_time AS DATE) = CAST(GETDATE() AS DATE) THEN 'TODAY'
        ELSE 'NOT TODAY'
    END as date_match
FROM meal_logs ml
WHERE ml.user_id = 1
ORDER BY ml.log_time DESC;

-- 2. Check nutrient values for User 1 today
SELECT 
    ml.log_id,
    ml.food_name,
    ml.log_time,
    n.nutrient_name,
    mln.value
FROM meal_log_nutrients mln
JOIN meal_logs ml ON mln.log_id = ml.log_id
JOIN nutrients n ON mln.nutrient_id = n.nutrient_id
WHERE ml.user_id = 1
  AND CAST(ml.log_time AS DATE) = CAST(GETDATE() AS DATE)
ORDER BY ml.log_time DESC, n.nutrient_name;

-- 3. Calculate totals (same as the function does)
SELECT 
    n.nutrient_name,
    COALESCE(SUM(mln.value), 0) as total_consumed
FROM nutrients n
LEFT JOIN meal_log_nutrients mln ON n.nutrient_id = mln.nutrient_id
LEFT JOIN meal_logs ml ON mln.log_id = ml.log_id 
    AND ml.user_id = 1
    AND CAST(ml.log_time AS DATE) = CAST(GETDATE() AS DATE)
WHERE n.nutrient_name IN ('calories', 'protein', 'carbs', 'fat')
GROUP BY n.nutrient_id, n.nutrient_name;

-- 4. Check if there are ANY meal logs for User 1 (regardless of date)
SELECT COUNT(*) as total_meal_logs
FROM meal_logs
WHERE user_id = 1;

-- 5. Check the most recent meal log date for User 1
SELECT 
    MAX(CAST(log_time AS DATE)) as most_recent_date,
    CAST(GETDATE() AS DATE) as today_date
FROM meal_logs
WHERE user_id = 1;
