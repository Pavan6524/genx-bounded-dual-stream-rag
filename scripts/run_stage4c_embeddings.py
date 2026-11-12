import json
import urllib.request
import time
import math

def run_embedding_generation():
    print("=" * 70)
    print("STAGE 4C: DUAL-STREAM EMBEDDING GENERATION (bge-m3:latest)")
    print("=" * 70)

    # 1. Inspect and load Framework chunks (Stage 4A refined)
    with open('scripts/stage4a_refined_results.json', 'r', encoding='utf-8') as f:
        stage4a_data = json.load(f)

    framework_chunks = []
    for s in stage4a_data:
        s_id = s['session_id']
        parsed = s['parsed_json']
        f_list = parsed.get('frameworks', []) if isinstance(parsed, dict) else []
        for f in f_list:
            parts = []
            if f.get('name'):
                parts.append(f"Framework: {f.get('name')}")
            if f.get('definition'):
                parts.append(f"Definition: {f.get('definition')}")
            if f.get('core_mechanism'):
                parts.append(f"Mechanism: {f.get('core_mechanism')}")
            if f.get('application'):
                parts.append(f"Application: {f.get('application')}")

            content = '\n'.join(parts)
            if len(content) > 0:
                framework_chunks.append({
                    'session_id': s_id,
                    'stream_type': 'framework',
                    'content': content,
                    'metadata': {
                        'framework_name': f.get('name') or 'Coaching Principle',
                        'session_id': s_id,
                        'source_timestamps': f.get('source_timestamps', [])
                    }
                })

    print(f"Total Framework Chunks to Embed: {len(framework_chunks)}")
    for i, fc in enumerate(framework_chunks):
        print(f"  [Framework {i+1}] Session: {fc['session_id']} | Name: {fc['metadata']['framework_name']} | Chars: {len(fc['content'])}")

    # 2. Inspect and load Voice chunks (Stage 4B)
    with open('scripts/stage4b_voice_results.json', 'r', encoding='utf-8') as f:
        stage4b_data = json.load(f)

    voice_chunks = []
    for s in stage4b_data:
        s_id = s['session_id']
        v_list = s.get('voice_chunks', [])
        for vc in v_list:
            voice_chunks.append(vc)

    print(f"\nTotal Voice Chunks to Embed: {len(voice_chunks)}")
    for i, vc in enumerate(voice_chunks):
        print(f"  [Voice {i+1}] Session: {vc['session_id']} | Timestamps: {vc['metadata']['source_timestamps']} | Chars: {len(vc['content'])}")

    # Embedding function calling Ollama bge-m3 sequentially
    def get_embedding(text, chunk_desc):
        req_body = {
            "model": "bge-m3:latest",
            "prompt": text
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
            data = json.loads(resp.read().decode('utf-8'))
        elapsed = time.time() - t0
        emb = data.get('embedding')
        return emb, elapsed

    def validate_embedding(emb):
        if not isinstance(emb, list):
            return False, "Embedding is not a list"
        if len(emb) != 1024:
            return False, f"Embedding dimension is {len(emb)}, expected 1024"
        for v in emb:
            if not isinstance(v, (int, float)):
                return False, f"Embedding element is not numeric: {type(v)}"
            if math.isnan(v) or math.isinf(v):
                return False, "Embedding contains NaN or Inf"
        return True, "Valid 1024-d float vector"

    # Process Framework Stream
    embedded_framework_chunks = []
    print("\n--- Generating Framework Embeddings ---")
    fw_latencies = []
    for i, fc in enumerate(framework_chunks):
        desc = f"Framework Chunk {i+1} ({fc['session_id']}: {fc['metadata']['framework_name']})"
        emb, lat = get_embedding(fc['content'], desc)
        fw_latencies.append(lat)
        is_valid, msg = validate_embedding(emb)
        print(f"  {desc} -> Latency: {lat:.2f}s | Dim: {len(emb) if emb else 0} | Valid: {is_valid} ({msg})")
        assert is_valid, f"Invalid embedding for {desc}: {msg}"
        embedded_framework_chunks.append({
            'session_id': fc['session_id'],
            'stream_type': 'framework',
            'content': fc['content'],
            'metadata': fc['metadata'],
            'embedding': emb,
            'embedding_dim': len(emb),
            'latency_sec': lat
        })

    # Process Voice Stream
    embedded_voice_chunks = []
    print("\n--- Generating Voice Embeddings ---")
    vc_latencies = []
    for i, vc in enumerate(voice_chunks):
        desc = f"Voice Chunk {i+1} ({vc['session_id']}: {vc['metadata']['source_timestamps']})"
        emb, lat = get_embedding(vc['content'], desc)
        vc_latencies.append(lat)
        is_valid, msg = validate_embedding(emb)
        print(f"  {desc} -> Latency: {lat:.2f}s | Dim: {len(emb) if emb else 0} | Valid: {is_valid} ({msg})")
        assert is_valid, f"Invalid embedding for {desc}: {msg}"
        embedded_voice_chunks.append({
            'session_id': vc['session_id'],
            'stream_type': 'voice_sample',
            'content': vc['content'],
            'metadata': vc['metadata'],
            'embedding': emb,
            'embedding_dim': len(emb),
            'latency_sec': lat
        })

    # Verify no rejected sessions were processed
    embedded_sessions = set([c['session_id'] for c in embedded_framework_chunks] + [c['session_id'] for c in embedded_voice_chunks])
    print(f"\nEmbedded sessions: {embedded_sessions}")
    assert 'TEST-SES-103' not in embedded_sessions, "CRITICAL: Rejected session TEST-SES-103 received embedding!"
    assert 'TEST-SES-104' not in embedded_sessions, "CRITICAL: Rejected session TEST-SES-104 received embedding!"
    print("PASS: Rejection isolation confirmed. Zero embeddings generated for TEST-SES-103 or TEST-SES-104.")

    results = {
        'model': 'bge-m3:latest',
        'endpoint': 'POST /api/embeddings',
        'total_framework_chunks': len(embedded_framework_chunks),
        'total_voice_chunks': len(embedded_voice_chunks),
        'total_embedded_chunks': len(embedded_framework_chunks) + len(embedded_voice_chunks),
        'embedding_dimension': 1024,
        'framework_latencies_sec': fw_latencies,
        'voice_latencies_sec': vc_latencies,
        'framework_chunks': embedded_framework_chunks,
        'voice_chunks': embedded_voice_chunks
    }

    # Save to file
    with open('scripts/stage4c_embedding_results.json', 'w', encoding='utf-8') as out_f:
        json.dump(results, out_f, indent=2)

    print("\nSuccessfully saved embedding results to scripts/stage4c_embedding_results.json")

if __name__ == '__main__':
    run_embedding_generation()
