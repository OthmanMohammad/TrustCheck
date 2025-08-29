"""
Diagnose validation issues in Phase 3
"""

import requests
from pydantic import ValidationError
from src.api.schemas.entity import EntityFilterRequest, EntitySearchRequest
from src.api.schemas.change_detection import CriticalChangesRequest

def test_local_validation():
    """Test if validation works locally."""
    print("Testing local Pydantic validation...")
    
    # Test 1: Invalid limit
    try:
        req = EntityFilterRequest(limit=5000)
        print("❌ Limit validation failed - should have raised error for limit=5000")
    except ValidationError as e:
        print("✅ Limit validation works locally - raised error for limit=5000")
    
    # Test 2: Negative offset
    try:
        req = EntityFilterRequest(offset=-1)
        print("❌ Offset validation failed - should have raised error for offset=-1")
    except ValidationError as e:
        print("✅ Offset validation works locally - raised error for offset=-1")
    
    # Test 3: Short search query
    try:
        req = EntitySearchRequest(query="a")
        print("❌ Query validation failed - should have raised error for query='a'")
    except ValidationError as e:
        print("✅ Query validation works locally - raised error for query='a'")
    
    # Test 4: Invalid hours
    try:
        req = CriticalChangesRequest(hours=200)
        print("❌ Hours validation failed - should have raised error for hours=200")
    except ValidationError as e:
        print("✅ Hours validation works locally - raised error for hours=200")
    
    print("\nLocal validation is working!\n")

def test_api_validation():
    """Test if API validates correctly."""
    BASE_URL = "http://localhost:8000"
    
    print("Testing API validation...")
    
    tests = [
        ("Invalid limit", "GET", f"{BASE_URL}/api/v2/entities?limit=5000", 422),
        ("Negative offset", "GET", f"{BASE_URL}/api/v2/entities?offset=-1", 422),
        ("Short query", "GET", f"{BASE_URL}/api/v2/entities/search?query=a", 422),
        ("Invalid hours", "GET", f"{BASE_URL}/api/v2/changes/critical?hours=200", 422),
    ]
    
    for name, method, url, expected_status in tests:
        response = requests.request(method, url)
        if response.status_code == expected_status:
            print(f"✅ {name}: Got expected {expected_status}")
        else:
            print(f"❌ {name}: Expected {expected_status}, got {response.status_code}")
            if response.status_code == 500:
                data = response.json()
                if 'error' in data:
                    print(f"   Error: {data['error'].get('message', 'Unknown')}")

if __name__ == "__main__":
    # Test local validation first
    test_local_validation()
    
    # Test API validation
    test_api_validation()