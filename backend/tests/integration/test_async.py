"""
Test script for async implementation
"""
import asyncio
import httpx
from datetime import datetime

async def test_api():
    """Test the async API endpoints."""
    
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        print("Testing TrustCheck Async API\n" + "="*50)
        
        # Test health
        print("\n1. Testing /health")
        response = await client.get(f"{base_url}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        # Test entities list
        print("\n2. Testing /api/v1/entities")
        response = await client.get(f"{base_url}/api/v1/entities?limit=5")
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Found {len(data['data']['entities'])} entities")
        
        # Test search
        print("\n3. Testing /api/v1/entities/search")
        response = await client.get(f"{base_url}/api/v1/entities/search?name=test")
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Search returned {data['data']['count']} results")
        
        # Test statistics
        print("\n4. Testing /api/v1/statistics")
        response = await client.get(f"{base_url}/api/v1/statistics")
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Statistics: {data['data']['entities']}")
        
        # Test changes
        print("\n5. Testing /api/v1/changes")
        response = await client.get(f"{base_url}/api/v1/changes?days=7")
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Change summary: {data['data']['summary']['totals']}")
        
        print("\n" + "="*50)
        print("✅ All tests completed!")

if __name__ == "__main__":
    asyncio.run(test_api())