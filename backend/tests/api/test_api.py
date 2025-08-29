#!/usr/bin/env python3
"""
Comprehensive API Testing Script for TrustCheck
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

def print_test(test_name: str, passed: bool, message: str = ""):
    """Print test result with color."""
    status = f"{GREEN}✓ PASSED{RESET}" if passed else f"{RED}✗ FAILED{RESET}"
    print(f"  {status}: {test_name}")
    if message:
        print(f"    {YELLOW}{message}{RESET}")

def test_endpoint(method: str, path: str, expected_status: int = 200, 
                  data: Dict = None, params: Dict = None) -> tuple:
    """Test a single endpoint."""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url, params=params, headers=HEADERS)
        elif method == "POST":
            response = requests.post(url, json=data, params=params, headers=HEADERS)
        else:
            response = requests.request(method, url, json=data, params=params, headers=HEADERS)
        
        success = response.status_code == expected_status
        return success, response
    except Exception as e:
        return False, str(e)

def run_tests():
    """Run all API tests."""
    print(f"\n{BLUE}========================================{RESET}")
    print(f"{BLUE}    TrustCheck API Test Suite{RESET}")
    print(f"{BLUE}========================================{RESET}\n")
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    # Test 1: Health Check
    print(f"{BLUE}Testing Health Endpoints:{RESET}")
    
    success, response = test_endpoint("GET", "/health")
    total_tests += 1
    if success and response.json().get("status") == "healthy":
        passed_tests += 1
        print_test("Health Check", True)
    else:
        print_test("Health Check", False, f"Response: {response}")
        failed_tests.append("Health Check")
    
    # Test 2: Root Endpoint
    success, response = test_endpoint("GET", "/")
    total_tests += 1
    if success:
        passed_tests += 1
        print_test("Root Endpoint", True)
    else:
        print_test("Root Endpoint", False)
        failed_tests.append("Root Endpoint")
    
    # Test 3: Entity Endpoints
    print(f"\n{BLUE}Testing Entity Endpoints:{RESET}")
    
    # Test listing entities
    success, response = test_endpoint("GET", "/api/v1/entities", params={"limit": 10})
    total_tests += 1
    if success and response.json().get("success"):
        entities = response.json()["data"]["entities"]
        passed_tests += 1
        print_test(f"List Entities (found {len(entities)})", True)
        
        # Test getting specific entity if we have any
        if entities:
            entity_uid = entities[0]["uid"]
            success, response = test_endpoint("GET", f"/api/v1/entities/{entity_uid}")
            total_tests += 1
            if success:
                passed_tests += 1
                print_test(f"Get Entity by UID ({entity_uid})", True)
            else:
                print_test(f"Get Entity by UID ({entity_uid})", False)
                failed_tests.append("Get Entity by UID")
    else:
        print_test("List Entities", False, f"Response: {response}")
        failed_tests.append("List Entities")
    
    # Test search endpoint
    success, response = test_endpoint("GET", "/api/v1/entities/search", params={"name": "John"})
    total_tests += 1
    if success:
        passed_tests += 1
        results = response.json()["data"]["results"] if response.json().get("data") else []
        print_test(f"Search Entities (found {len(results)})", True)
    else:
        print_test("Search Entities", False)
        failed_tests.append("Search Entities")
    
    # Test 4: Change Detection Endpoints
    print(f"\n{BLUE}Testing Change Detection Endpoints:{RESET}")
    
    # Test list changes
    success, response = test_endpoint("GET", "/api/v1/changes", params={"days": 7})
    total_tests += 1
    if success:
        passed_tests += 1
        print_test("List Changes", True)
    else:
        error_msg = response.text if hasattr(response, 'text') else str(response)
        print_test("List Changes", False, f"Error: {error_msg}")
        failed_tests.append("List Changes")
    
    # Test critical changes
    success, response = test_endpoint("GET", "/api/v1/changes/critical", params={"hours": 24})
    total_tests += 1
    if success:
        passed_tests += 1
        print_test("Get Critical Changes", True)
    else:
        print_test("Get Critical Changes", False)
        failed_tests.append("Get Critical Changes")
    
    # Test 5: Statistics Endpoint
    print(f"\n{BLUE}Testing Statistics Endpoints:{RESET}")
    
    success, response = test_endpoint("GET", "/api/v1/statistics")
    total_tests += 1
    if success:
        passed_tests += 1
        print_test("Get Statistics", True)
    else:
        if response and hasattr(response, 'status_code') and response.status_code == 404:
            print_test("Get Statistics", False, "Endpoint not implemented yet")
        else:
            print_test("Get Statistics", False)
        failed_tests.append("Get Statistics")
    
    # Test 6: Scraping Status
    print(f"\n{BLUE}Testing Scraping Endpoints:{RESET}")
    
    success, response = test_endpoint("GET", "/api/v1/scraping/status", params={"hours": 24})
    total_tests += 1
    if success:
        passed_tests += 1
        print_test("Scraping Status", True)
    else:
        print_test("Scraping Status", False)
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
    
    print(f"\n{BLUE}========================================{RESET}\n")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    all_passed = run_tests()
    sys.exit(0 if all_passed else 1)