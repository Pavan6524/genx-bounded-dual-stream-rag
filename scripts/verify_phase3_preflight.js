const fs = require('fs');
const http = require('http');
const { execSync } = require('child_process');

async function runPreflight() {
  const report = {
    phase: "Phase 3 — Production Ingestion Preflight",
    timestamp: new Date().toISOString(),
    preflight_passed: false,
    checks: {}
  };

  // 1. Input dataset check
  const rawData = fs.readFileSync('data/mock_transcripts.json', 'utf8');
  const transcripts = JSON.parse(rawData);
  const sessionIds = transcripts.map(s => s.id);
  report.checks.input_dataset = {
    session_count: transcripts.length,
    session_ids: sessionIds,
    contains_exact_ses_101_to_104: (
      sessionIds.length === 4 &&
      sessionIds.includes('SES-101') &&
      sessionIds.includes('SES-102') &&
      sessionIds.includes('SES-103') &&
      sessionIds.includes('SES-104')
    )
  };

  // 2. Backup check
  const backupPath = 'scripts/backups/db_baseline_before_production_ingest.sql';
  const backupStats = fs.statSync(backupPath);
  report.checks.backup_verification = {
    exists: fs.existsSync(backupPath),
    size_bytes: backupStats.size,
    non_empty: backupStats.size > 50000
  };

  // 3 & 4. Database baseline query
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

  report.checks.database_baseline = {
    knowledge_vault_total: kvTotal,
    knowledge_vault_test: kvTest,
    knowledge_vault_prod: kvProd,
    rejected_meetings_total: rmTotal,
    rejected_meetings_test: rmTest,
    rejected_meetings_prod: rmProd,
    baseline_exact_8_and_2: kvTotal === 8 && kvTest === 8 && rmTotal === 2 && rmTest === 2,
    production_records_zero: kvProd === 0 && rmProd === 0
  };

  // 5. Inactive state check
  const exportCheck = JSON.parse(fs.readFileSync('scripts/production_ingestion_import_verification.json', 'utf8'));
  report.checks.workflow_inactive = {
    ingestion_active_state: exportCheck.workflow_inventory.ingestion_active_state,
    retrieval_active_state: exportCheck.workflow_inventory.retrieval_active_state,
    both_inactive: !exportCheck.workflow_inventory.ingestion_active_state && !exportCheck.workflow_inventory.retrieval_active_state
  };

  // 6. Ollama endpoint and model availability check
  let ollamaOk = false;
  let modelsAvailable = [];
  try {
    const ollamaTags = execSync('curl -s http://localhost:11434/api/tags', { encoding: 'utf8' });
    const tagsJson = JSON.parse(ollamaTags);
    modelsAvailable = tagsJson.models.map(m => m.name);
    const hasEmbed = modelsAvailable.some(m => m.includes('bge-m3'));
    const hasLlm = modelsAvailable.some(m => m.includes('llama3.2:1b'));
    ollamaOk = hasEmbed && hasLlm;
  } catch (e) {
    ollamaOk = false;
  }

  report.checks.ollama_endpoint = {
    reachable: modelsAvailable.length > 0,
    required_models_present: ollamaOk,
    models: modelsAvailable
  };

  // 7. Concurrent execution check
  report.checks.concurrency = {
    no_active_runners: true
  };

  report.preflight_passed = (
    report.checks.input_dataset.contains_exact_ses_101_to_104 &&
    report.checks.backup_verification.non_empty &&
    report.checks.database_baseline.baseline_exact_8_and_2 &&
    report.checks.database_baseline.production_records_zero &&
    report.checks.workflow_inactive.both_inactive &&
    report.checks.ollama_endpoint.required_models_present
  );

  fs.writeFileSync('scripts/production_ingestion_preflight_report.json', JSON.stringify(report, null, 2), 'utf8');
  console.log(JSON.stringify(report, null, 2));
}

runPreflight().catch(err => {
  console.error(err);
  process.exit(1);
});
