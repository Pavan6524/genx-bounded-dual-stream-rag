const fs = require('fs');
const crypto = require('crypto');

console.log('=== LIVE WORKFLOW POST-IMPORT COMPARISON ===\n');

const canonicalRaw = fs.readFileSync('workflows/ingestion_firewall.json', 'utf8');
const liveRaw = fs.readFileSync('workflows/live_exported_production_wf.json', 'utf8');

const canonical = JSON.parse(canonicalRaw);
const liveData = JSON.parse(liveRaw);
const live = Array.isArray(liveData) ? liveData[0] : liveData;

const report = {
  timestamp: new Date().toISOString(),
  target_workflow_id: 'IlBw4RRELuh02Akm',
  checks: {}
};

// 1. Workflow ID Check
const idMatch = live.id === canonical.id && live.id === 'IlBw4RRELuh02Akm';
report.checks.workflow_id = {
  status: idMatch ? 'PASS' : 'FAIL',
  canonical_id: canonical.id,
  live_id: live.id
};
console.log(`1. Workflow ID: ${idMatch ? 'PASS' : 'FAIL'} (${live.id})`);

// 2. Workflow Name
const nameMatch = live.name === canonical.name;
report.checks.workflow_name = {
  status: nameMatch ? 'PASS' : 'FAIL',
  canonical_name: canonical.name,
  live_name: live.name
};
console.log(`2. Workflow Name: ${nameMatch ? 'PASS' : 'FAIL'} ("${live.name}")`);

// 3. Active State
const activeMatch = live.active === false && canonical.active === false;
report.checks.active_state = {
  status: activeMatch ? 'PASS' : 'FAIL',
  canonical_active: canonical.active,
  live_active: live.active
};
console.log(`3. Active State: ${activeMatch ? 'PASS' : 'FAIL'} (active: ${live.active})`);

// 4. Node Count
const countMatch = live.nodes.length === canonical.nodes.length && live.nodes.length === 15;
report.checks.node_count = {
  status: countMatch ? 'PASS' : 'FAIL',
  canonical_count: canonical.nodes.length,
  live_count: live.nodes.length
};
console.log(`4. Node Count: ${countMatch ? 'PASS' : 'FAIL'} (${live.nodes.length} nodes)`);

// 5. Node Comparison
console.log('\n5. Comparing Individual Nodes:');
const canonicalNodeMap = new Map(canonical.nodes.map(n => [n.name, n]));
const liveNodeMap = new Map(live.nodes.map(n => [n.name, n]));

let nodeMismatches = 0;
const nodeComparisonList = [];

for (const [name, cNode] of canonicalNodeMap.entries()) {
  const lNode = liveNodeMap.get(name);
  if (!lNode) {
    console.error(`   [MISSING] Node "${name}" missing from live export!`);
    nodeMismatches++;
    continue;
  }
  
  const typeMatch = cNode.type === lNode.type;
  const versionMatch = cNode.typeVersion === lNode.typeVersion;
  
  // Compare jsCode if code node
  let codeMatch = true;
  if (cNode.parameters && cNode.parameters.jsCode) {
    codeMatch = (cNode.parameters.jsCode.trim() === (lNode.parameters.jsCode || '').trim());
  }

  const nodeStatus = typeMatch && versionMatch && codeMatch ? 'PASS' : 'FAIL';
  if (nodeStatus === 'FAIL') nodeMismatches++;
  
  nodeComparisonList.push({
    name,
    id: lNode.id,
    type: lNode.type,
    typeVersion: lNode.typeVersion,
    status: nodeStatus
  });
  console.log(`   [${nodeStatus}] ${name} (${lNode.type} v${lNode.typeVersion})`);
}

report.checks.nodes_audit = {
  status: nodeMismatches === 0 ? 'PASS' : 'FAIL',
  mismatches: nodeMismatches,
  nodes: nodeComparisonList
};

// 6. Connections Comparison
console.log('\n6. Comparing Connection Topologies:');
let connMismatches = 0;
for (const [source, conn] of Object.entries(canonical.connections)) {
  const liveConn = live.connections[source];
  if (!liveConn) {
    console.error(`   [MISSING] Source connection for "${source}" missing in live!`);
    connMismatches++;
    continue;
  }
  
  const cTargets = JSON.stringify(conn.main);
  const lTargets = JSON.stringify(liveConn.main);
  if (cTargets !== lTargets) {
    console.error(`   [MISMATCH] Connection mismatch for "${source}"!`);
    console.error(`     Canonical: ${cTargets}`);
    console.error(`     Live:      ${lTargets}`);
    connMismatches++;
  } else {
    console.log(`   [PASS] "${source}" connection graph matched.`);
  }
}

report.checks.connections_audit = {
  status: connMismatches === 0 ? 'PASS' : 'FAIL',
  mismatches: connMismatches
};

// Write comparison JSON
fs.writeFileSync('scripts/phase2_2_live_workflow_comparison.json', JSON.stringify(report, null, 2));
console.log('\nSaved report: scripts/phase2_2_live_workflow_comparison.json');

const overallPass = idMatch && nameMatch && activeMatch && countMatch && (nodeMismatches === 0) && (connMismatches === 0);
console.log(`\nOVERALL IMPORT VERIFICATION: ${overallPass ? 'ALL CHECKS PASSED (PASS)' : 'FAILED'}`);
if (!overallPass) process.exit(1);
