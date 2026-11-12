import json
import os

def evaluate_voice_extraction():
    print("=" * 70)
    print("STAGE 4B: DUAL-STREAM VOICE EXTRACTION EVALUATION")
    print("=" * 70)

    # 1. Load fixture
    with open('workflows/runtime_ingestion_transcripts.json', 'r', encoding='utf-8') as f:
        fixture = json.load(f)

    # Load stage 3 results for acceptance/rejection status
    with open('scripts/stage3_evaluation_results.json', 'r', encoding='utf-8') as f:
        stage3_results = {r['session_id']: r for r in json.load(f)}

    COACH_NAME = 'Dr. Sara Hegy'

    def extract_voice_stream(session):
        transcript = session.get('transcript', [])
        consecutive_groups = []
        current_group = []

        for turn in transcript:
            if turn.get('speaker') == COACH_NAME:
                current_group.append(turn)
            else:
                if len(current_group) > 0:
                    consecutive_groups.append(current_group)
                    current_group = []

        if len(current_group) > 0:
            consecutive_groups.append(current_group)

        chunks = []
        for group in consecutive_groups:
            if len(group) == 1:
                t = group[0]
                chunks.append({
                    'session_id': session['id'],
                    'stream_type': 'voice_sample',
                    'content': t['text'],
                    'metadata': {
                        'speaker': COACH_NAME,
                        'session_id': session['id'],
                        'source_timestamps': [t['timestamp']],
                        'char_count': len(t['text']),
                        'turn_count': 1
                    }
                })
            else:
                combined_text = []
                combined_timestamps = []
                current_len = 0
                for t in group:
                    added_len = len(t['text']) + (1 if len(combined_text) > 0 else 0)
                    if current_len + added_len <= 700 or len(combined_text) == 0:
                        combined_text.append(t['text'])
                        combined_timestamps.append(t['timestamp'])
                        current_len += added_len
                    else:
                        c_str = '\n'.join(combined_text)
                        chunks.append({
                            'session_id': session['id'],
                            'stream_type': 'voice_sample',
                            'content': c_str,
                            'metadata': {
                                'speaker': COACH_NAME,
                                'session_id': session['id'],
                                'source_timestamps': combined_timestamps,
                                'char_count': len(c_str),
                                'turn_count': len(combined_text)
                            }
                        })
                        combined_text = [t['text']]
                        combined_timestamps = [t['timestamp']]
                        current_len = len(t['text'])
                if len(combined_text) > 0:
                    c_str = '\n'.join(combined_text)
                    chunks.append({
                        'session_id': session['id'],
                        'stream_type': 'voice_sample',
                        'content': c_str,
                        'metadata': {
                            'speaker': COACH_NAME,
                            'session_id': session['id'],
                            'source_timestamps': combined_timestamps,
                            'char_count': len(c_str),
                            'turn_count': len(combined_text)
                        }
                    })
        return chunks

    results = []

    for idx, session in enumerate(fixture):
        s_id = session['id']
        st3 = stage3_results.get(s_id, {})
        is_accepted = st3.get('is_accepted', False)

        print(f"\n--- Processing Session {idx+1}/4: {s_id} ({session.get('title')}) ---")
        print(f"Stage 3 Status: is_accepted={is_accepted} ({st3.get('meeting_type')})")

        if not is_accepted:
            print(f"REJECTION ISOLATION ENFORCED: {s_id} is rejected. Skipping voice extraction.")
            results.append({
                'session_id': s_id,
                'status': 'SKIPPED_REJECTED',
                'meeting_type': st3.get('meeting_type'),
                'voice_chunks': []
            })
            continue

        chunks = extract_voice_stream(session)
        print(f"Extracted Voice Chunks Count: {len(chunks)}")

        for c_idx, c in enumerate(chunks):
            print(f"\n  [Chunk {c_idx+1}]")
            print(f"    Stream Type:       {c['stream_type']}")
            print(f"    Speaker:           {c['metadata']['speaker']}")
            print(f"    Timestamps:        {c['metadata']['source_timestamps']}")
            print(f"    Character Count:   {c['metadata']['char_count']}")
            print(f"    Turn Count:        {c['metadata']['turn_count']}")
            print(f"    Verbatim Content:\n    \"{c['content']}\"")

        results.append({
            'session_id': s_id,
            'status': 'EXTRACTED',
            'meeting_type': st3.get('meeting_type'),
            'chunk_count': len(chunks),
            'voice_chunks': chunks
        })

    # Save results to file
    with open('scripts/stage4b_voice_results.json', 'w', encoding='utf-8') as out_f:
        json.dump(results, out_f, indent=2)

    print("\nSaved voice extraction results to scripts/stage4b_voice_results.json")

if __name__ == '__main__':
    evaluate_voice_extraction()
