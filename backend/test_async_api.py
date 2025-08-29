"""
Test script to verify async API endpoints are working correctly
"""
import asyncio
import aiohttp
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

async def test_endpoint(session, method, path, data=None):
    """Test a single endpoint"""
    url = f"{BASE_URL}{path}"
    print(f"\n{'='*60}")
    print(f"Testing: {method} {path}")
    print(f"{'='*60}")
    
    try:
        if method == "GET":
            async with session.get(url) as response:
                result = await response.json()
                print(f"Status: {response.status}")
                print(f"Response: {json.dumps(result, indent=2)[:500]}...")
                return response.status == 200
        elif method == "POST":
            async with session.post(url, json=data) as response:
                result = await response.json()
                print(f"Status: {response.status}")
                print(f"Response: {json.dumps(result, indent=2)[:500]}...")
                return response.status in [200, 201, 202]
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def run_tests():
    """Run all API tests"""
    print("\n" + "="*60)
    print("TESTING ASYNC API ENDPOINTS")
    print("="*60)
    
    async with aiohttp.ClientSession() as session:
        tests = [
            # Test health endpoint
            ("GET", "/health"),
            
            # Test v1 endpoints
            ("GET", "/api/v1/entities?limit=5"),
            ("GET", "/api/v1/entities/search?name=test"),
            ("GET", "/api/v1/changes?days=7&limit=5"),
            ("GET", "/api/v1/changes/critical?hours=24"),
            ("GET", "/api/v1/statistics"),
            ("GET", "/api/v1/health"),
            
            # Test v2 endpoints
            ("GET", "/api/v2/entities?limit=5"),
            ("GET", "/api/v2/entities/search?query=test"),
            ("GET", "/api/v2/changes?days=7&limit=5"),
            ("GET", "/api/v2/changes/critical?hours=24"),
            ("GET", "/api/v2/changes/summary?days=7"),
            ("GET", "/api/v2/statistics"),
            
            # Test POST endpoint
            ("POST", "/api/v2/scraping/run", {
                "source": "OFAC",
                "force_update": False,
                "timeout_seconds": 120
            }),
        ]
        
        results = []
        for test in tests:
            if len(test) == 2:
                method, path = test
                success = await test_endpoint(session, method, path)
            else:
                method, path, data = test
                success = await test_endpoint(session, method, path, data)
            
            results.append((path, success))
            await asyncio.sleep(0.5)  # Small delay between tests
        
        # Print summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        for path, success in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status}: {path}")
        
        total = len(results)
        passed = sum(1 for _, s in results if s)
        print(f"\nTotal: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n🎉 All tests passed! Async implementation is working correctly.")
        else:
            print("\n⚠️ Some tests failed. Check the implementation.")

async def test_concurrent_requests():
    """Test concurrent request handling"""
    print("\n" + "="*60)
    print("TESTING CONCURRENT REQUESTS")
    print("="*60)
    
    async with aiohttp.ClientSession() as session:
        # Make 10 concurrent requests
        urls = [f"{BASE_URL}/api/v1/entities?limit=5&offset={i*5}" for i in range(10)]
        
        start_time = datetime.now()
        tasks = [session.get(url) for url in urls]
        responses = await asyncio.gather(*tasks)
        end_time = datetime.now()
        
        for resp in responses:
            await resp.text()  # Consume response
            resp.close()
        
        duration = (end_time - start_time).total_seconds()
        print(f"✅ Handled 10 concurrent requests in {duration:.2f} seconds")
        print(f"Average: {duration/10:.3f} seconds per request")

if __name__ == "__main__":
    # First, start the server with: uvicorn src.main:app --reload
    print("Make sure the server is running with:")
    print("cd backend && uvicorn src.main:app --reload")
    print("\nPress Enter to start tests...")
    input()
    
    # Run the tests
    asyncio.run(run_tests())
    asyncio.run(test_concurrent_requests())