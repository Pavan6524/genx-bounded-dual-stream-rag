const fs = require('fs');
const log = fs.readFileSync('scripts/production_ingest_ses102_trace.log', 'utf8');

const key = '"Pass Framework Chunk":';
let idx = log.indexOf(key);
console.log('Index of ' + key + ':', idx);
if (idx !== -1) {
  console.log(log.substring(idx, idx + 600));
}

const key2 = '"Pass Voice Chunk":';
let idx2 = log.indexOf(key2);
console.log('Index of ' + key2 + ':', idx2);
if (idx2 !== -1) {
  console.log(log.substring(idx2, idx2 + 600));
}

const key3 = '"Format Framework Chunks":';
let idx3 = log.indexOf(key3);
console.log('Index of ' + key3 + ':', idx3);
if (idx3 !== -1) {
  console.log(log.substring(idx3, idx3 + 600));
}
