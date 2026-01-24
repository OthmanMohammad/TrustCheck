-- TrustCheck Database Initialization
-- This script runs when the PostgreSQL container starts for the first time

-- Enable trigram extension for fuzzy text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;
