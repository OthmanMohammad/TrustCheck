"""
TrustCheck Configuration Module.

Centralized configuration using Pydantic Settings for type-safe environment variables.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="TrustCheck", description="Application name")
    app_version: str = Field(default="4.0.0", description="Application version")
    environment: Literal["development", "staging", "production"] = Field(
        default="development", description="Deployment environment"
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )

    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")

    # Database - PostgreSQL is the default for enterprise use
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/trustcheck",
        description="Database connection URL (PostgreSQL recommended)",
    )

    # Database pool settings (PostgreSQL)
    db_pool_size: int = Field(default=10, description="Connection pool size")
    db_pool_max_overflow: int = Field(default=20, description="Max overflow connections")
    db_pool_timeout: int = Field(default=30, description="Pool connection timeout")
    db_echo: bool = Field(default=False, description="Echo SQL statements")

    # Scraping Configuration
    scraping_timeout: int = Field(
        default=120, description="HTTP request timeout in seconds"
    )
    scraping_max_retries: int = Field(
        default=3, description="Maximum retry attempts for failed requests"
    )
    scraping_user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        description="User agent for HTTP requests",
    )
    scraping_batch_size: int = Field(
        default=500, description="Batch size for database inserts during scraping"
    )

    # Scraping Intervals (in hours)
    ofac_interval_hours: int = Field(
        default=6, description="OFAC scraping interval in hours"
    )
    un_interval_hours: int = Field(
        default=24, description="UN scraping interval in hours"
    )
    eu_interval_hours: int = Field(
        default=24, description="EU scraping interval in hours"
    )
    uk_interval_hours: int = Field(
        default=24, description="UK scraping interval in hours"
    )

    # Screening Configuration
    default_match_threshold: float = Field(
        default=0.80, description="Default minimum score for name matches (0.0-1.0)"
    )
    max_screening_results: int = Field(
        default=100, description="Maximum results to return from screening"
    )
    batch_screening_limit: int = Field(
        default=10000, description="Maximum names in a batch screening request"
    )
    # Trigram similarity threshold for PostgreSQL pg_trgm
    trigram_similarity_threshold: float = Field(
        default=0.3, description="Minimum trigram similarity for candidate generation"
    )

    # Cache Configuration
    cache_ttl_seconds: int = Field(
        default=300, description="Cache TTL in seconds (5 minutes)"
    )
    cache_max_size: int = Field(
        default=10000, description="Maximum items in memory cache"
    )

    # Data Sources URLs
    ofac_sdn_url: str = Field(
        default="https://www.treasury.gov/ofac/downloads/sdn.xml",
        description="OFAC SDN list URL",
    )
    ofac_consolidated_url: str = Field(
        default="https://www.treasury.gov/ofac/downloads/consolidated/consolidated.xml",
        description="OFAC Consolidated list URL",
    )
    un_consolidated_url: str = Field(
        default="https://scsanctions.un.org/resources/xml/en/consolidated.xml",
        description="UN Consolidated sanctions list URL",
    )
    eu_sanctions_url: str = Field(
        default="https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw",
        description="EU sanctions list URL",
    )
    uk_sanctions_url: str = Field(
        default="https://assets.publishing.service.gov.uk/media/662119c877a30aa0c4757e96/UK_Sanctions_List.xml",
        description="UK sanctions list URL (static XML)",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL database."""
        return "postgresql" in self.database_url.lower()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite database (not recommended for production)."""
        return "sqlite" in self.database_url.lower()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def data_dir(self) -> Path:
        """Get the data directory path."""
        path = Path("data")
        path.mkdir(exist_ok=True)
        return path

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate and warn about database choice."""
        if "sqlite" in v.lower():
            import warnings
            warnings.warn(
                "SQLite is not recommended for production. "
                "Use PostgreSQL for concurrent access and better performance.",
                UserWarning,
                stacklevel=2
            )
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience accessor
settings = get_settings()
