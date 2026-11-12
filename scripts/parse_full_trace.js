const fs = require('fs');

const fullLog = fs.readFileSync('C:/Users/HP/.gemini/antigravity/brain/7140c1e0-4a45-49c6-83d1-b9d3e3bbd609/.system_generated/steps/3118/output.txt', 'utf8');
console.log('Full log size:', fullLog.length);

const startIdx = fullLog.indexOf('Execution error:\n====================================\n{');
console.log('startIdx:', startIdx);
if (startIdx !== -1) {
  const jsonStart = startIdx + 'Execution error:\n====================================\n'.length;
  let depth = 0;
  let jsonEnd = -1;
  for (let i = jsonStart; i < fullLog.length; i++) {
    if (fullLog[i] === '{') depth++;
    else if (fullLog[i] === '}') {
      depth--;
      if (depth === 0) {
        jsonEnd = i + 1;
        break;
      }
    }
  }
  console.log('jsonEnd:', jsonEnd);
  if (jsonEnd !== -1) {
    const parsed = JSON.parse(fullLog.substring(jsonStart, jsonEnd));
    console.log('Status:', parsed.status);
    console.log('Error message:', parsed.data.resultData.error.message);

    const runData = parsed.data.resultData.runData;
    console.log('Nodes in runData:', Object.keys(runData));

    if (runData['Pass Framework Chunk']) {
      console.log('\n--- Pass Framework Chunk ---');
      console.log('Run count:', runData['Pass Framework Chunk'].length);
      runData['Pass Framework Chunk'].forEach((r, idx) => {
        const items = r.data.main[0].map(item => item.json.session_id);
        console.log('  Run ' + idx + ': ' + items.join(', '));
      });
    }

    if (runData['Pass Voice Chunk']) {
      console.log('\n--- Pass Voice Chunk ---');
      console.log('Run count:', runData['Pass Voice Chunk'].length);
      runData['Pass Voice Chunk'].forEach((r, idx) => {
        const items = r.data.main[0].map(item => item.json.session_id + ' (time: ' + item.json.metadata?.source_timestamps + ')');
        console.log('  Run ' + idx + ': ' + items.join(', '));
      });
    }

    if (runData['Extract Voice Stream']) {
      console.log('\n--- Extract Voice Stream ---');
      console.log('Run count:', runData['Extract Voice Stream'].length);
      runData['Extract Voice Stream'].forEach((r, idx) => {
        const items = r.data.main[0].map(item => item.json.session_id + ' (len: ' + item.json.content?.length + ')');
        console.log('  Run ' + idx + ': ' + items.join(', '));
      });
    }

    if (runData['Validate & Assemble Chunks']) {
      console.log('\n--- Validate & Assemble Chunks ---');
      console.log('Run count:', runData['Validate & Assemble Chunks'].length);
      runData['Validate & Assemble Chunks'].forEach((r, idx) => {
        console.log('  Run ' + idx + ' status: ' + r.executionStatus);
        if (r.data?.main?.[0]) {
          console.log('    Output:', JSON.stringify(r.data.main[0].map(i => ({ session_id: i.json.session_id, chunk_count: i.json.chunk_count, fw: i.json.framework_count, voice: i.json.voice_count }))));
        }
      });
    }

    if (runData['Atomic Vault Replacement Function']) {
      console.log('\n--- Atomic Vault Replacement Function ---');
      console.log('Run count:', runData['Atomic Vault Replacement Function'].length);
      runData['Atomic Vault Replacement Function'].forEach((r, idx) => {
        console.log('  Run ' + idx + ' status: ' + r.executionStatus);
        if (r.data?.main?.[0]) {
          console.log('    Output:', JSON.stringify(r.data.main[0].map(i => i.json)));
        }
      });
    }
  }
}
