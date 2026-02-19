"""
app.py
------
Main entry point for the Agentic PRD pipeline.

Pipeline:
  1. TranscriptionAgent      — loads text / transcribes audio
  2. RequirementAnalyzerAgent — extracts FR, NFR, constraints, assumptions
  3. AmbiguityDetectionAgent  — finds gaps in the requirements
  4. QuestionGenerationAgent  — produces follow-up questions
  5. DocumentationAgent       — derives architecture hints
  6. CompletionEngine         — scores completeness
  7. RAGEngine                — builds retrieval index
  8. PRDGenerator             — generates persona-aware Markdown PRD
  9. StateManager + Database  — saves versioned state

Usage:
  python app.py --transcript sample_conversation.txt
  python app.py --transcript sample_conversation.txt --provider groq --persona CTO
  python app.py --transcript sample_conversation.txt --provider mock --persona Investor
  python app.py --audio meeting.wav --provider gemini --persona Dev
  python app.py --list-versions
  python app.py --load-version 2
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _load_env() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
        root = Path(__file__).resolve().parent
        load_dotenv(dotenv_path=root / ".env")
        load_dotenv(dotenv_path=root / ".venv" / ".env")
    except Exception:
        pass


def _build_llm(provider: str):
    if provider == "mock":
        class MockLLMClient:
            """Offline mock — produces empty strings; agents detect it and use rule-based logic."""
            _is_mock = True
            def generate_text(self, system_prompt: str, user_prompt: str) -> str:
                return ""
        return MockLLMClient()

    elif provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            sys.exit(
                "[Error] GROQ_API_KEY not set. Add it to E:\\BTP FINAL\\.env or set $env:GROQ_API_KEY."
            )
        from groq import Groq  # type: ignore

        class _GroqClient:
            def __init__(self):
                self._client = Groq(api_key=api_key)
                self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
                self._fallbacks = ["llama-3.3-70b-versatile", "llama3-70b-8192", "llama3-8b-8192"]

            def generate_text(self, system_prompt: str, user_prompt: str) -> str:
                candidates = list(dict.fromkeys([self.model] + self._fallbacks))
                last_err = None
                for model in candidates:
                    try:
                        resp = self._client.chat.completions.create(
                            model=model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            temperature=0.2,
                        )
                        return (resp.choices[0].message.content or "").strip()
                    except Exception as e:
                        last_err = e
                        msg = str(e).lower()
                        if "invalid api key" in msg or "401" in msg:
                            sys.exit(
                                "[Error] Invalid Groq API key. Rotate it at https://console.groq.com/keys "
                                "and update E:\\BTP FINAL\\.env"
                            )
                        if "decommissioned" not in msg:
                            break
                raise last_err or RuntimeError("Groq call failed.")

        return _GroqClient()

    elif provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            sys.exit("[Error] GEMINI_API_KEY not set.")
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-pro"))

        class _GeminiClient:
            def generate_text(self, system_prompt: str, user_prompt: str) -> str:
                resp = model.generate_content(
                    [{"role": "system", "parts": [system_prompt]},
                     {"role": "user", "parts": [user_prompt]}]
                )
                return (resp.text or "").strip()

        return _GeminiClient()

    else:
        sys.exit(f"[Error] Unknown provider: {provider}")


def run_pipeline(
    raw_text: str | None,
    audio_path: str | None,
    provider: str,
    persona_name: str,
    output_path: Path,
    project_name: str,
    client_name: str,
    domain: str,
) -> None:
    from state_schema import AgentState
    from agents import (
        TranscriptionAgent, RequirementAnalyzerAgent,
        AmbiguityDetectionAgent, QuestionGenerationAgent, DocumentationAgent,
    )
    from persona_config import get_persona
    from completion_engine import evaluate, report
    from rag_engine import build_from_state
    from prd_generator import PRDGenerator
    from state_manager import save_version
    from database import PRDDatabase

    # ── Init state ──────────────────────────────────────────────────────
    state = AgentState(
        project_name=project_name,
        client_name=client_name,
        domain=domain,
    )
    persona = get_persona(persona_name)
    state.persona = persona

    # ── Build LLM client ────────────────────────────────────────────────
    llm = _build_llm(provider)

    # ── Agent 1: Transcription ───────────────────────────────────────────
    ta = TranscriptionAgent()
    if raw_text is not None:
        ta.run_from_text(state, raw_text)
    else:
        ta.run_from_audio(state, audio_path, llm=llm)  # type: ignore

    # ── Agent 2: Requirement Analysis ────────────────────────────────────
    RequirementAnalyzerAgent(llm=llm).run(state)

    # ── Agent 3: Ambiguity Detection ─────────────────────────────────────
    AmbiguityDetectionAgent(llm=llm).run(state)

    # ── Agent 4: Question Generation ─────────────────────────────────────
    QuestionGenerationAgent(llm=llm).run(state)

    # ── Agent 5: Architecture Derivation ─────────────────────────────────
    DocumentationAgent(llm=llm).run(state)

    # ── Completion Engine ────────────────────────────────────────────────
    status = evaluate(state)
    print(report(status))

    # ── RAG Engine ───────────────────────────────────────────────────────
    rag = build_from_state(state)
    top_context = rag.query("authentication security login", top_k=2)
    if top_context:
        print(f"[RAG] Top context hit: \"{top_context[0][1][:80]}...\"")

    # ── PRD Generation ────────────────────────────────────────────────────
    gen = PRDGenerator(llm=None if provider == "mock" else llm)
    state.prd_markdown = gen.generate(state, persona)

    # ── Save state ────────────────────────────────────────────────────────
    save_version(state)
    db = PRDDatabase()
    db.save(state)
    db.close()

    # ── Write output ──────────────────────────────────────────────────────
    output_path.write_text(state.prd_markdown, encoding="utf-8")
    print(f"\n[DONE] PRD generated -> {output_path}  (v{state.version}, persona: {persona.name})")


def main() -> None:
    _load_env()

    parser = argparse.ArgumentParser(
        description="Agentic PRD pipeline — converts conversations into structured requirement docs."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--transcript", type=str, help="Path to plain-text transcript.")
    group.add_argument("--audio", type=str, help="Path to audio file (WAV/MP3).")

    parser.add_argument("--provider", choices=["mock", "groq", "gemini"],
                        default="mock", help="LLM provider (default: mock).")
    parser.add_argument("--persona", type=str, default="PM",
                        help="Output persona: PM, CTO, Dev, QA, Investor, Client.")
    parser.add_argument("--output", type=str, default="prd_output.md",
                        help="Output Markdown file path.")
    parser.add_argument("--project", type=str, default="Sample Project", help="Project name.")
    parser.add_argument("--client", type=str, default="", help="Client name.")
    parser.add_argument("--domain", type=str, default="General", help="Domain/industry.")
    parser.add_argument("--list-versions", action="store_true",
                        help="List all saved PRD versions and exit.")
    parser.add_argument("--load-version", type=int, default=None,
                        help="Load and print a saved PRD version.")

    args = parser.parse_args()

    # ── Utility sub-commands ─────────────────────────────────────────────
    if args.list_versions:
        from database import PRDDatabase
        db = PRDDatabase()
        rows = db.list_all()
        db.close()
        if not rows:
            print("No saved versions found.")
        else:
            print(f"{'Version':>8}  {'Project':<25}  {'Timestamp'}")
            print("-" * 60)
            for r in rows:
                print(f"v{r['version']:>7}  {r['project']:<25}  {r['timestamp']}")
        return

    if args.load_version is not None:
        from database import PRDDatabase
        db = PRDDatabase()
        state = db.load(args.load_version)
        db.close()
        print(state.prd_markdown)
        return

    # ── Normal pipeline run ──────────────────────────────────────────────
    if args.transcript is None and args.audio is None:
        parser.error("One of --transcript or --audio is required.")

    raw_text: str | None = None
    audio_path: str | None = None

    if args.transcript:
        p = Path(args.transcript)
        if not p.is_file():
            sys.exit(f"[Error] Transcript file not found: {p}")
        raw_text = p.read_text(encoding="utf-8")
    else:
        audio_path = args.audio

    run_pipeline(
        raw_text=raw_text,
        audio_path=audio_path,
        provider=args.provider,
        persona_name=args.persona,
        output_path=Path(args.output),
        project_name=args.project,
        client_name=args.client,
        domain=args.domain,
    )


if __name__ == "__main__":
    main()

