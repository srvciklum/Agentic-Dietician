"""
CLI entry point for Agentic Dietician.
Shared agent logic lives in orchestrator_core.py (also used by api_server.py).
"""
from orchestrator_core import parse_user_id, process_message

print("\n" + "*" * 65)
print(" Agentic Dietician: Full 6-Agent Tool Orchestrator Online")
print("*" * 65)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print(" Welcome to the Multi-Tenant Agentic Dietician ")
    print("=" * 60)

    try:
        user_input_id = input("Please enter your User ID (e.g., 1 or 2) to login: ")
        active_user_id = parse_user_id(user_input_id)
    except ValueError:
        print("Invalid ID. Defaulting to User 1.")
        active_user_id = 1

    print(f"\n[System] Logged in as User {active_user_id}. Booting AI Manager...")
    thread_id = f"dietician_session_user_{active_user_id}"

    while True:
        user_in = input(f"\nUser {active_user_id}: ").strip()
        if user_in.lower() in ["quit", "exit"]:
            print("Goodbye!")
            break

        result = process_message(active_user_id, user_in, thread_id)
        print(f"\nAI: {result['response']}")
