"""
Alembic Migration Environment

Production-grade database migration setup with:
- SQLAlchemy 2.0 support
- Transaction management
"""

import logging
import sys
from pathlib import Path
from sqlalchemy import engine_from_config, pool
from alembic import context

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import application components
from src.core.config.settings import settings
from src.infrastructure.database.models.base import Base
from src.utils.logging import get_logger

# ======================== ALEMBIC CONFIGURATION ========================

# Alembic Config object
config = context.config

# Set up logging
logger = get_logger("alembic")

# Override database URL from settings
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    logging.getLogger('alembic').setLevel(logging.INFO)

# Target metadata for autogenerate
target_metadata = Base.metadata

# ======================== MIGRATION FUNCTIONS ========================

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    
    This configures the context with just a URL and not an Engine,
    though an Engine is also acceptable here. By skipping the Engine
    creation we don't even need a DBAPI to be available.
    """
    logger.info("Running migrations in offline mode")
    
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=False,
        render_as_batch=False
    )
    
    with context.begin_transaction():
        context.run_migrations()
    
    logger.info("Offline migrations completed")


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    
    Creates an Engine and associates a connection with the context.
    """
    logger.info("Running migrations in online mode")
    
    # Create configuration for engine
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.database_url
    
    # Create engine
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    
    with connectable.connect() as connection:
        logger.info("Connected to database for migrations")
        
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=False,
            render_as_batch=False,
            transaction_per_migration=True,
            # Custom comparison functions
            compare_foreign_keys=True,
            include_name=include_name,
            include_object=include_object
        )
        
        try:
            with context.begin_transaction():
                context.run_migrations()
            logger.info("Online migrations completed successfully")
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise


def include_name(name: str, type_: str, parent_names: dict) -> bool:
    """
    Determine which names to include in migrations.
    
    Args:
        name: The name of the object
        type_: The type of object (table, column, index, etc.)
        parent_names: Dictionary of parent object names
        
    Returns:
        True if the object should be included in migrations
    """
    # Include all TrustCheck tables
    if type_ == "table":
        trustcheck_tables = [
            "sanctioned_entities",
            "change_events", 
            "scraper_runs",
            "content_snapshots",
            "entity_change_log",  # Legacy
            "scraping_log"        # Legacy
        ]
        return name in trustcheck_tables
    
    # Include all other objects by default
    return True


def include_object(obj, name: str, type_: str, reflected: bool, compare_to) -> bool:
    """
    Determine which objects to include in migrations.
    
    Args:
        obj: The SQLAlchemy object
        name: Name of the object
        type_: Type of object
        reflected: Whether the object was reflected from the database
        compare_to: The object being compared to (if any)
        
    Returns:
        True if the object should be included
    """
    # Skip temporary tables
    if type_ == "table" and name.startswith("temp_"):
        return False
    
    # Skip system tables
    if type_ == "table" and name.startswith(("pg_", "information_schema")):
        return False
    
    # Include all TrustCheck objects
    return True


# ======================== MIGRATION EXECUTION ========================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()