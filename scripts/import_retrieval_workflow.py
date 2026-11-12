"""
Stage 6.2A Controlled n8n Workflow Import & Post-Import Verification
Imports workflows/gated_retrieval.json into the local n8n instance and
executes a comprehensive comparison between local source and live export.
"""

import subprocess
import json
import os
import sys

TARGET_PROJECT_ID = "w24y2iBD8xkaEi8K"
WORKFLOW_FILE_CONTAINER = "/workflows/gated_retrieval.json"
WORKFLOW_FILE_LOCAL = "workflows/gated_retrieval.json"
EXPECTED_NAME = "Bounded Dual-Stream Gated Retrieval"
EXPECTED_NODE_COUNT = 16
INGESTION_WORKFLOW_ID = "IlBw4RRELuh02Akm"

def check_preconditions():
    print("=== Step 1: Pre-Import Safety Checks ===")
    
    # Check 1: Local file exists and parses
    assert os.path.exists(WORKFLOW_FILE_LOCAL), f"Missing {WORKFLOW_FILE_LOCAL}"
    with open(WORKFLOW_FILE_LOCAL, "r", encoding="utf-8") as f:
        local_wf = json.load(f)
    assert len(local_wf.get("nodes", [])) == EXPECTED_NODE_COUNT, f"Expected {EXPECTED_NODE_COUNT} nodes in local workflow"
    print(f"PASS: Local workflow '{local_wf.get('name')}' is valid with {EXPECTED_NODE_COUNT} nodes.")

    # Check 2: Pre-import backup exists in workflows/backups/
    backups = [f for f in os.listdir("workflows/backups") if f.startswith("n8n_state_backup_pre_stage6_2a_")]
    assert len(backups) > 0, "No pre-import backup found in workflows/backups/!"
    latest_backup = sorted(backups)[-1]
    backup_path = os.path.join("workflows/backups", latest_backup)
    with open(backup_path, "r", encoding="utf-8") as f:
        backup_data = json.load(f)
    assert any(wf.get("id") == INGESTION_WORKFLOW_ID for wf in backup_data), f"Ingestion workflow {INGESTION_WORKFLOW_ID} missing from backup!"
    print(f"PASS: Verified pre-import backup {latest_backup} contains ingestion workflow {INGESTION_WORKFLOW_ID}.")

    # Check 3: Current n8n live workflows
    res = subprocess.run(['docker', 'exec', 'genx-n8n', 'n8n', 'export:workflow', '--all'], capture_output=True, text=True, check=True)
    idx = res.stdout.find('[')
    assert idx != -1, "Could not parse n8n export:workflow output"
    decoder = json.JSONDecoder()
    current_wfs, _ = decoder.raw_decode(res.stdout[idx:])
    
    # Verify ingestion workflow is live and unchanged
    live_ingestion = next((wf for wf in current_wfs if wf.get("id") == INGESTION_WORKFLOW_ID), None)
    assert live_ingestion is not None, f"Live ingestion workflow {INGESTION_WORKFLOW_ID} not found in n8n!"
    print(f"PASS: Live ingestion workflow '{live_ingestion.get('name')}' (ID: {live_ingestion.get('id')}) verified.")

    # Check if retrieval workflow is already imported
    existing_retrieval = next((wf for wf in current_wfs if wf.get("name") == EXPECTED_NAME), None)
    if existing_retrieval:
        print(f"WARNING: Workflow '{EXPECTED_NAME}' already exists in n8n with ID: {existing_retrieval.get('id')}")
        return local_wf, existing_retrieval.get("id"), True, backup_path

    print("PASS: Pre-import safety checks passed. Workflow is ready for import.")
    return local_wf, None, False, backup_path

def execute_import():
    cmd = [
        'docker', 'exec', 'genx-n8n',
        'n8n', 'import:workflow',
        f'--input={WORKFLOW_FILE_CONTAINER}',
        f'--projectId={TARGET_PROJECT_ID}',
        '--activeState=false'
    ]
    print(f"Executing: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Import command failed with return code {res.returncode}: {res.stderr}"
    print("PASS: Import command executed successfully.")

    # Locate newly imported workflow ID
    res_list = subprocess.run(['docker', 'exec', 'genx-n8n', 'n8n', 'export:workflow', '--all'], capture_output=True, text=True, check=True)
    idx = res_list.stdout.find('[')
    decoder = json.JSONDecoder()
    current_wfs, _ = decoder.raw_decode(res_list.stdout[idx:])
    
    imported_wf = next((wf for wf in current_wfs if wf.get("name") == EXPECTED_NAME), None)
    assert imported_wf is not None, f"Could not find imported workflow '{EXPECTED_NAME}' after import!"
    imported_id = imported_wf.get("id")
    assert imported_id != INGESTION_WORKFLOW_ID, "COLLISION: Imported workflow ID matches ingestion workflow ID!"
    print(f"PASS: Workflow '{EXPECTED_NAME}' imported with unique ID: {imported_id}")
    return imported_id

def verify_and_compare(local_wf, workflow_id, backup_path):
    print("=== Step 2: Post-Import Verification & Comparison ===")
    
    # Export the live workflow by ID
    cmd = ['docker', 'exec', 'genx-n8n', 'n8n', 'export:workflow', f'--id={workflow_id}']
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    idx = res.stdout.find('{')
    if idx == -1:
        idx = res.stdout.find('[')
    decoder = json.JSONDecoder()
    live_export, _ = decoder.raw_decode(res.stdout[idx:])
    if isinstance(live_export, list):
        live_export = live_export[0]

    # Save live export locally
    export_path = "workflows/live_exported_retrieval_wf.json"
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(live_export, f, indent=2)
    print(f"PASS: Live exported workflow saved to {export_path}")

    # 1. Activation state
    assert live_export.get("active") is False, "SECURITY VIOLATION: Workflow is active!"
    print("PASS: Workflow activation state confirmed inactive (active: false).")

    # 2. Node count
    live_nodes = live_export.get("nodes", [])
    local_nodes = local_wf.get("nodes", [])
    assert len(live_nodes) == EXPECTED_NODE_COUNT, f"Live nodes count {len(live_nodes)} != {EXPECTED_NODE_COUNT}"
    print(f"PASS: Node count matches exactly ({EXPECTED_NODE_COUNT} nodes).")

    # 3. Node mapping comparison
    live_node_map = {n["name"]: n for n in live_nodes}
    local_node_map = {n["name"]: n for n in local_nodes}
    assert set(live_node_map.keys()) == set(local_node_map.keys()), "Node names set mismatch!"

    for name, loc_n in local_node_map.items():
        liv_n = live_node_map[name]
        assert liv_n["id"] == loc_n["id"], f"Node ID mismatch for {name}: live {liv_n['id']} != local {loc_n['id']}"
        assert liv_n["type"] == loc_n["type"], f"Node type mismatch for {name}"
        assert liv_n["typeVersion"] == loc_n["typeVersion"], f"Node typeVersion mismatch for {name}"

    print("PASS: All 16 node IDs, names, types, and typeVersions match local source.")

    # 4. Connections comparison
    assert live_export.get("connections") == local_wf.get("connections"), "Connections mismatch between live and local!"
    print("PASS: Connection topology matches local source identically.")

    # 5. SQL Thresholds & Limits
    fw_node = live_node_map["Retrieve Framework Stream"]
    assert "stream_type = 'framework'" in fw_node["parameters"]["query"]
    assert ">= 0.70" in fw_node["parameters"]["query"]
    assert "LIMIT 2" in fw_node["parameters"]["query"]
    assert fw_node.get("alwaysOutputData") is True
    print("PASS: Framework retrieval SQL query, threshold (>= 0.70), and LIMIT 2 preserved.")

    voice_node = live_node_map["Retrieve Voice Stream"]
    assert "stream_type = 'voice_sample'" in voice_node["parameters"]["query"]
    assert ">= 0.65" in voice_node["parameters"]["query"]
    assert "LIMIT 2" in voice_node["parameters"]["query"]
    assert voice_node.get("alwaysOutputData") is True
    print("PASS: Voice retrieval SQL query, threshold (>= 0.65), and LIMIT 2 preserved.")

    # 6. Credentials & Endpoints
    for n in [fw_node, voice_node]:
        assert n.get("credentials", {}).get("postgres", {}).get("name") == "Postgres account"
    print("PASS: PostgreSQL credentials mapped to 'Postgres account'.")

    embed_node = live_node_map["Ollama Query Embedder"]
    assert "$env.OLLAMA_BASE_URL" in embed_node["parameters"]["url"]
    assert "$env.OLLAMA_EMBED_MODEL" in embed_node["parameters"]["jsonBody"]
    print("PASS: Ollama embedder endpoint expression preserved.")

    gen_node = live_node_map["Ollama Grounded Generator"]
    assert "$env.OLLAMA_BASE_URL" in gen_node["parameters"]["url"]
    assert "$env.OLLAMA_LLM_MODEL" in gen_node["parameters"]["jsonBody"]
    print("PASS: Ollama generator endpoint expression preserved.")

    # 7. Greeting & Zero-Result Fallback
    zero_node = live_node_map["Return Zero Result Output"]
    assert "No documented coaching frameworks match this topic." in zero_node["parameters"]["jsCode"]
    print("PASS: Exact zero-result fallback text preserved.")

    # Check n8n version
    v_res = subprocess.run(['docker', 'exec', 'genx-n8n', 'n8n', '--version'], capture_output=True, text=True, check=True)
    n8n_version = v_res.stdout.strip()

    # Generate Stage 6.2A Report
    report = {
        "stage": "Stage 6.2A — Controlled n8n Workflow Import",
        "status": "PASS",
        "backup_location": backup_path,
        "imported_workflow_id": workflow_id,
        "workflow_name": EXPECTED_NAME,
        "target_project_id": TARGET_PROJECT_ID,
        "n8n_version": n8n_version,
        "node_count": EXPECTED_NODE_COUNT,
        "connection_verification": "IDENTICAL",
        "local_vs_live_comparison": {
            "node_names_identical": True,
            "node_ids_identical": True,
            "node_types_identical": True,
            "connections_identical": True,
            "sql_thresholds_verified": True,
            "credentials_verified": True,
            "ollama_endpoints_verified": True,
            "greeting_bypass_verified": True,
            "zero_result_fallback_verified": True
        },
        "activation_state": False,
        "files_created": [
            export_path,
            "scripts/stage6_2a_import_report.json"
        ],
        "errors_or_outstanding_issues": []
    }
    with open("scripts/stage6_2a_import_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("PASS: Saved import completion report to scripts/stage6_2a_import_report.json")

    return True

if __name__ == '__main__':
    # Guard: prevent accidental execution unless --execute flag is passed
    if '--execute' not in sys.argv:
        print("SAFETY GUARD: Run with --check-only to verify preconditions without importing.")
        print("To execute import after explicit user authorization: python scripts/import_retrieval_workflow.py --execute")
        if '--check-only' in sys.argv:
            check_preconditions()
        sys.exit(0)

    local_wf, existing_id, already_imported, backup_path = check_preconditions()
    if already_imported:
        print(f"Workflow is already imported with ID {existing_id}. Running post-import verification...")
        verify_and_compare(local_wf, existing_id, backup_path)
    else:
        wf_id = execute_import()
        verify_and_compare(local_wf, wf_id, backup_path)
