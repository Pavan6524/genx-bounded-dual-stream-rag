const fs = require('fs');
const log = fs.readFileSync('scripts/production_ingest_ses102_trace.log', 'utf8');

const match = log.match(/Execution error:\s*={30,}\s*(\{[\s\S]*?\})\s*Error executing/);
if (match) {
  const data = JSON.parse(match[1]);
  const runData = data.data.resultData.runData;
  console.log('Executed nodes in runData:', Object.keys(runData));
  
  if (runData['Pass Framework Chunk']) {
    console.log('Pass Framework Chunk runs count:', runData['Pass Framework Chunk'].length);
    runData['Pass Framework Chunk'].forEach((r, idx) => {
      const items = r.data.main[0].map(item => item.json.session_id);
      console.log('  Run ' + idx + ': ' + items.join(', '));
    });
  }
  
  if (runData['Pass Voice Chunk']) {
    console.log('Pass Voice Chunk runs count:', runData['Pass Voice Chunk'].length);
    runData['Pass Voice Chunk'].forEach((r, idx) => {
      const items = r.data.main[0].map(item => item.json.session_id + ' (time: ' + item.json.metadata?.source_timestamps + ')');
      console.log('  Run ' + idx + ': ' + items.join(', '));
    });
  }
  
  if (runData['Extract Voice Stream']) {
    console.log('Extract Voice Stream runs count:', runData['Extract Voice Stream'].length);
    runData['Extract Voice Stream'].forEach((r, idx) => {
      const items = r.data.main[0].map(item => item.json.session_id + ' len=' + item.json.content?.length);
      console.log('  Run ' + idx + ': ' + items.join(', '));
    });
  }
  
  if (runData['Validate & Assemble Chunks']) {
    console.log('Validate & Assemble Chunks runs count:', runData['Validate & Assemble Chunks'].length);
    runData['Validate & Assemble Chunks'].forEach((r, idx) => {
      console.log('  Run ' + idx + ' status: ' + r.executionStatus);
      if (r.data?.main?.[0]) {
        console.log('    Output:', JSON.stringify(r.data.main[0].map(i => i.json)));
      }
    });
  }

  if (runData['Process Sessions Sequentially']) {
    console.log('Process Sessions Sequentially runs count:', runData['Process Sessions Sequentially'].length);
    runData['Process Sessions Sequentially'].forEach((r, idx) => {
      console.log('  Run ' + idx + ': status=' + r.executionStatus);
    });
  }
}
