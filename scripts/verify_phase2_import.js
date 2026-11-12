const fs = require('fs');

const log = fs.readFileSync('C:/Users/HP/.gemini/antigravity/brain/7140c1e0-4a45-49c6-83d1-b9d3e3bbd609/.system_generated/tasks/task-3077.log', 'utf8');

// Parse export JSON
const match = log.match(/(\[[\s\S]*\])\s*$/);
if (!match) {
  console.error('Failed to parse export log');
  process.exit(1);
}

const allWfs = JSON.parse(match[1]);

const ingestionWf = allWfs.find(w => w.id === 'IlBw4RRELuh02Akm');
const retrievalWf = allWfs.find(w => w.id === 'TSvKBGpM9nK7eb3U');

const canonicalWf = JSON.parse(fs.readFileSync('workflows/ingestion_firewall.json', 'utf8'));

const valNode = ingestionWf.nodes.find(n => n.name === 'Validate & Assemble Chunks');
const valCode = valNode.parameters.jsCode;

let valSyntaxValid = false;
try {
  new Function(valCode);
  valSyntaxValid = true;
} catch (e) {
  valSyntaxValid = false;
}

const readNode = ingestionWf.nodes.find(n => n.name === 'Read Transcripts File');
const vaultNode = ingestionWf.nodes.find(n => n.name === 'Atomic Vault Replacement Function');
const rejNode = ingestionWf.nodes.find(n => n.name === 'Transactional Archive Rejected');

const report = {
  phase: "Phase 2 — Ingestion Workflow Import Verification",
  timestamp: new Date().toISOString(),
  verification_passed: true,
  workflow_inventory: {
    total_workflows: allWfs.length,
    exactly_one_ingestion_workflow: allWfs.filter(w => w.id === 'IlBw4RRELuh02Akm').length === 1,
    ingestion_workflow_id: ingestionWf?.id,
    ingestion_workflow_name: ingestionWf?.name,
    ingestion_project_id: ingestionWf?.shared?.[0]?.projectId,
    ingestion_active_state: ingestionWf?.active,
    retrieval_workflow_id: retrievalWf?.id,
    retrieval_active_state: retrievalWf?.active
  },
  workflow_nodes: {
    live_node_count: ingestionWf?.nodes?.length,
    canonical_node_count: canonicalWf.nodes.length,
    node_count_matches: ingestionWf?.nodes?.length === canonicalWf.nodes.length
  },
  javascript_validation: {
    syntax_valid: valSyntaxValid,
    has_test_guard: valCode.includes("startsWith('TEST-')"),
    validates_session_id: valCode.includes("typeof sessionId !== 'string'")
  },
  configuration_alignment: {
    input_path: readNode?.parameters?.fileSelector,
    input_path_correct: readNode?.parameters?.fileSelector === '/data/mock_transcripts.json',
    vault_sql_function: vaultNode?.parameters?.query,
    vault_sql_correct: vaultNode?.parameters?.query?.includes('ingest_session_vault'),
    rejection_sql_function: rejNode?.parameters?.query,
    rejection_sql_correct: rejNode?.parameters?.query?.includes('archive_rejected_meeting'),
    postgres_cred_id: vaultNode?.credentials?.postgres?.id,
    postgres_cred_correct: vaultNode?.credentials?.postgres?.id === 'NIeKz7GoX1wU6irq'
  }
};

report.verification_passed = (
  report.workflow_inventory.exactly_one_ingestion_workflow &&
  report.workflow_inventory.ingestion_workflow_id === 'IlBw4RRELuh02Akm' &&
  report.workflow_inventory.ingestion_project_id === 'w24y2iBD8xkaEi8K' &&
  report.workflow_inventory.ingestion_active_state === false &&
  report.workflow_inventory.retrieval_active_state === false &&
  report.workflow_nodes.node_count_matches &&
  report.javascript_validation.syntax_valid &&
  !report.javascript_validation.has_test_guard &&
  report.configuration_alignment.input_path_correct &&
  report.configuration_alignment.vault_sql_correct &&
  report.configuration_alignment.rejection_sql_correct &&
  report.configuration_alignment.postgres_cred_correct
);

fs.writeFileSync('scripts/production_ingestion_import_verification.json', JSON.stringify(report, null, 2), 'utf8');
console.log(JSON.stringify(report, null, 2));
