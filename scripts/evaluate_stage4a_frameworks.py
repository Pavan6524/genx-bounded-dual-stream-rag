import json
import urllib.request
import time

def evaluate_framework_extraction():
    print("=" * 70)
    print("STAGE 4A: DUAL-STREAM FRAMEWORK EXTRACTION EVALUATION")
    print("=" * 70)

    # 1. Load fixture
    with open('workflows/runtime_ingestion_transcripts.json', 'r', encoding='utf-8') as f:
        fixture = json.load(f)

    # Read Stage 3 classification results to verify acceptance/rejection
    with open('scripts/stage3_evaluation_results.json', 'r', encoding='utf-8') as f:
        stage3_results = {r['session_id']: r for r in json.load(f)}

    # Turn Sampler simulation
    def get_dialogue_text(session):
        transcript = session.get('transcript', [])
        total_turns = len(transcript)
        sampled_turns = []
        if total_turns <= 60:
            for i, t in enumerate(transcript):
                sampled_turns.append({
                    'original_index': i,
                    'timestamp': t['timestamp'],
                    'speaker': t['speaker'],
                    'text': t['text']
                })
        else:
            first40 = [{'original_index': i, 'timestamp': t['timestamp'], 'speaker': t['speaker'], 'text': t['text']} for i, t in enumerate(transcript[:40])]
            last20_start = max(40, total_turns - 20)
            last20 = [{'original_index': last20_start + idx, 'timestamp': t['timestamp'], 'speaker': t['speaker'], 'text': t['text']} for idx, t in enumerate(transcript[last20_start:])]
            sampled_turns = first40 + [t for t in last20 if t['original_index'] >= 40]

        return '\n'.join([f"{t['speaker']} [{t['timestamp']}]: {t['text']}" for t in sampled_turns])

    # Exact prompt template from n8n node 'Ollama Framework Extractor'
    def build_framework_prompt(dialogue_text):
        return (
            "Extract substantive coaching frameworks, principles, diagnostic rules, and handoff mechanisms explicitly discussed in this transcript.\n"
            "Never invent concepts, names, definitions, or unsupported rules. Preserve source timestamps.\n\n"
            "Transcript:\n" + dialogue_text + "\n\n"
            "Return JSON with this schema:\n"
            "{\n"
            "  \"frameworks\": [\n"
            "    {\n"
            "      \"name\": \"Framework or Principle Name\",\n"
            "      \"core_mechanism\": \"Exact mechanism or diagnostic rule discussed\",\n"
            "      \"definition\": \"Definition or conceptual explanation\",\n"
            "      \"application\": \"How it is applied\",\n"
            "      \"source_timestamps\": [\"00:00:00\"]\n"
            "    }\n"
            "  ]\n"
            "}"
        )

    # Exact formatting logic from n8n node 'Format Framework Chunks'
    def format_framework_chunks(raw_output, session):
        chunks = []
        try:
            parsed = json.loads(raw_output)
            framework_list = parsed.get('frameworks') if isinstance(parsed, dict) and isinstance(parsed.get('frameworks'), list) else []
            for f in framework_list:
                parts = []
                if f.get('name'):
                    parts.append(f"Framework: {f.get('name')}")
                if f.get('definition'):
                    parts.append(f"Definition: {f.get('definition')}")
                if f.get('core_mechanism'):
                    parts.append(f"Mechanism: {f.get('core_mechanism')}")
                if f.get('application'):
                    parts.append(f"Application: {f.get('application')}")

                content = '\n'.join(parts)
                if len(content) > 0:
                    chunks.append({
                        'session_id': session['id'],
                        'stream_type': 'framework',
                        'content': content,
                        'metadata': {
                            'framework_name': f.get('name') or 'Coaching Principle',
                            'session_id': session['id'],
                            'source_timestamps': f.get('source_timestamps') if isinstance(f.get('source_timestamps'), list) else []
                        }
                    })
        except Exception as e:
            print(f"Error parsing framework JSON: {e}")

        # Fallback: if no formal frameworks were returned, extract substantive rules directly from summary
        if len(chunks) == 0:
            chunks.append({
                'session_id': session['id'],
                'stream_type': 'framework',
                'content': f"Coaching Guidance for {session.get('title')}:\n{session.get('summary', '')}",
                'metadata': {
                    'framework_name': 'Coaching Summary',
                    'session_id': session['id'],
                    'source_timestamps': []
                }
            })

        return chunks

    results = []

    for idx, session in enumerate(fixture):
        s_id = session['id']
        st3 = stage3_results.get(s_id, {})
        is_accepted = st3.get('is_accepted', False)

        print(f"\n--- Processing Session {idx+1}/4: {s_id} ---")
        print(f"Stage 3 Status: is_accepted={is_accepted} ({st3.get('meeting_type')})")

        if not is_accepted:
            print(f"REJECTION ISOLATION ENFORCED: {s_id} is rejected. Skipping framework extraction.")
            results.append({
                'session_id': s_id,
                'status': 'SKIPPED_REJECTED',
                'meeting_type': st3.get('meeting_type'),
                'framework_chunks': []
            })
            continue

        dialogue_text = get_dialogue_text(session)
        prompt = build_framework_prompt(dialogue_text)

        req_body = {
            "model": "llama3.2:1b",
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0
            }
        }

        data_bytes = json.dumps(req_body).encode('utf-8')
        req = urllib.request.Request(
            'http://localhost:11434/api/generate',
            data=data_bytes,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        start_time = time.time()
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp_json = json.loads(resp.read().decode('utf-8'))
                raw_model_response = resp_json.get('response', '')
        except Exception as e:
            print(f"Error calling Ollama for {s_id}: {e}")
            raw_model_response = f"ERROR: {e}"

        elapsed = time.time() - start_time
        print(f"Inference elapsed time: {elapsed:.2f}s")
        print(f"Raw Model Response:\n{raw_model_response.strip()}")

        # Parse JSON
        parsed_json = None
        try:
            parsed_json = json.loads(raw_model_response)
        except Exception as e:
            print(f"JSON Parse Error: {e}")

        # Format chunks
        formatted_chunks = format_framework_chunks(raw_model_response, session)

        res_entry = {
            'session_id': s_id,
            'status': 'EXTRACTED',
            'raw_model_response': raw_model_response,
            'parsed_json': parsed_json,
            'chunk_count': len(formatted_chunks),
            'framework_chunks': formatted_chunks,
            'elapsed_sec': elapsed
        }
        results.append(res_entry)

        print(f"\nExtracted Framework Chunks Count: {len(formatted_chunks)}")
        for c_idx, c in enumerate(formatted_chunks):
            print(f"  [Chunk {c_idx+1}] Stream: {c['stream_type']}")
            print(f"    Framework Name: {c['metadata']['framework_name']}")
            print(f"    Source Timestamps: {c['metadata']['source_timestamps']}")
            print(f"    Content Preview:\n    " + c['content'].replace('\n', '\n    '))

    # Save to file
    with open('scripts/stage4a_framework_results.json', 'w', encoding='utf-8') as out_f:
        json.dump(results, out_f, indent=2)

    print("\nSaved framework results to scripts/stage4a_framework_results.json")

if __name__ == '__main__':
    evaluate_framework_extraction()
