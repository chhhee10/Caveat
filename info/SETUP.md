# Setup Guide
## AI Contract & Legal Intelligence System

---

## 1. Prerequisites

- Python 3.11+
- Node.js 20+
- Git
- Ubuntu 22.04+ or macOS (Tesseract Indian language packs easiest on Linux)
- 4 separate Groq accounts (one per team member email)
- GitHub account + personal access token (repo + PR scope)
- Slack workspace + incoming webhook URL
- Google account (for Google Translate API free tier)

---

## 2. Groq Account Setup

Each team member creates one free Groq account at https://console.groq.com

No credit card required. Get API key from console → API Keys → Create Key.

Collect all four keys — they go in `.env` as `GROQ_KEY_1` through `GROQ_KEY_4`.

**Important:** Four keys from ONE account share the same rate limit. You need four separate email signups.

---

## 3. System Dependencies

### Ubuntu / Debian
```bash
# Tesseract with Indian language packs
sudo apt-get update
sudo apt-get install -y \
  tesseract-ocr \
  tesseract-ocr-hin \
  tesseract-ocr-kan \
  tesseract-ocr-tam \
  tesseract-ocr-tel \
  tesseract-ocr-mal \
  tesseract-ocr-ben \
  tesseract-ocr-eng

# Verify
tesseract --list-langs
```

### macOS
```bash
brew install tesseract tesseract-lang
```

---

## 4. Ollama Setup (Local Embeddings — Free, No API Cost)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull embedding model
ollama pull nomic-embed-text

# Verify it's running
ollama list
# Should show: nomic-embed-text

# Ollama runs as a service on http://localhost:11434
# No API key needed
```

---

## 5. IndicTrans2 Setup (Indian Language Translation)

```bash
cd backend
git clone https://github.com/AI4Bharat/IndicTrans2.git
cd IndicTrans2
pip install -r requirements.txt

# Download model (choose the pair you need — en-indic and indic-en)
python -c "
from huggingface_hub import snapshot_download
snapshot_download(repo_id='ai4bharat/indictrans2-en-indic-1B', local_dir='./models/en-indic')
snapshot_download(repo_id='ai4bharat/indictrans2-indic-en-1B', local_dir='./models/indic-en')
"
```

---

## 6. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill environment file
cp .env.example .env
```

### `.env.example`
```env
# Groq — 4 separate accounts required
GROQ_KEY_1=gsk_xxxxxxxxxxxxxxxxxxxx
GROQ_KEY_2=gsk_xxxxxxxxxxxxxxxxxxxx
GROQ_KEY_3=gsk_xxxxxxxxxxxxxxxxxxxx
GROQ_KEY_4=gsk_xxxxxxxxxxxxxxxxxxxx

# GitHub
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
GITHUB_REPO=your-org/your-repo

# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/xxx/xxx

# Google Translate (free tier — 500,000 chars/month)
GOOGLE_TRANSLATE_API_KEY=AIzaxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Ollama (local — no key needed)
OLLAMA_BASE_URL=http://localhost:11434
EMBED_MODEL=nomic-embed-text

# ChromaDB (local)
CHROMA_PERSIST_DIR=./chroma_db

# SQLite
DATABASE_URL=sqlite:///./contracts.db
```

### Initialise Database
```bash
python -c "from db.models import Base; from sqlalchemy import create_engine; engine = create_engine('sqlite:///./contracts.db'); Base.metadata.create_all(engine); print('DB initialised')"
```

### Run Backend
```bash
uvicorn main:app --reload --port 8000
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

---

## 7. Frontend Setup

```bash
cd frontend
npm install

# Create env file
cp .env.example .env.local
```

### `frontend/.env.example`
```env
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

```bash
npm run dev
# Frontend at http://localhost:3000
```

---

## 8. Browser Extension Setup

```bash
# No build step needed for hackathon — load unpacked
```

1. Open Chrome → `chrome://extensions`
2. Enable **Developer Mode** (top right toggle)
3. Click **Load unpacked**
4. Select the `/extension` folder
5. Pin the extension to toolbar

**Before loading:** update `API_BASE` in `extension/background.js`:
```javascript
const API_BASE = "http://localhost:8000"  // dev
```

---

## 9. GitHub Setup for PR Output

1. Create a repo (or use existing): `your-org/contract-reviews`
2. Generate Personal Access Token: GitHub → Settings → Developer Settings → PAT (classic)
   - Scopes needed: `repo` (full)
3. Add to `.env` as `GITHUB_TOKEN` and `GITHUB_REPO`

The pipeline will auto-create branches and PRs in this repo.

---

## 10. Slack Setup for Alerts

1. Go to https://api.slack.com/apps → Create New App → From Scratch
2. Incoming Webhooks → Activate → Add to channel
3. Copy webhook URL → add to `.env` as `SLACK_WEBHOOK_URL`

---

## 11. Google Translate API Setup (Free Tier)

Free tier: 500,000 characters per month — sufficient for hackathon.

1. Go to https://console.cloud.google.com
2. Create new project
3. Enable Cloud Translation API
4. Create API key → APIs & Services → Credentials
5. Add to `.env` as `GOOGLE_TRANSLATE_API_KEY`

---

## 12. Verify Full Stack

```bash
# Terminal 1 — Ollama
ollama serve

# Terminal 2 — Backend
cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000

# Terminal 3 — Frontend
cd frontend && npm run dev

# Check backend health
curl http://localhost:8000/health
# Expected: {"status": "ok", "ollama": "ok", "chromadb": "ok"}
```

---

## 13. Regulation Corpus Files

Create these files in `backend/regulations/`:

### `dpdp_2023.json` (minimal structure)
```json
{
  "name": "Digital Personal Data Protection Act 2023",
  "short": "DPDP_2023",
  "key_provisions": [
    {
      "section": "8(2)",
      "topic": "data_fiduciary",
      "requirement": "Data fiduciary cannot delegate processing responsibilities to sub-processors without explicit written consent and binding contractual obligations on the sub-processor.",
      "penalty": "Up to INR 250 crore per violation"
    },
    {
      "section": "6",
      "topic": "consent",
      "requirement": "Consent must be free, specific, informed, unconditional, and unambiguous. Bundled consent is not permitted.",
      "penalty": "Up to INR 50 crore"
    }
  ]
}
```

### `gdpr.json` and `rbi_guidelines.json` — same structure, covering respective provisions.

---

## 14. Common Issues

| Issue | Fix |
|---|---|
| `tesseract: command not found` | Reinstall tesseract, verify with `which tesseract` |
| `ollama: connection refused` | Run `ollama serve` in a separate terminal |
| `ChromaDB: collection already exists` | Safe to ignore — `get_or_create_collection` handles this |
| Groq 429 on all tokens | All 4 accounts hit daily limit — wait or use next day |
| GitHub PR creation fails | Check PAT has `repo` scope, verify `GITHUB_REPO` format is `org/repo` |
| IndicTrans2 model not found | Re-run the snapshot_download step; check `./models/` directory |
