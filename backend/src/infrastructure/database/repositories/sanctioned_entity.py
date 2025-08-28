"""
SQLAlchemy Sanctioned Entity Repository Implementation - FIXED
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, text, String
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.core.domain.entities import SanctionedEntityDomain, PersonalInfo, Address
from src.core.domain.repositories import SanctionedEntityRepository
from src.core.enums import DataSource, EntityType
from src.core.exceptions import (
    ResourceNotFoundError, DatabaseError, handle_exception, ValidationError
)
from src.core.logging_config import get_logger, log_performance
from src.infrastructure.database.repositories.base import SQLAlchemyBaseRepository
from src.infrastructure.database.models import SanctionedEntity as SanctionedEntityORM

logger = get_logger(__name__)

class SQLAlchemySanctionedEntityRepository(SQLAlchemyBaseRepository):
    """SQLAlchemy implementation of SanctionedEntityRepository - FIXED."""
    
    def __init__(self, session: Session):
        super().__init__(session, SanctionedEntityORM)
        self.logger = get_logger(__name__)
    
    def _orm_to_domain(self, orm_entity: SanctionedEntityORM) -> SanctionedEntityDomain:
        """Convert ORM model to domain entity."""
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
                    parts = addr_str.split(', ') if isinstance(addr_str, str) else []
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
    
    # REMOVED async - these are synchronous operations
    def find_all(
        self,
        active_only: bool = True,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Find all entities with pagination."""
        try:
            query = self.session.query(SanctionedEntityORM)
            
            if active_only:
                query = query.filter(SanctionedEntityORM.is_active == True)
            
            # Order by updated_at for consistent pagination
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
    
    def get_by_uid(self, uid: str) -> Optional[SanctionedEntityDomain]:
        """Get entity by unique identifier."""
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
    
    def find_by_source(
        self, 
        source: DataSource, 
        active_only: bool = True,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Find entities by source."""
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
    
    def find_by_entity_type(
        self, 
        entity_type: EntityType,
        limit: Optional[int] = None,
        offset: int = 0  
    ) -> List[SanctionedEntityDomain]:
        """Find entities by type."""
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
    
    def search_by_name(
        self, 
        name: str, 
        fuzzy: bool = False,
        limit: int = 20,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Search entities by name (including aliases)."""
        try:
            if fuzzy and self.session.bind.dialect.name == 'postgresql':
                # Use PostgreSQL similarity for fuzzy matching
                # Ensure pg_trgm extension is installed
                query = self.session.query(SanctionedEntityORM).filter(
                    or_(
                        func.similarity(SanctionedEntityORM.name, name) > 0.3,
                        self.session.query(
                            func.jsonb_array_elements_text(SanctionedEntityORM.aliases)
                        ).filter(
                            func.similarity(
                                func.jsonb_array_elements_text(SanctionedEntityORM.aliases), 
                                name
                            ) > 0.3
                        ).exists()
                    ),
                    SanctionedEntityORM.is_active == True
                )
            else:
                # Exact substring matching
                query = self.session.query(SanctionedEntityORM).filter(
                    or_(
                        SanctionedEntityORM.name.ilike(f'%{name}%'),
                        # For JSON arrays, we need to cast to text for LIKE comparison
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
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get repository statistics."""
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
    
    # Keep async versions for compatibility with interfaces that expect them
    async def find_all_async(self, *args, **kwargs):
        """Async wrapper for compatibility."""
        return self.find_all(*args, **kwargs)
    
    async def create_async(self, *args, **kwargs):
        """Async wrapper for compatibility."""
        return self.create(*args, **kwargs)
    
    async def get_by_uid_async(self, *args, **kwargs):
        """Async wrapper for compatibility."""
        return self.get_by_uid(*args, **kwargs)
    
    async def find_by_source_async(self, *args, **kwargs):
        """Async wrapper for compatibility."""
        return self.find_by_source(*args, **kwargs)
    
    async def find_by_entity_type_async(self, *args, **kwargs):
        """Async wrapper for compatibility."""
        return self.find_by_entity_type(*args, **kwargs)
    
    async def search_by_name_async(self, *args, **kwargs):
        """Async wrapper for compatibility."""
        return self.search_by_name(*args, **kwargs)
    
    async def get_statistics_async(self, *args, **kwargs):
        """Async wrapper for compatibility."""
        return self.get_statistics(*args, **kwargs)
    
    async def get_all_for_change_detection_async(self, *args, **kwargs):
        """Async wrapper for compatibility."""
        return self.get_all_for_change_detection(*args, **kwargs)
    
    async def health_check(self) -> bool:
        """Check repository health/connectivity."""
        try:
            self.session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False