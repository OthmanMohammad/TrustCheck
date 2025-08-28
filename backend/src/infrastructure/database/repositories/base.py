"""
Base Repository Implementation with Common SQLAlchemy Operations - FIXED
"""

from typing import Type, Any, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from src.core.exceptions import DatabaseError, handle_exception
from src.core.logging_config import get_logger

class SQLAlchemyBaseRepository:
    """Base repository with common database operations."""
    
    def __init__(self, session: Session, model_class: Type):
        self.session = session
        self.model_class = model_class
        self.logger = get_logger(f"{self.__class__.__name__}")
    
    # REMOVED async - these are synchronous operations with SQLAlchemy
    def begin_transaction(self) -> None:
        """Begin database transaction."""
        try:
            if not self.session.in_transaction():
                self.session.begin()
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={"operation": "begin_transaction"})
            raise DatabaseError("Failed to begin transaction", cause=e)
    
    def commit_transaction(self) -> None:
        """Commit current transaction."""
        try:
            self.session.commit()
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={"operation": "commit_transaction"})
            raise DatabaseError("Failed to commit transaction", cause=e)
    
    def rollback_transaction(self) -> None:
        """Rollback current transaction."""
        try:
            self.session.rollback()
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={"operation": "rollback_transaction"})
            raise DatabaseError("Failed to rollback transaction", cause=e)
    
    def health_check(self) -> bool:
        """Check repository health/connectivity."""
        try:
            self.session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            self.logger.warning(f"Health check failed: {e}")
            return False
    
    # Keep async wrappers for compatibility with async interfaces
    async def begin_transaction_async(self) -> None:
        """Async wrapper for begin_transaction."""
        return self.begin_transaction()
    
    async def commit_transaction_async(self) -> None:
        """Async wrapper for commit_transaction."""
        return self.commit_transaction()
    
    async def rollback_transaction_async(self) -> None:
        """Async wrapper for rollback_transaction."""
        return self.rollback_transaction()
    
    async def health_check_async(self) -> bool:
        """Async wrapper for health_check."""
        return self.health_check()