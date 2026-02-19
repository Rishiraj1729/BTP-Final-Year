"""Agent 1 — Transcription: converts raw text/audio into structured conversation segments."""
from __future__ import annotations
from typing import Optional
from state_schema import AgentState


class TranscriptionAgent:
    """
    Populates state.raw_input and state.extracted_signals.actors
    from the raw transcript text (or audio via Gemini).
    """

    def run_from_text(self, state: AgentState, text: str) -> None:
        state.raw_input = text.strip()
        state.input_mode = "chat"
        self._extract_actors(state)
        print(f"[TranscriptionAgent] Loaded {len(state.raw_input.splitlines())} lines.")

    def run_from_audio(self, state: AgentState, audio_path: str,
                       llm=None, mime_type: str = "audio/wav") -> None:
        """Transcribe audio using Gemini multimodal and populate state."""
        if llm is None:
            raise RuntimeError("Audio transcription requires a GeminiLLMClient instance.")
        # Only GeminiLLMClient supports audio; duck-type check
        if not hasattr(llm, "_genai"):
            raise RuntimeError("Audio transcription is only supported with GeminiLLMClient.")
        genai = llm._genai
        model = genai.GenerativeModel(llm.model_name)
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        resp = model.generate_content([{"mime_type": mime_type, "data": audio_bytes}])
        state.raw_input = (resp.text or "").strip()
        state.input_mode = "audio"
        self._extract_actors(state)
        print(f"[TranscriptionAgent] Transcribed audio → {len(state.raw_input)} chars.")

    @staticmethod
    def _extract_actors(state: AgentState) -> None:
        text = state.raw_input.lower()
        actors = []
        for keyword, actor in [
            ("admin", "Admin"), ("customer", "Customer"), ("user", "User"),
            ("manager", "Manager"), ("client", "Client"), ("developer", "Developer"),
        ]:
            if keyword in text and actor not in actors:
                actors.append(actor)
        state.extracted_signals.actors = actors

