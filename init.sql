-- GenX Leadership Academy — Database Schema
-- Bounded Dual-Stream RAG Pipeline
--
-- Tables:
--   knowledge_vault    — embedded coaching knowledge (framework + voice_sample)
--   rejected_meetings  — relational archive for non-coaching meetings (NO embeddings)
--
-- Embedding model: bge-m3 (1024 dimensions)

-- ═══════════════════════════════════════════════════════
-- Enable pgvector extension
-- ═══════════════════════════════════════════════════════
CREATE EXTENSION IF NOT EXISTS vector;

-- ═══════════════════════════════════════════════════════
-- knowledge_vault
-- Stores embedded coaching knowledge in two streams:
--   'framework'    — conceptual coaching frameworks
--   'voice_sample' — Dr Sara Hegy's verbatim dialogue
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS knowledge_vault (
    id              SERIAL        PRIMARY KEY,
    session_id      VARCHAR(20)   NOT NULL,
    stream_type     VARCHAR(20)   NOT NULL
                    CHECK (stream_type IN ('framework', 'voice_sample')),
    content         TEXT          NOT NULL,
    metadata        JSONB         NOT NULL DEFAULT '{}',
    embedding       vector(1024)  NOT NULL,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- HNSW cosine similarity index
-- Operator class: vector_cosine_ops (cosine distance)
-- m=16:              max connections per graph node (default, RAM-friendly)
-- ef_construction=64: search breadth during index build (default)
CREATE INDEX IF NOT EXISTS idx_knowledge_vault_embedding
ON knowledge_vault
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- B-tree index for stream_type filtering (used before vector search)
CREATE INDEX IF NOT EXISTS idx_knowledge_vault_stream_type
ON knowledge_vault (stream_type);

-- B-tree index for session lookups
CREATE INDEX IF NOT EXISTS idx_knowledge_vault_session_id
ON knowledge_vault (session_id);

-- ═══════════════════════════════════════════════════════
-- rejected_meetings
-- Relational archive for meetings that failed the
-- ingestion classification firewall.
--
-- IMPORTANT: This table has NO embedding column.
-- Rejected meetings must NEVER receive embeddings.
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS rejected_meetings (
    id                SERIAL        PRIMARY KEY,
    session_id        VARCHAR(20)   NOT NULL,
    meeting_type      VARCHAR(50)   NOT NULL,
    confidence_score  NUMERIC(4,2)
                      CHECK (confidence_score >= 0 AND confidence_score <= 1),
    summary           TEXT,
    raw_transcript    TEXT,
    rejection_reason  VARCHAR(100)  NOT NULL,
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- B-tree index for session lookups on rejected meetings
CREATE INDEX IF NOT EXISTS idx_rejected_meetings_session_id
ON rejected_meetings (session_id);
