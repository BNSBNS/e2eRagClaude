-- Migration: Add RAG Type Selection to Documents
-- Date: 2024
-- Description: Adds rag_type and processing_metadata columns to documents table

-- Educational Note:
-- This migration adds user-controlled RAG type selection.
-- The rag_type field determines which processing pipeline is used:
-- - VECTOR: Only vector embeddings (ChromaDB)
-- - GRAPH: Only knowledge graph (Neo4j)
-- - HYBRID: Both approaches

-- Create ENUM type for RAG types
DO $$ BEGIN
    CREATE TYPE ragtype AS ENUM ('vector', 'graph', 'hybrid');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Add rag_type column
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS rag_type ragtype DEFAULT 'vector';

-- Add processing_metadata column
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS processing_metadata JSONB;

-- Create index on rag_type for efficient filtering
CREATE INDEX IF NOT EXISTS ix_documents_rag_type ON documents(rag_type);

-- Update existing documents to have vector RAG type (backward compatibility)
UPDATE documents
SET rag_type = 'vector'
WHERE rag_type IS NULL;

-- Add comment to table
COMMENT ON COLUMN documents.rag_type IS 'User-selected RAG processing type (vector, graph, or hybrid)';
COMMENT ON COLUMN documents.processing_metadata IS 'JSON metadata about RAG processing (chunk counts, entity counts, etc.)';

-- Verification query
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'documents' AND column_name IN ('rag_type', 'processing_metadata');
