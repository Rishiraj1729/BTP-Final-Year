"""
Test script for the enhanced agentic AI system
"""

import requests
import json
import time

BASE_URL = "http://localhost:8001"

def test_health():
    """Test health endpoint"""
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        print(f"Health check: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_conversation_start():
    """Test conversation start endpoint"""
    print("\nTesting conversation start...")
    try:
        data = {
            "context": {"source": "test", "initial_description": "I want to build a mobile app"},
            "stakeholders": [{"type": "business", "role": "product_owner"}],
            "domain": "mobile"
        }
        
        response = requests.post(f"{BASE_URL}/api/conversation/start", json=data)
        print(f"Conversation start: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Session ID: {result.get('session_id')}")
            return result.get('session_id')
        else:
            print(f"Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"Conversation start failed: {e}")
        return None

def test_conversation_stream(session_id):
    """Test conversation stream endpoint"""
    print(f"\nTesting conversation stream with session {session_id}...")
    try:
        data = {
            "session_id": session_id,
            "input_text": "I want to build a food delivery app for restaurants",
            "input_type": "text"
        }
        
        response = requests.post(f"{BASE_URL}/api/conversation/continuous", json=data)
        print(f"Conversation stream: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Status: {result.get('status')}")
            print(f"Questions: {len(result.get('questions', []))}")
            print(f"Completeness scores: {result.get('completeness_scores', {})}")
            return result
        else:
            print(f"Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"Conversation stream failed: {e}")
        return None

def test_conversation_status(session_id):
    """Test conversation status endpoint"""
    print(f"\nTesting conversation status for session {session_id}...")
    try:
        response = requests.get(f"{BASE_URL}/api/conversation/status/{session_id}")
        print(f"Conversation status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Phase: {result.get('phase')}")
            print(f"Active gaps: {len(result.get('active_gaps', []))}")
            return result
        else:
            print(f"Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"Conversation status failed: {e}")
        return None

def main():
    """Run all tests"""
    print("Testing Enhanced Agentic AI System")
    print("=" * 50)
    
    # Test 1: Health check
    if not test_health():
        print("Health check failed. Make sure backend is running.")
        return
    
    # Test 2: Start conversation
    session_id = test_conversation_start()
    if not session_id:
        print("Conversation start failed.")
        return
    
    # Test 3: Stream conversation
    stream_result = test_conversation_stream(session_id)
    if not stream_result:
        print("Conversation stream failed.")
        return
    
    # Test 4: Check status
    status_result = test_conversation_status(session_id)
    if not status_result:
        print("Conversation status failed.")
        return
    
    print("\nAll tests passed!")
    print(f"Session ID: {session_id}")
    print("You can now test the Streamlit interface at: http://localhost:8502")

if __name__ == "__main__":
    main()