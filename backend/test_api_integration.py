"""
API Integration Test Script

End-to-end testing of the API with DTOs.
"""

import requests
import json
from datetime import datetime
import sys

BASE_URL = "http://localhost:8000"

def test_entity_flow():
    """Test complete entity flow with DTOs."""
    print("Testing Entity Flow...")
    
    # 1. List entities
    response = requests.get(f"{BASE_URL}/api/v2/entities?limit=5")
    assert response.status_code == 200
    entities = response.json()
    print(f"✓ Listed {len(entities['data'])} entities")
    
    # 2. Search entities
    response = requests.get(f"{BASE_URL}/api/v2/entities/search?query=test")
    assert response.status_code == 200
    print(f"✓ Search completed")
    
    # 3. Get specific entity (if exists)
    if entities['data']:
        uid = entities['data'][0]['uid']
        response = requests.get(f"{BASE_URL}/api/v2/entities/{uid}")
        assert response.status_code == 200
        print(f"✓ Retrieved entity {uid}")
    
    return True

def test_change_detection_flow():
    """Test change detection flow with DTOs."""
    print("\nTesting Change Detection Flow...")
    
    # 1. Get change summary
    response = requests.get(f"{BASE_URL}/api/v2/changes?days=7")
    assert response.status_code == 200
    summary = response.json()
    print(f"✓ Got change summary: {summary['data']['totals']['total_changes']} changes")
    
    # 2. Get critical changes
    response = requests.get(f"{BASE_URL}/api/v2/changes/critical?hours=24")
    assert response.status_code == 200
    critical = response.json()
    print(f"✓ Got {critical['count']} critical changes")
    
    # 3. Get change statistics
    response = requests.get(f"{BASE_URL}/api/v2/changes/summary")
    assert response.status_code == 200
    print(f"✓ Retrieved change statistics")
    
    return True

def test_validation_errors():
    """Test that validation properly rejects bad data."""
    print("\nTesting Validation...")
    
    errors_caught = 0
    
    # Test invalid limit
    response = requests.get(f"{BASE_URL}/api/v2/entities?limit=5000")
    if response.status_code == 422:
        errors_caught += 1
        print(f"✓ Caught invalid limit")
    
    # Test invalid enum
    response = requests.get(f"{BASE_URL}/api/v2/entities?source=INVALID")
    if response.status_code == 422:
        errors_caught += 1
        print(f"✓ Caught invalid enum value")
    
    # Test invalid date range
    response = requests.get(f"{BASE_URL}/api/v2/changes?days=500")
    if response.status_code == 422:
        errors_caught += 1
        print(f"✓ Caught invalid date range")
    
    print(f"✓ Validation caught {errors_caught} errors")
    return errors_caught > 0

def test_performance():
    """Test API performance with DTOs."""
    print("\nTesting Performance...")
    
    import time
    
    # Test response time
    times = []
    for _ in range(10):
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/v2/entities?limit=10")
        times.append(time.time() - start)
    
    avg_time = sum(times) / len(times)
    print(f"✓ Average response time: {avg_time*1000:.1f}ms")
    
    # Should be under 100ms for simple queries
    assert avg_time < 0.1
    
    return True

def main():
    """Run all integration tests."""
    print("=" * 50)
    print("API v2 Integration Tests")
    print("=" * 50)
    
    # Check if API is running
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            print("❌ API is not healthy")
            sys.exit(1)
    except requests.ConnectionError:
        print("❌ Cannot connect to API. Is it running?")
        print(f"   Start with: python src/main_v2.py")
        sys.exit(1)
    
    tests = [
        test_entity_flow,
        test_change_detection_flow,
        test_validation_errors,
        test_performance
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"❌ {test.__name__} failed")
        except Exception as e:
            failed += 1
            print(f"❌ {test.__name__} failed: {e}")
    
    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✅ All tests passed!")
    
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()