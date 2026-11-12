"""
Execution and verification script for TC-02 (Framework Retrieval Runtime Test)
GenX Leadership Academy - Bounded Dual-Stream Gated Retrieval
Target Workflow: TSvKBGpM9nK7eb3U (Bounded Dual-Stream Gated Retrieval)
Query: "How do I practice Completion with Integrity when closing projects?"
"""

import subprocess
import json
import time
import sys
import os
import math

TARGET_WORKFLOW_ID = "TSvKBGpM9nK7eb3U"
INGESTION_WORKFLOW_ID = "IlBw4RRELuh02Akm"
DEFAULT_TARGET_QUERY = "How do I practice Completion with Integrity when closing projects?"
TARGET_QUERY = DEFAULT_TARGET_QUERY

def get_db_counts():
    """Retrieve row counts for knowledge_vault and rejected_meetings."""
    res = subprocess.run(
        ['docker', 'exec', 'genx-postgres', 'psql', '-U', 'genx', '-d', 'genx_rag', '-t', '-A', '-c',
         "SELECT count(*) FROM knowledge_vault UNION ALL SELECT count(*) FROM rejected_meetings;"],
        capture_output=True, text=True, check=True
    )
    counts = [int(x.strip()) for x in res.stdout.strip().split('\n') if x.strip()]
    return counts

def verify_workflow_state(workflow_id):
    """Verify workflow exists and retrieve its active status."""
    res = subprocess.run(
        ['docker', 'exec', 'genx-n8n', 'n8n', 'export:workflow', f'--id={workflow_id}'],
        capture_output=True, text=True, check=True
    )
    stdout = res.stdout.strip()
    idx = stdout.find('{')
    assert idx != -1, f"Failed to export workflow {workflow_id}"
    decoder = json.JSONDecoder()
    wf_data, _ = decoder.raw_decode(stdout[idx:])
    if isinstance(wf_data, list):
        wf_data = wf_data[0]
    return wf_data

def run_tc02(execute_mode=True, query=None):
    if query is None:
        query = os.environ.get("GENX_TEST_QUERY", DEFAULT_TARGET_QUERY)

    print("=" * 60)
    print("=== STAGE 6.2C: TC-02 FRAMEWORK RETRIEVAL RUNTIME TEST ===")
    print("=" * 60)
    print(f"Target Workflow ID: {TARGET_WORKFLOW_ID}")
    print(f"Query: \"{query}\"")
    print("Execution Mode: Manual via TC Runner Bridge")
    print("-" * 60)

    # 1. Pre-execution Safety Checks
    print("\n[PREFLIGHT] Checking PostgreSQL baseline row counts...")
    counts_pre = get_db_counts()
    print(f"  knowledge_vault:    {counts_pre[0]} (expected: 8)")
    print(f"  rejected_meetings:  {counts_pre[1]} (expected: 2)")
    assert counts_pre[0] == 8, f"Database integrity violation: knowledge_vault has {counts_pre[0]} rows (expected 8)"
    assert counts_pre[1] == 2, f"Database integrity violation: rejected_meetings has {counts_pre[1]} rows (expected 2)"
    print("  -> PostgreSQL baseline verified.")

    print("\n[PREFLIGHT] Verifying target workflow state...")
    wf_pre = verify_workflow_state(TARGET_WORKFLOW_ID)
    assert wf_pre.get("id") == TARGET_WORKFLOW_ID, "Target workflow ID mismatch!"
    assert wf_pre.get("active") is False, "Target workflow must be inactive (active: false)!"
    assert len(wf_pre.get("nodes", [])) == 16, f"Expected 16 nodes, found {len(wf_pre.get('nodes', []))}"
    print(f"  Target workflow '{wf_pre.get('name')}' is INACTIVE with 16 nodes.")

    print("\n[PREFLIGHT] Verifying ingestion workflow isolation...")
    ing_wf = verify_workflow_state(INGESTION_WORKFLOW_ID)
    assert ing_wf.get("id") == INGESTION_WORKFLOW_ID, "Ingestion workflow ID mismatch!"
    print(f"  Ingestion workflow '{ing_wf.get('name')}' verified untouched.")

    if not execute_mode:
        print("\n[READ-ONLY MODE] Preflight complete. TC-02 execution skipped pending user approval.")
        return True

    # 2. Execute via docker exec with TC Runner Bridge
    start_time = time.time()
    cmd = [
        'docker', 'exec',
        '-e', 'N8N_RUNNERS_BROKER_PORT=5699',
        '-e', 'N8N_BLOCK_ENV_ACCESS_IN_NODE=false',
        '-e', 'NODE_OPTIONS=--require=/data/tc_runner_bridge.js',
        '-e', f'GENX_TEST_QUERY={query}',
        'genx-n8n',
        'n8n', 'execute', f'--id={TARGET_WORKFLOW_ID}'
    ]
    print(f"\n[EXECUTION] Executing command:\n  {' '.join(cmd)}\n")
    res = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - start_time
    print(f"Command completed in {duration:.2f}s with returncode {res.returncode}")

    stdout_raw = res.stdout or ""
    stderr_raw = res.stderr or ""

    # Immediately persist raw outputs to disk before any assertions
    with open("scripts/tc02_raw_stdout.log", "w", encoding="utf-8") as f:
        f.write(stdout_raw)
    with open("scripts/tc02_raw_stderr.log", "w", encoding="utf-8") as f:
        f.write(stderr_raw)
    print("Saved raw output to scripts/tc02_raw_stdout.log and scripts/tc02_raw_stderr.log")

    if stderr_raw.strip():
        print("\n[STDERR OUTPUT]:")
        for line in stderr_raw.strip().split('\n'):
            print(f"  {line}")

    if stdout_raw.strip():
        print("\n[STDOUT OUTPUT (sample)]:")
        lines = stdout_raw.strip().split('\n')
        for line in lines[:30]:
            print(f"  {line}")
        if len(lines) > 30:
            print(f"  ... [{len(lines) - 30} more lines in scripts/tc02_raw_stdout.log]")

    # Attempt to parse JSON trace from stdout
    exec_data = None
    idx = stdout_raw.find('{')
    if idx != -1:
        try:
            decoder = json.JSONDecoder()
            exec_data, _ = decoder.raw_decode(stdout_raw[idx:])
            result_path = "scripts/tc02_execution_result.json"
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(exec_data, f, indent=2)
            print(f"\n[TRACE] Saved execution trace to {result_path}")
        except Exception as e:
            print(f"\n[WARNING] Could not parse JSON from stdout: {e}")

    # Handle non-zero exit code with structured diagnostic report
    if res.returncode != 0:
        error_info = {}
        if exec_data:
            result_data = exec_data.get("data", {}).get("resultData", {})
            error_obj = result_data.get("error", {})
            run_data = result_data.get("runData", {})
            executed_nodes = list(run_data.keys())
            last_node = executed_nodes[-1] if executed_nodes else None
            error_info = {
                "execution_id": exec_data.get("id"),
                "executed_nodes": executed_nodes,
                "last_executed_node": last_node,
                "error_message": error_obj.get("message"),
                "error_name": error_obj.get("name"),
                "error_description": error_obj.get("description"),
                "error_node": error_obj.get("node", {}).get("name") if isinstance(error_obj.get("node"), dict) else error_obj.get("node"),
                "error_stack": error_obj.get("stack")
            }

        diag_report = {
            "stage": "Stage 6.2C — TC-02 Execution Diagnostic Report",
            "status": "FAILED",
            "return_code": res.returncode,
            "duration_seconds": round(duration, 2),
            "target_workflow_id": TARGET_WORKFLOW_ID,
            "query": query,
            "stderr_summary": stderr_raw.strip(),
            "stdout_saved": "scripts/tc02_raw_stdout.log",
            "stderr_saved": "scripts/tc02_raw_stderr.log",
            "trace_saved": "scripts/tc02_execution_result.json" if exec_data else None,
            "n8n_error_details": error_info
        }
        with open("scripts/tc02_execution_failure_diagnosis.json", "w", encoding="utf-8") as f:
            json.dump(diag_report, f, indent=2)
        print(f"\n[DIAGNOSTIC] Wrote failure diagnostic report to scripts/tc02_execution_failure_diagnosis.json")
        print(f"\nCRITICAL: n8n execute returned code {res.returncode}. Execution halted without retry.")
        return False

    # 3. Extract execution details for successful runs
    assert exec_data is not None, "Execution succeeded but no execution data was parsed!"
    execution_id = exec_data.get("id") or exec_data.get("executionData", {}).get("id")
    result_data = exec_data.get("data", {}).get("resultData", {})
    run_data = result_data.get("runData", {})
    executed_nodes = list(run_data.keys())
    print(f"Execution ID: {execution_id}")
    print(f"Executed Nodes ({len(executed_nodes)}): {executed_nodes}")

    # 4. Rigorous Assertions on TC-02 Workflow Execution
    print("\n[VERIFICATION] Verifying executed DAG path and node contracts...")

    # Must NOT execute greeting response or zero result output
    prohibited_nodes = [
        "Static Greeting Response",
        "Return Zero Result Output"
    ]
    for p_node in prohibited_nodes:
        assert p_node not in executed_nodes, f"VIOLATION: Node '{p_node}' executed unexpectedly!"
    print("  PASS: Static Greeting Response and Return Zero Result Output were NOT executed.")

    # Must execute all required dual-stream RAG nodes
    required_nodes = [
        "When clicking ‘Execute workflow’",
        "Query Input & Normalizer",
        "Greeting Classifier",
        "Greeting Router",
        "Ollama Query Embedder",
        "Validate Query Vector",
        "Retrieve Framework Stream",
        "Retrieve Voice Stream",
        "Merge Retrieval Streams",
        "Aggregate & Gate Results",
        "Hard Gate (Has Results?)",
        "Format Grounded Prompt",
        "Ollama Grounded Generator",
        "Format Final Response"
    ]
    for r_node in required_nodes:
        assert r_node in executed_nodes, f"VIOLATION: Required node '{r_node}' was NOT executed!"
    print(f"  PASS: All {len(required_nodes)} required pipeline nodes executed.")

    # Verify Query Normalizer received correct query
    norm_data = run_data["Query Input & Normalizer"][0]["data"]["main"][0][0]["json"]
    assert norm_data.get("query") == query, f"Normalized query mismatch: {norm_data.get('query')}"
    print(f"  PASS: Query Input & Normalizer processed target query.")

    # Verify Greeting Classifier routed to non-greeting
    classifier_data = run_data["Greeting Classifier"][0]["data"]["main"][0][0]["json"]
    assert classifier_data.get("is_greeting") is False, "Classifier incorrectly flagged query as greeting!"
    print(f"  PASS: Greeting Classifier correctly identified non-greeting query.")

    # Verify Query Embedder and Vector Validation
    embed_data = run_data["Ollama Query Embedder"][0]["data"]["main"][0][0]["json"]
    raw_vector = embed_data.get("embedding")
    assert isinstance(raw_vector, list), "Ollama Query Embedder output 'embedding' is not a list"
    assert len(raw_vector) == 1024, f"Ollama embedding dimension mismatch: {len(raw_vector)} (expected 1024)"

    vec_data = run_data["Validate Query Vector"][0]["data"]["main"][0][0]["json"]
    assert vec_data.get("embedding_dimension") == 1024, f"Validated dimension mismatch: {vec_data.get('embedding_dimension')}"
    query_vector_str = vec_data.get("query_vector_str")
    assert isinstance(query_vector_str, str) and query_vector_str.startswith("[") and query_vector_str.endswith("]"), "Invalid query_vector_str format"

    # Parse query_vector_str and verify exactly 1,024 finite numeric values
    parsed_vector = json.loads(query_vector_str)
    assert isinstance(parsed_vector, list), "Parsed query_vector_str is not a list"
    assert len(parsed_vector) == 1024, f"Parsed query_vector_str dimension mismatch: {len(parsed_vector)} (expected 1024)"
    for idx, val in enumerate(parsed_vector):
        assert isinstance(val, (int, float)), f"Element {idx} in query_vector_str is non-numeric: {type(val)}"
        assert not (math.isnan(val) or math.isinf(val)), f"Element {idx} in query_vector_str is NaN or Inf"
    print(f"  PASS: Query embedded and validated as valid 1,024-dimensional vector.")

    # Verify Framework Stream Retrieval
    fw_tasks = run_data["Retrieve Framework Stream"][0]["data"]["main"][0]
    fw_rows = [item["json"] for item in fw_tasks if "id" in item.get("json", {})]
    print(f"  Framework stream returned {len(fw_rows)} rows:")
    for r in fw_rows:
        sim = float(r.get("similarity", 0.0))
        st = r.get("stream_type")
        sid = r.get("session_id")
        print(f"    - [{st}] session={sid}, similarity={sim:.4f}")
        assert st == "framework", f"Framework stream returned non-framework row: {st}"
        assert sim >= 0.70, f"Framework similarity threshold violated: {sim:.4f} < 0.70"
    assert len(fw_rows) >= 1, "TC-02 requires at least 1 framework match ('Completion with Integrity')!"
    assert len(fw_rows) <= 2, f"Framework stream exceeded LIMIT 2: {len(fw_rows)}"
    # Provenance verification: session_id must be TEST-SES-101
    assert any("TEST-SES-101" in r.get("session_id", "") for r in fw_rows), "Expected match from TEST-SES-101!"
    print("  PASS: Framework stream retrieved qualifying framework chunk(s) (similarity >= 0.70, LIMIT 2).")

    # Verify Voice Stream Retrieval
    voice_tasks = run_data["Retrieve Voice Stream"][0]["data"]["main"][0]
    voice_rows = [item["json"] for item in voice_tasks if "id" in item.get("json", {})]
    print(f"  Voice stream returned {len(voice_rows)} rows:")
    for r in voice_rows:
        sim = float(r.get("similarity", 0.0))
        st = r.get("stream_type")
        sid = r.get("session_id")
        print(f"    - [{st}] session={sid}, similarity={sim:.4f}")
        assert st == "voice_sample", f"Voice stream returned non-voice row: {st}"
        assert sim >= 0.65, f"Voice similarity threshold violated: {sim:.4f} < 0.65"
    assert len(voice_rows) <= 2, f"Voice stream exceeded LIMIT 2: {len(voice_rows)}"
    print("  PASS: Voice stream independently evaluated (similarity >= 0.65, LIMIT 2).")

    # Verify Aggregation & Gate Results
    agg_data = run_data["Aggregate & Gate Results"][0]["data"]["main"][0][0]["json"]
    total_qualifying = agg_data.get("total_qualifying_chunks", 0)
    fw_count = agg_data.get("framework_count", 0)
    voice_count = agg_data.get("voice_count", 0)
    assert total_qualifying > 0, "Hard gate violation: total_qualifying_chunks must be > 0"
    assert fw_count == len(fw_rows), f"Framework count mismatch: {fw_count} vs {len(fw_rows)}"
    assert voice_count == len(voice_rows), f"Voice count mismatch: {voice_count} vs {len(voice_rows)}"
    assert agg_data.get("has_qualifying_results") is True, f"Gate status mismatch: {agg_data.get('has_qualifying_results')}"
    print(f"  PASS: Aggregation node correctly passed hard gate (qualifying chunks: {total_qualifying}).")

    # Verify Format Final Response
    final_task = run_data["Format Final Response"][0]["data"]["main"][0][0]["json"]
    response_text = final_task.get("response", "")
    assert len(response_text) > 20, "Final response text is empty or too short!"
    meta = final_task.get("retrieval_metadata", {})
    assert meta.get("gate_status") == "PASSED_THRESHOLD", f"Final metadata gate_status mismatch: {meta.get('gate_status')}"
    assert meta.get("llm_invoked") is True, "Final metadata llm_invoked must be true"
    assert "Ollama Query Embedder" in executed_nodes, "Ollama Query Embedder must be in executed_nodes"
    assert "Retrieve Framework Stream" in executed_nodes, "Retrieve Framework Stream must be in executed_nodes"
    print(f"\n[GROUNDED RESPONSE GENERATED]:\n{response_text[:300]}...\n")
    print(f"  Metadata: {json.dumps(meta, indent=2)}")

    # 5. Post-execution Safety Checks
    print("\n[POSTFLIGHT] Checking PostgreSQL row counts after execution...")
    counts_post = get_db_counts()
    print(f"  knowledge_vault:    {counts_post[0]} (pre: {counts_pre[0]})")
    print(f"  rejected_meetings:  {counts_post[1]} (pre: {counts_pre[1]})")
    assert counts_pre == counts_post, f"DATABASE MUTATION DETECTED! Pre: {counts_pre}, Post: {counts_post}"
    print("  PASS: Zero database mutations confirmed.")

    print("\n[POSTFLIGHT] Checking workflow active state...")
    wf_post = verify_workflow_state(TARGET_WORKFLOW_ID)
    assert wf_post.get("active") is False, "Workflow became active unexpectedly!"
    print("  PASS: Workflow active state remains False.")

    # 6. Generate Stage 6.2C Runtime Test Report
    report = {
        "stage": "Stage 6.2C — Controlled Runtime Retrieval Testing",
        "phase": "TC-02 Framework Retrieval Only",
        "status": "PASS",
        "execution_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workflow_id": TARGET_WORKFLOW_ID,
        "workflow_name": wf_post.get("name"),
        "workflow_active_state": {
            "before_test": False,
            "after_test": False
        },
        "database_counts": {
            "knowledge_vault_before": counts_pre[0],
            "knowledge_vault_after": counts_post[0],
            "rejected_meetings_before": counts_pre[1],
            "rejected_meetings_after": counts_post[1],
            "mutations": 0
        },
        "test_results": {
            "TC-02": {
                "name": "Framework Retrieval Runtime Test",
                "input_query": query,
                "status": "PASS",
                "execution_id": execution_id,
                "duration_seconds": round(duration, 2),
                "executed_nodes": executed_nodes,
                "prohibited_nodes_executed": [],
                "network_calls": {
                    "ollama_embedding_called": True,
                    "postgresql_queried": True,
                    "ollama_generation_called": True
                },
                "retrieval_verification": {
                    "framework_stream": {
                        "count": len(fw_rows),
                        "threshold": ">= 0.70",
                        "limit": 2,
                        "qualifying_rows": [
                            {"id": r.get("id"), "session_id": r.get("session_id"), "similarity": float(r.get("similarity", 0))}
                            for r in fw_rows
                        ]
                    },
                    "voice_stream": {
                        "count": len(voice_rows),
                        "threshold": ">= 0.65",
                        "limit": 2,
                        "qualifying_rows": [
                            {"id": r.get("id"), "session_id": r.get("session_id"), "similarity": float(r.get("similarity", 0))}
                            for r in voice_rows
                        ]
                    },
                    "total_qualifying_chunks": total_qualifying,
                    "hard_gate_passed": True
                },
                "final_response": response_text,
                "retrieval_metadata": meta,
                "evidence_file": result_path
            }
        },
        "remaining_tests_status": {
            "TC-03_to_TC-10": "PAUSED_PENDING_APPROVAL"
        },
        "files_created_or_modified": [
            "scripts/tc02_execution_result.json",
            "scripts/stage6_2c_runtime_test_report.json"
        ]
    }

    report_path = "scripts/stage6_2c_runtime_test_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\n[REPORT] Saved test report to {report_path}")
    print("\n>>> TC-02 RUNTIME TEST COMPLETED WITH FULL PASS <<<")
    return True

if __name__ == '__main__':
    mode = True
    cli_query = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--preflight-only':
            mode = False
        elif args[i] == '--query' and i + 1 < len(args):
            cli_query = args[i + 1]
            i += 1
        elif args[i].startswith('--query='):
            cli_query = args[i].split('=', 1)[1]
        i += 1
    run_tc02(execute_mode=mode, query=cli_query)
