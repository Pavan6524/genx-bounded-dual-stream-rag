import subprocess
import json
import time
import sys
import os
import urllib.request

WORKFLOW_ID = "TSvKBGpM9nK7eb3U"
INGESTION_WORKFLOW_ID = "IlBw4RRELuh02Akm"

def check_preconditions():
    print("=" * 70)
    print("TASK 8: PRE-EXECUTION HEALTH CHECKS")
    print("=" * 70)

    # 1. Database counts
    res = subprocess.run(
        ['docker', 'exec', 'genx-postgres', 'psql', '-U', 'genx', '-d', 'genx_rag', '-t', '-A', '-c',
         "SELECT count(*) FROM knowledge_vault UNION ALL SELECT count(*) FROM rejected_meetings;"],
        capture_output=True, text=True, check=True
    )
    counts = [int(x.strip()) for x in res.stdout.strip().split('\n') if x.strip()]
    print(f"PostgreSQL knowledge_vault count:   {counts[0]} (expected: 16)")
    print(f"PostgreSQL rejected_meetings count: {counts[1]} (expected: 4)")
    assert counts[0] == 16, f"Database assertion failed: knowledge_vault has {counts[0]} rows (expected 8)"
    assert counts[1] == 4, f"Database assertion failed: rejected_meetings has {counts[1]} rows (expected 2)"

    # 2. Workflow states
    for wfid, name in [(WORKFLOW_ID, "Retrieval Workflow"), (INGESTION_WORKFLOW_ID, "Ingestion Workflow")]:
        res = subprocess.run(
            ['docker', 'exec', 'genx-n8n', 'n8n', 'export:workflow', f'--id={wfid}'],
            capture_output=True, text=True, check=True
        )
        stdout = res.stdout.strip()
        idx = stdout.find('{')
        assert idx != -1, f"Failed to export workflow {wfid}"
        decoder = json.JSONDecoder()
        wf_data, _ = decoder.raw_decode(stdout[idx:])
        if isinstance(wf_data, list):
            wf_data = wf_data[0]
        assert wf_data.get("active") is False, f"Workflow {wfid} ({name}) is active! Must be false."
        print(f"{name} ({wfid}): INACTIVE (active: false) [PASS]")

    # 3. Ollama reachability
    req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        tags_data = json.loads(resp.read().decode('utf-8'))
        models = [m['name'] for m in tags_data.get('models', [])]
        print(f"Ollama reachable. Available models: {models}")
        assert any('bge-m3' in m for m in models), "bge-m3 model missing from Ollama"
        assert any('llama3.2' in m for m in models), "llama3.2 model missing from Ollama"

    print("Pre-execution checks: ALL PASSED (SYSTEM READY)\n")
    return counts

def run_test_case(test_id, query, expected_gate_branch, require_llm=True):
    print("=" * 70)
    print(f"RUNNING {test_id}: \"{query}\"")
    print("=" * 70)

    # Pre-execution DB counts
    counts_pre = check_db_counts()

    # Execute workflow via docker exec with TC runner bridge
    cmd = [
        'docker', 'exec',
        '-e', 'N8N_RUNNERS_BROKER_PORT=5699',
        '-e', 'N8N_BLOCK_ENV_ACCESS_IN_NODE=false',
        '-e', 'NODE_OPTIONS=--require=/data/tc_runner_bridge.js',
        '-e', f'GENX_TEST_QUERY={query}',
        'genx-n8n',
        'n8n', 'execute', f'--id={WORKFLOW_ID}'
    ]
    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True)
    duration = time.time() - t0
    print(f"Subprocess finished in {duration:.2f}s with returncode {res.returncode}")

    stdout_raw = res.stdout or ""
    stderr_raw = res.stderr or ""

    # Save raw outputs
    with open(f"scripts/{test_id.lower()}_raw_stdout.log", "w", encoding="utf-8") as f:
        f.write(stdout_raw)
    with open(f"scripts/{test_id.lower()}_raw_stderr.log", "w", encoding="utf-8") as f:
        f.write(stderr_raw)

    assert res.returncode == 0, f"n8n execute returned non-zero code {res.returncode}"

    # Extract JSON execution trace
    idx = stdout_raw.find('{')
    assert idx != -1, "Could not find JSON trace in stdout"
    decoder = json.JSONDecoder()
    exec_data, _ = decoder.raw_decode(stdout_raw[idx:])

    trace_file = f"scripts/{test_id.lower()}_execution_result.json"
    with open(trace_file, "w", encoding="utf-8") as f:
        json.dump(exec_data, f, indent=2)
    print(f"Saved execution trace to {trace_file}")

    run_data = exec_data["data"]["resultData"]["runData"]
    executed_nodes = list(run_data.keys())
    print(f"Executed Nodes ({len(executed_nodes)}): {executed_nodes}")

    # Inspect Framework Stream
    fw_tasks = run_data.get("Retrieve Framework Stream", [{}])[0].get("data", {}).get("main", [[]])[0]
    fw_rows = [item["json"] for item in fw_tasks if "id" in item.get("json", {})]

    # Inspect Voice Stream
    voice_tasks = run_data.get("Retrieve Voice Stream", [{}])[0].get("data", {}).get("main", [[]])[0]
    voice_rows = [item["json"] for item in voice_tasks if "id" in item.get("json", {})]

    print(f"Framework Stream Rows ({len(fw_rows)}):")
    for r in fw_rows:
        print(f"  - ID {r.get('id')} ({r.get('session_id')}) -> sim: {r.get('similarity')}")
    print(f"Voice Stream Rows ({len(voice_rows)}):")
    for r in voice_rows:
        print(f"  - ID {r.get('id')} ({r.get('session_id')}) -> sim: {r.get('similarity')}")

    # Inspect Hard Gate
    hard_gate_main = run_data.get("Hard Gate (Has Results?)", [{}])[0].get("data", {}).get("main", [[], []])
    has_results_branch = len(hard_gate_main[0]) if len(hard_gate_main) > 0 else 0
    zero_results_branch = len(hard_gate_main[1]) if len(hard_gate_main) > 1 else 0

    print(f"Hard Gate branches: [has_results: {has_results_branch}, zero_results: {zero_results_branch}]")

    final_response = None
    retrieval_metadata = None
    llm_invoked = False

    if expected_gate_branch == "ZERO_RESULTS":
        assert zero_results_branch > 0, "Expected zero_results branch to receive item"
        assert "Return Zero Result Output" in executed_nodes, "Return Zero Result Output must be in executed_nodes"
        assert "Ollama Grounded Generator" not in executed_nodes, "Ollama Grounded Generator must NOT be executed"
        zr_out = run_data["Return Zero Result Output"][0]["data"]["main"][0][0]["json"]
        final_response = zr_out.get("response")
        assert final_response == "No documented coaching frameworks match this topic.", f"Fallback response mismatch: '{final_response}'"
        print(f"Exact Fallback Output Verified: \"{final_response}\" [PASS]")
    else:
        assert has_results_branch > 0, "Expected has_results branch to receive item"
        assert "Ollama Grounded Generator" in executed_nodes, "Ollama Grounded Generator must be in executed_nodes"
        assert "Format Final Response" in executed_nodes, "Format Final Response must be in executed_nodes"
        llm_invoked = True
        final_out = run_data["Format Final Response"][0]["data"]["main"][0][0]["json"]
        final_response = final_out.get("response")
        retrieval_metadata = final_out.get("retrieval_metadata")
        print(f"Final Response Generated ({len(final_response or '')} chars):\n{final_response[:200]}...\n")

    # Post-execution DB counts
    counts_post = check_db_counts()
    assert counts_pre == counts_post, f"Database mutation detected! Pre: {counts_pre}, Post: {counts_post}"
    print("Post-execution database counts verified unchanged (0 mutations).")

    report = {
        "test_id": test_id,
        "query": query,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_seconds": round(duration, 2),
        "return_code": res.returncode,
        "executed_nodes": executed_nodes,
        "framework_stream": {
            "count": len(fw_rows),
            "rows": fw_rows
        },
        "voice_stream": {
            "count": len(voice_rows),
            "rows": voice_rows
        },
        "hard_gate_branch_selected": "ZERO_RESULTS" if zero_results_branch > 0 else "HAS_RESULTS",
        "llm_invoked": llm_invoked,
        "final_response": final_response,
        "retrieval_metadata": retrieval_metadata,
        "evidence_files": {
            "trace": trace_file,
            "stdout": f"scripts/{test_id.lower()}_raw_stdout.log",
            "stderr": f"scripts/{test_id.lower()}_raw_stderr.log"
        },
        "status": "PASS"
    }

    report_path = f"scripts/{test_id.lower()}_runtime_test_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Saved test report to {report_path}\n")
    return report

def check_db_counts():
    res = subprocess.run(
        ['docker', 'exec', 'genx-postgres', 'psql', '-U', 'genx', '-d', 'genx_rag', '-t', '-A', '-c',
         "SELECT count(*) FROM knowledge_vault UNION ALL SELECT count(*) FROM rejected_meetings;"],
        capture_output=True, text=True, check=True
    )
    return [int(x.strip()) for x in res.stdout.strip().split('\n') if x.strip()]

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--preflight':
        check_preconditions()
    elif len(sys.argv) > 2 and sys.argv[1] == '--run':
        test_case = sys.argv[2]
        if test_case == "TC-07":
            run_test_case(
                test_id="TC-07",
                query="What is the optimal fertilizer ratio for growing hydroponic tomatoes in winter?",
                expected_gate_branch="ZERO_RESULTS",
                require_llm=False
            )
        elif test_case == "TC-03":
            run_test_case(
                test_id="TC-03",
                query="Look, Mark, is micromanagement really an ego problem or an information architecture breakdown?",
                expected_gate_branch="HAS_RESULTS",
                require_llm=True
            )
        elif test_case == "TC-04":
            run_test_case(
                test_id="TC-04",
                query="How do top performers use the Completion with Integrity framework and binary exit criteria to eliminate micromanagement?",
                expected_gate_branch="HAS_RESULTS",
                require_llm=True
            )
        elif test_case == "TC-06":
            run_test_case(
                test_id="TC-06",
                query="How does an executive protect cognitive bandwidth and let the architecture absorb ambiguity?",
                expected_gate_branch="HAS_RESULTS",
                require_llm=True
            )
        else:
            print(f"Unknown test case {test_case}")
            sys.exit(1)
    else:
        print("Usage: python scripts/run_task8_tests.py [--preflight | --run <TC-ID>]")
