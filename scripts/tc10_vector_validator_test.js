/**
 * GenX Leadership Academy — TC-10 Vector Validator Isolated Unit Test
 * Extracts the exact JavaScript code from 'workflows/gated_retrieval.json'
 * and executes unit test cases against the live node implementation.
 * Zero database calls, zero Ollama calls, zero n8n activation.
 */

const fs = require('fs');
const path = require('path');

function runUnitTests() {
  console.log('=' .repeat(70));
  console.log('TC-10: VECTOR VALIDATOR ISOLATED UNIT TEST');
  console.log('=' .repeat(70));

  // 1. Read live workflow JSON and extract the exact validator jsCode
  const workflowPath = path.join(__dirname, '..', 'workflows', 'gated_retrieval.json');
  const wf = JSON.parse(fs.readFileSync(workflowPath, 'utf8'));
  const validatorNode = wf.nodes.find(n => n.name === 'Validate Query Vector');

  if (!validatorNode || !validatorNode.parameters || !validatorNode.parameters.jsCode) {
    throw new Error("Could not extract 'Validate Query Vector' code from workflows/gated_retrieval.json");
  }

  const validatorCode = validatorNode.parameters.jsCode;
  console.log(`Successfully extracted ${validatorCode.length} bytes of validator code.\n`);

  // Function to run the extracted validator code with simulated n8n context
  function executeValidator(embeddingInput, queryInput = 'Test coaching query') {
    const $input = {
      first: () => ({
        json: {
          embedding: embeddingInput
        }
      })
    };

    const $ = (nodeName) => ({
      first: () => ({
        json: {
          query: queryInput
        }
      })
    });

    // Create function from extracted code
    const validatorFn = new Function('$input', '$', validatorCode);
    return validatorFn($input, $);
  }

  const results = [];

  // Helper to generate a valid 1024-d float vector
  function createValidVector() {
    const vec = new Array(1024);
    for (let i = 0; i < 1024; i++) {
      vec[i] = (Math.sin(i) * 0.1);
    }
    return vec;
  }

  // Test Case 1: Missing embedding
  try {
    executeValidator(null);
    results.push({ case_id: "TC10-1", name: "Missing Embedding", expected: "ERROR", actual: "PASS", pass: false });
  } catch (err) {
    const pass = err.message.includes('missing or not an array');
    results.push({ case_id: "TC10-1", name: "Missing Embedding", expected: "ERROR", actual: `CAUGHT: ${err.message}`, pass });
  }

  // Test Case 2: Non-array embedding
  try {
    executeValidator("not_an_array");
    results.push({ case_id: "TC10-2", name: "Non-array Embedding", expected: "ERROR", actual: "PASS", pass: false });
  } catch (err) {
    const pass = err.message.includes('missing or not an array');
    results.push({ case_id: "TC10-2", name: "Non-array Embedding", expected: "ERROR", actual: `CAUGHT: ${err.message}`, pass });
  }

  // Test Case 3: Incorrect dimensions (512 instead of 1024)
  try {
    const shortVec = new Array(512).fill(0.1);
    executeValidator(shortVec);
    results.push({ case_id: "TC10-3", name: "Incorrect Dimensions (512)", expected: "ERROR", actual: "PASS", pass: false });
  } catch (err) {
    const pass = err.message.includes('dimension is 512, expected 1024');
    results.push({ case_id: "TC10-3", name: "Incorrect Dimensions (512)", expected: "ERROR", actual: `CAUGHT: ${err.message}`, pass });
  }

  // Test Case 4: NaN value
  try {
    const nanVec = createValidVector();
    nanVec[42] = NaN;
    executeValidator(nanVec);
    results.push({ case_id: "TC10-4", name: "NaN Value at Index 42", expected: "ERROR", actual: "PASS", pass: false });
  } catch (err) {
    const pass = err.message.includes('element at index 42 is non-numeric or non-finite');
    results.push({ case_id: "TC10-4", name: "NaN Value at Index 42", expected: "ERROR", actual: `CAUGHT: ${err.message}`, pass });
  }

  // Test Case 5: Positive and Negative Infinity
  try {
    const infVec = createValidVector();
    infVec[100] = Infinity;
    executeValidator(infVec);
    results.push({ case_id: "TC10-5", name: "Infinity Value at Index 100", expected: "ERROR", actual: "PASS", pass: false });
  } catch (err) {
    const pass = err.message.includes('element at index 100 is non-numeric or non-finite');
    results.push({ case_id: "TC10-5", name: "Infinity Value at Index 100", expected: "ERROR", actual: `CAUGHT: ${err.message}`, pass });
  }

  // Test Case 6: Valid 1024-dimensional float vector
  try {
    const validVec = createValidVector();
    const output = executeValidator(validVec);
    const item = output[0].json;
    const pass = item.embedding_dimension === 1024 &&
                 typeof item.query_vector_str === 'string' &&
                 item.query_vector_str.startsWith('[') &&
                 item.query_vector_str.endsWith(']');
    results.push({
      case_id: "TC10-6",
      name: "Valid 1024-d Float Vector",
      expected: "PASS",
      actual: `PRODUCED: dimension=${item.embedding_dimension}, vector_str_len=${item.query_vector_str.length}`,
      pass
    });
  } catch (err) {
    results.push({ case_id: "TC10-6", name: "Valid 1024-d Float Vector", expected: "PASS", actual: `ERROR: ${err.message}`, pass: false });
  }

  // Output test summary
  console.log('TEST RESULTS:');
  console.log('-'.repeat(80));
  let allPass = true;
  for (const r of results) {
    console.log(`[${r.pass ? 'PASS' : 'FAIL'}] ${r.case_id}: ${r.name}`);
    console.log(`       Result: ${r.actual}`);
    if (!r.pass) allPass = false;
  }
  console.log('-'.repeat(80));
  console.log(`OVERALL STATUS: ${allPass ? 'ALL TESTS PASSED (FULL PASS)' : 'SOME TESTS FAILED'}`);

  const report = {
    test_id: "TC-10",
    name: "Invalid Embedding Vector Rejection Unit Test",
    timestamp: new Date().toISOString(),
    extracted_source_node: "Validate Query Vector (workflows/gated_retrieval.json)",
    isolation_safety: {
      database_access: "NONE",
      ollama_access: "NONE",
      n8n_activation: "NONE"
    },
    total_cases: results.length,
    passed_cases: results.filter(r => r.pass).length,
    failed_cases: results.filter(r => !r.pass).length,
    test_cases: results,
    overall_status: allPass ? "PASS" : "FAIL"
  };

  const reportPath = path.join(__dirname, 'tc10_vector_validator_report.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf8');
  console.log(`\nSaved test report to ${reportPath}`);
}

runUnitTests();
