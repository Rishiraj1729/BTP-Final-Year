"""
persona_config.py
-----------------
Predefined personas that control PRD tone, focus, and output format.

Usage:
    from persona_config import get_persona, PERSONAS
    persona = get_persona("CTO")
"""

from __future__ import annotations

from typing import Dict, List
from state_schema import PersonaConfig

# ---------------------------------------------------------------------------
# Built-in personas
# ---------------------------------------------------------------------------

PERSONAS: Dict[str, PersonaConfig] = {
    "PM": PersonaConfig(
        name="PM",
        tone="professional",
        focus=["user stories", "acceptance criteria", "delivery timeline", "stakeholder alignment"],
        output_format="standard",
    ),
    "CTO": PersonaConfig(
        name="CTO",
        tone="technical",
        focus=["scalability", "system architecture", "tech stack", "security", "performance", "integrations"],
        output_format="detailed",
    ),
    "Dev": PersonaConfig(
        name="Dev",
        tone="technical",
        focus=["implementation details", "APIs", "data models", "edge cases", "acceptance criteria"],
        output_format="detailed",
    ),
    "QA": PersonaConfig(
        name="QA",
        tone="professional",
        focus=["acceptance criteria", "test cases", "edge cases", "negative flows", "regression risk"],
        output_format="detailed",
    ),
    "Investor": PersonaConfig(
        name="Investor",
        tone="executive",
        focus=["business value", "market opportunity", "ROI", "risk", "milestones", "scope"],
        output_format="summary",
    ),
    "Client": PersonaConfig(
        name="Client",
        tone="professional",
        focus=["features", "user experience", "deliverables", "timeline", "cost"],
        output_format="summary",
    ),
}


def get_persona(name: str) -> PersonaConfig:
    """
    Return the PersonaConfig for the given name.
    Falls back to the PM persona if name is not recognised.
    """
    name_clean = name.strip()
    # Try exact match first (handles ALL-CAPS like CTO, QA)
    # then title-case match (handles 'investor' → 'Investor')
    key = name_clean if name_clean in PERSONAS else name_clean.title()
    if key not in PERSONAS:
        print(f"[PersonaConfig] Unknown persona '{name}', defaulting to PM.")
        return PERSONAS["PM"]
    return PERSONAS[key]


def persona_system_prompt(persona: PersonaConfig) -> str:
    """
    Build the LLM system prompt prefix that enforces the persona's
    tone, focus areas, and output format.
    """
    focus_str = ", ".join(persona.focus) if persona.focus else "general software requirements"
    format_hint = {
        "summary":  "Keep the document concise with executive-level summaries. Avoid deep technical detail.",
        "detailed": "Be thorough and precise. Include technical specifics, edge cases, and implementation notes.",
        "standard": "Balance clarity with completeness. Use structured sections with IDs.",
    }.get(persona.output_format, "")

    return (
        f"You are writing a Product Requirements Document (PRD) for a {persona.name}.\n"
        f"Tone: {persona.tone}.\n"
        f"Prioritise these areas: {focus_str}.\n"
        f"{format_hint}\n"
    )


def list_personas() -> List[str]:
    return list(PERSONAS.keys())

