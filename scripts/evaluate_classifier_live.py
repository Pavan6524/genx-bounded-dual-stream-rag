import json
import urllib.request
import urllib.error
import time

def run_classifier_evaluation():
    print("=" * 70)
    print("PHASE 2: LIVE OLLAMA CLASSIFIER EVALUATION ON TEST FIXTURE")
    print("=" * 70)

    # 1. Load fixture
    with open('workflows/runtime_ingestion_transcripts.json', 'r', encoding='utf-8') as f:
        fixture = json.load(f)

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

    # Exact prompt template from n8n node 'Ollama Classifier'
    def build_prompt(dialogue_text):
        return (
            "You are an expert meeting classification firewall for GenX Leadership Academy.\n\n"
            "Transcript:\n" + dialogue_text + "\n\n"
            "Classification Rules:\n"
            "1. \"Internal Operations\" (reject): Discussions about technical infrastructure, code, bugs, webhooks, database migrations, or git. Dr. Sara Hegy is absent.\n"
            "2. \"Sales Discovery\" (reject): Sales Rep or commercial discussions about pricing, retainer fees ($8,500), budgets, contract terms, or pilot proposals. Dr. Sara Hegy is absent.\n"
            "3. \"Client Coaching\" (accept): 1-on-1 executive coaching sessions where Dr. Sara Hegy is present and coaching an executive client (e.g. Mark D. or Elena R.) on leadership, management, or executive feedback. If Dr. Sara Hegy is absent, this can NEVER be Client Coaching.\n"
            "4. \"Other\" (reject): Any meeting that does not match the above.\n\n"
            "Instructions:\n"
            "- Write a 1-sentence summary first.\n"
            "- Choose the exact meeting_type matching the rules above.\n"
            "- Provide a numeric confidence_score between 0.0 and 1.0 reflecting your certainty.\n\n"
            "Output valid JSON with keys \"summary\", \"meeting_type\", and \"confidence_score\":\n"
            "{\n"
            "  \"summary\": \"...\",\n"
            "  \"meeting_type\": \"...\",\n"
            "  \"confidence_score\": 0.95\n"
            "}"
        )

    # Exact firewall validation logic from n8n node 'Validate Classification'
    def validate_classification(raw_output, session):
        valid_meeting_types = ['Client Coaching', 'Internal Operations', 'Sales Discovery', 'Other']
        
        parsed = None
        try:
            parsed = json.loads(raw_output)
        except Exception as e:
            return {
                'meeting_type': 'Other',
                'confidence_score': 0.0,
                'summary': 'Malformed classification JSON from LLM',
                'is_accepted': False,
                'rejection_reason': f"Malformed classification JSON output: {str(e)}",
                'parsed_json': None
            }

        if not parsed or not isinstance(parsed, dict):
            return {
                'meeting_type': 'Other',
                'confidence_score': 0.0,
                'summary': 'Classification output is not a JSON object',
                'is_accepted': False,
                'rejection_reason': 'Classification output is not a JSON object',
                'parsed_json': parsed
            }

        meeting_type = parsed.get('meeting_type')
        try:
            confidence_score = float(parsed.get('confidence_score'))
        except (ValueError, TypeError):
            confidence_score = float('nan')
        
        summary = parsed.get('summary') if isinstance(parsed.get('summary'), str) else ''

        if meeting_type not in valid_meeting_types:
            return {
                'meeting_type': 'Other',
                'confidence_score': 0.0,
                'summary': summary,
                'is_accepted': False,
                'rejection_reason': f"Invalid meeting_type: '{meeting_type}'",
                'parsed_json': parsed
            }

        import math
        if math.isnan(confidence_score) or confidence_score < 0.0 or confidence_score > 1.0:
            return {
                'meeting_type': meeting_type,
                'confidence_score': 0.0,
                'summary': summary,
                'is_accepted': False,
                'rejection_reason': f"Invalid confidence_score: '{parsed.get('confidence_score')}'",
                'parsed_json': parsed
            }

        if meeting_type != 'Client Coaching':
            return {
                'meeting_type': meeting_type,
                'confidence_score': confidence_score,
                'summary': summary,
                'is_accepted': False,
                'rejection_reason': f"Non-coaching meeting type: {meeting_type}",
                'parsed_json': parsed
            }

        if confidence_score < 0.80:
            return {
                'meeting_type': meeting_type,
                'confidence_score': confidence_score,
                'summary': summary,
                'is_accepted': False,
                'rejection_reason': f"Low confidence: {confidence_score:.2f} < 0.80 threshold",
                'parsed_json': parsed
            }

        return {
            'meeting_type': meeting_type,
            'confidence_score': confidence_score,
            'summary': summary,
            'is_accepted': True,
            'rejection_reason': None,
            'parsed_json': parsed
        }

    results = []
    
    # Process sequentially to respect 8GB RAM
    for idx, session in enumerate(fixture):
        s_id = session['id']
        print(f"\n--- Evaluating Session {idx+1}/{len(fixture)}: {s_id} ---")
        dialogue_text = get_dialogue_text(session)
        prompt = build_prompt(dialogue_text)
        
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
        print(f"Raw Model Response: {raw_model_response.strip()}")

        val = validate_classification(raw_model_response, session)
        
        item_res = {
            'session_id': s_id,
            'raw_model_response': raw_model_response,
            'parsed_json': val['parsed_json'],
            'meeting_type': val['meeting_type'],
            'confidence_score': val['confidence_score'],
            'summary': val['summary'],
            'is_accepted': val['is_accepted'],
            'rejection_reason': val['rejection_reason'],
            'elapsed_sec': elapsed
        }
        results.append(item_res)

        print(f"  Parsed meeting_type:   {val['meeting_type']}")
        print(f"  Parsed confidence:     {val['confidence_score']}")
        print(f"  Parsed summary:        {val['summary']}")
        print(f"  Firewall is_accepted:  {val['is_accepted']}")
        print(f"  Rejection Reason:      {val['rejection_reason']}")

    # Save results to scratch
    with open('scripts/stage3_evaluation_results.json', 'w', encoding='utf-8') as out_f:
        json.dump(results, out_f, indent=2)

    print("\nSaved evaluation results to scripts/stage3_evaluation_results.json")

if __name__ == '__main__':
    run_classifier_evaluation()
