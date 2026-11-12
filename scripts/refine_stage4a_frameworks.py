import json
import urllib.request
import time

def run_refined_framework_extraction():
    print("=" * 70)
    print("STAGE 4A REFINEMENT: GROUNDED FRAMEWORK EXTRACTION")
    print("=" * 70)

    with open('workflows/runtime_ingestion_transcripts.json', 'r', encoding='utf-8') as f:
        fixture = json.load(f)

    def get_dialogue_text(session):
        transcript = session.get('transcript', [])
        return '\n'.join([f"{t['speaker']} [{t['timestamp']}]: {t['text']}" for t in transcript])

    # Refined prompt adhering strictly to User's Grounding & Semantic Validation rules
    def build_refined_prompt(dialogue_text):
        return (
            "You are a precision coaching framework extractor for executive coaching sessions.\n\n"
            "Rules for Framework Extraction:\n"
            "1. Explicitly named frameworks: If Dr. Sara Hegy explicitly names a framework (e.g. 'framework called Completion with Integrity' or 'Table and Shoulder Test'), retain that exact name.\n"
            "2. Unnamed concepts: Do not invent names or represent general remarks, questions, or closing assignments as separate frameworks. Group related principles under the primary framework discussed.\n"
            "3. Grounded Definitions: The definition must state what the framework is based solely on the transcript. Never infer definitions from unrelated conversational remarks or closing instructions (such as 'Run the diagnosis tomorrow'). If no explicit definition is given beyond its core mechanism, leave definition empty \"\".\n"
            "4. Core Mechanism: State the exact diagnostic rule or operational mechanism directly stated in the text. Preserve exact meaning (e.g. if the transcript says 'surveillance drops to zero', do NOT claim it prioritizes surveillance).\n"
            "5. Application: Describe the concrete executive application directly discussed in the transcript. Do not invent hypothetical scenarios.\n"
            "6. Source Timestamps: List only timestamps where the concept, its mechanism, or its application was actively discussed.\n\n"
            "Transcript:\n" + dialogue_text + "\n\n"
            "Return valid JSON adhering strictly to this schema:\n"
            "{\n"
            "  \"frameworks\": [\n"
            "    {\n"
            "      \"name\": \"Exact Name or Descriptive Label\",\n"
            "      \"is_named_framework\": true,\n"
            "      \"definition\": \"Direct explanation from transcript, or empty if none\",\n"
            "      \"core_mechanism\": \"Exact diagnostic rule or mechanism from transcript\",\n"
            "      \"application\": \"Concrete application discussed in session\",\n"
            "      \"source_timestamps\": [\"00:00:00\"]\n"
            "    }\n"
            "  ]\n"
            "}"
        )

    sessions_to_test = [s for s in fixture if s['id'] in ['TEST-SES-101', 'TEST-SES-102']]
    results = []

    for s in sessions_to_test:
        s_id = s['id']
        print(f"\nEvaluating Refined Extraction on {s_id} ({s.get('title')})...")
        dialogue_text = get_dialogue_text(s)
        prompt = build_refined_prompt(dialogue_text)

        req_body = {
            "model": "llama3.2:1b",
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0
            }
        }

        start_time = time.time()
        req = urllib.request.Request(
            'http://localhost:11434/api/generate',
            data=json.dumps(req_body).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp_json = json.loads(resp.read().decode('utf-8'))
                raw_model_response = resp_json.get('response', '')
        except Exception as e:
            raw_model_response = f"ERROR: {e}"

        elapsed = time.time() - start_time
        print(f"Elapsed: {elapsed:.2f}s")
        print("Raw Response:\n" + raw_model_response.strip())

        parsed_json = None
        try:
            parsed_json = json.loads(raw_model_response)
        except Exception as e:
            print(f"JSON Parse Error: {e}")

        results.append({
            'session_id': s_id,
            'title': s.get('title'),
            'raw_model_response': raw_model_response,
            'parsed_json': parsed_json,
            'elapsed_sec': elapsed
        })

    with open('scripts/stage4a_refined_results.json', 'w', encoding='utf-8') as out_f:
        json.dump(results, out_f, indent=2)

    print("\nSaved refined results to scripts/stage4a_refined_results.json")

if __name__ == '__main__':
    run_refined_framework_extraction()
