import json
import urllib.request
import time
import subprocess

def embed_query(query_text):
    req_body = {
        "model": "bge-m3:latest",
        "prompt": query_text
    }
    data_bytes = json.dumps(req_body).encode('utf-8')
    req = urllib.request.Request(
        'http://localhost:11434/api/embeddings',
        data=data_bytes,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    return data.get('embedding')

def evaluate_similarities(query_text):
    vec = embed_query(query_text)
    vec_str = "[" + ",".join(str(x) for x in vec) + "]"
    
    sql = f"""
    SELECT json_agg(t) FROM (
        SELECT 
            id,
            session_id,
            stream_type,
            REGEXP_REPLACE(LEFT(content, 60), E'[\\r\\n]+', ' ', 'g') AS content_preview,
            ROUND((1 - (embedding <=> '{vec_str}'::vector))::numeric, 4) AS similarity
        FROM knowledge_vault
        ORDER BY similarity DESC
    ) t;
    """
    res = subprocess.run(
        ['docker', 'exec', 'genx-postgres', 'psql', '-U', 'genx', '-d', 'genx_rag', '-t', '-A', '-c', sql],
        capture_output=True, text=True, check=True
    )
    rows = json.loads(res.stdout.strip())
    top_fw = next((r for r in rows if r['stream_type'] == 'framework'), None)
    top_voice = next((r for r in rows if r['stream_type'] == 'voice_sample'), None)
    return {
        "query": query_text,
        "top_framework": top_fw,
        "top_voice": top_voice,
        "all_rows": rows
    }

def main():
    candidate_queries = [
        # TC-03 Candidates (Need Voice >= 0.65)
        {"tc": "TC-03", "query": "Look, Mark, is micromanagement really an ego problem or an information architecture breakdown?"},
        {"tc": "TC-03", "query": "How do top performers fail against ambiguous standards in our practice?"},
        
        # TC-04 Candidates (Need Framework >= 0.70 AND Voice >= 0.65)
        {"tc": "TC-04", "query": "How does an executive use the Table and Shoulder test when operational velocity outpaces direct reports?"},
        {"tc": "TC-04", "query": "How do top performers use the Completion with Integrity framework and binary exit criteria to eliminate micromanagement?"},
        
        # TC-06 Candidates (Need Voice >= 0.65 AND Framework < 0.70)
        {"tc": "TC-06", "query": "How does an executive protect cognitive bandwidth and let the architecture absorb ambiguity?"},
        {"tc": "TC-06", "query": "When you regulate your own state first, how do you give your team the safety to stabilize theirs?"},
        
        # TC-07 Candidate (Need Framework < 0.70 AND Voice < 0.65)
        {"tc": "TC-07", "query": "What is the optimal fertilizer ratio for growing hydroponic tomatoes in winter?"}
    ]
    
    print("=" * 80)
    print("SIMILARITY CALIBRATION EVALUATION FOR TC-03, TC-04, TC-06, TC-07")
    print("=" * 80)
    
    results = []
    for item in candidate_queries:
        tc = item["tc"]
        q = item["query"]
        print(f"\nEvaluating [{tc}]: \"{q}\"")
        eval_res = evaluate_similarities(q)
        fw = eval_res["top_framework"]
        vc = eval_res["top_voice"]
        
        fw_sim = fw["similarity"] if fw else 0.0
        vc_sim = vc["similarity"] if vc else 0.0
        
        fw_pass = fw_sim >= 0.70
        vc_pass = vc_sim >= 0.65
        
        print(f"  Top Framework: ID {fw['id']} ({fw['session_id']}) -> {fw_sim:.4f} (Threshold 0.70) -> {'PASS' if fw_pass else 'FAIL'}")
        print(f"  Top Voice:     ID {vc['id']} ({vc['session_id']}) -> {vc_sim:.4f} (Threshold 0.65) -> {'PASS' if vc_pass else 'FAIL'}")
        
        results.append({
            "test_case": tc,
            "query": q,
            "framework_similarity": fw_sim,
            "framework_chunk_id": fw['id'] if fw else None,
            "framework_qualifies": fw_pass,
            "voice_similarity": vc_sim,
            "voice_chunk_id": vc['id'] if vc else None,
            "voice_qualifies": vc_pass
        })
        
    with open("scripts/query_calibration_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nSaved calibration results to scripts/query_calibration_results.json")

if __name__ == "__main__":
    main()
