"""
Sanctioned Entity Repository - Async Implementation
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, desc, String
from sqlalchemy.orm import selectinload

from src.core.domain.entities import SanctionedEntityDomain, PersonalInfo, Address
from src.core.enums import DataSource, EntityType
from src.core.logging_config import get_logger
from src.infrastructure.database.models import SanctionedEntity as SanctionedEntityORM

logger = get_logger(__name__)

class SQLAlchemySanctionedEntityRepository:
    """Async repository for sanctioned entities."""
    
    def __init__(self, session: AsyncSession):
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
    
    async def find_all(
        self,
        active_only: bool = True,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Find all entities."""
        try:
            stmt = select(SanctionedEntityORM)
            
            if active_only:
                stmt = stmt.where(SanctionedEntityORM.is_active == True)
            
            stmt = stmt.order_by(desc(SanctionedEntityORM.updated_at))
            stmt = stmt.offset(offset)
            
            if limit:
                stmt = stmt.limit(limit)
            
            result = await self.session.execute(stmt)
            orm_entities = result.scalars().all()
            return [self._orm_to_domain(orm_entity) for orm_entity in orm_entities]
            
        except Exception as e:
            self.logger.error(f"Error in find_all: {e}")
            return []
    
    async def get_by_uid(self, uid: str) -> Optional[SanctionedEntityDomain]:
        """Get entity by UID."""
        try:
            stmt = select(SanctionedEntityORM).where(SanctionedEntityORM.uid == uid)
            result = await self.session.execute(stmt)
            orm_entity = result.scalar_one_or_none()
            return self._orm_to_domain(orm_entity) if orm_entity else None
            
        except Exception as e:
            self.logger.error(f"Error in get_by_uid: {e}")
            return None
    
    async def find_by_source(
        self, 
        source: DataSource, 
        active_only: bool = True,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Find entities by source."""
        try:
            stmt = select(SanctionedEntityORM).where(
                SanctionedEntityORM.source == source.value
            )
            
            if active_only:
                stmt = stmt.where(SanctionedEntityORM.is_active == True)
            
            stmt = stmt.order_by(desc(SanctionedEntityORM.updated_at))
            stmt = stmt.offset(offset)
            
            if limit:
                stmt = stmt.limit(limit)
            
            result = await self.session.execute(stmt)
            orm_entities = result.scalars().all()
            return [self._orm_to_domain(orm_entity) for orm_entity in orm_entities]
            
        except Exception as e:
            self.logger.error(f"Error in find_by_source: {e}")
            return []
    
    async def find_by_entity_type(
        self, 
        entity_type: EntityType,
        limit: Optional[int] = None,
        offset: int = 0  
    ) -> List[SanctionedEntityDomain]:
        """Find entities by type."""
        try:
            stmt = select(SanctionedEntityORM).where(
                and_(
                    SanctionedEntityORM.entity_type == entity_type.value,
                    SanctionedEntityORM.is_active == True
                )
            )
            
            stmt = stmt.order_by(desc(SanctionedEntityORM.updated_at))
            stmt = stmt.offset(offset)
            
            if limit:
                stmt = stmt.limit(limit)
            
            result = await self.session.execute(stmt)
            orm_entities = result.scalars().all()
            return [self._orm_to_domain(orm_entity) for orm_entity in orm_entities]
            
        except Exception as e:
            self.logger.error(f"Error in find_by_entity_type: {e}")
            return []
    
    async def search_by_name(
        self, 
        name: str, 
        fuzzy: bool = False,
        limit: int = 20,
        offset: int = 0
    ) -> List[SanctionedEntityDomain]:
        """Search entities by name."""
        try:
            # For JSON fields, we need to cast to text for ILIKE
            stmt = select(SanctionedEntityORM).where(
                and_(
                    or_(
                        SanctionedEntityORM.name.ilike(f'%{name}%'),
                        # For aliases (JSON array), we need different approach
                        func.cast(SanctionedEntityORM.aliases, String).ilike(f'%{name}%')
                    ),
                    SanctionedEntityORM.is_active == True
                )
            )
            
            stmt = stmt.order_by(SanctionedEntityORM.name)
            stmt = stmt.offset(offset).limit(limit)
            
            result = await self.session.execute(stmt)
            orm_entities = result.scalars().all()
            return [self._orm_to_domain(orm_entity) for orm_entity in orm_entities]
            
        except Exception as e:
            self.logger.error(f"Error in search_by_name: {e}")
            return []
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get repository statistics."""
        try:
            # Total active
            active_stmt = select(func.count(SanctionedEntityORM.id)).where(
                SanctionedEntityORM.is_active == True
            )
            active_result = await self.session.execute(active_stmt)
            total_active = active_result.scalar() or 0
            
            # Total inactive
            inactive_stmt = select(func.count(SanctionedEntityORM.id)).where(
                SanctionedEntityORM.is_active == False
            )
            inactive_result = await self.session.execute(inactive_stmt)
            total_inactive = inactive_result.scalar() or 0
            
            # By source
            source_stmt = select(
                SanctionedEntityORM.source,
                func.count(SanctionedEntityORM.id).label('count')
            ).where(
                SanctionedEntityORM.is_active == True
            ).group_by(SanctionedEntityORM.source)
            
            source_result = await self.session.execute(source_stmt)
            source_stats = {row.source: row.count for row in source_result}
            
            # By type
            type_stmt = select(
                SanctionedEntityORM.entity_type,
                func.count(SanctionedEntityORM.id).label('count')
            ).where(
                SanctionedEntityORM.is_active == True
            ).group_by(SanctionedEntityORM.entity_type)
            
            type_result = await self.session.execute(type_stmt)
            type_stats = {row.entity_type: row.count for row in type_result}
            
            return {
                'total_active': total_active,
                'total_inactive': total_inactive,
                'by_source': source_stats,
                'by_type': type_stats,
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
    
    async def get_all_for_change_detection(self, source: DataSource) -> List[SanctionedEntityDomain]:
        """Get all entities for change detection."""
        return await self.find_by_source(source, active_only=True, limit=None)
    
    async def health_check(self) -> bool:
        """Check repository health."""
        try:
            stmt = select(func.count(SanctionedEntityORM.id)).limit(1)
            await self.session.execute(stmt)
            return True
        except:
            return False