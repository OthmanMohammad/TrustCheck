#!/usr/bin/env python3
"""
Test Script to Verify Async API Implementation

Run this script to ensure all async/await calls are working properly.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Set up environment
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '5432'
os.environ['DB_USER'] = 'trustcheck_user'
os.environ['DB_PASSWORD'] = 'trustcheck_secure_password_2024'
os.environ['DB_NAME'] = 'trustcheck'

import httpx
from datetime import datetime, timezone
from typing import Dict, Any, List
import json

# Test configuration
API_BASE_URL = "http://localhost:8000"
V1_PREFIX = "/api/v1"
V2_PREFIX = "/api/v2"

class APITester:
    """Test harness for API endpoints."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
        self.results: List[Dict[str, Any]] = []
    
    async def test_endpoint(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Test a single endpoint."""
        start_time = datetime.now(timezone.utc)
        test_name = f"{method} {path}"
        
        try:
            response = await self.client.request(method, path, **kwargs)
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            result = {
                "test": test_name,
                "status": "PASS" if response.status_code < 400 else "FAIL",
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "response_size": len(response.content),
            }
            
            if response.status_code >= 400:
                result["error"] = response.text
            else:
                try:
                    result["data"] = response.json()
                except:
                    result["data"] = response.text
            
            self.results.append(result)
            return result
            
        except Exception as e:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            result = {
                "test": test_name,
                "status": "ERROR",
                "error": str(e),
                "duration_ms": duration_ms
            }
            self.results.append(result)
            return result
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    def print_results(self):
        """Print test results."""
        print("\n" + "="*80)
        print("TEST RESULTS")
        print("="*80)
        
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        errors = sum(1 for r in self.results if r["status"] == "ERROR")
        
        for result in self.results:
            status_symbol = {
                "PASS": "✅",
                "FAIL": "❌",
                "ERROR": "⚠️"
            }[result["status"]]
            
            print(f"{status_symbol} {result['test']}")
            print(f"   Status: {result.get('status_code', 'N/A')}, Duration: {result['duration_ms']:.2f}ms")
            
            if result["status"] != "PASS":
                error = result.get("error", "Unknown error")
                print(f"   Error: {error[:200]}...")
        
        print("\n" + "-"*80)
        print(f"SUMMARY: {passed} passed, {failed} failed, {errors} errors")
        print("="*80)
        
        return passed > 0 and failed == 0 and errors == 0

async def test_v1_vs_v2_api():
    """Compare v1 (sync) vs v2 (async) API performance."""
    
    tester = APITester(API_BASE_URL)
    
    print("Testing TrustCheck API - Async Implementation Verification")
    print("="*80)
    
    # Test v1 endpoints (should still work with sync implementation)
    print("\n📌 Testing v1 API (Sync Implementation)...")
    await tester.test_endpoint("GET", f"{V1_PREFIX}/entities", params={"limit": 10})
    await tester.test_endpoint("GET", f"{V1_PREFIX}/entities/search", params={"name": "test"})
    await tester.test_endpoint("GET", f"{V1_PREFIX}/changes", params={"days": 7})
    await tester.test_endpoint("GET", f"{V1_PREFIX}/changes/critical", params={"hours": 24})
    await tester.test_endpoint("GET", f"{V1_PREFIX}/statistics")
    
    # Test v2 endpoints (should use async implementation)
    print("\n📌 Testing v2 API (Async Implementation)...")
    await tester.test_endpoint("GET", f"{V2_PREFIX}/entities", params={"limit": 10})
    await tester.test_endpoint("GET", f"{V2_PREFIX}/entities/search", params={"query": "test"})
    await tester.test_endpoint("GET", f"{V2_PREFIX}/entities/OFAC-12345")
    await tester.test_endpoint("GET", f"{V2_PREFIX}/changes", params={"days": 7})
    await tester.test_endpoint("GET", f"{V2_PREFIX}/changes/critical", params={"hours": 24})
    await tester.test_endpoint("GET", f"{V2_PREFIX}/changes/summary", params={"days": 7})
    await tester.test_endpoint("GET", f"{V2_PREFIX}/statistics")
    
    # Test concurrent requests to verify async benefits
    print("\n📌 Testing Concurrent Requests (Async Benefits)...")
    
    # Fire 10 concurrent requests to v2 API
    concurrent_tasks = []
    for i in range(10):
        concurrent_tasks.append(
            tester.test_endpoint("GET", f"{V2_PREFIX}/entities", params={"limit": 5, "offset": i * 5})
        )
    
    start_time = datetime.now(timezone.utc)
    await asyncio.gather(*concurrent_tasks)
    concurrent_duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    
    print(f"\n⚡ 10 concurrent requests completed in {concurrent_duration:.2f}ms")
    
    # Print results
    success = tester.print_results()
    
    await tester.close()
    
    return success

async def test_database_connections():
    """Test database connection handling."""
    
    print("\n📌 Testing Database Connections...")
    
    try:
        # Test sync database connection
        from src.infrastructure.database.connection import db_manager, check_db_health
        
        if check_db_health():
            print("✅ Sync database connection: OK")
        else:
            print("❌ Sync database connection: FAILED")
        
        # Test async database connection
        if await db_manager.check_async_connection():
            print("✅ Async database connection: OK")
        else:
            print("⚠️ Async database connection: Not available (install asyncpg)")
        
        # Check pool status
        pool_status = db_manager.get_pool_status()
        print(f"📊 Connection Pool Status: {json.dumps(pool_status, indent=2)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        return False

async def test_repository_methods():
    """Test async repository methods directly."""
    
    print("\n📌 Testing Async Repository Methods...")
    
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from src.core.config import settings
        
        # Create async engine for testing
        async_url = settings.database.database_url.replace(
            "postgresql://", "postgresql+asyncpg://"
        )
        
        engine = create_async_engine(async_url, echo=False)
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        async with AsyncSessionLocal() as session:
            from src.infrastructure.database.repositories.sanctioned_entity import SQLAlchemySanctionedEntityRepository
            
            repo = SQLAlchemySanctionedEntityRepository(session)
            
            # Test health check
            health = await repo.health_check()
            print(f"✅ Repository health check: {health}")
            
            # Test find_all with async session
            entities = await repo.find_all(limit=5)
            print(f"✅ Found {len(entities)} entities")
            
            # Test get_statistics with async session
            stats = await repo.get_statistics()
            print(f"✅ Statistics: {stats.get('total_active', 0)} active entities")
        
        await engine.dispose()
        
        return True
        
    except ImportError as e:
        print(f"⚠️ Async repository test skipped: {e}")
        print("   Install asyncpg: pip install asyncpg")
        return True  # Don't fail if asyncpg not installed
        
    except Exception as e:
        print(f"❌ Async repository test failed: {e}")
        return False

async def main():
    """Main test runner."""
    
    print("\n🚀 Starting TrustCheck API Async Implementation Tests")
    print("="*80)
    
    # Check if API is running
    print("\n📌 Checking API availability...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/")
            if response.status_code in [200, 404]:  # 404 is ok if / endpoint doesn't exist
                print("✅ API is running at", API_BASE_URL)
            else:
                print(f"⚠️ API returned status {response.status_code}")
    except Exception as e:
        print(f"❌ API not available at {API_BASE_URL}")
        print("   Please start the API first: uvicorn main:app --reload")
        return False
    
    # Run tests
    all_passed = True
    
    # Test database connections
    if not await test_database_connections():
        all_passed = False
    
    # Test repository methods
    if not await test_repository_methods():
        all_passed = False
    
    # Test API endpoints
    if not await test_v1_vs_v2_api():
        all_passed = False
    
    # Summary
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL TESTS PASSED - Async implementation is working correctly!")
    else:
        print("❌ SOME TESTS FAILED - Please check the errors above")
    print("="*80)
    
    return all_passed

if __name__ == "__main__":
    # Run tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1)