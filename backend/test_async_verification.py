#!/usr/bin/env python3
"""
Simple Test to Verify Your API Works
"""

import requests
import json
from datetime import datetime

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def test_api():
    """Test if API is actually returning data."""
    
    print("\n" + "="*60)
    print("Testing TrustCheck API")
    print("="*60)
    
    base_url = "http://localhost:8000"
    
    # 1. Test Health
    print("\n1. Testing Health Check...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print(f"{GREEN}✓ Health check passed{RESET}")
        else:
            print(f"{RED}✗ Health check failed: {response.status_code}{RESET}")
    except Exception as e:
        print(f"{RED}✗ API not running: {e}{RESET}")
        print(f"{YELLOW}Start API with: uvicorn src.main:app --reload{RESET}")
        return
    
    # 2. Test Get Entities
    print("\n2. Testing Get Entities...")
    try:
        response = requests.get(f"{base_url}/api/v1/entities?limit=5")
        if response.status_code == 200:
            data = response.json()
            entity_count = len(data['data']['entities'])
            total_active = data['data']['statistics'].get('total_active', 0)
            
            print(f"{GREEN}✓ API responded successfully{RESET}")
            print(f"   - Entities returned: {entity_count}")
            print(f"   - Total in database: {total_active}")
            
            if entity_count > 0:
                print(f"{GREEN}✓ Data is being returned correctly!{RESET}")
                first_entity = data['data']['entities'][0]
                print(f"   First entity: {first_entity['name']} ({first_entity['source']})")
            else:
                print(f"{RED}✗ No entities returned (but {total_active} in database){RESET}")
                print(f"{YELLOW}   This means the find_all() method isn't working{RESET}")
        else:
            print(f"{RED}✗ Failed: {response.status_code}{RESET}")
            print(f"   Error: {response.text[:200]}")
    except Exception as e:
        print(f"{RED}✗ Error: {e}{RESET}")
    
    # 3. Test Search
    print("\n3. Testing Entity Search...")
    try:
        response = requests.get(f"{base_url}/api/v1/entities/search?name=Iran")
        if response.status_code == 200:
            data = response.json()
            result_count = len(data['data']['results'])
            print(f"{GREEN}✓ Search works{RESET}")
            print(f"   - Results found: {result_count}")
            if result_count > 0:
                print(f"   - First match: {data['data']['results'][0]['name']}")
        else:
            print(f"{RED}✗ Search failed: {response.status_code}{RESET}")
    except Exception as e:
        print(f"{RED}✗ Error: {e}{RESET}")
    
    # 4. Test Statistics
    print("\n4. Testing Statistics...")
    try:
        response = requests.get(f"{base_url}/api/v1/statistics")
        if response.status_code == 200:
            data = response.json()
            stats = data['data']['entities']
            print(f"{GREEN}✓ Statistics work{RESET}")
            print(f"   - Active entities: {stats.get('total_active', 0)}")
            print(f"   - By source: {stats.get('by_source', {})}")
        else:
            print(f"{RED}✗ Statistics failed: {response.status_code}{RESET}")
    except Exception as e:
        print(f"{RED}✗ Error: {e}{RESET}")
    
    # 5. Test Changes
    print("\n5. Testing Change Detection...")
    try:
        response = requests.get(f"{base_url}/api/v1/changes?days=30")
        if response.status_code == 200:
            data = response.json()
            total_changes = data['data']['summary'].get('total_changes', 0)
            print(f"{GREEN}✓ Change detection works{RESET}")
            print(f"   - Changes in last 30 days: {total_changes}")
        else:
            print(f"{RED}✗ Changes failed: {response.status_code}{RESET}")
    except Exception as e:
        print(f"{RED}✗ Error: {e}{RESET}")
    
    print("\n" + "="*60)
    print("Test Complete")
    print("="*60)

if __name__ == "__main__":
    test_api()