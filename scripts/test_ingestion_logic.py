import json
import os
import sys

def sample_turns(transcript):
    """
    Applies the turn sampling rule:
    - <=60 turns: use all original turns unchanged.
    - >60 turns: first 40 plus last 20 using original indexes without duplication.
    Preserves original order, speaker names, timestamps, and text.
    """
    total = len(transcript)
    if total <= 60:
        return [dict(t, original_index=i) for i, t in enumerate(transcript)]
    
    first_40 = [(i, transcript[i]) for i in range(40)]
    last_20_start = max(40, total - 20)
    last_20 = [(i, transcript[i]) for i in range(last_20_start, total)]
    
    combined = first_40 + [item for item in last_20 if item[0] >= 40]
    return [dict(t, original_index=i) for i, t in combined]

def validate_classification(llm_output_raw):
    """
    Strict classification parser:
    - Only accept Client Coaching with confidence >= 0.80.
    - Malformed JSON, missing fields, invalid meeting types, or invalid confidence values
      must result in confidence 0.0 and rejection.
    - Record explicit rejection reason.
    """
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
    """
    Extracts voice stream according to strict requirements:
    - Exact coach identity: Dr. Sara Hegy.
    - Include only her actual spoken dialogue, verbatim.
    - Never include client speech.
    - Combine only consecutive coach turns. Never merge across client turns.
    - Preserve original wording and source timestamps.
    - Target 400-700 characters where possible.
    - Preserve shorter chunks without padding, paraphrasing or fabrication.
    """
    COACH_NAME = "Dr. Sara Hegy"
    chunks = []
    
    # First, group strictly consecutive coach turns
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
        # If there's 1 turn:
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
            # Try combining consecutive turns up to ~700 chars
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
                    # Emit current
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

if __name__ == "__main__":
    print("Running Ingestion Logic Verification...")
    
    # 1. Test <=60 turns
    short_turns = [{"speaker": "A", "text": f"T{i}", "timestamp": "00:00:00"} for i in range(25)]
    sampled_short = sample_turns(short_turns)
    assert len(sampled_short) == 25, f"Expected 25, got {len(sampled_short)}"
    assert [x["original_index"] for x in sampled_short] == list(range(25))
    print("PASS: <=60 turn sampling preserves all turns unchanged.")
    
    # 2. Test >60 turns with synthetic fixture
    synth_path = os.path.join("tests", "fixtures", "synthetic_long_transcript.json")
    with open(synth_path, "r", encoding="utf-8") as f:
        synth_data = json.load(f)
    synth_sampled = sample_turns(synth_data["transcript"])
    assert len(synth_sampled) == 60, f"Expected 60, got {len(synth_sampled)}"
    first_40_idx = [x["original_index"] for x in synth_sampled[:40]]
    last_20_idx = [x["original_index"] for x in synth_sampled[40:]]
    assert first_40_idx == list(range(40)), f"First 40 mismatch: {first_40_idx}"
    assert last_20_idx == list(range(50, 70)), f"Last 20 mismatch: {last_20_idx}"
    print("PASS: >60 turn sampling selects first 40 and last 20 without duplication.")
    
    # 3. Test Classification Validator
    # Malformed JSON
    res = validate_classification("not a json")
    assert res["is_accepted"] is False and res["confidence_score"] == 0.0 and "Malformed" in res["rejection_reason"]
    # Invalid meeting type
    res = validate_classification('{"meeting_type": "InvalidType", "confidence_score": 0.95, "summary": "test"}')
    assert res["is_accepted"] is False and res["confidence_score"] == 0.0
    # Invalid confidence
    res = validate_classification('{"meeting_type": "Client Coaching", "confidence_score": 1.5, "summary": "test"}')
    assert res["is_accepted"] is False and res["confidence_score"] == 0.0
    # Low confidence
    res = validate_classification('{"meeting_type": "Client Coaching", "confidence_score": 0.79, "summary": "test"}')
    assert res["is_accepted"] is False and "Low confidence" in res["rejection_reason"]
    # Valid non-coaching
    res = validate_classification('{"meeting_type": "Internal Operations", "confidence_score": 0.99, "summary": "test"}')
    assert res["is_accepted"] is False and "Non-coaching" in res["rejection_reason"]
    # Valid Client Coaching
    res = validate_classification('{"meeting_type": "Client Coaching", "confidence_score": 0.85, "summary": "test"}')
    assert res["is_accepted"] is True and res["confidence_score"] == 0.85
    print("PASS: Classification validation and strict gating pass all edge cases.")
    
    # 4. Test Voice Extraction on SES-101
    mock_path = os.path.join("data", "mock_transcripts.json")
    with open(mock_path, "r", encoding="utf-8") as f:
        mocks = json.load(f)
    ses101 = next(m for m in mocks if m["id"] == "SES-101")
    ses101_voice = extract_voice_samples(ses101["transcript"], "SES-101")
    assert len(ses101_voice) == 3, f"Expected 3 voice chunks for SES-101, got {len(ses101_voice)}"
    for v in ses101_voice:
        assert v["metadata"]["speaker"] == "Dr. Sara Hegy"
        assert "Mark" not in v["content"].split()[0] # No client prefix
        assert len(v["content"]) > 0
    print("PASS: Voice extraction on SES-101 contains strictly Dr. Sara Hegy dialogue, verbatim.")
    
    # Check SES-103 has ZERO voice chunks
    ses103 = next(m for m in mocks if m["id"] == "SES-103")
    ses103_voice = extract_voice_samples(ses103["transcript"], "SES-103")
    assert len(ses103_voice) == 0, f"Expected 0 voice chunks for SES-103, got {len(ses103_voice)}"
    print("PASS: SES-103 has zero voice chunks.")
    
    print("\nALL INGESTION LOGIC UNIT TESTS PASSED SUCCESSFULLY.")
