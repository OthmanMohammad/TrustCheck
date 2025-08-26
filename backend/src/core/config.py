"""
Enhanced Configuration Management
"""

from pydantic import Field, validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional, Set
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
    
    host: str = "localhost"
    port: int = 5432
    user: str = "trustcheck_user"
    password: SecretStr = SecretStr("trustcheck_secure_password_2024")
    name: str = "trustcheck"
    url: Optional[str] = None
    
    # Connection pool settings
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    
    @property
    def database_url(self) -> str:
        """Construct database URL from components."""
        if self.url:
            return self.url
        return f"postgresql://{self.user}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.name}"

class RedisSettings(BaseSettings):
    """Redis configuration section."""
    model_config = SettingsConfigDict(env_prefix="REDIS_")
    
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[SecretStr] = None
    url: Optional[str] = None
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL from components."""
        if self.url:
            return self.url
        
        auth_part = f":{self.password.get_secret_value()}@" if self.password else ""
        return f"redis://{auth_part}{self.host}:{self.port}/{self.db}"

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
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000"
    ]
    
    @validator('secret_key')
    def secret_key_length(cls, v):
        if len(v) < 32:
            raise ValueError('Secret key must be at least 32 characters')
        return v

class ScrapingSettings(BaseSettings):
    """Scraping configuration section."""
    model_config = SettingsConfigDict(env_prefix="SCRAPING_")
    
    # Intervals
    default_interval_hours: int = 6
    parallel_scrapers: int = 3
    
    # HTTP settings
    timeout: int = 60
    max_retries: int = 3
    backoff_factor: float = 0.3
    user_agent: str = "TrustCheck-Compliance-Platform/2.0 (+https://trustcheck.com)"
    
    # Content validation
    min_content_size: int = 1000
    max_content_size: int = 100_000_000  # 100MB

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
    """Main application settings."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Application metadata
    project_name: str = "TrustCheck"
    version: str = "2.0.0"
    description: str = "Real-time sanctions compliance platform with change detection"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = Field(default=False, description="Enable debug mode")
    
    # API configuration
    api_v1_prefix: str = "/api/v1"
    docs_enabled: bool = True
    
    # Configuration sections
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    scraping: ScrapingSettings = Field(default_factory=ScrapingSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    
    # External data sources
    data_sources: dict = Field(default={
        "ofac_sdn_url": "https://www.treasury.gov/ofac/downloads/sdn.xml",
        "un_consolidated_url": "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
        "eu_consolidated_url": "https://webgate.ec.europa.eu/europeaid/fsd/fsf/public/files/xmlFullSanctionsList/content",
        "uk_hmt_url": "https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/1178224/UK_Sanctions_List.xlsx"
    })
    
    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == Environment.DEVELOPMENT
    
    @validator('environment')
    def validate_environment_settings(cls, env, values):
        """Validate environment-specific settings."""
        debug = values.get('debug', False)
        
        if env == Environment.PRODUCTION and debug:
            raise ValueError("Debug mode cannot be enabled in production")
        
        return env
    
    def get_data_source_url(self, source: str) -> str:
        """Get URL for a specific data source."""
        return self.data_sources.get(f"{source}_url", "")

# Global settings instance
settings = Settings()

# Environment file template for documentation
ENV_TEMPLATE = """
# TrustCheck Environment Configuration Template
# Copy to .env and customize for your environment

# Application
ENVIRONMENT=development
DEBUG=true
PROJECT_NAME=TrustCheck

# Database
DB_HOST=localhost
DB_PORT=5432
DB_USER=trustcheck_user
DB_PASSWORD=your_secure_password_here
DB_NAME=trustcheck

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Security
SECURITY_SECRET_KEY=your_32_character_secret_key_here
SECURITY_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Scraping
SCRAPING_DEFAULT_INTERVAL_HOURS=6
SCRAPING_TIMEOUT=60
SCRAPING_MAX_RETRIES=3

# Observability
OBSERVABILITY_LOG_LEVEL=INFO
OBSERVABILITY_ENABLE_METRICS=true
OBSERVABILITY_SENTRY_DSN=your_sentry_dsn_here
"""

def create_env_file() -> None:
    """Create .env.example file."""
    env_file = Path(".env.example")
    if not env_file.exists():
        env_file.write_text(ENV_TEMPLATE.strip())
        print(f"Created {env_file}")

if __name__ == "__main__":
    create_env_file()
    print("Configuration loaded:")
    print(f"Environment: {settings.environment}")
    print(f"Debug: {settings.debug}")
    print(f"Database: {settings.database.host}:{settings.database.port}")
    print(f"Redis: {settings.redis.host}:{settings.redis.port}")