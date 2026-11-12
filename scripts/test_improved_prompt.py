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
    
    prompt = f"""You are an expert meeting classification firewall for GenX Leadership Academy.
Classify the following transcript into exactly one meeting_type:

1. "Client Coaching": 1-on-1 executive coaching session between Dr. Sara Hegy and an external client discussing leadership, behavioral patterns, management, or organizational frameworks.
2. "Internal Operations": Internal company discussion between team members about software, webhooks, databases, code, technical bugs, or deployment releases.
3. "Sales Discovery": Commercial call between a sales representative and a prospective buyer discussing pricing, retainer fees, contract terms, pilot agreements, or budgets.
4. "Other": Any conversation that does not fit the above categories.

Rules:
- If the conversation is about technical bugs, database migrations, webhooks, or git branches, it is "Internal Operations".
- If the conversation is about pricing, retainer fees, budgets, or contracts, it is "Sales Discovery".
- If Dr. Sara Hegy is coaching a client on leadership or executive dilemmas, it is "Client Coaching".
- Provide a realistic confidence_score between 0.80 and 1.00 when the category is clear.

Transcript:
{dialogue}

Respond with valid JSON only in this exact format:
{{
  "meeting_type": "Client Coaching",
  "confidence_score": 0.95,
  "summary": "Concise summary of the meeting."
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
        print(f"=== {sid} IMPROVED OUTPUT ===")
        print(res["response"])
