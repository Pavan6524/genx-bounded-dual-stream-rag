const fs = require('fs');

const testWf = JSON.parse(fs.readFileSync('workflows/ingestion_firewall_runtime_test.json', 'utf8'));

// Clone
const prodWf = JSON.parse(JSON.stringify(testWf));

prodWf.id = 'IlBw4RRELuh02Akm';
prodWf.name = 'Ingestion Firewall & Dual-Stream Extraction';
prodWf.active = false;

// 1. Read Transcripts File -> /data/mock_transcripts.json
const readNode = prodWf.nodes.find(n => n.name === 'Read Transcripts File');
readNode.parameters.fileSelector = '/data/mock_transcripts.json';

// 2. Validate & Assemble Chunks -> general session ID validation
const valNode = prodWf.nodes.find(n => n.name === 'Validate & Assemble Chunks');
valNode.parameters.jsCode = valNode.parameters.jsCode.replace(
  /if \(!sessionId \|\| !sessionId\.startsWith\('TEST-'\)\) \{[\s\S]*?\}/,
  "if (!sessionId || typeof sessionId !== 'string' || sessionId.trim().length === 0) {\n  throw new Error(`CRITICAL VALIDATION FAILURE: Invalid or missing session ID: '${sessionId}'`);\n}"
);

// 3. Update SQL queries to production functions
const vaultNode = prodWf.nodes.find(n => n.name === 'Atomic Vault Replacement Function');
vaultNode.parameters.query = 'SELECT * FROM ingest_session_vault($1, $2::jsonb);';
vaultNode.credentials = { postgres: { id: 'NIeKz7GoX1wU6irq', name: 'Postgres account' } };

const rejNode = prodWf.nodes.find(n => n.name === 'Transactional Archive Rejected');
rejNode.parameters.query = 'SELECT * FROM archive_rejected_meeting($1, $2, $3, $4, $5, $6);';
rejNode.credentials = { postgres: { id: 'NIeKz7GoX1wU6irq', name: 'Postgres account' } };

fs.writeFileSync('workflows/ingestion_firewall.json', JSON.stringify(prodWf, null, 2), 'utf8');
console.log('Production workflows/ingestion_firewall.json written successfully.');
