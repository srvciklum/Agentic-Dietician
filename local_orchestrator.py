from transformers import pipeline
import time

print("Loading Local Router Model... (This will download a ~250MB DistilBERT model on the very first run. It will be instant next time.)")

# Load a lightweight zero-shot classification model (DistilBERT/DistilRoBERTa based)
classifier = pipeline(
    "zero-shot-classification", 
    model="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
)

# Broader, more distinct labels
INTENT_LABELS = [
    "logging or recording eaten food", 
    "asking if a specific food is safe to eat", 
    "asking for meal, food, or drink recommendations", 
    "reporting a medical emergency or physical symptom", 
    "sending an email, writing code, or doing a non-diet task"
]

def classify_intent_local(user_input):
    result = classifier(
        user_input, 
        INTENT_LABELS, 
        hypothesis_template="This text is about {}.", 
        multi_label=False 
    )
    
    top_intent = result['labels'][0]
    confidence = result['scores'][0]
    
    # THE STRICTER THRESHOLD:
    # If it's less than 50% sure, it's definitely out of scope.
    if confidence < 0.50:
        return "unrelated or out of scope", confidence
        
    # ROUTING MAP:
    if top_intent == "sending an email, writing code, or doing a non-diet task":
        return "unrelated or out of scope", confidence
    if top_intent == "logging or recording eaten food": 
        return "log food intake", confidence
    if top_intent == "asking if a specific food is safe to eat": 
        return "ask if food is safe to eat", confidence
    if top_intent == "asking for meal, food, or drink recommendations": 
        return "recommend a meal", confidence
    if top_intent == "reporting a medical emergency or physical symptom": 
        return "medical emergency", confidence
    
    return "unrelated or out of scope", confidence

def run_local_orchestrator(user_input):
    start_time = time.time()
    
    # 1. Classify the Intent locally
    intent, confidence = classify_intent_local(user_input)
    
    end_time = time.time()
    routing_speed = round((end_time - start_time) * 1000, 2) 
    
    print("\n--- DISTILBERT ORCHESTRATOR ---")
    print(f"Detected Intent : [{intent.upper()}]")
    print(f"Confidence      : {confidence*100:.1f}%")
    print(f"Routing Speed   : {routing_speed} ms")
    print("-------------------------------")
    
    # 2. Route based on the exact label matched
    if intent == "log food intake" or intent == "ask if food is safe to eat":
        print("-> Step 1: Routing to Agent 1 (Extractor) to get Food & Qty...")
        print("   [Orchestrator receives JSON back]")
        
        print("-> Step 2: Routing to Agent 2 (Resolver) to fetch Nutrients from Food DB...")
        print("   [Orchestrator receives Macros/Ingredients back]")
        
        print("-> Step 3: Ambiguity Check...")
        print("   [Condition met: Exact Match. Proceeding to Math/Safety]")
        
        print("-> Step 4: Routing to Agent 3 (Calculator) for Remaining Limits...")
        print("-> Step 5: Routing to Agent 4 (Guardrail) for Allergy/Disease Check...")
        
        print("-> Step 6: Routing to Agent 5 (Synthesizer) to write final response to user...")
        
    elif intent == "recommend a meal":
        print("-> Bypassing Agent 1, 2, 3, and 4 (No specific food to validate).")
        print("-> Routing to Agent 6 (Recommendation Engine) to search DB for safe meal ideas...")
        print("-> Routing to Agent 5 (Synthesizer) to present options to user...")
        
    elif intent == "medical emergency":
        print("-> ALERT: Bypassing ALL nutrition agents.")
        print("-> Routing to Agent 5 (Synthesizer) to generate IMMEDIATE MEDICAL WARNING...")
        
    elif intent == "unrelated or out of scope":
        print("-> Bypassing ALL nutrition agents.")
        print("-> Routing to Agent 5 (Synthesizer) to politely refuse the request...")

    print("===============================\n")

# --- Console Testing Loop ---
if __name__ == "__main__":
    print("\nLocal Orchestrator is Online. Type 'quit' to exit.")
    while True:
        user_in = input("You: ")
        if user_in.lower() in ['quit', 'exit']:
            break
        run_local_orchestrator(user_in)