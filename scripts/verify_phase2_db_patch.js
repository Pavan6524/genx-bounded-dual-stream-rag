const { execSync } = require('child_process');

// 1. Verify function definitions
const ingestDef = execSync(
  'docker exec genx-postgres psql -U genx -d genx_rag -t -A -c "SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname = \'ingest_session_vault\';"',
  { encoding: 'utf8' }
);

const archiveDef = execSync(
  'docker exec genx-postgres psql -U genx -d genx_rag -t -A -c "SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname = \'archive_rejected_meeting\';"',
  { encoding: 'utf8' }
);

const testIngestDef = execSync(
  'docker exec genx-postgres psql -U genx -d genx_rag -t -A -c "SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname = \'ingest_test_session_vault\';"',
  { encoding: 'utf8' }
);

const hasKvIngest = ingestDef.includes('kv.session_id = p_session_id');
const hasRmIngest = ingestDef.includes('rm.session_id = p_session_id');

const hasRmArchive = archiveDef.includes('rm.session_id = p_session_id');
const hasKvArchive = archiveDef.includes('kv.session_id = p_session_id');

const testStillRestricted = testIngestDef.includes("TEST-%");

// 2. Verify database counts
const dbCheckRaw = execSync(
  'docker exec genx-postgres psql -U genx -d genx_rag -t -A -c "SELECT \'kv\', count(*), count(*) FILTER (WHERE session_id LIKE \'TEST-%\'), count(*) FILTER (WHERE session_id IN (\'SES-101\', \'SES-102\', \'SES-103\', \'SES-104\')) FROM knowledge_vault UNION ALL SELECT \'rm\', count(*), count(*) FILTER (WHERE session_id LIKE \'TEST-%\'), count(*) FILTER (WHERE session_id IN (\'SES-101\', \'SES-102\', \'SES-103\', \'SES-104\')) FROM rejected_meetings;"',
  { encoding: 'utf8' }
).trim();

const lines = dbCheckRaw.split('\n');
const kvParts = lines.find(l => l.startsWith('kv|')).split('|');
const rmParts = lines.find(l => l.startsWith('rm|')).split('|');

const kvTotal = parseInt(kvParts[1], 10);
const kvTest = parseInt(kvParts[2], 10);
const kvProd = parseInt(kvParts[3], 10);

const rmTotal = parseInt(rmParts[1], 10);
const rmTest = parseInt(rmParts[2], 10);
const rmProd = parseInt(rmParts[3], 10);

const report = {
  phase: "Phase 2 — Database Function Patch Verification",
  patch_applied: true,
  functions: {
    ingest_session_vault_qualified: hasKvIngest && hasRmIngest,
    archive_rejected_meeting_qualified: hasRmArchive && hasKvArchive,
    test_functions_untouched: testStillRestricted
  },
  database_counts: {
    knowledge_vault_total: kvTotal,
    knowledge_vault_test: kvTest,
    knowledge_vault_prod: kvProd,
    rejected_meetings_total: rmTotal,
    rejected_meetings_test: rmTest,
    rejected_meetings_prod: rmProd,
    baseline_exact_8_and_2: kvTotal === 8 && kvTest === 8 && rmTotal === 2 && rmTest === 2,
    production_records_zero: kvProd === 0 && rmProd === 0
  }
};

console.log(JSON.stringify(report, null, 2));
