import json
import urllib.request
import time

def run_fine_tuned_extraction():
    with open('workflows/runtime_ingestion_transcripts.json', 'r', encoding='utf-8') as f:
        fixture = json.load(f)

    def get_dialogue_text(session):
        transcript = session.get('transcript', [])
        return '\n'.join([f"{t['speaker']} [{t['timestamp']}]: {t['text']}" for t in transcript])

    def build_prompt(dialogue_text):
        return (
            "You are a precision coaching framework extractor for executive coaching transcripts.\n\n"
            "Extraction Rules:\n"
            "1. Framework Name: Retain the exact name of any explicitly named framework (e.g. 'Completion with Integrity', 'Table and Shoulder Test'). Set is_named_framework: true.\n"
            "2. Unnamed Concepts: Group related diagnostic rules and advice under the primary framework rather than splitting into separate artificial frameworks.\n"
            "3. Definition: What the framework is, strictly based on the transcript's conceptual explanation. Do not borrow conversational instructions or closing remarks.\n"
            "4. Core Mechanism: Detail the complete diagnostic rule, operational mechanism, and decision criteria discussed (e.g. how variables are isolated, questions asked, and structural vs capacity outcomes). Preserve original meaning precisely.\n"
            "5. Application: Describe how the executive client applies the framework to their immediate leadership situation. Do not substitute closing conversational remarks (e.g. 'report back tomorrow').\n"
            "6. Source Timestamps: List the timestamps where the framework, mechanism, and application occur.\n\n"
            "Transcript:\n" + dialogue_text + "\n\n"
            "Return valid JSON adhering strictly to this schema:\n"
            "{\n"
            "  \"frameworks\": [\n"
            "    {\n"
            "      \"name\": \"Exact Name\",\n"
            "      \"is_named_framework\": true,\n"
            "      \"definition\": \"Conceptual explanation from transcript\",\n"
            "      \"core_mechanism\": \"Complete diagnostic rule and decision criteria from transcript\",\n"
            "      \"application\": \"Client application to their leadership situation\",\n"
            "      \"source_timestamps\": [\"00:00:00\"]\n"
            "    }\n"
            "  ]\n"
            "}"
        )

    sessions = [s for s in fixture if s['id'] in ['TEST-SES-101', 'TEST-SES-102']]
    results = []

    for s in sessions:
        s_id = s['id']
        dialogue = get_dialogue_text(s)
        prompt = build_prompt(dialogue)

        req_body = {
            "model": "llama3.2:1b",
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.0}
        }

        req = urllib.request.Request(
            'http://localhost:11434/api/generate',
            data=json.dumps(req_body).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        t0 = time.time()
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            raw = data.get('response', '')
        elapsed = time.time() - t0

        parsed = json.loads(raw)
        results.append({
            'session_id': s_id,
            'title': s.get('title'),
            'raw_model_response': raw,
            'parsed_json': parsed,
            'elapsed_sec': elapsed
        })
        print(f"=== {s_id} ===")
        print(json.dumps(parsed, indent=2))

    with open('scripts/stage4a_refined_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

if __name__ == '__main__':
    run_fine_tuned_extraction()
