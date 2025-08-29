"""
Enhanced Configuration Management with Celery Support
"""

from pydantic import Field, validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, Set, Dict, Any
from pathlib import Path
import secrets
from enum import Enum

class Environment(str, Enum):
    """Application environment types."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"

class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class DatabaseSettings(BaseSettings):
    """Database configuration section."""
    model_config = SettingsConfigDict(env_prefix="DB_")
    
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    user: str = Field(default="trustcheck_user", description="Database user")
    password: SecretStr = Field(
        default=SecretStr("trustcheck_secure_password_2024"),
        description="Database password"
    )
    name: str = Field(default="trustcheck", description="Database name")
    url: Optional[str] = Field(None, description="Override database URL")
    
    # Connection pool settings
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max overflow connections")
    pool_timeout: int = Field(default=30, description="Pool timeout in seconds")
    pool_recycle: int = Field(default=3600, description="Recycle connections after seconds")
    pool_pre_ping: bool = Field(default=True, description="Test connections before using")
    
    @property
    def database_url(self) -> str:
        """Construct database URL from components."""
        if self.url:
            return self.url
        return f"postgresql://{self.user}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.name}"
    
    @property
    def async_database_url(self) -> str:
        """Construct async database URL."""
        base_url = self.database_url
        if base_url.startswith("postgresql://"):
            return base_url.replace("postgresql://", "postgresql+asyncpg://")
        return base_url

class RedisSettings(BaseSettings):
    """Redis configuration section."""
    model_config = SettingsConfigDict(env_prefix="REDIS_")
    
    host: str = Field(default="localhost", description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    db: int = Field(default=0, description="Redis database number")
    password: Optional[SecretStr] = Field(None, description="Redis password")
    url: Optional[str] = Field(None, description="Override Redis URL")
    
    # Connection pool settings
    max_connections: int = Field(default=50, description="Max connections in pool")
    socket_keepalive: bool = Field(default=True, description="Enable TCP keepalive")
    socket_connect_timeout: int = Field(default=5, description="Connection timeout")
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL from components."""
        if self.url:
            return self.url
        
        auth_part = f":{self.password.get_secret_value()}@" if self.password else ""
        return f"redis://{auth_part}{self.host}:{self.port}/{self.db}"

class CelerySettings(BaseSettings):
    """Celery configuration section."""
    model_config = SettingsConfigDict(env_prefix="CELERY_")
    
    # Broker settings
    broker_url: Optional[str] = Field(None, description="Celery broker URL")
    result_backend: Optional[str] = Field(None, description="Celery result backend")
    
    # Task settings
    task_serializer: str = Field(default="json", description="Task serialization format")
    result_serializer: str = Field(default="json", description="Result serialization format")
    accept_content: List[str] = Field(default=["json"], description="Accepted content types")
    timezone: str = Field(default="UTC", description="Celery timezone")
    enable_utc: bool = Field(default=True, description="Use UTC timestamps")
    
    # Worker settings
    worker_prefetch_multiplier: int = Field(default=4, description="Prefetch multiplier")
    worker_max_tasks_per_child: int = Field(default=1000, description="Max tasks per worker")
    worker_disable_rate_limits: bool = Field(default=False, description="Disable rate limits")
    worker_concurrency: Optional[int] = Field(None, description="Number of concurrent workers")
    
    # Task execution settings
    task_acks_late: bool = Field(default=True, description="Acknowledge tasks late")
    task_reject_on_worker_lost: bool = Field(default=True, description="Reject on worker lost")
    task_track_started: bool = Field(default=True, description="Track task start")
    task_time_limit: int = Field(default=900, description="Hard time limit (seconds)")
    task_soft_time_limit: int = Field(default=600, description="Soft time limit (seconds)")
    
    # Retry settings
    task_default_retry_delay: int = Field(default=60, description="Default retry delay")
    task_max_retries: int = Field(default=3, description="Maximum retry attempts")
    
    # Result backend settings
    result_expires: int = Field(default=3600, description="Result expiration (seconds)")
    result_compression: str = Field(default="gzip", description="Result compression")
    result_backend_transport_options: Dict[str, Any] = Field(
        default_factory=lambda: {
            'master_name': 'mymaster',
            'visibility_timeout': 3600,
            'fanout_prefix': True,
            'fanout_patterns': True
        }
    )
    
    # Beat scheduler settings
    beat_scheduler: str = Field(
        default="redbeat.RedBeatScheduler",
        description="Beat scheduler backend"
    )
    beat_max_loop_interval: int = Field(default=5, description="Max loop interval")
    beat_schedule_filename: str = Field(
        default="celerybeat-schedule",
        description="Beat schedule file"
    )
    
    # Queue routing
    task_routes: Dict[str, str] = Field(
        default_factory=lambda: {
            "src.tasks.scraping_tasks.*": "scraping",
            "src.tasks.notification_tasks.*": "notifications",
            "src.tasks.report_tasks.*": "reports",
            "src.tasks.maintenance_tasks.*": "maintenance"
        },
        description="Task routing rules"
    )
    
    # Queue configuration with priorities
    task_queue_max_priority: int = Field(default=10, description="Maximum queue priority")
    task_default_queue: str = Field(default="default", description="Default queue name")
    task_default_exchange: str = Field(default="default", description="Default exchange")
    task_default_routing_key: str = Field(default="default", description="Default routing key")
    
    @property
    def celery_broker_url(self) -> str:
        """Get broker URL with fallback to Redis settings."""
        if self.broker_url:
            return self.broker_url
        # Fallback to Redis URL from Redis settings
        from src.core.config import settings
        return f"{settings.redis.redis_url}/0"
    
    @property
    def celery_result_backend(self) -> str:
        """Get result backend URL with fallback to Redis settings."""
        if self.result_backend:
            return self.result_backend
        # Fallback to Redis URL from Redis settings
        from src.core.config import settings
        return f"{settings.redis.redis_url}/1"
    
    def get_celery_config(self) -> Dict[str, Any]:
        """Get complete Celery configuration dictionary."""
        return {
            # Broker settings
            'broker_url': self.celery_broker_url,
            'result_backend': self.celery_result_backend,
            'broker_connection_retry_on_startup': True,
            'broker_connection_retry': True,
            'broker_connection_max_retries': 10,
            
            # Serialization
            'task_serializer': self.task_serializer,
            'result_serializer': self.result_serializer,
            'accept_content': self.accept_content,
            
            # Timezone
            'timezone': self.timezone,
            'enable_utc': self.enable_utc,
            
            # Worker settings
            'worker_prefetch_multiplier': self.worker_prefetch_multiplier,
            'worker_max_tasks_per_child': self.worker_max_tasks_per_child,
            'worker_disable_rate_limits': self.worker_disable_rate_limits,
            
            # Task execution
            'task_acks_late': self.task_acks_late,
            'task_reject_on_worker_lost': self.task_reject_on_worker_lost,
            'task_track_started': self.task_track_started,
            'task_time_limit': self.task_time_limit,
            'task_soft_time_limit': self.task_soft_time_limit,
            
            # Retry settings
            'task_default_retry_delay': self.task_default_retry_delay,
            'task_max_retries': self.task_max_retries,
            
            # Result backend
            'result_expires': self.result_expires,
            'result_compression': self.result_compression,
            'result_backend_transport_options': self.result_backend_transport_options,
            
            # Beat scheduler
            'beat_scheduler': self.beat_scheduler,
            'beat_max_loop_interval': self.beat_max_loop_interval,
            'beat_schedule_filename': self.beat_schedule_filename,
            
            # Routing
            'task_routes': self.task_routes,
            'task_queue_max_priority': self.task_queue_max_priority,
            'task_default_queue': self.task_default_queue,
            'task_default_exchange': self.task_default_exchange,
            'task_default_routing_key': self.task_default_routing_key,
        }

class SecuritySettings(BaseSettings):
    """Security configuration section."""
    model_config = SettingsConfigDict(env_prefix="SECURITY_")
    
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # API Security
    api_key_header: str = "X-API-Key"
    rate_limit_per_minute: int = 100
    rate_limit_per_hour: int = 1000
    
    # CORS
    allowed_origins: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000"
        ]
    )
    
    # Flower authentication
    flower_basic_auth_username: str = Field(default="admin", description="Flower username")
    flower_basic_auth_password: SecretStr = Field(
        default=SecretStr("trustcheck2024"),
        description="Flower password"
    )
    
    @validator('secret_key')
    def secret_key_length(cls, v):
        if len(v) < 32:
            raise ValueError('Secret key must be at least 32 characters')
        return v

class ScrapingSettings(BaseSettings):
    """Scraping configuration section."""
    model_config = SettingsConfigDict(env_prefix="SCRAPING_")
    
    # Intervals (in hours)
    ofac_interval_hours: int = Field(default=6, description="OFAC scraping interval")
    un_interval_hours: int = Field(default=24, description="UN scraping interval")
    eu_interval_hours: int = Field(default=24, description="EU scraping interval")
    uk_interval_hours: int = Field(default=24, description="UK scraping interval")
    
    # Performance settings
    parallel_scrapers: int = Field(default=3, description="Parallel scraper limit")
    timeout: int = Field(default=120, description="Scraping timeout (seconds)")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    backoff_factor: float = Field(default=0.3, description="Retry backoff factor")
    
    # User agent
    user_agent: str = Field(
        default="TrustCheck-Compliance-Platform/2.0 (+https://trustcheck.com)",
        description="HTTP User-Agent header"
    )
    
    # Content validation
    min_content_size: int = Field(default=1000, description="Minimum content size (bytes)")
    max_content_size: int = Field(default=100_000_000, description="Maximum content size (bytes)")

class ObservabilitySettings(BaseSettings):
    """Monitoring and observability configuration."""
    model_config = SettingsConfigDict(env_prefix="OBSERVABILITY_")
    
    # Logging
    log_level: LogLevel = LogLevel.INFO
    log_format: str = "json"  # json or text
    enable_request_logging: bool = True
    
    # Metrics
    enable_metrics: bool = True
    metrics_port: int = 9090
    
    # Tracing
    enable_tracing: bool = False
    jaeger_endpoint: Optional[str] = None
    
    # External monitoring
    sentry_dsn: Optional[str] = None
    new_relic_license_key: Optional[str] = None

class Settings(BaseSettings):
    """Main application settings with all configurations."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application metadata
    project_name: str = Field(default="TrustCheck", description="Project name")
    version: str = Field(default="2.0.0", description="Application version")
    description: str = Field(
        default="Real-time sanctions compliance platform with change detection",
        description="Application description"
    )
    environment: Environment = Field(default=Environment.DEVELOPMENT, description="Environment")
    debug: bool = Field(default=False, description="Enable debug mode")
    
    # API configuration
    api_v1_prefix: str = Field(default="/api/v1", description="API v1 prefix")
    api_v2_prefix: str = Field(default="/api/v2", description="API v2 prefix")
    docs_enabled: bool = Field(default=True, description="Enable API documentation")
    
    # Configuration sections
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    scraping: ScrapingSettings = Field(default_factory=ScrapingSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    
    # External data sources
    data_sources: Dict[str, str] = Field(
        default={
            "ofac_sdn_url": "https://www.treasury.gov/ofac/downloads/sdn.xml",
            "un_consolidated_url": "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
            "eu_consolidated_url": "https://webgate.ec.europa.eu/europeaid/fsd/fsf/public/files/xmlFullSanctionsList/content",
            "uk_hmt_url": "https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/1178224/UK_Sanctions_List.xlsx"
        },
        description="External data source URLs"
    )
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing."""
        return self.environment == Environment.TESTING
    
    @validator('environment')
    def validate_environment_settings(cls, env, values):
        """Validate environment-specific settings."""
        debug = values.get('debug', False)
        
        if env == Environment.PRODUCTION and debug:
            raise ValueError("Debug mode cannot be enabled in production")
        
        return env
    
    def get_data_source_url(self, source: str) -> str:
        """Get URL for a specific data source."""
        return self.data_sources.get(f"{source.lower()}_url", "")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary (for debugging)."""
        return {
            "project_name": self.project_name,
            "version": self.version,
            "environment": self.environment.value,
            "debug": self.debug,
            "database": {
                "host": self.database.host,
                "port": self.database.port,
                "name": self.database.name
            },
            "redis": {
                "host": self.redis.host,
                "port": self.redis.port,
                "db": self.redis.db
            },
            "celery": {
                "broker": self.celery.celery_broker_url,
                "backend": self.celery.celery_result_backend
            }
        }

# Global settings instance
settings = Settings()

# Environment file template for documentation
ENV_TEMPLATE = """
# TrustCheck Environment Configuration
# Copy to .env and customize for your environment

# ==================== APPLICATION ====================
ENVIRONMENT=development
DEBUG=true
PROJECT_NAME=TrustCheck
VERSION=2.0.0

# ==================== DATABASE ====================
DB_HOST=localhost
DB_PORT=5432
DB_USER=trustcheck_user
DB_PASSWORD=trustcheck_secure_password_2024
DB_NAME=trustcheck
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# ==================== REDIS ====================
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
# REDIS_PASSWORD=your_redis_password_if_needed
REDIS_MAX_CONNECTIONS=50

# ==================== CELERY ====================
# Celery will use Redis settings by default
# Override if using different broker/backend
# CELERY_BROKER_URL=redis://localhost:6379/0
# CELERY_RESULT_BACKEND=redis://localhost:6379/1
CELERY_TASK_TIME_LIMIT=900
CELERY_TASK_SOFT_TIME_LIMIT=600
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000

# ==================== SECURITY ====================
SECURITY_SECRET_KEY=your_32_character_secret_key_here_change_this
SECURITY_ACCESS_TOKEN_EXPIRE_MINUTES=30
SECURITY_FLOWER_BASIC_AUTH_USERNAME=admin
SECURITY_FLOWER_BASIC_AUTH_PASSWORD=trustcheck2024

# ==================== SCRAPING ====================
SCRAPING_OFAC_INTERVAL_HOURS=6
SCRAPING_UN_INTERVAL_HOURS=24
SCRAPING_EU_INTERVAL_HOURS=24
SCRAPING_UK_INTERVAL_HOURS=24
SCRAPING_TIMEOUT=120
SCRAPING_MAX_RETRIES=3

# ==================== OBSERVABILITY ====================
OBSERVABILITY_LOG_LEVEL=INFO
OBSERVABILITY_LOG_FORMAT=json
OBSERVABILITY_ENABLE_METRICS=true
OBSERVABILITY_METRICS_PORT=9090
# OBSERVABILITY_SENTRY_DSN=your_sentry_dsn_here

# ==================== AWS (for production) ====================
# AWS_REGION=us-east-1
# AWS_ACCESS_KEY_ID=your_access_key
# AWS_SECRET_ACCESS_KEY=your_secret_key
"""

def create_env_file() -> None:
    """Create .env.example file."""
    env_file = Path(".env.example")
    if not env_file.exists():
        env_file.write_text(ENV_TEMPLATE.strip())
        print(f"Created {env_file}")

if __name__ == "__main__":
    create_env_file()
    print("\n" + "="*50)
    print("Configuration loaded successfully!")
    print("="*50)
    print(f"Environment: {settings.environment.value}")
    print(f"Debug: {settings.debug}")
    print(f"Database: {settings.database.host}:{settings.database.port}/{settings.database.name}")
    print(f"Redis: {settings.redis.host}:{settings.redis.port}")
    print(f"Celery Broker: {settings.celery.celery_broker_url}")
    print(f"Celery Backend: {settings.celery.celery_result_backend}")
    print("="*50)