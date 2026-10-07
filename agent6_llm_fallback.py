import json
import time
import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# --- AZURE CONFIGURATION ---
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1")

_CANNOT_ESTIMATE = {"error": "cannot estimate", "needs_user_breakdown": True}


def _parse_json_content(result_text: str):
    result_text = (result_text or "").strip()
    if result_text.startswith("```json"):
        result_text = result_text[7:-3].strip()
    elif result_text.startswith("```"):
        result_text = result_text[3:-3].strip()
    return json.loads(result_text)


def _identify_food(food_name: str) -> dict:
    """
    Gate 1: Can the LLM recognize this as a real food?
    Returns {known: bool, reason?: str}
    """
    response = client.chat.completions.create(
        model=DEPLOYMENT_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You identify whether a food name is a real, recognizable food or drink "
                    "(including common branded products). "
                    "Respond ONLY with JSON: "
                    '{"known": true/false, "canonical_name": "..."}. '
                    "Set known=false for made-up words, nonsense, unknown slang, or anything "
                    "you cannot confidently identify. Do not guess."
                ),
            },
            {"role": "user", "content": f"Food name: {food_name}"},
        ],
        temperature=0.0,
        max_completion_tokens=80,
    )
    return _parse_json_content(response.choices[0].message.content)


def estimate_nutrition(food_name, qty, tracked_nutrients=None):
    start_time = time.time()

    if tracked_nutrients:
        nutrient_list = ", ".join(tracked_nutrients)
        nutrient_instruction = f"Estimate these nutrients: {nutrient_list}. "
    else:
        nutrient_list = "calories, protein, carbs, fat, fiber, sodium, potassium"
        nutrient_instruction = f"Estimate these common nutrients: {nutrient_list}. "

    try:
        # --- Step A: identify via LLM ---
        identity = _identify_food(food_name)
        print(f"[Agent 6] Food identity check: {json.dumps(identity)}")
        if not identity.get("known", False):
            parsed_data = dict(_CANNOT_ESTIMATE)
            parsed_data["reason"] = identity.get("reason") or "unrecognized food"
            execution_time = round((time.time() - start_time) * 1000, 2)
            print("\n--- AGENT 6: LLM NUTRITION FALLBACK ---")
            print(f"Execution Speed : {execution_time} ms")
            print(f"Action          : Unrecognized food '{food_name}' — ask user for breakdown")
            print(f"JSON Payload    : {json.dumps(parsed_data)}")
            print("---------------------------------------")
            return json.dumps(parsed_data)

        canonical = identity.get("canonical_name") or food_name

        # --- Step B: estimate only if known ---
        system_prompt = (
            "You are an expert nutritional database. "
            f"Estimate total nutrition for the EXACT quantity of a recognized food. "
            f"{nutrient_instruction}"
            "CRITICAL RULES: "
            "1. Respond ONLY with a valid JSON object. No markdown, no extra text. "
            f"2. Format: {{\"calories\": 100, \"protein\": 5, \"carbs\": 10, \"fat\": 2, ...}}. "
            "3. All values must be numbers. "
            "4. Units: calories kcal; protein/carbs/fat/fiber g; sodium/potassium/calcium mg. "
            "5. If still unsure, return exactly: "
            "{\"error\": \"cannot estimate\", \"needs_user_breakdown\": true}."
        )
        user_prompt = f"Food: {canonical}\nQuantity: {qty}"

        response = client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )

        parsed_data = _parse_json_content(response.choices[0].message.content)

        if isinstance(parsed_data, dict) and "error" not in parsed_data:
            numeric = [
                v for k, v in parsed_data.items()
                if k != "allergens" and isinstance(v, (int, float))
            ]
            if not numeric:
                parsed_data = dict(_CANNOT_ESTIMATE)

    except Exception as e:
        parsed_data = {
            "error": f"LLM estimation failed: {str(e)}",
            "needs_user_breakdown": True,
        }

    execution_time = round((time.time() - start_time) * 1000, 2)
    print("\n--- AGENT 6: LLM NUTRITION FALLBACK ---")
    print(f"Execution Speed : {execution_time} ms")
    print(f"Action          : LLM path for '{qty} {food_name}'")
    print(f"JSON Payload    : {json.dumps(parsed_data)}")
    print("---------------------------------------")

    return json.dumps(parsed_data)
