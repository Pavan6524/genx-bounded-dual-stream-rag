const fs = require('fs');
const path = require('path');

function walk(dir) {
  let results = [];
  const list = fs.readdirSync(dir);
  list.forEach(file => {
    if (file === '.git' || file === 'node_modules' || file === 'postgres_data' || file === 'n8n_data' || file === '__pycache__') return;
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat && stat.isDirectory()) {
      results = results.concat(walk(fullPath));
    } else {
      results.push(fullPath);
    }
  });
  return results;
}

const files = walk('.');

const secretChecks = [
  { name: 'Private Key', regex: /-----BEGIN [A-Z ]*PRIVATE KEY-----/ },
  { name: 'Generic API Key', regex: /(?:api[_-]?key|bearer|token)\s*[:=]\s*['"][A-Za-z0-9_\-]{20,}['"]/i },
  { name: 'Hardcoded Secret', regex: /client_secret\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}['"]/i }
];

console.log(`Scanning ${files.length} files for secrets...`);
let found = 0;
files.forEach(f => {
  if (f === '.env' || f.endsWith('.png') || f.endsWith('.jpg') || f.endsWith('.pyc')) return;
  try {
    const content = fs.readFileSync(f, 'utf8');
    secretChecks.forEach(chk => {
      if (chk.regex.test(content)) {
        console.warn(`[WARNING] Potential ${chk.name} in ${f}`);
        found++;
      }
    });
  } catch (e) {}
});

console.log(`Scan completed. Flags found: ${found}`);
