# VORIS

Autonomous Universal Responsive Assistant

VORIS is a local-first, JARVIS-style assistant prototype that combines chat, document generation, controlled desktop actions, voice scaffolding, memory, and a safety-first execution model.

VORIS is currently a **Level 3 / early Level 4 JARVIS-style assistant prototype**. It is useful for controlled local demos and continued development, but it is **not** a finished production assistant and it is **not** real JARVIS-level autonomy.

## What VORIS Is

- A FastAPI-based assistant runtime with a modern `web_v2` interface.
- A controlled assistant system that can answer, plan, generate documents, launch safe apps, run limited browser actions, and perform permission-gated OS automation.
- A truth-first project: unsupported, unsafe, or dependency-based capabilities should be labeled clearly instead of pretending to work.

## What VORIS Is Not

- Not a production-ready personal AI operating system.
- Not a fully autonomous desktop controller.
- Not a Level 5 real JARVIS system.
- Not safe for unrestricted passwords, banking, payments, destructive file operations, or arbitrary shell execution.
- Not guaranteed to run every voice, OCR, provider, or automation feature on every machine without local dependencies.

## Current Status

Status: active local development and controlled demo readiness.

The stable path is:

`run_VORIS.py` -> FastAPI app in `api/api_server.py` -> runtime/brain/tools/security modules -> `interface/web_v2`

The project currently has a broad automated test suite. At the latest stable milestone, the local unittest suite covered more than 250 tests, with the recent full run reporting 293 passing tests.

## Key Features

- Chat-first VORIS interface with orb state presence.
- ChatGPT-style progressive response rendering with safe markdown/code display.
- Authenticated and public session handling.
- Scoped memory and personalization safeguards.
- Provider-backed response generation with degraded fallback behavior.
- Document generation for notes, assignments, PDF, DOCX, TXT, and PPTX outputs.
- Direct document download delivery and preview cards.
- **Pollinations Image Generation Bypass** — regex-based command interception in `api/api_server.py` that strips natural-language image triggers, builds a Pollinations URL, and returns immediately with `execution_mode: "image_bypass"` (skips the standard text engine, provider routing, and the older `tools/image_generation.py` unavailable stub on `/api/chat`).
- Provider-ready image generation abstraction (`tools/image_generation.py`) for non-trigger phrasing; still reports unavailable until a verified adapter is configured.
- Controlled desktop app launching for allowlisted apps.
- Controlled browser actions such as safe URL/search flows.
- Permission-gated OS automation wrappers for limited actions.
- Basic screen capture and OCR-based safety checks.
- Browser push-to-talk and desktop voice runtime scaffolding.
- Trust model for safe, private, sensitive, and critical actions.

## Architecture Overview

```text
User input
  -> API layer
  -> identity/session context
  -> intent routing
  -> permissions/trust check
  -> provider, document, Pollinations image bypass, action, automation, or fallback path
  -> response shaping
  -> memory update where safe
  -> web_v2 delivery
```

Important paths:

- `run_VORIS.py` - supported local launcher.
- `api/api_server.py` - live FastAPI API.
- `brain/` - runtime orchestration, response quality, providers, traces.
- `security/` - sessions, permissions, trust enforcement.
- `memory/` - scoped memory and personalization data.
- `tools/` - documents, desktop control, browser actions, OS automation, screen capture.
- `voice/` - browser-independent desktop voice runtime scaffolding.
- `interface/web_v2/` - current browser interface.
- `tests/` - regression and system behavior tests.

## Response Rendering and Artifacts

VORIS uses public, standard AI-app patterns for the writing experience:

- progressive response rendering through `/api/chat/stream`;
- safe markdown rendering in `web_v2`;
- readable code blocks with copy-code controls;
- document artifacts/cards for generated deliverables;
- Pollinations image bypass responses delivered with `image_url` and `execution_mode: "image_bypass"` (streaming disabled for this path so the UI does not flash the raw URL).
- Legacy `tools/image_generation.py` hooks that stay honest when no provider adapter is configured.

See `docs/RESPONSE_RENDERING.md`.

### Pollinations Image Generation Bypass

When a chat message matches the trigger pattern at the start of the text:

```text
^(generate|create|make|draw)\s+(an?\s+)?(image|picture|photo|drawing)\s+(of\s+)?
```

`api_server.py` uses `re.sub` to remove the trigger, URL-encodes the remaining prompt, and returns:

```text
https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true
```

Active on:

- `POST /api/chat` (primary `web_v2` path) via `_try_pollinations_image_bypass()` before `detect_image_generation_request()`.
- `POST /chat` (legacy compatibility) with the same regex helper.

The frontend (`interface/web_v2/app.js`) checks `execution_mode === "image_bypass"` or `image_url` in `buildMessageRow()` and appends an inline `<img>` (styled in `styles.css`) instead of printing the URL as the assistant reply text.

## Safety and Trust Model

VORIS uses trust levels to prevent unsafe behavior:

- `safe` - normal chat, document generation, safe app open/search.
- `private` - user/account information and memory-related actions.
- `sensitive` - keyboard/mouse control, typing into apps, screen-aware automation.
- `critical` - passwords, payments, banking, destructive actions, account/security changes.

Critical actions must remain blocked or require a stronger verification flow. VORIS must not silently control the system.

## Setup

Prerequisites:

- Windows is the primary development target.
- Python 3.10+ recommended.
- Node.js for JavaScript syntax checks.
- Optional local dependencies for voice, OCR, DOCX/PDF/PPTX export, and automation.

Create and activate a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Create a local `.env` file only for your own machine. Do not commit secrets.

## Run

```powershell
python run_VORIS.py
```

Then open:

```text
http://127.0.0.1:5000/
```

Useful health check:

```powershell
python tools/health_check.py
```

## Test

```powershell
python -m py_compile run_VORIS.py api\api_server.py
node --check interface\web_v2\app.js
node --check interface\web_v2\auth.js
python -m unittest discover -s tests -p "test_*.py"
```

## Usage

Open `http://127.0.0.1:5000/`, type in the chat composer, and send. Most requests flow through `POST /api/chat` (or `/api/chat/stream` for progressive text).

### Image generation (Pollinations bypass)

Start your message with a supported trigger, then describe what you want. Examples:

- `draw a picture of a horse`
- `make an image of a cyberpunk city`
- `generate an image of a calm cyan assistant orb`
- `create a photo of a mountain lake at sunset`
- `draw a drawing of a robot reading a book`

VORIS strips the trigger words (including optional `a` / `an` and trailing `of`), calls Pollinations, and the assistant bubble shows the generated image inline when the API returns `execution_mode: "image_bypass"` and `image_url`.

Phrasing that does not match the regex at the start of the message may fall through to the standard chat engine or the honest unavailable image provider stub instead of the bypass.

## Demo Commands

Safe demo commands:

- `hello`
- `explain artificial intelligence simply`
- `write a 3 page assignment on climate change`
- `make notes on transformers`
- `open chrome and search AI trends`
- `draw a picture of a horse` or `make an image of a cyberpunk city` for inline Pollinations output
- `open notepad and type hello` then approve control if the environment supports it
- `type my password` to show critical blocking

Avoid demoing:

- Banking, payment, password, or destructive workflows.
- Full always-on voice claims unless the desktop voice runtime is explicitly enabled and verified.
- Broad screen understanding beyond OCR-level context.
- Unsupported apps or arbitrary shell commands.

## Screenshots

Screenshots are not committed in this cleanup pass. Add verified screenshots later under `docs/screenshots/` and reference them here.

Suggested screenshots:

- VORIS web_v2 chat shell.
- Document delivery card.
- Action plan approval card.
- Desktop voice status panel.
- Blocked critical action example.

## Limitations

- Voice reliability depends on local microphone, STT, TTS, and optional runtime dependencies.
- Provider reliability currently depends heavily on configured provider keys, especially Groq in local development.
- Pollinations bypass requires network access to `image.pollinations.ai`; image quality and availability depend on that service.
- Non-regex image requests still use `tools/image_generation.py`, which remains provider-ready but inactive until a verified adapter is configured.
- OCR screen awareness is useful for safety checks but not deep visual understanding.
- OS automation is intentionally narrow and permission-gated.
- Long-form document quality is improving but still needs stronger research and references.
- Memory is scoped and safer than earlier builds, but long-term personalization still needs more hardening.

## Roadmap

Near-term focus:

- Runtime reliability and Windows startup polish.
- Memory and identity isolation.
- Desktop voice reliability.
- Provider health truth and fallback quality.
- Document intelligence polish.
- Screen awareness and automation robustness.
- UI/orb polish and demo packaging.

See `ROADMAP.md` for the full plan.

## License / Status

No license file is currently present. Until a license is added, this repository should be treated as private/all-rights-reserved by default.
Collaborator added: Syed Abdur Raffay
# VORIS (Voice-Oriented Responsive Intelligence System)

A secure, local Personal AI Workspace featuring custom smart-routing, a dark-mode UI, and in-browser data processing.

## 🚀 Recent Updates: Local File RAG Pipeline
VORIS now supports lightweight, memory-safe Retrieval-Augmented Generation (RAG) for local file analysis (CSV/TXT) without relying on heavy Vector Databases.

### **Features:**
* **Seamless UI Integration:** Added a sleek file upload interface directly into the chat composer with dynamic attachment badges.
* **Frontend Chunking & Memory Safety:** To prevent API timeouts and local server crashes, files are read natively in the browser via JavaScript `FileReader`, safely truncated to a 2000-character limit, and attached to the user's prompt as raw text.
* **Smart Traffic Routing:** The frontend `classifyCommand` traffic cop was re-architected. VORIS now intelligently ignores dead/spam URLs inside uploaded datasets (preventing rogue new tabs) and forces the system into an internal analysis route when a file is present.
* **DOM Optimization:** Cleaned up ghost elements and duplicate component IDs in the `app-shell` to ensure smooth CSS rendering and layout stability.

### **Architecture Flow:**
1. User attaches a file via the `+` button.
2. JS intercepts the file, reads it as text, and enforces memory limits.
3. The raw user text is classified (bypassing external URL triggers if a file is present).
4. The file data is stapled to the user's prompt.
5. The combined payload is routed to the Python (FastAPI) backend for AI processing.
# VORIS Backend Update: SambaNova Migration & Stability Fixes

## ⚠️ Critical Architectural Changes

### 1. Engine Migration: SambaNova API
The core routing engine has been migrated to SambaNova to completely bypass previous TPM (Tokens Per Minute) rate limits, allowing for massive, uninterrupted 4096-token outputs.
* **Text Engine:** `Meta-Llama-3.3-70B-Instruct`
* **Vision Engine:** `Llama-3.2-11B-Vision-Instruct`
* **Action Required:** Generate a free API key at [cloud.sambanova.ai](https://cloud.sambanova.ai/).

### 2. Security Configuration (.env)
API keys are no longer hardcoded into the Python execution files. You must create a `.env` file in the root directory and add it to your `.gitignore`.
```env
SAMBANOVA_API_KEY=your_actual_key_here
# 1. Force Python 3.12 Virtual Environment creation
py -3.12 -m venv venv

# 2. Activate the environment
.\venv\Scripts\Activate.ps1

# 3. Install core C-compiled and standard dependencies
pip install fastapi pydantic waitress python-dotenv openai cffi cryptography

# 4. Direct Launch
python run_aura.py