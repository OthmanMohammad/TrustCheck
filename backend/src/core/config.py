"""
Centralized configuration using Pydantic Settings with environment variable support.
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
import secrets

class Settings(BaseSettings):
    """Application settings."""
    
    # Application Metadata
    PROJECT_NAME: str = "TrustCheck"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Real-time sanctions compliance platform"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database Configuration - PostgreSQL
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "trustcheck_user"
    DB_PASSWORD: str = "trustcheck_secure_password_2024"
    DB_NAME: str = "trustcheck"
    DATABASE_URL: Optional[str] = None
    
    @property
    def database_url(self) -> str:
        """Construct database URL from components."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: Optional[str] = None
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL from components."""
        if self.REDIS_URL:
            return self.REDIS_URL
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # API Configuration
    API_V1_STR: str = "/api/v1"
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000"
    ]
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Celery Configuration
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
    @property
    def celery_broker_url(self) -> str:
        """Get Celery broker URL."""
        return self.CELERY_BROKER_URL or self.redis_url
    
    @property
    def celery_result_backend(self) -> str:
        """Get Celery result backend URL."""
        return self.CELERY_RESULT_BACKEND or self.redis_url
    
    # External Data Sources
    OFAC_SDN_URL: str = "https://www.treasury.gov/ofac/downloads/sdn.xml"
    UN_CONSOLIDATED_URL: str = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
    EU_CONSOLIDATED_URL: str = "https://webgate.ec.europa.eu/europeaid/fsd/fsf/public/files/xmlFullSanctionsList/content"
    UK_HMT_URL: str = "https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/1178224/UK_Sanctions_List.xlsx"
    
    # HTTP Client Configuration
    HTTP_TIMEOUT: int = 60
    MAX_RETRIES: int = 3
    BACKOFF_FACTOR: float = 0.3
    
    # File Storage
    S3_BUCKET_NAME: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_DEFAULT_REGION: str = "us-east-1"
    
    # Email Configuration
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_TLS: bool = True
    
    # Monitoring & Logging
    SENTRY_DSN: Optional[str] = None
    NEW_RELIC_LICENSE_KEY: Optional[str] = None
    
    # Database Connection Pool
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    
    # Scraping Configuration
    SCRAPING_INTERVAL_HOURS: int = 6
    PARALLEL_SCRAPERS: int = 3
    SCRAPER_USER_AGENT: str = "TrustCheck-Compliance-Platform/1.0 (+https://trustcheck.com)"
    
    # Cache Configuration
    CACHE_TTL_SECONDS: int = 3600
    SEARCH_CACHE_TTL_SECONDS: int = 300
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

# Global settings instance
settings = Settings()