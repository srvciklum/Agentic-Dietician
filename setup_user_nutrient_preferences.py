"""
Script to populate user_nutrient_preferences table with nutrient tracking preferences.

This script sets up which nutrients each user wants to track and their daily limits.
"""

from nutrient_utils import set_user_nutrient_preference, get_all_available_nutrients
import sys

def setup_user_preferences():
    """Sets up nutrient preferences for users."""
    
    print("=" * 60)
    print("USER NUTRIENT PREFERENCES SETUP")
    print("=" * 60)
    
    # Check available nutrients
    print("\nChecking available nutrients in database...")
    available_nutrients = get_all_available_nutrients()
    if not available_nutrients:
        print("ERROR: No nutrients found in database!")
        print("Please run setup_flexible_nutrients.py first to create the nutrients table.")
        return False
    
    print(f"✓ Found {len(available_nutrients)} available nutrients")
    print("\nAvailable nutrients:")
    for nut in available_nutrients[:10]:  # Show first 10
        print(f"  - {nut['display_name']} ({nut['nutrient_name']}) - {nut['unit']}")
    if len(available_nutrients) > 10:
        print(f"  ... and {len(available_nutrients) - 10} more")
    
    # ============================================
    # USER 1: 4 Nutrients
    # ============================================
    print("\n" + "=" * 60)
    print("Setting up User 1 preferences (4 nutrients)...")
    print("=" * 60)
    
    user1_preferences = [
        ("calories", 2000),      # kcal
        ("protein", 150),        # g
        ("carbs", 250),          # g
        ("fat", 70)              # g
    ]
    
    success_count = 0
    for nutrient_name, daily_limit in user1_preferences:
        if set_user_nutrient_preference(1, nutrient_name, daily_limit):
            print(f"✓ User 1: {nutrient_name} = {daily_limit}")
            success_count += 1
        else:
            print(f"✗ User 1: Failed to set {nutrient_name}")
    
    print(f"\nUser 1: {success_count}/{len(user1_preferences)} preferences set successfully")
    
    # ============================================
    # USER 2: 3 Nutrients
    # ============================================
    print("\n" + "=" * 60)
    print("Setting up User 2 preferences (3 nutrients)...")
    print("=" * 60)
    
    user2_preferences = [
        ("calories", 1800),      # kcal
        ("protein", 120),        # g
        ("potassium", 3500)      # mg
    ]
    
    success_count = 0
    for nutrient_name, daily_limit in user2_preferences:
        if set_user_nutrient_preference(2, nutrient_name, daily_limit):
            print(f"✓ User 2: {nutrient_name} = {daily_limit}")
            success_count += 1
        else:
            print(f"✗ User 2: Failed to set {nutrient_name}")
    
    print(f"\nUser 2: {success_count}/{len(user2_preferences)} preferences set successfully")
    
    # ============================================
    # Summary
    # ============================================
    print("\n" + "=" * 60)
    print("SETUP COMPLETE!")
    print("=" * 60)
    print("\nSummary:")
    print(f"  User 1: Tracking {len(user1_preferences)} nutrients")
    print(f"  User 2: Tracking {len(user2_preferences)} nutrients")
    print("\nYou can now use the system with these users!")
    print("\nTo verify, run:")
    print("  from nutrient_utils import get_user_tracked_nutrients")
    print("  print(get_user_tracked_nutrients(1))")
    print("  print(get_user_tracked_nutrients(2))")
    
    return True

def verify_setup():
    """Verifies that preferences were set correctly."""
    from nutrient_utils import get_user_tracked_nutrients
    
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    
    for user_id in [1, 2]:
        print(f"\nUser {user_id} tracked nutrients:")
        tracked = get_user_tracked_nutrients(user_id)
        if tracked:
            for nutrient_name, info in tracked.items():
                print(f"  - {nutrient_name}: limit={info['limit']} {info['unit']}")
        else:
            print(f"  No preferences found for User {user_id}")

if __name__ == "__main__":
    try:
        # Setup preferences
        if setup_user_preferences():
            # Verify setup
            verify_setup()
        else:
            print("\nSetup failed. Please check the error messages above.")
            sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
