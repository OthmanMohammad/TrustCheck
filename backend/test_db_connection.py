import asyncio
from src.infrastructure.database.connection import db_manager

async def test_connection():
    is_connected = await db_manager.check_connection()
    print(f"Database connected: {is_connected}")
    
    if is_connected:
        async with db_manager.get_session() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"PostgreSQL version: {version}")

asyncio.run(test_connection())