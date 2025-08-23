-- TrustCheck Database Initialization
-- This script runs when PostgreSQL container starts

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text matching
CREATE EXTENSION IF NOT EXISTS "unaccent"; -- For accent-insensitive search

-- Create custom types
DO $$
BEGIN
    -- Entity types enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'entity_type') THEN
        CREATE TYPE entity_type AS ENUM ('PERSON', 'COMPANY', 'VESSEL', 'AIRCRAFT', 'OTHER');
    END IF;
    
    -- Change types enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'change_type') THEN
        CREATE TYPE change_type AS ENUM ('ADDED', 'MODIFIED', 'REMOVED');
    END IF;
    
    -- Source lists enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'source_list') THEN
        CREATE TYPE source_list AS ENUM ('OFAC', 'UN', 'EU', 'UK_HMT', 'INTERPOL');
    END IF;
    
    -- Scraping status enum
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'scraping_status') THEN
        CREATE TYPE scraping_status AS ENUM ('SUCCESS', 'FAILED', 'PARTIAL', 'RUNNING');
    END IF;
END
$$;

-- Create indexes for better performance (will be created after tables exist)
-- Note: The actual tables are created by SQLAlchemy, these are additional optimizations

COMMENT ON DATABASE trustcheck IS 'TrustCheck Sanctions Compliance Database';

-- Display confirmation
SELECT 'TrustCheck database initialization completed successfully' as status;