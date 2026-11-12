const fs = require('fs');

// Load mock transcripts
const transcripts = JSON.parse(fs.readFileSync('data/mock_transcripts.json', 'utf8'));

console.log('Testing unified dual-stream chunk preparation...');

for (const session of transcripts) {
  if (session.id !== 'SES-101' && session.id !== 'SES-102') continue;
  
  // 1. Framework extraction simulation
  let fwName = session.id === 'SES-101' ? 'Completion with Integrity' : 'Table and Shoulder Test';
  let fwContent = session.id === 'SES-101'
    ? 'Framework: Completion with Integrity\nDefinition: Pre-agreed handoff constraints eliminate micromanagement.'
    : 'Framework: Table and Shoulder Test\nDefinition: Isolate neurological load versus operational drift.';
  
  const fwChunk = {
    session_id: session.id,
    stream_type: 'framework',
    content: fwContent,
    metadata: {
      framework_name: fwName,
      session_id: session.id,
      source_timestamps: ['00:01:55']
    }
  };

  // 2. Voice extraction
  const COACH_NAME = 'Dr. Sara Hegy';
  const voiceChunks = [];
  for (const turn of session.transcript) {
    if (turn.speaker === COACH_NAME) {
      voiceChunks.push({
        session_id: session.id,
        stream_type: 'voice_sample',
        content: turn.text,
        metadata: {
          speaker: COACH_NAME,
          session_id: session.id,
          source_timestamps: [turn.timestamp],
          char_count: turn.text.length,
          turn_count: 1
        }
      });
    }
  }

  const sessionChunks = [fwChunk, ...voiceChunks];
  console.log(`Session ${session.id}: Total chunks = ${sessionChunks.length} (1 framework, ${voiceChunks.length} voice)`);
  console.log('  Voice chunk lengths:', voiceChunks.map(v => v.metadata.char_count));
  
  // Validate
  if (sessionChunks.length !== 4) {
    throw new Error(`Expected exactly 4 chunks for ${session.id}, got ${sessionChunks.length}`);
  }
}

console.log('Dual-stream chunk preparation test: PASSED!');
