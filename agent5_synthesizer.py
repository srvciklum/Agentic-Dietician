import os
import pyodbc
import time
import json
from dotenv import load_dotenv
from openai import AzureOpenAI
import re


# Load variables from .env file
load_dotenv()

# 1. Initialize Azure OpenAI Client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)


# The name you gave your model deployment in Azure AI Studio
DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

def synthesize_response(agent4_json_string):
    start_time = time.time()
    data = json.loads(agent4_json_string)
    
    flags = data.get("Safety_Flags", [])
    
    # --- SCENARIO A: ERROR HANDLING ---
    if "error" in data:
        system_prompt = (
            "You are a polite, helpful dietary assistant. "
            "The system encountered missing information. "
            "Write a friendly 2-line response asking the user for the missing details."
        )
        user_prompt = f"Missing Info Context: {data['error']}"
        
    # --- SCENARIO B: SUCCESSFUL PIPELINE ---
    else:
        food = data.get("Food_Eaten")
        qty = data.get("Amount_Logged", 1)
        intent = data.get("Intent", "log")
        
        # For inquiries, show what WOULD happen (projected). For logs, show actual values
        if intent == "inquire":
            # Use projected remaining limits for "what if" scenario
            limits = data.get("Projected_Remaining_Limits", data.get("Remaining_Daily_Limits", {}))
        else:
            # Use actual remaining limits
            limits = data.get("Remaining_Daily_Limits", {})
        
        tracked_nutrients = data.get("Tracked_Nutrients", ["calories", "protein", "carbs", "fat"])
        
        system_prompt = (
            "You are a friendly, encouraging dietary assistant speaking DIRECTLY to the user. "
            "Always address the user as 'you' (second person) for remaining limits and advice. "
            "Never say 'they', 'their', or 'them' about the user. "
            "Your job is to summarize the user's meal status concisely. "
            "CRITICAL RULES:\n"
            "1. Maximum of 2 to 3 sentences.\n"
            "2. Be polite and conversational, using you/your for remaining limits.\n"
            "3. Do not give medical advice.\n"
            "4. If the user has EXCEEDED their limits (remaining is 0 or negative), mention that you've gone over your daily limits, not that you've 'reached' them.\n"
            "5. If the user has remaining limits, mention how much you have left for calories/protein/carbs/fat as available.\n"
            "6. Be accurate - 'exceeded' means over, 'remaining' means some left.\n"
            "7. For logged meals, start with 'Saved ...' — never 'You saved ...'.\n"
            "8. Do NOT re-list ingredients or photo details — those were already shown. Focus on saved status and remaining daily limits."
        )

        # Build a summary of key nutrients with status
        nutrient_summary = []
        exceeded_nutrients = []
        priority_nutrients = ["calories", "protein", "carbs", "fat"]
        
        # Add priority nutrients first
        for nut in priority_nutrients:
            if nut in limits and nut in tracked_nutrients:
                remaining = limits.get(nut, 0)
                if remaining <= 0:
                    exceeded_nutrients.append(nut)
                    nutrient_summary.append(f"{nut}: exceeded by {abs(remaining):.0f}")
                else:
                    nutrient_summary.append(f"{nut}: {remaining:.0f} remaining")
        
        # Add other tracked nutrients (limit to 2 more)
        other_nutrients = [n for n in tracked_nutrients if n not in priority_nutrients][:2]
        for nut in other_nutrients:
            if nut in limits:
                remaining = limits.get(nut, 0)
                unit = "mg" if nut in ["sodium", "potassium", "calcium"] else "g"
                if remaining <= 0:
                    exceeded_nutrients.append(nut)
                    nutrient_summary.append(f"{nut}: exceeded by {abs(remaining):.0f}{unit}")
                else:
                    nutrient_summary.append(f"{nut}: {remaining:.0f}{unit} remaining")
        
        summary_text = ", ".join(nutrient_summary[:3])  # Show top 3
        
        # Determine status message
        if exceeded_nutrients:
            status_context = f"The user has EXCEEDED their daily limits for: {', '.join(exceeded_nutrients)}. "
        else:
            status_context = ""

        if intent == "inquire":
            user_prompt = (
                f"The user is asking a hypothetical question. They have NOT eaten this yet. "
                f"{status_context}"
                f"Speak to the user as YOU. Politely explain that if you eat {qty} {food}, "
                f"your remaining daily limits would be: {summary_text}. "
                f"Use light Markdown: bold nutrient names like **calories** when helpful."
            )
        else:
            user_prompt = (
                f"The user just logged a meal. "
                f"Start the reply exactly like: 'Saved {qty} {food}...' "
                f"(do NOT say 'You saved'). Then tell them their remaining daily limits: {summary_text}. "
                f"{status_context}"
                f"Use light Markdown: bold nutrient names like **calories** when helpful."
            )

    # --- 1. CALL AZURE OPENAI ---
    try:
        response = client.chat.completions.create(
            model=DEPLOYMENT_NAME, # Azure uses your deployment name here!
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_completion_tokens=100
        )
        final_message = response.choices[0].message.content.strip()
    except Exception as e:
        final_message = f"I apologize, but I encountered a cloud communication error: {e}"
        
    # --- 2. DETERMINISTIC SAFETY FLAGS (The Proper Way) ---
    if not ("error" in data) and flags:
        final_message += "\n\n### ⚠️ System alerts"
        for flag in flags:
            final_message += f"\n- **{flag}**"

    execution_time = round((time.time() - start_time) * 1000, 2)
    print("\n--- AGENT 5: THE SYNTHESIZER (AZURE CLOUD) ---")
    print(f"Execution Speed : {execution_time} ms")
    # Final user-facing text is printed once by agentic_main (avoid duplicate)
    print("----------------------------------------------\n")
    return final_message