"""
Base Repository Implementation - Fully Async
"""

from typing import Type, Any, Dict
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from src.core.exceptions import DatabaseError, handle_exception
from src.core.logging_config import get_logger

class SQLAlchemyBaseRepository:
    """Base repository with common async database operations."""
    
    def __init__(self, session: AsyncSession, model_class: Type):
        self.session = session
        self.model_class = model_class
        self.logger = get_logger(f"{self.__class__.__name__}")
    
    async def begin_transaction(self) -> None:
        """Begin database transaction."""
        try:
            # AsyncSession handles transactions automatically
            pass
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={"operation": "begin_transaction"})
            raise DatabaseError("Failed to begin transaction", cause=e)
    
    async def commit_transaction(self) -> None:
        """Commit current transaction."""
        try:
            await self.session.commit()
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={"operation": "commit_transaction"})
            raise DatabaseError("Failed to commit transaction", cause=e)
    
    async def rollback_transaction(self) -> None:
        """Rollback current transaction."""
        try:
            await self.session.rollback()
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={"operation": "rollback_transaction"})
            raise DatabaseError("Failed to rollback transaction", cause=e)
    
    async def health_check(self) -> bool:
        """Check repository health/connectivity."""
        try:
            await self.session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            self.logger.warning(f"Health check failed: {e}")
            return False