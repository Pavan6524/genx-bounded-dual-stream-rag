const fs = require('fs');
const log = fs.readFileSync('scripts/production_ingest_ses102_trace.log', 'utf8');

let pos = 0;
while ((pos = log.indexOf('SES-102', pos)) !== -1) {
  console.log('--- Found SES-102 at pos', pos, '---');
  console.log(log.substring(pos - 100, pos + 200));
  pos += 7;
}
