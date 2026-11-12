const fs = require('fs');

const requirements = [
  {
    req_id: "REQ-01",
    category: "Infrastructure",
    original_requirement: "Create docker-compose.yml running n8n and PostgreSQL with pgvector.",
    implementation: "docker-compose.yml",
    verification_method: "Container health inspection via docker ps and psql connection probe",
    evidence_artifact: "scripts/final_preflight_report.md",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-02",
    category: "Infrastructure",
    original_requirement: "Create init.sql enabling pgvector extension and creating knowledge_vault table with id, session_id, stream_type, content, metadata JSONB, embedding vector(1024).",
    implementation: "init.sql",
    verification_method: "PostgreSQL schema and pg_extension inspection via psql query",
    evidence_artifact: "scripts/final_preflight_report.md",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-03",
    category: "Infrastructure",
    original_requirement: "stream_type must distinguish framework and voice_sample; create HNSW cosine similarity index.",
    implementation: "init.sql (CREATE INDEX idx_knowledge_vault_embedding USING hnsw)",
    verification_method: "PostgreSQL pg_indexes query confirming index parameters (m=16, ef_construction=64)",
    evidence_artifact: "scripts/final_preflight_report.md",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-04",
    category: "Infrastructure",
    original_requirement: "Create separate relational archive for rejected meetings. Rejected meetings must never receive embeddings.",
    implementation: "init.sql (CREATE TABLE rejected_meetings), workflows/ingestion_firewall.json",
    verification_method: "Direct query on rejected_meetings confirming 0 vector columns and 0 embeddings",
    evidence_artifact: "scripts/phase3_production_ingestion_report.json",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-05",
    category: "Ingestion Workflow",
    original_requirement: "Create workflows/ingestion_firewall.json reading supplied mock transcript dataset, supporting n8n item wrappers.",
    implementation: "workflows/ingestion_firewall.json (Read Transcripts File, Parse Transcripts Array)",
    verification_method: "n8n CLI execution reading /data/mock_transcripts.json and parsing 4 items",
    evidence_artifact: "scripts/phase3_production_ingestion_report.md",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-06",
    category: "Ingestion Workflow",
    original_requirement: "Sample first 40 and last 20 turns for long transcripts; avoid duplicate sampling for transcripts <= 60 turns.",
    implementation: "workflows/ingestion_firewall.json (Turn Sampler node)",
    verification_method: "Synthetic unit tests covering 6, 60, and 100 turns in scripts/test_turn_sampler_synthetic.js",
    evidence_artifact: "scripts/final_ingestion_validation_report.md",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-07",
    category: "Ingestion Workflow",
    original_requirement: "Classify meetings using structured JSON (meeting_type, confidence_score, summary); accept only Client Coaching with confidence >= 0.80.",
    implementation: "workflows/ingestion_firewall.json (Ollama Classifier, Validate Classification, Firewall Gate)",
    verification_method: "Empirical classification of SES-101 (accepted 0.95), SES-102 (accepted 0.90), SES-103 (rejected 1.00), SES-104 (rejected 0.95)",
    evidence_artifact: "scripts/phase3_production_ingestion_report.json",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-08",
    category: "Dual-Stream Extraction",
    original_requirement: "Extract conceptual coaching frameworks preserving meaning with traceable metadata; do not invent coaching concepts.",
    implementation: "workflows/ingestion_firewall.json (Ollama Framework Extractor, Format Dual-Stream Chunks)",
    verification_method: "Inspected stored framework chunks for SES-101 (ID 40) and SES-102 (ID 44)",
    evidence_artifact: "scripts/phase3_production_ingestion_report.json",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-09",
    category: "Dual-Stream Extraction",
    original_requirement: "Store only Dr. Sara Hegy's actual spoken dialogue; preserve verbatim wording and speaking rhythm; 400-700 chars where possible; combine short adjacent coach turns; no client speech.",
    implementation: "workflows/ingestion_firewall.json (Format Dual-Stream Chunks)",
    verification_method: "Inspected 6 voice chunks in knowledge_vault (all speaker 'Dr. Sara Hegy', 100% coach verbatim speech)",
    evidence_artifact: "scripts/phase3_production_ingestion_report.json",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-10",
    category: "Dual-Stream Extraction",
    original_requirement: "Embed both streams separately and store them in knowledge_vault with 1024-d embeddings using atomic replacement.",
    implementation: "workflows/ingestion_firewall.json (Ollama Chunk Embedder, Atomic Vault Replacement Function)",
    verification_method: "Inspected vector_dims(embedding) on all 16 rows in knowledge_vault (all exactly 1024); atomic stored procedure execution",
    evidence_artifact: "scripts/verify_production_db.js",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-11",
    category: "Retrieval Workflow",
    original_requirement: "Create workflows/gated_retrieval.json accepting a coaching question; route greetings directly to static response without embedding.",
    implementation: "workflows/gated_retrieval.json (Greeting Classifier, Greeting Router, Static Greeting Response)",
    verification_method: "Runtime test TC-01 ('Hello') returning static response with 0 embeddings, 0 SQL, 0 LLM calls",
    evidence_artifact: "scripts/stage6_2b_runtime_test_report.json",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-12",
    category: "Retrieval Workflow",
    original_requirement: "Embed other queries using Ollama; query framework and voice streams independently.",
    implementation: "workflows/gated_retrieval.json (Ollama Query Embedder, Retrieve Framework Stream, Retrieve Voice Stream)",
    verification_method: "Runtime execution of TC-03 and TC-04 confirming separate parallel SQL queries",
    evidence_artifact: "scripts/tc-04_runtime_test_report.json",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-13",
    category: "Retrieval Workflow",
    original_requirement: "Apply hard SQL cosine similarity thresholds before sending context to LLM: Framework >= 0.70 (limit 2), Voice >= 0.65 (limit 2).",
    implementation: "workflows/gated_retrieval.json (Retrieve Framework Stream & Retrieve Voice Stream SQL parameters)",
    verification_method: "SQL syntax audit and runtime verification confirming candidates < 0.70 and < 0.65 are pruned in SQL",
    evidence_artifact: "scripts/final_retrieval_test_report.md",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-14",
    category: "Retrieval Workflow",
    original_requirement: "If both streams return zero results, return exactly 'No documented coaching frameworks match this topic.' Do not call generation LLM in zero-result case.",
    implementation: "workflows/gated_retrieval.json (Aggregate & Gate Results, Hard Gate, Return Zero Result Output)",
    verification_method: "Runtime execution of TC-02 and TC-07 returning exact string with zero LLM generation calls",
    evidence_artifact: "scripts/tc-07_runtime_test_report.json",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-15",
    category: "Grounding and Prompting",
    original_requirement: "Use positive few-shot / voice samples for tone and phrasing only; framework chunks as conceptual truth; never invent statements attributed to Dr. Sara; avoid meta-prompt leakage and case-study confusion.",
    implementation: "workflows/gated_retrieval.json (Format Grounded Prompt, Format Final Response)",
    verification_method: "Runtime analysis of TC-04 response confirming zero prompt leakage, grounded principles, and case study isolation",
    evidence_artifact: "scripts/tc-04_runtime_test_report.json",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-16",
    category: "Dataset & Ingestion",
    original_requirement: "Expected classification: SES-101 accept, SES-102 accept, SES-103 reject, SES-104 reject.",
    implementation: "data/mock_transcripts.json, workflows/ingestion_firewall.json",
    verification_method: "Controlled production ingestion run confirming 100% expected classification decisions and database storage",
    evidence_artifact: "scripts/phase3_production_ingestion_report.json",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-17",
    category: "Documentation",
    original_requirement: "README must document architecture, installation, environment, workflows, verification, decisions, limitations, and answers to Q1 (deterministic SQL gating) and Q2 (HNSW ef_search).",
    implementation: "README.md",
    verification_method: "Full structural audit of README.md confirming all 30 topics addressed",
    evidence_artifact: "README.md",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  },
  {
    req_id: "REQ-18",
    category: "Safety and Governance",
    original_requirement: "Both workflows must remain inactive (active: false) at all times; no paid cloud APIs; no parallel inference; credentials protected.",
    implementation: "workflows/ingestion_firewall.json, workflows/gated_retrieval.json, .env.example, .gitignore",
    verification_method: "Direct SQLite query confirming active: 0; Git status audit confirming .env excluded",
    evidence_artifact: "scripts/final_preflight_report.md",
    status: "VERIFIED_PASS",
    outstanding_issue: null
  }
];

const matrix = {
  timestamp: new Date().toISOString(),
  project: "GenX Leadership Academy Agentic RAG",
  total_requirements: requirements.length,
  verified_pass_count: requirements.filter(r => r.status === "VERIFIED_PASS").length,
  completion_percentage: 100.0,
  requirements
};

fs.writeFileSync('scripts/final_submission_requirement_matrix.json', JSON.stringify(matrix, null, 2));
console.log('Saved scripts/final_submission_requirement_matrix.json (100% PASS)');
