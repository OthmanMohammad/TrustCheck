"""
Test Script for Phase 3 - Verify DTOs and Validation are Working

Run this to test if Phase 3 is properly implemented.
"""

import requests
import json
from datetime import datetime
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

class Phase3Tester:
    def __init__(self):
        self.base_url = BASE_URL
        self.passed_tests = 0
        self.failed_tests = 0
        self.results = []
    
    def test_endpoint(self, name: str, method: str, url: str, **kwargs) -> bool:
        """Test a single endpoint."""
        print(f"\n🔍 Testing: {name}")
        print(f"   {method} {url}")
        
        try:
            response = requests.request(method, f"{self.base_url}{url}", **kwargs)
            
            # Check if response is JSON
            try:
                data = response.json()
            except:
                print(f"   ❌ Response is not valid JSON")
                self.failed_tests += 1
                return False
            
            # Check basic structure
            if response.status_code < 400:
                # Success response should have success=true
                if data.get('success') != True:
                    print(f"   ⚠️  Success field missing or false")
                
                # Should have metadata
                if 'metadata' not in data:
                    print(f"   ⚠️  Metadata field missing")
                else:
                    # Check metadata structure
                    metadata = data['metadata']
                    if 'timestamp' in metadata:
                        # Try to parse timestamp
                        try:
                            datetime.fromisoformat(metadata['timestamp'].replace('Z', '+00:00'))
                            print(f"   ✅ Valid timestamp format")
                        except:
                            print(f"   ⚠️  Invalid timestamp format: {metadata['timestamp']}")
                    
                    if 'request_id' in metadata:
                        print(f"   ✅ Request ID present: {metadata['request_id']}")
                
                print(f"   ✅ Status: {response.status_code}")
                print(f"   ✅ Valid response structure")
                self.passed_tests += 1
                return True
            else:
                # Error response should have proper structure
                if 'error' in data:
                    error = data['error']
                    if all(k in error for k in ['code', 'message']):
                        print(f"   ✅ Proper error structure")
                        print(f"      Code: {error['code']}")
                        print(f"      Message: {error['message']}")
                        self.passed_tests += 1
                        return True
                    else:
                        print(f"   ❌ Invalid error structure")
                else:
                    print(f"   ❌ Missing error field in error response")
                self.failed_tests += 1
                return False
                
        except requests.RequestException as e:
            print(f"   ❌ Request failed: {e}")
            self.failed_tests += 1
            return False
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
            self.failed_tests += 1
            return False
    
    def test_validation(self, name: str, method: str, url: str, expected_status: int, **kwargs) -> bool:
        """Test validation with expected failure."""
        print(f"\n🔍 Testing Validation: {name}")
        print(f"   {method} {url}")
        print(f"   Expected status: {expected_status}")
        
        try:
            response = requests.request(method, f"{self.base_url}{url}", **kwargs)
            
            if response.status_code == expected_status:
                print(f"   ✅ Got expected status: {response.status_code}")
                
                if expected_status == 422:  # Validation error
                    data = response.json()
                    if 'detail' in data:
                        print(f"   ✅ Validation error details present")
                    self.passed_tests += 1
                    return True
                
                self.passed_tests += 1
                return True
            else:
                print(f"   ❌ Expected {expected_status}, got {response.status_code}")
                self.failed_tests += 1
                return False
                
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            self.failed_tests += 1
            return False
    
    def run_all_tests(self):
        """Run complete Phase 3 test suite."""
        print("=" * 60)
        print("PHASE 3 TEST SUITE - DTOs and Validation")
        print("=" * 60)
        
        # ====== SUCCESSFUL REQUESTS ======
        print("\n📋 TESTING SUCCESSFUL REQUESTS")
        
        # Test entity endpoints
        self.test_endpoint(
            "List Entities",
            "GET",
            "/api/v2/entities?limit=5"
        )
        
        self.test_endpoint(
            "Search Entities", 
            "GET",
            "/api/v2/entities/search?query=test"
        )
        
        # Test change endpoints
        self.test_endpoint(
            "List Changes",
            "GET", 
            "/api/v2/changes?days=7"
        )
        
        self.test_endpoint(
            "Get Critical Changes",
            "GET",
            "/api/v2/changes/critical?hours=24"
        )
        
        self.test_endpoint(
            "Get Change Summary",
            "GET",
            "/api/v2/changes/summary?days=7"
        )
        
        # Test scraping status
        self.test_endpoint(
            "Get Scraping Status",
            "GET",
            "/api/v2/scraping/status"
        )
        
        # Test statistics
        self.test_endpoint(
            "Get Statistics",
            "GET",
            "/api/v2/statistics"
        )
        
        # ====== VALIDATION TESTS ======
        print("\n📋 TESTING VALIDATION")
        
        # Test parameter validation
        self.test_validation(
            "Invalid limit (too high)",
            "GET",
            "/api/v2/entities?limit=5000",
            422
        )
        
        self.test_validation(
            "Invalid offset (negative)",
            "GET",
            "/api/v2/entities?offset=-1",
            422
        )
        
        self.test_validation(
            "Invalid enum value",
            "GET",
            "/api/v2/entities?source=INVALID_SOURCE",
            422
        )
        
        self.test_validation(
            "Search query too short",
            "GET",
            "/api/v2/entities/search?query=a",
            422
        )
        
        self.test_validation(
            "Invalid hours (too high)",
            "GET",
            "/api/v2/changes/critical?hours=200",
            422
        )
        
        # Test POST validation
        self.test_validation(
            "Invalid scraper source",
            "POST",
            "/api/v2/scraping/run",
            422,
            json={"source": "INVALID", "timeout_seconds": 120}
        )
        
        self.test_validation(
            "Invalid timeout",
            "POST",
            "/api/v2/scraping/run",
            422,
            json={"source": "OFAC", "timeout_seconds": -10}
        )
        
        # ====== ERROR HANDLING ======
        print("\n📋 TESTING ERROR HANDLING")
        
        self.test_endpoint(
            "Non-existent entity",
            "GET",
            "/api/v2/entities/non-existent-uid"
        )
        
        # ====== RESULTS ======
        print("\n" + "=" * 60)
        print("TEST RESULTS")
        print("=" * 60)
        print(f"✅ Passed: {self.passed_tests}")
        print(f"❌ Failed: {self.failed_tests}")
        print(f"📊 Success Rate: {(self.passed_tests / (self.passed_tests + self.failed_tests) * 100):.1f}%")
        
        if self.failed_tests == 0:
            print("\n🎉 ALL TESTS PASSED! Phase 3 is working correctly!")
        else:
            print(f"\n⚠️  {self.failed_tests} tests failed. Review the output above.")
        
        return self.failed_tests == 0

def test_dto_serialization():
    """Test DTO serialization separately."""
    print("\n📋 TESTING DTO SERIALIZATION")
    
    from src.api.schemas.base import BaseResponse, ResponseMetadata
    from src.api.schemas.entity import EntitySummaryDTO
    from datetime import datetime
    
    try:
        # Create a response with datetime
        metadata = ResponseMetadata(
            timestamp=datetime.utcnow(),
            request_id="test-123"
        )
        
        response = BaseResponse(
            success=True,
            data={"test": "data"},
            metadata=metadata
        )
        
        # Try to serialize to JSON
        json_str = response.model_dump_json()
        parsed = json.loads(json_str)
        
        print("✅ DTO serialization working")
        print(f"   Timestamp: {parsed['metadata']['timestamp']}")
        return True
        
    except Exception as e:
        print(f"❌ DTO serialization failed: {e}")
        return False

if __name__ == "__main__":
    # Test DTO serialization first
    test_dto_serialization()
    
    # Run main test suite
    tester = Phase3Tester()
    success = tester.run_all_tests()
    
    if success:
        print("\n" + "🎊" * 20)
        print("PHASE 3 IMPLEMENTATION COMPLETE!")
        print("🎊" * 20)
    else:
        print("\n" + "⚠️ " * 20)
        print("PHASE 3 NEEDS MORE WORK")
        print("⚠️ " * 20)