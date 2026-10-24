# N.E.X.U.S.

## Networked EXpert for Unified Synthesis

*A direct-command assistant — clear requests, supported actions, honest results.*

**A Windows-first, local-first AI assistant that understands requests, runs direct commands, manages files, research, and documents, and reports clear results.**

[![Python](https://img.shields.io/badge/Python-3.10--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Windows](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Playwright](https://img.shields.io/badge/Browser-Playwright-45BA4B?logo=playwright&logoColor=white)](https://playwright.dev/)

> **NEXUS is built around direct commands, not a chat-only interface:**  
> **Understand → Respond → Act on supported commands → Report clearly**

---

## What is NEXUS?

NEXUS is an open development project for a **general-purpose AI assistant for Windows**.

Instead of only generating text, NEXUS turns natural-language instructions into supported direct actions and reports clear results.

The goal is a single assistant with many tools — not a collection of disconnected utilities.

### Core idea

```text
                    USER
                      │
                      ▼
              ┌───────────────┐
              │    N.E.X.U.S  │
              │ Command Layer │
              └───────┬───────┘
                      │
             Understand request
                      │
                      ▼
                 Direct command
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
    COMPUTER       BROWSER        OFFICE
        │             │             │
        └─────────────┼─────────────┘
                      ▼
                 Clear result
```

---

## What can NEXUS do?

### 🧠 Natural-language commands

- Natural-language command understanding
- Direct single-step actions
- Conversation history and memory
- Reminders, notes, and todos
- Clear spoken and logged results

### 🖥️ Windows computer control

- Windows UI Automation (UIA)
- Application and window discovery
- Semantic element discovery
- Clicking, typing, scrolling and keyboard shortcuts
- Clipboard operations
- Window management
- Screenshots
- OCR and vision-assisted inspection
- Bounded, recoverable automation

### 🌐 Browser automation

- Chromium control through Playwright
- Navigation and searching
- Form filling and interaction
- Tabs and screenshots
- Web-content extraction
- Boilerplate/navigation cleanup before research analysis
- Image searching for generated documents and presentations

### 📄 Research → Word / PowerPoint

NEXUS is designed to **analyze research before generating an artifact**.

```text
Discover
   ↓
Extract
   ↓
Clean
   ↓
Analyze
   ↓
Compare
   ↓
Synthesize
   ↓
Generate
   ↓
Verify
```

It can generate:

- Word documents with `python-docx`
- PowerPoint presentations with `python-pptx`
- Tables and charts
- Research reports
- Source-based summaries
- Presentation images
- PDF text extraction

Generated artifacts are exposed through the NEXUS files/gallery system.

### 📁 File analysis & document Q&A

- Analyze uploaded files
- Extract document text
- Ask questions about file contents
- OCR image/scanned documents
- Process code files
- Produce corrected versions of supported files

### 🛠️ Code Intelligence

NEXUS includes a Code Core for inspecting and repairing its own codebase.

- AST / syntax checks
- `py_compile` validation
- Per-file issue detection
- Code health information
- Nemotron/NVIDIA-powered repair
- Preview → Apply Patch workflow
- Validation after changes
- Automatic rollback on failed repairs
- Large-file segmented repair
- Uploaded-file inspection and refactoring

### 🎙️ Voice

NEXUS includes Windows/browser-oriented voice capabilities and is designed to support natural voice interaction as the project evolves.

### 📱 Additional capabilities

NEXUS also contains **Android/ADB and phone-mirroring functionality**.

These capabilities are part of the project but are **not the current primary development focus**. Current development is concentrated on Windows commands, browser control, memory, research, voice and code intelligence.

The same principle applies to supporting utilities such as the watchdog: they remain part of the project where implemented, even when they are not the current development priority.

### 🗄️ Zetaris AI Data Gateway (Read-Only SQL)

NEXUS includes a read-only connector for the **Zetaris AI Data Gateway** — a local data virtualization platform that exposes registered data sources (PostgreSQL, MySQL, CSV, Parquet, etc.) through a unified SQL interface.

**Commands:**
```
zetaris: test connection
zetaris: query SELECT * FROM NY_TAXI.customers LIMIT 2
zetaris: run SELECT COUNT(*) FROM NY_TAXI.trips
zetaris: SELECT * FROM TPCDS_DB.store_sales LIMIT 5
```

**Features:**
- HTTP Basic authentication via Zetaris UI proxy (port 3000)
- Bearer token session management (auto-login, cached in memory)
- SELECT/WITH queries only — writes and DDL rejected
- Configurable row limits (default 50, max 100 per query)
- Query pagination (auto-fetches additional pages up to limit)
- Query token cleanup (always closes server-side cursor)
- Timeouts and error handling with actionable messages
- Credentials stored in gitignored `config.json` (never committed)

**Requires:** Local Zetaris deployment (Docker Compose) with sample data (NY_TAXI, TPCDS_DB).

---

## Architecture

NEXUS separates the model layer from the tool/runtime layer.

### Model roles

- **Gemini** — conversation and supported vision tasks
- **NVIDIA NIM / Nemotron** — code intelligence and repair workflows
- Other configured providers can be used for supported optional features

### Runtime

```text
NEXUS
│
├── Command Runtime (/api/command)
│   ├── Memory / conversation history
│   ├── Notifications / reminders
│   ├── Voice / language helpers
│   └── Recovery (crash repair with rollback)
│
├── Computer Tools
│   └── Windows UI Automation
│
├── Browser Tools
│   └── Playwright / Chromium
│
├── Office Tools
│   ├── Word
│   ├── PowerPoint
│   └── Charts
│
├── Research
│   └── Analyze → Compare → Synthesize
│
├── Vision / OCR
│
├── Code Core
│   └── Audit → Repair → Validate → Rollback
│
├── Voice
│
├── Android / ADB
│
└── React + Vite Dashboard
```

### Repository structure

```text
NEXUS/
├── main.py
├── agent.py
├── system_ops.py
├── code_core.py
├── document_intel.py
├── phone_control.py
├── start_nexus.py
├── google_oauth.py
│
├── backend/
│   ├── agent/
│   │   ├── notifications.py
│   │   ├── phase1_memory.py
│   │   ├── phase1_runtime.py
│   │   ├── voice.py
│   │   ├── lang_detect.py
│   │   ├── hindi.py
│   │   ├── marathi.py
│   │   └── human_replies.py
│   │
│   └── tools/
│       ├── computer.py
│       ├── browser.py
│       ├── office.py
│       ├── charts.py
│       └── vision.py
│
├── src/                    # React + Vite dashboard
├── tests/
├── requirements.txt
└── README.md
```

---

## Why NEXUS?

The project is focused on moving from:

```text
AI that tells you what to do
          ↓
AI that understands commands
          ↓
AI that acts on supported tasks
          ↓
AI that reports results clearly
          ↓
AI that stays within its scope
```

The important part is **clear, honest results**.

NEXUS should not simply say:

> "Done."

It reports what it did, and says plainly when something is outside its scope.

---

## Requirements

### System

- Windows 10/11
- Python 3.10–3.14
- Node.js 18+
- npm
- Google Chrome/Chromium for Playwright

### Optional service credentials

NEXUS can use configured external AI services for specific capabilities. Credentials are feature-dependent.

| Configuration | Purpose |
|---|---|
| `gemini_api_key` | Conversation, memory, supported vision/OCR and document Q&A |
| `nvidia_api_key` | Code intelligence / Nemotron workflows |
| `huggingface_api_key` | Optional image-generation fallback |
| `groq_api_key` | Cloud fallback for voice transcription (free at console.groq.com) |
| Google OAuth configuration | Supported protected Google features |
| `zetaris_base_url` | Zetaris UI origin (default: http://localhost:3000) |
| `zetaris_username` | Zetaris login email |
| `zetaris_password` | Zetaris login password |
| `zetaris_org_id` | Numeric organization ID from Zetaris UI |
| `zetaris_default_limit` | Default rows per query (1-100, default: 50) |
| `zetaris_max_limit` | Hard cap on rows per query (1-100, default: 100) |
| `zetaris_timeout_seconds` | Request timeout (default: 30) |

The project is designed so that missing optional credentials produce a clear feature-specific limitation rather than silently pretending a capability worked.

Python dependencies are listed in **`requirements.txt`**.

---

## Installation

Clone the repository:

```bash
git clone https://github.com/TAHA-SHAIKH27/NEXUS.git
cd NEXUS
```

Create a virtual environment:

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

Install Playwright Chromium:

```bash
python -m playwright install chromium
```

Install frontend dependencies:

```bash
npm install
```

Configure the services you want to use through the project's local configuration.

**Never commit API keys, OAuth secrets, browser credentials or personal data.**

---

## First run on a new machine

NEXUS is **offline-first**: a fresh clone with *zero* API keys still runs. Local commands (volume, screenshots, timers, files, math, weather via IP location, jokes, Hindi/Marathi/English offline replies), reminders, notes and the full dashboard all work. AI features light up as you add keys below.

### 1. Add API keys (all optional, easiest via the UI)

Open the dashboard → **Settings** (gear icon) and paste keys, or create `config.json` in the project root (it is gitignored — never commit it):

```json
{
  "gemini_api_key": "AIza… or AQ.…",
  "huggingface_api_key": "hf_…",
  "gemini_project_id": "",
  "groq_api_key": "",
  "nvidia_api_key": "nvapi-…",
  "nvidia_model": "z-ai/glm-5.3-flash",
  "zetaris_base_url": "http://localhost:3000",
  "zetaris_username": "admin@zetaris.com",
  "zetaris_password": "Zetaris1@",
  "zetaris_org_id": "1",
  "zetaris_default_limit": 50,
  "zetaris_max_limit": 100,
  "zetaris_timeout_seconds": 30
}
```

| Key | Unlocks |
|---|---|
| `gemini_api_key` | Full conversation, memory, vision, document Q&A (or link Google in Settings instead) |
| `groq_api_key` | Cloud fallback for voice transcription (free at console.groq.com) |
| `nvidia_api_key` | Code Core audits and repairs |
| `huggingface_api_key` | Image generation |
| `zetaris_*` | Zetaris AI Data Gateway read-only SQL queries (requires local Zetaris deployment) |

| Key | Unlocks |
|---|---|
| `gemini_api_key` | Full conversation, memory, vision, document Q&A (or link Google in Settings instead) |
| `groq_api_key` | Cloud fallback for voice transcription (free at console.groq.com) |
| `nvidia_api_key` | Code Core audits and repairs |
| `huggingface_api_key` | Image generation |

### 2. Optional `.env` file

```bash
Copy-Item .env.example .env
```

Only needed for phone mirroring (`NEXUS_ADB_PATH`, `NEXUS_PHONE_PIN`) or voice fallback (`GROQ_API_KEY`). Everything has a working default without it.

### 3. Optional: Gmail + Google

- **Gemini via Google account:** Settings → *Link Google* (no key needed).
- **Gmail reading/sending:** Settings → *Link Gmail*. First link needs a Google Cloud **Desktop-app** OAuth client saved as `client_secret.json` in the project root (gitignored). Without it, mail features simply report "not linked" — nothing breaks.

### 4. Optional components (all degrade gracefully if missing)

| Component | Install | If missing |
|---|---|---|
| OCR text in screenshots | Tesseract binary (`winget install UB-Mannheim.TesseractOCR`) | OCR steps report unavailable |
| Phone mirror / ADB control | `adb` + `scrcpy` on PATH, `ws-scrcpy/` folder | Phone panel reports unavailable |
| Desktop app window | `npm run build`, then `npm run electron` (dev: backend + `npm run dev` + `npm run electron`) | Use the browser at `:3000` instead |

All runtime folders (`work_files/`, `backend/data/`, `downloads/`) are **auto-created on first run** — there is nothing to copy from another machine, and nothing personal is required.

### Troubleshooting a fresh clone

- `vite` / `uvicorn` not recognized → virtualenv or `node_modules` step missed above.
- Port `3000`/`8000` in use → stop the other copy; the ports are fixed (`vite.config.js`, `main.py`).
- `python -m playwright install chromium` fixes "browser won't launch".
- PowerShell blocks `.venv\Scripts\activate` → `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- Blank AI answers with no keys → expected: you're in offline mode; add a Gemini key or link Google.

---

## Running NEXUS

The convenience launcher can start the backend and frontend:

```bash
python start_nexus.py
```

Or run them separately:

```bash
# Backend
.venv\\Scripts\\activate
uvicorn main:app --host 127.0.0.1 --port 8000

# Frontend
npm run dev
```

The dashboard normally runs at:

```text
http://localhost:3000
```

The FastAPI documentation is available at:

```text
http://127.0.0.1:8000/docs
```

---

## Development principles

1. Prefer semantic UI Automation over guessed coordinates.
2. Report results honestly instead of assuming success.
3. Keep actions bounded and recoverable.
4. Make targeted changes and fix root causes rather than symptoms.
5. Preserve existing working functionality.

---

## Security

Never commit:

- API keys
- OAuth credentials
- `.env` files containing secrets
- `config.json` containing live credentials
- `client_secret.json`
- Authentication cookies
- Browser profiles containing personal sessions
- Private certificates
- Personal/private data

Use environment variables or a **gitignored** local configuration file.

---

## Current development focus

NEXUS contains many capabilities, but development is intentionally focused rather than attempting to build everything simultaneously.

### Current priority

- Conversation and memory
- Browser automation
- Voice
- Research and document generation
- Code Intelligence

### Existing but lower-priority capabilities

- Android / ADB integration
- Phone mirroring
- Watchdog/support utilities
- Additional experimental integrations

These remain part of NEXUS. They are simply outside the main development path at the moment.

---

## Roadmap

### Phase 1 — Conversation and Memory
Memory, context, and reminders.

### Phase 2 — Desktop Control & Vision
Windows UI Automation, browser control, and vision support.

### Phase 3 — Research & Presentation Generation
Source extraction, analysis, comparison, synthesis and structured Word/PPT generation.

### Phase 4 — Document & File Expansion
Charts, tables, document gallery and broader file support.

### Phase 5 — Code Intelligence
Self-audit, Nemotron repair, validation, rollback and uploaded-file inspection.

### Future expansion

Continue improving the core assistant while gradually bringing additional existing capabilities into the main workflow.

---

## Contributing

NEXUS is an evolving project.

If you want to contribute:

1. Understand the current architecture.
2. Keep changes focused.
3. Preserve existing functionality.
4. Test changes before submitting them.
5. Document meaningful architectural changes.
6. Avoid committing secrets, generated runtime state or personal files.

---

## License

No open-source license has currently been declared in this repository. Until a license is added, the source remains subject to the repository owner's default copyright.

---

## Project

**N.E.X.U.S. — Networked EXpert for Unified Synthesis**

*A direct-command assistant — clear requests, supported actions, honest results.*

Built with the goal of creating a capable, transparent and extensible AI assistant for everyday computer tasks.
