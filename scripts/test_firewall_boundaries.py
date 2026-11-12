import json
import math

def simulate_validate_classification(raw_response, session_turn_sampler):
    """
    Simulates the exact jsCode logic from the 'Validate Classification' node:
    
    // Strict classification validator
    // Accept only Client Coaching with confidence >= 0.80
    // Malformed JSON, missing fields, or invalid values -> confidence 0.0 and reject
    """
    valid_meeting_types = ['Client Coaching', 'Internal Operations', 'Sales Discovery', 'Other']
    session = dict(session_turn_sampler)

    # 1. JSON parsing
    parsed = None
    try:
        parsed = json.loads(raw_response) if isinstance(raw_response, str) else raw_response
    except Exception as e:
        return {
            **session,
            'meeting_type': 'Other',
            'confidence_score': 0.0,
            'summary': 'Malformed classification JSON from LLM',
            'is_accepted': False,
            'rejection_reason': f"Malformed classification JSON output: {str(e)}"
        }

    if not isinstance(parsed, dict):
        return {
            **session,
            'meeting_type': 'Other',
            'confidence_score': 0.0,
            'summary': 'Classification output is not a JSON object',
            'is_accepted': False,
            'rejection_reason': 'Classification output is not a JSON object'
        }

    meeting_type = parsed.get('meeting_type')
    raw_conf = parsed.get('confidence_score')
    try:
        confidence_score = float(raw_conf) if raw_conf is not None else float('nan')
    except (ValueError, TypeError):
        confidence_score = float('nan')

    summary = parsed.get('summary') if isinstance(parsed.get('summary'), str) else ''

    # 2. Check meeting_type validity
    if meeting_type not in valid_meeting_types:
        return {
            **session,
            'meeting_type': 'Other',
            'confidence_score': 0.0,
            'summary': summary,
            'is_accepted': False,
            'rejection_reason': f"Invalid meeting_type: '{meeting_type}'"
        }

    # 3. Check numeric confidence range [0.0, 1.0]
    if math.isnan(confidence_score) or confidence_score < 0.0 or confidence_score > 1.0:
        return {
            **session,
            'meeting_type': meeting_type,
            'confidence_score': 0.0,
            'summary': summary,
            'is_accepted': False,
            'rejection_reason': f"Invalid confidence_score: '{raw_conf}'"
        }

    # 4. Filter for Client Coaching
    if meeting_type != 'Client Coaching':
        return {
            **session,
            'meeting_type': meeting_type,
            'confidence_score': confidence_score,
            'summary': summary,
            'is_accepted': False,
            'rejection_reason': f"Non-coaching meeting type: {meeting_type}"
        }

    # 5. Threshold gating: confidence >= 0.80
    if confidence_score < 0.80:
        return {
            **session,
            'meeting_type': meeting_type,
            'confidence_score': confidence_score,
            'summary': summary,
            'is_accepted': False,
            'rejection_reason': f"Low confidence: {confidence_score:.2f} < 0.80 threshold"
        }

    # Accepted Client Coaching
    return {
        **session,
        'meeting_type': meeting_type,
        'confidence_score': confidence_score,
        'summary': summary,
        'is_accepted': True,
        'rejection_reason': None
    }


def run_firewall_boundary_tests():
    print("=" * 65)
    print("PHASE 3: FIREWALL CLASSIFICATION BOUNDARY TESTS")
    print("=" * 65)

    base_session = {
        'id': 'TEST-SES-101',
        'title': 'Test Session',
        'dialogue_text': 'Dr. Sara Hegy [00:00:15]: Coaching dialogue...'
    }

    test_cases = [
        # (Case Name, Payload string, Expected is_accepted, Expected meeting_type, Expected conf)
        ("1. Client Coaching, 0.79 (below 0.80 threshold)",
         json.dumps({"summary": "Coaching", "meeting_type": "Client Coaching", "confidence_score": 0.79}),
         False, "Client Coaching", 0.79),

        ("2. Client Coaching, 0.80 (exact threshold)",
         json.dumps({"summary": "Coaching", "meeting_type": "Client Coaching", "confidence_score": 0.80}),
         True, "Client Coaching", 0.80),

        ("3. Client Coaching, 0.95 (high confidence)",
         json.dumps({"summary": "Coaching", "meeting_type": "Client Coaching", "confidence_score": 0.95}),
         True, "Client Coaching", 0.95),

        ("4. Internal Operations, 0.99 (high confidence reject)",
         json.dumps({"summary": "Ops sync", "meeting_type": "Internal Operations", "confidence_score": 0.99}),
         False, "Internal Operations", 0.99),

        ("5. Sales Discovery, 0.99 (high confidence reject)",
         json.dumps({"summary": "Sales call", "meeting_type": "Sales Discovery", "confidence_score": 0.99}),
         False, "Sales Discovery", 0.99),

        ("6. Other meeting type, 0.85",
         json.dumps({"summary": "Unknown", "meeting_type": "Other", "confidence_score": 0.85}),
         False, "Other", 0.85),

        ("7. Missing meeting_type (None)",
         json.dumps({"summary": "Missing type", "confidence_score": 0.95}),
         False, "Other", 0.0),

        ("8. Invalid meeting_type string ('Vendor Pitch')",
         json.dumps({"summary": "Pitch", "meeting_type": "Vendor Pitch", "confidence_score": 0.95}),
         False, "Other", 0.0),

        ("9. Missing confidence_score (None)",
         json.dumps({"summary": "Coaching", "meeting_type": "Client Coaching"}),
         False, "Client Coaching", 0.0),

        ("10. Non-numeric confidence_score ('very high')",
         json.dumps({"summary": "Coaching", "meeting_type": "Client Coaching", "confidence_score": "very high"}),
         False, "Client Coaching", 0.0),

        ("11. Out-of-bounds confidence_score > 1.0 (1.25)",
         json.dumps({"summary": "Coaching", "meeting_type": "Client Coaching", "confidence_score": 1.25}),
         False, "Client Coaching", 0.0),

        ("12. Out-of-bounds confidence_score < 0.0 (-0.1)",
         json.dumps({"summary": "Coaching", "meeting_type": "Client Coaching", "confidence_score": -0.1}),
         False, "Client Coaching", 0.0),

        ("13. Malformed JSON string (unparseable)",
         "{\"summary\": \"broken json...",
         False, "Other", 0.0),

        ("14. Non-object JSON (JSON array instead of object)",
         "[{\"meeting_type\": \"Client Coaching\", \"confidence_score\": 0.95}]",
         False, "Other", 0.0),
    ]

    all_passed = True
    for name, payload, exp_accepted, exp_type, exp_conf in test_cases:
        res = simulate_validate_classification(payload, base_session)
        pass_acc = res['is_accepted'] == exp_accepted
        pass_type = res['meeting_type'] == exp_type
        pass_conf = math.isclose(res['confidence_score'], exp_conf, abs_tol=1e-4)
        
        status = "PASS" if (pass_acc and pass_type and pass_conf) else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"[{status}] {name}")
        if status == "FAIL":
            print(f"       Expected: accepted={exp_accepted}, type={exp_type}, conf={exp_conf}")
            print(f"       Got:      accepted={res['is_accepted']}, type={res['meeting_type']}, conf={res['confidence_score']}, reason={res['rejection_reason']}")
        else:
            reason_info = f" (rejection_reason: '{res['rejection_reason']}')" if not res['is_accepted'] else " (ACCEPTED)"
            print(f"       -> is_accepted={res['is_accepted']}, type={res['meeting_type']}, conf={res['confidence_score']}{reason_info}")

    assert all_passed, "Some boundary tests failed!"
    print("\n>>> ALL 14 FIREWALL BOUNDARY TESTS PASSED SUCCESSFULLY <<<")

if __name__ == '__main__':
    run_firewall_boundary_tests()
