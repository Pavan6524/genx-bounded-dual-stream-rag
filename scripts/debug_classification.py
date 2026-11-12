import json
import urllib.request
import os

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

with open("data/mock_transcripts.json", "r") as f:
    mocks = json.load(f)

for s in mocks:
    sid = s["id"]
    turns = s["transcript"]
    dialogue = "\n".join([f"{t['speaker']} [{t['timestamp']}]: {t['text']}" for t in turns])
    classify_prompt = f"""Classify this meeting transcript into exactly one meeting_type:
- "Client Coaching" (executive or 1:1 leadership coaching session)
- "Internal Operations" (team internal sync, infrastructure, engineering)
- "Sales Discovery" (prospect call, pricing, contract negotiation)
- "Other"

Transcript:
{dialogue}

Return JSON ONLY with this schema:
{{
  "meeting_type": "...",
  "confidence_score": 0.00 to 1.00,
  "summary": "1-2 sentence summary"
}}"""

    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": "llama3.2:1b",
        "prompt": classify_prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0}
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print(f"=== {sid} RAW LLM OUTPUT ===")
        print(res["response"])
