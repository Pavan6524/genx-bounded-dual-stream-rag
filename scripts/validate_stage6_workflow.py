"""
Validation script for workflows/gated_retrieval.json
Performs static analysis and verification of workflow DAG topology,
threshold gating, credentials, endpoints, and isolation properties.
"""

import json
import re
import sys

def validate_gated_retrieval(workflow_path="workflows/gated_retrieval.json"):
    print(f"=== Statically Validating {workflow_path} ===")
    with open(workflow_path, "r", encoding="utf-8") as f:
        wf = json.load(f)

    # 1. Basic properties
    name = wf.get("name")
    nodes = wf.get("nodes", [])
    connections = wf.get("connections", {})
    print(f"Workflow Name: {name}")
    print(f"Total Nodes: {len(nodes)}")
    assert len(nodes) == 16, f"Expected exactly 16 nodes, found {len(nodes)}"

    # 2. Node uniqueness
    node_names = {}
    node_ids = {}
    for n in nodes:
        assert n["name"] not in node_names, f"Duplicate node name: {n['name']}"
        assert n["id"] not in node_ids, f"Duplicate node id: {n['id']}"
        node_names[n["name"]] = n
        node_ids[n["id"]] = n
    print("PASS: All node names and IDs are unique.")

    # 3. Connection integrity (no dangling edges)
    for src_name, conn_data in connections.items():
        assert src_name in node_names, f"Connection source '{src_name}' does not exist in nodes!"
        for out_type, out_branches in conn_data.items():
            for branch_idx, targets in enumerate(out_branches):
                for target in targets:
                    t_name = target["node"]
                    assert t_name in node_names, f"Connection target '{t_name}' (from '{src_name}') not found in nodes!"
    print("PASS: All connection sources and targets exist in node inventory.")

    # 4. Check for orphaned nodes
    target_nodes = set()
    for src_name, conn_data in connections.items():
        for out_type, out_branches in conn_data.items():
            for targets in out_branches:
                for t in targets:
                    target_nodes.add(t["node"])
    
    entry_nodes = [n["name"] for n in nodes if n["type"] == "n8n-nodes-base.manualTrigger"]
    assert len(entry_nodes) == 1, f"Expected 1 entry trigger, found {len(entry_nodes)}"
    
    for n in nodes:
        n_name = n["name"]
        if n_name != entry_nodes[0]:
            assert n_name in target_nodes, f"Orphaned node detected (no incoming connections): {n_name}"
    print("PASS: No orphaned nodes detected.")

    # 5. Database safety: NO database mutations
    for n in nodes:
        if n["type"] == "n8n-nodes-base.postgres":
            query = n.get("parameters", {}).get("query", "").upper()
            assert "INSERT" not in query, f"Mutation detected in {n['name']}: contains INSERT"
            assert "UPDATE" not in query, f"Mutation detected in {n['name']}: contains UPDATE"
            assert "DELETE" not in query, f"Mutation detected in {n['name']}: contains DELETE"
            assert "DROP" not in query, f"Mutation detected in {n['name']}: contains DROP"
            assert "ALTER" not in query, f"Mutation detected in {n['name']}: contains ALTER"
            assert "TRUNCATE" not in query, f"Mutation detected in {n['name']}: contains TRUNCATE"
            print(f"PASS: Read-only query confirmed for Postgres node '{n['name']}'")

    # 6. SQL Query, Threshold & Parameter Validation
    fw_node = node_names.get("Retrieve Framework Stream")
    assert fw_node is not None, "Missing 'Retrieve Framework Stream' node"
    fw_query = fw_node["parameters"]["query"]
    assert "stream_type = 'framework'" in fw_query, "Framework query missing stream_type filter"
    assert ">= 0.70" in fw_query, "Framework query missing >= 0.70 threshold"
    assert "LIMIT 2" in fw_query, "Framework query missing LIMIT 2"
    assert "(embedding <=> $1::vector)" in fw_query, "Framework query missing cosine distance operator"
    assert fw_node.get("alwaysOutputData") is True, "'Retrieve Framework Stream' must have alwaysOutputData: true"
    print("PASS: Framework retrieval query meets all threshold and limit specifications (>= 0.70, LIMIT 2).")

    voice_node = node_names.get("Retrieve Voice Stream")
    assert voice_node is not None, "Missing 'Retrieve Voice Stream' node"
    voice_query = voice_node["parameters"]["query"]
    assert "stream_type = 'voice_sample'" in voice_query, "Voice query missing stream_type filter"
    assert ">= 0.65" in voice_query, "Voice query missing >= 0.65 threshold"
    assert "LIMIT 2" in voice_query, "Voice query missing LIMIT 2"
    assert "(embedding <=> $1::vector)" in voice_query, "Voice query missing cosine distance operator"
    assert voice_node.get("alwaysOutputData") is True, "'Retrieve Voice Stream' must have alwaysOutputData: true"
    print("PASS: Voice retrieval query meets all threshold and limit specifications (>= 0.65, LIMIT 2).")

    # 7. Greeting Bypass Verification
    # Trace reachable nodes from Greeting Router main[0] (true branch)
    greeting_visited = set()
    greeting_queue = [t["node"] for t in connections["Greeting Router"]["main"][0]]
    while greeting_queue:
        curr = greeting_queue.pop(0)
        if curr in greeting_visited:
            continue
        greeting_visited.add(curr)
        for out_branches in connections.get(curr, {}).get("main", []):
            for t in out_branches:
                greeting_queue.append(t["node"])
    
    print(f"Reachable nodes along Greeting bypass branch: {greeting_visited}")
    assert "Static Greeting Response" in greeting_visited
    prohibited_from_greeting = [
        "Ollama Query Embedder", "Validate Query Vector",
        "Retrieve Framework Stream", "Retrieve Voice Stream",
        "Ollama Grounded Generator"
    ]
    for p in prohibited_from_greeting:
        assert p not in greeting_visited, f"VIOLATION: Node '{p}' is reachable from greeting branch!"
    print("PASS: Greeting branch strictly bypasses Ollama embedding, PostgreSQL, and LLM generation.")

    # 8. Zero-Result Gate Verification
    # Trace reachable nodes from Hard Gate main[1] (false branch: 0 qualifying results)
    zero_result_visited = set()
    zero_result_queue = [t["node"] for t in connections["Hard Gate (Has Results?)"]["main"][1]]
    while zero_result_queue:
        curr = zero_result_queue.pop(0)
        if curr in zero_result_visited:
            continue
        zero_result_visited.add(curr)
        for out_branches in connections.get(curr, {}).get("main", []):
            for t in out_branches:
                zero_result_queue.append(t["node"])

    print(f"Reachable nodes along Zero-Result branch: {zero_result_visited}")
    assert "Return Zero Result Output" in zero_result_visited
    assert "Ollama Grounded Generator" not in zero_result_visited, "VIOLATION: LLM generator reachable from zero-result branch!"
    print("PASS: Zero-result branch strictly bypasses Ollama LLM generation.")

    # Check exact fallback text in Return Zero Result Output
    zero_code = node_names["Return Zero Result Output"]["parameters"]["jsCode"]
    assert "No documented coaching frameworks match this topic." in zero_code, "Missing exact zero-result fallback text"
    print("PASS: Exact zero-result fallback string verified: 'No documented coaching frameworks match this topic.'")

    # 9. Credentials & Environment
    for n in [fw_node, voice_node]:
        cred = n.get("credentials", {}).get("postgres", {})
        assert cred.get("name") == "Postgres account", f"Expected Postgres account credential, got {cred}"
    print("PASS: Postgres credentials verified.")

    embed_node = node_names["Ollama Query Embedder"]
    assert "$env.OLLAMA_BASE_URL" in embed_node["parameters"]["url"]
    assert "$env.OLLAMA_EMBED_MODEL" in embed_node["parameters"]["jsonBody"]
    print("PASS: Ollama embedder endpoint configured with environment variables.")

    gen_node = node_names["Ollama Grounded Generator"]
    assert "$env.OLLAMA_BASE_URL" in gen_node["parameters"]["url"]
    assert "$env.OLLAMA_LLM_MODEL" in gen_node["parameters"]["jsonBody"]
    print("PASS: Ollama generator endpoint configured with environment variables.")

    print("\n>>> ALL STATIC VALIDATIONS PASSED SUCCESSFULLY <<<")
    return True

if __name__ == "__main__":
    validate_gated_retrieval()
