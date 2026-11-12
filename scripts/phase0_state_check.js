const http = require('http');
const { execSync } = require('child_process');

console.log('=== Checking Ollama from Host ===');
const req = http.get('http://127.0.0.1:11434/api/tags', res => {
  let d = '';
  res.on('data', c => d += c);
  res.on('end', () => {
    console.log('Host Ollama status:', res.statusCode);
    const j = JSON.parse(d);
    console.log('Host models:', j.models.map(m => m.name));

    console.log('\n=== Checking Ollama from genx-n8n Container ===');
    try {
      const out = execSync(`docker exec genx-n8n node -e "const h=require('http');h.get('http://host.docker.internal:11434/api/tags',r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>console.log('Container probe status:',r.statusCode,JSON.parse(d).models.map(m=>m.name)));});"`).toString();
      console.log(out.trim());
    } catch (e) {
      console.error('Container probe error:', e.message);
    }

    console.log('\n=== Checking Vector Dimensions in DB ===');
    try {
      const dbOut = execSync(`docker exec genx-postgres psql -U genx -d genx_rag -t -c "SELECT vector_dims(embedding) FROM knowledge_vault LIMIT 1;"`).toString();
      console.log('Vector dimension in DB:', dbOut.trim());
    } catch (e) {
      console.error('DB query error:', e.message);
    }
  });
}).on('error', err => {
  console.error('Host Ollama probe error:', err.message);
});
