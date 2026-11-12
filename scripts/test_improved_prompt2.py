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
    
    prompt = f"""You are a meeting classifier. You must categorize this transcript into one of 4 categories:

CATEGORIES:
- "Client Coaching": Dr. Sara Hegy is coaching Mark or Elena on leadership, management, or communication.
- "Internal Operations": Team members (Oussama, Youssef) discuss technical work, webhooks, bugs, code, or databases. Dr. Sara Hegy is NOT present.
- "Sales Discovery": Sales rep and David Clark discuss retainer pricing, budget, costs, contracts, or pilots.
- "Other": Anything else.

TRANSCRIPT:
{dialogue}

TASK:
Determine:
1. Is this about software engineering / webhooks / database? -> "Internal Operations"
2. Is this about pricing / contract / pilot / budget? -> "Sales Discovery"
3. Is Dr. Sara Hegy coaching an executive? -> "Client Coaching"

Output JSON with your classification (confidence between 0.85 and 0.99):
{{
  "meeting_type": "<CHOOSE: Client Coaching | Internal Operations | Sales Discovery | Other>",
  "confidence_score": <FLOAT between 0.85 and 0.99>,
  "summary": "<1-2 sentences describing what happened>"
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
        print(f"=== {sid} PROMPT 2 OUTPUT ===")
        print(res["response"])
