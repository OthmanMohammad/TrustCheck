#!/usr/bin/env python3
"""
Test script to verify all fixes are working
"""

import requests
import json
import sys
from datetime import datetime
from typing import Dict, Any, List

# Configuration
BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_test(test_name: str, passed: bool, details: str = ""):
    """Print test result with color."""
    status = f"{GREEN}✓ PASSED{RESET}" if passed else f"{RED}✗ FAILED{RESET}"
    print(f"  {status}: {test_name}")
    if details:
        print(f"    {YELLOW}{details}{RESET}")

def test_endpoint(method: str, path: str, expected_status: int = 200, 
                  data: Dict = None, params: Dict = None) -> tuple:
    """Test a single endpoint."""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, params=params, headers=HEADERS, timeout=10)
        else:
            response = requests.request(method, url, json=data, params=params, headers=HEADERS, timeout=10)
        
        success = response.status_code == expected_status
        
        # Check response structure
        if success and response.status_code == 200:
            try:
                json_data = response.json()
                # Check for proper response structure
                if not isinstance(json_data, dict):
                    return False, "Response is not a dictionary"
                if 'success' in json_data and not json_data['success']:
                    return False, f"API returned success=false: {json_data.get('error', 'Unknown error')}"
            except json.JSONDecodeError:
                return False, "Invalid JSON response"
        
        return success, response
    except requests.exceptions.Timeout:
        return False, "Request timeout"
    except requests.exceptions.ConnectionError:
        return False, "Connection error - is the server running?"
    except Exception as e:
        return False, str(e)

def run_tests():
    """Run all API tests with fixes."""
    print(f"\n{BLUE}========================================{RESET}")
    print(f"{BLUE}    TrustCheck Fixed API Test Suite{RESET}")
    print(f"{BLUE}========================================{RESET}\n")
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    # Test 1: Health Check
    print(f"{BLUE}1. Testing Health Endpoints:{RESET}")
    
    success, response = test_endpoint("GET", "/health")
    total_tests += 1
    if success and response.json().get("status") == "healthy":
        passed_tests += 1
        print_test("Health Check", True)
    else:
        error = response.text if hasattr(response, 'text') else str(response)
        print_test("Health Check", False, f"Response: {error[:100]}")
        failed_tests.append("Health Check")
    
    # Test 2: Root Endpoint
    success, response = test_endpoint("GET", "/")
    total_tests += 1
    if success:
        passed_tests += 1
        print_test("Root Endpoint", True)
    else:
        print_test("Root Endpoint", False, str(response))
        failed_tests.append("Root Endpoint")
    
    # Test 3: Entity Endpoints (These should already work)
    print(f"\n{BLUE}2. Testing Entity Endpoints:{RESET}")
    
    # Test listing entities
    success, response = test_endpoint("GET", "/api/v1/entities", params={"limit": 5})
    total_tests += 1
    if success and response.json().get("success"):
        entities = response.json()["data"]["entities"]
        passed_tests += 1
        print_test(f"List Entities", True, f"Found {len(entities)} entities")
        
        # Test getting specific entity if we have any
        if entities:
            entity_uid = entities[0]["uid"]
            success, response = test_endpoint("GET", f"/api/v1/entities/{entity_uid}")
            total_tests += 1
            if success:
                passed_tests += 1
                entity_name = response.json()["data"]["name"]
                print_test(f"Get Entity by UID", True, f"Entity: {entity_name}")
            else:
                print_test(f"Get Entity by UID", False, str(response))
                failed_tests.append("Get Entity by UID")
    else:
        error = response.text if hasattr(response, 'text') else str(response)
        print_test("List Entities", False, f"Response: {error[:100]}")
        failed_tests.append("List Entities")
    
    # Test search endpoint
    success, response = test_endpoint("GET", "/api/v1/entities/search", params={"name": "John", "limit": 5})
    total_tests += 1
    if success:
        results = response.json()["data"]["results"] if response.json().get("data") else []
        passed_tests += 1
        print_test(f"Search Entities", True, f"Found {len(results)} results for 'John'")
    else:
        print_test("Search Entities", False, str(response))
        failed_tests.append("Search Entities")
    
    # Test 4: Change Detection Endpoints - SHOULD BE FIXED
    print(f"\n{BLUE}3. Testing Change Detection Endpoints (FIXED):{RESET}")
    
    # Test list changes
    success, response = test_endpoint("GET", "/api/v1/changes", params={"days": 7, "limit": 10})
    total_tests += 1
    if success:
        try:
            data = response.json()
            if data.get("success"):
                summary = data.get("data", {}).get("summary", {})
                total_changes = summary.get("totals", {}).get("total_changes", 0)
                passed_tests += 1
                print_test("List Changes", True, f"Found {total_changes} changes in last 7 days")
            else:
                print_test("List Changes", False, f"API error: {data.get('error', 'Unknown')}")
                failed_tests.append("List Changes")
        except Exception as e:
            print_test("List Changes", False, f"Parse error: {e}")
            failed_tests.append("List Changes")
    else:
        error = response.text if hasattr(response, 'text') else str(response)
        print_test("List Changes", False, f"Error: {error[:200]}")
        failed_tests.append("List Changes")
    
    # Test critical changes
    success, response = test_endpoint("GET", "/api/v1/changes/critical", params={"hours": 24})
    total_tests += 1
    if success:
        try:
            data = response.json()
            if data.get("success"):
                critical_count = len(data.get("data", {}).get("critical_changes", []))
                passed_tests += 1
                print_test("Get Critical Changes", True, f"Found {critical_count} critical changes in last 24h")
            else:
                print_test("Get Critical Changes", False, f"API error: {data.get('error', 'Unknown')}")
                failed_tests.append("Get Critical Changes")
        except Exception as e:
            print_test("Get Critical Changes", False, f"Parse error: {e}")
            failed_tests.append("Get Critical Changes")
    else:
        error = response.text if hasattr(response, 'text') else str(response)
        print_test("Get Critical Changes", False, f"Error: {error[:200]}")
        failed_tests.append("Get Critical Changes")
    
    # Test 5: Statistics Endpoint - SHOULD BE FIXED
    print(f"\n{BLUE}4. Testing Statistics Endpoints (FIXED):{RESET}")
    
    success, response = test_endpoint("GET", "/api/v1/statistics")
    total_tests += 1
    if success:
        try:
            data = response.json()
            if data.get("success"):
                entities = data.get("data", {}).get("entities", {})
                changes = data.get("data", {}).get("changes", {})
                passed_tests += 1
                print_test("Get Statistics", True, 
                          f"Entities: {entities.get('total_active', 0)} active, "
                          f"Changes: {changes.get('totals', {}).get('total_changes', 0)} total")
            else:
                print_test("Get Statistics", False, f"API error: {data.get('error', 'Unknown')}")
                failed_tests.append("Get Statistics")
        except Exception as e:
            print_test("Get Statistics", False, f"Parse error: {e}")
            failed_tests.append("Get Statistics")
    else:
        error = response.text if hasattr(response, 'text') else str(response)
        print_test("Get Statistics", False, f"Error: {error[:200]}")
        failed_tests.append("Get Statistics")
    
    # Test 6: Scraping Status - SHOULD BE FIXED
    print(f"\n{BLUE}5. Testing Scraping Endpoints (FIXED):{RESET}")
    
    success, response = test_endpoint("GET", "/api/v1/scraping/status", params={"hours": 24})
    total_tests += 1
    if success:
        try:
            data = response.json()
            if data.get("success"):
                status = data.get("data", {})
                metrics = status.get("metrics", {})
                total_runs = metrics.get("total_runs", 0)
                passed_tests += 1
                print_test("Scraping Status", True, f"Total runs in last 24h: {total_runs}")
            else:
                print_test("Scraping Status", False, f"API error: {data.get('error', 'Unknown')}")
                failed_tests.append("Scraping Status")
        except Exception as e:
            print_test("Scraping Status", False, f"Parse error: {e}")
            failed_tests.append("Scraping Status")
    else:
        error = response.text if hasattr(response, 'text') else str(response)
        print_test("Scraping Status", False, f"Error: {error[:200]}")
        failed_tests.append("Scraping Status")
    
    # Print Summary
    print(f"\n{BLUE}========================================{RESET}")
    print(f"{BLUE}           Test Summary{RESET}")
    print(f"{BLUE}========================================{RESET}")
    print(f"Total Tests: {total_tests}")
    print(f"{GREEN}Passed: {passed_tests}{RESET}")
    print(f"{RED}Failed: {total_tests - passed_tests}{RESET}")
    
    if failed_tests:
        print(f"\n{RED}Failed Tests:{RESET}")
        for test in failed_tests:
            print(f"  - {test}")
    else:
        print(f"\n{GREEN}🎉 All tests passed! The fixes are working.{RESET}")
    
    print(f"\n{BLUE}========================================{RESET}")
    
    # Additional diagnostics if any tests failed
    if failed_tests and "--debug" in sys.argv:
        print(f"\n{YELLOW}Debug Mode - Testing individual problem endpoints:{RESET}")
        
        problem_endpoints = [
            ("/api/v1/changes?days=7", "Changes endpoint"),
            ("/api/v1/changes/critical?hours=24", "Critical changes endpoint"),
            ("/api/v1/statistics", "Statistics endpoint"),
            ("/api/v1/scraping/status?hours=24", "Scraping status endpoint"),
        ]
        
        for endpoint, name in problem_endpoints:
            print(f"\nTesting {name}: {endpoint}")
            try:
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
                print(f"  Status: {response.status_code}")
                if response.status_code != 200:
                    print(f"  Error: {response.text[:500]}")
                else:
                    data = response.json()
                    print(f"  Success: {data.get('success', False)}")
                    if not data.get('success'):
                        print(f"  Error: {data.get('error', 'Unknown')}")
            except Exception as e:
                print(f"  Exception: {e}")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    print("\n🔍 TrustCheck API Fixed Test Suite")
    print("This test verifies that all repository fixes are working.\n")
    
    if "--help" in sys.argv:
        print("Usage: python test_fixes.py [--debug]")
        print("  --debug : Show detailed debug information for failed tests")
        sys.exit(0)
    
    all_passed = run_tests()
    
    if all_passed:
        print(f"\n{GREEN}✨ SUCCESS: All fixes are working correctly!{RESET}")
        print("The API is now fully functional with proper NULL handling in repositories.")
    else:
        print(f"\n{RED}⚠️  Some tests are still failing. Check the fixes above.{RESET}")
        if "--debug" not in sys.argv:
            print("Run with --debug flag for more detailed error information.")
    
    sys.exit(0 if all_passed else 1)