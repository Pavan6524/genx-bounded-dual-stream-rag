const fs = require('fs');

const log = fs.readFileSync('scripts/production_ingest_ses102_trace.log', 'utf8');

// Find all occurrences of "Pass Framework Chunk"
let idx = 0;
while ((idx = log.indexOf('"name": "Pass Framework Chunk"', idx)) !== -1) {
  console.log('Found Pass Framework Chunk at', idx);
  // print following 500 chars
  console.log(log.substring(idx, idx + 500));
  idx += 30;
}
