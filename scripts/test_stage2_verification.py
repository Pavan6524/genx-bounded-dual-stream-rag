import json
import os

def test_stage2():
    print("=" * 60)
    print("STAGE 2 VERIFICATION: PARSER & TURN SAMPLER")
    print("=" * 60)

    # 1. Verify runtime workflow JSON
    wf_path = 'workflows/ingestion_firewall_runtime_test.json'
    assert os.path.exists(wf_path), f"Missing {wf_path}"
    with open(wf_path, 'r', encoding='utf-8') as f:
        wf = json.load(f)

    nodes = {n['name']: n for n in wf['nodes']}
    print(f"Total nodes in runtime test workflow: {len(wf['nodes'])}")
    assert len(wf['nodes']) == 21, f"Expected 21 nodes, got {len(wf['nodes'])}"

    # Parse Transcripts Array
    parse_node = nodes.get('Parse Transcripts Array')
    assert parse_node is not None, "Missing Parse Transcripts Array node"
    parse_code = parse_node['parameters'].get('jsCode', '')
    assert "this.helpers.getBinaryDataBuffer(0, 'data')" in parse_code, "Parse Transcripts Array must use this.helpers.getBinaryDataBuffer(0, 'data')"
    print("PASS: Parse Transcripts Array uses this.helpers.getBinaryDataBuffer(0, 'data')")

    # Process Sessions Sequentially loop output
    conns = wf['connections'].get('Process Sessions Sequentially', {})
    main_conns = conns.get('main', [])
    assert len(main_conns) >= 2, "Process Sessions Sequentially must have at least 2 outputs"
    loop_targets = [t['node'] for t in main_conns[1]]
    assert loop_targets == ['Turn Sampler'], f"Expected loop output main[1] -> ['Turn Sampler'], got {loop_targets}"
    done_targets = [t['node'] for t in main_conns[0]] if len(main_conns[0]) > 0 else []
    assert done_targets == [], f"Expected done output main[0] -> [], got {done_targets}"
    print("PASS: Process Sessions Sequentially sends loop output (main[1]) strictly to Turn Sampler")

    # 2. Verify fixture file
    fixture_path = 'workflows/runtime_ingestion_transcripts.json'
    assert os.path.exists(fixture_path), f"Missing {fixture_path}"
    with open(fixture_path, 'r', encoding='utf-8') as f:
        fixture_data = json.load(f)

    assert isinstance(fixture_data, list), "Fixture must be a JSON array"
    assert len(fixture_data) == 4, f"Fixture must contain exactly 4 sessions, found {len(fixture_data)}"
    
    expected_ids = ['TEST-SES-101', 'TEST-SES-102', 'TEST-SES-103', 'TEST-SES-104']
    actual_ids = [s.get('id') for s in fixture_data]
    assert actual_ids == expected_ids, f"Expected session IDs {expected_ids}, got {actual_ids}"

    for idx, s in enumerate(fixture_data):
        assert 'transcript' in s and isinstance(s['transcript'], list), f"Session {s.get('id')} missing transcript array"
        assert len(s['transcript']) > 0, f"Session {s.get('id')} has empty transcript"
        for t_idx, turn in enumerate(s['transcript']):
            assert 'speaker' in turn and turn['speaker'], f"Session {s.get('id')} turn {t_idx} missing speaker"
            assert 'timestamp' in turn and turn['timestamp'], f"Session {s.get('id')} turn {t_idx} missing timestamp"
            assert 'text' in turn and turn['text'], f"Session {s.get('id')} turn {t_idx} missing text"

    print(f"PASS: Fixture contains exactly 4 valid sessions with correct IDs and non-empty transcript arrays")

    # 3. Verify Turn Sampler logic simulation
    def run_turn_sampler(session):
        transcript = session.get('transcript', [])
        total_turns = len(transcript)
        sampled_turns = []

        if total_turns <= 60:
            for i, t in enumerate(transcript):
                sampled_turns.append({
                    'original_index': i,
                    'timestamp': t['timestamp'],
                    'speaker': t['speaker'],
                    'text': t['text']
                })
        else:
            first40 = [{'original_index': i, 'timestamp': t['timestamp'], 'speaker': t['speaker'], 'text': t['text']} for i, t in enumerate(transcript[:40])]
            last20_start = max(40, total_turns - 20)
            last20 = [{'original_index': last20_start + idx, 'timestamp': t['timestamp'], 'speaker': t['speaker'], 'text': t['text']} for idx, t in enumerate(transcript[last20_start:])]
            sampled_turns = first40 + [t for t in last20 if t['original_index'] >= 40]

        formatted_dialogue = '\n'.join([f"{t['speaker']} [{t['timestamp']}]: {t['text']}" for t in sampled_turns])

        return {
            'id': session['id'],
            'title': session['title'],
            'created_at': session['created_at'],
            'participants': session['participants'],
            'total_turns': total_turns,
            'is_sampled': total_turns > 60,
            'transcript': session['transcript'],
            'sampled_turns': sampled_turns,
            'dialogue_text': formatted_dialogue
        }

    # Test SES-101
    s101_out = run_turn_sampler(fixture_data[0])
    assert s101_out['id'] == 'TEST-SES-101'
    assert s101_out['total_turns'] == 6, f"Expected 6 turns, got {s101_out['total_turns']}"
    assert s101_out['is_sampled'] is False, f"Expected is_sampled False, got {s101_out['is_sampled']}"
    assert len(s101_out['sampled_turns']) == 6, f"Expected 6 sampled turns, got {len(s101_out['sampled_turns'])}"
    assert len(s101_out['dialogue_text'].split('\n')) == 6, "Expected 6 dialogue lines"
    for i in range(6):
        assert s101_out['sampled_turns'][i]['original_index'] == i
    print("PASS: TEST-SES-101 sampling: total_turns=6, is_sampled=False, sampled_turns.length=6, full dialogue_text")

    # Test edge case: exactly 60 turns
    dummy_60 = {
        'id': 'TEST-DUMMY-60',
        'title': 'Test 60',
        'created_at': '2026-01-01',
        'participants': ['A', 'B'],
        'transcript': [{'speaker': 'A', 'timestamp': f'00:{i:02d}:00', 'text': f'Turn {i}'} for i in range(60)]
    }
    s60_out = run_turn_sampler(dummy_60)
    assert s60_out['total_turns'] == 60
    assert s60_out['is_sampled'] is False
    assert len(s60_out['sampled_turns']) == 60
    assert [t['original_index'] for t in s60_out['sampled_turns']] == list(range(60))
    print("PASS: Exactly 60 turns preserved unchanged without sampling")

    # Test edge case: 75 turns (>60)
    dummy_75 = {
        'id': 'TEST-DUMMY-75',
        'title': 'Test 75',
        'created_at': '2026-01-01',
        'participants': ['A', 'B'],
        'transcript': [{'speaker': 'A', 'timestamp': f'00:{i:02d}:00', 'text': f'Turn {i}'} for i in range(75)]
    }
    s75_out = run_turn_sampler(dummy_75)
    assert s75_out['total_turns'] == 75
    assert s75_out['is_sampled'] is True
    assert len(s75_out['sampled_turns']) == 60 # 40 + 20
    indices = [t['original_index'] for t in s75_out['sampled_turns']]
    assert indices[:40] == list(range(40)), "First 40 turns match"
    assert indices[40:] == list(range(55, 75)), f"Last 20 turns match, got {indices[40:]}"
    assert len(set(indices)) == 60, "No duplicate turns sampled"
    print("PASS: >60 turns (75 turns) selects first 40 and last 20 with exact original indexes and zero duplication")

    print("\nSTAGE 2 ALL STATIC & LOGICAL VERIFICATIONS PASSED.")

if __name__ == '__main__':
    test_stage2()
