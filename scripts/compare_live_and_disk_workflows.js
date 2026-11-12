const fs = require('fs');

const liveRaw = fs.readFileSync('workflows/live_exported_production_wf.json', 'utf8');
const liveWf = JSON.parse(liveRaw)[0];
const diskWf = JSON.parse(fs.readFileSync('workflows/ingestion_firewall.json', 'utf8'));

console.log('Live WF ID:', liveWf.id);
console.log('Disk WF ID:', diskWf.id);
console.log('Live WF Name:', liveWf.name);
console.log('Disk WF Name:', diskWf.name);
console.log('Live WF Active:', liveWf.active);
console.log('Disk WF Active:', diskWf.active);
console.log('Live WF Node Count:', liveWf.nodes.length);
console.log('Disk WF Node Count:', diskWf.nodes.length);

const httpNodeNames = [
  'Ollama Classifier',
  'Ollama Framework Extractor',
  'Ollama Framework Embedder',
  'Ollama Voice Embedder'
];

for (const name of httpNodeNames) {
  const liveN = liveWf.nodes.find(n => n.name === name);
  const diskN = diskWf.nodes.find(n => n.name === name);
  const liveBody = liveN?.parameters?.jsonBody || '';
  const diskBody = diskN?.parameters?.jsonBody || '';
  console.log('--- ' + name + ' ---');
  console.log('Identical:', liveBody === diskBody);
  console.log('Live body syntax:', liveBody.startsWith('={{ {') ? 'JS Object Expression' : 'String Template');
  console.log('Disk body syntax:', diskBody.startsWith('={{ {') ? 'JS Object Expression' : 'String Template');
}
