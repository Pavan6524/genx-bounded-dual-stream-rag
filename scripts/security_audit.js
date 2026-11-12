const fs = require('fs');
const path = require('path');

function walk(dir) {
  let results = [];
  const list = fs.readdirSync(dir);
  list.forEach(file => {
    if (file === '.git' || file === 'node_modules' || file === 'postgres_data' || file === 'n8n_data') return;
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat && stat.isDirectory()) {
      results = results.concat(walk(fullPath));
    } else {
      results.push({ path: fullPath, size: stat.size });
    }
  });
  return results;
}

const allFiles = walk('.');
console.log('Total files found:', allFiles.length);

const largeFiles = allFiles.filter(f => f.size > 500 * 1024);
console.log('Files > 500KB:', largeFiles);

// Files by extension
const extensions = {};
allFiles.forEach(f => {
  const ext = path.extname(f.path) || '(no ext)';
  extensions[ext] = (extensions[ext] || 0) + 1;
});
console.log('Extensions:', extensions);

// Check if .env is present
console.log('.env exists in workspace:', fs.existsSync('.env'));
