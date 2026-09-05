-- POLAR-AI Database Initialization
-- Enables PostGIS extension for spatial data types

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Confirm extensions
SELECT postgis_version();
