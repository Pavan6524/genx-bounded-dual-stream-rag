import json
import urllib.request
import time
import math
import subprocess
import os

def run_measurement():
    print("=" * 70)
    print("TASK 4: CANDIDATE QUERY 1 SIMILARITY MEASUREMENT")
    print("=" * 70)

    target_query = "How does an executive use Completion with Integrity and binary exit criteria to eliminate micromanagement?"
    print(f"Target Query: {target_query}\n")

    cache_file = "scripts/candidate_query_1_embedding.json"
    embedding = None
    elapsed = 0.0

    if os.path.exists(cache_file):
        print(f"Loading cached embedding from {cache_file}...")
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            embedding = data.get("embedding")
            elapsed = data.get("elapsed", 0.0)
    else:
        # Generate exactly one embedding via Ollama bge-m3:latest
        req_body = {
            "model": "bge-m3:latest",
            "prompt": target_query
        }
        data_bytes = json.dumps(req_body).encode('utf-8')
        req = urllib.request.Request(
            'http://localhost:11434/api/embeddings',
            data=data_bytes,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        t0 = time.time()
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp_data = json.loads(resp.read().decode('utf-8'))
        elapsed = time.time() - t0

        embedding = resp_data.get('embedding')
        print(f"Embedding generated in {elapsed:.2f}s")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"query": target_query, "embedding": embedding, "elapsed": elapsed}, f)

    # 2. Verify vector properties
    assert isinstance(embedding, list), "Embedding is not a list"
    assert len(embedding) == 1024, f"Expected 1024 dimensions, got {len(embedding)}"
    for idx, v in enumerate(embedding):
        assert isinstance(v, (int, float)), f"Element {idx} is not numeric"
        assert not (math.isnan(v) or math.isinf(v)), f"Element {idx} is NaN or Inf"
    print("Vector validation: PASS (1024 finite numeric dimensions)\n")

    # Format vector string for pgvector
    vector_str = "[" + ",".join(str(x) for x in embedding) + "]"

    # 3. Read-only SQL Cosine Similarity query against knowledge_vault using json_agg for safe serialization
    sql_query = f"""
    SELECT json_agg(t) FROM (
        SELECT 
            id,
            session_id,
            stream_type,
            REGEXP_REPLACE(LEFT(content, 60), E'[\\r\\n]+', ' ', 'g') AS content_preview,
            ROUND((1 - (embedding <=> '{vector_str}'::vector))::numeric, 4) AS similarity
        FROM knowledge_vault
        ORDER BY similarity DESC
    ) t;
    """

    res = subprocess.run(
        ['docker', 'exec', 'genx-postgres', 'psql', '-U', 'genx', '-d', 'genx_rag', '-t', '-A', '-c', sql_query],
        capture_output=True, text=True, check=True
    )

    rows = json.loads(res.stdout.strip())

    print(f"Evaluated all {len(rows)} chunks against Candidate Query 1:\n")
    print(f"{'ID':<4} | {'Session':<14} | {'Stream Type':<14} | {'Similarity':<10} | {'Preview'}")
    print("-" * 80)
    for r in rows:
        print(f"{r['id']:<4} | {r['session_id']:<14} | {r['stream_type']:<14} | {r['similarity']:<10.4f} | {r['content_preview']}...")

    # 4. Gating threshold analysis
    framework_threshold = 0.70
    voice_threshold = 0.65

    top_framework = next((r for r in rows if r["stream_type"] == "framework"), None)
    top_voice = next((r for r in rows if r["stream_type"] == "voice_sample"), None)

    fw_pass = top_framework["similarity"] >= framework_threshold if top_framework else False
    voice_pass = top_voice["similarity"] >= voice_threshold if top_voice else False

    print("\n" + "=" * 70)
    print("THRESHOLD GATING EVALUATION")
    print("=" * 70)
    print(f"Top Framework Chunk: ID {top_framework['id']} ({top_framework['session_id']}) -> Similarity: {top_framework['similarity']:.4f} (Threshold: {framework_threshold:.2f}) -> {'QUALIFIES (PASS)' if fw_pass else 'FAILS'}")
    print(f"Top Voice Chunk:     ID {top_voice['id']} ({top_voice['session_id']}) -> Similarity: {top_voice['similarity']:.4f} (Threshold: {voice_threshold:.2f}) -> {'QUALIFIES (PASS)' if voice_pass else 'FAILS'}")

    report = {
        "stage": "Task 4 — Candidate Query 1 Similarity Measurement",
        "query": target_query,
        "embedding_model": "bge-m3:latest",
        "embedding_dimensions": len(embedding),
        "embedding_elapsed_sec": round(elapsed, 3),
        "framework_threshold": framework_threshold,
        "voice_threshold": voice_threshold,
        "total_chunks_evaluated": len(rows),
        "all_chunks_ranked": rows,
        "top_framework_chunk": top_framework,
        "top_framework_qualifies": fw_pass,
        "top_voice_chunk": top_voice,
        "top_voice_qualifies": voice_pass,
        "overall_gating_status": "QUALIFIES_FOR_POSITIVE_RETRIEVAL" if (fw_pass or voice_pass) else "BLOCKED_BY_HARD_GATE"
    }

    with open("scripts/candidate_query_1_similarity_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nSaved structured measurement report to scripts/candidate_query_1_similarity_report.json")
    print(f"Overall Gating Result: {report['overall_gating_status']}")

if __name__ == "__main__":
    run_measurement()
