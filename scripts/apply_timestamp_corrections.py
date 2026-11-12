import json

def apply_corrections():
    with open('scripts/stage4a_refined_results.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    corrected_timestamps = {
        'TEST-SES-101': ["00:01:55", "00:44:10", "00:44:40"],
        'TEST-SES-102': ["00:00:55", "00:02:00"]
    }

    for item in data:
        s_id = item['session_id']
        if s_id in corrected_timestamps:
            new_ts = corrected_timestamps[s_id]
            # Update parsed_json
            item['parsed_json']['frameworks'][0]['source_timestamps'] = new_ts
            
            # Update raw_model_response string cleanly
            raw_parsed = json.loads(item['raw_model_response'])
            raw_parsed['frameworks'][0]['source_timestamps'] = new_ts
            item['raw_model_response'] = json.dumps(raw_parsed, indent=2)

    with open('scripts/stage4a_refined_results.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    print("Successfully updated timestamp arrays in scripts/stage4a_refined_results.json")

if __name__ == '__main__':
    apply_corrections()
