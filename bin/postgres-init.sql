-- Enable pgvector extension for embedding storage.
-- Runs once on first container start (docker-entrypoint-initdb.d).
CREATE EXTENSION IF NOT EXISTS vector;
