

\# GenX Leadership Academy — Agentic AI Assessment



\## Project Objective



Build a local, Docker-based bounded dual-stream RAG pipeline using n8n, PostgreSQL with pgvector, and Ollama.



The solution must demonstrate:

1\. An ingestion classification firewall.

2\. Dual-stream knowledge extraction.

3\. Separate framework and coach voice retrieval.

4\. Hard cosine similarity thresholds enforced in SQL.

5\. Grounded coaching responses using positive few-shot examples.



\## Technology Stack



\- n8n: workflow orchestration

\- PostgreSQL 16: relational storage

\- pgvector: vector similarity search

\- Ollama: local LLM and embedding inference

\- Docker Compose: local infrastructure

\- JavaScript: n8n Code nodes

\- SQL: database schema and gated retrieval



Prefer local inference. Do not introduce paid cloud APIs without explicit approval.



\## Assignment Requirements



\### Infrastructure

\- Create docker-compose.yml.

\- Run n8n and PostgreSQL with pgvector.

\- Create init.sql.

\- Enable the PostgreSQL vector extension.

\- Create knowledge\_vault with:

&#x20; - id

&#x20; - session\_id

&#x20; - stream\_type

&#x20; - content

&#x20; - metadata JSONB

&#x20; - embedding vector

\- stream\_type must distinguish framework and voice\_sample.

\- Create an HNSW cosine similarity index.

\- Create a separate relational archive for rejected meetings.

\- Rejected meetings must never receive embeddings.



\### Ingestion Workflow



Create workflows/ingestion\_firewall.json.



1\. Read the supplied mock transcript dataset.

2\. Support n8n item wrappers.

3\. Sample first 40 and last 20 turns for long transcripts.

4\. Avoid duplicate sampling for transcripts with 60 or fewer turns.

5\. Classify meetings using structured JSON:

&#x20;  - meeting\_type

&#x20;  - confidence\_score

&#x20;  - summary

6\. Accept only Client Coaching with confidence >= 0.80.

7\. Archive Internal Operations, Sales Discovery, Other, and low-confidence meetings.

8\. Never embed rejected meetings.



\### Dual-Stream Extraction



For accepted coaching sessions:



Framework stream:

\- Extract conceptual coaching frameworks.

\- Preserve the meaning of the discussion.

\- Include traceable source metadata.

\- Do not invent coaching concepts.



Voice stream:

\- Store only Dr Sara Hegy's actual spoken dialogue.

\- Preserve verbatim wording and speaking rhythm.

\- Create chunks approximately 400–700 characters where possible.

\- Combine short adjacent coach turns where appropriate.

\- Do not fabricate, paraphrase, or include client speech.

\- Preserve session and speaker metadata.



Embed both streams separately and store them in knowledge\_vault.



\### Retrieval Workflow



Create workflows/gated\_retrieval.json.



1\. Accept a coaching question.

2\. Route greetings such as Hello and Hi directly to a static response.

3\. Do not embed greeting messages.

4\. Embed other queries using Ollama.

5\. Query framework and voice streams independently.

6\. Apply hard SQL cosine similarity thresholds BEFORE sending context to the LLM.



Framework threshold:

1 - cosine\_distance >= 0.70

Maximum results: 2



Voice threshold:

1 - cosine\_distance >= 0.65

Maximum results: 2



If both streams return zero results:

Return exactly:

"No documented coaching frameworks match this topic."



Do not call the generation LLM in this zero-result case.



If either stream contains relevant results, generate a grounded response using the retrieved material.



\### Grounding and Prompting



\- Use positive few-shot examples to establish Dr Sara's coaching style.

\- Use voice samples for tone and phrasing only.

\- Use framework chunks as the source of conceptual knowledge.

\- Never invent statements and attribute them to Dr Sara.

\- Never claim that a retrieved framework exists if it was not retrieved.

\- Do not use long negative ban lists as a substitute for good grounding.



\## Dataset



Use the supplied mock\_transcripts.json.



Expected classification:

\- SES-101: Client Coaching — accept.

\- SES-102: Client Coaching — accept.

\- SES-103: Internal Operations — reject.

\- SES-104: Sales Discovery — reject.



Support both short sample transcripts and longer transcripts.



\## Required Deliverables



\- docker-compose.yml

\- init.sql

\- workflows/ingestion\_firewall.json

\- workflows/gated\_retrieval.json

\- data/mock\_transcripts.json

\- README.md



Additional configuration and test files are allowed when useful.



\## Documentation and Verification



README must document:

\- Architecture and components.

\- Installation and startup.

\- Environment configuration.

\- Workflow execution.

\- Verification and testing.

\- Architectural decisions and limitations.



Verify:

\- SES-101 and SES-102 are ingested.

\- SES-103 and SES-104 are rejected.

\- Rejected meetings have no embeddings.

\- Framework and voice chunks are stored separately.

\- SQL thresholds are applied before LLM generation.

\- Greetings bypass embedding and database retrieval.

\- Zero-result queries bypass generation LLM.

\- Partial retrieval results still produce grounded responses.



Explain:

1\. Why deterministic SQL threshold gating is preferable to asking an LLM to say "I don't know".

2\. How HNSW ef\_search affects recall and query latency.



\## Development Rules



\- Inspect existing files before editing.

\- Implement one module at a time.

\- Do not rewrite working modules unnecessarily.

\- Maintain consistent schemas, node interfaces, and workflow contracts.

\- Use environment variables for secrets and configuration.

\- Never hardcode API keys or passwords.

\- Validate input and handle errors.

\- Use actual executable n8n workflow exports, not pseudo-code.

\- Test every module before proceeding.

\- Never claim a test passed unless it was actually executed.

\- Avoid unnecessary dependencies and scope creep.

\- Keep the implementation suitable for a Windows 11 computer with 8 GB RAM.

\- Prefer lightweight local models and sequential inference.

\- Store large model and Docker data on the available non-system drive where practical.



\## Collaboration Protocol



Work with the user one stage at a time.



Before modifying a module:

1\. Explain the objective.

2\. Inspect relevant existing files.

3\. Identify dependencies and interfaces.

4\. Implement only the requested stage.



After implementation:

1\. Explain files changed.

2\. Provide exact commands to test.

3\. Report actual test results.

4\. Identify outstanding issues.

5\. Wait for user approval before advancing.



Do not silently change architecture or assignment requirements.



