-- ==============================================================================
-- GenX Leadership Academy — Production Ingestion Rollback Script
-- Target: Rollback only production records SES-101, SES-102, SES-103, SES-104
-- NEVER deletes TEST-* records. NEVER truncates tables.
-- ==============================================================================

\set ON_ERROR_STOP on

BEGIN;

-- 1. Pre-rollback Safety Assertion: Confirm TEST-prefixed records exist
DO $$
DECLARE
    test_vault_count INT;
    test_rej_count INT;
BEGIN
    SELECT count(*) INTO test_vault_count FROM knowledge_vault WHERE session_id LIKE 'TEST-%';
    SELECT count(*) INTO test_rej_count FROM rejected_meetings WHERE session_id LIKE 'TEST-%';
    
    IF test_vault_count < 8 THEN
        RAISE EXCEPTION 'CRITICAL INTEGRITY FAILURE: Expected at least 8 TEST-* vault rows, found %', test_vault_count;
    END IF;
    
    IF test_rej_count < 2 THEN
        RAISE EXCEPTION 'CRITICAL INTEGRITY FAILURE: Expected at least 2 TEST-* rejected rows, found %', test_rej_count;
    END IF;
END $$;

-- 2. Targeted Deletion of Production Records Only
DELETE FROM knowledge_vault 
WHERE session_id IN ('SES-101', 'SES-102', 'SES-103', 'SES-104')
  AND session_id NOT LIKE 'TEST-%';

DELETE FROM rejected_meetings 
WHERE session_id IN ('SES-101', 'SES-102', 'SES-103', 'SES-104')
  AND session_id NOT LIKE 'TEST-%';

-- 3. Post-rollback Verification: Ensure baseline is restored exactly
DO $$
DECLARE
    total_vault_count INT;
    total_rej_count INT;
    prod_vault_count INT;
    prod_rej_count INT;
BEGIN
    SELECT count(*) INTO total_vault_count FROM knowledge_vault;
    SELECT count(*) INTO total_rej_count FROM rejected_meetings;
    SELECT count(*) INTO prod_vault_count FROM knowledge_vault WHERE session_id IN ('SES-101', 'SES-102', 'SES-103', 'SES-104');
    SELECT count(*) INTO prod_rej_count FROM rejected_meetings WHERE session_id IN ('SES-101', 'SES-102', 'SES-103', 'SES-104');

    IF prod_vault_count > 0 OR prod_rej_count > 0 THEN
        RAISE EXCEPTION 'ROLLBACK FAILED: Production records still detected in database!';
    END IF;

    IF total_vault_count != 8 OR total_rej_count != 2 THEN
        RAISE EXCEPTION 'ROLLBACK FAILED: Database baseline count mismatch! Vault: %, Rejected: % (Expected 8 and 2)', total_vault_count, total_rej_count;
    END IF;

    RAISE NOTICE 'ROLLBACK SUCCESS: Database restored to exact 8-vault and 2-rejected baseline.';
END $$;

COMMIT;

-- Read-only verification query
SELECT 'knowledge_vault' AS table_name, count(*) AS row_count, count(*) FILTER (WHERE session_id LIKE 'TEST-%') AS test_rows FROM knowledge_vault
UNION ALL
SELECT 'rejected_meetings' AS table_name, count(*) AS row_count, count(*) FILTER (WHERE session_id LIKE 'TEST-%') AS test_rows FROM rejected_meetings;
