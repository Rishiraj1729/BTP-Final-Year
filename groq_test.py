import os

from groq import Groq


def main() -> None:
    # Load .env if present (project-root preferred; also support .venv/.env fallback)
    try:
        from dotenv import load_dotenv  # type: ignore
        from pathlib import Path

        project_root = Path(__file__).resolve().parent
        load_dotenv(dotenv_path=project_root / ".env")
        load_dotenv(dotenv_path=project_root / ".venv" / ".env")
    except Exception:
        pass

    # Uses GROQ_API_KEY from env/.env
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Put it in E:\\BTP FINAL\\.env or set it in your PowerShell session.")

    client = Groq(api_key=api_key)

    resp = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "user", "content": "Explain the speed of Groq's LPU Inference Engine in 4 bullet points."}
        ],
        temperature=0.2,
    )

    print(resp.choices[0].message.content)


if __name__ == "__main__":
    main()


