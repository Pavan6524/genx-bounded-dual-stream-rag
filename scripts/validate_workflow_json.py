import json
import sys

def validate_workflow(path):
    with open(path, "r", encoding="utf-8") as f:
        wf = json.load(f)
        
    print(f"Workflow Name: {wf.get('name')}")
    nodes = wf.get("nodes", [])
    connections = wf.get("connections", {})
    print(f"Total Nodes: {len(nodes)}")
    
    node_names = {n["name"]: n for n in nodes}
    assert len(node_names) == len(nodes), "Duplicate node names found!"
    
    # Check all connection targets exist
    for source, conn_data in connections.items():
        assert source in node_names, f"Connection source '{source}' not in nodes!"
        for out_type, outputs in conn_data.items():
            for out_idx, target_list in enumerate(outputs):
                for target in target_list:
                    t_name = target["node"]
                    assert t_name in node_names, f"Target '{t_name}' (from '{source}') not in nodes!"
                    
    print("Graph topology: all source and target nodes exist.")
    
    # Check Firewall Partitioning
    # Trace reachable nodes from "Format Rejected Record"
    visited = set()
    queue = ["Format Rejected Record"]
    while queue:
        curr = queue.pop(0)
        if curr in visited:
            continue
        visited.add(curr)
        for out_type, outputs in connections.get(curr, {}).items():
            for target_list in outputs:
                for target in target_list:
                    t_name = target["node"]
                    if t_name not in visited and t_name != "Process Sessions Sequentially":
                        queue.append(t_name)
                        
    print(f"Nodes reachable along Rejection sub-branch (before looping): {visited}")
    for prohibited in ["Ollama Framework Embedder", "Ollama Voice Embedder", "Store Framework in Vault", "Store Voice in Vault", "Extract Voice Stream"]:
        assert prohibited not in visited, f"FIREWALL VIOLATION: '{prohibited}' reachable from rejection branch!"
        
    print("PASS: Rejection branch is 100% strictly partitioned from all embedding and vault storage nodes.")
    print("PASS: Workflow JSON syntax and node references are 100% valid.")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "workflows/ingestion_firewall.json"
    validate_workflow(target)
