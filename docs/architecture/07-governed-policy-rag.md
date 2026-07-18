# Governed Policy Retrieval

## Purpose

Every live workflow grounds its recommendation in both operational evidence and an approved
policy corpus. Policy retrieval is a read-only MCP tool, not hidden prompt context. Its query,
ranked chunks, source URLs, versions, capture timestamps, and SHA-256 content hashes are emitted
as evidence and inspected by the same grounding evaluator as API evidence.

## Runtime Modes

| Mode               | Retrieval                                    | Storage                                         | Intended use                         |
| ------------------ | -------------------------------------------- | ----------------------------------------------- | ------------------------------------ |
| Public demo        | MiniSearch lexical ranking                   | Versioned source snapshot in `policy-corpus.ts` | Zero-infrastructure Vercel execution |
| Managed production | Postgres full-text + pgvector hybrid ranking | `policy_documents` and `policy_chunks`          | Tenant-scoped enterprise deployment  |

The public snapshot contains normalized passages from authoritative public sources. It is never
presented as private enterprise data. Managed ingestion retains the original document URI,
authority, version, effective date, capture time, content hash, tenant boundary, and supersession
status before chunking or embedding.

## Workflow Corpora

| Workflow                     | Approved authorities                                             |
| ---------------------------- | ---------------------------------------------------------------- |
| Production incident response | NIST SP 800-61 and NIST Cybersecurity Framework Respond guidance |
| Engineering issue triage     | NIST SP 800-218 Secure Software Development Framework            |
| Hassantuk villa response     | UAE Ministry of Interior and UAE Legislation                     |
| Supplier entity risk         | OECD Responsible Business Conduct due-diligence guidance         |
| Finance evidence             | SEC Staff Accounting Bulletins 99 and 108                        |

## Production Controls

- Retrieval is scenario- and tenant-scoped before ranking.
- Only active document versions are eligible; superseded and withdrawn documents remain auditable.
- Full-text search remains available when embeddings are disabled or unavailable.
- Embeddings are stored in pgvector with the embedding model recorded per chunk.
- Retrieved text is treated as untrusted evidence, not executable instructions.
- MCP input schemas cap query length and result count.
- OPA allowlists retrieval and continues to hold every write or external side effect.
- The evaluator rejects a run that does not capture every required operational and policy source.

## Main Components

- `apps/web/lib/agentic/policy-corpus.ts`: authoritative public-demo corpus and MiniSearch index.
- `enterprise_policy_search`: typed MCP retrieval boundary.
- `20260718_1315_0002_policy_knowledge_store.py`: Postgres/pgvector production schema.
- `decision-lens.tsx`: visible policy citations and provenance in the execution story.
- `workflow-canvas.tsx`: policy specialist and retrieval nodes in the live topology.
