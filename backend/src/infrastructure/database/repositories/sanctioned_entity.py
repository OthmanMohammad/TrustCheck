"""
SQLAlchemy Sanctioned Entity Repository Implementation - FIXED with Proper Async Support

This repository supports both sync (for v1 API) and async (for v2 API) operations.
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, desc, func, text, String, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import asyncio
from functools import wraps

from src.core.domain.entities import SanctionedEntityDomain, PersonalInfo, Address
from src.core.domain.repositories import SanctionedEntityRepository
from src.core.enums import DataSource, EntityType
from src.core.exceptions import (
    ResourceNotFoundError, DatabaseError, handle_exception, ValidationError
)
from src.core.logging_config import get_logger
from src.infrastructure.database.models import SanctionedEntity as SanctionedEntityORM

logger = get_logger(__name__)

def async_compatible(func):
    """Decorator to make sync methods callable from async context."""
    @wraps(func)
    async def async_wrapper(self, *args, **kwargs):
        if self.is_async:
            # For async session, we need to use async operations
            return await self._execute_async(func.__name__, *args, **kwargs)
        else:
            # For sync session, run in executor to not block event loop
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func, self, *args, **kwargs)
    
    # Store both sync and async versions
    func.async_version = async_wrapper
    return func

class SQLAlchemySanctionedEntityRepository:
    """
    SQLAlchemy implementation of SanctionedEntityRepository.
    Supports both sync and async operations.
    """
    
    def __init__(self, session: Union[Session, AsyncSession]):
        self.session = session
        self.is_async = isinstance(session, AsyncSession)
        self.logger = get_logger(__name__)
    
    def _orm_to_domain(self, orm_entity: SanctionedEntityORM) -> SanctionedEntityDomain:
        """Convert ORM model to domain entity."""
        if not orm_entity:
            return None
            
        # Handle personal info for persons
        personal_info = None
        if orm_entity.entity_type == EntityType.PERSON.value:
            personal_info = PersonalInfo(
                first_name=None,
                last_name=orm_entity.name,
                date_of_birth=orm_entity.dates_of_birth[0] if orm_entity.dates_of_birth else None,
                place_of_birth=orm_entity.places_of_birth[0] if orm_entity.places_of_birth else None,
                nationality=orm_entity.nationalities[0] if orm_entity.nationalities else None
            )
        
        # Convert address strings to Address objects
        addresses = []
        if orm_entity.addresses:
            for addr_str in orm_entity.addresses:
                if isinstance(addr_str, str):
                    parts = addr_str.split(', ')
                    address = Address(
                        street=parts[0] if len(parts) > 0 else None,
                        city=parts[1] if len(parts) > 1 else None,
                        country=parts[-1] if len(parts) > 2 else None
                    )
                    addresses.append(address)
        
        return SanctionedEntityDomain(
            uid=orm_entity.uid,
            name=orm_entity.name,
            entity_type=EntityType(orm_entity.entity_type),
            source=DataSource(orm_entity.source),
            programs=orm_entity.programs or [],
            aliases=orm_entity.aliases or [],
            addresses=addresses,
            personal_info=personal_info,
            nationalities=orm_entity.nationalities or [],
            remarks=orm_entity.remarks,
            is_active=orm_entity.is_active,
            created_at=orm_entity.created_at,
            updated_at=orm_entity.updated_at,
            last_seen=orm_entity.last_seen,
            content_hash=orm_entity.content_hash
        )
    
    def _domain_to_orm(self, domain_entity: SanctionedEntityDomain) -> SanctionedEntityORM:
        """Convert domain entity to ORM model."""
        # Convert Address objects to strings
        address_strings = []
        for addr in domain_entity.addresses:
            address_strings.append(str(addr))
        
        return SanctionedEntityORM(
            uid=domain_entity.uid,
            name=domain_entity.name,
            entity_type=domain_entity.entity_type.value,
            source=domain_entity.source.value,
            programs=domain_entity.programs,
            aliases=domain_entity.aliases,
            addresses=address_strings,
            dates_of_birth=([domain_entity.personal_info.date_of_birth] 
                           if domain_entity.personal_info and domain_entity.personal_info.date_of_birth 
                           else []),
            places_of_birth=([domain_entity.personal_info.place_of_birth]
                            if domain_entity.personal_info and domain_entity.personal_info.place_of_birth
                            else []),
            nationalities=domain_entity.nationalities,
            remarks=domain_entity.remarks,
            is_active=domain_entity.is_active,
            created_at=domain_entity.created_at,
            updated_at=domain_entity.updated_at,
            last_seen=domain_entity.last_seen,
            content_hash=domain_entity.content_hash
        )
    
    # ======================== ASYNC EXECUTION HELPER ========================
    
    async def _execute_async(self, method_name: str, *args, **kwargs):
        """Execute the async version of a method."""
        method = getattr(self, f'_async_{method_name}')
        return await method(*args, **kwargs)
    
    # ======================== SYNC METHODS (for v1 API) ========================
    
    @async_compatible
    def find_all(
        self,
        active_only: bool = True,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Find all entities with pagination (sync version)."""
        try:
            query = self.session.query(SanctionedEntityORM)
            
            if active_only:
                query = query.filter(SanctionedEntityORM.is_active == True)
            
            query = query.order_by(desc(SanctionedEntityORM.updated_at))
            query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            orm_entities = query.all()
            return [self._orm_to_domain(orm_entity) for orm_entity in orm_entities]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_all",
                "active_only": active_only,
                "limit": limit,
                "offset": offset
            })
            raise DatabaseError("Failed to retrieve all entities", cause=e)
    
    @async_compatible
    def get_by_uid(self, uid: str) -> Optional[SanctionedEntityDomain]:
        """Get entity by unique identifier (sync version)."""
        try:
            orm_entity = self.session.query(SanctionedEntityORM).filter(
                SanctionedEntityORM.uid == uid
            ).first()
            
            return self._orm_to_domain(orm_entity) if orm_entity else None
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "get_by_uid",
                "entity_uid": uid
            })
            raise DatabaseError("Failed to retrieve entity", cause=e)
    
    @async_compatible
    def find_by_source(
        self, 
        source: DataSource, 
        active_only: bool = True,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Find entities by source (sync version)."""
        try:
            query = self.session.query(SanctionedEntityORM).filter(
                SanctionedEntityORM.source == source.value
            )
            
            if active_only:
                query = query.filter(SanctionedEntityORM.is_active == True)
            
            query = query.order_by(desc(SanctionedEntityORM.updated_at))
            query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            orm_entities = query.all()
            return [self._orm_to_domain(orm_entity) for orm_entity in orm_entities]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_by_source",
                "source": source.value
            })
            raise DatabaseError("Failed to query entities by source", cause=e)
    
    @async_compatible
    def find_by_entity_type(
        self, 
        entity_type: EntityType,
        limit: Optional[int] = None,
        offset: int = 0  
    ) -> List[SanctionedEntityDomain]:
        """Find entities by type (sync version)."""
        try:
            query = self.session.query(SanctionedEntityORM).filter(
                SanctionedEntityORM.entity_type == entity_type.value,
                SanctionedEntityORM.is_active == True
            )
            
            query = query.order_by(desc(SanctionedEntityORM.updated_at))
            query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            orm_entities = query.all()
            return [self._orm_to_domain(orm_entity) for orm_entity in orm_entities]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "find_by_entity_type",
                "entity_type": entity_type.value
            })
            raise DatabaseError("Failed to query entities by type", cause=e)
    
    @async_compatible
    def search_by_name(
        self, 
        name: str, 
        fuzzy: bool = False,
        limit: int = 20,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Search entities by name (sync version)."""
        try:
            query = self.session.query(SanctionedEntityORM).filter(
                or_(
                    SanctionedEntityORM.name.ilike(f'%{name}%'),
                    func.cast(SanctionedEntityORM.aliases, String).ilike(f'%{name}%')
                ),
                SanctionedEntityORM.is_active == True
            )
            
            query = query.order_by(SanctionedEntityORM.name)
            query = query.offset(offset).limit(limit)
            orm_entities = query.all()
            
            return [self._orm_to_domain(orm_entity) for orm_entity in orm_entities]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "search_by_name",
                "name": name,
                "fuzzy": fuzzy
            })
            raise DatabaseError("Failed to search entities by name", cause=e)
    
    @async_compatible
    def get_statistics(self) -> Dict[str, Any]:
        """Get repository statistics (sync version)."""
        try:
            # Total counts
            total_active = self.session.query(SanctionedEntityORM).filter(
                SanctionedEntityORM.is_active == True
            ).count()
            
            total_inactive = self.session.query(SanctionedEntityORM).filter(
                SanctionedEntityORM.is_active == False
            ).count()
            
            # Count by source
            source_stats = self.session.query(
                SanctionedEntityORM.source,
                func.count(SanctionedEntityORM.id).label('count')
            ).filter(
                SanctionedEntityORM.is_active == True
            ).group_by(SanctionedEntityORM.source).all()
            
            # Count by entity type
            type_stats = self.session.query(
                SanctionedEntityORM.entity_type,
                func.count(SanctionedEntityORM.id).label('count')
            ).filter(
                SanctionedEntityORM.is_active == True
            ).group_by(SanctionedEntityORM.entity_type).all()
            
            return {
                'total_active': total_active,
                'total_inactive': total_inactive,
                'by_source': {row.source: row.count for row in source_stats},
                'by_type': {row.entity_type: row.count for row in type_stats},
                'last_updated': datetime.utcnow().isoformat()
            }
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={"operation": "get_statistics"})
            raise DatabaseError("Failed to get repository statistics", cause=e)
    
    # ======================== ASYNC METHODS (for v2 API) ========================
    
    async def _async_find_all(
        self,
        active_only: bool = True,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Find all entities with pagination (async version)."""
        try:
            query = select(SanctionedEntityORM)
            
            if active_only:
                query = query.where(SanctionedEntityORM.is_active == True)
            
            query = query.order_by(desc(SanctionedEntityORM.updated_at))
            query = query.offset(offset)
            
            if limit:
                query = query.limit(limit)
            
            result = await self.session.execute(query)
            orm_entities = result.scalars().all()
            
            return [self._orm_to_domain(orm_entity) for orm_entity in orm_entities]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "async_find_all",
                "active_only": active_only,
                "limit": limit,
                "offset": offset
            })
            raise DatabaseError("Failed to retrieve all entities", cause=e)
    
    async def _async_get_by_uid(self, uid: str) -> Optional[SanctionedEntityDomain]:
        """Get entity by unique identifier (async version)."""
        try:
            query = select(SanctionedEntityORM).where(
                SanctionedEntityORM.uid == uid
            )
            result = await self.session.execute(query)
            orm_entity = result.scalar_one_or_none()
            
            return self._orm_to_domain(orm_entity) if orm_entity else None
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "async_get_by_uid",
                "entity_uid": uid
            })
            raise DatabaseError("Failed to retrieve entity", cause=e)
    
    async def _async_find_by_source(
        self, 
        source: DataSource, 
        active_only: bool = True,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Find entities by source (async version)."""
        try:
            query = select(SanctionedEntityORM).where(
                SanctionedEntityORM.source == source.value
            )
            
            if active_only:
                query = query.where(SanctionedEntityORM.is_active == True)
            
            query = query.order_by(desc(SanctionedEntityORM.updated_at))
            query = query.offset(offset)
            
            if limit:
                query = query.limit(limit)
            
            result = await self.session.execute(query)
            orm_entities = result.scalars().all()
            
            return [self._orm_to_domain(orm_entity) for orm_entity in orm_entities]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "async_find_by_source",
                "source": source.value
            })
            raise DatabaseError("Failed to query entities by source", cause=e)
    
    async def _async_find_by_entity_type(
        self, 
        entity_type: EntityType,
        limit: Optional[int] = None,
        offset: int = 0  
    ) -> List[SanctionedEntityDomain]:
        """Find entities by type (async version)."""
        try:
            query = select(SanctionedEntityORM).where(
                and_(
                    SanctionedEntityORM.entity_type == entity_type.value,
                    SanctionedEntityORM.is_active == True
                )
            )
            
            query = query.order_by(desc(SanctionedEntityORM.updated_at))
            query = query.offset(offset)
            
            if limit:
                query = query.limit(limit)
            
            result = await self.session.execute(query)
            orm_entities = result.scalars().all()
            
            return [self._orm_to_domain(orm_entity) for orm_entity in orm_entities]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "async_find_by_entity_type",
                "entity_type": entity_type.value
            })
            raise DatabaseError("Failed to query entities by type", cause=e)
    
    async def _async_search_by_name(
        self, 
        name: str, 
        fuzzy: bool = False,
        limit: int = 20,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Search entities by name (async version)."""
        try:
            query = select(SanctionedEntityORM).where(
                and_(
                    or_(
                        SanctionedEntityORM.name.ilike(f'%{name}%'),
                        func.cast(SanctionedEntityORM.aliases, String).ilike(f'%{name}%')
                    ),
                    SanctionedEntityORM.is_active == True
                )
            )
            
            query = query.order_by(SanctionedEntityORM.name)
            query = query.offset(offset).limit(limit)
            
            result = await self.session.execute(query)
            orm_entities = result.scalars().all()
            
            return [self._orm_to_domain(orm_entity) for orm_entity in orm_entities]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "async_search_by_name",
                "name": name,
                "fuzzy": fuzzy
            })
            raise DatabaseError("Failed to search entities by name", cause=e)
    
    async def _async_get_statistics(self) -> Dict[str, Any]:
        """Get repository statistics (async version)."""
        try:
            # Total active count
            active_query = select(func.count(SanctionedEntityORM.id)).where(
                SanctionedEntityORM.is_active == True
            )
            active_result = await self.session.execute(active_query)
            total_active = active_result.scalar() or 0
            
            # Total inactive count
            inactive_query = select(func.count(SanctionedEntityORM.id)).where(
                SanctionedEntityORM.is_active == False
            )
            inactive_result = await self.session.execute(inactive_query)
            total_inactive = inactive_result.scalar() or 0
            
            # Count by source
            source_query = select(
                SanctionedEntityORM.source,
                func.count(SanctionedEntityORM.id).label('count')
            ).where(
                SanctionedEntityORM.is_active == True
            ).group_by(SanctionedEntityORM.source)
            
            source_result = await self.session.execute(source_query)
            source_stats = source_result.all()
            
            # Count by entity type
            type_query = select(
                SanctionedEntityORM.entity_type,
                func.count(SanctionedEntityORM.id).label('count')
            ).where(
                SanctionedEntityORM.is_active == True
            ).group_by(SanctionedEntityORM.entity_type)
            
            type_result = await self.session.execute(type_query)
            type_stats = type_result.all()
            
            return {
                'total_active': total_active,
                'total_inactive': total_inactive,
                'by_source': {row.source: row.count for row in source_stats},
                'by_type': {row.entity_type: row.count for row in type_stats},
                'last_updated': datetime.utcnow().isoformat()
            }
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={"operation": "async_get_statistics"})
            raise DatabaseError("Failed to get repository statistics", cause=e)
    
    # ======================== OTHER REQUIRED METHODS ========================
    
    @async_compatible
    def create(self, entity: SanctionedEntityDomain) -> SanctionedEntityDomain:
        """Create new sanctioned entity."""
        try:
            orm_entity = self._domain_to_orm(entity)
            self.session.add(orm_entity)
            self.session.flush()
            
            return self._orm_to_domain(orm_entity)
            
        except IntegrityError as e:
            handle_exception(e, self.logger, context={
                "operation": "create_entity",
                "entity_uid": entity.uid
            })
            raise ValidationError(f"Entity with UID {entity.uid} already exists", cause=e)
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "create_entity",
                "entity_uid": entity.uid
            })
            raise DatabaseError("Failed to create entity", cause=e)
    
    @async_compatible
    def get_all_for_change_detection(
        self, 
        source: DataSource
    ) -> List[SanctionedEntityDomain]:
        """Get all entities for change detection comparison."""
        try:
            orm_entities = self.session.query(SanctionedEntityORM).filter(
                SanctionedEntityORM.source == source.value,
                SanctionedEntityORM.is_active == True
            ).all()
            
            return [self._orm_to_domain(orm_entity) for orm_entity in orm_entities]
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "get_all_for_change_detection",
                "source": source.value
            })
            raise DatabaseError("Failed to get entities for change detection", cause=e)
    
    # ======================== HEALTH CHECK ========================
    
    async def health_check(self) -> bool:
        """Check repository health/connectivity."""
        try:
            if self.is_async:
                await self.session.execute(text("SELECT 1"))
            else:
                self.session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
    
    # ======================== METHOD RESOLUTION ========================
    
    def __getattr__(self, name):
        """
        Route method calls to sync or async versions based on context.
        This allows the repository to be used seamlessly in both contexts.
        """
        # Check if it's an async method call (from v2 API)
        if name.endswith('_async') or name.startswith('find_') or name.startswith('get_') or name == 'search_by_name' or name == 'create':
            base_method = getattr(self, name.replace('_async', ''), None)
            if base_method and hasattr(base_method, 'async_version'):
                return base_method.async_version
        
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")