import spacy
import json
import time
import re

print("Loading spaCy NLP Model (Agent 1)...")
nlp = spacy.load("en_core_web_sm")

# Words that are not food names
FOOD_STOPWORDS = {
    "i", "me", "my", "a", "an", "the", "some", "any", "just", "today", "now",
    "ate", "eat", "eaten", "had", "have", "finished", "consumed", "drank", "drink",
    "food", "meal", "snack", "item", "please", "also",
    # Meta words from "find similar / within limits" questions — not dish names
    "similar", "alternative", "alternatives", "option", "options", "compare",
    "comparison", "limit", "limits", "breach", "breaches", "exceed", "exceeds",
    "remaining", "daily", "find", "suggest", "suggestion", "safer", "better",
    "another", "other", "instead", "want", "need", "help", "question",
}


def _suggested_unit_hint(food_name: str) -> str:
    """Suggest a quantity unit style based on food type."""
    f = (food_name or "").lower()
    liquid_keywords = [
        "milk", "water", "juice", "coffee", "tea", "soda", "cola", "smoothie",
        "shake", "milkshake", "soup", "broth", "beer", "wine", "drink", "beverage", "oil",
    ]
    powder_keywords = [
        "powder", "supplement", "protein powder", "creatine", "vitamin", "salt", "sugar",
    ]
    slice_keywords = ["pizza", "bread", "toast", "cake", "pie", "cheese", "ham"]

    if any(k in f for k in liquid_keywords):
        return "ml or cups"
    if any(k in f for k in powder_keywords):
        return "mg, g, or scoops"
    if any(k in f for k in slice_keywords):
        return "slices, pieces, or grams"
    return "grams, pieces, cups, or ml (whichever fits)"


def extract_food_and_qty(user_input):
    start_time = time.time()
    doc = nlp(user_input.lower())

    # --- INTENT DETECTION ---
    inquiry_keywords = [
        "can i", "should i", "what if", "how many", "is it safe", "could i",
        "will that", "would that", "thinking about", "considering", "planning to",
        "ruin my", "affect my", "impact my", "fit in", "work with", "will it",
        "similar food", "similar dish", "find a similar", "find similar",
        "alternative", "another option", "safer option", "won't breach",
        "will not breach", "not breach", "within my limit", "within limits",
        "under my limit", "won't exceed", "will not exceed", "does not exceed",
        "stay within", "without exceeding", "compare",
    ]
    confirmation_keywords = [
        "that's fine", "that's ok", "ok", "yes", "sure", "log it",
        "i just finished", "i finished", "i ate it", "done",
    ]

    intent = "log"
    user_lower = user_input.lower()

    for kw in inquiry_keywords:
        if kw in user_lower:
            intent = "inquire"
            break

    for kw in confirmation_keywords:
        if kw in user_lower:
            intent = "log"
            break

    fractions = {
        "half": "0.5", "quarter": "0.25", "a": "1", "an": "1",
        "one": "1", "two": "2", "three": "3",
    }
    measurement_units = [
        "g", "grams", "gram", "mg", "milligram", "milligrams",
        "oz", "ounce", "ounces", "ml", "milliliter", "milliliters",
        "liter", "liters", "cup", "cups", "tbsp", "tsp",
        "tablespoon", "teaspoon", "scoop", "scoops",
        "slice", "slices", "piece", "pieces", "bowl", "bowls",
        "handful", "pinch", "plate",
    ]
    strict_math_units = ["g", "grams", "gram", "mg", "oz", "ounce", "ounces", "ml", "kg", "lbs"]

    quantity_parts = []
    food_parts = []
    has_number = False
    has_unit = False
    prev_was_food_noun = False

    for token in doc:
        text = token.text
        lemma = token.lemma_

        if token.pos_ == "NUM" or text in fractions:
            val = fractions.get(text, text)
            if val not in quantity_parts:
                quantity_parts.append(val)
            has_number = True
            prev_was_food_noun = False
        elif lemma in measurement_units or text in measurement_units:
            # "rice bowl" / "soup plate" — container is part of the dish unless a number came first
            if lemma in ("bowl", "bowls", "plate", "plates") and not has_number:
                if text not in FOOD_STOPWORDS and lemma not in FOOD_STOPWORDS:
                    food_parts.append(text)
                    prev_was_food_noun = True
                else:
                    prev_was_food_noun = False
            else:
                quantity_parts.append(text)
                has_unit = True
                prev_was_food_noun = False
        elif token.pos_ in ["NOUN", "PROPN", "ADJ"]:
            if text not in FOOD_STOPWORDS and lemma not in FOOD_STOPWORDS:
                food_parts.append(text)
                prev_was_food_noun = token.pos_ in ["NOUN", "PROPN"]
            else:
                prev_was_food_noun = False
        elif token.pos_ == "VERB" and prev_was_food_noun:
            # Keep compound food names spaCy tags as verbs (e.g. "milk shake")
            if text not in FOOD_STOPWORDS and lemma not in measurement_units:
                food_parts.append(text)
            prev_was_food_noun = False
        else:
            prev_was_food_noun = False

    container_food_words = {"bowl", "bowls", "plate", "plates"}
    filtered_food = [
        f
        for f in food_parts
        if f not in strict_math_units
        and (f not in measurement_units or f in container_food_words)
    ]
    food_item = " ".join(filtered_food) if filtered_food else "Unknown"
    # Normalize common split compounds
    food_item = food_item.replace("milk shake", "milkshake").replace("ice cream", "ice cream")

    # "find a similar food that won't breach limits" has no dish name — use previous food
    alternative_request = any(
        p in user_lower
        for p in (
            "similar food",
            "similar dish",
            "find a similar",
            "find similar",
            "alternative",
            "another option",
            "safer option",
            "won't breach",
            "will not breach",
            "within my limit",
            "within limits",
            "won't exceed",
            "stay within",
        )
    )
    if alternative_request and (
        food_item == "Unknown"
        or all(w in FOOD_STOPWORDS for w in food_item.split())
        or food_item in ("similar limits", "similar limit", "limits", "similar")
    ):
        food_item = "[PREVIOUS_FOOD]"
        intent = "inquire"

    # Real quantity only if user gave a number and/or an explicit unit.
    quantity_specified = bool(quantity_parts) and (has_number or has_unit)
    # "I ate a banana" (article only, no unit) is NOT a real quantity
    if quantity_parts == ["1"] and not has_unit and re.search(r"\b(a|an)\b", user_lower):
        quantity_specified = False

    quantity = " ".join(quantity_parts) if quantity_specified else ""

    if intent == "log" and food_item == "Unknown":
        confirmation_phrases = [
            "that's fine", "that's ok", "ok", "yes", "sure",
            "i just finished", "i finished", "i ate it", "done",
        ]
        if any(phrase in user_lower for phrase in confirmation_phrases):
            food_item = "[PREVIOUS_FOOD]"

    qty_only_reply = quantity_specified and food_item == "Unknown"

    payload = {
        "Food": food_item,
        "Qty": quantity if quantity else None,
        "Intent": intent,
        "Quantity_Specified": quantity_specified,
        "Quantity_Only_Reply": qty_only_reply,
        "Suggested_Unit_Hint": (
            _suggested_unit_hint(food_item)
            if food_item not in ("Unknown", "[PREVIOUS_FOOD]")
            else "grams, ml, or pieces"
        ),
    }

    execution_time = round((time.time() - start_time) * 1000, 2)

    print("\n--- AGENT 1: EXTRACTOR ---")
    print(f"Execution Speed : {execution_time} ms")
    print(f"Action          : Detected Intent -> {intent.upper()}")
    print(f"JSON Payload    : {json.dumps(payload)}")
    print("--------------------------\n")

    return json.dumps(payload)
