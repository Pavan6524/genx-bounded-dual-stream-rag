const fs = require('fs');

const workflow = {
  id: "IlBw4RRELuh02Akm",
  name: "Ingestion Firewall & Dual-Stream Extraction",
  active: false,
  nodes: [
    {
      parameters: {},
      id: "e6a2c2bf-8bf0-4f91-88f5-19e072f91df0",
      name: "When clicking ‘Execute workflow’",
      type: "n8n-nodes-base.manualTrigger",
      typeVersion: 1,
      position: [220, 460]
    },
    {
      parameters: {
        operation: "read",
        fileSelector: "/data/mock_transcripts.json",
        options: {}
      },
      id: "7b8d4f6c-8439-4d8b-9a4c-53e7f9e8a001",
      name: "Read Transcripts File",
      type: "n8n-nodes-base.readWriteFile",
      typeVersion: 1,
      position: [440, 460]
    },
    {
      parameters: {
        jsCode: `const item = $input.first();

const buffer = await this.helpers.getBinaryDataBuffer(0, 'data');
const rawText = buffer.toString('utf8').replace(/^\\uFEFF/, '');

let transcripts;
try {
  transcripts = JSON.parse(rawText);
} catch (error) {
  throw new Error('Transcript JSON parsing failed: ' + error.message);
}

if (!Array.isArray(transcripts)) {
  throw new Error('Expected the transcript file to contain a JSON array.');
}

for (let i = 0; i < transcripts.length; i++) {
  const session = transcripts[i];
  if (!session.id || !session.transcript || !Array.isArray(session.transcript)) {
    throw new Error('Session at index ' + i + ' is missing required id or transcript array.');
  }
}

return transcripts.map(transcript => ({
  json: transcript
}));`
      },
      id: "9a4c53e7-7b8d-4f6c-8439-53e7f9e8a002",
      name: "Parse Transcripts Array",
      type: "n8n-nodes-base.code",
      typeVersion: 2,
      position: [660, 460]
    },
    {
      parameters: {
        batchSize: 1,
        options: {}
      },
      id: "84394d8b-9a4c-53e7-7b8d-53e7f9e8a003",
      name: "Process Sessions Sequentially",
      type: "n8n-nodes-base.splitInBatches",
      typeVersion: 3,
      position: [880, 460]
    },
    {
      parameters: {
        jsCode: `// Turn Sampler: First 40 + Last 20 turns for >60 turns
const session = $input.first().json;
const transcript = session.transcript || [];
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
  .join('\\n');

return [{
  json: {
    ...session,
    dialogue_text: dialogueText,
    turn_sampling: {
      total_turns: totalTurns,
      sampled_turns: sampledTurns.length,
      is_sampled: totalTurns > 60
    }
  }
}];`
      },
      id: "53e7f9e8-8439-4d8b-9a4c-7b8d4f6c0004",
      name: "Turn Sampler",
      type: "n8n-nodes-base.code",
      typeVersion: 2,
      position: [1100, 460]
    },
    {
      parameters: {
        method: "POST",
        url: "={{ $env.OLLAMA_BASE_URL || 'http://host.docker.internal:11434' }}/api/generate",
        sendBody: true,
        specifyBody: "json",
        jsonBody: `={{ {\n  model: $env.OLLAMA_LLM_MODEL || 'llama3.2:1b',\n  prompt: "You are an expert meeting classification firewall for GenX Leadership Academy.\\n\\nTranscript:\\n" + $json.dialogue_text + "\\n\\nClassification Rules:\\n1. \\\"Internal Operations\\\" (reject): Discussions about technical infrastructure, code, bugs, webhooks, database migrations, or git. Dr. Sara Hegy is absent.\\n2. \\\"Sales Discovery\\\" (reject): Sales Rep or commercial discussions about pricing, retainer fees ($8,500), budgets, contract terms, or pilot proposals. Dr. Sara Hegy is absent.\\n3. \\\"Client Coaching\\\" (accept): 1-on-1 executive coaching sessions where Dr. Sara Hegy is present and coaching an executive client (e.g. Mark D. or Elena R.) on leadership, management, or executive feedback. If Dr. Sara Hegy is absent, this can NEVER be Client Coaching.\\n4. \\\"Other\\\" (reject): Any meeting that does not match the above.\\n\\nInstructions:\\n- Write a 1-sentence summary first.\\n- Choose the exact meeting_type matching the rules above.\\n- Provide a numeric confidence_score between 0.0 and 1.0 reflecting your certainty.\\n\\nOutput valid JSON with keys \\\"summary\\\", \\\"meeting_type\\\", and \\\"confidence_score\\\":\\n{\\n  \\\"summary\\\": \\\"...\\\",\\n  \\\"meeting_type\\\": \\\"...\\\",\\n  \\\"confidence_score\\\": 0.95\\n}",\n  format: 'json',\n  stream: false,\n  options: {\n    temperature: 0.0\n  }\n} }}`,
        options: { timeout: 90000 }
      },
      id: "4d8b9a4c-53e7-7b8d-8439-7b8d4f6c0005",
      name: "Ollama Classifier",
      type: "n8n-nodes-base.httpRequest",
      typeVersion: 4.1,
      position: [1320, 460]
    },
    {
      parameters: {
        jsCode: `// Validate Ollama Classification Output
const session = $('Process Sessions Sequentially').item.json;
const rawResponse = $input.first().json.response;

let parsed = {};
try {
  parsed = JSON.parse(rawResponse);
} catch (e) {
  const jsonMatch = rawResponse.match(/\\{[\\s\\S]*\\}/);
  if (jsonMatch) {
    try { parsed = JSON.parse(jsonMatch[0]); } catch (e2) {}
  }
}

const meetingType = parsed.meeting_type || 'Other';
let confidenceScore = parseFloat(parsed.confidence_score);
if (isNaN(confidenceScore)) confidenceScore = 0.5;
confidenceScore = Math.max(0.0, Math.min(1.0, confidenceScore));
const summary = parsed.summary || session.title || 'Executive coaching session';

// Firewall Acceptance Gate: Client Coaching AND confidence >= 0.80
const isCoaching = meetingType === 'Client Coaching';
const isAccepted = isCoaching && confidenceScore >= 0.80;

return [{
  json: {
    ...session,
    classification: {
      meeting_type: meetingType,
      confidence_score: confidenceScore,
      summary: summary
    },
    is_accepted: isAccepted,
    dialogue_text: $('Turn Sampler').item.json.dialogue_text
  }
}];`
      },
      id: "7b8d4f6c-53e7-4d8b-9a4c-7b8d4f6c0006",
      name: "Validate Classification",
      type: "n8n-nodes-base.code",
      typeVersion: 2,
      position: [1540, 460]
    },
    {
      parameters: {
        conditions: {
          boolean: [
            {
              value1: "={{ $json.is_accepted }}",
              value2: true
            }
          ]
        }
      },
      id: "53e7f9e8-7b8d-4f6c-8439-7b8d4f6c0007",
      name: "Firewall Gate",
      type: "n8n-nodes-base.if",
      typeVersion: 1,
      position: [1780, 460]
    },
    {
      parameters: {
        jsCode: `// Format Rejected Record
const item = $input.first().json;
const session = $('Process Sessions Sequentially').item.json;
const classification = item.classification || {};

const rawTranscript = (session.transcript || [])
  .map(turn => turn.timestamp + ' ' + turn.speaker + ': ' + turn.text)
  .join('\\n');

let rejectionReason = 'Low confidence score: ' + (classification.confidence_score || 0);
if (classification.meeting_type !== 'Client Coaching') {
  rejectionReason = 'Non-coaching meeting type: ' + classification.meeting_type;
}

return [{
  json: {
    session_id: session.id,
    meeting_type: classification.meeting_type || 'Other',
    confidence_score: classification.confidence_score || 0.0,
    summary: classification.summary || 'Rejected meeting',
    raw_transcript: rawTranscript,
    rejection_reason: rejectionReason
  }
}];`
      },
      id: "84394d8b-7b8d-4f6c-53e7-7b8d4f6c0008",
      name: "Format Rejected Record",
      type: "n8n-nodes-base.code",
      typeVersion: 2,
      position: [2020, 600]
    },
    {
      parameters: {
        operation: "executeQuery",
        query: "SELECT * FROM archive_rejected_meeting($1, $2, $3, $4, $5, $6);",
        options: {
          queryReplacement: "={{ $json.session_id }}, {{ $json.meeting_type }}, {{ $json.confidence_score }}, {{ $json.summary }}, {{ $json.raw_transcript }}, {{ $json.rejection_reason }}"
        }
      },
      id: "4d8b9a4c-8439-7b8d-53e7-7b8d4f6c0010",
      name: "Transactional Archive Rejected",
      type: "n8n-nodes-base.postgres",
      typeVersion: 2.4,
      position: [2260, 600],
      credentials: {
        postgres: {
          id: "3188",
          name: "Postgres account"
        }
      }
    },
    {
      parameters: {
        method: "POST",
        url: "={{ $env.OLLAMA_BASE_URL || 'http://host.docker.internal:11434' }}/api/generate",
        sendBody: true,
        specifyBody: "json",
        jsonBody: `={{ {\n  model: $env.OLLAMA_LLM_MODEL || 'llama3.2:1b',\n  prompt: "You are a coaching knowledge extractor. Extract only explicitly discussed coaching frameworks and diagnostic rules from this transcript.\\n\\nRules:\\n1. Framework Names: When Dr. Sara Hegy explicitly names a framework (e.g. 'Completion with Integrity', 'Table and Shoulder Test'), retain that exact name. Unnamed concepts may use concise descriptive labels, but never invent formal framework names or split one coherent framework into fragmented concepts.\\n2. Definition: Explain what the framework is conceptually. If not explicitly defined, return an empty string \\\"\\\". Never use conversational instructions or closing remarks as definitions.\\n3. Core Mechanism: Detail the concrete diagnostic rule or operational mechanism. Extract decision logic only when explicitly supported by the current transcript. The Table and Shoulder Test example must not introduce unsupported concepts into unrelated sessions. For Completion with Integrity, preserve that surveillance drops as clarity increases. Never use generic directives like \\\"Run the test\\\".\\n4. Application: Describe the client-specific leadership application directly supported by the transcript. If unsupported, return an empty string \\\"\\\". Never use generic sign-offs or \\\"report back\\\" as application.\\n5. Source Timestamps: Every source timestamp must exactly match a timestamp present in the original transcript. Never invent timestamps.\\n\\nTranscript:\\n" + $('Validate Classification').item.json.dialogue_text + "\\n\\nReturn JSON with this exact schema:\\n{\\n  \\\"frameworks\\\": [\\n    {\\n      \\\"name\\\": \\\"Exact Framework Name\\\",\\n      \\\"definition\\\": \\\"Definition or empty string\\\",\\n      \\\"core_mechanism\\\": \\\"Exact diagnostic rule or mechanism\\\",\\n      \\\"application\\\": \\\"Client application or empty string\\\",\\n      \\\"source_timestamps\\\": [\\\"00:00:45\\\"]\\n    }\\n  ]\\n}",\n  format: 'json',\n  stream: false,\n  options: {\n    temperature: 0.0\n  }\n} }}`,
        options: { timeout: 90000 }
      },
      id: "9a4c53e7-4d8b-7b8d-8439-7b8d4f6c0012",
      name: "Ollama Framework Extractor",
      type: "n8n-nodes-base.httpRequest",
      typeVersion: 4.1,
      position: [2020, 320]
    },
    {
      parameters: {
        jsCode: `// Assemble all dual-stream chunks (1 framework + 3 voice) for current session
const session = $('Process Sessions Sequentially').item.json;
const rawOutput = $input.first().json.response;
const COACH_NAME = 'Dr. Sara Hegy';

// 1. Framework chunk extraction
let fwChunks = [];
try {
  const parsed = JSON.parse(rawOutput);
  const list = Array.isArray(parsed.frameworks) ? parsed.frameworks : [];
  for (const f of list) {
    const parts = [];
    if (f.name) parts.push('Framework: ' + f.name);
    if (f.definition) parts.push('Definition: ' + f.definition);
    if (f.core_mechanism) parts.push('Mechanism: ' + f.core_mechanism);
    if (f.application) parts.push('Application: ' + f.application);
    const content = parts.join('\\n');
    if (content.length > 0) {
      fwChunks.push({
        session_id: session.id,
        stream_type: 'framework',
        content: content,
        metadata: {
          framework_name: f.name || 'Coaching Principle',
          session_id: session.id,
          source_timestamps: Array.isArray(f.source_timestamps) ? f.source_timestamps : []
        }
      });
    }
  }
} catch (e) {}

if (fwChunks.length === 0) {
  fwChunks.push({
    session_id: session.id,
    stream_type: 'framework',
    content: 'Coaching Guidance for ' + session.title + ':\\n' + (session.classification?.summary || session.title),
    metadata: {
      framework_name: 'Coaching Principle',
      session_id: session.id,
      source_timestamps: []
    }
  });
}

// 2. Voice chunks extraction: Dr. Sara Hegy verbatim turns only
const transcript = session.transcript || [];
const voiceChunks = [];
for (const turn of transcript) {
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

// Combine all chunks for this session
const allSessionChunks = fwChunks.concat(voiceChunks);

// Emit each chunk as an individual item so n8n processes embeddings sequentially
return allSessionChunks.map((chunk, idx) => ({
  json: {
    ...chunk,
    chunk_index: idx,
    total_session_chunks: allSessionChunks.length
  }
}));`
      },
      id: "7b8d4f6c-8439-4d8b-9a4c-53e7f9e8a014",
      name: "Format Dual-Stream Chunks",
      type: "n8n-nodes-base.code",
      typeVersion: 2,
      position: [2260, 320]
    },
    {
      parameters: {
        method: "POST",
        url: "={{ $env.OLLAMA_BASE_URL || 'http://host.docker.internal:11434' }}/api/embeddings",
        sendBody: true,
        specifyBody: "json",
        jsonBody: `={{ {\n  model: $env.OLLAMA_EMBED_MODEL || 'bge-m3',\n  prompt: $json.content\n} }}`,
        options: { timeout: 60000 }
      },
      id: "53e7f9e8-8439-4d8b-9a4c-7b8d4f6c0016",
      name: "Ollama Chunk Embedder",
      type: "n8n-nodes-base.httpRequest",
      typeVersion: 4.1,
      position: [2500, 320]
    },
    {
      parameters: {
        jsCode: `// Validate & Assemble Complete Session Chunks Array
// Runs after all chunks of the current session have been embedded
const items = $input.all();
const session = $('Process Sessions Sequentially').item.json;
const sessionId = session.id;

if (!sessionId || typeof sessionId !== 'string' || sessionId.trim().length === 0) {
  throw new Error('CRITICAL VALIDATION FAILURE: Invalid or missing session ID');
}

// 1. Reconstruct Framework Chunk from the session's framework extraction
const rawFwOutput = $('Ollama Framework Extractor').item.json.response;
let fwChunks = [];
try {
  const parsed = JSON.parse(rawFwOutput);
  const list = Array.isArray(parsed.frameworks) ? parsed.frameworks : [];
  for (const f of list) {
    const parts = [];
    if (f.name) parts.push('Framework: ' + f.name);
    if (f.definition) parts.push('Definition: ' + f.definition);
    if (f.core_mechanism) parts.push('Mechanism: ' + f.core_mechanism);
    if (f.application) parts.push('Application: ' + f.application);
    const content = parts.join('\\n');
    if (content.length > 0) {
      fwChunks.push({
        session_id: sessionId,
        stream_type: 'framework',
        content: content,
        metadata: {
          framework_name: f.name || 'Coaching Principle',
          session_id: sessionId,
          source_timestamps: Array.isArray(f.source_timestamps) ? f.source_timestamps : []
        }
      });
    }
  }
} catch (e) {}

if (fwChunks.length === 0) {
  fwChunks.push({
    session_id: sessionId,
    stream_type: 'framework',
    content: 'Coaching Guidance for ' + session.title + ':\\n' + (session.classification?.summary || session.title),
    metadata: {
      framework_name: 'Coaching Principle',
      session_id: sessionId,
      source_timestamps: []
    }
  });
}

// 2. Reconstruct Voice Chunks: Dr. Sara Hegy verbatim turns only
const COACH_NAME = 'Dr. Sara Hegy';
const transcript = session.transcript || [];
const voiceChunks = [];
for (const turn of transcript) {
  if (turn.speaker === COACH_NAME) {
    voiceChunks.push({
      session_id: sessionId,
      stream_type: 'voice_sample',
      content: turn.text,
      metadata: {
        speaker: COACH_NAME,
        session_id: sessionId,
        source_timestamps: [turn.timestamp],
        char_count: turn.text.length,
        turn_count: 1
      }
    });
  }
}

const rawChunks = fwChunks.concat(voiceChunks);

// 3. Verify exact 1-to-1 match between raw chunks and embedded items
if (items.length !== rawChunks.length) {
  throw new Error('Embedding count mismatch for ' + sessionId + ': expected ' + rawChunks.length + ' embeddings, got ' + items.length);
}

// 4. Assemble and validate each chunk
const assembledChunks = [];
for (let i = 0; i < rawChunks.length; i++) {
  const rawChunk = rawChunks[i];
  const embData = items[i].json;
  const embedding = embData.embedding;

  if (!Array.isArray(embedding) || embedding.length !== 1024) {
    throw new Error('Chunk ' + i + ' embedding dimension invalid: expected 1024, got ' + (embedding ? embedding.length : 'null'));
  }
  for (let d = 0; d < 1024; d++) {
    if (typeof embedding[d] !== 'number' || !Number.isFinite(embedding[d])) {
      throw new Error('Chunk ' + i + ' embedding[' + d + '] is not a valid finite number.');
    }
  }

  if (rawChunk.stream_type === 'voice_sample') {
    if (rawChunk.metadata.speaker !== COACH_NAME) {
      throw new Error('Chunk ' + i + ' voice sample speaker is not ' + COACH_NAME);
    }
  }

  assembledChunks.push({
    session_id: sessionId,
    stream_type: rawChunk.stream_type,
    content: rawChunk.content,
    metadata: rawChunk.metadata,
    embedding: embedding
  });
}

if (assembledChunks.length === 0) {
  throw new Error('Validation failed for ' + sessionId + ': Combined chunks array is empty.');
}

const fwCount = assembledChunks.filter(c => c.stream_type === 'framework').length;
const voiceCount = assembledChunks.filter(c => c.stream_type === 'voice_sample').length;

return [{\n  json: {\n    session_id: sessionId,\n    chunk_count: assembledChunks.length,\n    framework_count: fwCount,\n    voice_count: voiceCount,\n    chunks: assembledChunks\n  }\n}];`
      },
      id: "6c4d8b9a-9a4c-4f6c-7b8d-53e7f9e8a021",
      name: "Validate & Assemble Chunks",
      type: "n8n-nodes-base.code",
      typeVersion: 2,
      position: [2740, 320]
    },
    {
      parameters: {
        operation: "executeQuery",
        query: "SELECT * FROM ingest_session_vault($1, $2::jsonb);",
        options: {
          queryReplacement: "={{ $json.session_id }}, {{ JSON.stringify($json.chunks) }}"
        }
      },
      id: "7b8d4f6c-8439-4d8b-9a4c-53e7f9e8a022",
      name: "Atomic Vault Replacement Function",
      type: "n8n-nodes-base.postgres",
      typeVersion: 2.4,
      position: [2980, 320],
      credentials: {
        postgres: {
          id: "3188",
          name: "Postgres account"
        }
      }
    }
  ],
  connections: {
    "When clicking ‘Execute workflow’": {
      main: [[{ node: "Read Transcripts File", type: "main", index: 0 }]]
    },
    "Read Transcripts File": {
      main: [[{ node: "Parse Transcripts Array", type: "main", index: 0 }]]
    },
    "Parse Transcripts Array": {
      main: [[{ node: "Process Sessions Sequentially", type: "main", index: 0 }]]
    },
    "Process Sessions Sequentially": {
      main: [
        [],
        [{ node: "Turn Sampler", type: "main", index: 0 }]
      ]
    },
    "Turn Sampler": {
      main: [[{ node: "Ollama Classifier", type: "main", index: 0 }]]
    },
    "Ollama Classifier": {
      main: [[{ node: "Validate Classification", type: "main", index: 0 }]]
    },
    "Validate Classification": {
      main: [[{ node: "Firewall Gate", type: "main", index: 0 }]]
    },
    "Firewall Gate": {
      main: [
        [{ node: "Ollama Framework Extractor", type: "main", index: 0 }],
        [{ node: "Format Rejected Record", type: "main", index: 0 }]
      ]
    },
    "Format Rejected Record": {
      main: [[{ node: "Transactional Archive Rejected", type: "main", index: 0 }]]
    },
    "Transactional Archive Rejected": {
      main: [[{ node: "Process Sessions Sequentially", type: "main", index: 0 }]]
    },
    "Ollama Framework Extractor": {
      main: [[{ node: "Format Dual-Stream Chunks", type: "main", index: 0 }]]
    },
    "Format Dual-Stream Chunks": {
      main: [[{ node: "Ollama Chunk Embedder", type: "main", index: 0 }]]
    },
    "Ollama Chunk Embedder": {
      main: [[{ node: "Validate & Assemble Chunks", type: "main", index: 0 }]]
    },
    "Validate & Assemble Chunks": {
      main: [[{ node: "Atomic Vault Replacement Function", type: "main", index: 0 }]]
    },
    "Atomic Vault Replacement Function": {
      main: [[{ node: "Process Sessions Sequentially", type: "main", index: 0 }]]
    }
  }
};

fs.writeFileSync('workflows/ingestion_firewall.json', JSON.stringify(workflow, null, 2));
console.log('Successfully generated workflows/ingestion_firewall.json');
