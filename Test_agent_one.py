from agent_one import log_food_intake

# TEST DATA: User 1 ate a "Greek Yogurt"
# Parameters: user_id, food_name, cal, protein, sugar, sodium
result = log_food_intake(1, "Greek Yogurt", 150, 15, 5, 60)

print(f"Database Response: {result}")