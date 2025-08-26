"""
Base Repository Implementation

Abstract repository with common CRUD operations for all entities.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional, Dict, Any, Type
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, DataError
from sqlalchemy import desc, asc, and_, or_, func, text
from contextlib import contextmanager
from datetime import datetime

from src.infrastructure.database.models.base import BaseModel
from src.core.exceptions import (
    EntityNotFoundError,
    DatabaseIntegrityError,
    DatabaseOperationError
)
from src.core.enums import SortOrder
from src.utils.logging import get_logger

# ======================== TYPE VARIABLES ========================

ModelType = TypeVar("ModelType", bound=BaseModel)

# ======================== BASE REPOSITORY ========================

class BaseRepository(ABC, Generic[ModelType]):
    """
    Abstract base repository with common CRUD operations.
    
    Features:
    - Generic CRUD operations
    - Transaction management
    - Error handling and logging
    - Query builders
    - Pagination support
    """
    
    def __init__(self, model: Type[ModelType], db_session: Session):
        self.model = model
        self.db_session = db_session
        self.logger = get_logger(f"repository.{model.__tablename__}")
    
    # ======================== TRANSACTION MANAGEMENT ========================
    
    @contextmanager
    def transaction(self):
        """Database transaction context manager."""
        try:
            yield self.db_session
            self.db_session.commit()
        except Exception as e:
            self.db_session.rollback()
            self.logger.error(f"Transaction failed: {e}")
            raise DatabaseOperationError(f"Transaction failed: {str(e)}")
        finally:
            pass  # Session lifecycle managed externally
    
    # ======================== CRUD OPERATIONS ========================
    
    def create(self, obj_data: Dict[str, Any]) -> ModelType:
        """Create a new entity."""
        try:
            db_obj = self.model(**obj_data)
            self.db_session.add(db_obj)
            self.db_session.commit()
            self.db_session.refresh(db_obj)
            
            self.logger.info(f"Created {self.model.__name__} with ID: {getattr(db_obj, 'id', 'N/A')}")
            return db_obj
            
        except IntegrityError as e:
            self.db_session.rollback()
            self.logger.error(f"Integrity error creating {self.model.__name__}: {e}")
            raise DatabaseIntegrityError(f"Failed to create {self.model.__name__}: {str(e)}")
        except Exception as e:
            self.db_session.rollback()
            self.logger.error(f"Error creating {self.model.__name__}: {e}")
            raise DatabaseOperationError(f"Failed to create {self.model.__name__}: {str(e)}")
    
    def get_by_id(self, id: Any) -> Optional[ModelType]:
        """Get entity by ID."""
        try:
            entity = self.db_session.query(self.model).filter(self.model.id == id).first()
            if entity:
                self.logger.debug(f"Retrieved {self.model.__name__} with ID: {id}")
            return entity
        except Exception as e:
            self.logger.error(f"Error retrieving {self.model.__name__} with ID {id}: {e}")
            raise DatabaseOperationError(f"Failed to retrieve {self.model.__name__}: {str(e)}")
    
    def get_by_field(self, field_name: str, value: Any) -> Optional[ModelType]:
        """Get entity by specific field."""
        try:
            if not hasattr(self.model, field_name):
                raise ValueError(f"Model {self.model.__name__} has no field '{field_name}'")
            
            field = getattr(self.model, field_name)
            entity = self.db_session.query(self.model).filter(field == value).first()
            
            if entity:
                self.logger.debug(f"Retrieved {self.model.__name__} by {field_name}: {value}")
            
            return entity
        except Exception as e:
            self.logger.error(f"Error retrieving {self.model.__name__} by {field_name}: {e}")
            raise DatabaseOperationError(f"Failed to retrieve {self.model.__name__}: {str(e)}")
    
    def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[str] = None,
        order_direction: SortOrder = SortOrder.DESC,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        """Get multiple entities with pagination and filtering."""
        try:
            query = self.db_session.query(self.model)
            
            # Apply filters
            if filters:
                for field_name, value in filters.items():
                    if hasattr(self.model, field_name):
                        field = getattr(self.model, field_name)
                        if isinstance(value, list):
                            query = query.filter(field.in_(value))
                        elif isinstance(value, str) and value.startswith('%'):
                            query = query.filter(field.ilike(value))
                        else:
                            query = query.filter(field == value)
            
            # Apply ordering
            if order_by and hasattr(self.model, order_by):
                field = getattr(self.model, order_by)
                if order_direction == SortOrder.DESC:
                    query = query.order_by(desc(field))
                else:
                    query = query.order_by(asc(field))
            else:
                # Default ordering by created_at if available
                if hasattr(self.model, 'created_at'):
                    query = query.order_by(desc(self.model.created_at))
            
            # Apply pagination
            entities = query.offset(skip).limit(limit).all()
            
            self.logger.debug(f"Retrieved {len(entities)} {self.model.__name__} entities")
            return entities
            
        except Exception as e:
            self.logger.error(f"Error retrieving multiple {self.model.__name__}: {e}")
            raise DatabaseOperationError(f"Failed to retrieve {self.model.__name__} list: {str(e)}")
    
    def update(self, id: Any, update_data: Dict[str, Any]) -> ModelType:
        """Update existing entity."""
        try:
            db_obj = self.get_by_id(id)
            if not db_obj:
                raise EntityNotFoundError(self.model.__name__, id)
            
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)
            
            # Update timestamp if available
            if hasattr(db_obj, 'updated_at'):
                db_obj.updated_at = datetime.utcnow()
            
            self.db_session.commit()
            self.db_session.refresh(db_obj)
            
            self.logger.info(f"Updated {self.model.__name__} with ID: {id}")
            return db_obj
            
        except EntityNotFoundError:
            raise
        except IntegrityError as e:
            self.db_session.rollback()
            self.logger.error(f"Integrity error updating {self.model.__name__}: {e}")
            raise DatabaseIntegrityError(f"Failed to update {self.model.__name__}: {str(e)}")
        except Exception as e:
            self.db_session.rollback()
            self.logger.error(f"Error updating {self.model.__name__}: {e}")
            raise DatabaseOperationError(f"Failed to update {self.model.__name__}: {str(e)}")
    
    def delete(self, id: Any) -> bool:
        """Delete entity by ID."""
        try:
            db_obj = self.get_by_id(id)
            if not db_obj:
                raise EntityNotFoundError(self.model.__name__, id)
            
            self.db_session.delete(db_obj)
            self.db_session.commit()
            
            self.logger.info(f"Deleted {self.model.__name__} with ID: {id}")
            return True
            
        except EntityNotFoundError:
            raise
        except Exception as e:
            self.db_session.rollback()
            self.logger.error(f"Error deleting {self.model.__name__}: {e}")
            raise DatabaseOperationError(f"Failed to delete {self.model.__name__}: {str(e)}")
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count entities with optional filters."""
        try:
            query = self.db_session.query(func.count(self.model.id))
            
            if filters:
                for field_name, value in filters.items():
                    if hasattr(self.model, field_name):
                        field = getattr(self.model, field_name)
                        if isinstance(value, list):
                            query = query.filter(field.in_(value))
                        else:
                            query = query.filter(field == value)
            
            count = query.scalar()
            self.logger.debug(f"Counted {count} {self.model.__name__} entities")
            return count
            
        except Exception as e:
            self.logger.error(f"Error counting {self.model.__name__}: {e}")
            raise DatabaseOperationError(f"Failed to count {self.model.__name__}: {str(e)}")
    
    def exists(self, id: Any) -> bool:
        """Check if entity exists."""
        try:
            exists = self.db_session.query(
                self.db_session.query(self.model).filter(self.model.id == id).exists()
            ).scalar()
            return bool(exists)
        except Exception as e:
            self.logger.error(f"Error checking existence of {self.model.__name__}: {e}")
            return False