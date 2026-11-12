const fs = require('fs');

const wf = JSON.parse(fs.readFileSync('workflows/ingestion_firewall.json', 'utf8'));

console.log('Workflow ID:', wf.id);
console.log('Workflow Name:', wf.name);
console.log('Node Count:', wf.nodes.length);
console.log('Active State:', wf.active);

// Verify all code nodes
for (const n of wf.nodes) {
  if (n.type.includes('code')) {
    const code = n.parameters.jsCode;
    try {
      new Function(code);
      console.log(`Node "${n.name}": JS syntax PASS`);
    } catch (e) {
      console.error(`Node "${n.name}": JS syntax FAIL -`, e.message);
      process.exit(1);
    }
  }
}

// Verify all httpRequest nodes
for (const n of wf.nodes) {
  if (n.type.includes('httpRequest')) {
    const body = n.parameters.jsonBody;
    const isObj = body.startsWith('={{ {') && body.endsWith('} }}');
    console.log(`Node "${n.name}": Body is native JS object expression:`, isObj);
    if (!isObj) {
      console.error(`Node "${n.name}": invalid body expression!`);
      process.exit(1);
    }
  }
}

// Verify connections
const allNodeNames = new Set(wf.nodes.map(n => n.name));
for (const [src, conns] of Object.entries(wf.connections)) {
  if (!allNodeNames.has(src)) {
    console.error(`Source node "${src}" not found in nodes list!`);
    process.exit(1);
  }
  for (const [type, targets] of Object.entries(conns)) {
    for (const tList of targets) {
      for (const t of tList) {
        if (!allNodeNames.has(t.node)) {
          console.error(`Target node "${t.node}" not found in nodes list!`);
          process.exit(1);
        }
      }
    }
  }
}
console.log('DAG Connectivity: All nodes and connections valid!');
console.log('ALL SYNTHETIC CHECKS PASSED 100%!');
