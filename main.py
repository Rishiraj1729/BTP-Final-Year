import argparse
from pathlib import Path

from schemas import PipelineState, ProjectMetadata
from agents import (
    TranscriptionAgent,
    RequirementAnalyzerAgent,
    AmbiguityDetectionAgent,
    QuestionGenerationAgent,
    DocumentationAgent,
    MockLLMClient,
    GeminiLLMClient,
    GroqLLMClient,
)


def run_pipeline(transcript_path, audio_path, output_path: Path, provider: str) -> None:
    state = PipelineState(
        metadata=ProjectMetadata(
            project_name="Sample Project",
            client_name="Sample Client",
            domain="General",
        )
    )

    if provider == "mock":
        llm = MockLLMClient()
    elif provider == "gemini":
        llm = GeminiLLMClient()
    elif provider == "groq":
        llm = GroqLLMClient()
    else:
        raise ValueError(f"Unknown provider: {provider}")
    transcription_agent = TranscriptionAgent(llm=llm)

    # 1. Transcription: either from existing text transcript or from audio
    if transcript_path is not None:
        text = transcript_path.read_text(encoding="utf-8")
        state.conversation = transcription_agent.run_from_text(text)
    elif audio_path is not None:
        state.conversation = transcription_agent.run_from_audio(str(audio_path))
    else:
        raise ValueError("Either transcript_path or audio_path must be provided.")

    # 2. Requirement analysis
    req_agent = RequirementAnalyzerAgent(llm=llm)
    req_agent.run(state)

    # 3. Ambiguity detection
    amb_agent = AmbiguityDetectionAgent(llm=llm)
    amb_agent.run(state)

    # 4. Question generation
    q_agent = QuestionGenerationAgent(llm=llm)
    q_agent.run(state)

    # 5. Documentation
    doc_agent = DocumentationAgent(llm=llm)
    markdown = doc_agent.run(state)

    output_path.write_text(markdown, encoding="utf-8")


def main() -> None:
    # Load environment variables from a local .env file (if present).
    # Imported lazily so the code still runs even if python-dotenv isn't installed.
    try:
        from dotenv import load_dotenv  # type: ignore
        from pathlib import Path

        project_root = Path(__file__).resolve().parent
        # Prefer project-root .env, but also support the common mistake of putting it under .venv/.env
        load_dotenv(dotenv_path=project_root / ".env")
        load_dotenv(dotenv_path=project_root / ".venv" / ".env")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="Agentic pipeline: conversation → structured requirements Markdown (Gemini)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--transcript",
        type=str,
        help="Path to a plain-text transcript file.",
    )
    group.add_argument(
        "--audio",
        type=str,
        help="Path to an audio file (e.g., WAV/MP3) to be transcribed with Gemini.",
    )
    parser.add_argument(
        "--provider",
        choices=["mock", "gemini", "groq"],
        default=None,
        help="Which LLM backend to use. If not set, --mock controls mock vs gemini.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run offline without Gemini (no API key required). Produces deterministic demo outputs.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="requirements.md",
        help="Path to output Markdown file.",
    )

    args = parser.parse_args()
    transcript_path = Path(args.transcript) if args.transcript else None
    audio_path = Path(args.audio) if args.audio else None
    output_path = Path(args.output)

    if transcript_path is not None and not transcript_path.is_file():
        raise SystemExit(f"Transcript file not found: {transcript_path}")
    if audio_path is not None and not audio_path.is_file():
        raise SystemExit(f"Audio file not found: {audio_path}")

    # Backward compatible behavior:
    # - If --provider is set, use it.
    # - Else if --mock is set, use mock; otherwise default to gemini.
    provider = args.provider or ("mock" if args.mock else "gemini")
    run_pipeline(transcript_path, audio_path, output_path, provider=provider)
    print(f"Requirement document generated at: {output_path}")


if __name__ == "__main__":
    main()


