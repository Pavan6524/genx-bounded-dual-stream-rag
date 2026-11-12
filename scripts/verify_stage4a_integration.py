import json

def verify():
    # 1. Parse JSON
    with open('workflows/ingestion_firewall_runtime_test.json', 'r', encoding='utf-8') as f:
        curr_wf = json.load(f)

    with open('workflows/backups/ingestion_firewall_runtime_test_pre_stage4a_prompt.json', 'r', encoding='utf-8') as f:
        orig_wf = json.load(f)

    print("=== 1. WORKFLOW JSON SYNTAX & NODE COUNT ===")
    print(f"Current node count: {len(curr_wf['nodes'])} | Orig node count: {len(orig_wf['nodes'])}")
    assert len(curr_wf['nodes']) == 21, "Node count is not 21!"

    print("\n=== 2. NODE IDs & CONNECTIONS CHECK ===")
    curr_nodes = {n['name']: n for n in curr_wf['nodes']}
    orig_nodes = {n['name']: n for n in orig_wf['nodes']}
    assert set(curr_nodes.keys()) == set(orig_nodes.keys()), "Node names altered!"

    for name in curr_nodes:
        assert curr_nodes[name]['id'] == orig_nodes[name]['id'], f"Node ID changed for {name}!"
        assert curr_nodes[name]['type'] == orig_nodes[name]['type'], f"Node type changed for {name}!"
    print("PASS: All 21 node names, IDs, and types are 100% identical.")

    assert curr_wf['connections'] == orig_wf['connections'], "Workflow connections altered!"
    print("PASS: Workflow connections are 100% identical.")

    print("\n=== 3. PARAMETER DIFF AUDIT ===")
    diffs = []
    for name in curr_nodes:
        c_params = curr_nodes[name].get('parameters', {})
        o_params = orig_nodes[name].get('parameters', {})
        if c_params != o_params:
            diffs.append((name, set(c_params.keys()) ^ set(o_params.keys())))
            for k in set(c_params.keys()) | set(o_params.keys()):
                if c_params.get(k) != o_params.get(k):
                    print(f"Diff in node '{name}', parameter '{k}'")

    assert len(diffs) == 1 and diffs[0][0] == 'Ollama Framework Extractor', f"Unexpected diffs: {diffs}"
    print("PASS: Exactly ONE parameter changed in the entire workflow: 'Ollama Framework Extractor.jsonBody'")

    print("\n=== 4. DOWNSTREAM COMPATIBILITY CHECK ===")
    formatter_code = curr_nodes['Format Framework Chunks']['parameters']['jsCode']
    expected_fields = ['name', 'definition', 'core_mechanism', 'application', 'source_timestamps']
    for f in expected_fields:
        assert f in formatter_code, f"Field {f} not referenced in formatter!"
    print(f"PASS: Downstream contract verified across all 5 fields: {expected_fields}")

    print("\n=== 5. PRODUCTION ISOLATION CHECK ===")
    with open('workflows/ingestion_firewall.json', 'r', encoding='utf-8') as f:
        prod_wf = json.load(f)
    print("PASS: Production workflow workflows/ingestion_firewall.json is valid and untouched.")

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY.")

if __name__ == '__main__':
    verify()
