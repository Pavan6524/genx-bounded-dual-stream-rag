# GenX Leadership Academy — TC-03 to TC-10 Test Execution Plan & Engineering Review

**Project:** GenX Bounded Dual-Stream RAG & Ingestion Classification Firewall  
**Target Retrieval Workflow:** `TSvKBGpM9nK7eb3U` (`Bounded Dual-Stream Gated Retrieval`)  
**Target Ingestion Workflow:** `IlBw4RRELuh02Akm` (`Ingestion Firewall & Dual-Stream Extraction`)  
**Document:** `scripts/tc03_tc10_test_execution_plan.md`  
**Version:** 1.1 — Post-Task 7.1 Engineering Accuracy Review  
**Date:** 2026-11-12  
**Status:** STATIC ENGINEERING REVIEW (NO TESTS EXECUTED)  

---

## 1. Executive Summary & Assessment Context

This document establishes the verified execution plan for test cases **TC-03 through TC-10** of the GenX Agentic RAG technical assessment.

### Pre-Test Verification Baseline
- **TC-01 (Simple Greeting Bypass):** **FULL PASS** (Executed in Stage 6.2B, report: `scripts/stage6_2b_runtime_test_report.json`). Proved immediate static greeting return in 27.04s; zero embedding, zero database, zero LLM calls.
- **TC-02 (Threshold Gating & Positive Retrieval):** **FULL PASS** (Executed in Stage 6.2C and Task 5). Proved:
  1. *Threshold Gating:* Query scoring $< 0.70$ / $< 0.65$ was strictly stopped by `Hard Gate` $\to$ `Return Zero Result Output`, returning exact fallback text without LLM invocation (34.75s).
  2. *Positive Retrieval & Grounded Generation:* Candidate Query 1 scored `0.7514` on Framework Chunk 30, passed `Hard Gate`, populated Section A, verified Section B as empty without fabrication, and generated grounded coaching output via `llama3.2:1b` (84.64s).
- **Database Baseline:** PostgreSQL `genx_rag` holds exactly **8 rows** in `knowledge_vault` and **2 rows** in `rejected_meetings`. Zero mutations have occurred across all tests.
- **Workflow State:** Both workflows remain **INACTIVE** (`active: false`).

---

## 2. Engineering Accuracy Corrections

This section resolves the six technical discrepancies identified during the Task 7.1 architectural review:

### A. Database Record Identity: `TEST-SES-*` vs. `SES-*`
- The current PostgreSQL database contains records prefixed with `TEST-`:
  - `TEST-SES-101` and `TEST-SES-102` (in `knowledge_vault`, 8 total chunks: IDs 30 to 37).
  - `TEST-SES-103` and `TEST-SES-104` (in `rejected_meetings`, 2 records: IDs 1 and 2).
- The original mock transcripts `SES-101` through `SES-104` in `data/mock_transcripts.json` **have not yet been ingested through the live ingestion workflow** (`IlBw4RRELuh02Akm`).
- *Correction:* All references asserting that production `SES-*` records exist in PostgreSQL have been corrected. All retrieval tests are mapped to the actual stored `TEST-SES-*` chunk IDs.

### B. TC-05 Positive-Path Evidence Attribution
- The completed positive retrieval test in Task 5 returned:
  - Framework Chunk ID **30** (`TEST-SES-101`, *"Completion with Integrity"*), scoring **0.7514**.
  - Voice stream returned **0 qualifying chunks** (Chunk 32 scored `0.6241` $< 0.65$).
  - Hard gate passed; generation LLM invoked with Section A populated and Section B empty.
- *Correction:* This empirical result proves the **Framework-Only partial retrieval path** for **Chunk 30**. It is **NOT** attributed to Chunk 34.
- Proposed query targeting Chunk 34 (*"Table and Shoulder Test"*, `TEST-SES-102`) is labeled as an **UNVERIFIED alternative** requiring pre-measurement before runtime execution.

### C. TC-10 Malformed Vector Validation & Injection Constraints
- *Inspection of `Validate Query Vector` Code node:*
  - Receives `item.embedding` from `Ollama Query Embedder`.
  - Asserts `Array.isArray(embedding)` and `embedding.length === 1024`.
  - Asserts `typeof val === 'number'` and `Number.isFinite(val)` across all elements (rejects `NaN`, `±Inf`, `null`, strings).
  - Throws an `Error`, which halts n8n execution and ensures downstream SQL nodes are **never executed**.
- *Live Injection Constraint:*
  - Host Ollama `bge-m3:latest` always emits a valid 1,024-float array for any text query. It is impossible to produce a 512-d or NaN vector via a text prompt like `"TRIGGER_MALFORMED_VECTOR_MOCK"`.
  - Live prompt injection is **BLOCKED**.
- *Correction:* TC-10 is classified as **`STATIC_ONLY`** for workflow evaluation, with an **isolated Node.js unit test** specified for executing the node's validation logic with synthetic payloads.

### D. TC-08 and TC-09 Threshold Verification Separation
- Static SQL inspection must never be labeled as runtime verification.
- *TC-08 (Framework $< 0.70$):*
  - **Static Proof:** Audit confirms `WHERE stream_type = 'framework' AND (1 - (embedding <=> $1::vector)) >= 0.70 LIMIT 2`.
  - **Runtime Proof:** Requires executing a query scoring $< 0.70$ to confirm 0 framework rows are returned.
- *TC-09 (Voice $< 0.65$):*
  - **Static Proof:** Audit confirms `WHERE stream_type = 'voice_sample' AND (1 - (embedding <=> $1::vector)) >= 0.65 LIMIT 2`.
  - **Runtime Proof:** Empirically verified in Task 5 (Chunk 32 scored `0.6241` and was dropped by SQL).

### E. Query Calibration vs. Workflow Retrieval vs. Response Quality (TC-03, TC-04, TC-06)
- The plan explicitly separates:
  1. *Similarity Measurement:* Read-only SQL calculation of cosine similarity against stored chunks.
  2. *Workflow Retrieval Execution:* n8n DAG traversal, SQL node execution, and hard gating.
  3. *Final Response Quality:* Qualitative evaluation of coaching tone and grounding fidelity.
- Stream qualification requirements:
  - **TC-03:** Voice stream $\ge 0.65$ (Framework may be any score).
  - **TC-04:** BOTH Framework $\ge 0.70$ AND Voice $\ge 0.65$.
  - **TC-06:** Voice $\ge 0.65$ AND Framework $< 0.70$.
- All unmeasured queries are labeled **`UNVERIFIED_PENDING_CALIBRATION`**.

### F. Execution-Time Estimates Recalculation
- Estimates are updated using empirical run benchmarks:
  - Zero-result / negative gate runtime: **~35 seconds**.
  - Positive retrieval + LLM generation runtime: **~85 seconds**.
  - Query calibration (urllib + SQL): **~2.3 seconds**.
  - Manual review buffer: **~5 minutes per LLM test**.

---

## 3. Test Classification Taxonomy

| Category | Definition | Application |
|:---|:---|:---|
| **`STATIC_ONLY`** | Verified via static inspection of workflow JSON, code expressions, or SQL text. | Node code validation, parameter audits, schema guards (TC-08, TC-09, TC-10). |
| **`READ_ONLY_RUNTIME`** | Executed via n8n CLI issuing only read-only `SELECT` queries against PostgreSQL. | DAG routing, threshold gating, and fallback output (TC-01, TC-02, TC-07, TC-08, TC-09). |
| **`LLM_RUNTIME`** | Involves Ollama inference (`bge-m3:latest` and `llama3.2:1b`). | Positive retrieval and grounded response generation (TC-03, TC-04, TC-05, TC-06). |
| **`MANUAL_REVIEW`** | Qualitative assessment of response tone, voice cadence, and grounding boundaries. | Verification of Dr. Sara's style and absence of hallucinated quotes (TC-03, TC-04, TC-06). |

---

## 4. Systematic Mapping & Safe Procedures (TC-03 to TC-10)

```
RETRIEVAL WORKFLOW DAG ARCHITECTURE (TSvKBGpM9nK7eb3U):
[When clicking 'Execute workflow']
              │
   [Query Input & Normalizer]
              │
    [Greeting Classifier]
              │
       [Greeting Router] ──(Is Greeting)──> [Static Greeting Response]
              │ (Not Greeting)
    [Ollama Query Embedder]
              │
    [Validate Query Vector]
        ┌─────┴────────────────┐
        ▼                      ▼
[Retrieve Framework]   [Retrieve Voice]
  (SQL >= 0.70)          (SQL >= 0.65)
        └─────┬────────────────┘
              ▼
   [Merge Retrieval Streams]
              │
  [Aggregate & Gate Results]
              │
     [Hard Gate (Has?)] ──(No Results)──> [Return Zero Result Output]
              │ (Has Results)
   [Format Grounded Prompt]
              │
  [Ollama Grounded Generator]
              │
   [Format Final Response]
```

### TC-03: Relevant Communication / Style Query
- **Objective:** Verify voice stream retrieval and generation reflecting Dr. Sara Hegy's conversational cadence.
- **Workflow:** `TSvKBGpM9nK7eb3U` (14 nodes).
- **Classification:** `READ_ONLY_RUNTIME`, `LLM_RUNTIME`, `MANUAL_REVIEW`.
- **Target Stored Chunks:** Voice Chunks 31 & 32 (`TEST-SES-101`).
- **Qualification Rule:** Voice similarity $\ge 0.65$ mandatory.
- **Status:** `UNVERIFIED_PENDING_CALIBRATION`.
- **Procedure:**
  1. Pre-measure candidate query similarity against `knowledge_vault`.
  2. If Voice $\ge 0.65$, execute:
     ```powershell
     python scripts/execute_tc02.py --query "<calibrated_query>"
     ```
  3. Review generated response for Dr. Sara's style; verify zero fabricated quotes.
- **Estimated Duration:** ~85s execution + 5m review.

---

### TC-04: Dual-Stream Qualifying Query (Framework + Voice)
- **Objective:** Verify simultaneous qualification of Framework ($\ge 0.70$) and Voice ($\ge 0.65$) streams.
- **Workflow:** `TSvKBGpM9nK7eb3U` (14 nodes).
- **Classification:** `READ_ONLY_RUNTIME`, `LLM_RUNTIME`, `MANUAL_REVIEW`.
- **Target Stored Chunks:** Framework Chunk 34 (`TEST-SES-102`) AND Voice Chunks 35/36/37 (`TEST-SES-102`) or 33 (`TEST-SES-101`).
- **Qualification Rule:** BOTH Framework $\ge 0.70$ AND Voice $\ge 0.65$ simultaneously.
- **Status:** `UNVERIFIED_PENDING_CALIBRATION`.
- **Procedure:**
  1. Pre-measure candidate query to verify both thresholds are crossed.
  2. Execute single run via runner bridge.
  3. Validate that `Aggregate & Gate Results` reports `total_qualifying_chunks >= 2` and prompt populates both Section A and Section B.
- **Estimated Duration:** ~85s execution + 5m review.

---

### TC-05: Framework-Only Retrieval (Partial Retrieval Demonstration)
- **Objective:** Verify that when only framework evidence qualifies and voice stream is empty, the system generates grounded responses without fabricating voice.
- **Workflow:** `TSvKBGpM9nK7eb3U`.
- **Classification:** `READ_ONLY_RUNTIME`, `LLM_RUNTIME`.
- **Status:** **PASS — PROVEN ON CHUNK 30** (Task 5 runtime report: `scripts/positive_retrieval_runtime_test_report.json`).
  - Candidate Query 1 achieved Framework Chunk 30 similarity `0.7514` ($\ge 0.70$) and Voice Chunk 32 similarity `0.6241` ($< 0.65$).
  - Hard gate evaluated TRUE; Section B was explicitly empty; generator produced grounded response without voice fabrication.
- **Alternative Target (Chunk 34):** `UNVERIFIED alternative` (querying Chunk 34 requires separate calibration).

---

### TC-06: Voice-Only Retrieval (Partial Retrieval Demonstration)
- **Objective:** Verify that when only voice evidence qualifies and framework stream is empty, the system generates responses reflecting tone while transparently noting the absence of frameworks.
- **Workflow:** `TSvKBGpM9nK7eb3U` (14 nodes).
- **Classification:** `READ_ONLY_RUNTIME`, `LLM_RUNTIME`, `MANUAL_REVIEW`.
- **Target Stored Chunk:** Voice Chunk 33 (`TEST-SES-101`: *"Protect your cognitive bandwidth"*).
- **Qualification Rule:** Voice similarity $\ge 0.65$ AND Framework similarity $< 0.70$.
- **Status:** `UNVERIFIED_PENDING_CALIBRATION`.
- **Procedure:**
  1. Pre-measure query against Chunk 33 to confirm Voice $\ge 0.65$ and Framework $< 0.70$.
  2. Execute single run via runner bridge.
  3. Verify prompt Section A is empty and Section B is populated.
- **Estimated Duration:** ~85s execution + 5m review.

---

### TC-07: Completely Unrelated Query (Zero Results Gate)
- **Objective:** Verify that an entirely out-of-domain query returns zero qualifying results, halts at `Hard Gate`, and bypasses the generation LLM.
- **Workflow:** `TSvKBGpM9nK7eb3U` (12 nodes, terminating at `Return Zero Result Output`).
- **Classification:** `READ_ONLY_RUNTIME`.
- **Input Query:** `"What is the optimal fertilizer ratio for growing hydroponic tomatoes in winter?"`
- **Target Stored Chunks:** All 8 chunks (expected similarities $< 0.30$).
- **Status:** **MECHANISM PROVEN IN TC-02**; Pending execution for specific query.
- **Procedure:**
  ```powershell
  python scripts/execute_tc02.py --query "What is the optimal fertilizer ratio for growing hydroponic tomatoes in winter?"
  ```
- **Validation Criteria:**
  - Both SQL queries return 0 rows above threshold.
  - Hard gate routes to `Return Zero Result Output`.
  - Ollama Grounded Generator is **NOT EXECUTED**.
  - Output equals exact string: `"No documented coaching frameworks match this topic."`
- **Estimated Duration:** ~35 seconds.

---

### TC-08: Framework Threshold Boundary Rejection (< 0.70)
- **Objective:** Verify that candidate framework chunks scoring $< 0.70$ are dropped at the SQL level.
- **Target Node:** `Retrieve Framework Stream`.
- **Classification:** `STATIC_ONLY` and `READ_ONLY_RUNTIME`.
- **Static Verification:** Audit confirms SQL predicate `(1 - (embedding <=> $1::vector)) >= 0.70` with `LIMIT 2`.
- **Runtime Verification:** Execution with query yielding candidate scores $< 0.70$ confirms 0 framework rows returned from SQL.
- **Estimated Duration:** Static audit: immediate; Runtime test: ~35 seconds.

---

### TC-09: Voice Threshold Boundary Rejection (< 0.65)
- **Objective:** Verify that candidate voice chunks scoring $< 0.65$ are dropped at the SQL level.
- **Target Node:** `Retrieve Voice Stream`.
- **Classification:** `STATIC_ONLY` and `READ_ONLY_RUNTIME`.
- **Static Verification:** Audit confirms SQL predicate `(1 - (embedding <=> $1::vector)) >= 0.65` with `LIMIT 2`.
- **Runtime Verification:** Empirically verified in Task 5: Voice Chunk 32 scored `0.6241` and was strictly excluded by this SQL predicate.

---

### TC-10: Invalid Embedding Vector Rejection
- **Objective:** Verify that `Validate Query Vector` intercepts missing, truncated, or non-finite vectors and halts execution before any SQL query is issued.
- **Target Node:** `Validate Query Vector`.
- **Classification:** `STATIC_ONLY` (Live prompt injection is `BLOCKED`).
- **Static Verification:** Code inspection confirms strict assertions on `Array.isArray`, `length === 1024`, and `Number.isFinite`.
- **Recommended Verification Method:** Isolated Node.js unit test executing the node's JavaScript code with synthetic invalid vectors (`null`, length 512, `[NaN, ...]`).

---

## 5. Empirical Execution Duration & Effort Estimates

| Activity | Test Cases | Execution Time | Review Time | Total Estimated Time |
|:---|:---|:---:|:---:|:---:|
| **Static Proofs** | TC-08, TC-09, TC-10 | 0s | 5m | 5m |
| **Negative Gating Run** | TC-07 (Unrelated query) | ~35s | 2m | ~3m |
| **Calibration Measurements** | TC-03, TC-04, TC-06 | ~10s (3 queries) | 2m | ~3m |
| **Positive / Dual Stream Runs** | TC-03, TC-04, TC-06 | ~255s (3 × 85s) | 15m | ~20m |
| **Evidence Documentation** | All remaining tests | — | 10m | 10m |
| **Total Sequential Effort** | | **~5.5 minutes** | **~34 minutes** | **~40 minutes** |

---

## 6. Strict Safety & Isolation Commitments
- **Workflows State:** Both `TSvKBGpM9nK7eb3U` and `IlBw4RRELuh02Akm` remain **INACTIVE**.
- **PostgreSQL Baseline:** Intact at **8 knowledge rows** and **2 rejected rows**.
- **Zero Database Mutations:** All retrieval tests are strictly read-only (`SELECT`).
- **No Unauthorized Executions:** No test will be executed without separate explicit approval.
