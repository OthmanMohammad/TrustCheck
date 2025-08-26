"""
Concrete Repository Implementations

SQLAlchemy-based implementations of repository interfaces.
These handle all database-specific operations and ORM mapping.
"""

from typing import List, Optional, Dict, Any, Type
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import logging

# Domain imports (no SQLAlchemy dependencies)
from src.core.domain.entities import (
    SanctionedEntityDomain, ChangeEventDomain, ScraperRunDomain, 
    ContentSnapshotDomain, ChangeDetectionResult
)
from src.core.domain.repositories import (
    SanctionedEntityRepository, ChangeEventRepository,
    ScraperRunRepository, ContentSnapshotRepository
)
from src.core.enums import DataSource, EntityType, ChangeType, RiskLevel, ScrapingStatus
from src.core.exceptions import (
    ResourceNotFoundError, DatabaseError, handle_exception,
    TransactionError, ValidationError
)
from src.core.logging_config import get_logger, log_exception, log_performance

# Infrastructure imports (SQLAlchemy models)
from src.infrastructure.database.models import (
    SanctionedEntity as SanctionedEntityORM,
    ChangeEvent as ChangeEventORM,
    ScraperRun as ScraperRunORM,
    ContentSnapshot as ContentSnapshotORM
)

logger = get_logger(__name__)

# ======================== BASE REPOSITORY IMPLEMENTATION ========================

class SQLAlchemyBaseRepository:
    """Base repository implementation with common SQLAlchemy operations."""
    
    def __init__(self, session: Session, model_class: Type):
        self.session = session
        self.model_class = model_class
        self.logger = get_logger(f"{self.__class__.__name__}")
        
    async def begin_transaction(self) -> None:
        """Begin database transaction."""
        try:
            if not self.session.in_transaction():
                self.session.begin()
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={"operation": "begin_transaction"})
            raise DatabaseError("Failed to begin transaction", cause=e)
    
    async def commit_transaction(self) -> None:
        """Commit current transaction."""
        try:
            self.session.commit()
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={"operation": "commit_transaction"})
            raise DatabaseError("Failed to commit transaction", cause=e)
    
    async def rollback_transaction(self) -> None:
        """Rollback current transaction."""
        try:
            self.session.rollback()
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={"operation": "rollback_transaction"})
            raise DatabaseError("Failed to rollback transaction", cause=e)
    
    async def health_check(self) -> bool:
        """Check repository health/connectivity."""
        try:
            self.session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            self.logger.warning(f"Health check failed: {e}")
            return False

# ======================== SANCTIONED ENTITY REPOSITORY ========================

class SQLAlchemySanctionedEntityRepository(SQLAlchemyBaseRepository):
    """SQLAlchemy implementation of SanctionedEntityRepository."""
    
    def __init__(self, session: Session):
        super().__init__(session, SanctionedEntityORM)
    
    # ======================== DOMAIN-ORM MAPPING ========================
    
    def _orm_to_domain(self, orm_entity: SanctionedEntityORM) -> SanctionedEntityDomain:
        """Convert ORM model to domain entity."""
        from src.core.domain.entities import PersonalInfo, Address
        
        # Handle personal info for persons
        personal_info = None
        if orm_entity.entity_type == EntityType.PERSON.value:
            personal_info = PersonalInfo(
                # Extract from JSON or use defaults
                first_name=None,  # Would extract from entity data
                last_name=orm_entity.name,  # Simplified mapping
                date_of_birth=orm_entity.dates_of_birth[0] if orm_entity.dates_of_birth else None,
                place_of_birth=orm_entity.places_of_birth[0] if orm_entity.places_of_birth else None,
                nationality=orm_entity.nationalities[0] if orm_entity.nationalities else None
            )
        
        # Convert address strings to Address objects
        addresses = []
        if orm_entity.addresses:
            for addr_str in orm_entity.addresses:
                # Simple parsing - in production you'd have better parsing
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
    
    # ======================== BASIC CRUD OPERATIONS ========================
    
    async def create(self, entity: SanctionedEntityDomain) -> SanctionedEntityDomain:
        """Create new sanctioned entity."""
        start_time = datetime.utcnow()
        
        try:
            orm_entity = self._domain_to_orm(entity)
            self.session.add(orm_entity)
            self.session.flush()  # Get ID without committing
            
            # Convert back to get generated fields
            result = self._orm_to_domain(orm_entity)
            
            log_performance(
                self.logger,
                "create_entity",
                (datetime.utcnow() - start_time).total_seconds() * 1000,
                success=True,
                entity_uid=entity.uid,
                source=entity.source.value
            )
            
            return result
            
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
    
    async def get_by_uid(self, uid: str) -> Optional[SanctionedEntityDomain]:
        """Get entity by unique identifier."""
        start_time = datetime.utcnow()
        
        try:
            orm_entity = self.session.query(SanctionedEntityORM).filter(
                SanctionedEntityORM.uid == uid
            ).first()
            
            result = self._orm_to_domain(orm_entity) if orm_entity else None
            
            log_performance(
                self.logger,
                "get_by_uid",
                (datetime.utcnow() - start_time).total_seconds() * 1000,
                success=True,
                entity_found=result is not None,
                entity_uid=uid
            )
            
            return result
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "get_by_uid",
                "entity_uid": uid
            })
            raise DatabaseError("Failed to retrieve entity", cause=e)
    
    async def get_by_id(self, entity_id: int) -> Optional[SanctionedEntityDomain]:
        """Get entity by database ID."""
        try:
            orm_entity = self.session.get(SanctionedEntityORM, entity_id)
            return self._orm_to_domain(orm_entity) if orm_entity else None
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "get_by_id",
                "entity_id": entity_id
            })
            raise DatabaseError("Failed to retrieve entity", cause=e)
    
    async def update(self, entity: SanctionedEntityDomain) -> SanctionedEntityDomain:
        """Update existing entity."""
        start_time = datetime.utcnow()
        
        try:
            orm_entity = self.session.query(SanctionedEntityORM).filter(
                SanctionedEntityORM.uid == entity.uid
            ).first()
            
            if not orm_entity:
                raise ResourceNotFoundError("SanctionedEntity", entity.uid)
            
            # Update fields
            updated_orm = self._domain_to_orm(entity)
            for key, value in updated_orm.__dict__.items():
                if not key.startswith('_') and key != 'id':
                    setattr(orm_entity, key, value)
            
            self.session.flush()
            result = self._orm_to_domain(orm_entity)
            
            log_performance(
                self.logger,
                "update_entity",
                (datetime.utcnow() - start_time).total_seconds() * 1000,
                success=True,
                entity_uid=entity.uid,
                source=entity.source.value
            )
            
            return result
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "update_entity",
                "entity_uid": entity.uid
            })
            raise DatabaseError("Failed to update entity", cause=e)
    
    async def delete_by_uid(self, uid: str) -> bool:
        """Delete entity by UID (hard delete)."""
        try:
            result = self.session.query(SanctionedEntityORM).filter(
                SanctionedEntityORM.uid == uid
            ).delete()
            
            return result > 0
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "delete_by_uid",
                "entity_uid": uid
            })
            raise DatabaseError("Failed to delete entity", cause=e)
    
    async def deactivate_by_uid(self, uid: str) -> bool:
        """Soft delete entity by UID."""
        try:
            result = self.session.query(SanctionedEntityORM).filter(
                SanctionedEntityORM.uid == uid,
                SanctionedEntityORM.is_active == True
            ).update({
                'is_active': False,
                'updated_at': datetime.utcnow()
            })
            
            return result > 0
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "deactivate_by_uid",
                "entity_uid": uid
            })
            raise DatabaseError("Failed to deactivate entity", cause=e)
    
    # ======================== BULK OPERATIONS ========================
    
    async def create_many(self, entities: List[SanctionedEntityDomain]) -> List[SanctionedEntityDomain]:
        """Create multiple entities efficiently."""
        start_time = datetime.utcnow()
        
        try:
            orm_entities = [self._domain_to_orm(entity) for entity in entities]
            self.session.add_all(orm_entities)
            self.session.flush()
            
            results = [self._orm_to_domain(orm_entity) for orm_entity in orm_entities]
            
            log_performance(
                self.logger,
                "create_many",
                (datetime.utcnow() - start_time).total_seconds() * 1000,
                success=True,
                entity_count=len(entities)
            )
            
            return results
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "create_many",
                "entity_count": len(entities)
            })
            raise DatabaseError("Failed to create multiple entities", cause=e)
    
    async def replace_source_data(
        self, 
        source: DataSource, 
        entities: List[SanctionedEntityDomain]
    ) -> Dict[str, int]:
        """Replace all data for a source with new entities."""
        start_time = datetime.utcnow()
        
        try:
            # Get current entities for the source
            current_entities = self.session.query(SanctionedEntityORM).filter(
                SanctionedEntityORM.source == source.value
            ).all()
            
            current_uids = {entity.uid for entity in current_entities}
            new_uids = {entity.uid for entity in entities}
            
            # Calculate changes
            added_uids = new_uids - current_uids
            updated_uids = new_uids & current_uids
            removed_uids = current_uids - new_uids
            
            # Delete removed entities
            if removed_uids:
                self.session.query(SanctionedEntityORM).filter(
                    SanctionedEntityORM.source == source.value,
                    SanctionedEntityORM.uid.in_(removed_uids)
                ).delete(synchronize_session=False)
            
            # Process new and updated entities
            entities_by_uid = {entity.uid: entity for entity in entities}
            
            # Add new entities
            new_orm_entities = []
            for uid in added_uids:
                orm_entity = self._domain_to_orm(entities_by_uid[uid])
                new_orm_entities.append(orm_entity)
            
            if new_orm_entities:
                self.session.add_all(new_orm_entities)
            
            # Update existing entities
            for uid in updated_uids:
                domain_entity = entities_by_uid[uid]
                orm_entity = next(e for e in current_entities if e.uid == uid)
                
                # Update fields
                updated_orm = self._domain_to_orm(domain_entity)
                for key, value in updated_orm.__dict__.items():
                    if not key.startswith('_') and key not in ['id', 'created_at']:
                        setattr(orm_entity, key, value)
                orm_entity.updated_at = datetime.utcnow()
            
            self.session.flush()
            
            result = {
                'added': len(added_uids),
                'updated': len(updated_uids), 
                'removed': len(removed_uids)
            }
            
            log_performance(
                self.logger,
                "replace_source_data",
                (datetime.utcnow() - start_time).total_seconds() * 1000,
                success=True,
                source=source.value,
                **result
            )
            
            return result
            
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "replace_source_data",
                "source": source.value,
                "entity_count": len(entities)
            })
            raise DatabaseError("Failed to replace source data", cause=e)
    
    # ======================== QUERY OPERATIONS ========================
    
    async def find_by_source(
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
    
    async def search_by_name(
        self, 
        name: str, 
        fuzzy: bool = False,
        limit: int = 20,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Search entities by name (including aliases)."""
        try:
            if fuzzy:
                # Use PostgreSQL similarity for fuzzy matching
                query = self.session.query(SanctionedEntityORM).filter(
                    or_(
                        func.similarity(SanctionedEntityORM.name, name) > 0.3,
                        func.jsonb_array_elements_text(SanctionedEntityORM.aliases).op('%%')(name)
                    )
                )
            else:
                # Exact substring matching
                query = self.session.query(SanctionedEntityORM).filter(
                    or_(
                        SanctionedEntityORM.name.ilike(f'%{name}%'),
                        func.jsonb_array_elements_text(SanctionedEntityORM.aliases).ilike(f'%{name}%')
                    )
                )
            
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
    
    # ======================== AGGREGATE OPERATIONS ========================
    
    async def count_by_source(self, source: DataSource) -> int:
        """Count entities by source."""
        try:
            return self.session.query(SanctionedEntityORM).filter(
                SanctionedEntityORM.source == source.value,
                SanctionedEntityORM.is_active == True
            ).count()
        except SQLAlchemyError as e:
            handle_exception(e, self.logger, context={
                "operation": "count_by_source",
                "source": source.value
            })
            raise DatabaseError("Failed to count entities by source", cause=e)
    
    async def get_statistics(self) -> Dict[str, Any]:
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
    
    # ======================== CHANGE DETECTION SUPPORT ========================
    
    async def get_all_for_change_detection(
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

# Similar implementations would be created for:
# - SQLAlchemyChangeEventRepository 
# - SQLAlchemyScraperRunRepository
# - SQLAlchemyContentSnapshotRepository

# ======================== EXPORTS ========================

__all__ = [
    'SQLAlchemyBaseRepository',
    'SQLAlchemySanctionedEntityRepository'
    # Add other repository implementations
]