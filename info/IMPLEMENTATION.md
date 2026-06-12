# Implementation Specification
## AI Contract & Legal Intelligence System

**Version:** 1.0  
**Audience:** Cursor / Windsurf / engineering team  
**Read alongside:** `PRD.md`, `ARCHITECTURE.md`, `API_CONTRACT.md`

---

## 1. Repository Structure

```
project-root/
├── backend/
│   ├── main.py                   # FastAPI app entry point
│   ├── config.py                 # Environment variables, model config
│   ├── token_pool.py             # Groq token pool + round-robin rotation
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── pipeline.py           # LangGraph pipeline definition
│   │   ├── agent_ingestor.py     # Agent 1
│   │   ├── agent_extractor.py    # Agent 2A
│   │   ├── agent_reg_loader.py   # Agent 2B
│   │   ├── agent_memory.py       # Agent 2C
│   │   ├── agent_classifier.py   # Agent 3
│   │   ├── agent_redliner.py     # Agent 5
│   │   └── agent_reporter.py     # Agent 6
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── chroma_client.py      # ChromaDB initialisation + collection management
│   │   ├── embedder.py           # Ollama nomic-embed-text wrapper
│   │   └── rag.py                # RAG Q&A query logic
│   ├── ocr/
│   │   ├── __init__.py
│   │   ├── tesseract_ocr.py      # Tesseract wrapper + script detection
│   │   └── confidence.py         # Confidence scoring + re-photograph trigger
│   ├── translation/
│   │   ├── __init__.py
│   │   ├── indictrans.py         # IndicTrans2 wrapper
│   │   └── google_translate.py   # Google Translate API fallback
│   ├── regulations/
│   │   ├── dpdp_2023.json        # DPDP Act 2023 clause corpus
│   │   ├── gdpr.json             # GDPR key provisions
│   │   └── rbi_guidelines.json   # RBI payment + data localisation rules
│   ├── outputs/
│   │   ├── __init__.py
│   │   ├── github_pr.py          # PyGithub PR creation
│   │   └── slack_webhook.py      # Slack webhook alert
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py             # SQLite table definitions (SQLAlchemy)
│   │   └── crud.py               # DB read/write helpers
│   ├── routers/
│   │   ├── enterprise.py         # /api/enterprise/* endpoints
│   │   ├── consumer.py           # /api/consumer/* endpoints
│   │   └── sse.py                # /api/stream/* SSE endpoints
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx              # Landing / home
│   │   ├── enterprise/
│   │   │   ├── page.tsx          # Enterprise dashboard
│   │   │   └── [jobId]/
│   │   │       └── page.tsx      # Job detail + live SSE progress
│   │   ├── consumer/
│   │   │   └── page.tsx          # Consumer upload + results
│   │   └── chat/
│   │       └── page.tsx          # RAG Q&A chat interface
│   ├── components/
│   │   ├── FileUpload.tsx
│   │   ├── PipelineProgress.tsx  # SSE-driven live progress
│   │   ├── RiskReport.tsx        # Enterprise risk output
│   │   ├── ConsumerReport.tsx    # Consumer plain-language output
│   │   ├── MemoryChat.tsx        # RAG Q&A component
│   │   └── ContradictionPanel.tsx
│   ├── lib/
│   │   ├── api.ts                # API client
│   │   └── sse.ts                # SSE EventSource wrapper
│   ├── store/
│   │   └── useStore.ts           # Zustand global state
│   └── package.json
└── extension/
    ├── manifest.json             # Manifest V3
    ├── content.js                # MutationObserver + text extraction
    ├── background.js             # Service worker + API calls
    ├── sidebar/
    │   ├── sidebar.html
    │   ├── sidebar.js
    │   └── sidebar.css
    └── icons/
        ├── icon-default.png
        ├── icon-amber.png
        └── icon-red.png
```

---

## 2. Backend Implementation

### 2.1 Environment Variables (`config.py`)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Groq token pool — 4 separate accounts
    GROQ_KEY_1: str
    GROQ_KEY_2: str
    GROQ_KEY_3: str
    GROQ_KEY_4: str

    # GitHub
    GITHUB_TOKEN: str
    GITHUB_REPO: str          # "org/repo-name"

    # Slack
    SLACK_WEBHOOK_URL: str

    # Google Translate (free tier)
    GOOGLE_TRANSLATE_API_KEY: str

    # Ollama (local, no key needed)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    EMBED_MODEL: str = "nomic-embed-text"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # SQLite
    DATABASE_URL: str = "sqlite:///./contracts.db"

    class Config:
        env_file = ".env"

settings = Settings()
```

---

### 2.2 Groq Token Pool (`token_pool.py`)

```python
import time
from groq import Groq, RateLimitError
from config import settings

class GroqTokenPool:
    def __init__(self):
        self.tokens = [
            {"key": settings.GROQ_KEY_1, "retry_after": None, "fails": 0},
            {"key": settings.GROQ_KEY_2, "retry_after": None, "fails": 0},
            {"key": settings.GROQ_KEY_3, "retry_after": None, "fails": 0},
            {"key": settings.GROQ_KEY_4, "retry_after": None, "fails": 0},
        ]
        self.index = 0

    def get_available(self) -> dict:
        now = time.time()
        for _ in range(len(self.tokens)):
            token = self.tokens[self.index % len(self.tokens)]
            self.index += 1
            if token["retry_after"] is None or now > token["retry_after"]:
                return token
        raise Exception("All Groq tokens rate limited. Wait and retry.")

    def mark_limited(self, token: dict, retry_after_seconds: int):
        token["retry_after"] = time.time() + retry_after_seconds
        token["fails"] += 1

    async def call(self, model: str, messages: list, **kwargs) -> str:
        for _ in range(len(self.tokens)):
            token = self.get_available()
            try:
                client = Groq(api_key=token["key"])
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    **kwargs
                )
                token["fails"] = 0
                return response.choices[0].message.content
            except RateLimitError as e:
                retry_after = int(
                    getattr(e.response, "headers", {}).get("retry-after", 60)
                )
                self.mark_limited(token, retry_after)
                continue
        raise Exception("All Groq tokens exhausted after rotation.")

# Singleton — import this everywhere
pool = GroqTokenPool()
```

---

### 2.3 Model Routing

```python
# config.py — model assignments per agent
MODELS = {
    "extractor":   "meta-llama/llama-4-scout-17b-16e-instruct",  # 30K TPM, long context
    "reg_loader":  "groq/compound",                               # built-in web search
    "memory":      "meta-llama/llama-4-scout-17b-16e-instruct",
    "classifier":  "llama-3.3-70b-versatile",                    # best reasoning
    "redliner":    "llama-3.3-70b-versatile",
    "reporter":    "llama-3.1-8b-instant",                       # 14.4K RPD, fast
    "consumer":    "llama-3.1-8b-instant",
    "rag_chat":    "qwen/qwen3-32b",                             # 60 RPM, multilingual
}

# Fallback chain per model
MODEL_FALLBACK = {
    "meta-llama/llama-4-scout-17b-16e-instruct": "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile":                   "qwen/qwen3-32b",
    "qwen/qwen3-32b":                            "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant":                      "llama-3.1-8b-instant",
    "groq/compound":                             "llama-3.3-70b-versatile",
}
```

---

### 2.4 LangGraph Pipeline (`agents/pipeline.py`)

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, List

class PipelineState(TypedDict):
    job_id: str
    org_id: str
    project_id: str
    file_path: str
    raw_text: str
    clause_manifest: List[dict]       # output of 2A
    regulation_corpus: dict           # output of 2B
    contradiction_hits: List[dict]    # output of 2C
    historical_flags: List[dict]      # output of 2C
    risk_report: List[dict]           # output of Agent 3
    redlines: List[dict]              # output of Agent 5
    github_pr_url: Optional[str]
    slack_sent: bool
    sse_events: List[str]
    error: Optional[str]

def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("ingestor",    agent_ingestor)
    graph.add_node("extractor",   agent_extractor)
    graph.add_node("reg_loader",  agent_reg_loader)
    graph.add_node("memory",      agent_memory)
    graph.add_node("classifier",  agent_classifier)
    graph.add_node("redliner",    agent_redliner)
    graph.add_node("reporter",    agent_reporter)

    graph.set_entry_point("ingestor")
    graph.add_edge("ingestor",   "extractor")

    # 2A and 2B run in parallel — LangGraph parallel branches
    graph.add_edge("extractor",  "reg_loader")
    graph.add_edge("extractor",  "memory")

    # 2C waits for 2A output; joins before classifier
    graph.add_edge("reg_loader", "classifier")
    graph.add_edge("memory",     "classifier")

    graph.add_edge("classifier", "redliner")
    graph.add_edge("redliner",   "reporter")
    graph.add_edge("reporter",   END)

    return graph.compile()
```

---

### 2.5 Agent Specifications

#### Agent 1 — Ingestor
```python
# agent_ingestor.py
async def agent_ingestor(state: PipelineState) -> PipelineState:
    # 1. Validate file exists and is PDF or DOCX
    # 2. Compute SHA-256 hash of file for audit trail
    # 3. Store document record in SQLite (job_id, org_id, project_id, file_hash, timestamp)
    # 4. Emit SSE event: {"event": "ingest_complete", "job_id": job_id}
    # 5. Return updated state with job_id confirmed
```

#### Agent 2A — Extractor
```python
# agent_extractor.py
# Input: file_path
# Output: clause_manifest — list of {clause_id, clause_type, text, page_number, start_char, end_char}
#
# Steps:
# 1. If PDF: use pdfplumber to extract text page by page
# 2. If DOCX: use python-docx to extract paragraphs
# 3. Send extracted full text to llama-4-scout with prompt:
#    "Segment this legal document into individual clauses.
#     For each clause return JSON: {clause_id, clause_type, text}
#     clause_type must be one of: data_processing, liability, termination,
#     payment, ip_ownership, dispute_resolution, confidentiality, other"
# 4. Parse JSON response into ClauseManifest
# 5. Emit SSE event: {"event": "extraction_complete", "clause_count": N}
```

#### Agent 2B — Reg Loader
```python
# agent_reg_loader.py
# Runs in parallel with 2A
# Steps:
# 1. Load local regulation corpus files (dpdp_2023.json, gdpr.json, rbi_guidelines.json)
# 2. Use groq/compound (has built-in web_search tool) to search:
#    "DPDP Act 2023 latest amendments", "GDPR enforcement 2025", "RBI data localisation 2025"
# 3. Merge live search results with local corpus
# 4. Return regulation_corpus dict keyed by regulation name
```

#### Agent 2C — Memory Scanner
```python
# agent_memory.py
# Input: clause_manifest, org_id, project_id
# Output: contradiction_hits, historical_flags; side-effect: upserts to ChromaDB
#
# Steps:
# 1. For each clause in manifest:
#    a. Generate embedding via Ollama nomic-embed-text
#    b. Upsert to ChromaDB project collection with metadata:
#       {clause_id, clause_type, org_id, project_id, job_id, timestamp}
#
# 2. Contradiction detection (project-level):
#    For each clause, query project ChromaDB collection (exclude current job_id)
#    Retrieve top-3 semantically similar clauses
#    Send pairs to llama-4-scout:
#    "Do these two clauses on the same topic contradict each other?
#     Reply JSON: {is_contradiction: bool, explanation: str, severity: low|medium|high}"
#    Collect contradictions above medium severity
#
# 3. Historical flagging (org-level):
#    Query org ChromaDB collection for each high/violation clause type
#    Tag matches as "Previously flagged at org level" with original job_id and date
#
# 4. Emit SSE event: {"event": "memory_scan_complete", "contradictions": N, "historical_flags": N}
```

#### Agent 3 — Classifier
```python
# agent_classifier.py
# Input: clause_manifest, regulation_corpus, contradiction_hits, historical_flags
# Output: risk_report — list of {clause_id, risk_level, regulation, explanation, confidence}
#
# For each clause:
# 1. Build context: clause text + relevant regulation sections + contradiction hits + historical flags
# 2. Send to llama-3.3-70b with structured prompt:
#    "Classify this clause against the provided regulation corpus.
#     Return XML:
#     <classification>
#       <risk_level>compliant|low|medium|high|violation</risk_level>
#       <regulation>DPDP_2023|GDPR|RBI|NONE</regulation>
#       <explanation>...</explanation>
#       <confidence>0.0-1.0</confidence>
#     </classification>"
# 3. Parse XML response
# 4. If confidence < 0.72: re-run with reflection prompt (max 2 retries)
#    Reflection prompt: "Your previous classification had low confidence.
#    Here is the clause again with additional context. Reconsider carefully."
# 5. Emit SSE event per batch of 5 clauses: {"event": "classification_progress", "done": N, "total": M}
```

#### Agent 5 — Redliner
```python
# agent_redliner.py
# Input: risk_report (filter to medium/high/violation only), regulation_corpus
# Output: redlines — list of {clause_id, original_text, redlined_text, explanation}
#
# For each flagged clause:
# 1. Send to llama-3.3-70b:
#    "The following clause violates [regulation] because [explanation].
#     Draft a compliant replacement clause that:
#     - Satisfies [regulation] requirements
#     - Preserves the original commercial intent
#     - Uses clear, professional legal language
#     Return JSON: {redlined_text: str, explanation: str}"
# 2. Emit SSE event: {"event": "redline_complete", "redlined_count": N}
```

#### Agent 6 — Reporter
```python
# agent_reporter.py
# Fires three concurrent outputs using asyncio.gather
#
# Output 1 — GitHub PR (PyGithub):
#   - Create branch: f"contract-review/{job_id}"
#   - Commit file: f"reports/{job_id}/risk_report.md" (full clause-by-clause diff + regulation citations)
#   - Open PR with title: f"Contract Review: {filename} — {violation_count} violations found"
#   - PR body: structured markdown with severity table, regulation breakdown, redline summary
#
# Output 2 — Slack Webhook:
#   POST to SLACK_WEBHOOK_URL with payload:
#   {
#     "text": f"*Contract Review Complete*\n
#              File: {filename}\n
#              Violations: {violation_count} | High: {high_count} | Medium: {medium_count}\n
#              PR: {github_pr_url}"
#   }
#
# Output 3 — SSE completion event:
#   {"event": "pipeline_complete", "job_id": job_id, "pr_url": github_pr_url,
#    "violation_count": N, "duration_seconds": elapsed}
#
# Also writes final audit record to SQLite:
#   (job_id, file_hash, timestamp, agent_outputs_json, risk_scores_json, pr_url)
```

---

### 2.6 Consumer Pipeline

```python
# routers/consumer.py

# POST /api/consumer/upload
# Accepts: multipart/form-data — file (PDF/DOCX) + preferred_language
# Returns: job_id for SSE tracking

# POST /api/consumer/photo
# Accepts: multipart/form-data — image file + preferred_language
# Steps:
#   1. Run Tesseract OCR with script detection
#   2. Compute confidence score
#   3. If confidence < 0.7: return {"status": "low_confidence", "message": "Please retake photo"}
#   4. If confidence >= 0.7: proceed to analysis

# Consumer analysis flow (shared with upload):
#   1. Detect language of extracted text
#   2. If Indian language: translate to English via IndicTrans2
#   3. If other language: translate to English via Google Translate API
#   4. Run consumer prompt on llama-3.1-8b-instant:
#      "Analyse this legal document and return JSON:
#       {
#         summary: [5-8 bullets in plain English, 8th grade reading level],
#         unfair_clauses: [{clause_text, explanation, fair_alternative}],
#         obligation_map: {user_obligations: [], company_obligations: []},
#         ambiguity_flags: [{term, explanation}],
#         benchmark: [{finding, context}]
#       }"
#   5. Translate output back to preferred_language
#   6. Return structured JSON to frontend
```

---

### 2.7 OCR Implementation

```python
# ocr/tesseract_ocr.py
import pytesseract
from PIL import Image

SCRIPT_LANG_MAP = {
    "Devanagari": "hin+mar+nep",
    "Kannada":    "kan",
    "Tamil":      "tam",
    "Telugu":     "tel",
    "Malayalam":  "mal",
    "Bengali":    "ben",
    "Latin":      "eng",
}

def detect_script(image_path: str) -> str:
    # Use pytesseract OSD (orientation and script detection)
    osd = pytesseract.image_to_osd(Image.open(image_path))
    # Parse script from OSD output
    for line in osd.split("\n"):
        if "Script:" in line:
            return line.split(":")[1].strip()
    return "Latin"

def extract_text(image_path: str) -> dict:
    script = detect_script(image_path)
    lang = SCRIPT_LANG_MAP.get(script, "eng")
    
    data = pytesseract.image_to_data(
        Image.open(image_path),
        lang=lang,
        output_type=pytesseract.Output.DICT
    )
    
    # Compute mean confidence (ignore -1 values)
    confidences = [c for c in data["conf"] if c != -1]
    mean_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    text = pytesseract.image_to_string(Image.open(image_path), lang=lang)
    
    return {
        "text": text,
        "confidence": mean_confidence / 100,  # normalise to 0-1
        "script": script,
        "language_code": lang,
    }
```

---

### 2.8 Memory / ChromaDB

```python
# memory/chroma_client.py
import chromadb
from config import settings

client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)

def get_project_collection(org_id: str, project_id: str):
    return client.get_or_create_collection(
        name=f"org_{org_id}_project_{project_id}",
        metadata={"hnsw:space": "cosine"}
    )

def get_org_collection(org_id: str):
    return client.get_or_create_collection(
        name=f"org_{org_id}_global",
        metadata={"hnsw:space": "cosine"}
    )

# memory/embedder.py
import httpx

async def embed(text: str) -> list[float]:
    response = await httpx.AsyncClient().post(
        f"{settings.OLLAMA_BASE_URL}/api/embeddings",
        json={"model": settings.EMBED_MODEL, "prompt": text}
    )
    return response.json()["embedding"]
```

---

### 2.9 RAG Q&A Endpoint

```python
# routers/enterprise.py

# POST /api/enterprise/chat
# Body: {org_id, project_id, query, conversation_history}
# Steps:
#   1. Embed query via Ollama nomic-embed-text
#   2. Query project ChromaDB collection — top 5 results
#   3. Build context string from retrieved chunks
#   4. Send to qwen/qwen3-32b:
#      System: "You are a legal contract analyst. Answer questions based only on the
#               provided contract excerpts. Cite which document each finding comes from."
#      User: f"Context:\n{context}\n\nQuestion: {query}"
#   5. Return {answer, sources: [{doc_id, clause_text, relevance_score}]}
```

---

### 2.10 SSE Endpoint

```python
# routers/sse.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio

router = APIRouter()

# In-memory event queues keyed by job_id
event_queues: dict[str, asyncio.Queue] = {}

@router.get("/api/stream/{job_id}")
async def stream_job(job_id: str):
    queue = event_queues.get(job_id, asyncio.Queue())
    event_queues[job_id] = queue

    async def generator():
        while True:
            event = await queue.get()
            yield f"data: {event}\n\n"
            if '"event": "pipeline_complete"' in event:
                break

    return StreamingResponse(generator(), media_type="text/event-stream")

# Helper used by agents to push events
async def push_event(job_id: str, payload: dict):
    import json
    if job_id in event_queues:
        await event_queues[job_id].put(json.dumps(payload))
```

---

## 3. Frontend Implementation

### 3.1 SSE Client (`lib/sse.ts`)

```typescript
export function subscribeToJob(
  jobId: string,
  onEvent: (event: Record<string, unknown>) => void,
  onComplete: () => void
) {
  const es = new EventSource(`/api/stream/${jobId}`)
  
  es.onmessage = (e) => {
    const data = JSON.parse(e.data)
    onEvent(data)
    if (data.event === "pipeline_complete") {
      es.close()
      onComplete()
    }
  }

  es.onerror = () => es.close()
  return () => es.close()
}
```

### 3.2 Pipeline Progress Component
- Render a vertical stepper: Ingest → Extract → Load Regs → Memory Scan → Classify → Redline → Report
- Each step activates as SSE events arrive
- Show spinner on active step, checkmark on complete, clause counts as subtitles

### 3.3 Enterprise Risk Report Component
- Severity table: violations / high / medium / low / compliant counts
- Clause list grouped by risk level
- Each clause card: original text, risk level badge, regulation tag, explanation, redlined alternative (collapsible)
- Contradiction hits panel: side-by-side clause pairs with conflict explanation
- Historical flags panel: "Previously flagged in Project X on [date]"
- GitHub PR link + Slack confirmation banner

### 3.4 Consumer Report Component
- Clean card layout, no legal jargon, no regulation codes
- Summary bullets at top
- Obligation asymmetry: two columns — "What you agree to" vs "What they agree to"
- Flagged clauses in red cards with plain-English explanation and fair alternative
- Ambiguity flags in amber
- Benchmark comparisons in blue info boxes
- Language selector at top right (persisted to localStorage)
- Prominent disclaimer footer

---

## 4. Browser Extension Implementation

### 4.1 manifest.json

```json
{
  "manifest_version": 3,
  "name": "Legal Clarity",
  "version": "1.0.0",
  "description": "Understand any legal agreement before you click Accept",
  "permissions": ["activeTab", "storage"],
  "host_permissions": ["<all_urls>"],
  "background": {
    "service_worker": "background.js"
  },
  "content_scripts": [
    {
      "matches": ["<all_urls>"],
      "js": ["content.js"],
      "run_at": "document_idle"
    }
  ],
  "action": {
    "default_icon": {
      "32": "icons/icon-default.png"
    },
    "default_title": "Legal Clarity"
  }
}
```

### 4.2 Content Script (`content.js`)

```javascript
const AGREE_PATTERNS = /i agree|accept|i accept|agree & continue|continue|i consent/i
const MODAL_SELECTORS = ['[role="dialog"]', '.modal', '.overlay', '[class*="terms"]', '[class*="consent"]']

let detectedText = null

const observer = new MutationObserver(() => {
  for (const selector of MODAL_SELECTORS) {
    const el = document.querySelector(selector)
    if (!el) continue

    const buttons = el.querySelectorAll('button, [role="button"], a')
    const hasAgreeButton = Array.from(buttons).some(b => AGREE_PATTERNS.test(b.textContent))
    if (!hasAgreeButton) continue

    // Extract full text including hidden scroll content
    const allText = Array.from(el.querySelectorAll('*'))
      .map(n => n.innerText)
      .filter(Boolean)
      .join('\n')

    if (allText.length > 200) {
      detectedText = allText
      chrome.runtime.sendMessage({ type: "AGREEMENT_DETECTED", text: allText })
      break
    }
  }
})

observer.observe(document.body, { childList: true, subtree: true })

// Listen for sidebar injection trigger
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "INJECT_SIDEBAR") {
    injectSidebar(msg.results)
  }
})

function injectSidebar(results) {
  const iframe = document.createElement('iframe')
  iframe.src = chrome.runtime.getURL('sidebar/sidebar.html')
  iframe.style.cssText = `
    position: fixed; top: 0; right: 0; width: 420px; height: 100vh;
    border: none; z-index: 2147483647; box-shadow: -4px 0 24px rgba(0,0,0,0.15);
  `
  document.body.appendChild(iframe)
  // Pass results to iframe via postMessage after load
  iframe.onload = () => iframe.contentWindow.postMessage({ type: "RESULTS", results }, "*")
}
```

### 4.3 Background Service Worker (`background.js`)

```javascript
const API_BASE = "https://your-backend-url.com"  // update before build

chrome.runtime.onMessage.addListener(async (msg, sender) => {
  if (msg.type === "AGREEMENT_DETECTED") {
    // Update icon to amber
    chrome.action.setIcon({ tabId: sender.tab.id, path: "icons/icon-amber.png" })

    // Quick pre-scan for icon colour
    const preScan = await fetch(`${API_BASE}/api/consumer/prescan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: msg.text })
    }).then(r => r.json())

    if (preScan.high_risk) {
      chrome.action.setIcon({ tabId: sender.tab.id, path: "icons/icon-red.png" })
    }

    // Store text for when user clicks icon
    chrome.storage.local.set({ [`pending_${sender.tab.id}`]: msg.text })
  }
})

chrome.action.onClicked.addListener(async (tab) => {
  const stored = await chrome.storage.local.get(`pending_${tab.id}`)
  const text = stored[`pending_${tab.id}`]
  if (!text) return

  const results = await fetch(`${API_BASE}/api/consumer/analyse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, source: "extension" })
  }).then(r => r.json())

  chrome.tabs.sendMessage(tab.id, { type: "INJECT_SIDEBAR", results })
})
```

---

## 5. Database Schema (`db/models.py`)

```python
from sqlalchemy import Column, String, Text, Float, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
import datetime

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    job_id       = Column(String, primary_key=True)
    org_id       = Column(String, nullable=False)
    project_id   = Column(String, nullable=False)
    filename     = Column(String)
    file_hash    = Column(String)           # SHA-256, immutable audit
    tier         = Column(String)           # "enterprise" | "consumer"
    status       = Column(String)           # "processing" | "complete" | "error"
    created_at   = Column(DateTime, default=datetime.datetime.utcnow)

class AuditTrail(Base):
    __tablename__ = "audit_trail"
    job_id            = Column(String, primary_key=True)
    file_hash         = Column(String)
    timestamp         = Column(DateTime, default=datetime.datetime.utcnow)
    agent_outputs     = Column(JSON)        # full agent output per step
    risk_scores       = Column(JSON)        # {clause_id: risk_level}
    github_pr_url     = Column(String)
    violation_count   = Column(Float)
    duration_seconds  = Column(Float)

class Clause(Base):
    __tablename__ = "clauses"
    clause_id    = Column(String, primary_key=True)
    job_id       = Column(String)
    org_id       = Column(String)
    project_id   = Column(String)
    clause_type  = Column(String)
    text         = Column(Text)
    risk_level   = Column(String)
    regulation   = Column(String)
    confidence   = Column(Float)
    created_at   = Column(DateTime, default=datetime.datetime.utcnow)
```

---

## 6. Dependencies

### backend/requirements.txt
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
python-multipart==0.0.9
pydantic-settings==2.3.0
langgraph==0.2.0
langchain==0.2.0
groq==0.9.0
pdfplumber==0.11.0
python-docx==1.1.2
pytesseract==0.3.13
Pillow==10.4.0
chromadb==0.5.0
httpx==0.27.0
PyGithub==2.3.0
sqlalchemy==2.0.31
aiosqlite==0.20.0
python-dotenv==1.0.1
```

### frontend/package.json (key deps)
```json
{
  "dependencies": {
    "next": "14.2.5",
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "zustand": "4.5.4",
    "react-dropzone": "14.2.3",
    "tailwindcss": "3.4.7"
  }
}
```

---

## 7. Build & Run

### Backend
```bash
# Install Ollama and pull embedding model
curl -fsSL https://ollama.com/install.sh | sh
ollama pull nomic-embed-text

# Install Tesseract with Indian language packs
sudo apt-get install tesseract-ocr tesseract-ocr-hin tesseract-ocr-kan \
  tesseract-ocr-tam tesseract-ocr-tel tesseract-ocr-mal tesseract-ocr-ben

# Python setup
cd backend
pip install -r requirements.txt
cp .env.example .env  # fill in keys

# Run
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

### Extension
```bash
# Load unpacked in Chrome:
# 1. Open chrome://extensions
# 2. Enable Developer Mode
# 3. Click "Load unpacked" → select /extension folder
```

---

## 8. Key Implementation Notes for Cursor / Windsurf

- **Token pool is a singleton.** Import `pool` from `token_pool.py` in every agent. Never instantiate a new pool.
- **LangGraph parallel branches** for agents 2A/2B/2C — use `add_edge` from a fan-out node, then a join node before Agent 3.
- **SSE queue must be awaited** — agents call `await push_event(job_id, payload)` not a sync call.
- **ChromaDB collections** use cosine similarity space — set at creation, cannot change after.
- **Tesseract languages** must be installed at OS level before pytesseract can use them — include in setup script.
- **Groq compound model** for Agent 2B has built-in web search — do not add a separate search tool, it is already in the model.
- **IndicTrans2** requires a separate model download — see `translation/indictrans.py` for setup instructions.
- **Extension service worker** cannot use `localStorage` — use `chrome.storage.local` only.
- **All ChromaDB IDs** must be strings — cast integers to str before upsert.
