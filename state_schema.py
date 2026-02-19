"""
state_schema.py
---------------
Central structured state definition for the Agentic PRD pipeline.

Every agent reads from and writes to this shared state dict.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Literal, Optional


# ---------------------------------------------------------------------------
# Sub-schemas
# ---------------------------------------------------------------------------

@dataclass
class PersonaConfig:
    name: str = "PM"                   # e.g. "CTO", "PM", "Dev", "QA", "Investor"
    tone: str = "professional"         # "technical" | "executive" | "professional"
    focus: List[str] = field(default_factory=list)  # e.g. ["scalability", "cost"]
    output_format: str = "standard"    # "detailed" | "summary" | "standard"


@dataclass
class ExtractedSignals:
    """Raw, categorised signals pulled from the conversation."""
    features: List[str] = field(default_factory=list)
    pain_points: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    actors: List[str] = field(default_factory=list)
    integrations: List[str] = field(default_factory=list)
    tech_preferences: List[str] = field(default_factory=list)


@dataclass
class GapEntry:
    id: str
    category: str          # "missing_detail" | "conflict" | "vague_term" | "implicit_requirement"
    description: str
    severity: str = "medium"   # "low" | "medium" | "high"
    resolved: bool = False
    resolution: str = ""


@dataclass
class CompletionStatus:
    """Completeness score per section (0.0 – 1.0)."""
    functional: float = 0.0
    non_functional: float = 0.0
    constraints: float = 0.0
    assumptions: float = 0.0
    actors_defined: bool = False
    acceptance_criteria_present: bool = False
    overall_score: float = 0.0

    def is_complete(self, threshold: float = 0.7) -> bool:
        return self.overall_score >= threshold


@dataclass
class ArchitectureHint:
    """Derived high-level architecture signals."""
    suggested_layers: List[str] = field(default_factory=list)    # e.g. ["frontend", "API", "DB"]
    suggested_tech: List[str] = field(default_factory=list)      # e.g. ["React", "FastAPI", "PostgreSQL"]
    integration_points: List[str] = field(default_factory=list)  # e.g. ["payment gateway", "SMS API"]
    deployment_notes: List[str] = field(default_factory=list)


@dataclass
class PRDVersion:
    version: int
    timestamp: str
    content_md: str
    state_snapshot: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Master state
# ---------------------------------------------------------------------------

@dataclass
class AgentState:
    """
    Master state object passed through the entire agent pipeline.

    state = {
        "input_mode":            "audio" | "chat",
        "persona":               PersonaConfig,
        "extracted_signals":     ExtractedSignals,
        "gaps":                  [GapEntry, ...],
        "completion_status":     CompletionStatus,
        "derived_architecture":  ArchitectureHint,
        "version":               int
    }
    """

    # Input
    input_mode: Literal["audio", "chat"] = "chat"
    raw_input: str = ""                                    # original transcript / chat text

    # Persona
    persona: PersonaConfig = field(default_factory=PersonaConfig)

    # Extraction
    extracted_signals: ExtractedSignals = field(default_factory=ExtractedSignals)

    # Requirements (structured)
    functional: List[Dict[str, Any]] = field(default_factory=list)
    non_functional: List[Dict[str, Any]] = field(default_factory=list)
    constraints_list: List[Dict[str, Any]] = field(default_factory=list)
    assumptions_list: List[Dict[str, Any]] = field(default_factory=list)

    # Gaps & questions
    gaps: List[GapEntry] = field(default_factory=list)
    follow_up_questions: List[Dict[str, Any]] = field(default_factory=list)

    # Completeness
    completion_status: CompletionStatus = field(default_factory=CompletionStatus)

    # Architecture hints
    derived_architecture: ArchitectureHint = field(default_factory=ArchitectureHint)

    # Versioning
    version: int = 1
    history: List[PRDVersion] = field(default_factory=list)

    # Final output
    prd_markdown: str = ""

    # Metadata
    project_name: str = "Untitled Project"
    client_name: str = ""
    domain: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentState":
        """Reconstruct an AgentState from a plain dict (e.g. loaded from DB)."""
        import copy
        d = copy.deepcopy(data)

        def _build(klass, val):
            if isinstance(val, dict):
                try:
                    import inspect
                    sig = inspect.signature(klass.__init__)
                    valid = {k for k in sig.parameters if k != "self"}
                    return klass(**{k: v for k, v in val.items() if k in valid})
                except Exception:
                    return val
            return val

        state = cls()
        state.input_mode = d.get("input_mode", "chat")
        state.raw_input = d.get("raw_input", "")
        state.persona = _build(PersonaConfig, d.get("persona", {}))
        state.extracted_signals = _build(ExtractedSignals, d.get("extracted_signals", {}))
        state.functional = d.get("functional", [])
        state.non_functional = d.get("non_functional", [])
        state.constraints_list = d.get("constraints_list", [])
        state.assumptions_list = d.get("assumptions_list", [])
        state.gaps = [_build(GapEntry, g) for g in d.get("gaps", [])]
        state.follow_up_questions = d.get("follow_up_questions", [])
        state.completion_status = _build(CompletionStatus, d.get("completion_status", {}))
        state.derived_architecture = _build(ArchitectureHint, d.get("derived_architecture", {}))
        state.version = d.get("version", 1)
        state.history = d.get("history", [])
        state.prd_markdown = d.get("prd_markdown", "")
        state.project_name = d.get("project_name", "Untitled Project")
        state.client_name = d.get("client_name", "")
        state.domain = d.get("domain", "")
        return state

