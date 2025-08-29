# diagnose_api.py
"""Diagnose API response formats."""

import requests
import json

BASE_URL = "http://localhost:8000"

def diagnose():
    print("🔍 Diagnosing API responses...\n")
    
    # Test entities endpoint
    print("1. Testing /api/v2/entities")
    try:
        response = requests.get(f"{BASE_URL}/api/v2/entities?limit=5")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Response type: {type(data)}")
            
            if isinstance(data, dict):
                print(f"   Keys: {list(data.keys())}")
                if 'data' in data:
                    print(f"   Data type: {type(data['data'])}")
                    if isinstance(data['data'], list) and len(data['data']) > 0:
                        print(f"   First item keys: {list(data['data'][0].keys())}")
            elif isinstance(data, list):
                print(f"   List length: {len(data)}")
                if len(data) > 0:
                    print(f"   First item: {data[0]}")
            
            print(f"   Full response (truncated):\n   {json.dumps(data, indent=2)[:500]}")
        else:
            print(f"   Error response: {response.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n2. Testing /api/v2/changes")
    try:
        response = requests.get(f"{BASE_URL}/api/v2/changes?days=7")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Response type: {type(data)}")
            if isinstance(data, dict):
                print(f"   Keys: {list(data.keys())}")
            print(f"   Response (truncated):\n   {json.dumps(data, indent=2)[:300]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n3. Testing validation")
    try:
        response = requests.get(f"{BASE_URL}/api/v2/entities?limit=5000")
        print(f"   Invalid limit status: {response.status_code}")
        if response.status_code == 422:
            print("   ✅ Validation working")
        else:
            print(f"   ⚠️ Expected 422, got {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    diagnose()