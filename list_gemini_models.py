"""
List Gemini models available for your API key (Flash filter).
Run:  .\venv\Scripts\python.exe list_gemini_models.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise SystemExit("GEMINI_API_KEY is not set in the environment or .env file.")

client = genai.Client(api_key=api_key)

print("Available Flash models:")
for model in client.models.list():
    if "flash" in model.name.lower():
        print(model.name)
