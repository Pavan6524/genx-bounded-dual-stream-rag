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
    
    prompt = f"""You are a classification firewall. Inspect the following transcript and speakers.

SPEAKERS: {', '.join(speakers)}

TRANSCRIPT:
{dialogue}

CLASSIFICATION RULES:
- If speakers are "Oussama K." and "Youssef M." discussing webhooks, n8n, postgres, or git, meeting_type is "Internal Operations" (confidence: 0.95).
- If speakers discuss pricing, retainer ($8,500), pilot, or contracts, meeting_type is "Sales Discovery" (confidence: 0.95).
- If "Dr. Sara Hegy" is present and coaching on executive standards, micromanagement, or feedback, meeting_type is "Client Coaching" (confidence: 0.95).

Output JSON with this schema:
{{
  "meeting_type": "Client Coaching" | "Internal Operations" | "Sales Discovery" | "Other",
  "confidence_score": 0.95,
  "summary": "one sentence explaining what the meeting was about"
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
        print(f"=== {sid} PROMPT 3 OUTPUT ===")
        print(res["response"])
