"""
Redis Cache Service
"""

import json
import pickle
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
import redis
from redis.connection import ConnectionPool
import logging

from src.core.config.settings import settings
from src.core.exceptions import ExternalServiceError
from src.utils.logging import get_logger


# ======================== CACHE SERVICE ========================

class CacheService:
    """
    Redis cache service with comprehensive error handling.
    
    Features:
    - Connection pooling
    - Automatic serialization/deserialization
    - Graceful fallback when Redis is unavailable
    - Cache key namespacing
    - Performance metrics
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        self.logger = get_logger("cache.redis")
        self.redis_url = redis_url or settings.redis_url
        self.namespace = f"{settings.PROJECT_NAME.lower()}:"
        
        # Connection pool for performance
        self.pool = None
        self.redis_client = None
        self.is_available = False
        
        # Performance tracking
        self.hit_count = 0
        self.miss_count = 0
        self.error_count = 0
        
        # Initialize connection
        self._initialize_connection()
    
    def _initialize_connection(self) -> None:
        """Initialize Redis connection with error handling."""
        try:
            # Create connection pool
            self.pool = ConnectionPool.from_url(
                self.redis_url,
                max_connections=20,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Create Redis client
            self.redis_client = redis.Redis(
                connection_pool=self.pool,
                decode_responses=False  # We'll handle encoding ourselves
            )
            
            # Test connection
            self.redis_client.ping()
            self.is_available = True
            
            self.logger.info("✅ Redis cache service initialized successfully")
            
        except Exception as e:
            self.is_available = False
            self.logger.warning(f"⚠️ Redis cache unavailable: {e}")
            self.logger.info("Application will continue without caching")
    
    def _get_key(self, key: str) -> str:
        """Generate namespaced cache key."""
        return f"{self.namespace}{key}"
    
    def _serialize_value(self, value: Any) -> bytes:
        """Serialize value for Redis storage."""
        try:
            # Handle different data types efficiently
            if isinstance(value, (str, int, float, bool)):
                return json.dumps(value).encode('utf-8')
            elif isinstance(value, (dict, list)):
                return json.dumps(value).encode('utf-8')
            else:
                # Use pickle for complex objects
                return pickle.dumps(value)
        except Exception as e:
            self.logger.warning(f"Serialization failed for {type(value)}: {e}")
            return pickle.dumps(value)
    
    def _deserialize_value(self, data: bytes) -> Any:
        """Deserialize value from Redis storage."""
        try:
            # Try JSON first (most common)
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            try:
                # Fall back to pickle
                return pickle.loads(data)
            except Exception as e:
                self.logger.error(f"Deserialization failed: {e}")
                return None
    
    # ======================== BASIC CACHE OPERATIONS ========================
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/error
        """
        if not self.is_available:
            self.miss_count += 1
            return None
        
        try:
            cache_key = self._get_key(key)
            data = self.redis_client.get(cache_key)
            
            if data is None:
                self.miss_count += 1
                self.logger.debug(f"Cache MISS: {key}")
                return None
            
            value = self._deserialize_value(data)
            self.hit_count += 1
            self.logger.debug(f"Cache HIT: {key}")
            return value
            
        except Exception as e:
            self.error_count += 1
            self.logger.warning(f"Cache GET error for key '{key}': {e}")
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available:
            return False
        
        try:
            cache_key = self._get_key(key)
            serialized_value = self._serialize_value(value)
            
            if ttl:
                result = self.redis_client.setex(cache_key, ttl, serialized_value)
            else:
                result = self.redis_client.set(cache_key, serialized_value)
            
            if result:
                self.logger.debug(f"Cache SET: {key} (TTL: {ttl})")
                return True
            else:
                self.logger.warning(f"Cache SET failed for key: {key}")
                return False
                
        except Exception as e:
            self.error_count += 1
            self.logger.warning(f"Cache SET error for key '{key}': {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available:
            return False
        
        try:
            cache_key = self._get_key(key)
            deleted_count = self.redis_client.delete(cache_key)
            
            if deleted_count > 0:
                self.logger.debug(f"Cache DELETE: {key}")
                return True
            else:
                self.logger.debug(f"Cache DELETE: {key} (key not found)")
                return False
                
        except Exception as e:
            self.error_count += 1
            self.logger.warning(f"Cache DELETE error for key '{key}': {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.is_available:
            return False
        
        try:
            cache_key = self._get_key(key)
            return bool(self.redis_client.exists(cache_key))
        except Exception as e:
            self.error_count += 1
            self.logger.warning(f"Cache EXISTS error for key '{key}': {e}")
            return False
    
    # ======================== ADVANCED CACHE OPERATIONS ========================
    
    def get_multi(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dictionary of key-value pairs (only existing keys)
        """
        if not self.is_available or not keys:
            return {}
        
        try:
            cache_keys = [self._get_key(key) for key in keys]
            values = self.redis_client.mget(cache_keys)
            
            result = {}
            for i, (original_key, data) in enumerate(zip(keys, values)):
                if data is not None:
                    try:
                        result[original_key] = self._deserialize_value(data)
                        self.hit_count += 1
                    except Exception:
                        self.miss_count += 1
                else:
                    self.miss_count += 1
            
            self.logger.debug(f"Cache MGET: {len(result)}/{len(keys)} hits")
            return result
            
        except Exception as e:
            self.error_count += 1
            self.logger.warning(f"Cache MGET error: {e}")
            return {}
    
    def set_multi(
        self,
        mapping: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> int:
        """
        Set multiple values in cache.
        
        Args:
            mapping: Dictionary of key-value pairs
            ttl: Time to live in seconds
            
        Returns:
            Number of successfully set keys
        """
        if not self.is_available or not mapping:
            return 0
        
        try:
            pipeline = self.redis_client.pipeline()
            
            for key, value in mapping.items():
                cache_key = self._get_key(key)
                serialized_value = self._serialize_value(value)
                
                if ttl:
                    pipeline.setex(cache_key, ttl, serialized_value)
                else:
                    pipeline.set(cache_key, serialized_value)
            
            results = pipeline.execute()
            successful = sum(1 for result in results if result)
            
            self.logger.debug(f"Cache MSET: {successful}/{len(mapping)} successful")
            return successful
            
        except Exception as e:
            self.error_count += 1
            self.logger.warning(f"Cache MSET error: {e}")
            return 0
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Delete keys matching a pattern.
        
        Args:
            pattern: Redis key pattern (e.g., "user:*")
            
        Returns:
            Number of deleted keys
        """
        if not self.is_available:
            return 0
        
        try:
            cache_pattern = self._get_key(pattern)
            keys = self.redis_client.keys(cache_pattern)
            
            if not keys:
                return 0
            
            deleted_count = self.redis_client.delete(*keys)
            self.logger.info(f"Cache DELETE pattern '{pattern}': {deleted_count} keys deleted")
            return deleted_count
            
        except Exception as e:
            self.error_count += 1
            self.logger.warning(f"Cache DELETE pattern error for '{pattern}': {e}")
            return 0
    
    # ======================== HASH OPERATIONS ========================
    
    def hget(self, name: str, key: str) -> Optional[Any]:
        """Get field value from hash."""
        if not self.is_available:
            return None
        
        try:
            cache_name = self._get_key(name)
            data = self.redis_client.hget(cache_name, key)
            
            if data is None:
                return None
            
            return self._deserialize_value(data)
            
        except Exception as e:
            self.error_count += 1
            self.logger.warning(f"Cache HGET error for '{name}.{key}': {e}")
            return None
    
    def hset(self, name: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set field value in hash."""
        if not self.is_available:
            return False
        
        try:
            cache_name = self._get_key(name)
            serialized_value = self._serialize_value(value)
            
            pipeline = self.redis_client.pipeline()
            pipeline.hset(cache_name, key, serialized_value)
            
            if ttl:
                pipeline.expire(cache_name, ttl)
            
            results = pipeline.execute()
            return bool(results[0])
            
        except Exception as e:
            self.error_count += 1
            self.logger.warning(f"Cache HSET error for '{name}.{key}': {e}")
            return False
    
    def hgetall(self, name: str) -> Dict[str, Any]:
        """Get all field-value pairs from hash."""
        if not self.is_available:
            return {}
        
        try:
            cache_name = self._get_key(name)
            data = self.redis_client.hgetall(cache_name)
            
            result = {}
            for field, value in data.items():
                try:
                    result[field.decode('utf-8')] = self._deserialize_value(value)
                except Exception:
                    continue
            
            return result
            
        except Exception as e:
            self.error_count += 1
            self.logger.warning(f"Cache HGETALL error for '{name}': {e}")
            return {}
    
    # ======================== LIST OPERATIONS ========================
    
    def lpush(self, key: str, *values: Any) -> int:
        """Push values to the left of list."""
        if not self.is_available:
            return 0
        
        try:
            cache_key = self._get_key(key)
            serialized_values = [self._serialize_value(v) for v in values]
            return self.redis_client.lpush(cache_key, *serialized_values)
            
        except Exception as e:
            self.error_count += 1
            self.logger.warning(f"Cache LPUSH error for key '{key}': {e}")
            return 0
    
    def rpop(self, key: str) -> Optional[Any]:
        """Pop value from the right of list."""
        if not self.is_available:
            return None
        
        try:
            cache_key = self._get_key(key)
            data = self.redis_client.rpop(cache_key)
            
            if data is None:
                return None
            
            return self._deserialize_value(data)
            
        except Exception as e:
            self.error_count += 1
            self.logger.warning(f"Cache RPOP error for key '{key}': {e}")
            return None
    
    def lrange(self, key: str, start: int = 0, end: int = -1) -> List[Any]:
        """Get range of values from list."""
        if not self.is_available:
            return []
        
        try:
            cache_key = self._get_key(key)
            data_list = self.redis_client.lrange(cache_key, start, end)
            
            result = []
            for data in data_list:
                try:
                    result.append(self._deserialize_value(data))
                except Exception:
                    continue
            
            return result
            
        except Exception as e:
            self.error_count += 1
            self.logger.warning(f"Cache LRANGE error for key '{key}': {e}")
            return []
    
    # ======================== SPECIALIZED CACHING PATTERNS ========================
    
    def cache_with_expiry(
        self,
        key: str,
        fetch_function,
        ttl: int = 3600,
        force_refresh: bool = False
    ) -> Any:
        """
        Cache-aside pattern with automatic refresh.
        
        Args:
            key: Cache key
            fetch_function: Function to fetch data if not cached
            ttl: Time to live in seconds
            force_refresh: Force refresh even if cached
            
        Returns:
            Cached or fetched data
        """
        if not force_refresh:
            cached_value = self.get(key)
            if cached_value is not None:
                return cached_value
        
        try:
            # Fetch fresh data
            fresh_data = fetch_function()
            
            # Cache the result
            self.set(key, fresh_data, ttl)
            
            return fresh_data
            
        except Exception as e:
            self.logger.error(f"Cache-aside fetch function failed for key '{key}': {e}")
            
            # Return stale data if available
            if not force_refresh:
                stale_data = self.get(key)
                if stale_data is not None:
                    self.logger.warning(f"Returning stale data for key '{key}'")
                    return stale_data
            
            raise
    
    def cached_result(self, ttl: int = 3600):
        """
        Decorator for caching function results.
        
        Args:
            ttl: Time to live in seconds
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Generate cache key from function name and arguments
                import hashlib
                key_data = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
                cache_key = f"func:{hashlib.md5(key_data.encode()).hexdigest()}"
                
                # Try to get from cache
                cached_result = self.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Execute function and cache result
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl)
                
                return result
            
            return wrapper
        return decorator
    
    # ======================== MONITORING AND HEALTH ========================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            'is_available': self.is_available,
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'error_count': self.error_count,
            'total_requests': total_requests,
            'hit_rate_percent': round(hit_rate, 2),
            'namespace': self.namespace
        }
        
        if self.is_available:
            try:
                info = self.redis_client.info()
                stats.update({
                    'redis_version': info.get('redis_version'),
                    'connected_clients': info.get('connected_clients'),
                    'used_memory_human': info.get('used_memory_human'),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0)
                })
            except Exception as e:
                self.logger.warning(f"Failed to get Redis info: {e}")
        
        return stats
    
    def health_check(self) -> Dict[str, Any]:
        """Check cache service health."""
        if not self.is_available:
            return {
                'status': 'unhealthy',
                'message': 'Redis connection not available',
                'timestamp': datetime.utcnow().isoformat()
            }
        
        try:
            # Test basic operations
            test_key = f"health_check_{datetime.utcnow().timestamp()}"
            test_value = "health_check_value"
            
            # Test SET
            set_result = self.set(test_key, test_value, 10)
            if not set_result:
                raise Exception("SET operation failed")
            
            # Test GET
            get_result = self.get(test_key)
            if get_result != test_value:
                raise Exception("GET operation failed")
            
            # Test DELETE
            delete_result = self.delete(test_key)
            if not delete_result:
                raise Exception("DELETE operation failed")
            
            return {
                'status': 'healthy',
                'message': 'All cache operations successful',
                'timestamp': datetime.utcnow().isoformat(),
                'stats': self.get_stats()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Health check failed: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def clear_all(self) -> bool:
        """Clear all cache entries (use with caution)."""
        if not self.is_available:
            return False
        
        try:
            # Only clear keys with our namespace
            pattern = f"{self.namespace}*"
            deleted_count = self.delete_pattern("*")
            
            self.logger.warning(f"CLEARED ALL CACHE: {deleted_count} keys deleted")
            return True
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Cache clear all failed: {e}")
            return False


# ======================== CACHE DECORATORS ========================

def cached(ttl: int = 3600, key_prefix: str = ""):
    """
    Decorator for caching function results.
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Optional prefix for cache keys
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get cache service (you'd inject this properly in your app)
            cache_service = CacheService()
            
            # Generate cache key
            import hashlib
            key_data = f"{key_prefix}:{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cache_key = f"cached_func:{hashlib.md5(key_data.encode()).hexdigest()}"
            
            # Try cache first
            cached_result = cache_service.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_service.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


# ======================== FACTORY FUNCTION ========================

def create_cache_service(redis_url: Optional[str] = None) -> CacheService:
    """Factory function for creating cache service."""
    return CacheService(redis_url)