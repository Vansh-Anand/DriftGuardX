-- DriftGuard-X v2 — PostgreSQL init script
-- Runs once on first container start

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- The Alembic migrations will create all tables.
-- This file handles extensions and any pre-migration setup only.
