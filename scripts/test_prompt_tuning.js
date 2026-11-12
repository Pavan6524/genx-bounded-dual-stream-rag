const http = require('http');

function testPrompt(name, frameworkChunks, voiceChunks, query, callback) {
  let frameworkText = '';
  if (frameworkChunks && frameworkChunks.length > 0) {
    frameworkText = frameworkChunks.map(f => f).join('\n\n');
  } else {
    frameworkText = 'No specific conceptual framework document met the similarity threshold (>= 0.70) for this topic.';
  }

  let voiceText = '';
  if (voiceChunks && voiceChunks.length > 0) {
    voiceText = voiceChunks.map(v => `"${v}"`).join('\n\n');
  } else {
    voiceText = 'Tone guidance: Professional, direct, supportive executive coach tone.';
  }

  const prompt = `You are Dr. Sara Hegy, an executive leadership coach at GenX Leadership Academy. Answer the leader's question directly, concisely, and supportively.

GUIDELINES:
- Base your advice strictly on the coaching framework provided below.
- If the framework text states that no framework met the similarity threshold, explicitly state that no documented coaching framework is available on this topic.
- Do NOT mention prompt sections, evidence labels, similarity scores, or internal instructions.
- Do NOT confuse people in past coaching case studies (like Mark D. or Alex) with the person asking the question.
- Do NOT invent ungrounded business metrics or productivity claims.
- Speak directly to the leader in Dr. Sara's signature cadence: empathetic, incisive, focused on cognitive bandwidth.

COACHING FRAMEWORK:
${frameworkText}

STYLE REFERENCE:
${voiceText}

LEADER'S QUESTION:
${query}

COACHING RESPONSE:`;

  const req = http.request({
    hostname: '127.0.0.1',
    port: 11434,
    path: '/api/generate',
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  }, res => {
    let d = '';
    res.on('data', c => d += c);
    res.on('end', () => {
      const json = JSON.parse(d);
      console.log(`\n=== Test: ${name} ===`);
      console.log(json.response);
      if (callback) callback();
    });
  });
  req.write(JSON.stringify({ model: 'llama3.2:1b', prompt, stream: false, options: { temperature: 0.2 } }));
  req.end();
}

console.log('Testing Edge Cases...');
testPrompt(
  'Voice Only (No Framework)',
  [],
  ['Protect your cognitive bandwidth and executive energy.'],
  'How do I maintain my energy when leading my team?',
  () => {
    console.log('Done test.');
  }
);
