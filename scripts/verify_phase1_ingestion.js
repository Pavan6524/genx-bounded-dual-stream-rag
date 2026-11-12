const fs = require('fs');

const wf = JSON.parse(fs.readFileSync('workflows/ingestion_firewall.json', 'utf8'));

const results = {
  workflow_id: wf.id,
  workflow_name: wf.name,
  active_state: wf.active,
  total_nodes: wf.nodes.length,
  checks: {}
};

// Check 1 & 2 & 3: Validate & Assemble Chunks JavaScript code syntax
const valNode = wf.nodes.find(n => n.name === 'Validate & Assemble Chunks');
const valCode = valNode.parameters.jsCode;

let syntaxPass = false;
let syntaxError = null;
try {
  new Function(valCode);
  syntaxPass = true;
} catch (e) {
  syntaxError = e.message;
}

results.checks.validate_node_syntax = {
  pass: syntaxPass,
  error: syntaxError
};

// Check 4: Logic checks on Validate & Assemble Chunks
results.checks.validate_node_logic = {
  has_test_restriction: valCode.includes("startsWith('TEST-')"),
  validates_session_id_exists: valCode.includes('!sessionId'),
  checks_session_id_string: valCode.includes("typeof sessionId !== 'string'"),
  validates_stream_types: valCode.includes("['framework', 'voice_sample']"),
  enforces_1024_dims: valCode.includes('1024'),
  validates_dr_sara_speaker: valCode.includes("chunk.metadata.speaker !== 'Dr. Sara Hegy'"),
  preserves_metadata: valCode.includes('metadata: c.metadata')
};

// Check 5 & 6: HttpRequest nodes jsonBody syntax
const httpNodes = [
  'Ollama Classifier',
  'Ollama Framework Extractor',
  'Ollama Framework Embedder',
  'Ollama Voice Embedder'
];

results.checks.http_nodes = {};
for (const name of httpNodes) {
  const n = wf.nodes.find(node => node.name === name);
  const body = n.parameters.jsonBody || '';
  const isObjectExpression = body.startsWith('={{ {') && body.endsWith('} }}');
  results.checks.http_nodes[name] = {
    present: !!n,
    typeVersion: n.typeVersion,
    is_object_expression: isObjectExpression,
    body_snippet: body.substring(0, 60).replace(/\n/g, ' ')
  };
}

// Check 7: 21 nodes and connection count
results.checks.dag = {
  node_count: wf.nodes.length,
  connection_count: Object.keys(wf.connections).length
};

// Check 8: Input path
const readNode = wf.nodes.find(n => n.name === 'Read Transcripts File');
results.checks.input_path = {
  fileSelector: readNode?.parameters?.fileSelector,
  matches_production: readNode?.parameters?.fileSelector === '/data/mock_transcripts.json'
};

// Check 9: Database functions
const vaultNode = wf.nodes.find(n => n.name === 'Atomic Vault Replacement Function');
const rejNode = wf.nodes.find(n => n.name === 'Transactional Archive Rejected');

results.checks.database_functions = {
  vault_query: vaultNode?.parameters?.query,
  uses_ingest_session_vault: vaultNode?.parameters?.query?.includes('ingest_session_vault'),
  rejection_query: rejNode?.parameters?.query,
  uses_archive_rejected_meeting: rejNode?.parameters?.query?.includes('archive_rejected_meeting')
};

// Check 10: Postgres credentials
results.checks.credentials = {
  vault_cred_name: vaultNode?.credentials?.postgres?.name,
  vault_cred_id: vaultNode?.credentials?.postgres?.id,
  rej_cred_name: rejNode?.credentials?.postgres?.name,
  rej_cred_id: rejNode?.credentials?.postgres?.id,
  matches_expected_account: vaultNode?.credentials?.postgres?.id === 'NIeKz7GoX1wU6irq' && rejNode?.credentials?.postgres?.id === 'NIeKz7GoX1wU6irq'
};

console.log(JSON.stringify(results, null, 2));
