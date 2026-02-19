"""
prd_generator.py
----------------
Persona-aware PRD Markdown generator.

Two modes:
  1. LLM mode  – passes structured state + persona prompt to the LLM
  2. Template mode – deterministic Markdown rendering (no API key needed)

Usage:
    from prd_generator import PRDGenerator
    gen = PRDGenerator(llm=llm_client)        # or llm=None for template mode
    markdown = gen.generate(state, persona)
"""

from __future__ import annotations

import json
from typing import Optional, Protocol

from state_schema import AgentState
from persona_config import PersonaConfig, persona_system_prompt


class LLMClient(Protocol):
    def generate_text(self, system_prompt: str, user_prompt: str) -> str: ...


class PRDGenerator:
    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        self._llm = llm

    def generate(self, state: AgentState, persona: Optional[PersonaConfig] = None) -> str:
        persona = persona or state.persona
        if self._llm is not None:
            return self._llm_generate(state, persona)
        return self._template_generate(state, persona)

    # ------------------------------------------------------------------
    # LLM generation
    # ------------------------------------------------------------------

    def _llm_generate(self, state: AgentState, persona: PersonaConfig) -> str:
        persona_prefix = persona_system_prompt(persona)
        system_prompt = persona_prefix + """
Generate a complete Product Requirements Document (PRD) in Markdown.
Include:
1. Project Overview
2. Goals & Success Metrics
3. Scope (In / Out)
4. Stakeholders & Personas
5. Functional Requirements (with IDs FR-XX, acceptance criteria)
6. Non-Functional Requirements (NFR-XX)
7. Constraints & Assumptions
8. Derived Architecture Hints
9. Open Points & Clarification Questions
10. Version History

Return ONLY valid Markdown. No JSON, no code fences.
"""
        payload = {
            "project": state.project_name,
            "client": state.client_name,
            "domain": state.domain,
            "functional": state.functional,
            "nonFunctional": state.non_functional,
            "constraints": state.constraints_list,
            "assumptions": state.assumptions_list,
            "gaps": [g.__dict__ if hasattr(g, "__dict__") else g for g in state.gaps],
            "followUpQuestions": state.follow_up_questions,
            "derivedArchitecture": state.derived_architecture.__dict__,
            "completionScore": state.completion_status.overall_score,
            "version": state.version,
        }
        return (self._llm.generate_text(  # type: ignore[union-attr]
            system_prompt=system_prompt,
            user_prompt=json.dumps(payload, indent=2),
        ) or "").strip()

    # ------------------------------------------------------------------
    # Template generation (no LLM)
    # ------------------------------------------------------------------

    def _template_generate(self, state: AgentState, persona: PersonaConfig) -> str:
        lines = []
        is_summary = persona.output_format == "summary"

        lines.append(f"# PRD — {state.project_name}")
        lines.append(f"> **Persona**: {persona.name}  |  **Version**: v{state.version}  |  "
                     f"**Completeness**: {state.completion_status.overall_score * 100:.0f}%")
        lines.append("")

        # 1. Overview
        lines.append("## 1. Project Overview")
        lines.append(f"- **Project**: {state.project_name or 'TBD'}")
        lines.append(f"- **Client**: {state.client_name or 'TBD'}")
        lines.append(f"- **Domain**: {state.domain or 'TBD'}")
        lines.append("")

        # 2. Goals
        lines.append("## 2. Goals & Success Metrics")
        lines.append("- Primary goal: deliver the features described in this PRD.")
        lines.append("- Success metric: all acceptance criteria pass UAT.")
        lines.append("")

        # 3. Scope
        lines.append("## 3. Scope")
        lines.append("### In-Scope")
        for fr in state.functional:
            lines.append(f"- {fr.get('title', fr.get('id', 'Unknown'))}")
        lines.append("### Out-of-Scope")
        lines.append("- Any feature not listed above (to be confirmed in follow-up).")
        lines.append("")

        # 4. Stakeholders
        actors = set()
        for fr in state.functional:
            for a in fr.get("actors", []):
                if a:
                    actors.add(a)
        lines.append("## 4. Stakeholders & Personas")
        if actors:
            for a in sorted(actors):
                lines.append(f"- **{a}**")
        else:
            lines.append("- To be defined.")
        lines.append("")

        # 5. Functional Requirements
        lines.append("## 5. Functional Requirements")
        if not state.functional:
            lines.append("- None extracted.")
        for fr in state.functional:
            lines.append(f"### {fr.get('id', 'FR-??')}: {fr.get('title', '')}")
            lines.append(fr.get("description", ""))
            lines.append(f"- **Priority**: {fr.get('priority', 'Medium')}")
            if fr.get("actors"):
                lines.append(f"- **Actors**: {', '.join(fr['actors'])}")
            if fr.get("preconditions"):
                lines.append(f"- **Preconditions**: {', '.join(fr['preconditions'])}")
            if fr.get("postconditions"):
                lines.append(f"- **Postconditions**: {', '.join(fr['postconditions'])}")
            ac = fr.get("acceptance_criteria") or fr.get("acceptanceCriteria", [])
            if ac and not is_summary:
                lines.append("- **Acceptance Criteria**:")
                for a in ac:
                    lines.append(f"  - {a}")
            lines.append("")

        # 6. Non-Functional Requirements
        lines.append("## 6. Non-Functional Requirements")
        if not state.non_functional:
            lines.append("- None extracted.")
        for nfr in state.non_functional:
            lines.append(f"### {nfr.get('id', 'NFR-??')}: {nfr.get('title', '')}")
            lines.append(f"- **Category**: {nfr.get('category', 'General')}")
            lines.append(f"- **Priority**: {nfr.get('priority', 'Medium')}")
            lines.append(nfr.get("description", ""))
            lines.append("")

        # 7. Constraints & Assumptions
        lines.append("## 7. Constraints & Assumptions")
        if state.constraints_list:
            lines.append("### Constraints")
            for c in state.constraints_list:
                lines.append(f"- **{c.get('id', 'CON-??')}**: {c.get('description', '')}")
        if state.assumptions_list:
            lines.append("### Assumptions")
            for a in state.assumptions_list:
                lines.append(f"- **{a.get('id', 'ASM-??')}**: {a.get('description', '')}")
        if not state.constraints_list and not state.assumptions_list:
            lines.append("- None captured.")
        lines.append("")

        # 8. Architecture hints (skip for summary personas)
        if not is_summary:
            arch = state.derived_architecture
            lines.append("## 8. Derived Architecture Hints")
            if arch.suggested_layers:
                lines.append(f"- **Layers**: {', '.join(arch.suggested_layers)}")
            if arch.suggested_tech:
                lines.append(f"- **Suggested Tech**: {', '.join(arch.suggested_tech)}")
            if arch.integration_points:
                lines.append(f"- **Integrations**: {', '.join(arch.integration_points)}")
            if arch.deployment_notes:
                for note in arch.deployment_notes:
                    lines.append(f"- {note}")
            if not any([arch.suggested_layers, arch.suggested_tech,
                        arch.integration_points, arch.deployment_notes]):
                lines.append("- To be defined after further requirement clarification.")
            lines.append("")

        # 9. Open points / clarification questions
        lines.append("## 9. Open Points & Clarification Questions")
        if state.follow_up_questions:
            for q in state.follow_up_questions:
                q_id = q.get("id", "Q-??")
                q_text = q.get("question", "")
                q_pri = q.get("priority", "medium")
                links = q.get("linked_ambiguities") or q.get("linkedAmbiguities", [])
                link_str = f" _(links: {', '.join(links)})_" if links else ""
                lines.append(f"- **{q_id} [{q_pri}]**: {q_text}{link_str}")
        else:
            lines.append("- No open questions.")
        lines.append("")

        # 10. Gaps summary
        if state.gaps:
            lines.append("## 10. Identified Gaps")
            for g in state.gaps:
                gd = g if isinstance(g, dict) else g.__dict__
                resolved = "[Resolved]" if gd.get("resolved") else "[Open]"
                lines.append(
                    f"- **{gd.get('id', '?')}** [{gd.get('severity', 'medium').upper()}] "
                    f"({resolved}): {gd.get('description', '')}"
                )
            lines.append("")

        # 11. Version history
        lines.append("## 11. Version History")
        if state.history:
            for h in state.history:
                hd = h if isinstance(h, dict) else h.__dict__
                lines.append(f"- **v{hd.get('version', '?')}** — {hd.get('timestamp', 'unknown')}")
        else:
            lines.append(f"- **v{state.version}** — Initial version")
        lines.append("")

        return "\n".join(lines)

