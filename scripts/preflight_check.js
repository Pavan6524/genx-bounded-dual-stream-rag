const { execSync } = require('child_process');
const http = require('http');

console.log('=== Checking PostgreSQL Schema, Extension, and Functions ===');
const ext = execSync('docker exec genx-postgres psql -U genx -d genx_rag -t -c "SELECT extname, extversion FROM pg_extension WHERE extname = \'vector\';"').toString().trim();
console.log('pgvector extension:', ext);

const cols = execSync('docker exec genx-postgres psql -U genx -d genx_rag -t -c "SELECT column_name, udt_name FROM information_schema.columns WHERE table_name = \'knowledge_vault\' ORDER BY ordinal_position;"').toString().trim();
console.log('knowledge_vault columns:\n' + cols);

const funcs = execSync('docker exec genx-postgres psql -U genx -d genx_rag -t -c "SELECT proname FROM pg_proc WHERE proname IN (\'ingest_session_vault\', \'archive_rejected_meeting\');"').toString().trim();
console.log('stored functions:\n' + funcs);

const idx = execSync('docker exec genx-postgres psql -U genx -d genx_rag -t -c "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = \'knowledge_vault\';"').toString().trim();
console.log('knowledge_vault indexes:\n' + idx);

console.log('\n=== Testing Embedding Quality (1024 finite floats) ===');
const req = http.request({
  hostname: '127.0.0.1',
  port: 11434,
  path: '/api/embeddings',
  method: 'POST',
  headers: { 'Content-Type': 'application/json' }
}, res => {
  let d = '';
  res.on('data', c => d += c);
  res.on('end', () => {
    const json = JSON.parse(d);
    const emb = json.embedding;
    const isArray = Array.isArray(emb);
    const length = emb ? emb.length : 0;
    const allFinite = isArray && emb.every(v => typeof v === 'number' && Number.isFinite(v));
    console.log('Embedding status:', res.statusCode);
    console.log('Dimension count:', length);
    console.log('All finite numbers:', allFinite);
  });
});
req.write(JSON.stringify({ model: 'bge-m3:latest', prompt: 'Preflight test embedding verification' }));
req.end();
