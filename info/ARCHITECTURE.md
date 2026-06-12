# Architecture Document
## AI Contract & Legal Intelligence System

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        THREE SURFACES                           │
│                                                                 │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐   │
│  │  Enterprise  │   │   Consumer   │   │    Extension     │   │
│  │  Dashboard   │   │     Web      │   │  Chrome MV3      │   │
│  │  (Next.js)   │   │   (Next.js)  │   │  Content Script  │   │
│  └──────┬───────┘   └──────┬───────┘   └────────┬─────────┘   │
│         │                  │                     │             │
└─────────┼──────────────────┼─────────────────────┼─────────────┘
          │                  │                     │
          └──────────────────┼─────────────────────┘
                             │  HTTP / SSE
                    ┌────────▼────────┐
                    │   FastAPI App   │
                    │   (uvicorn)     │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼───┐  ┌───────▼────┐  ┌────▼──────────┐
     │  Enterprise │  │  Consumer  │  │   RAG / Chat  │
     │  Pipeline   │  │  Pipeline  │  │   Endpoint    │
     │  (LangGraph)│  │            │  │               │
     └────────┬───┘  └───────┬────┘  └────┬──────────┘
              │              │             │
              └──────────────┼─────────────┘
                             │
              ┌──────────────▼──────────────────┐
              │         Shared Services          │
              │                                  │
              │  ┌────────────┐  ┌────────────┐  │
              │  │  Groq API  │  │  ChromaDB  │  │
              │  │ Token Pool │  │  (local)   │  │
              │  │ 4 accounts │  │            │  │
              │  └────────────┘  └────────────┘  │
              │                                  │
              │  ┌────────────┐  ┌────────────┐  │
              │  │   Ollama   │  │   SQLite   │  │
              │  │ nomic-embed│  │    (DB)    │  │
              │  │  (local)   │  │            │  │
              │  └────────────┘  └────────────┘  │
              └──────────────────────────────────┘
```

---

## 2. Enterprise Pipeline — Detailed Flow

```
File Upload
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Agent 1 — Ingestor                                  │
│ • Validate file type (PDF/DOCX)                     │
│ • SHA-256 hash → audit trail                        │
│ • Write to SQLite                                   │
│ • Push SSE: ingest_complete                         │
└──────────────────┬──────────────────────────────────┘
                   │
         ┌─────────▼─────────┐
         │                   │
         ▼                   ▼
┌────────────────┐  ┌────────────────────────────────┐
│ Agent 2A       │  │ Agent 2B — Reg Loader           │
│ Extractor      │  │ • Load local DPDP/GDPR/RBI JSON │
│ • pdfplumber   │  │ • groq/compound web search for  │
│   / python-docx│  │   latest amendments             │
│ • LLM segment  │  │ • Merge into regulation_corpus  │
│ • ClauseManifest│ └────────────┬───────────────────┘
└────────┬───────┘               │
         │                       │
         ▼                       │
┌────────────────────────────────┘
│ Agent 2C — Memory Scanner
│ • Embed each clause (Ollama nomic-embed-text)
│ • Upsert to ChromaDB project collection
│ • Query project store → contradiction_hits
│ • Query org store → historical_flags
│ • Push SSE: memory_scan_complete
└──────────────────┬──────────────────────────────────
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ Agent 3 — Classifier                                │
│ • Per clause: text + regulation + contradictions    │
│   + historical flags → llama-3.3-70b-versatile      │
│ • Structured XML output: risk_level, confidence     │
│ • Confidence < 0.72 → reflection loop (max 2x)      │
│ • Push SSE: classification_progress (per 5 clauses) │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ Agent 5 — Redliner                                  │
│ • Filter: medium + high + violation only            │
│ • Per clause: llama-3.3-70b-versatile drafts        │
│   compliant replacement                             │
│ • Push SSE: redline_complete                        │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│ Agent 6 — Reporter (three concurrent outputs)       │
│                                                     │
│  asyncio.gather(                                    │
│    create_github_pr(),    ← PyGithub               │
│    send_slack_alert(),    ← Slack Webhook           │
│    push_sse_complete()    ← SSE event               │
│  )                                                  │
│                                                     │
│ + Write final audit record to SQLite                │
└─────────────────────────────────────────────────────┘
```

---

## 3. Consumer Pipeline — Detailed Flow

```
Input (one of three)
  ├── Photo    → Tesseract OCR → confidence check
  ├── PDF/DOCX → pdfplumber / python-docx text extract
  └── Extension text → direct pass-through
          │
          ▼
    Language Detection
    (script + language ID on raw text)
          │
    ┌─────▼───────────────────────────┐
    │ Is Indian language?             │
    │ Yes → IndicTrans2 → English     │
    │ No  → Google Translate → English│
    └─────────────────┬───────────────┘
                      │
                      ▼
          llama-3.1-8b-instant
          Consumer analysis prompt
          Returns structured JSON
                      │
                      ▼
          Translate output back to
          user's preferred language
                      │
                      ▼
          Return to frontend / extension
```

---

## 4. Memory Layer Architecture

```
                  ChromaDB (local persistent)
                         │
          ┌──────────────┼──────────────┐
          │              │              │
    org_A_global   org_A_proj_1   org_A_proj_2
    (org-wide      (project-      (project-
     flags)         scoped)        scoped)
          │
          │  Query flow for new document:
          │
          │  1. Embed new clause (Ollama)
          │  2. Query same project collection
          │     → top-3 similar clauses from OTHER jobs
          │     → LLM: "do these contradict?"
          │     → collect medium/high contradictions
          │
          │  3. Query org global collection
          │     → top-3 similar clauses across ALL projects
          │     → tag as "Previously flagged at org level"
          │
          │  4. Upsert new clause to both collections
          │
          ▼
    Agent 3 receives enriched input:
    clause_text + contradiction_hits + historical_flags
```

---

## 5. Groq Token Pool Flow

```
Agent requests LLM call
          │
          ▼
    GroqTokenPool.call(model, messages)
          │
          ▼
    get_available()
    ┌─────────────────────────────────┐
    │ Round-robin through 4 tokens    │
    │ Skip if retry_after > now       │
    │ Return first available          │
    └─────────────────────────────────┘
          │
          ▼
    Groq API call
    ┌─────────────┬──────────────────┐
    │   Success   │   429 Error      │
    │             │                  │
    │ Reset fails │ Read retry-after │
    │ Return resp │ mark_limited()   │
    │             │ Try next token   │
    └─────────────┴──────────────────┘
          │
    If all 4 tokens exhausted:
    raise Exception → agent handles gracefully
```

---

## 6. Browser Extension Flow

```
Page loads
    │
    ▼
MutationObserver watches DOM
    │
    ├── No modal detected → idle
    │
    └── Modal with agree button detected
              │
              ▼
        Extract innerText (incl. hidden scroll)
              │
              ▼
        Send to background service worker
              │
              ▼
        POST /api/consumer/prescan
              │
        ┌─────┴──────┐
        │            │
      amber         red
      (detected)  (high risk)
        │            │
        └─────┬──────┘
              │
        Update extension icon
              │
        User clicks icon
              │
              ▼
        POST /api/consumer/analyse
              │
              ▼
        Inject iframe sidebar
        Pass results via postMessage
              │
              ▼
        Render results in sidebar
        User reads → decides → clicks Accept or not
```

---

## 7. Data Flow Summary

| Data | Source | Destination | Format |
|---|---|---|---|
| Uploaded contract | Frontend | FastAPI `/api/enterprise/upload` | multipart/form-data |
| Job status events | FastAPI agents | Frontend SSE client | `text/event-stream` |
| Clause embeddings | Ollama nomic-embed-text | ChromaDB | float[] |
| LLM completions | Groq API | Agents | JSON / XML string |
| Risk report | Agent 3 | Agent 5, Agent 6, SQLite | JSON |
| Redlines | Agent 5 | Agent 6, SQLite | JSON |
| GitHub PR | PyGithub | GitHub repo | HTTP |
| Slack alert | Slack Webhooks | Slack channel | HTTP POST |
| Consumer results | FastAPI | Frontend / Extension | JSON |
| Agreement text | Extension content script | Background worker → FastAPI | JSON |

---

## 8. Security Considerations

- All Groq API keys stored in `.env`, never committed to repository
- Document file hashes stored for integrity verification
- Extension sends only agreement text — no cookies, no page URL, no browsing history
- Consumer analysis results not persisted by default (session only)
- Audit trail records are append-only in SQLite (no UPDATE or DELETE on audit_trail table)
- GitHub token scoped to single repo with PR-only permissions

---

## 9. Scalability Path (Post-Hackathon)

| Now (Hackathon) | Later (Production) |
|---|---|
| SQLite | PostgreSQL |
| ChromaDB in-process | ChromaDB server or Qdrant |
| Ollama local embeddings | Dedicated embedding service |
| 4 free Groq accounts | Groq paid Developer tier |
| Single FastAPI process | Multiple workers + Redis queue |
| SSE in-memory queues | Redis Pub/Sub |
| IndicTrans2 self-hosted | Dedicated translation microservice |
