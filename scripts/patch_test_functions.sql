\set ON_ERROR_STOP on
BEGIN;

-- ═══════════════════════════════════════════════════════════════
-- 1. Corrected Rejected Meeting Archival Function (TEST Isolation)
-- ═══════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION archive_rejected_test_meeting(
    p_session_id VARCHAR,
    p_meeting_type VARCHAR,
    p_confidence_score NUMERIC,
    p_summary TEXT,
    p_raw_transcript TEXT,
    p_rejection_reason VARCHAR
)
RETURNS TABLE(session_id VARCHAR, archived_count INT, status TEXT) AS $$
BEGIN
    -- 1. Validate session ID: non-null, non-empty, and strictly TEST-*
    IF p_session_id IS NULL OR length(trim(p_session_id)) = 0 OR NOT (p_session_id LIKE 'TEST-%') THEN
        RAISE EXCEPTION 'Safety violation: p_session_id must be non-null and start with TEST- (got %)', p_session_id;
    END IF;

    -- 2. Validate required fields
    IF p_meeting_type IS NULL OR length(trim(p_meeting_type)) = 0 THEN
        RAISE EXCEPTION 'Validation failure: meeting_type cannot be null or empty for session %', p_session_id;
    END IF;

    IF p_confidence_score IS NULL OR p_confidence_score < 0.0 OR p_confidence_score > 1.0 THEN
        RAISE EXCEPTION 'Validation failure: confidence_score % out of range [0.0, 1.0] for session %', p_confidence_score, p_session_id;
    END IF;

    IF p_rejection_reason IS NULL OR length(trim(p_rejection_reason)) = 0 THEN
        RAISE EXCEPTION 'Validation failure: rejection_reason cannot be null or empty for session %', p_session_id;
    END IF;

    -- 3. Acquire transaction-level advisory lock for session concurrency safety
    PERFORM pg_advisory_xact_lock(hashtext(p_session_id));

    -- 4. Sequential atomic replacement: DELETE prior records, then INSERT
    DELETE FROM rejected_meetings rm WHERE rm.session_id = p_session_id AND rm.session_id LIKE 'TEST-%';
    DELETE FROM knowledge_vault kv WHERE kv.session_id = p_session_id AND kv.session_id LIKE 'TEST-%';
    
    INSERT INTO rejected_meetings (
        session_id,
        meeting_type,
        confidence_score,
        summary,
        raw_transcript,
        rejection_reason
    )
    VALUES (
        p_session_id,
        p_meeting_type,
        p_confidence_score,
        p_summary,
        p_raw_transcript,
        p_rejection_reason
    );
    
    RETURN QUERY SELECT p_session_id, 1, 'archived'::TEXT;
END;
$$ LANGUAGE plpgsql;

-- ═══════════════════════════════════════════════════════════════
-- 2. Corrected Accepted Session Vault Ingestion Function (TEST Isolation)
-- ═══════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION ingest_test_session_vault(
    p_session_id VARCHAR,
    p_chunks JSONB
)
RETURNS TABLE(session_id VARCHAR, inserted_count INT, status TEXT) AS $$
DECLARE
    item JSONB;
    c_count INT := 0;
    vec_dims INT;
BEGIN
    -- 1. Validate session ID: non-null, non-empty, and strictly TEST-*
    IF p_session_id IS NULL OR length(trim(p_session_id)) = 0 OR NOT (p_session_id LIKE 'TEST-%') THEN
        RAISE EXCEPTION 'Safety violation: p_session_id must be non-null and start with TEST- (got %)', p_session_id;
    END IF;

    -- 2. Validate non-empty chunks array
    IF p_chunks IS NULL OR jsonb_typeof(p_chunks) <> 'array' OR jsonb_array_length(p_chunks) = 0 THEN
        RAISE EXCEPTION 'Validation failure: p_chunks must be a non-empty JSONB array for session %', p_session_id;
    END IF;

    -- 3. Pre-validation loop: verify EVERY chunk BEFORE any deletion or mutation
    FOR item IN SELECT * FROM jsonb_array_elements(p_chunks) LOOP
        -- Verify stream_type
        IF item->>'stream_type' IS NULL OR item->>'stream_type' NOT IN ('framework', 'voice_sample') THEN
            RAISE EXCEPTION 'Validation failure: invalid stream_type % in session %', item->>'stream_type', p_session_id;
        END IF;

        -- Verify content
        IF item->>'content' IS NULL OR length(trim(item->>'content')) = 0 THEN
            RAISE EXCEPTION 'Validation failure: chunk content cannot be null or empty in session %', p_session_id;
        END IF;

        -- Verify metadata is a valid JSON object
        IF item->'metadata' IS NULL OR jsonb_typeof(item->'metadata') <> 'object' THEN
            RAISE EXCEPTION 'Validation failure: metadata must be a valid JSON object in session %', p_session_id;
        END IF;

        -- Verify embedding is a valid JSON array of length 1024
        IF item->'embedding' IS NULL OR jsonb_typeof(item->'embedding') <> 'array' OR jsonb_array_length(item->'embedding') <> 1024 THEN
            RAISE EXCEPTION 'Validation failure: embedding must be an array of exactly 1024 numbers in session %', p_session_id;
        END IF;

        -- Verify vector dimension via pgvector
        vec_dims := vector_dims((item->>'embedding')::vector);
        IF vec_dims <> 1024 THEN
            RAISE EXCEPTION 'Validation failure: vector_dims % != 1024 in session %', vec_dims, p_session_id;
        END IF;
    END LOOP;

    -- 4. Acquire transaction-level advisory lock for session concurrency safety
    PERFORM pg_advisory_xact_lock(hashtext(p_session_id));

    -- 5. Sequential atomic replacement: DELETE first, then INSERT
    DELETE FROM knowledge_vault kv WHERE kv.session_id = p_session_id AND kv.session_id LIKE 'TEST-%';
    DELETE FROM rejected_meetings rm WHERE rm.session_id = p_session_id AND rm.session_id LIKE 'TEST-%';
    
    FOR item IN SELECT * FROM jsonb_array_elements(p_chunks) LOOP
        INSERT INTO knowledge_vault (
            session_id,
            stream_type,
            content,
            metadata,
            embedding
        )
        VALUES (
            p_session_id,
            item->>'stream_type',
            item->>'content',
            (item->'metadata')::jsonb,
            (item->>'embedding')::vector
        );
        c_count := c_count + 1;
    END LOOP;
    
    RETURN QUERY SELECT p_session_id, c_count, 'ingested'::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMIT;
