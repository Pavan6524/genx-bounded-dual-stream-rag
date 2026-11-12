import json
import os
import sys
import subprocess
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
COACH_NAME = "Dr. Sara Hegy"

def call_ollama_generate(model, prompt, format_json=True):
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0}
    }
    if format_json:
        payload["format"] = "json"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res["response"]

def call_ollama_embed(model, text):
    url = f"{OLLAMA_URL}/api/embeddings"
    payload = {"model": model, "prompt": text}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res["embedding"]

def sample_turns(transcript):
    total = len(transcript)
    if total <= 60:
        return [dict(t, original_index=i) for i, t in enumerate(transcript)]
    first_40 = [(i, transcript[i]) for i in range(40)]
    last_20_start = max(40, total - 20)
    last_20 = [(i, transcript[i]) for i in range(last_20_start, total)]
    combined = first_40 + [item for item in last_20 if item[0] >= 40]
    return [dict(t, original_index=i) for i, t in combined]

def validate_classification(llm_output_raw):
    valid_meeting_types = {"Client Coaching", "Internal Operations", "Sales Discovery", "Other"}
    try:
        data = json.loads(llm_output_raw)
    except Exception as e:
        return {
            "meeting_type": "Other",
            "confidence_score": 0.0,
            "summary": "Malformed JSON output from classifier",
            "is_accepted": False,
            "rejection_reason": f"Malformed classification JSON: {str(e)}"
        }
    
    if not isinstance(data, dict):
        return {
            "meeting_type": "Other",
            "confidence_score": 0.0,
            "summary": "Output is not a JSON object",
            "is_accepted": False,
            "rejection_reason": "Output is not a JSON object"
        }
        
    m_type = data.get("meeting_type")
    c_score = data.get("confidence_score")
    summary = data.get("summary", "")
    
    if m_type not in valid_meeting_types:
        return {
            "meeting_type": "Other",
            "confidence_score": 0.0,
            "summary": str(summary),
            "is_accepted": False,
            "rejection_reason": f"Invalid meeting_type: '{m_type}'"
        }
        
    try:
        c_score = float(c_score)
        if c_score < 0.0 or c_score > 1.0:
            raise ValueError("Out of range")
    except Exception:
        return {
            "meeting_type": m_type,
            "confidence_score": 0.0,
            "summary": str(summary),
            "is_accepted": False,
            "rejection_reason": f"Invalid confidence_score: '{c_score}'"
        }
        
    if m_type != "Client Coaching":
        return {
            "meeting_type": m_type,
            "confidence_score": c_score,
            "summary": str(summary),
            "is_accepted": False,
            "rejection_reason": f"Non-coaching meeting type: {m_type}"
        }
        
    if c_score < 0.80:
        return {
            "meeting_type": m_type,
            "confidence_score": c_score,
            "summary": str(summary),
            "is_accepted": False,
            "rejection_reason": f"Low confidence: {c_score:.2f} < 0.80 threshold"
        }
        
    return {
        "meeting_type": m_type,
        "confidence_score": c_score,
        "summary": str(summary),
        "is_accepted": True,
        "rejection_reason": None
    }

def extract_voice_samples(transcript, session_id):
    chunks = []
    consecutive_groups = []
    current_group = []
    for turn in transcript:
        if turn.get("speaker") == COACH_NAME:
            current_group.append(turn)
        else:
            if current_group:
                consecutive_groups.append(current_group)
                current_group = []
    if current_group:
        consecutive_groups.append(current_group)
        
    for group in consecutive_groups:
        if len(group) == 1:
            t = group[0]
            chunks.append({
                "session_id": session_id,
                "stream_type": "voice_sample",
                "content": t["text"],
                "metadata": {
                    "speaker": COACH_NAME,
                    "session_id": session_id,
                    "source_timestamps": [t["timestamp"]],
                    "char_count": len(t["text"]),
                    "turn_count": 1
                }
            })
        else:
            combined_text = []
            combined_timestamps = []
            current_len = 0
            for t in group:
                text = t["text"]
                added_len = len(text) + (1 if combined_text else 0)
                if current_len + added_len <= 700 or not combined_text:
                    combined_text.append(text)
                    combined_timestamps.append(t["timestamp"])
                    current_len += added_len
                else:
                    c_str = "\n".join(combined_text)
                    chunks.append({
                        "session_id": session_id,
                        "stream_type": "voice_sample",
                        "content": c_str,
                        "metadata": {
                            "speaker": COACH_NAME,
                            "session_id": session_id,
                            "source_timestamps": list(combined_timestamps),
                            "char_count": len(c_str),
                            "turn_count": len(combined_text)
                        }
                    })
                    combined_text = [text]
                    combined_timestamps = [t["timestamp"]]
                    current_len = len(text)
            if combined_text:
                c_str = "\n".join(combined_text)
                chunks.append({
                    "session_id": session_id,
                    "stream_type": "voice_sample",
                    "content": c_str,
                    "metadata": {
                        "speaker": COACH_NAME,
                        "session_id": session_id,
                        "source_timestamps": list(combined_timestamps),
                        "char_count": len(c_str),
                        "turn_count": len(combined_text)
                    }
                })
    return chunks

def extract_frameworks(transcript, session_id):
    formatted_dialogue = "\n".join([f"{t['speaker']} [{t['timestamp']}]: {t['text']}" for t in transcript])
    prompt = f"""Extract substantive coaching frameworks, principles, diagnostic rules, and handoff mechanisms explicitly discussed in this transcript.
Never invent concepts, names, definitions, or unsupported rules. Preserve source timestamps.

Transcript:
{formatted_dialogue}

Return JSON with this schema:
{{
  "frameworks": [
    {{
      "name": "Framework or Principle Name",
      "core_mechanism": "Exact mechanism or diagnostic rule discussed",
      "definition": "Definition or conceptual explanation",
      "application": "How it is applied",
      "source_timestamps": ["00:00:00"]
    }}
  ]
}}"""
    resp = call_ollama_generate("llama3.2:1b", prompt, format_json=True)
    chunks = []
    try:
        parsed = json.loads(resp)
        f_list = parsed.get("frameworks", [])
        for f in f_list:
            content_parts = []
            if f.get("name"):
                content_parts.append(f"Framework: {f['name']}")
            if f.get("definition"):
                content_parts.append(f"Definition: {f['definition']}")
            if f.get("core_mechanism"):
                content_parts.append(f"Mechanism: {f['core_mechanism']}")
            if f.get("application"):
                content_parts.append(f"Application: {f['application']}")
            
            c_text = "\n".join(content_parts)
            chunks.append({
                "session_id": session_id,
                "stream_type": "framework",
                "content": c_text,
                "metadata": {
                    "framework_name": f.get("name", "Coaching Framework"),
                    "session_id": session_id,
                    "source_timestamps": f.get("source_timestamps", [])
                }
            })
    except Exception as e:
        print(f"Warning: parsing frameworks: {e}")
        
    return chunks

def run_psql(sql):
    cmd = ["docker", "exec", "-i", "genx-postgres", "psql", "-U", "genx", "-d", "genx_rag", "-t", "-A"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = proc.communicate(input=sql)
    if proc.returncode != 0:
        raise RuntimeError(f"psql error: {stderr}")
    return stdout.strip()

def test_isolated_transactional_ingestion(dry_run_with_rollback=True):
    print("\n--- SAFE TRANSACTIONAL VERIFICATION (Isolated Session IDs) ---")
    print(f"Transactional Rollback Mode: {dry_run_with_rollback}")
    print("Reading data/mock_transcripts.json in READ-ONLY mode...")
    
    with open("data/mock_transcripts.json", "r", encoding="utf-8") as f:
        sessions = json.load(f)
        
    test_sessions = []
    for s in sessions:
        test_s = dict(s)
        test_s["id"] = f"TEST-{s['id']}"
        test_sessions.append(test_s)
        
    for s in test_sessions:
        sid = s["id"]
        assert sid.startswith("TEST-"), f"SAFETY VIOLATION: {sid} does not have TEST- prefix!"
        
        turns = sample_turns(s["transcript"])
        dialogue_text = "\n".join([f"{t['speaker']}: {t['text']}" for t in turns])
        
        classify_prompt = f"""You are an expert meeting classification firewall for GenX Leadership Academy.

Transcript:
{dialogue_text}

Classification Rules:
1. "Internal Operations" (reject): Discussions about technical infrastructure, code, bugs, webhooks, database migrations, or git. Dr. Sara Hegy is absent.
2. "Sales Discovery" (reject): Sales Rep or commercial discussions about pricing, retainer fees ($8,500), budgets, contract terms, or pilot proposals. Dr. Sara Hegy is absent.
3. "Client Coaching" (accept): 1-on-1 executive coaching sessions where Dr. Sara Hegy is present and coaching an executive client (e.g. Mark D. or Elena R.) on leadership, management, or executive feedback. If Dr. Sara Hegy is absent, this can NEVER be Client Coaching.
4. "Other" (reject): Any meeting that does not match the above.

Instructions:
- Write a 1-sentence summary first.
- Choose the exact meeting_type matching the rules above.
- Provide a numeric confidence_score between 0.0 and 1.0 reflecting your certainty.

Output valid JSON with keys "summary", "meeting_type", and "confidence_score":
{{
  "summary": "...",
  "meeting_type": "...",
  "confidence_score": 0.95
}}"""
        raw_class = call_ollama_generate("llama3.2:1b", classify_prompt, format_json=True)
        validated = validate_classification(raw_class)
        print(f"Session {sid}: Classified as '{validated['meeting_type']}' (conf: {validated['confidence_score']}), Accepted: {validated['is_accepted']}")
        
        if not validated["is_accepted"]:
            summary_esc = validated["summary"].replace("'", "''")
            raw_esc = dialogue_text.replace("'", "''")
            reason_esc = validated["rejection_reason"].replace("'", "''")
            
            sql = f"""
            BEGIN;
            DELETE FROM rejected_meetings WHERE session_id = '{sid}';
            DELETE FROM knowledge_vault WHERE session_id = '{sid}';
            INSERT INTO rejected_meetings (session_id, meeting_type, confidence_score, summary, raw_transcript, rejection_reason)
            VALUES ('{sid}', '{validated["meeting_type"]}', {validated["confidence_score"]}, '{summary_esc}', '{raw_esc}', '{reason_esc}');
            {"ROLLBACK;" if dry_run_with_rollback else "COMMIT;"}
            """
            try:
                run_psql(sql)
                print(f"  -> Verified atomic archive transaction for {sid} (NO EMBEDDINGS) [ROLLED BACK].")
            except Exception as e:
                run_psql("ROLLBACK;")
                raise e
        else:
            fw_chunks = extract_frameworks(s["transcript"], sid)
            voice_chunks = extract_voice_samples(s["transcript"], sid)
            
            fw_records = []
            for c in fw_chunks:
                emb = call_ollama_embed("bge-m3", c["content"])
                assert len(emb) == 1024, f"Embedding dimension mismatch: {len(emb)}"
                fw_records.append((c, emb))
                
            voice_records = []
            for c in voice_chunks:
                emb = call_ollama_embed("bge-m3", c["content"])
                assert len(emb) == 1024, f"Embedding dimension mismatch: {len(emb)}"
                voice_records.append((c, emb))
                
            sql_parts = ["BEGIN;"]
            sql_parts.append(f"DELETE FROM knowledge_vault WHERE session_id = '{sid}';")
            sql_parts.append(f"DELETE FROM rejected_meetings WHERE session_id = '{sid}';")
            
            for c, emb in fw_records:
                c_esc = c["content"].replace("'", "''")
                m_esc = json.dumps(c["metadata"]).replace("'", "''")
                emb_str = "[" + ",".join(map(str, emb)) + "]"
                sql_parts.append(f"""INSERT INTO knowledge_vault (session_id, stream_type, content, metadata, embedding)
                VALUES ('{sid}', 'framework', '{c_esc}', '{m_esc}'::jsonb, '{emb_str}'::vector);""")
                
            for c, emb in voice_records:
                c_esc = c["content"].replace("'", "''")
                m_esc = json.dumps(c["metadata"]).replace("'", "''")
                emb_str = "[" + ",".join(map(str, emb)) + "]"
                sql_parts.append(f"""INSERT INTO knowledge_vault (session_id, stream_type, content, metadata, embedding)
                VALUES ('{sid}', 'voice_sample', '{c_esc}', '{m_esc}'::jsonb, '{emb_str}'::vector);""")
                
            sql_parts.append("ROLLBACK;" if dry_run_with_rollback else "COMMIT;")
            full_sql = "\n".join(sql_parts)
            try:
                run_psql(full_sql)
                print(f"  -> Verified atomic vault transaction for {sid} ({len(fw_records)} fw chunks, {len(voice_records)} voice chunks) [ROLLED BACK].")
            except Exception as e:
                run_psql("ROLLBACK;")
                raise e

    print("\n--- SAFETY AUDIT: VERIFYING POST-EXECUTION DATABASE STATE ---")
    test_kv_out = run_psql("SELECT COUNT(*) FROM knowledge_vault WHERE session_id LIKE 'TEST-%';")
    test_rej_out = run_psql("SELECT COUNT(*) FROM rejected_meetings WHERE session_id LIKE 'TEST-%';")
    
    test_kv_count = int(test_kv_out.strip())
    test_rej_count = int(test_rej_out.strip())
    
    print(f"Remaining TEST-* records in knowledge_vault (must be 0): {test_kv_count}")
    print(f"Remaining TEST-* records in rejected_meetings (must be 0): {test_rej_count}")
    assert test_kv_count == 0, f"Test records persisted in knowledge_vault: {test_kv_count}"
    assert test_rej_count == 0, f"Test records persisted in rejected_meetings: {test_rej_count}"

    prod_kv_out = run_psql("SELECT COUNT(*) FROM knowledge_vault WHERE session_id IN ('SES-101','SES-102','SES-103','SES-104');")
    prod_rej_out = run_psql("SELECT COUNT(*) FROM rejected_meetings WHERE session_id IN ('SES-101','SES-102','SES-103','SES-104');")
    prod_kv_count = int(prod_kv_out.strip())
    prod_rej_count = int(prod_rej_out.strip())
    
    print(f"SES-101..104 in knowledge_vault: {prod_kv_count}")
    print(f"SES-101..104 in rejected_meetings: {prod_rej_count}")
    print("Database verification passed: ZERO residue, 100% rollback confirmed.")

if __name__ == "__main__":
    test_isolated_transactional_ingestion(dry_run_with_rollback=True)
