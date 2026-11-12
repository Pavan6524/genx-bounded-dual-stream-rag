const fs = require('fs');
const transcripts = JSON.parse(fs.readFileSync('data/mock_transcripts.json', 'utf8'));

for (const session of transcripts) {
  if (session.id !== 'SES-101' && session.id !== 'SES-102') continue;
  console.log(`=== SESSION: ${session.id} ===`);
  const transcript = session.transcript || [];
  const COACH_NAME = 'Dr. Sara Hegy';

  const consecutiveGroups = [];
  let currentGroup = [];

  for (const turn of transcript) {
    if (turn.speaker === COACH_NAME) {
      currentGroup.push(turn);
    } else {
      if (currentGroup.length > 0) {
        consecutiveGroups.push(currentGroup);
        currentGroup = [];
      }
    }
  }
  if (currentGroup.length > 0) {
    consecutiveGroups.push(currentGroup);
  }

  const chunks = [];
  for (const group of consecutiveGroups) {
    if (group.length === 1) {
      const t = group[0];
      chunks.push({
        session_id: session.id,
        stream_type: 'voice_sample',
        content: t.text,
        metadata: {
          speaker: COACH_NAME,
          session_id: session.id,
          source_timestamps: [t.timestamp],
          char_count: t.text.length,
          turn_count: 1
        }
      });
    } else {
      let combinedText = [];
      let combinedTimestamps = [];
      let currentLen = 0;
      for (const t of group) {
        const addedLen = t.text.length + (combinedText.length > 0 ? 1 : 0);
        if (currentLen + addedLen <= 700 || combinedText.length === 0) {
          combinedText.push(t.text);
          combinedTimestamps.push(t.timestamp);
          currentLen += addedLen;
        } else {
          const cStr = combinedText.join('\n');
          chunks.push({
            session_id: session.id,
            stream_type: 'voice_sample',
            content: cStr,
            metadata: {
              speaker: COACH_NAME,
              session_id: session.id,
              source_timestamps: combinedTimestamps,
              char_count: cStr.length,
              turn_count: combinedText.length
            }
          });
          combinedText = [t.text];
          combinedTimestamps = [t.timestamp];
          currentLen = t.text.length;
        }
      }
      if (combinedText.length > 0) {
        const cStr = combinedText.join('\n');
        chunks.push({
          session_id: session.id,
          stream_type: 'voice_sample',
          content: cStr,
          metadata: {
            speaker: COACH_NAME,
            session_id: session.id,
            source_timestamps: combinedTimestamps,
            char_count: cStr.length,
            turn_count: combinedText.length
          }
        });
      }
    }
  }

  chunks.forEach((c, idx) => {
    console.log(`Chunk ${idx + 1}: length = ${c.metadata.char_count} chars, timestamps = [${c.metadata.source_timestamps.join(', ')}]`);
    console.log(`Content: "${c.content}"\n`);
  });
}
