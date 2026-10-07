"""
Shared Agentic Dietician orchestrator core.
Used by both the CLI (agentic_main.py) and the HTTP API (api_server.py).
"""
from __future__ import annotations

import json
import os
import re
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import AzureChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

load_dotenv()

import agent1_extractor
import agent2_resolver
import agent3_calculator
import agent4_guardrail
import agent5_synthesizer
import agent6_llm_fallback
from nutrient_utils import get_today_nutrient_totals, get_user_tracked_nutrients

# Per-request user id (safe for concurrent API calls)
_active_user_id: ContextVar[int] = ContextVar("active_user_id", default=1)


def get_active_user_id() -> int:
    return _active_user_id.get()


def parse_user_id(raw: str | int) -> int:
    """Accept 1, '1', 'P-001', 'P-1' -> int user id."""
    if isinstance(raw, int):
        return raw
    text = str(raw).strip().upper()
    digits = re.findall(r"\d+", text)
    if not digits:
        raise ValueError(f"Invalid user id: {raw}")
    return int(digits[-1])


# --- TOOLS ---

@tool
def analyze_user_text(user_text: str):
    """
    Call this tool FIRST with the exact raw text the user typed.
    Returns JSON with Food, Qty, Intent, Quantity_Specified, Quantity_Only_Reply, Suggested_Unit_Hint.
    If Quantity_Specified is false, ask the user for quantity before continuing the pipeline.
    If Quantity_Only_Reply is true, combine Qty with the pending food from the previous question.
    """
    print(f"\n[Tool Execution] Agent 1: Extracting intent and entities...")
    return agent1_extractor.extract_food_and_qty(user_text)


@tool
def search_food_database(food_name: str, quantity: str, intent: str):
    """
    Call this tool SECOND to search the vector database for a food item's macros.
    """
    print(f"\n[Tool Execution] Agent 2: Searching Vector DB for '{food_name}'...")
    payload = json.dumps({"Food": food_name, "Qty": quantity, "Intent": intent})
    return agent2_resolver.resolve_nutrition(payload)


@tool
def estimate_macros_with_ai(food_name: str, quantity: str):
    """
    Call this tool THIRD if the local vector database fails to find the food.
    This uses a cloud LLM to estimate nutritional values for all common nutrients.
    """
    print(f"\n[Tool Execution] Agent 6: Estimating nutrition for '{quantity} {food_name}'...")
    return agent6_llm_fallback.estimate_nutrition(food_name, quantity)


def _process_and_log_meal_internal(food_name: str, qty, intent: str, agent2_response_json: str):
    user_id = get_active_user_id()
    print(f"\n[Tool Execution] Agents 3 & 4: Nutrients & Guardrails for User {user_id}...")
    qty_display = str(qty).strip() if qty is not None else "1"

    try:
        agent_response = (
            json.loads(agent2_response_json)
            if isinstance(agent2_response_json, str)
            else agent2_response_json
        )

        nutrition_is_total = False
        if "Base_Nutrition_Per_100g" in agent_response:
            nutrition_dict = agent_response["Base_Nutrition_Per_100g"]
            ingredients = agent_response.get("Ingredients_Breakdown", [food_name])
            matched_food = agent_response.get("Matched_Food", food_name)
            qty_for_agent3 = str(agent_response.get("User_Requested_Qty") or qty_display)
        elif "error" in agent_response:
            nutrition_dict = {}
            ingredients = [food_name]
            matched_food = food_name
            qty_for_agent3 = qty_display
        else:
            # Agent 6 returns totals for the requested quantity already
            nutrition_dict = agent_response
            ingredients = [food_name]
            matched_food = food_name
            qty_for_agent3 = "1"
            nutrition_is_total = True
            # Keep human-readable amount for the reply (e.g. "1000 ml")
            qty_display = qty_display if qty_display and qty_display != "1" else qty_display
    except Exception as e:
        print(f"Warning: Could not parse nutrition data: {e}")
        nutrition_dict = {}
        ingredients = [food_name]
        matched_food = food_name
        qty_for_agent3 = qty_display
        nutrition_is_total = False

    payload = {
        "Matched_Food": matched_food,
        "User_Requested_Qty": qty_for_agent3,
        "Display_Qty": qty_display,
        "Nutrition_Is_Total": nutrition_is_total,
        "Intent": intent,
        "Base_Nutrition_Per_100g": nutrition_dict,
        "Ingredients_Breakdown": ingredients,
    }

    agent3_result = agent3_calculator.calculate_final_macros(json.dumps(payload), user_id)
    return agent4_guardrail.run_safety_checks(agent3_result)


@tool
def process_and_log_meal(food_name: str, qty: str, intent: str, agent2_response_json: str):
    """
    Calculate nutrients, apply medical guardrails, and optionally log the meal.
    Pass qty as the full quantity string (e.g. '1000 ml', '2 slices'), not just a number.
    Pass the FULL JSON from search_food_database or estimate_macros_with_ai.
    """
    return _process_and_log_meal_internal(food_name, qty, intent, agent2_response_json)


@tool
def combine_nutrition_data(nutrition_json_list: str):
    """Combine multiple food nutrition JSON objects into one payload."""
    print(f"\n[Tool Execution] Combining nutrition data for multiple foods...")
    try:
        items = json.loads(nutrition_json_list)
        combined = {}
        all_ingredients = []
        food_names = []

        for item in items:
            if isinstance(item, str):
                item = json.loads(item)
            if "error" in item:
                continue
            food_names.append(item.get("Matched_Food", item.get("Food", "food")))
            nuts = item.get("Base_Nutrition_Per_100g", item)
            for k, v in nuts.items():
                if k in ("allergens",) or not isinstance(v, (int, float)):
                    continue
                combined[k] = combined.get(k, 0) + v
            ings = item.get("Ingredients_Breakdown", [])
            if isinstance(ings, list):
                all_ingredients.extend(ings)

        return json.dumps(
            {
                "Matched_Food": " + ".join(food_names) if food_names else "combined meal",
                "Ingredients_Breakdown": all_ingredients,
                "Base_Nutrition_Per_100g": combined,
            }
        )
    except Exception as e:
        return json.dumps({"error": f"Failed to combine nutrition: {e}"})


@tool
def log_previous_food(food_name: str, qty: str, agent2_response_json: str):
    """Log a previously inquired food (intent=log). Pass qty as full string e.g. '1000 ml'."""
    return _process_and_log_meal_internal(food_name, qty, "log", agent2_response_json)


@tool
def apply_user_provided_nutrition(
    food_name: str,
    quantity: str,
    intent: str,
    calories: float,
    protein: float,
    carbs: float,
    fat: float,
    fiber: float = 0.0,
    sodium: float = 0.0,
    potassium: float = 0.0,
):
    """
    Use when the user provides nutritional breakdown for an unknown food.
    Pass the values they stated for that quantity (totals for the amount eaten, not per 100g).
    """
    print(f"\n[Tool Execution] Applying user-provided nutrition for '{quantity} {food_name}'...")
    nutrition = {
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
    }
    if fiber:
        nutrition["fiber"] = fiber
    if sodium:
        nutrition["sodium"] = sodium
    if potassium:
        nutrition["potassium"] = potassium
    return _process_and_log_meal_internal(
        food_name,
        quantity,
        intent,
        json.dumps(nutrition),
    )


@tool
def format_final_response(agent4_json_string: str):
    """Format the final natural-language reply for the user."""
    print(f"\n[Tool Execution] Agent 5: Synthesizing final response...")
    return agent5_synthesizer.synthesize_response(agent4_json_string)


llm = AzureChatOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    temperature=0.0,
)

system_message = """You are a helpful dietary assistant that maintains conversation context. Always address the user as "you".

CONTEXT AWARENESS - CRITICAL:
- If the user says something like "that's fine", "I just finished eating", "log it", "yes", or similar confirmations AFTER an inquiry, they want to LOG the food from the PREVIOUS inquiry.
- In that case, use `log_previous_food` with the food_name, qty, and agent2_response_json from the PREVIOUS conversation turn.
- DO NOT ask for clarification if the context is clear - just log it!
- Remember the last dish from a photo upload (Dish: ...) as the pending food for follow-up questions.

FOOD PHOTO ANALYSIS - CRITICAL:
- If the user message includes a section titled "FOOD PHOTO ANALYSIS (Gemini)", a meal photo was already analyzed.
- Use the user's own words for Intent (log vs inquire) via `analyze_user_text` on their stated request.
- Prefer the photo analysis for food items, portion, and calories/protein/carbs/fat.
- When the photo analysis includes approximate macros, call `apply_user_provided_nutrition` with those totals
  (do NOT invent different numbers; do NOT require searching the DB first for photo-backed meals).
- If multiple foods are clearly separated with their own macros in the photo analysis, you may call
  `apply_user_provided_nutrition` once per food OR combine into one log using the combined totals —
  prefer one call with the primary meal / combined plate totals when that matches the user's request.
- Then call `format_final_response`.

SIMILAR / ALTERNATIVE FOOD REQUESTS - CRITICAL:
- If the user asks for a similar food that will not breach / exceed their limits (or Food is [PREVIOUS_FOOD]):
  - Intent is inquire. Do NOT log anything unless they clearly ask to log afterward.
  - Use the previous dish from this conversation (photo Dish or last discussed food) as the reference.
  - If there is no previous dish, ask only: "Which food should I find a similar option for?"
  - If you need a serving size for the comparison, ask a clear question that NAMES the dish, e.g.
    "For the comparison, how much **vegetable rice bowl** should I use — for example 200 g, 1 bowl, or 1 cup?"
  - Never ask vague questions like "How much of the food..." without naming the dish.
  - Suggest or look up a similar option and run an inquire (not log). Explain projected remaining limits.
  - Never substitute and silently log an unrelated dish (e.g. Pad Thai) when they asked for a comparison.

MISSING QUANTITY - CRITICAL:
- After `analyze_user_text`, check Quantity_Specified.
- If Food is Unknown or [PREVIOUS_FOOD] and there is no clear pending dish in context:
  - Ask for the food name first (do not ask only for quantity).
- If Intent is "log" or "inquire", Food is a real food name, and Quantity_Specified is false:
  - DO NOT call search_food_database, estimate_macros_with_ai, or process_and_log_meal yet.
  - Reply directly (no tools after analyze) asking how much, ALWAYS naming the food:
    e.g. "How much banana did you eat — for example 1 piece, 100 g, or 1 cup?"
  - Remember the food name for the next turn.
- When the user replies with a quantity, use the FULL pending food name from your previous question
  (e.g. "vanilla milkshake", not a shortened form) and the FULL quantity string (e.g. "1000 ml").
- Always pass qty to tools as a string including units when the user provided units.
- If Quantity_Only_Reply is true (user answered with only an amount like "200 ml" or "2 slices"):
  - Use the PENDING food from your previous quantity question as food_name.
  - If you do not actually know the pending food, ask for the food name — do not invent one.
  - Use their reply as quantity (full string with units).
  - Then continue the normal pipeline below (inquire stays inquire; log stays log).

For NEW food mentions WITH quantity (Quantity_Specified true) and NO photo analysis section:
1. ALWAYS call `analyze_user_text` first.
2. Use the extracted food name and quantity to call `search_food_database`.
3. IF `search_food_database` returns an "error" key, IMMEDIATELY call `estimate_macros_with_ai`
   (LLM checks whether it recognizes the food, then estimates only if known).
4. IF `estimate_macros_with_ai` returns an "error" or needs_user_breakdown=true:
   - The food was not in DB and the LLM could not identify/estimate it.
   - DO NOT invent nutrition and DO NOT call process_and_log_meal.
   - Reply directly asking the user for the nutritional breakdown for that exact quantity.
   - Ask at least for: calories (kcal), protein (g), carbs (g), and fat (g).
   - Example: "I couldn't find kochansh in my database or recognize it. For 40 ml, please share calories, protein (g), carbs (g), and fat (g)."
   - Remember food_name, quantity, and intent for the next turn.
5. If the user later replies with numbers (e.g. "200 calories, 5g protein, 20g carbs, 8g fat"):
   - Call `apply_user_provided_nutrition` with those values, then `format_final_response`.
6. IF the user mentioned MULTIPLE distinct foods (e.g., "pizza and a coke"):
   - Call `search_food_database` (or `estimate_macros_with_ai`) for EACH food
   - Then call `combine_nutrition_data` with a JSON array of all those responses
   - Then call `process_and_log_meal` ONCE with the combined result
7. For SINGLE food with successful DB/AI nutrition: Pass the ENTIRE JSON to `process_and_log_meal`, then `format_final_response`.
8. Use the intent from analyze_user_text (usually "inquire" for questions, "log" for statements).

CRITICAL: When `format_final_response` returns its text, output THAT EXACT TEXT word-for-word.
When asking for quantity or a nutrition breakdown, speak naturally as you — do not call format_final_response for that ask.
"""

tools = [
    analyze_user_text,
    search_food_database,
    estimate_macros_with_ai,
    combine_nutrition_data,
    process_and_log_meal,
    log_previous_food,
    apply_user_provided_nutrition,
    format_final_response,
]
memory = MemorySaver()
agent_executor = create_react_agent(llm, tools, prompt=system_message, checkpointer=memory)


def thread_id_for_user(user_id: int, thread_id: Optional[str] = None) -> str:
    return thread_id or f"dietician_session_user_{user_id}"


def get_protocol_statuses(user_id: int) -> List[Dict[str, Any]]:
    """Build UI nutrient status cards from SQL preferences + today's totals."""
    tracked = get_user_tracked_nutrients(user_id)
    if not tracked:
        return []
    today = get_today_nutrient_totals(user_id, list(tracked.keys()))
    statuses = []
    for name, info in tracked.items():
        limit = float(info.get("limit") or 0)
        consumed = float(today.get(name, 0) or 0)
        remaining = limit - consumed
        statuses.append(
            {
                "name": info.get("display_name") or name.title(),
                "limit": limit,
                "unit": info.get("unit") or "",
                "consumed_today": round(consumed, 2),
                "remaining": round(remaining, 2),
                "is_violated": consumed > limit if limit > 0 else False,
            }
        )
    return statuses


def get_session_messages(user_id: int, thread_id: Optional[str] = None) -> List[Dict[str, str]]:
    tid = thread_id_for_user(user_id, thread_id)
    config = {"configurable": {"thread_id": tid}}
    try:
        state = agent_executor.get_state(config)
        messages = state.values.get("messages", []) if state and state.values else []
    except Exception:
        return []

    out: List[Dict[str, str]] = []
    for m in messages:
        role = getattr(m, "type", None) or getattr(m, "role", None)
        content = getattr(m, "content", None)
        if not content or not isinstance(content, str):
            continue
        if role in ("human", "user"):
            out.append({"role": "human", "content": content})
        elif role == "ai" and not getattr(m, "tool_calls", None):
            out.append({"role": "assistant", "content": content})
    return out


def process_message(
    user_id: int | str,
    message: str,
    thread_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run one user turn through the multi-agent orchestrator.
    Returns dict compatible with the UI chat API.
    """
    uid = parse_user_id(user_id)
    token = _active_user_id.set(uid)
    tid = thread_id_for_user(uid, thread_id)
    config = {"configurable": {"thread_id": tid}}

    final_ai_message = ""
    action_type = "HYPOTHETICAL"
    last_agent4: Dict[str, Any] = {}

    try:
        for event in agent_executor.stream(
            {"messages": [("user", message)]},
            config,
            stream_mode="values",
        ):
            message_obj = event["messages"][-1]

            if getattr(message_obj, "type", None) == "tool":
                try:
                    tool_data = json.loads(message_obj.content)
                    if isinstance(tool_data, dict) and "Intent" in tool_data:
                        last_agent4 = tool_data
                        intent = str(tool_data.get("Intent", "")).lower()
                        action_type = "ACTUAL" if intent == "log" else "HYPOTHETICAL"
                except Exception:
                    pass

            if getattr(message_obj, "type", None) == "ai" and message_obj.content:
                # Prefer non-empty final assistant text (after tools)
                if not getattr(message_obj, "tool_calls", None):
                    final_ai_message = message_obj.content

        statuses = get_protocol_statuses(uid)
        # For inquire, optionally show projected remaining from last agent4 payload
        if action_type == "HYPOTHETICAL" and last_agent4.get("Projected_Remaining_Limits"):
            projected = last_agent4["Projected_Remaining_Limits"]
            tracked = get_user_tracked_nutrients(uid)
            today = get_today_nutrient_totals(uid, list(tracked.keys())) if tracked else {}
            hypo_statuses = []
            for name, info in (tracked or {}).items():
                limit = float(info.get("limit") or 0)
                # UI only updates sidebar on ACTUAL; still return projected for transparency
                consumed = float(today.get(name, 0) or 0)
                remaining = float(projected.get(name, limit - consumed))
                hypo_statuses.append(
                    {
                        "name": info.get("display_name") or name.title(),
                        "limit": limit,
                        "unit": info.get("unit") or "",
                        "consumed_today": round(consumed, 2),
                        "remaining": round(remaining, 2),
                        "is_violated": remaining < 0 if limit > 0 else False,
                    }
                )
            if hypo_statuses:
                statuses = hypo_statuses

        return {
            "thread_id": tid,
            "response": final_ai_message or "I couldn't generate a response.",
            "action_type": action_type,
            "protocol_statuses": statuses,
            "debug_today_consumption": get_today_nutrient_totals(uid) or {},
        }
    finally:
        _active_user_id.reset(token)


def process_message_with_optional_image(
    user_id: int | str,
    message: str,
    thread_id: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    image_filename: str = "upload.jpg",
) -> Dict[str, Any]:
    """
    Text-only: normal workflow.
    Image without text: ask the user what they ate / want to eat (no Gemini call yet).
    Image + text: Gemini Flash breakdown, then usual agent workflow with that context.
    """
    text = (message or "").strip()
    has_image = bool(image_bytes)

    if has_image and not text:
        uid = parse_user_id(user_id)
        tid = thread_id_for_user(uid, thread_id)
        return {
            "thread_id": tid,
            "response": (
                "I see a meal photo. Please tell me what you want to do — "
                "for example \"I ate this\" or \"Can I have this?\" — and I'll analyze the photo and continue."
            ),
            "action_type": "HYPOTHETICAL",
            "protocol_statuses": get_protocol_statuses(uid),
            "debug_today_consumption": get_today_nutrient_totals(uid) or {},
        }

    if not has_image:
        return process_message(user_id, text, thread_id)

    from vision_food import (
        analyze_food_image_bytes_for_chat,
        format_photo_ingredient_breakdown,
        is_recognizable_food,
        parse_plate_total,
    )

    try:
        analysis = analyze_food_image_bytes_for_chat(image_bytes or b"", image_filename)
    except Exception as vision_err:
        uid = parse_user_id(user_id)
        tid = thread_id_for_user(uid, thread_id)
        detail = str(vision_err)
        if "high demand" in detail.lower() or "unavailable" in detail.lower() or "503" in detail:
            detail = (
                "Gemini is temporarily busy (high demand). "
                "Please wait a few seconds and send the photo again."
            )
        return {
            "thread_id": tid,
            "response": f"**Photo analysis failed**\n\n{detail}",
            "action_type": "HYPOTHETICAL",
            "protocol_statuses": get_protocol_statuses(uid),
            "debug_today_consumption": get_today_nutrient_totals(uid) or {},
        }

    if not is_recognizable_food(analysis):
        uid = parse_user_id(user_id)
        tid = thread_id_for_user(uid, thread_id)
        return {
            "thread_id": tid,
            "response": "**Not recognizable food item**\n\nPlease upload a clear photo of a meal, snack, or drink.",
            "action_type": "HYPOTHETICAL",
            "protocol_statuses": get_protocol_statuses(uid),
            "debug_today_consumption": get_today_nutrient_totals(uid) or {},
        }

    plate = parse_plate_total(analysis)
    breakdown = format_photo_ingredient_breakdown(analysis)

    # Prefer a deterministic log path so Agent 1 does not treat the whole Gemini dump as food_name
    # (that previously broke SQL inserts and left Daily Limits unchanged).
    if plate:
        uid = parse_user_id(user_id)
        token = _active_user_id.set(uid)
        tid = thread_id_for_user(uid, thread_id)
        try:
            intent = _infer_intent_from_user_text(text)
            nutrition = {
                "calories": plate["calories"],
                "protein": plate["protein"],
                "carbs": plate["carbs"],
                "fat": plate["fat"],
            }
            for nutrient, amount in (plate.get("extras") or {}).items():
                if amount:
                    nutrition[nutrient] = amount
            agent4_json = _process_and_log_meal_internal(
                plate["food"],
                plate["portion"],
                intent,
                json.dumps(nutrition),
            )
            remaining_part = agent5_synthesizer.synthesize_response(agent4_json)
            action_type = "ACTUAL" if intent == "log" else "HYPOTHETICAL"
            full_response = f"{breakdown}\n\n---\n\n{remaining_part}".strip()
            # Keep dish in agent memory so follow-ups like "find a similar food" still know it
            try:
                config = {"configurable": {"thread_id": tid}}
                agent_executor.update_state(
                    config,
                    {
                        "messages": [
                            HumanMessage(
                                content=(
                                    f"{text}\n\n"
                                    f"Photo meal recorded as Dish: {plate['food']} "
                                    f"({plate['portion']}). Intent: {intent}."
                                )
                            ),
                            AIMessage(content=full_response),
                        ]
                    },
                )
            except Exception as mem_err:
                print(f"Warning: could not sync photo turn into agent memory: {mem_err}")
            return {
                "thread_id": tid,
                "response": full_response,
                "action_type": action_type,
                "protocol_statuses": get_protocol_statuses(uid),
                "debug_today_consumption": get_today_nutrient_totals(uid) or {},
            }
        finally:
            _active_user_id.reset(token)

    # Fallback: short clean message for the ReAct agent (no giant analysis dump)
    food_hint = "meal from photo"
    enriched = (
        f"{text}\n\n"
        f"From my meal photo, treat the food as '{food_hint}'. "
        f"FOOD PHOTO ANALYSIS (Gemini):\n{analysis}\n\n"
        "Call analyze_user_text on my short request only for intent, then "
        "apply_user_provided_nutrition using the PLATE_TOTAL macros from the analysis "
        "with a SHORT food name (not the full analysis text). Keep guardrail alerts."
    )
    result = process_message(user_id, enriched, thread_id)
    remaining_part = (result.get("response") or "").strip()
    result["response"] = f"{breakdown}\n\n---\n\n{remaining_part}".strip()
    return result


def _infer_intent_from_user_text(text: str) -> str:
    """Map photo chat phrasing to log vs inquire without changing agent3/4 behavior."""
    t = (text or "").lower()
    inquire_hints = (
        "can i",
        "could i",
        "should i",
        "may i",
        "what if",
        "is it ok",
        "is it okay",
        "ok to eat",
        "okay to eat",
        "would it be",
    )
    if any(h in t for h in inquire_hints):
        return "inquire"
    return "log"
