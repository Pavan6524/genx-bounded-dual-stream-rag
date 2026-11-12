# GenX Leadership Academy — Production Ingestion Safety Review & Execution Plan

**Project:** GenX Bounded Dual-Stream RAG & Ingestion Classification Firewall  
**Document:** `scripts/production_ingestion_safety_review.md`  
**Date:** 2026-11-12  
**Target Ingestion Workflow ID:** `IlBw4RRELuh02Akm`  
**Input Dataset:** `data/mock_transcripts.json` (`SES-101`, `SES-102`, `SES-103`, `SES-104`)  
**Status:** STATIC ARCHITECTURAL REVIEW — PENDING EXPLICIT APPROVAL  

---

## 1. Executive Summary & Critical Workflow Discovery

This document establishes the safety architecture, mutation plan, and rollback strategy for ingesting the four production mock transcripts (`SES-101` through `SES-104`) into PostgreSQL `genx_rag`.

### Critical Architectural Finding:
During pre-ingestion inspection of the live workflow `IlBw4RRELuh02Akm` in n8n, a structural distinction was discovered:
1. **Live n8n Workflow `IlBw4RRELuh02Akm` (21 nodes):**
   - Title: *"Ingestion Firewall & Dual-Stream Extraction (Runtime Test)"*.
   - In node `Read Transcripts File`: reads `/workflows/runtime_ingestion_transcripts.json`.
   - In node `Validate & Assemble Chunks`: enforces a strict safety guard:
     ```javascript
     if (!sessionId || !sessionId.startsWith('TEST-')) {
       throw new Error(`CRITICAL SAFETY VIOLATION: Non-TEST session ID in test workflow: '${sessionId}'`);
     }
     ```
   - In SQL nodes: invokes test-scoped database functions `archive_rejected_test_meeting()` and `ingest_test_session_vault()`, which both contain PostgreSQL-level triggers that fail if `p_session_id` does not begin with `TEST-`.
2. **Canonical Workflow on Disk `workflows/ingestion_firewall.json` (19 nodes):**
   - Title: *"Ingestion Firewall & Dual-Stream Extraction"*.
   - In node `Read Transcripts File`: reads `/data/mock_transcripts.json`.
   - In SQL nodes: executes direct transactional SQL statements (`Store Framework in Vault`, `Store Voice in Vault`, and `Transactional Archive Rejected`) without requiring a `TEST-` prefix.

**Resolution for Production Ingestion:**
To execute the production dataset ingestion safely without violating safety guards or modifying existing records, Workflow A must be imported from the canonical `workflows/ingestion_firewall.json` (or executed via a dedicated runner script) that safely processes `data/mock_transcripts.json`.

---

## 2. Systematic Workflow Node Trace & Ingestion Mechanics

### A. Input Reading & Turn Sampling
1. **File Access:** Host `d:\ProjectsD\genx-agentic-rag\data` is mounted to `/data` in container `genx-n8n`. `/data/mock_transcripts.json` is verified accessible.
2. **Parsing:** Node `Parse Transcripts Array` unpacks the JSON array into individual items.
3. **Sequential Loop:** `Process Sessions Sequentially` processes meetings 1-by-1 (`batchSize: 1`).
4. **Turn Sampling:** `Turn Sampler` evaluates `total_turns`:
   - All 4 sessions have 5–6 turns ($\le 60$), so all turns are passed through unchanged without truncation or duplication.

### B. Classification Firewall & Gating
1. **Ollama Classifier:** Invokes `llama3.2:1b` with the structured prompt requiring `meeting_type`, `confidence_score`, and `summary`.
2. **Gating Rule:** Node `Validate Classification` enforces:
   - Accept ONLY `meeting_type === 'Client Coaching'` AND `confidence_score >= 0.80`.
   - Any missing fields, non-coaching type, or confidence $< 0.80$ routes to REJECT.
3. **Branching:**
   - **`SES-101` (Weekly Strategy Session, Mark D. & Dr. Sara):** Client Coaching ($\ge 0.90$) $\to$ **ACCEPT**
   - **`SES-102` (Executive Catch-up, Elena R. & Dr. Sara):** Client Coaching ($\ge 0.90$) $\to$ **ACCEPT**
   - **`SES-103` (Technical Sync, Engineering team):** Internal Operations $\to$ **REJECT**
   - **`SES-104` (Partnership Call, Sales Rep):** Sales Discovery $\to$ **REJECT**

### C. Rejected Meeting Handling (SES-103 & SES-104)
- **Node:** `Transactional Archive Rejected`
- **SQL Executed:**
  ```sql
  BEGIN;
  DELETE FROM rejected_meetings WHERE session_id = $1;
  DELETE FROM knowledge_vault WHERE session_id = $1;
  INSERT INTO rejected_meetings (session_id, meeting_type, confidence_score, summary, raw_transcript, rejection_reason)
  VALUES ($1, $2, $3, $4, $5, $6);
  COMMIT;
  ```
- **Vector Isolation:** `rejected_meetings` schema contains **no vector column**. Rejected meetings **never reach embedding nodes**.

### D. Accepted Meeting Dual-Stream Extraction (SES-101 & SES-102)
1. **Framework Extraction:**
   - `Ollama Framework Extractor` $\to$ `Format Framework Chunks` parses conceptual frameworks.
   - `SES-101` yields **1 framework chunk**: *"Completion with Integrity"*.
   - `SES-102` yields **1 framework chunk**: *"Table and Shoulder Test"*.
   - Embedded via `Ollama Framework Embedder` (`bge-m3:latest`, 1,024 dimensions).
   - Stored in `knowledge_vault` with `stream_type = 'framework'`.
2. **Voice Stream Extraction:**
   - Node `Extract Voice Stream` extracts strictly Dr. Sara Hegy's spoken turns (verbatim dialogue, client turns excluded).
   - `SES-101` yields **3 voice chunks** (turns 0, 2, 4).
   - `SES-102` yields **3 voice chunks** (turns 0, 2, 4).
   - Embedded via `Ollama Voice Embedder` (`bge-m3:latest`, 1,024 dimensions).
   - Stored in `knowledge_vault` with `stream_type = 'voice_sample'`.

---

## 3. Production Ingestion Mutation Plan

### Before and After Row Counts

| Table | Pre-Ingestion Baseline | Expected New Rows from Production Ingest | Expected Post-Ingestion Total |
|:---|:---:|:---:|:---:|
| **`knowledge_vault`** | **8 rows** (`TEST-SES-101`, `TEST-SES-102`) | **+8 rows** (`SES-101`: 4 chunks, `SES-102`: 4 chunks) | **16 rows** |
| — *Framework Chunks* | 2 rows | +2 rows | 4 rows |
| — *Voice Sample Chunks* | 6 rows | +6 rows | 12 rows |
| **`rejected_meetings`** | **2 rows** (`TEST-SES-103`, `TEST-SES-104`) | **+2 rows** (`SES-103`, `SES-104`) | **4 rows** |

### Coexistence & Idempotency Guarantee:
- Production sessions (`SES-*`) and test sessions (`TEST-SES-*`) share the same tables cleanly without collisions.
- Re-running ingestion on `SES-101` to `SES-104` is idempotent because prior records for that specific `session_id` are replaced cleanly.
- TEST-prefixed records (`TEST-SES-*`) are never matched or touched by production session operations.

---

## 4. Rollback Strategy & Backup Procedure

### A. Pre-Execution Database Backup
Before running any production ingestion, an atomic SQL dump of the database baseline will be generated:
```powershell
docker exec genx-postgres pg_dump -U genx -d genx_rag --data-only > scripts/backups/db_baseline_before_production_ingest.sql
```
Verified by asserting the backup file contains the 8 `knowledge_vault` and 2 `rejected_meetings` records.

### B. Rollback Script: `scripts/production_ingestion_rollback.sql`
- **Scope:** Targets strictly `session_id IN ('SES-101', 'SES-102', 'SES-103', 'SES-104')`.
- **Safety Assertions:**
  - Verifies at least 8 `TEST-*` vault rows and 2 `TEST-*` rejected rows exist before proceeding.
  - Deletes only rows where `session_id NOT LIKE 'TEST-%'`.
  - Verifies post-deletion counts return to exactly 8 vault rows and 2 rejected rows.
  - Wrapped in a strict `BEGIN ... COMMIT` block with `\set ON_ERROR_STOP on`.

---

## 5. Execution Procedure (Manual / CLI)

To execute production ingestion safely without activating either workflow:

```powershell
# 1. Backup current database baseline
docker exec genx-postgres pg_dump -U genx -d genx_rag -f /tmp/baseline_pre_prod.sql

# 2. Execute Ingestion via controlled CLI execution
docker exec -e N8N_RUNNERS_BROKER_PORT=5699 -e N8N_BLOCK_ENV_ACCESS_IN_NODE=false genx-n8n n8n execute --id=IlBw4RRELuh02Akm
```

### Safety Confirmations:
- Workflow A remains **INACTIVE** (`active: false`).
- Workflow B (`TSvKBGpM9nK7eb3U`) remains **UNTOUCHED and INACTIVE**.
- No webhooks, polling triggers, or cron jobs are enabled.
- Single execution; zero automated retries.

---

## 6. Persisted Artifacts
- **Mutation Plan JSON:** [scripts/production_ingestion_mutation_plan.json](file:///d:/ProjectsD/genx-agentic-rag/scripts/production_ingestion_mutation_plan.json)
- **Rollback SQL Script:** [scripts/production_ingestion_rollback.sql](file:///d:/ProjectsD/genx-agentic-rag/scripts/production_ingestion_rollback.sql)

---

**STOPPED.** Review complete. Awaiting explicit approval before proceeding with production ingestion.
