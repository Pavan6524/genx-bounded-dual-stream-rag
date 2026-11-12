import json
import os
import sys
import urllib.request
import urllib.error

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

def call_ollama_generate(model, prompt, format_json=True):
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0}
    }
    if format_json:
        payload["format"] = "json"
        
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res["response"]

def call_ollama_embed(model, text):
    url = f"{OLLAMA_URL}/api/embeddings"
    payload = {
        "model": model,
        "prompt": text
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res["embedding"]

if __name__ == "__main__":
    print(f"Connecting to Ollama at {OLLAMA_URL}...")
    try:
        # Check models
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m["name"] for m in data.get("models", [])]
            print(f"Available Ollama models: {models}")
    except Exception as e:
        print(f"ERROR connecting to Ollama: {e}")
        sys.exit(1)
        
    # Test embedding dimension
    print("Testing bge-m3 embedding...")
    emb = call_ollama_embed("bge-m3", "Test coaching phrase")
    print(f"bge-m3 embedding dimension: {len(emb)}")
    assert len(emb) == 1024, f"Expected 1024, got {len(emb)}"
    
    # Test llama3.2:1b classification on a sample text
    print("Testing llama3.2:1b structured classification...")
    sample_prompt = """Classify this meeting transcript into exactly one meeting_type:
- "Client Coaching" (executive or 1:1 leadership coaching session)
- "Internal Operations" (team internal sync, infrastructure, engineering)
- "Sales Discovery" (prospect call, pricing, contract negotiation)
- "Other"

Transcript:
Dr. Sara Hegy: In our practice, we use a framework called Completion with Integrity.
Mark D.: That hits home. How do I define exit criteria?

Return JSON ONLY with this exact schema:
{
  "meeting_type": "Client Coaching",
  "confidence_score": 0.95,
  "summary": "1-2 sentence summary"
}"""
    llm_resp = call_ollama_generate("llama3.2:1b", sample_prompt, format_json=True)
    print(f"Classification test response: {llm_resp}")
    parsed = json.loads(llm_resp)
    print(f"Parsed meeting_type: {parsed.get('meeting_type')}, confidence: {parsed.get('confidence_score')}")
    print("Ollama connection and models verified successfully!")
