# Product Requirements Document
## AI Contract & Legal Intelligence System

**Version:** 1.0  
**Status:** Internal — Hackathon Build  
**Team:** 2 engineers  

---

## 1. Product Overview

A unified AI-powered legal intelligence platform with three delivery surfaces — an enterprise compliance pipeline, a consumer legal clarity tool, and a browser extension — all running on a shared intelligence core.

**One line:** An AI contract intelligence system that automates enterprise compliance and lets any Indian understand what they are signing — in their language, from a phone photo.

---

## 2. Problem Statement

### 2.1 Consumer
- Legal documents arrive as blurry WhatsApp photos, in English legalese, to people who speak Hindi, Kannada, Tamil, Telugu, or other Indian languages
- Physical paper is the dominant format for rent agreements, loan letters, employment contracts from small businesses
- No free, instant, vernacular tool exists for the average Indian salaried worker
- Every app install and SaaS signup presents a ToS nobody reads, containing data-sharing and arbitration clauses that would shock users if explained plainly

### 2.2 Enterprise
- Manual legal review takes 3–5 days per contract; business pressure wins and contracts get signed anyway
- Regulations (DPDP Act 2023, GDPR, RBI Guidelines) are living documents; contracts signed two years ago may now carry crore-level liability
- No cross-document contradiction detection exists in any current tool
- No audit trail means good-faith compliance cannot be proven to regulators
- Redlining requires a lawyer and weeks of back-and-forth

---

## 3. Goals

| Goal | Metric |
|---|---|
| Enterprise pipeline end-to-end | Under 45 seconds per contract |
| Consumer analysis | Under 60 seconds from photo to plain-language output |
| Extension detection | Under 2 seconds from page load to icon glow |
| Memory layer contradiction detection | Runs within enterprise pipeline, no added latency gate |
| Zero paid infrastructure for hackathon | All services free-tier or self-hosted |

---

## 4. Non-Goals (v1)

- Mobile native app (web PWA only)
- Firefox extension (v2)
- Org-level historical flag promotion UI (v2)
- Clause timeline view UI (v2)
- Scenario simulation and negotiation phrasing on consumer tier (v2)
- Paid tier, billing, or subscription management
- Real legal advice (platform is awareness and education only)

---

## 5. Users

### 5.1 Enterprise User
- Legal / compliance officer at a mid-to-large Indian company
- Uploads vendor agreements, SaaS contracts, data processing agreements
- Wants: risk classification, compliant redlines, GitHub PR, Slack alert, audit trail
- Does not want: to read 40 pages themselves

### 5.2 Consumer User
- Any Indian adult signing any document
- May only have a phone and a physical paper
- Speaks Hindi, Kannada, Tamil, Telugu, Malayalam, Bengali, or English
- Wants: "tell me what I am actually agreeing to"
- Does not want: legal jargon, citations, or to pay anything

### 5.3 Extension User
- Anyone browsing the web
- Hits an "I Agree" wall on a SaaS signup, banking onboarding, or government portal
- Wants: instant sidebar explanation without leaving the page

---

## 6. Features

### 6.1 Enterprise Tier

#### 6.1.1 Contract Ingestion
- Accept PDF and DOCX uploads via drag-and-drop or file picker
- Validate file type and size (max 50MB)
- Generate unique job ID, store document, fire first SSE event to frontend
- Store document hash for audit trail immutability

#### 6.1.2 Seven-Agent Pipeline
See `IMPLEMENTATION.md` for full agent specifications.

| Agent | Responsibility |
|---|---|
| Agent 1 — Ingestor | File validation, DB storage, job ID generation, SSE event |
| Agent 2A — Extractor | PDF/DOCX parsing → typed ClauseManifest |
| Agent 2B — Reg Loader | Load DPDP/GDPR/RBI corpus + live regulatory web search |
| Agent 2C — Memory Scanner | Embed clauses → ChromaDB; contradiction + historical flag queries |
| Agent 3 — Classifier | Risk classification per clause; reflection loop if confidence < 0.72 |
| Agent 5 — Redliner | Compliant clause replacement drafts for medium/high/violation clauses |
| Agent 6 — Reporter | Concurrent GitHub PR + Slack alert + SSE dashboard completion event |

#### 6.1.3 Risk Classification
- Four levels: `compliant` / `low` / `medium` / `high` / `violation`
- Regulations covered: DPDP Act 2023, GDPR, RBI Guidelines
- Live web search for regulatory updates at classification time
- Confidence threshold: 0.72. Below threshold → reflection loop, max 2 iterations

#### 6.1.4 Memory Layer
- Every ingested clause chunk embedded and stored in ChromaDB
- Scoped at two levels: project and organisation
- **Contradiction detection:** new document queried against project store; semantic conflicts surfaced in risk report
- **Historical flagging:** new document queried against org store; previously flagged clause patterns tagged
- **RAG Q&A:** natural language chat across all documents in a project
- **Clause timeline:** version history of how a clause type has evolved across documents (UI in v2)

#### 6.1.5 Outputs
- **GitHub PR:** full clause-by-clause redline diff with regulation citations. Auto-generated, reviewable, mergeable
- **Slack alert:** 3-line summary with severity breakdown and link to full report
- **Live dashboard:** real-time SSE-powered pipeline progress and final findings
- **Audit trail:** immutable log per run — timestamp, document hash, agent outputs, risk scores

### 6.2 Consumer Tier

#### 6.2.1 Input Methods
- **Camera / photo capture:** photograph physical document. OCR extracts text. Script detection for Devanagari, Kannada, Tamil, Telugu, Malayalam, Bengali. Low-confidence extraction → re-photograph prompt, no silent hallucination
- **PDF / DOCX upload:** standard file upload
- **Browser extension intercept:** text passed directly from extension, no manual input

#### 6.2.2 Multilingual Pipeline
1. Auto language and script detection on raw input
2. Normalise to English via IndicTrans2 (Indian language pairs) or Google Translate API (other languages)
3. Analysis runs in English
4. Output translated back to user's preferred language before display
5. Language preference persists in local storage; overridable per document

#### 6.2.3 Output Features (v1)
- Plain language summary: 5–8 bullets at 8th-grade reading level
- Unfair clause highlights: flagged clauses with plain-English explanation
- What a fair clause would say: consumer-friendly balanced alternative
- Obligation asymmetry map: what YOU commit to vs what THEY commit to side-by-side
- Ambiguity flags: vague terms ("trusted partners", "reasonable notice", "at our discretion") flagged and explained
- Benchmark comparison: contextual comparison to normal for that document category

#### 6.2.4 Output Features (v2)
- Scenario simulation: what-if reasoning on key clauses
- Negotiation phrasing: exact email text to request clause changes

#### 6.2.5 Scope Disclaimer
Displayed prominently on every output: platform provides awareness and education only, not legal advice. Users with high-stakes documents are encouraged to consult a qualified lawyer.

### 6.3 Browser Extension

#### 6.3.1 Detection
- Lightweight content script with MutationObserver on every page
- Watches for: agreement modals, ToS popups, cookie consent walls, buttons with text matching "I Agree", "Accept", "Continue", "I Accept", "Agree & Continue"
- No notification or interruption — passive detection only

#### 6.3.2 Icon States
- Default: inactive grey
- Amber glow: agreement detected
- Red glow: preliminary scan flags high-risk clauses

#### 6.3.3 Analysis Flow
1. User clicks glowing icon
2. Extension extracts full `innerText` of agreement modal, including hidden-scroll content
3. Text sent to consumer pipeline backend
4. Results rendered in slide-in sidebar on right side of current page — user never leaves page
5. Sidebar shows: plain-language summary, flagged clauses, recommendation ("We found 3 clauses above industry standard for data sharing")

#### 6.3.4 Privacy
- No agreement text stored beyond analysis session
- No browsing history logged
- Only detected agreement text sent to backend — no other page data

#### 6.3.5 Platform Support
- v1: Chrome, Edge, Brave (Manifest V3)
- v2: Firefox (WebExtensions API)

#### 6.3.6 Coverage Targets
- SaaS signup and checkout flows
- Banking and insurance onboarding
- Government portals (DigiLocker, UIDAI-style flows)
- E-commerce terms acknowledgements
- Employment portals and HR systems
- App install flows

---

## 7. Tech Stack

### 7.1 Backend
| Component | Technology | Notes |
|---|---|---|
| API framework | FastAPI + uvicorn | Async, SSE support |
| Agent orchestration | LangGraph | Multi-agent pipeline with typed state |
| PDF parsing | pdfplumber | Clause extraction |
| DOCX parsing | python-docx | Clause extraction |
| OCR | Tesseract 5 + pytesseract | Indian script support: Devanagari, Kannada, Tamil, Telugu, Malayalam, Bengali |
| Indian language translation | IndicTrans2 (IIT Madras) | Self-hosted, open source, best-in-class Indian language pairs |
| General translation | Google Translate API (free tier) | Non-Indian language pairs |
| LLM inference | Groq API | Free tier, LPU-accelerated |
| Vector store | ChromaDB | Self-hosted in-process, no cost |
| Embeddings | `nomic-embed-text` via Ollama OR `llama3.1` Groq endpoint | Free |
| Database | SQLite (MVP) | Upgrade to PostgreSQL post-hackathon |
| GitHub integration | PyGithub | PR creation |
| Slack integration | Slack Webhooks | Alert delivery |
| Real-time updates | Server-Sent Events (SSE) | FastAPI native |
| Regulation corpus | Local JSON/text files + live web search | DPDP, GDPR, RBI |

### 7.2 Groq Models
| Agent / Use Case | Model | Reason |
|---|---|---|
| Extraction, Memory Scanner | `meta-llama/llama-4-scout-17b-16e-instruct` | Highest TPM (30K), long context |
| Classification, Redlining | `llama-3.3-70b-versatile` | Best reasoning quality |
| Reporting, Consumer summaries | `llama-3.1-8b-instant` | Highest RPD (14,400), fast |
| RAG Q&A chat | `qwen/qwen3-32b` | 60 RPM, strong multilingual |
| Live regulation web search | `groq/compound` | Built-in web search tool |

### 7.3 Groq Token Pool
- 4 separate Groq accounts (4 team members / email signups)
- Round-robin rotation with 429 fallback
- Per-token cooldown using `retry-after` response header
- Per-agent model pinning with graceful model fallback

### 7.4 Frontend
| Component | Technology |
|---|---|
| Framework | Next.js 14 (App Router) |
| Styling | Tailwind CSS |
| Real-time | EventSource API (SSE client) |
| State | Zustand |
| File upload | react-dropzone |

### 7.5 Browser Extension
| Component | Technology |
|---|---|
| Manifest | V3 |
| Content script | Vanilla JS + MutationObserver |
| Background | Service Worker |
| Sidebar | Injected iframe (Next.js micro-frontend) |
| Auth | Token stored in chrome.storage.local |

---

## 8. MVP Scope

### In Scope (Hackathon v1)
- All 7 enterprise pipeline agents including memory layer
- Consumer: photo input + PDF/DOCX + plain language output + multilingual
- Browser extension: Chrome, DOM detection, sidebar
- RAG Q&A on project document set
- Contradiction detection across project documents
- GitHub PR output
- Slack alert output
- Live SSE dashboard

### Out of Scope (v2)
- Clause timeline UI
- Org-level historical flag UI
- Scenario simulation (consumer)
- Negotiation phrasing (consumer)
- Firefox extension
- PostgreSQL migration
- Billing / subscription

---

## 9. Open Decisions

| Decision | Options | Recommendation |
|---|---|---|
| Project name | TBD | Decide before submission |
| OCR stack | Tesseract (free, open source) vs Google Cloud Vision (better accuracy, API cost) | Tesseract for hackathon; Cloud Vision fallback if quality insufficient |
| Embeddings | Ollama nomic-embed-text (local) vs Groq endpoint | Ollama local — no API cost, no rate limit |
| ChromaDB mode | In-process vs server | In-process for hackathon |
| Extension sidebar | Injected iframe vs shadow DOM | Iframe — cleaner isolation |
