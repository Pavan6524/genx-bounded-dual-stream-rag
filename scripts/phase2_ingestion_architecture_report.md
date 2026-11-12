# Phase 2 Ingestion Architecture Correction Report

**Project Root:** `D:\ProjectsD\genx-agentic-rag`  
**Workflow ID:** `IlBw4RRELuh02Akm` (`Ingestion Firewall & Dual-Stream Extraction`)  
**Timestamp:** 2026-11-12T23:51:00Z  
**Authors:** Principal AI Engineer, Senior n8n Workflow Architect, PostgreSQL Database Architect, and QA Lead  
**Status:** ARCHITECTURE PERMANENTLY CORRECTED & STATICALLY VALIDATED (7/7 PASS)  

---

## 1. Executive Summary

This report documents the permanent architectural correction of the GenX Ingestion Classification Firewall and Dual-Stream Extraction workflow (`IlBw4RRELuh02Akm`).

The previous production ingestion failed because `Validate & Assemble Chunks` attempted to gather embedded items using cross-run lookups (`$('Pass Framework Chunk').all()` and `$('Pass Voice Chunk').all()`). In n8n's execution engine, `.all()` without an explicit runIndex parameter defaults to `runIndex = 0`. As a result:
- For `SES-101`: Inner loop iterations for voice turns were truncated, capturing only 1 of the 3 voice chunks.
- For `SES-102`: Cross-run lookups returned `SES-101` data from `runIndex = 0`, causing session ID filtering to yield an empty array and throwing: `Validation failed for SES-102: Combined chunks array is empty.`

We have redesigned the ingestion workflow into a **deterministic 15-node single-loop pipeline** that completely eliminates fragile cross-run lookups and inner loops while preserving all assessment requirements.

---

## 2. Root Cause Analysis

### A. The Flawed 21-Node Architecture (Nested Loops)

The legacy workflow contained three separate, nested `splitInBatches` loops:
1. **Outer Loop:** `Process Sessions Sequentially` (batchSize: 1, iterates through sessions).
2. **Middle Loop:** `Sequential Framework Loop` (batchSize: 1, iterates through framework chunks).
3. **Inner Loop:** `Sequential Voice Loop` (batchSize: 1, iterates through voice chunks).

When `Sequential Voice Loop` completed, its "Done" output (Output 0) emitted the **unembedded input items**, not the accumulated embeddings. Downstream node `Validate & Assemble Chunks` attempted to reach back into the inner loops via:
```javascript
const fwItems = $('Pass Framework Chunk').all().filter(item => item.json && item.json.session_id === sessionId);
const voiceItems = $('Pass Voice Chunk').all().filter(item => item.json && item.json.session_id === sessionId);
```

### B. The Scoping Failure Mechanism

In n8n's expression engine:
1. `$('Node').all()` defaults to execution run index 0 (`runIndex = 0`).
2. Inside `Validate & Assemble Chunks`, `$('Validate Classification').first()` returned `SES-101` even during the execution of `SES-102`.
3. During `SES-102`, `fwItems` and `voiceItems` read from `runIndex = 0` (which belonged to `SES-101`). Filtering for `session_id === 'SES-102'` produced `[]`.
4. The node threw `Validation failed for SES-102: Combined chunks array is empty.` and halted execution.

---

## 3. The Corrected Deterministic Architecture (15 Nodes)

### A. Core Architectural Principles

1. **Single Outer Loop Only:** The workflow retains only ONE loop: `Process Sessions Sequentially` (batchSize 1). All inner loops (`Sequential Framework Loop` and `Sequential Voice Loop`) have been permanently removed.
2. **Native Item Batching for Sequential Inference:** In n8n, passing multiple items into an HTTP Request node executes HTTP requests sequentially, one item at a time. This guarantees low memory footprint and sequential CPU inference without any loop nodes.
3. **Zero Cross-Run Lookups:** Neither `$('...').all()` nor `$('...').first()` is used anywhere in the pipeline.
4. **Session-Scoped Lineage:** Data needed across the session branch is accessed via `$('Process Sessions Sequentially').item.json`, which strictly resolves to the current session batch.
5. **Exact 1-to-1 Pairing & Validation:** `Validate & Assemble Chunks` pairs raw chunks with embeddings from `$input.all()`, validates 1,024 finite numeric dimensions and coach identity, and produces a single consolidated payload.
6. **Single Database Call Per Accepted Session:** The production function `ingest_session_vault` is called exactly once per accepted session with the complete chunk array.

---

## 4. Node-by-Node Pipeline Architecture

```
[When clicking 'Execute workflow']
              │
    [Read Transcripts File] (/data/mock_transcripts.json)
              │
   [Parse Transcripts Array] (4 sessions)
              │
┌─────────────┴────────────────────────────────────────────────┐
│   [Process Sessions Sequentially] (splitInBatches: size 1)   │◄────────┐
└─────────────┬────────────────────────────────────────────────┘         │
              ▼ (Batch 1 session)                                        │
        [Turn Sampler] (First 40 + Last 20 for >60 turns)               │
              │                                                          │
      [Ollama Classifier] (llama3.2:1b, 4 classification rules)          │
              │                                                          │
    [Validate Classification] (is_accepted: Client Coaching & >=0.80)   │
              │                                                          │
        [Firewall Gate]                                                  │
       /              \                                                  │
[True: Accepted]     [False: Rejected]                                   │
      │                       │                                          │
[Ollama Framework      [Format Rejected Record]                          │
   Extractor]                 │                                          │
      │                [Transactional Archive                            │
[Format Dual-Stream       Rejected] (archive_rejected_meeting)           │
   Chunks] (4 items)          │                                          │
      │                       └──────────────────────────────────────────┤
[Ollama Chunk Embedder] (bge-m3, 1024-d, sequential)                     │
      │                                                                  │
[Validate & Assemble Chunks] (Consolidates 4 chunks into single payload) │
      │                                                                  │
[Atomic Vault Replacement Function] (ingest_session_vault)               │
      │                                                                  │
      └──────────────────────────────────────────────────────────────────┘
```

---

## 5. Key Node Implementations

### A. `Format Dual-Stream Chunks` (Node 12)
- Replaces separate framework and voice loops.
- Extracts 1 conceptual framework chunk from `Ollama Framework Extractor` response.
- Extracts all verbatim Dr. Sara Hegy spoken dialogue turns from `session.transcript` (3 voice chunks for SES-101 and SES-102).
- Non-adjacent coach turns are preserved individually (no merging across client speech).
- Emits exactly 4 items into the DAG.

### B. `Ollama Chunk Embedder` (Node 13)
- HTTP Request node (`POST /api/embeddings`, model: `bge-m3:latest`).
- Receives the 4 chunk items and executes 4 sequential HTTP requests on host Ollama.
- Outputs 4 items containing `{ embedding: [1024 floats] }`.

### C. `Validate & Assemble Chunks` (Node 14)
- Receives the 4 embedded items directly in `$input.all()`.
- Accesses current session via `$('Process Sessions Sequentially').item.json` and framework output via `$('Ollama Framework Extractor').item.json.response`.
- Asserts strict 1-to-1 match: `items.length === rawChunks.length`.
- Validates 1,024 finite float dimensions for each chunk.
- Validates `speaker === 'Dr. Sara Hegy'` on all voice chunks.
- Outputs single consolidated payload:
  ```json
  {
    "session_id": "SES-101",
    "chunk_count": 4,
    "framework_count": 1,
    "voice_count": 3,
    "chunks": [ ... 4 validated chunk objects ... ]
  }
  ```

### D. `Atomic Vault Replacement Function` (Node 15)
- PostgreSQL node executing `SELECT * FROM ingest_session_vault($1, $2::jsonb);`.
- Parameters: `p_session_id = $json.session_id`, `p_chunks = JSON.stringify($json.chunks)`.
- Replaces vault rows atomically inside a transaction with advisory locking.
- Loops back to `Process Sessions Sequentially`.

---

## 6. Static Verification Results

All 7 validation gates executed and passed via `scripts/verify_phase2_architecture.js`:

| Gate | Check | Result | Evidence |
|:---:|:---|:---:|:---|
| **1** | JSON Schema Validation | `PASS` | Canonical JSON valid (15 nodes, 15 connections) |
| **2** | Workflow Active State | `PASS` | `active: false` in JSON, verified `active: 0` in n8n SQLite DB |
| **3** | JavaScript Syntax Validation | `PASS` | All 6 Code nodes parsed with `AsyncFunction` with 0 syntax errors |
| **4** | Node Reference Integrity | `PASS` | All 15 source and target node connections verified in node registry |
| **5** | Cross-Run Lookups Audit | `PASS` | **Zero** occurrences of `$('...').all()` or cross-node `$('...').first()` |
| **6** | Rejection & Acceptance Routing | `PASS` | Accepted branch: 6 dual-stream nodes $\to$ loop back.<br>Rejected branch: archive $\to$ loop back (0 embeddings). |
| **7** | Per-Session Mock Data Contracts | `PASS` | SES-101: 1 fw + 3 voice (lens: 280, 402, 154)<br>SES-102: 1 fw + 3 voice (lens: 261, 393, 132)<br>SES-103: Rejected (Internal Operations)<br>SES-104: Rejected (Sales Discovery) |

---

## 7. Database & Workflow Invariant State

- **Database State:** Verified on `genx-postgres`:
  - `knowledge_vault`: **8 rows** (100% `TEST-` baseline rows, 0 production rows).
  - `rejected_meetings`: **2 rows** (100% `TEST-` baseline rows, 0 production rows).
  - **Zero mutations occurred.**
- **Workflow State:** Verified on `genx-n8n`:
  - `IlBw4RRELuh02Akm`: `active: 0` (`false`)
  - `TSvKBGpM9nK7eb3U`: `active: 0` (`false`)

---

## 8. Conclusion & Readiness

The permanent architecture correction is complete, statically verified, and backed by comprehensive reports.
The workflow is ready for a controlled, approved runtime test.
