"""
Entity Repository Implementation

Concrete repository for sanctioned entities with domain-specific operations.
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, text, desc, asc
from datetime import datetime, timedelta

from src.infrastructure.database.repositories.base import BaseRepository
from src.infrastructure.database.models.sanctioned_entity import SanctionedEntity
from src.schemas.entity_schemas import EntitySearchFilters
from src.core.enums import SanctionsSource, SortOrder
from src.core.exceptions import DatabaseOperationError
from src.utils.logging import get_logger

class EntityRepository(BaseRepository[SanctionedEntity]):
    """
    Repository for sanctioned entities with domain-specific operations.
    
    Features:
    - Advanced search capabilities
    - Statistics and analytics
    - Performance optimizations
    - Business-specific queries
    """
    
    def __init__(self, db_session: Session):
        super().__init__(SanctionedEntity, db_session)
        self.logger = get_logger("repository.entity")
    
    # ======================== BUSINESS-SPECIFIC QUERIES ========================
    
    def get_by_uid(self, source: SanctionsSource, uid: str) -> Optional[SanctionedEntity]:
        """Get entity by source and UID."""
        try:
            entity = self.db_session.query(self.model).filter(
                and_(
                    self.model.source == source.value,
                    self.model.uid == uid
                )
            ).first()
            
            return entity
            
        except Exception as e:
            self.logger.error(f"Failed to get entity {source.value}:{uid}: {e}")
            raise DatabaseOperationError(f"Failed to get entity: {str(e)}")
    
    def get_by_source(
        self, 
        source: SanctionsSource, 
        limit: Optional[int] = None,
        active_only: bool = True
    ) -> List[SanctionedEntity]:
        """Get all entities from a specific source."""
        try:
            query = self.db_session.query(self.model).filter(
                self.model.source == source.value
            )
            
            if active_only:
                query = query.filter(self.model.is_active == True)
            
            if limit:
                query = query.limit(limit)
            
            entities = query.all()
            return entities
            
        except Exception as e:
            self.logger.error(f"Failed to get entities by source {source.value}: {e}")
            raise DatabaseOperationError(f"Failed to get entities by source: {str(e)}")
    
    def get_by_programs(self, programs: List[str]) -> List[SanctionedEntity]:
        """Get entities associated with specific programs."""
        try:
            program_filters = [
                self.model.programs.contains([program])
                for program in programs
            ]
            
            query = self.db_session.query(self.model).filter(
                or_(*program_filters)
            )
            
            entities = query.all()
            return entities
            
        except Exception as e:
            self.logger.error(f"Failed to get entities by programs: {e}")
            raise DatabaseOperationError(f"Failed to get entities by programs: {str(e)}")
    
    def get_recently_added(
        self, 
        days: int = 7, 
        source: Optional[SanctionsSource] = None
    ) -> List[SanctionedEntity]:
        """Get entities added in the last N days."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            query = self.db_session.query(self.model).filter(
                self.model.created_at >= cutoff_date
            )
            
            if source:
                query = query.filter(self.model.source == source.value)
            
            query = query.order_by(desc(self.model.created_at))
            
            entities = query.all()
            return entities
            
        except Exception as e:
            self.logger.error(f"Failed to get recently added entities: {e}")
            raise DatabaseOperationError(f"Failed to get recently added entities: {str(e)}")
    
    # ======================== ADVANCED SEARCH OPERATIONS ========================
    
    def search_with_filters(
        self,
        filters: EntitySearchFilters,
        skip: int = 0,
        limit: int = 50,
        order_by: str = "created_at",
        order_direction: SortOrder = SortOrder.DESC
    ) -> Tuple[List[SanctionedEntity], int]:
        """
        Advanced search with filters and pagination.
        
        Returns:
            Tuple of (entities, total_count)
        """
        try:
            # Build base query
            query = self.db_session.query(self.model)
            count_query = self.db_session.query(func.count(self.model.id))
            
            # Apply filters
            query, count_query = self._apply_search_filters(query, count_query, filters)
            
            # Get total count before pagination
            total_count = count_query.scalar()
            
            # Apply ordering
            if hasattr(self.model, order_by):
                order_field = getattr(self.model, order_by)
                if order_direction == SortOrder.DESC:
                    query = query.order_by(desc(order_field))
                else:
                    query = query.order_by(asc(order_field))
            
            # Apply pagination
            query = query.offset(skip).limit(limit)
            
            # Execute query
            entities = query.all()
            
            self.logger.debug(
                f"Search returned {len(entities)} entities (total: {total_count})"
            )
            
            return entities, total_count
            
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            raise DatabaseOperationError(f"Search failed: {str(e)}")
    
    def _apply_search_filters(
        self,
        query,
        count_query,
        filters: EntitySearchFilters
    ) -> Tuple[Any, Any]:
        """Apply search filters to queries."""
        
        # Name search (case-insensitive, partial match)
        if filters.name:
            name_filter = or_(
                self.model.name.ilike(f"%{filters.name}%"),
                func.array_to_string(self.model.aliases, ' ').ilike(f"%{filters.name}%")
            )
            query = query.filter(name_filter)
            count_query = count_query.filter(name_filter)
        
        # Entity type filter
        if filters.entity_type:
            type_filter = self.model.entity_type == filters.entity_type.value
            query = query.filter(type_filter)
            count_query = count_query.filter(type_filter)
        
        # Source filter
        if filters.source:
            source_filter = self.model.source == filters.source.value
            query = query.filter(source_filter)
            count_query = count_query.filter(source_filter)
        
        # Programs filter (any of the specified programs)
        if filters.programs:
            programs_filter = or_(
                *[self.model.programs.contains([program]) for program in filters.programs]
            )
            query = query.filter(programs_filter)
            count_query = count_query.filter(programs_filter)
        
        # Nationalities filter
        if filters.nationalities:
            nat_filter = or_(
                *[self.model.nationalities.contains([nat]) for nat in filters.nationalities]
            )
            query = query.filter(nat_filter)
            count_query = count_query.filter(nat_filter)
        
        # Active status filter
        if filters.is_active is not None:
            active_filter = self.model.is_active == filters.is_active
            query = query.filter(active_filter)
            count_query = count_query.filter(active_filter)
        
        return query, count_query
    
    # ======================== STATISTICS AND ANALYTICS ========================
    
    def get_statistics(self, source: Optional[SanctionsSource] = None) -> Dict[str, Any]:
        """Get comprehensive entity statistics."""
        try:
            base_query = self.db_session.query(self.model)
            
            if source:
                base_query = base_query.filter(self.model.source == source.value)
            
            # Basic counts
            total_entities = base_query.count()
            active_entities = base_query.filter(self.model.is_active == True).count()
            
            # Count by source
            by_source = dict(
                self.db_session.query(
                    self.model.source,
                    func.count(self.model.id)
                ).group_by(self.model.source).all()
            ) if not source else {source.value: total_entities}
            
            # Count by entity type
            by_type = dict(
                base_query.with_entities(
                    self.model.entity_type,
                    func.count(self.model.id)
                ).group_by(self.model.entity_type).all()
            )
            
            # Recent activity (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_additions = base_query.filter(
                self.model.created_at >= thirty_days_ago
            ).count()
            
            return {
                'total_entities': total_entities,
                'active_entities': active_entities,
                'inactive_entities': total_entities - active_entities,
                'by_source': by_source,
                'by_type': by_type,
                'recent_additions_30d': recent_additions,
                'statistics_generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate statistics: {e}")
            raise DatabaseOperationError(f"Failed to generate statistics: {str(e)}")
    
    # ======================== BULK OPERATIONS ========================
    
    def bulk_create(self, entities_data: List[Dict[str, Any]]) -> List[SanctionedEntity]:
        """Bulk create entities for performance."""
        try:
            db_entities = []
            
            for entity_data in entities_data:
                entity_data['created_at'] = datetime.utcnow()
                db_entity = self.model(**entity_data)
                db_entities.append(db_entity)
            
            self.db_session.add_all(db_entities)
            self.db_session.commit()
            
            # Refresh all entities to get IDs
            for db_entity in db_entities:
                self.db_session.refresh(db_entity)
            
            self.logger.info(f"Bulk created {len(db_entities)} entities")
            return db_entities
            
        except Exception as e:
            self.db_session.rollback()
            self.logger.error(f"Bulk create failed: {e}")
            raise DatabaseOperationError(f"Bulk create failed: {str(e)}")
    
    def bulk_update_last_seen(
        self,
        source: SanctionsSource,
        timestamp: Optional[datetime] = None
    ) -> int:
        """Bulk update last_seen timestamp for all entities from a source."""
        try:
            if not timestamp:
                timestamp = datetime.utcnow()
            
            updated_count = self.db_session.query(self.model).filter(
                self.model.source == source.value
            ).update({
                'last_seen': timestamp,
                'updated_at': timestamp
            })
            
            self.db_session.commit()
            
            self.logger.info(f"Bulk updated last_seen for {updated_count} entities")
            return updated_count
            
        except Exception as e:
            self.db_session.rollback()
            self.logger.error(f"Bulk update last_seen failed: {e}")
            raise DatabaseOperationError(f"Bulk update failed: {str(e)}")
    
    def mark_inactive_entities(
        self,
        source: SanctionsSource,
        exclude_uids: List[str],
        timestamp: Optional[datetime] = None
    ) -> int:
        """Mark entities as inactive if not in the exclude list."""
        try:
            if not timestamp:
                timestamp = datetime.utcnow()
            
            query = self.db_session.query(self.model).filter(
                and_(
                    self.model.source == source.value,
                    ~self.model.uid.in_(exclude_uids),
                    self.model.is_active == True
                )
            )
            
            inactive_count = query.update({
                'is_active': False,
                'updated_at': timestamp
            })
            
            self.db_session.commit()
            
            self.logger.info(
                f"Marked {inactive_count} entities as inactive for source {source.value}"
            )
            return inactive_count
            
        except Exception as e:
            self.db_session.rollback()
            self.logger.error(f"Mark inactive entities failed: {e}")
            raise DatabaseOperationError(f"Mark inactive failed: {str(e)}")

# ======================== FACTORY FUNCTION ========================

def create_entity_repository(db_session: Session) -> EntityRepository:
    """Factory function for creating entity repository."""
    return EntityRepository(db_session)