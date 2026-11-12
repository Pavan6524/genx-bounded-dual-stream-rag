const fs = require('fs');

const wf = JSON.parse(fs.readFileSync('workflows/ingestion_firewall.json', 'utf8'));
const valNode = wf.nodes.find(n => n.name === 'Validate & Assemble Chunks');

const originalCode = valNode.parameters.jsCode;
// Split into lines
const lines = originalCode.split('\n');

// Find the bad line: line with }'`);
const badIndex = lines.findIndex(l => l.includes("}'`);"));
console.log('Bad line index:', badIndex);
if (badIndex !== -1) {
  console.log('Bad line content:', lines[badIndex]);
  // Remove the bad line
  lines.splice(badIndex, 1);
  valNode.parameters.jsCode = lines.join('\n');
  fs.writeFileSync('workflows/ingestion_firewall.json', JSON.stringify(wf, null, 2), 'utf8');
  console.log('Removed bad line successfully.');
} else {
  console.log('Bad line not found directly; inspecting lines 5-12:');
  console.log(lines.slice(5, 12).join('\n'));
}
