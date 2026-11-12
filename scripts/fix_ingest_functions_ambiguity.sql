-- Fix ambiguous column reference in ingest_session_vault and archive_rejected_meeting
-- Qualifying table columns as kv.session_id and rm.session_id resolves the conflict with RETURNS TABLE(session_id ...)

CREATE OR REPLACE FUNCTION public.ingest_session_vault(p_session_id character varying, p_chunks jsonb)
 RETURNS TABLE(session_id character varying, inserted_count integer, status text)
 LANGUAGE plpgsql
AS $function$
DECLARE
    item JSONB;
    c_count INT := 0;
    vec_dims INT;
BEGIN
    IF p_session_id IS NULL OR length(trim(p_session_id)) = 0 THEN
        RAISE EXCEPTION 'Validation failure: p_session_id cannot be null or empty';
    END IF;
    IF p_chunks IS NULL OR jsonb_typeof(p_chunks) <> 'array' OR jsonb_array_length(p_chunks) = 0 THEN
        RAISE EXCEPTION 'Validation failure: p_chunks must be non-empty for session %', p_session_id;
    END IF;

    FOR item IN SELECT * FROM jsonb_array_elements(p_chunks) LOOP
        IF item->>'stream_type' IS NULL OR item->>'stream_type' NOT IN ('framework', 'voice_sample') THEN
            RAISE EXCEPTION 'Validation failure: invalid stream_type in session %', p_session_id;
        END IF;
        IF item->>'content' IS NULL OR length(trim(item->>'content')) = 0 THEN
            RAISE EXCEPTION 'Validation failure: empty content in session %', p_session_id;
        END IF;
        IF item->'metadata' IS NULL OR jsonb_typeof(item->'metadata') <> 'object' THEN
            RAISE EXCEPTION 'Validation failure: metadata must be valid JSON in session %', p_session_id;
        END IF;
        IF item->'embedding' IS NULL OR jsonb_typeof(item->'embedding') <> 'array' OR jsonb_array_length(item->'embedding') <> 1024 THEN
            RAISE EXCEPTION 'Validation failure: embedding must have length 1024 in session %', p_session_id;
        END IF;
        vec_dims := vector_dims((item->>'embedding')::vector);
        IF vec_dims <> 1024 THEN
            RAISE EXCEPTION 'Validation failure: embedding dimension % != 1024 in session %', vec_dims, p_session_id;
        END IF;
    END LOOP;

    PERFORM pg_advisory_xact_lock(hashtext(p_session_id));

    -- Qualify with table aliases kv and rm to avoid PL/pgSQL variable ambiguity
    DELETE FROM knowledge_vault kv WHERE kv.session_id = p_session_id;
    DELETE FROM rejected_meetings rm WHERE rm.session_id = p_session_id;

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
$function$;

CREATE OR REPLACE FUNCTION public.archive_rejected_meeting(
    p_session_id character varying,
    p_meeting_type character varying,
    p_confidence_score numeric,
    p_summary text,
    p_raw_transcript text,
    p_rejection_reason character varying
)
 RETURNS TABLE(session_id character varying, archived_count integer, status text)
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF p_session_id IS NULL OR length(trim(p_session_id)) = 0 THEN
        RAISE EXCEPTION 'Validation failure: p_session_id cannot be null or empty';
    END IF;
    IF p_meeting_type IS NULL OR length(trim(p_meeting_type)) = 0 THEN
        RAISE EXCEPTION 'Validation failure: meeting_type cannot be null or empty';
    END IF;
    IF p_confidence_score IS NULL OR p_confidence_score < 0.0 OR p_confidence_score > 1.0 THEN
        RAISE EXCEPTION 'Validation failure: confidence_score out of range';
    END IF;
    IF p_rejection_reason IS NULL OR length(trim(p_rejection_reason)) = 0 THEN
        RAISE EXCEPTION 'Validation failure: rejection_reason cannot be null or empty';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtext(p_session_id));

    -- Qualify with table aliases rm and kv to avoid PL/pgSQL variable ambiguity
    DELETE FROM rejected_meetings rm WHERE rm.session_id = p_session_id;
    DELETE FROM knowledge_vault kv WHERE kv.session_id = p_session_id;

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
$function$;
