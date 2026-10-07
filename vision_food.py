"""
Gemini vision POC: analyze a food photo for items, ingredients, portion.

Gemma helpers below are kept for reference only (not wired to API/UI).
Re-enable later by restoring analyze_food_image_bytes_gemma in api_server + UI button.
"""
import os
import re
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ServerError
from PIL import Image

# Always load project-root .env (override so a restarted server picks up new keys)
_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH, override=True)

FOOD_VISION_PROMPT = """
Analyze this image and identify all food items and drinks.
Return the response formatted as follows:
- Main Items (e.g., Pizza, Milkshake)
- Key Ingredients visible or implied
- Approximate Portion / Size (e.g., Large 12-inch, 500ml glass)
- Estimated Nutrition for the visible portion:
  Always include calories (kcal), protein (g), carbs (g), fat (g).
  Also include any other nutrients that are nutritionally significant for this specific food or drink
  (with units, e.g. mg), clearly marked as approximate.
"""

# Used when chat attaches a photo for meal logging / inquire workflow
CHAT_FOOD_VISION_PROMPT = """
First decide whether this image clearly shows edible food or drink.

If it is NOT recognizable food/drink (person, animal, landscape, furniture, packaging only,
electronics, document, empty scene, or anything that is not a meal/snack/beverage):
Return EXACTLY these two lines and nothing else:
FOOD_RECOGNIZED: no
MESSAGE: Not recognizable food item

If it IS food or drink:
Return ONLY these lines (no Main Items, ingredients list, or long narrative):
FOOD_RECOGNIZED: yes
DISH: <short dish/drink name>
PORTION: <short portion size>
NUTRIENTS: <comma-separated estimated totals, e.g. 200 kcal, 0.5 g protein, 48 g carbs, 0.2 g fat, 400 mg potassium>
PLATE_TOTAL: calories=<number>; protein_g=<number>; carbs_g=<number>; fat_g=<number>; portion=<short text>; food=<short food name>
You may append other nutrient_key=<number> values on the PLATE_TOTAL line when relevant (lowercase keys, optional _mg/_g suffix).
Keep NUTRIENTS as one compact comma-separated string. Do not add extra sections.
"""

# --- Gemma (reference only; not called from API/UI currently) ---
GEMMA_FOOD_VISION_PROMPT = """
Analyze this food image.
Provide:
- Main Items (e.g., Pizza, Milkshake)
- Key Ingredients
- Estimated Portion/Size
"""

GEMMA_PRIMARY_MODEL = "gemma-4-31b-it"
GEMMA_FALLBACK_MODEL = "gemma-4-26b-a4b-it"


def _require_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in the environment or .env file.")
    return genai.Client(api_key=api_key)


def _mime_for_path(path: Path) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(path.suffix.lower(), "image/jpeg")


def analyze_food_image(image_path: str, prompt: str | None = None) -> str:
    """
    Pass an image + prompt to Gemini Flash and return the text breakdown.
    Requires GEMINI_API_KEY in the environment / .env
    Retries briefly on temporary Gemini 503 / high-demand errors.
    """
    client = _require_gemini_client()
    img = Image.open(image_path)
    last_error: Exception | None = None

    for attempt in range(4):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=[img, prompt or FOOD_VISION_PROMPT],
            )
            return response.text or ""
        except ServerError as e:
            last_error = e
            # 503 UNAVAILABLE / high demand — wait and retry
            status = getattr(e, "status_code", None) or getattr(e, "code", None)
            msg = str(e).lower()
            if status == 503 or "unavailable" in msg or "high demand" in msg:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise

    raise RuntimeError(
        "Gemini is temporarily unavailable (high demand). Please try the photo again in a moment."
    ) from last_error


def _generate_gemma_with_image(client: genai.Client, model: str, image_path: str) -> str:
    """
    REFERENCE ONLY — not wired to API/UI.

    Gemma vision on the Gemini API is more reliable with Files API upload
    (or inline bytes) than with a raw PIL Image — PIL often returns 500 INTERNAL.
    """
    path = Path(image_path)
    uploaded = client.files.upload(
        file=str(path),
        config={"mimeType": _mime_for_path(path)},
    )
    response = client.models.generate_content(
        model=model,
        contents=[uploaded, GEMMA_FOOD_VISION_PROMPT],
        config=types.GenerateContentConfig(
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    return response.text or ""


def analyze_food_gemma(image_path: str) -> str:
    """
    REFERENCE ONLY — not wired to API/UI.

    Analyze food image with hosted Gemma 31B (gemma-4-31b-it).
    Retries on transient 500s; falls back to gemma-4-26b-a4b-it if 31B keeps failing.
    """
    client = _require_gemini_client()
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            return _generate_gemma_with_image(client, GEMMA_PRIMARY_MODEL, image_path)
        except ServerError as e:
            last_error = e
            time.sleep(1.5 * (attempt + 1))

    try:
        text = _generate_gemma_with_image(client, GEMMA_FALLBACK_MODEL, image_path)
        note = (
            f"(Note: {GEMMA_PRIMARY_MODEL} returned a temporary API error; "
            f"used {GEMMA_FALLBACK_MODEL} instead.)\n\n"
        )
        return note + text
    except Exception as fallback_error:
        raise RuntimeError(
            f"{GEMMA_PRIMARY_MODEL} failed after retries ({last_error}). "
            f"Fallback {GEMMA_FALLBACK_MODEL} also failed ({fallback_error})."
        ) from fallback_error


def analyze_food_image_gemma(image_path: str) -> str:
    """REFERENCE ONLY — alias for analyze_food_gemma."""
    return analyze_food_gemma(image_path)


def _analyze_bytes(data: bytes, filename: str, analyzer) -> str:
    """Save upload bytes to a temp file, then run the given analyzer."""
    suffix = Path(filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        return analyzer(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def analyze_food_image_bytes(data: bytes, filename: str = "upload.jpg") -> str:
    """Save upload bytes to a temp file, then analyze with Gemini Flash."""
    return _analyze_bytes(data, filename, analyze_food_image)


def analyze_food_image_bytes_for_chat(data: bytes, filename: str = "upload.jpg") -> str:
    """Gemini Flash analysis shaped for the chat meal-log workflow."""
    return _analyze_bytes(
        data,
        filename,
        lambda path: analyze_food_image(path, CHAT_FOOD_VISION_PROMPT),
    )


def format_photo_ingredient_breakdown(analysis: str) -> str:
    """
    Compact chat summary: dish name + comma-separated estimated nutrients.
    """
    text = (analysis or "").strip()
    if not text:
        return "**Dish:** _(unknown)_\n**Nutrients:** _(none)_"

    dish = None
    portion = None
    nutrients = None
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"(?i)^dish\s*:", stripped):
            dish = stripped.split(":", 1)[1].strip()
        elif re.match(r"(?i)^portion\s*:", stripped):
            portion = stripped.split(":", 1)[1].strip()
        elif re.match(r"(?i)^nutrients?\s*:", stripped):
            nutrients = stripped.split(":", 1)[1].strip()

    plate = parse_plate_total(text)
    if not dish and plate:
        dish = plate.get("food")
    if not portion and plate:
        portion = plate.get("portion")
    if not nutrients and plate:
        bits = [
            f"{plate['calories']:g} kcal",
            f"{plate['protein']:g} g protein",
            f"{plate['carbs']:g} g carbs",
            f"{plate['fat']:g} g fat",
        ]
        for name, amount in (plate.get("extras") or {}).items():
            bits.append(f"{amount:g} {name}")
        nutrients = ", ".join(bits)

    dish_line = dish or "meal from photo"
    if portion:
        dish_line = f"{dish_line} ({portion})"

    return f"**Dish:** {dish_line}\n**Nutrients:** {nutrients or 'approximate values unavailable'}"


def is_recognizable_food(analysis: str) -> bool:
    """True when Gemini confirms the image contains food/drink."""
    text = (analysis or "").strip()
    if not text:
        return False
    lower = text.lower()
    if re.search(r"food_recognized\s*:\s*no\b", lower):
        return False
    if "not recognizable food item" in lower and not re.search(
        r"food_recognized\s*:\s*yes\b", lower
    ):
        return False
    return True


def parse_plate_total(analysis: str) -> dict | None:
    """
    Parse PLATE_TOTAL into core macros plus any extra nutrients Gemini included.
    Example:
    PLATE_TOTAL: calories=200; protein_g=0.5; carbs_g=48; fat_g=0.2; fiber_g=0; sodium_mg=10; portion=1 glass; food=sugarcane juice
    """
    text = analysis or ""
    match = re.search(r"PLATE_TOTAL:\s*(.+)", text, flags=re.IGNORECASE)
    if not match:
        return None

    raw = match.group(1).strip()
    parts: dict[str, str] = {}
    for chunk in raw.split(";"):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        parts[key.strip().lower()] = value.strip()

    def _num(*keys: str) -> float | None:
        for k in keys:
            if k not in parts:
                continue
            m = re.search(r"[-+]?\d*\.?\d+", parts[k].replace(",", ""))
            if m:
                try:
                    return float(m.group(0))
                except ValueError:
                    return None
        return None

    calories = _num("calories", "kcal")
    protein = _num("protein_g", "protein")
    carbs = _num("carbs_g", "carbs")
    fat = _num("fat_g", "fat")
    if calories is None:
        return None

    food = (parts.get("food") or "meal from photo").strip()[:120] or "meal from photo"
    portion = (parts.get("portion") or "1 serving").strip()[:80] or "1 serving"

    reserved = {
        "calories",
        "kcal",
        "protein",
        "protein_g",
        "carbs",
        "carbs_g",
        "fat",
        "fat_g",
        "food",
        "portion",
    }
    extras: dict[str, float] = {}
    for key, value in parts.items():
        if key in reserved:
            continue
        m = re.search(r"[-+]?\d*\.?\d+", value.replace(",", ""))
        if not m:
            continue
        try:
            amount = float(m.group(0))
        except ValueError:
            continue
        # Normalize keys like potassium_mg -> potassium, fiber_g -> fiber
        nutrient = re.sub(r"_(mg|g|mcg|ug|kcal)$", "", key)
        if nutrient and nutrient not in reserved:
            extras[nutrient] = amount

    return {
        "food": food,
        "portion": portion,
        "calories": calories,
        "protein": protein if protein is not None else 0.0,
        "carbs": carbs if carbs is not None else 0.0,
        "fat": fat if fat is not None else 0.0,
        "extras": extras,
    }


def analyze_food_image_bytes_gemma(data: bytes, filename: str = "upload.jpg") -> str:
    """REFERENCE ONLY — not wired to API/UI."""
    return _analyze_bytes(data, filename, analyze_food_image_gemma)
