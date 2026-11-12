import json
import math
import hashlib

def run_stage5_preflight():
    print("=" * 70)
    print("STAGE 5: DATABASE INGESTION PREFLIGHT INSPECTION")
    print("=" * 70)

    # 1. Load stage4c_embedding_results.json
    with open('scripts/stage4c_embedding_results.json', 'r', encoding='utf-8') as f:
        emb_data = json.load(f)

    # 2. Load stage3 evaluation results (for rejected session metadata)
    with open('scripts/stage3_evaluation_results.json', 'r', encoding='utf-8') as f:
        stage3_data = {s['session_id']: s for s in json.load(f)}

    # 3. Load runtime fixture transcripts
    with open('workflows/runtime_ingestion_transcripts.json', 'r', encoding='utf-8') as f:
        fixture_transcripts = {s['id']: s for s in json.load(f)}

    # Verify Embedding Inputs
    fw_chunks = emb_data.get('framework_chunks', [])
    vc_chunks = emb_data.get('voice_chunks', [])
    total_embedded = len(fw_chunks) + len(vc_chunks)

    print(f"Total Framework Chunks in Stage 4C: {len(fw_chunks)}")
    print(f"Total Voice Chunks in Stage 4C:      {len(vc_chunks)}")
    print(f"Total Embedded Chunks:               {total_embedded}")

    assert len(fw_chunks) == 2, f"Expected 2 framework chunks, got {len(fw_chunks)}"
    assert len(vc_chunks) == 6, f"Expected 6 voice chunks, got {len(vc_chunks)}"
    assert total_embedded == 8, f"Expected 8 total embedded chunks, got {total_embedded}"

    all_chunks = fw_chunks + vc_chunks
    session_distribution = {}

    # Validate vector dimensions, numerics, and metadata for every chunk
    for idx, c in enumerate(all_chunks):
        s_id = c.get('session_id')
        st_type = c.get('stream_type')
        content = c.get('content')
        metadata = c.get('metadata')
        embedding = c.get('embedding')

        assert s_id in ['TEST-SES-101', 'TEST-SES-102'], f"Invalid session_id: {s_id}"
        assert st_type in ['framework', 'voice_sample'], f"Invalid stream_type: {st_type}"
        assert isinstance(content, str) and len(content.strip()) > 0, f"Empty content in chunk {idx}"
        assert isinstance(metadata, dict), f"Invalid metadata in chunk {idx}"
        assert isinstance(embedding, list), f"Embedding is not a list in chunk {idx}"
        assert len(embedding) == 1024, f"Dimension is {len(embedding)} != 1024 in chunk {idx}"

        for v in embedding:
            assert isinstance(v, (int, float)), f"Non-numeric vector element in chunk {idx}"
            assert not math.isnan(v), f"NaN vector element in chunk {idx}"
            assert not math.isinf(v), f"Inf vector element in chunk {idx}"

        if s_id not in session_distribution:
            session_distribution[s_id] = {'framework': 0, 'voice_sample': 0, 'chunks': []}
        session_distribution[s_id][st_type] += 1
        
        # Prepare chunk object formatted for ingest_test_session_vault
        session_distribution[s_id]['chunks'].append({
            'stream_type': st_type,
            'content': content,
            'metadata': metadata,
            'embedding': embedding
        })

    print(f"\nAccepted Session Distribution:")
    for s_id, dist in session_distribution.items():
        print(f"  {s_id}: {dist['framework']} framework, {dist['voice_sample']} voice_sample (Total: {len(dist['chunks'])})")
        assert dist['framework'] == 1, f"Expected 1 framework chunk for {s_id}"
        assert dist['voice_sample'] == 3, f"Expected 3 voice chunks for {s_id}"
        assert len(dist['chunks']) == 4, f"Expected 4 total chunks for {s_id}"

    # Verify Rejection Isolation
    all_embedded_session_ids = set([c['session_id'] for c in all_chunks])
    assert 'TEST-SES-103' not in all_embedded_session_ids
    assert 'TEST-SES-104' not in all_embedded_session_ids
    print("\nPASS: Rejection isolation confirmed. Zero embeddings exist for TEST-SES-103 or TEST-SES-104.")

    # Prepare Rejected Session Archival Parameters
    rejected_sessions_plan = []
    for rej_id in ['TEST-SES-103', 'TEST-SES-104']:
        st3 = stage3_data[rej_id]
        fx = fixture_transcripts[rej_id]
        raw_text = '\n'.join([f"{t['speaker']} [{t['timestamp']}]: {t['text']}" for t in fx['transcript']])

        rejected_sessions_plan.append({
            'session_id': rej_id,
            'meeting_type': st3['meeting_type'],
            'confidence_score': st3['confidence_score'],
            'summary': st3['summary'],
            'raw_transcript_len': len(raw_text),
            'rejection_reason': st3['rejection_reason'],
            'sql_call': f"SELECT * FROM archive_rejected_test_meeting('{rej_id}', '{st3['meeting_type']}', {st3['confidence_score']}, ...);"
        })
        print(f"  Rejected Session: {rej_id} ({st3['meeting_type']}, conf={st3['confidence_score']}) -> Reason: {st3['rejection_reason']}")

    # Build Preflight Report
    preflight_report = {
        'status': 'PASS',
        'inspection_timestamp': '2026-11-12T15:53:00Z',
        'accepted_sessions_vault_plan': {
            'target_table': 'knowledge_vault',
            'target_function': 'ingest_test_session_vault(p_session_id, p_chunks::jsonb)',
            'total_sessions': 2,
            'session_ids': ['TEST-SES-101', 'TEST-SES-102'],
            'total_records': 8,
            'records_by_stream': {
                'framework': 2,
                'voice_sample': 6
            },
            'records_by_session': {
                'TEST-SES-101': {'framework': 1, 'voice_sample': 3, 'total': 4},
                'TEST-SES-102': {'framework': 1, 'voice_sample': 3, 'total': 4}
            },
            'vector_dimension': 1024,
            'numeric_validity': '100% finite float (zero null, NaN, or Inf)',
            'atomic_replacement_mechanism': 'DELETE prior session records + INSERT in single transaction with advisory xact lock'
        },
        'rejected_sessions_archive_plan': {
            'target_table': 'rejected_meetings',
            'target_function': 'archive_rejected_test_meeting(p_session_id, p_meeting_type, p_confidence_score, p_summary, p_raw_transcript, p_rejection_reason)',
            'total_sessions': 2,
            'session_ids': ['TEST-SES-103', 'TEST-SES-104'],
            'sessions': rejected_sessions_plan,
            'has_embedding_column': False,
            'atomic_replacement_mechanism': 'DELETE prior session records + INSERT in single transaction with advisory xact lock'
        },
        'rejection_isolation_verification': {
            'verified': True,
            'excluded_from_vault': ['TEST-SES-103', 'TEST-SES-104'],
            'excluded_from_embeddings': ['TEST-SES-103', 'TEST-SES-104']
        },
        'database_mutations_executed': {
            'inserts': 0,
            'updates': 0,
            'deletes': 0,
            'truncate': 0,
            'function_calls': 0,
            'confirmation': 'Zero database writes occurred during preflight'
        }
    }

    with open('scripts/stage5_preflight_report.json', 'w', encoding='utf-8') as out_f:
        json.dump(preflight_report, out_f, indent=2)

    print("\nSaved preflight report to scripts/stage5_preflight_report.json")
    print(">>> STAGE 5 PREFLIGHT COMPLETE (ZERO DATABASE WRITES) <<<")

if __name__ == '__main__':
    run_stage5_preflight()
