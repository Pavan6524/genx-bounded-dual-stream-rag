import json

def run_audit():
    with open('workflows/runtime_ingestion_transcripts.json', 'r', encoding='utf-8') as f:
        fixture = {s['id']: s for s in json.load(f)}

    with open('scripts/stage4a_refined_results.json', 'r', encoding='utf-8') as f:
        s4a = json.load(f)

    with open('scripts/stage4b_voice_results.json', 'r', encoding='utf-8') as f:
        s4b = json.load(f)

    print("=== 1. FRAMEWORK TIMESTAMPS VS ORIGINAL TURNS ===")
    for item in s4a:
        s_id = item['session_id']
        raw = fixture[s_id]
        trans_ts = [t['timestamp'] for t in raw['transcript']]
        parsed = item.get('parsed_json', {})
        for fw in parsed.get('frameworks', []):
            fw_name = fw.get('name')
            src_ts = fw.get('source_timestamps', [])
            print(f"\nSession {s_id} - Framework: '{fw_name}'")
            print(f"  Extracted timestamps: {src_ts}")
            print(f"  All session timestamps: {trans_ts}")
            nonexistent = [t for t in src_ts if t not in trans_ts]
            print(f"  Nonexistent timestamps: {nonexistent}")
            
            # Detailed breakdown
            for t_idx, turn in enumerate(raw['transcript']):
                in_extracted = turn['timestamp'] in src_ts
                print(f"    Turn {t_idx} [{turn['timestamp']}] ({turn['speaker']}): extracted={in_extracted} | text: {turn['text'][:70]}...")

    print("\n=== 2. VOICE CHUNKS AUDIT ===")
    for item in s4b:
        s_id = item['session_id']
        chunks = item.get('voice_chunks', [])
        print(f"\nSession {s_id} - Status: {item.get('status')} - Chunks: {len(chunks)}")
        for i, c in enumerate(chunks):
            spk = c['metadata']['speaker']
            ts = c['metadata']['source_timestamps']
            length = c['metadata']['char_count']
            print(f"  Chunk {i+1}: Speaker='{spk}' | Timestamps={ts} | Length={length}")
            print(f"    Excerpt: {c['content'][:70]}...")

if __name__ == '__main__':
    run_audit()
