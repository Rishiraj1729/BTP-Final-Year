"""agents package — all five pipeline agents."""
from .transcription import TranscriptionAgent
from .analyzer import RequirementAnalyzerAgent
from .ambiguity import AmbiguityDetectionAgent
from .questions import QuestionGenerationAgent
from .documentation import DocumentationAgent


def _llm_is_mock(llm) -> bool:
    """Return True when the LLM client is the offline mock (no API calls)."""
    if llm is None:
        return True
    if getattr(llm, "_is_mock", False):
        return True
    return type(llm).__name__ == "MockLLMClient"


__all__ = [
    "TranscriptionAgent",
    "RequirementAnalyzerAgent",
    "AmbiguityDetectionAgent",
    "QuestionGenerationAgent",
    "DocumentationAgent",
    "_llm_is_mock",
]

