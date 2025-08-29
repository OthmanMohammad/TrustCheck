"""
Simple Sanctioned Entity Repository - Just Sync Methods That Work
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, text, String

from src.core.domain.entities import SanctionedEntityDomain, PersonalInfo, Address
from src.core.domain.repositories import SanctionedEntityRepository
from src.core.enums import DataSource, EntityType
from src.core.exceptions import DatabaseError, handle_exception
from src.core.logging_config import get_logger
from src.infrastructure.database.models import SanctionedEntity as SanctionedEntityORM

logger = get_logger(__name__)

class SQLAlchemySanctionedEntityRepository:
    """Simple sync-only repository that actually works."""
    
    def __init__(self, session: Session):
        self.session = session
        self.logger = get_logger(__name__)
    
    def _orm_to_domain(self, orm_entity: SanctionedEntityORM) -> SanctionedEntityDomain:
        """Convert ORM model to domain entity."""
        if not orm_entity:
            return None
            
        personal_info = None
        if orm_entity.entity_type == EntityType.PERSON.value:
            personal_info = PersonalInfo(
                first_name=None,
                last_name=orm_entity.name,
                date_of_birth=orm_entity.dates_of_birth[0] if orm_entity.dates_of_birth else None,
                place_of_birth=orm_entity.places_of_birth[0] if orm_entity.places_of_birth else None,
                nationality=orm_entity.nationalities[0] if orm_entity.nationalities else None
            )
        
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
    
    def find_all(
        self,
        active_only: bool = True,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Find all entities - SIMPLE SYNC VERSION."""
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
            
        except Exception as e:
            self.logger.error(f"Error in find_all: {e}")
            return []
    
    def get_by_uid(self, uid: str) -> Optional[SanctionedEntityDomain]:
        """Get entity by UID."""
        try:
            orm_entity = self.session.query(SanctionedEntityORM).filter(
                SanctionedEntityORM.uid == uid
            ).first()
            
            return self._orm_to_domain(orm_entity) if orm_entity else None
            
        except Exception as e:
            self.logger.error(f"Error in get_by_uid: {e}")
            return None
    
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
            
        except Exception as e:
            self.logger.error(f"Error in find_by_source: {e}")
            return []
    
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
            
        except Exception as e:
            self.logger.error(f"Error in find_by_entity_type: {e}")
            return []
    
    def search_by_name(
        self, 
        name: str, 
        fuzzy: bool = False,
        limit: int = 20,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Search entities by name."""
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
            
        except Exception as e:
            self.logger.error(f"Error in search_by_name: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get repository statistics."""
        try:
            total_active = self.session.query(SanctionedEntityORM).filter(
                SanctionedEntityORM.is_active == True
            ).count()
            
            total_inactive = self.session.query(SanctionedEntityORM).filter(
                SanctionedEntityORM.is_active == False
            ).count()
            
            source_stats = self.session.query(
                SanctionedEntityORM.source,
                func.count(SanctionedEntityORM.id).label('count')
            ).filter(
                SanctionedEntityORM.is_active == True
            ).group_by(SanctionedEntityORM.source).all()
            
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
            
        except Exception as e:
            self.logger.error(f"Error in get_statistics: {e}")
            return {
                'total_active': 0,
                'total_inactive': 0,
                'by_source': {},
                'by_type': {},
                'last_updated': datetime.utcnow().isoformat()
            }
    
    def health_check(self) -> bool:
        """Check repository health."""
        try:
            self.session.execute(text("SELECT 1"))
            return True
        except:
            return False