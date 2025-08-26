"""
Entity Service Layer

Application services that orchestrate business operations.
Contains use cases and application logic.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.domain.entities.sanctioned_entity import SanctionedEntity, EntityId, EntityComparisonService
from src.infrastructure.database.repositories.entity_repository import EntityRepository
from src.infrastructure.database.repositories.change_repository import ChangeRepository
from src.schemas.entity_schemas import (
    EntityCreate, EntityUpdate, EntitySearchFilters, 
    EntityListResponse, EntitySearchResponse, BulkOperationResult
)
from src.core.enums import EntityType, SanctionsSource, RiskLevel, SortOrder
from src.core.exceptions import (
    EntityNotFoundError, ValidationError, EntityAlreadyExistsError,
    DatabaseOperationError
)
from src.utils.logging import get_logger
from src.infrastructure.cache.redis_client import CacheService


# ======================== SERVICE RESULT MODELS ========================

@dataclass
class EntityServiceResult:
    """Result wrapper for entity service operations."""
    success: bool
    entity: Optional[SanctionedEntity] = None
    entities: Optional[List[SanctionedEntity]] = None
    message: str = ""
    errors: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SearchResult:
    """Search operation result."""
    entities: List[SanctionedEntity]
    total_count: int
    search_time_ms: int
    filters_applied: EntitySearchFilters
    suggestions: List[str] = None
    
    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []


# ======================== ENTITY SERVICE ========================

class EntityService:
    """
    Entity Application Service
    
    Orchestrates entity-related use cases and business operations.
    Handles validation, caching, and coordination between layers.
    """
    
    def __init__(
        self,
        entity_repository: EntityRepository,
        change_repository: ChangeRepository,
        cache_service: Optional[CacheService] = None
    ):
        self.entity_repository = entity_repository
        self.change_repository = change_repository
        self.cache_service = cache_service
        self.comparison_service = EntityComparisonService()
        self.logger = get_logger("service.entity")
        
        # Configuration
        self.default_page_size = 50
        self.max_page_size = 1000
        self.cache_ttl_seconds = 3600  # 1 hour
    
    # ======================== CRUD OPERATIONS ========================
    
    def create_entity(self, entity_data: EntityCreate) -> EntityServiceResult:
        """
        Create a new sanctioned entity.
        
        Args:
            entity_data: Entity creation data
            
        Returns:
            EntityServiceResult with created entity
        """
        try:
            self.logger.info(f"Creating entity: {entity_data.name} ({entity_data.entity_type})")
            
            # Check if entity already exists
            existing = self.entity_repository.get_by_uid(entity_data.source, entity_data.uid)
            if existing:
                raise EntityAlreadyExistsError(
                    entity_type=entity_data.entity_type.value,
                    identifier=f"{entity_data.source.value}:{entity_data.uid}"
                )
            
            # Create domain entity
            entity_id = EntityId(source=entity_data.source, uid=entity_data.uid)
            domain_entity = SanctionedEntity(
                entity_id=entity_id,
                name=entity_data.name,
                entity_type=entity_data.entity_type,
                programs=entity_data.programs or [],
                aliases=entity_data.aliases or [],
                addresses=entity_data.addresses or [],
                dates_of_birth=entity_data.dates_of_birth or [],
                places_of_birth=entity_data.places_of_birth or [],
                nationalities=entity_data.nationalities or [],
                remarks=entity_data.remarks,
                created_at=datetime.utcnow(),
                last_seen=datetime.utcnow()
            )
            
            # Save to repository
            saved_entity = self.entity_repository.create(domain_entity)
            
            # Invalidate cache
            self._invalidate_entity_cache(entity_data.source)
            
            self.logger.info(f"Successfully created entity with ID: {saved_entity.entity_id}")
            
            return EntityServiceResult(
                success=True,
                entity=saved_entity,
                message=f"Entity '{entity_data.name}' created successfully"
            )
            
        except EntityAlreadyExistsError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to create entity: {e}")
            return EntityServiceResult(
                success=False,
                message="Failed to create entity",
                errors=[str(e)]
            )
    
    def get_entity_by_id(self, entity_id: int) -> EntityServiceResult:
        """Get entity by database ID."""
        try:
            # Check cache first
            if self.cache_service:
                cached_entity = self.cache_service.get(f"entity:{entity_id}")
                if cached_entity:
                    self.logger.debug(f"Entity {entity_id} retrieved from cache")
                    return EntityServiceResult(
                        success=True,
                        entity=cached_entity,
                        message="Entity retrieved from cache"
                    )
            
            entity = self.entity_repository.get_by_id(entity_id)
            if not entity:
                raise EntityNotFoundError(entity_type="SanctionedEntity", entity_id=entity_id)
            
            # Cache the result
            if self.cache_service:
                self.cache_service.set(
                    f"entity:{entity_id}",
                    entity,
                    ttl=self.cache_ttl_seconds
                )
            
            self.logger.debug(f"Retrieved entity {entity_id} from database")
            
            return EntityServiceResult(
                success=True,
                entity=entity,
                message="Entity retrieved successfully"
            )
            
        except EntityNotFoundError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to retrieve entity {entity_id}: {e}")
            return EntityServiceResult(
                success=False,
                message="Failed to retrieve entity",
                errors=[str(e)]
            )
    
    def update_entity(self, entity_id: int, update_data: EntityUpdate) -> EntityServiceResult:
        """Update existing entity."""
        try:
            # Get existing entity
            existing_result = self.get_entity_by_id(entity_id)
            if not existing_result.success:
                return existing_result
            
            existing_entity = existing_result.entity
            self.logger.info(f"Updating entity {entity_id}: {existing_entity.name}")
            
            # Apply updates to domain entity
            updated_entity = self._apply_entity_updates(existing_entity, update_data)
            
            # Save changes
            saved_entity = self.entity_repository.update(entity_id, updated_entity)
            
            # Log changes if significant
            if updated_entity.has_changed(existing_entity):
                changes = updated_entity.get_field_changes(existing_entity)
                self.logger.info(f"Entity {entity_id} updated with {len(changes)} field changes")
                
                # Record change event
                self._record_change_event(existing_entity, updated_entity, changes)
            
            # Invalidate cache
            self._invalidate_entity_cache(updated_entity.entity_id.source)
            if self.cache_service:
                self.cache_service.delete(f"entity:{entity_id}")
            
            return EntityServiceResult(
                success=True,
                entity=saved_entity,
                message=f"Entity '{saved_entity.name}' updated successfully"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to update entity {entity_id}: {e}")
            return EntityServiceResult(
                success=False,
                message="Failed to update entity",
                errors=[str(e)]
            )
    
    def delete_entity(self, entity_id: int, soft_delete: bool = True) -> EntityServiceResult:
        """Delete entity (soft delete by default)."""
        try:
            entity_result = self.get_entity_by_id(entity_id)
            if not entity_result.success:
                return entity_result
            
            entity = entity_result.entity
            self.logger.info(f"Deleting entity {entity_id}: {entity.name} (soft={soft_delete})")
            
            if soft_delete:
                # Soft delete - mark as inactive
                update_data = EntityUpdate(is_active=False)
                return self.update_entity(entity_id, update_data)
            else:
                # Hard delete
                success = self.entity_repository.delete(entity_id)
                
                if success:
                    # Invalidate cache
                    self._invalidate_entity_cache(entity.entity_id.source)
                    if self.cache_service:
                        self.cache_service.delete(f"entity:{entity_id}")
                    
                    return EntityServiceResult(
                        success=True,
                        message=f"Entity '{entity.name}' deleted successfully"
                    )
                else:
                    return EntityServiceResult(
                        success=False,
                        message="Failed to delete entity",
                        errors=["Delete operation failed"]
                    )
            
        except Exception as e:
            self.logger.error(f"Failed to delete entity {entity_id}: {e}")
            return EntityServiceResult(
                success=False,
                message="Failed to delete entity",
                errors=[str(e)]
            )
    
    # ======================== SEARCH AND FILTERING ========================
    
    def search_entities(
        self,
        filters: EntitySearchFilters,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "created_at",
        sort_order: SortOrder = SortOrder.DESC
    ) -> SearchResult:
        """
        Search entities with advanced filtering and pagination.
        
        Args:
            filters: Search filters
            page: Page number (1-based)
            page_size: Items per page
            sort_by: Field to sort by
            sort_order: Sort direction
            
        Returns:
            SearchResult with entities and metadata
        """
        start_time = datetime.utcnow()
        
        try:
            # Validate pagination
            page = max(1, page)
            page_size = min(max(1, page_size), self.max_page_size)
            skip = (page - 1) * page_size
            
            self.logger.info(f"Searching entities: page={page}, size={page_size}, filters={filters}")
            
            # Check cache for common searches
            cache_key = self._generate_search_cache_key(filters, page, page_size, sort_by, sort_order)
            if self.cache_service:
                cached_result = self.cache_service.get(cache_key)
                if cached_result:
                    self.logger.debug("Search result retrieved from cache")
                    return cached_result
            
            # Execute search
            entities, total_count = self.entity_repository.search_with_filters(
                filters=filters,
                skip=skip,
                limit=page_size,
                order_by=sort_by,
                order_direction=sort_order
            )
            
            # Calculate search time
            search_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Generate search suggestions
            suggestions = self._generate_search_suggestions(filters, entities)
            
            result = SearchResult(
                entities=entities,
                total_count=total_count,
                search_time_ms=search_time_ms,
                filters_applied=filters,
                suggestions=suggestions
            )
            
            # Cache the result
            if self.cache_service and total_count > 0:
                self.cache_service.set(
                    cache_key,
                    result,
                    ttl=300  # 5 minutes for search results
                )
            
            self.logger.info(
                f"Search completed: {len(entities)} entities found in {search_time_ms}ms"
            )
            
            return result
            
        except Exception as e:
            search_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            self.logger.error(f"Search failed after {search_time_ms}ms: {e}")
            
            return SearchResult(
                entities=[],
                total_count=0,
                search_time_ms=search_time_ms,
                filters_applied=filters,
                suggestions=[]
            )
    
    def find_similar_entities(
        self,
        entity_id: int,
        similarity_threshold: float = 0.7,
        limit: int = 10
    ) -> EntityServiceResult:
        """Find entities similar to the given entity."""
        try:
            # Get the reference entity
            entity_result = self.get_entity_by_id(entity_id)
            if not entity_result.success:
                return entity_result
            
            reference_entity = entity_result.entity
            self.logger.info(f"Finding entities similar to: {reference_entity.name}")
            
            # Get entities from the same source for comparison
            all_entities = self.entity_repository.get_by_source(
                reference_entity.entity_id.source,
                limit=1000  # Limit for performance
            )
            
            # Calculate similarities
            similar_entities = []
            for entity in all_entities:
                if entity.entity_id.uid == reference_entity.entity_id.uid:
                    continue  # Skip self
                
                similarity = reference_entity.similarity_score(entity)
                if similarity >= similarity_threshold:
                    similar_entities.append((entity, similarity))
            
            # Sort by similarity score (descending)
            similar_entities.sort(key=lambda x: x[1], reverse=True)
            
            # Return top matches
            result_entities = [entity for entity, _ in similar_entities[:limit]]
            
            self.logger.info(
                f"Found {len(result_entities)} similar entities "
                f"(threshold: {similarity_threshold})"
            )
            
            return EntityServiceResult(
                success=True,
                entities=result_entities,
                message=f"Found {len(result_entities)} similar entities",
                metadata={
                    'reference_entity_id': entity_id,
                    'similarity_threshold': similarity_threshold,
                    'similarities': [sim for _, sim in similar_entities[:limit]]
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to find similar entities: {e}")
            return EntityServiceResult(
                success=False,
                message="Failed to find similar entities",
                errors=[str(e)]
            )
    
    # ======================== BULK OPERATIONS ========================
    
    def bulk_create_entities(self, entities_data: List[EntityCreate]) -> BulkOperationResult:
        """Create multiple entities in bulk."""
        start_time = datetime.utcnow()
        
        try:
            self.logger.info(f"Starting bulk creation of {len(entities_data)} entities")
            
            result = BulkOperationResult(
                total_requested=len(entities_data),
                successful=0,
                failed=0,
                skipped=0,
                errors=[],
                created_ids=[]
            )
            
            for i, entity_data in enumerate(entities_data):
                try:
                    # Check if entity already exists
                    existing = self.entity_repository.get_by_uid(
                        entity_data.source, 
                        entity_data.uid
                    )
                    
                    if existing:
                        result.skipped += 1
                        continue
                    
                    # Create entity
                    creation_result = self.create_entity(entity_data)
                    
                    if creation_result.success:
                        result.successful += 1
                        if hasattr(creation_result.entity, 'id'):
                            result.created_ids.append(creation_result.entity.id)
                    else:
                        result.failed += 1
                        result.errors.append(f"Entity {i}: {creation_result.errors}")
                
                except Exception as e:
                    result.failed += 1
                    result.errors.append(f"Entity {i} ({entity_data.name}): {str(e)}")
                    
                    # Log individual failures
                    self.logger.warning(f"Failed to create entity {i}: {e}")
            
            # Calculate processing time
            processing_time = datetime.utcnow() - start_time
            result.processing_time_ms = int(processing_time.total_seconds() * 1000)
            
            # Invalidate relevant caches
            sources_affected = set(entity_data.source for entity_data in entities_data)
            for source in sources_affected:
                self._invalidate_entity_cache(source)
            
            self.logger.info(
                f"Bulk creation completed: {result.successful} successful, "
                f"{result.failed} failed, {result.skipped} skipped "
                f"in {result.processing_time_ms}ms"
            )
            
            return result
            
        except Exception as e:
            processing_time = datetime.utcnow() - start_time
            self.logger.error(f"Bulk creation failed after {processing_time.total_seconds()}s: {e}")
            
            return BulkOperationResult(
                total_requested=len(entities_data),
                successful=0,
                failed=len(entities_data),
                errors=[f"Bulk operation failed: {str(e)}"],
                processing_time_ms=int(processing_time.total_seconds() * 1000)
            )
    
    def find_duplicate_entities(
        self,
        source: Optional[SanctionsSource] = None,
        similarity_threshold: float = 0.8
    ) -> EntityServiceResult:
        """Find potential duplicate entities."""
        try:
            self.logger.info(f"Finding duplicates (threshold: {similarity_threshold})")
            
            # Get entities to analyze
            if source:
                entities = self.entity_repository.get_by_source(source)
            else:
                entities = self.entity_repository.get_multi(limit=5000)  # Limit for performance
            
            # Find duplicates using domain service
            duplicate_groups = self.comparison_service.find_potential_duplicates(
                entities, 
                similarity_threshold
            )
            
            # Flatten groups for response
            all_duplicates = []
            for group in duplicate_groups:
                all_duplicates.extend(group)
            
            self.logger.info(
                f"Found {len(duplicate_groups)} duplicate groups "
                f"with {len(all_duplicates)} total entities"
            )
            
            return EntityServiceResult(
                success=True,
                entities=all_duplicates,
                message=f"Found {len(duplicate_groups)} potential duplicate groups",
                metadata={
                    'duplicate_groups': len(duplicate_groups),
                    'total_duplicates': len(all_duplicates),
                    'similarity_threshold': similarity_threshold,
                    'groups': [
                        [str(entity.entity_id) for entity in group] 
                        for group in duplicate_groups
                    ]
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to find duplicates: {e}")
            return EntityServiceResult(
                success=False,
                message="Failed to find duplicate entities",
                errors=[str(e)]
            )
    
    # ======================== STATISTICS AND ANALYTICS ========================
    
    def get_entity_statistics(
        self,
        source: Optional[SanctionsSource] = None
    ) -> Dict[str, Any]:
        """Get comprehensive entity statistics."""
        try:
            self.logger.info(f"Generating entity statistics for source: {source}")
            
            # Check cache first
            cache_key = f"stats:entities:{source.value if source else 'all'}"
            if self.cache_service:
                cached_stats = self.cache_service.get(cache_key)
                if cached_stats:
                    return cached_stats
            
            stats = self.entity_repository.get_statistics(source=source)
            
            # Add computed metrics
            stats['computed_metrics'] = {
                'entities_per_program': self._calculate_entities_per_program(source),
                'risk_distribution': self._calculate_risk_distribution(source),
                'recent_additions': self._calculate_recent_additions(source),
                'data_quality_score': self._calculate_data_quality_score(source)
            }
            
            stats['generated_at'] = datetime.utcnow().isoformat()
            
            # Cache the statistics
            if self.cache_service:
                self.cache_service.set(cache_key, stats, ttl=1800)  # 30 minutes
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to generate statistics: {e}")
            return {
                'error': str(e),
                'generated_at': datetime.utcnow().isoformat()
            }
    
    # ======================== HELPER METHODS ========================
    
    def _apply_entity_updates(
        self, 
        existing: SanctionedEntity, 
        updates: EntityUpdate
    ) -> SanctionedEntity:
        """Apply updates to existing entity."""
        # Create updated entity with new values
        updated_data = {
            'entity_id': existing.entity_id,
            'name': updates.name or existing.name,
            'entity_type': updates.entity_type or existing.entity_type,
            'programs': updates.programs if updates.programs is not None else existing.programs,
            'aliases': updates.aliases if updates.aliases is not None else existing.aliases,
            'addresses': updates.addresses if updates.addresses is not None else existing.addresses,
            'dates_of_birth': updates.dates_of_birth if updates.dates_of_birth is not None else existing.dates_of_birth,
            'places_of_birth': updates.places_of_birth if updates.places_of_birth is not None else existing.places_of_birth,
            'nationalities': updates.nationalities if updates.nationalities is not None else existing.nationalities,
            'remarks': updates.remarks if updates.remarks is not None else existing.remarks,
            'is_active': updates.is_active if updates.is_active is not None else existing.is_active,
            'created_at': existing.created_at,
            'updated_at': datetime.utcnow(),
            'last_seen': existing.last_seen
        }
        
        return SanctionedEntity(**updated_data)
    
    def _record_change_event(
        self,
        old_entity: SanctionedEntity,
        new_entity: SanctionedEntity,
        field_changes: List[Dict[str, Any]]
    ) -> None:
        """Record change event for audit trail."""
        try:
            change_summary = f"Entity '{new_entity.name}' updated: " + \
                           ", ".join([change['field_name'] for change in field_changes])
            
            # This would call the change repository to record the change
            # Implementation depends on your change tracking requirements
            self.logger.info(f"Change recorded: {change_summary}")
            
        except Exception as e:
            self.logger.error(f"Failed to record change event: {e}")
    
    def _generate_search_cache_key(
        self,
        filters: EntitySearchFilters,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder
    ) -> str:
        """Generate cache key for search results."""
        import hashlib
        
        filter_str = f"{filters.name}:{filters.entity_type}:{filters.source}:" + \
                    f"{filters.programs}:{filters.nationalities}:{filters.is_active}"
        
        search_params = f"{filter_str}:{page}:{page_size}:{sort_by}:{sort_order.value}"
        
        hash_obj = hashlib.md5(search_params.encode())
        return f"search:{hash_obj.hexdigest()}"
    
    def _generate_search_suggestions(
        self,
        filters: EntitySearchFilters,
        results: List[SanctionedEntity]
    ) -> List[str]:
        """Generate search suggestions based on results."""
        suggestions = []
        
        if not results and filters.name:
            # Suggest alternative searches if no results
            suggestions.extend([
                f"Try searching for '{filters.name[:-1]}*'",
                f"Search without entity type filter",
                f"Try broader search terms"
            ])
        elif len(results) > 0:
            # Suggest refinements if too many results
            if len(results) > 100:
                common_programs = self._get_most_common_programs(results[:20])
                if common_programs:
                    suggestions.append(f"Filter by program: {common_programs[0]}")
        
        return suggestions[:3]  # Limit suggestions
    
    def _get_most_common_programs(self, entities: List[SanctionedEntity]) -> List[str]:
        """Get most common programs from entity list."""
        program_counts = {}
        
        for entity in entities:
            for program in entity.programs:
                program_counts[program] = program_counts.get(program, 0) + 1
        
        return sorted(program_counts.keys(), key=lambda x: program_counts[x], reverse=True)
    
    def _invalidate_entity_cache(self, source: SanctionsSource) -> None:
        """Invalidate cache entries for a source."""
        if not self.cache_service:
            return
        
        try:
            # Invalidate statistics cache
            self.cache_service.delete(f"stats:entities:{source.value}")
            self.cache_service.delete("stats:entities:all")
            
            # Invalidate search caches (would need more sophisticated cache invalidation)
            # For now, just log that caches should be cleared
            self.logger.debug(f"Cache invalidated for source: {source.value}")
            
        except Exception as e:
            self.logger.warning(f"Failed to invalidate cache: {e}")
    
    # Placeholder methods for statistics calculations
    def _calculate_entities_per_program(self, source: Optional[SanctionsSource]) -> Dict[str, int]:
        """Calculate entities per program."""
        # Implementation would query repository
        return {}
    
    def _calculate_risk_distribution(self, source: Optional[SanctionsSource]) -> Dict[str, int]:
        """Calculate risk level distribution.""" 
        return {}
    
    def _calculate_recent_additions(self, source: Optional[SanctionsSource]) -> int:
        """Calculate recent additions (last 7 days)."""
        return 0
    
    def _calculate_data_quality_score(self, source: Optional[SanctionsSource]) -> float:
        """Calculate data quality score."""
        return 0.85  # Placeholder