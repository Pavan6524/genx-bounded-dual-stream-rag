# GenX Leadership Academy — Test Data Gap Analysis & Boundary Evaluation

**Project:** GenX Bounded Dual-Stream RAG & Ingestion Classification Firewall  
**Document:** `scripts/tc03_tc10_data_gap_analysis.md`  
**Version:** 1.1 — Post-Task 7.1 Engineering Accuracy Review  
**Date:** 2026-11-12  
**Status:** STATIC ENGINEERING REVIEW (NO TESTS EXECUTED)  

---

## 1. Database Record Identity & Production vs. Test Status

### Critical Architectural Clarification:
The current PostgreSQL database (`genx_rag`) holds **test-prefixed records** created during the atomic Stage 5 baseline ingestion:
- **`TEST-SES-101`** (Client Coaching, Mark D.)
- **`TEST-SES-102`** (Client Coaching, Rachel K.)
- **`TEST-SES-103`** (Internal Operations, Engineering sync)
- **`TEST-SES-104`** (Sales Discovery, Partnership call)

The original mock transcripts in `data/mock_transcripts.json` (`SES-101`, `SES-102`, `SES-103`, `SES-104`) **have not yet been ingested through the live ingestion workflow** (`IlBw4RRELuh02Akm`).

All retrieval tests (TC-01 through TC-10) operate strictly against the **existing 8 chunks in `knowledge_vault` and 2 records in `rejected_meetings`**:

### Existing Stored Chunks in `knowledge_vault`
| ID | Session ID | Stream Type | Identifier / Content Summary | Measured Baseline Score (Candidate Query 1) |
|:---:|:---:|:---:|:---|:---:|
| **30** | `TEST-SES-101` | **framework** | **Completion with Integrity** | **0.7514** (Qualifies $\ge 0.70$) |
| **34** | `TEST-SES-102` | **framework** | **Table and Shoulder Test** | **0.3760** (Unverified for TC-04/05) |
| **31** | `TEST-SES-101` | `voice_sample` | *"Look, Mark, micromanagement is almost never..."* | 0.5348 |
| **32** | `TEST-SES-101` | `voice_sample` | *"The reality is, top performers don't fail..."* | 0.6241 (Sub-threshold $< 0.65$) |
| **33** | `TEST-SES-101` | `voice_sample` | *"Exactly. Protect your cognitive bandwidth..."* | 0.4198 |
| **35** | `TEST-SES-102` | `voice_sample` | *"The reality is that top performers don't decay..."* | 0.3801 |
| **36** | `TEST-SES-102` | `voice_sample` | *"Has the company's operational velocity..."* | 0.4493 |
| **37** | `TEST-SES-102` | `voice_sample` | *"When you regulate your own state first..."* | 0.3903 |

---

## 2. Evidence Attribution: TC-05 Positive Retrieval Baseline

The completed positive retrieval test (Task 5, documented in `scripts/positive_retrieval_runtime_test_report.json`) returned:
- **Framework Chunk ID 30** (`TEST-SES-101`, *"Completion with Integrity"*), scoring **0.7514** (threshold $\ge 0.70$).
- **Zero qualifying voice chunks** (Chunk 32 scored `0.6241`, below threshold $0.65$).
- **Hard gate evaluated TRUE** ($1 + 0 = 1$ qualifying chunk $> 0$).
- **Generation LLM (`llama3.2:1b`) invoked** with Section A populated and Section B marked empty.

**Correction & Attribution:**
- This empirical evidence proves the **Framework-Only partial retrieval path** on **Chunk ID 30**.
- **Chunk ID 34** (*"Table and Shoulder Test"*, `TEST-SES-102`) was **NOT** the subject of this passed test. Any proposal to use Chunk 34 for TC-05 must be classified as an **UNVERIFIED alternative** requiring pre-measurement calibration.

---

## 3. Query Calibration vs. Workflow Retrieval vs. Response Quality (TC-03, TC-04, TC-06)

To ensure technical accuracy, three distinct phases must be separated for retrieval testing:

1. **Similarity Measurement:**
   - Evaluated via a standalone Python script querying PostgreSQL directly (`SELECT 1 - (embedding <=> query_vec)`).
   - Verifies whether a candidate query actually crosses the hard threshold (`>= 0.70` for framework, `>= 0.65` for voice).
   - Does NOT prove workflow execution or DAG routing.
2. **Workflow Retrieval Execution:**
   - Evaluated via n8n CLI execution (`python scripts/execute_tc02.py --query "..."`).
   - Verifies live node execution: Query Normalization $\to$ Embedding $\to$ Vector Validation $\to$ SQL execution $\to$ Stream Merging $\to$ Hard Gating.
   - Proves whether nodes execute or bypass correctly based on SQL output.
3. **Final Response Quality:**
   - Evaluated via manual qualitative review of the generated response.
   - Verifies adherence to Section A (conceptual grounding), Section B (voice style), and absence of hallucinated quotes.

### Test Stream Qualification Requirements:
- **TC-03 (Voice Style):** Requires **Voice similarity $\ge 0.65$** (Targeting Chunk 31/32). Framework stream may be $< 0.70$ or $\ge 0.70$.
- **TC-04 (Dual-Stream):** Requires **BOTH Framework $\ge 0.70$ AND Voice $\ge 0.65$** simultaneously.
- **TC-06 (Voice-Only):** Requires **Voice $\ge 0.65$ AND Framework $< 0.70$**.

*Status:* All candidate queries for TC-03, TC-04, and TC-06 remain **UNVERIFIED** until measured against the stored chunks.

---

## 4. TC-10 Malformed Vector Validation Analysis

### Actual Implementation in `Validate Query Vector`:
```javascript
const item = $input.first().json;
const embedding = item.embedding;
const query = $('Greeting Classifier').first().json.query;

if (!embedding || !Array.isArray(embedding)) {
  throw new Error('Ollama embedding service failed: vector is missing or not an array.');
}
if (embedding.length !== 1024) {
  throw new Error(`Embedding vector validation failed: dimension is ${embedding.length}, expected 1024.`);
}
for (let i = 0; i < embedding.length; i++) {
  const val = embedding[i];
  if (typeof val !== 'number' || !Number.isFinite(val)) {
    throw new Error(`Embedding vector validation failed: element at index ${i} is non-numeric or non-finite (${val}).`);
  }
}
const vectorStr = '[' + embedding.join(',') + ']';
return [{ json: { query, query_vector_str: vectorStr, embedding_dimension: embedding.length } }];
```

### Engineering Findings:
1. **Input Structure:** Receives `{ "embedding": [...] }` from `Ollama Query Embedder` (HTTP Request node).
2. **Dimension Verification:** Strictly checks `embedding.length === 1024`.
3. **Finite Value Verification:** Loops through all elements and asserts `typeof val === 'number'` and `Number.isFinite(val)`. Rejects `NaN`, `Infinity`, `-Infinity`, strings, and `null`.
4. **Halting Behavior:** Throwing an `Error` in an n8n Code node causes the execution to halt immediately. Downstream nodes (`Retrieve Framework Stream`, `Retrieve Voice Stream`) are **never triggered**, ensuring zero SQL calls.
5. **Live Workflow Injection Feasibility:** **BLOCKED VIA TEXT PROMPT**.
   - Host Ollama `bge-m3:latest` always returns a valid 1,024-float vector for any input text string.
   - It is impossible to force Ollama to return a 512-d or NaN vector by sending a prompt like `"TRIGGER_MALFORMED_VECTOR_MOCK"`.
   - Modifying the workflow JSON to simulate this is strictly prohibited.
6. **Recommended Verification:** An **isolated Node.js unit test** that invokes the node's JavaScript logic directly with synthetic payloads (`null`, `[1, 2]`, `[NaN, ...]`).

---

## 5. TC-08 & TC-09 Static SQL Audit vs. Runtime Proof

| Test | Static Proof (Node SQL Audit) | Runtime Proof (Execution Trace) | Current Status |
|:---|:---|:---|:---:|
| **TC-08** (Framework $< 0.70$) | Verified: SQL contains `WHERE stream_type = 'framework' AND (1 - (embedding <=> $1::vector)) >= 0.70 LIMIT 2` | Requires execution of a query scoring between `0.00` and `0.6999`, confirming 0 framework rows returned | **Static: PASS / Runtime: PENDING** |
| **TC-09** (Voice $< 0.65$) | Verified: SQL contains `WHERE stream_type = 'voice_sample' AND (1 - (embedding <=> $1::vector)) >= 0.65 LIMIT 2` | Empirically verified in Task 5: Chunk 32 scored `0.6241` and was dropped by SQL | **Static: PASS / Runtime: PASS (Task 5)** |

---

## 6. Empirical Execution Duration Benchmarks

Estimates must reflect empirical execution times measured under Windows 11 / Docker / host Ollama conditions:

| Execution Type | Actual Measured Duration | Applicable Test Cases |
|:---|:---:|:---|
| **Query Embedding Calibration** | **~2.3s** (urllib POST `/api/embeddings`) | Pre-measurement for TC-03, TC-04, TC-06 |
| **Greeting Bypass Runtime** | **27.04s** (n8n CLI execution) | TC-01 (Completed) |
| **Zero-Result / Fallback Runtime** | **34.75s** (Embedding + SQL + Gate + Fallback) | TC-02 (Completed), TC-07, TC-08, TC-09 |
| **Positive Retrieval + LLM Generation** | **84.64s** (Embedding + SQL + Gate + llama3.2 Generation) | TC-02/Candidate 1 (Completed), TC-03, TC-04, TC-05, TC-06 |
| **Manual Output Review** | **~5 minutes** | Qualitative evaluation for TC-03, TC-04, TC-06 |

Total sequential runtime for remaining tests is estimated at **~25–35 minutes** including calibration and review.
