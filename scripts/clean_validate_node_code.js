const fs = require('fs');

const wf = JSON.parse(fs.readFileSync('workflows/ingestion_firewall.json', 'utf8'));
const valNode = wf.nodes.find(n => n.name === 'Validate & Assemble Chunks');

const cleanCode = `// Validate & Assemble Complete Session Chunks Array
// Enforces all validation criteria before ANY database replacement operation
const session = $('Validate Classification').first().json;
const sessionId = session.id;

// 1. Session ID validation
if (!sessionId || typeof sessionId !== 'string' || sessionId.trim().length === 0) {
  throw new Error('CRITICAL VALIDATION FAILURE: Invalid or missing session ID');
}

// 2. Gather all embedded framework chunks
const fwItems = $('Pass Framework Chunk').all().filter(item => item.json && item.json.session_id === sessionId);
const frameworkChunks = fwItems.map(item => {
  const c = item.json;
  return {
    session_id: sessionId,
    stream_type: 'framework',
    content: c.content,
    metadata: c.metadata || {},
    embedding: c.embedding
  };
});

// 3. Gather all embedded voice chunks (if any)
let voiceChunks = [];
try {
  const voiceItems = $('Pass Voice Chunk').all().filter(item => item.json && item.json.session_id === sessionId);
  if (Array.isArray(voiceItems)) {
    voiceChunks = voiceItems.map(item => {
      const c = item.json;
      return {
        session_id: sessionId,
        stream_type: 'voice_sample',
        content: c.content,
        metadata: c.metadata || {},
        embedding: c.embedding
      };
    });
  }
} catch (e) {
  // Voice stream empty (allowed if no coach dialogue existed)
}

const allChunks = frameworkChunks.concat(voiceChunks);

// 4. Validate non-empty combined array
if (!Array.isArray(allChunks) || allChunks.length === 0) {
  throw new Error('Validation failed for ' + sessionId + ': Combined chunks array is empty.');
}

// 5. Deep validation of every chunk
const validStreamTypes = ['framework', 'voice_sample'];
for (let i = 0; i < allChunks.length; i++) {
  const chunk = allChunks[i];
  
  // Stream type validation
  if (!validStreamTypes.includes(chunk.stream_type)) {
    throw new Error('Chunk ' + i + ' invalid stream_type: ' + chunk.stream_type);
  }
  
  // Content validation
  if (typeof chunk.content !== 'string' || chunk.content.trim().length === 0) {
    throw new Error('Chunk ' + i + ' has empty or non-string content.');
  }
  
  // Embedding dimension validation: strictly 1024 numeric dimensions
  if (!Array.isArray(chunk.embedding) || chunk.embedding.length !== 1024) {
    throw new Error('Chunk ' + i + ' embedding dimension invalid: expected 1024, got ' + (chunk.embedding ? chunk.embedding.length : 'null'));
  }
  for (let d = 0; d < 1024; d++) {
    if (typeof chunk.embedding[d] !== 'number' || isNaN(chunk.embedding[d])) {
      throw new Error('Chunk ' + i + ' embedding[' + d + '] is not a valid number.');
    }
  }
  
  // Metadata validation: valid JSON object
  if (!chunk.metadata || typeof chunk.metadata !== 'object' || Array.isArray(chunk.metadata)) {
    throw new Error('Chunk ' + i + ' metadata is not a valid object.');
  }
  
  // Voice stream dialogue purity validation
  if (chunk.stream_type === 'voice_sample') {
    if (chunk.metadata.speaker !== 'Dr. Sara Hegy') {
      throw new Error('Chunk ' + i + ' voice sample speaker is not Dr. Sara Hegy (got ' + chunk.metadata.speaker + ')');
    }
  }
}

return [{
  json: {
    session_id: sessionId,
    chunk_count: allChunks.length,
    framework_count: frameworkChunks.length,
    voice_count: voiceChunks.length,
    chunks: allChunks
  }
}];`;

// Syntax test using Function constructor to ensure zero syntax errors
new Function(cleanCode);
console.log('cleanCode syntax check: PASSED');

valNode.parameters.jsCode = cleanCode;
fs.writeFileSync('workflows/ingestion_firewall.json', JSON.stringify(wf, null, 2), 'utf8');
console.log('Saved clean code to workflows/ingestion_firewall.json');
