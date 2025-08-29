# test_integration.py
import asyncio
import aiohttp

async def test_full_flow():
    async with aiohttp.ClientSession() as session:
        # Test health
        async with session.get('http://localhost:8000/health') as resp:
            health = await resp.json()
            print(f"Health: {health}")
        
        # Test entities endpoint
        async with session.get('http://localhost:8000/api/v2/entities?limit=10') as resp:
            data = await resp.json()
            print(f"Entities: {data.get('pagination', {}).get('returned', 0)} returned")
        
        # Test changes endpoint
        async with session.get('http://localhost:8000/api/v2/changes?days=7') as resp:
            data = await resp.json()
            print(f"Changes: {data.get('pagination', {}).get('returned', 0)} changes")

asyncio.run(test_full_flow())