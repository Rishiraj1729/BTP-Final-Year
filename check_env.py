import os


def _present(name: str) -> str:
    val = os.getenv(name)
    if not val:
        return "MISSING"
    return f"SET (length={len(val)})"


def main() -> None:
    # Load .env if available (project-root preferred; also support .venv/.env fallback)
    try:
        from dotenv import load_dotenv  # type: ignore
        from pathlib import Path

        project_root = Path(__file__).resolve().parent
        load_dotenv(dotenv_path=project_root / ".env")
        load_dotenv(dotenv_path=project_root / ".venv" / ".env")
    except Exception:
        pass

    # We do NOT print actual values (secrets). Only presence/length.
    print("Environment check (secrets are NOT printed):")
    print(f"- GROQ_API_KEY: {_present('GROQ_API_KEY')}")
    print(f"- GROQ_MODEL: {os.getenv('GROQ_MODEL') or 'DEFAULT/EMPTY'}")
    print(f"- GEMINI_API_KEY: {_present('GEMINI_API_KEY')}")
    print(f"- GEMINI_MODEL: {os.getenv('GEMINI_MODEL') or 'DEFAULT/EMPTY'}")


if __name__ == "__main__":
    main()


