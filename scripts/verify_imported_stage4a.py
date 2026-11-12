import json

def verify_live():
    with open(r'C:\Users\HP\.gemini\antigravity\brain\7140c1e0-4a45-49c6-83d1-b9d3e3bbd609\.system_generated\tasks\task-1523.log', 'r', encoding='utf-8') as f:
        raw_log = f.read()

    data = json.loads(raw_log)
    live_wf = data[0] if isinstance(data, list) else data

    with open('workflows/ingestion_firewall_runtime_test.json', 'r', encoding='utf-8') as f:
        local_wf = json.load(f)

    print("=== LIVE WORKFLOW METADATA ===")
    print("ID:", live_wf.get('id'))
    print("Name:", live_wf.get('name'))
    print("Version Counter:", live_wf.get('versionCounter'))
    print("Version ID:", live_wf.get('versionId'))

    assert live_wf.get('id') == 'IlBw4RRELuh02Akm', f"Workflow ID changed: {live_wf.get('id')}"
    assert live_wf.get('name') == 'Ingestion Firewall & Dual-Stream Extraction (Runtime Test)'

    print("\n=== NODE COUNT & CONNECTIONS ===")
    print("Live node count:", len(live_wf['nodes']), "| Local node count:", len(local_wf['nodes']))
    assert len(live_wf['nodes']) == 21

    live_nodes = {n['name']: n for n in live_wf['nodes']}
    local_nodes = {n['name']: n for n in local_wf['nodes']}

    assert set(live_nodes.keys()) == set(local_nodes.keys())
    assert live_wf['connections'] == local_wf['connections']
    print("PASS: Node names, IDs, and connections 100% match local file.")

    print("\n=== PROMPT SYNCHRONIZATION CHECK ===")
    live_prompt = live_nodes['Ollama Framework Extractor']['parameters']['jsonBody']
    local_prompt = local_nodes['Ollama Framework Extractor']['parameters']['jsonBody']
    assert live_prompt == local_prompt, "Live prompt differs from local!"
    print("PASS: Ollama Framework Extractor jsonBody is 100% synchronized with local file.")

    # Check the two specific wording rules
    assert "Every source timestamp must exactly match a timestamp present in the original transcript. Never invent timestamps." in live_prompt
    assert "Extract decision logic only when explicitly supported by the current transcript. The Table and Shoulder Test example must not introduce unsupported concepts into unrelated sessions." in live_prompt
    print("PASS: Both wording corrections verified in the live workflow.")

if __name__ == '__main__':
    verify_live()
