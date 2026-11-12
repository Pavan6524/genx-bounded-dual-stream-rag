const assert = require('assert');

function runTurnSampler(transcript) {
  const totalTurns = transcript.length;
  let sampledTurns = [];

  if (totalTurns > 60) {
    const first40 = transcript.slice(0, 40);
    const last20 = transcript.slice(-20);
    sampledTurns = first40.concat(last20);
  } else {
    sampledTurns = transcript.slice();
  }

  const dialogueText = sampledTurns
    .map(turn => turn.speaker + ': ' + turn.text)
    .join('\n');

  return {
    dialogue_text: dialogueText,
    turn_sampling: {
      total_turns: totalTurns,
      sampled_turns: sampledTurns.length,
      is_sampled: totalTurns > 60
    },
    sampledTurns
  };
}

console.log('=== Testing Turn Sampler (Synthetic Verification) ===');

// Test Case 1: Short transcript (6 turns)
const shortTurns = Array.from({ length: 6 }, (_, i) => ({
  speaker: i % 2 === 0 ? 'Dr. Sara Hegy' : 'Client',
  text: `Turn ${i + 1} content`
}));
const res1 = runTurnSampler(shortTurns);
assert.strictEqual(res1.turn_sampling.total_turns, 6);
assert.strictEqual(res1.turn_sampling.sampled_turns, 6);
assert.strictEqual(res1.turn_sampling.is_sampled, false);
console.log('[PASS] Short transcript (6 turns): preserved all 6 turns without sampling.');

// Test Case 2: Exact boundary transcript (60 turns)
const boundaryTurns = Array.from({ length: 60 }, (_, i) => ({
  speaker: i % 2 === 0 ? 'Dr. Sara Hegy' : 'Client',
  text: `Turn ${i + 1} content`
}));
const res2 = runTurnSampler(boundaryTurns);
assert.strictEqual(res2.turn_sampling.total_turns, 60);
assert.strictEqual(res2.turn_sampling.sampled_turns, 60);
assert.strictEqual(res2.turn_sampling.is_sampled, false);
console.log('[PASS] Boundary transcript (60 turns): preserved all 60 turns without sampling.');

// Test Case 3: Long transcript (100 turns)
const longTurns = Array.from({ length: 100 }, (_, i) => ({
  speaker: i % 2 === 0 ? 'Dr. Sara Hegy' : 'Client',
  text: `Turn ${i + 1} content`
}));
const res3 = runTurnSampler(longTurns);
assert.strictEqual(res3.turn_sampling.total_turns, 100);
assert.strictEqual(res3.turn_sampling.sampled_turns, 60);
assert.strictEqual(res3.turn_sampling.is_sampled, true);
assert.strictEqual(res3.sampledTurns[0].text, 'Turn 1 content');
assert.strictEqual(res3.sampledTurns[39].text, 'Turn 40 content');
assert.strictEqual(res3.sampledTurns[40].text, 'Turn 81 content');
assert.strictEqual(res3.sampledTurns[59].text, 'Turn 100 content');
console.log('[PASS] Long transcript (100 turns): sampled exactly first 40 (turns 1-40) and last 20 (turns 81-100).');

console.log('\nALL TURN SAMPLER SYNTHETIC TESTS PASSED (100% SUCCESS)');
