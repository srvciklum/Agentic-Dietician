"""
List Gemma models available for your Gemini API key.
Run:  .\venv\Scripts\python.exe list_gemma_models.py
"""
from pathlib import Path
import os

from dotenv import load_dotenv
from google import genai

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("GEMINI_API_KEY is not set in the environment or .env file.")

client = genai.Client(api_key=api_key)

# List all Gemma models accessible via your Gemini API key
gemma_models = [m.name for m in client.models.list() if "gemma" in m.name]
print("Available Gemma Models:", gemma_models)
