# API Contract
## AI Contract & Legal Intelligence System

**Base URL:** `http://localhost:8000` (dev) / `https://api.your-domain.com` (prod)  
**All requests:** `Content-Type: application/json` unless noted  
**All responses:** JSON unless noted

---

## 1. Enterprise Endpoints

### POST `/api/enterprise/upload`
Upload a contract for full pipeline analysis.

**Request:** `multipart/form-data`
| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | Yes | PDF or DOCX, max 50MB |
| `org_id` | string | Yes | Organisation identifier |
| `project_id` | string | Yes | Project identifier |
| `filename` | string | No | Override filename |

**Response `202`:**
```json
{
  "job_id": "job_abc123",
  "status": "processing",
  "stream_url": "/api/stream/job_abc123"
}
```

**Response `400`:**
```json
{ "error": "Unsupported file type. Upload PDF or DOCX." }
```

---

### GET `/api/enterprise/job/{job_id}`
Get final results for a completed job.

**Response `200`:**
```json
{
  "job_id": "job_abc123",
  "status": "complete",
  "filename": "vendor_agreement.pdf",
  "duration_seconds": 38.4,
  "summary": {
    "total_clauses": 42,
    "violation": 2,
    "high": 5,
    "medium": 8,
    "low": 11,
    "compliant": 16
  },
  "clauses": [
    {
      "clause_id": "c_001",
      "clause_type": "data_processing",
      "text": "The vendor reserves unlimited rights...",
      "risk_level": "violation",
      "regulation": "DPDP_2023",
      "explanation": "Constitutes unlawful delegation of data fiduciary responsibility under Section 8(2) of DPDP Act 2023.",
      "confidence": 0.94,
      "redlined_text": "The vendor may sub-process client data only with named sub-processors listed in Schedule A, subject to written approval from the client and bound by equivalent data protection obligations.",
      "redline_explanation": "Limits sub-processing to named parties with explicit consent, compliant with DPDP Act 2023 Section 8(2).",
      "contradiction_hits": [],
      "historical_flags": []
    }
  ],
  "contradictions": [
    {
      "clause_a_id": "c_005",
      "clause_b_id": "c_017",
      "clause_a_text": "Data deleted within 30 days of termination.",
      "clause_b_text": "Vendor retains data for up to 90 days post-termination for audit purposes.",
      "explanation": "Clauses contradict each other on data retention period post-termination.",
      "severity": "high"
    }
  ],
  "historical_flags": [
    {
      "clause_id": "c_012",
      "text": "Arbitration shall be the sole remedy...",
      "flagged_in_job": "job_xyz789",
      "flagged_in_project": "vendor-contracts-2024",
      "flagged_date": "2024-11-15T10:23:00Z",
      "original_risk_level": "high"
    }
  ],
  "github_pr_url": "https://github.com/org/repo/pull/47",
  "audit_trail": {
    "file_hash": "sha256:abc123...",
    "timestamp": "2025-06-12T08:45:00Z"
  }
}
```

**Response `202`** (still processing):
```json
{ "job_id": "job_abc123", "status": "processing" }
```

---

### POST `/api/enterprise/chat`
RAG Q&A chat over a project's document set.

**Request:**
```json
{
  "org_id": "org_001",
  "project_id": "proj_001",
  "query": "Which vendor agreements allow sub-processing without explicit consent?",
  "conversation_history": [
    { "role": "user", "content": "How many contracts are in this project?" },
    { "role": "assistant", "content": "There are 7 contracts in this project." }
  ]
}
```

**Response `200`:**
```json
{
  "answer": "Two vendor agreements allow sub-processing without explicit consent: the Acme SaaS agreement (job_abc123, clause c_001) and the DataVendor contract (job_def456, clause c_014). Both clauses use broad language granting unlimited sub-processing rights.",
  "sources": [
    {
      "job_id": "job_abc123",
      "filename": "acme_agreement.pdf",
      "clause_id": "c_001",
      "clause_text": "The vendor reserves unlimited rights to sub-process...",
      "relevance_score": 0.91
    }
  ]
}
```

---

### GET `/api/enterprise/projects/{org_id}`
List all projects and their document counts for an organisation.

**Response `200`:**
```json
{
  "org_id": "org_001",
  "projects": [
    {
      "project_id": "proj_001",
      "name": "Vendor Contracts 2025",
      "document_count": 7,
      "last_updated": "2025-06-10T14:22:00Z",
      "violation_count": 3
    }
  ]
}
```

---

## 2. Consumer Endpoints

### POST `/api/consumer/photo`
Analyse a photographed physical document.

**Request:** `multipart/form-data`
| Field | Type | Required | Description |
|---|---|---|---|
| `image` | File | Yes | JPEG, PNG, WEBP |
| `preferred_language` | string | No | ISO 639-1 code, default `en` |

**Response `200`** (high confidence):
```json
{
  "status": "success",
  "ocr_confidence": 0.87,
  "detected_language": "kan",
  "detected_script": "Kannada",
  "analysis": { /* same shape as /analyse response */ }
}
```

**Response `200`** (low confidence):
```json
{
  "status": "low_confidence",
  "ocr_confidence": 0.54,
  "message": "The photo is unclear. Please retake in better lighting and ensure the full document is visible.",
  "analysis": null
}
```

---

### POST `/api/consumer/upload`
Analyse a PDF or DOCX document.

**Request:** `multipart/form-data`
| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | Yes | PDF or DOCX |
| `preferred_language` | string | No | ISO 639-1 code, default `en` |

**Response `200`:**
```json
{
  "status": "success",
  "detected_language": "en",
  "analysis": { /* same shape as /analyse response */ }
}
```

---

### POST `/api/consumer/analyse`
Analyse raw text (used by browser extension).

**Request:**
```json
{
  "text": "By clicking Accept you agree to the following terms...",
  "preferred_language": "en",
  "source": "extension"
}
```

**Response `200`:**
```json
{
  "status": "success",
  "analysis": {
    "summary": [
      "The company can share your name, email, and phone number with any of their business partners without asking you again.",
      "You agree not to sue them in court — all disputes go to private arbitration.",
      "They can change these terms at any time with only 7 days notice.",
      "Your subscription auto-renews unless you cancel 30 days before the renewal date.",
      "They can terminate your account for any reason with no refund."
    ],
    "unfair_clauses": [
      {
        "clause_text": "The company reserves the right to share user data with affiliated third parties at its discretion.",
        "explanation": "This means they can give your personal information to any company they choose, without asking you. You have no control over who gets your data.",
        "fair_alternative": "A fair version would say: we share your data only with the specific service providers you use, listed here, and only for the purpose of delivering your service."
      }
    ],
    "obligation_map": {
      "user_obligations": [
        "Pay the subscription fee monthly",
        "Not share your account credentials",
        "Cancel 30 days before renewal to avoid charge",
        "Use arbitration for all disputes — no court claims"
      ],
      "company_obligations": [
        "Provide the service (no uptime guarantee specified)",
        "Give 7 days notice before changing terms"
      ]
    },
    "ambiguity_flags": [
      {
        "term": "trusted partners",
        "explanation": "This term is never defined. It could mean any company they choose. Vague terms in contracts almost always benefit the party that wrote the contract."
      },
      {
        "term": "reasonable notice",
        "explanation": "No specific timeframe is given. This makes it impossible to know how much warning you will actually get."
      }
    ],
    "benchmark_comparisons": [
      {
        "finding": "Auto-renewal cancellation window is 30 days",
        "context": "Most subscription services require 7–14 days notice. This 30-day window is stricter than average and easy to miss."
      }
    ],
    "risk_level": "high",
    "disclaimer": "This analysis is for awareness and education only. It is not legal advice. For documents with significant financial or legal consequences, please consult a qualified lawyer."
  }
}
```

---

### POST `/api/consumer/prescan`
Quick pre-scan used by browser extension to set icon colour. Fast, no full analysis.

**Request:**
```json
{ "text": "By clicking Accept you agree to..." }
```

**Response `200`:**
```json
{
  "high_risk": true,
  "risk_indicators": ["unlimited data sharing", "mandatory arbitration", "auto-renewal"]
}
```

---

## 3. SSE Stream Endpoint

### GET `/api/stream/{job_id}`
Server-Sent Events stream for real-time pipeline progress.

**Response:** `text/event-stream`

**Event shapes:**

```
data: {"event": "ingest_complete", "job_id": "job_abc123", "timestamp": "..."}

data: {"event": "extraction_complete", "job_id": "job_abc123", "clause_count": 42}

data: {"event": "memory_scan_complete", "job_id": "job_abc123", "contradictions": 2, "historical_flags": 1}

data: {"event": "classification_progress", "job_id": "job_abc123", "done": 10, "total": 42}

data: {"event": "classification_complete", "job_id": "job_abc123"}

data: {"event": "redline_complete", "job_id": "job_abc123", "redlined_count": 7}

data: {"event": "pipeline_complete", "job_id": "job_abc123", "pr_url": "https://github.com/...", "violation_count": 2, "duration_seconds": 38.4}

data: {"event": "pipeline_error", "job_id": "job_abc123", "error": "All Groq tokens exhausted"}
```

**Frontend usage:**
```typescript
const es = new EventSource(`/api/stream/${jobId}`)
es.onmessage = (e) => {
  const event = JSON.parse(e.data)
  // handle by event.event string
  if (event.event === "pipeline_complete") es.close()
}
```

---

## 4. Error Responses

All error responses follow this shape:
```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE_SLUG",
  "details": {}
}
```

| HTTP Code | When |
|---|---|
| `400` | Invalid file type, missing required fields |
| `404` | Job ID not found |
| `429` | All Groq tokens exhausted (rare with pool) |
| `500` | Unexpected pipeline failure |
| `503` | Ollama / ChromaDB not reachable |
