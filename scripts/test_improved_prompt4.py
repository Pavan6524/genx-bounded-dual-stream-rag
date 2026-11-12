import json
import urllib.request
import os

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

with open("data/mock_transcripts.json", "r") as f:
    mocks = json.load(f)

for s in mocks:
    sid = s["id"]
    turns = s["transcript"]
    dialogue = "\n".join([f"{t['speaker']}: {t['text']}" for t in turns])
    speakers = list(set(t["speaker"] for t in turns))
    
    prompt = f"""You are a meeting classifier.

Transcript:
{dialogue}

Instructions:
1. Summarize the meeting in 1 sentence.
2. Select meeting_type from this list:
   - "Internal Operations" if discussing software, bugs, webhooks, or database.
   - "Sales Discovery" if discussing pricing, retainer, budget, or sales contract.
   - "Client Coaching" if Dr. Sara Hegy is coaching a client on leadership.
   - "Other" if none of the above.
3. Assign confidence_score as a number between 0.85 and 0.99.

Output valid JSON only with keys "summary", "meeting_type", and "confidence_score":
{{
  "summary": "...",
  "meeting_type": "...",
  "confidence_score": 0.95
}}"""

    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": "llama3.2:1b",
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0}
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print(f"=== {sid} PROMPT 4 OUTPUT ===")
        print(res["response"])
