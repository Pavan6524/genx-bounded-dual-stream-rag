const fs = require('fs');

const wf = JSON.parse(fs.readFileSync('workflows/ingestion_firewall.json', 'utf8'));

console.log('ID:', wf.id);
console.log('Name:', wf.name);
console.log('Active:', wf.active);
console.log('Node count:', wf.nodes.length);
console.log('File selector:', wf.nodes.find(n => n.name === 'Read Transcripts File')?.parameters?.fileSelector);
console.log('Vault query:', wf.nodes.find(n => n.name === 'Atomic Vault Replacement Function')?.parameters?.query);
console.log('Rejection query:', wf.nodes.find(n => n.name === 'Transactional Archive Rejected')?.parameters?.query);
console.log('Vault creds:', JSON.stringify(wf.nodes.find(n => n.name === 'Atomic Vault Replacement Function')?.credentials));
console.log('Rejection creds:', JSON.stringify(wf.nodes.find(n => n.name === 'Transactional Archive Rejected')?.credentials));

const valCode = wf.nodes.find(n => n.name === 'Validate & Assemble Chunks')?.parameters?.jsCode;
console.log('Contains TEST- restriction:', valCode.includes("startsWith('TEST-')"));
console.log('Contains general validation:', valCode.includes("CRITICAL VALIDATION FAILURE"));
