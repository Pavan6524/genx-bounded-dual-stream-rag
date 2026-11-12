import json

def verify_voice_purity():
    with open('workflows/runtime_ingestion_transcripts.json', 'r', encoding='utf-8') as f:
        fixture = {s['id']: s for s in json.load(f)}

    with open('scripts/stage4b_voice_results.json', 'r', encoding='utf-8') as f:
        results = json.load(f)

    for item in results:
        s_id = item['session_id']
        if item['status'] == 'SKIPPED_REJECTED':
            assert len(item['voice_chunks']) == 0
            print(f"PASS: {s_id} is rejected and has exactly 0 voice chunks.")
            continue

        raw_session = fixture[s_id]
        sara_turns = {t['timestamp']: t['text'] for t in raw_session['transcript'] if t['speaker'] == 'Dr. Sara Hegy'}
        client_turns = {t['timestamp']: t['text'] for t in raw_session['transcript'] if t['speaker'] != 'Dr. Sara Hegy'}

        for c_idx, chunk in enumerate(item['voice_chunks']):
            ts_list = chunk['metadata']['source_timestamps']
            content = chunk['content']

            # 1. Verify speaker
            assert chunk['metadata']['speaker'] == 'Dr. Sara Hegy'
            assert chunk['stream_type'] == 'voice_sample'
            assert chunk['session_id'] == s_id

            # 2. Verify verbatim match
            reconstructed = '\n'.join([sara_turns[ts] for ts in ts_list])
            assert content == reconstructed, f"Content mismatch in {s_id} chunk {c_idx+1}"

            # 3. Verify zero client speech contamination
            for c_ts, c_text in client_turns.items():
                assert c_text not in content, f"Client speech leaked into {s_id} chunk {c_idx+1}: {c_text}"

            # 4. Verify char count
            assert chunk['metadata']['char_count'] == len(content)

            print(f"PASS: {s_id} Chunk {c_idx+1} ({ts_list}) is 100% verbatim Dr. Sara speech, zero client leakage, char_count={len(content)}.")

if __name__ == '__main__':
    verify_voice_purity()
