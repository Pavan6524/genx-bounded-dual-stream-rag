const { execSync } = require('child_process');

function runSql(query) {
  const cmd = `docker exec genx-postgres psql -U genx -d genx_rag -t -A -F"|" -c "${query}"`;
  return execSync(cmd).toString().trim();
}

console.log('=== Checking Knowledge Vault ===');
const vaultRows = runSql("SELECT id, session_id, stream_type, vector_dims(embedding), length(content), metadata->>'speaker' AS speaker FROM knowledge_vault ORDER BY id;");
console.log('Vault Rows:\n' + vaultRows);

console.log('\n=== Checking Rejected Meetings ===');
const rejectedRows = runSql("SELECT id, session_id, meeting_type, rejection_reason, confidence_score FROM rejected_meetings ORDER BY id;");
console.log('Rejected Rows:\n' + rejectedRows);

console.log('\n=== Aggregate Statistics ===');
const stats = runSql(`
SELECT 
  (SELECT count(*) FROM knowledge_vault) AS vault_total,
  (SELECT count(*) FROM knowledge_vault WHERE session_id LIKE 'TEST-%') AS vault_test,
  (SELECT count(*) FROM knowledge_vault WHERE session_id NOT LIKE 'TEST-%') AS vault_prod,
  (SELECT count(*) FROM knowledge_vault WHERE session_id = 'SES-101' AND stream_type = 'framework') AS ses101_fw,
  (SELECT count(*) FROM knowledge_vault WHERE session_id = 'SES-101' AND stream_type = 'voice_sample') AS ses101_voice,
  (SELECT count(*) FROM knowledge_vault WHERE session_id = 'SES-102' AND stream_type = 'framework') AS ses102_fw,
  (SELECT count(*) FROM knowledge_vault WHERE session_id = 'SES-102' AND stream_type = 'voice_sample') AS ses102_voice,
  (SELECT count(*) FROM rejected_meetings) AS rej_total,
  (SELECT count(*) FROM rejected_meetings WHERE session_id LIKE 'TEST-%') AS rej_test,
  (SELECT count(*) FROM rejected_meetings WHERE session_id NOT LIKE 'TEST-%') AS rej_prod,
  (SELECT count(*) FROM rejected_meetings WHERE session_id = 'SES-103') AS ses103_rej,
  (SELECT count(*) FROM rejected_meetings WHERE session_id = 'SES-104') AS ses104_rej;
`);
console.log('Stats (pipe-separated):\n' + stats);
