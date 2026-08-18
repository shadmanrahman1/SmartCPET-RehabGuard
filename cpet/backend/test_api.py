"""
Test script for CPET Arrhythmia Detection System API
Run this after starting the backend server to verify all endpoints work.
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"


def print_response(response, endpoint_name):
    """Pretty print API response"""
    print(f"\n{'=' * 60}")
    print(f"Testing: {endpoint_name}")
    print(f"{'=' * 60}")
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"Error: {response.text}")
    return response


def test_api():
    """Test all API endpoints"""

    # 1. Test system status
    print("\n🔍 TESTING SYSTEM STATUS")
    response = requests.get(f"{BASE_URL}/api/status")
    print_response(response, "GET /api/status")

    # 2. Test device status
    print("\n🔍 TESTING DEVICE STATUS")
    response = requests.get(f"{BASE_URL}/api/devices/status")
    print_response(response, "GET /api/devices/status")

    # 3. Start a test session
    print("\n🔍 TESTING SESSION CREATION")
    session_data = {
        "patient_id": "P001",
        "patient_name": "John Doe",
        "age": 35,
        "gender": "Male",
    }
    response = requests.post(f"{BASE_URL}/api/sessions/start", json=session_data)
    result = print_response(response, "POST /api/sessions/start")

    if response.status_code != 200:
        print("❌ Failed to create session. Exiting.")
        return

    session_id = result.json()["session_id"]
    print(f"\n✅ Created session with ID: {session_id}")

    # 4. Send test prediction events
    print("\n🔍 TESTING EVENT STORAGE")
    events_data = {
        "session_id": session_id,
        "events": [
            {
                "timestamp": datetime.now().isoformat(),
                "predicted_class": 0,
                "class_name": "Normal",
                "confidence": 0.98,
                "is_alert": False,
            },
            {
                "timestamp": datetime.now().isoformat(),
                "predicted_class": 0,
                "class_name": "Normal",
                "confidence": 0.97,
                "is_alert": False,
            },
            {
                "timestamp": datetime.now().isoformat(),
                "predicted_class": 2,
                "class_name": "Ventricular",
                "confidence": 0.96,
                "is_alert": True,
            },
            {
                "timestamp": datetime.now().isoformat(),
                "predicted_class": 1,
                "class_name": "Supraventricular",
                "confidence": 0.92,
                "is_alert": False,
            },
            {
                "timestamp": datetime.now().isoformat(),
                "predicted_class": 0,
                "class_name": "Normal",
                "confidence": 0.99,
                "is_alert": False,
            },
        ],
    }
    response = requests.post(f"{BASE_URL}/api/events", json=events_data)
    print_response(response, "POST /api/events")

    # 5. Get session statistics
    print("\n🔍 TESTING SESSION STATISTICS")
    response = requests.get(f"{BASE_URL}/api/sessions/{session_id}/stats")
    print_response(response, f"GET /api/sessions/{session_id}/stats")

    # 6. Get session events
    print("\n🔍 TESTING SESSION EVENTS RETRIEVAL")
    response = requests.get(f"{BASE_URL}/api/sessions/{session_id}/events?limit=10")
    print_response(response, f"GET /api/sessions/{session_id}/events")

    # 7. Get all sessions
    print("\n🔍 TESTING SESSION LISTING")
    response = requests.get(f"{BASE_URL}/api/sessions")
    print_response(response, "GET /api/sessions")

    # 8. Get specific session
    print("\n🔍 TESTING SPECIFIC SESSION RETRIEVAL")
    response = requests.get(f"{BASE_URL}/api/sessions/{session_id}")
    print_response(response, f"GET /api/sessions/{session_id}")

    # 9. Stop session
    print("\n🔍 TESTING SESSION STOP")
    response = requests.post(f"{BASE_URL}/api/sessions/{session_id}/stop")
    print_response(response, f"POST /api/sessions/{session_id}/stop")

    # Final summary
    print("\n" + "=" * 60)
    print("✅ API TESTING COMPLETE")
    print("=" * 60)
    print(f"\n📊 Summary:")
    print(f"   - Session ID: {session_id}")
    print(f"   - Patient: John Doe (35 years, Male)")
    print(f"   - Total events sent: 5 (3 Normal, 1 Supraventricular, 1 Ventricular)")
    print(f"   - Alerts triggered: 1 (Ventricular beat)")
    print(f"\n🌐 Next step: Open dashboard at http://localhost:3000")
    print(f"   Navigate to /analysis/{session_id} to see the test data")


if __name__ == "__main__":
    try:
        print("=" * 60)
        print("CPET ARRHYTHMIA DETECTION SYSTEM - API TEST")
        print("=" * 60)
        print("\n⏳ Starting API tests...")
        test_api()
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to backend server!")
        print("   Make sure the backend is running at http://localhost:8000")
        print("\n   Start it with:")
        print("   cd backend")
        print("   uvicorn main:app --reload")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
