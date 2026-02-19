## Agentic Requirement Document Generator (Gemini-based)

This project is a small **agentic AI pipeline** that:

- Takes a **client conversation transcript** (or text from audio)
- Extracts **structured requirements**
- Detects **ambiguities and gaps**
- Generates **follow-up clarification questions**
- Produces a **professional Markdown requirement document**

It is designed around 5 logical agents:

- Transcription Agent (audio → text; here you provide text or hook in your own STT)
- Requirement Analyzer Agent
- Ambiguity Detection Agent
- Question Generation Agent
- Documentation Agent

The language model backend is **Gemini** via the official `google-generativeai` Python SDK.

> **Important:** Never hardcode your API key. Set it via environment variables instead.

---

### 1. Setup

1. Create and activate a virtual environment (optional but recommended):

```bash
cd "E:\BTP FINAL"
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set your Gemini API key as an environment variable:

On Windows PowerShell:

```powershell
$env:GEMINI_API_KEY = "YOUR_REAL_KEY_HERE"
```

(Or create a `.env` file with `GEMINI_API_KEY=...`.)

#### Recommended: use `.env` (avoid leaking keys)

Create a file `E:\BTP FINAL\.env` (it is ignored by git via `.gitignore`) and put:

```text
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

Then just run the commands normally without pasting keys into chat or terminal history.

### Using Groq instead of Gemini

If you want to use **Groq** as the LLM backend (instead of Gemini), set:

```powershell
$env:GROQ_API_KEY = "YOUR_GROQ_KEY"
$env:GROQ_MODEL = "llama-3.3-70b-versatile"
```

Then run with `--provider groq`.

> Never “scrape” another provider’s API or reuse credentials across services. Use each provider’s official SDK and your own key.

---

### 2. Running the pipeline

The main entry point is `main.py`. It expects a plain-text transcript file for now
(you can later plug in real audio transcription):

```bash
python main.py --transcript sample_conversation.txt --output requirements.md
```

#### Offline demo mode (no API key)

If you want to run the full pipeline **without Gemini**, use `--mock`:

```bash
python main.py --mock --transcript sample_conversation.txt --output requirements.md
```

#### Using Groq

```bash
python main.py --provider groq --transcript sample_conversation.txt --output requirements.md
```

#### Quick env check (recommended)

Before running `--provider groq` or `--provider gemini`, verify your environment is set (without printing secrets):

```bash
python check_env.py
```

This will:

- Run the **Requirement Analyzer Agent** on the conversation
- Run **Ambiguity Detection** and **Question Generation**
- Produce a final **Markdown document** at the given output path.

---

### 3. Extending to real audio

- Replace the simple text-based `TranscriptionAgent` stub with:
  - Google Speech-to-Text, Gemini audio models, or Whisper
  - Populate the `ConversationSegment` objects with speaker labels and timestamps
- The rest of the agents will work unchanged, since they operate on text and structured JSON.

---

### 4. Project structure

- `schemas.py` – Shared data models for conversation, requirements, ambiguities, questions.
- `agents.py` – Implementations of the 5 agents using Gemini.
- `main.py` – Orchestrator that wires the agents together.


