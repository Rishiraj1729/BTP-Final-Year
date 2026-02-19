"""Agent 3 — Ambiguity Detection: identifies gaps, vague terms, conflicts in requirements."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from state_schema import AgentState, GapEntry


class AmbiguityDetectionAgent:
    def __init__(self, llm=None) -> None:
        self._llm = llm

    def run(self, state: AgentState) -> None:
        from agents import _llm_is_mock
        if self._llm is None or _llm_is_mock(self._llm):
            self._run_mock(state)
        else:
            self._run_llm(state)
        state.extracted_signals.pain_points = [g.description for g in state.gaps if g.severity == "high"]
        print(f"[AmbiguityAgent] {len(state.gaps)} gaps found.")

    def _run_llm(self, state: AgentState) -> None:
        reqs = {
            "functional": state.functional,
            "nonFunctional": state.non_functional,
            "constraints": state.constraints_list,
            "assumptions": state.assumptions_list,
        }
        system_prompt = """You are a requirements quality reviewer.
Identify ambiguities, conflicts, vague terms, and missing details.

Return ONLY valid JSON array:
[{
  "id": "AMB-01",
  "category": "missing_detail|conflict|vague_term|implicit_requirement",
  "description": "",
  "severity": "low|medium|high"
}]"""

        try:
            raw = self._llm.generate_text(
                system_prompt=system_prompt,
                user_prompt=f"Requirements JSON:\n{json.dumps(reqs, indent=2)}"
            ).strip()
            raw = _strip_fences(raw)
            if not raw:
                raise ValueError("Empty LLM response")
            arr_match = re.search(r'\[.*\]', raw, re.DOTALL)
            data = json.loads(arr_match.group()) if arr_match else json.loads(raw)
            if not isinstance(data, list):
                raise ValueError("Expected JSON array")
            state.gaps = [
                GapEntry(
                    id=item.get("id", f"AMB-{i+1:02d}"),
                    category=item.get("category", "missing_detail"),
                    description=item.get("description", ""),
                    severity=item.get("severity", "medium"),
                )
                for i, item in enumerate(data)
            ]
        except Exception as e:
            print(f"[AmbiguityAgent] LLM parse failed ({e}), falling back to rule-based.")
            self._run_mock(state)

    def _run_mock(self, state: AgentState) -> None:
        gaps: List[GapEntry] = []
        idx = 1

        def add(category: str, desc: str, severity: str = "medium") -> None:
            nonlocal idx
            gaps.append(GapEntry(
                id=f"AMB-{idx:02d}", category=category,
                description=desc, severity=severity
            ))
            idx += 1

        text = state.raw_input.lower()

        # Vague performance NFR
        if any("fast" in n.get("description", "").lower() or
               "quickly" in n.get("description", "").lower()
               for n in state.non_functional):
            add("vague_term",
                "Performance requirements lack measurable targets (e.g. p95 response time, "
                "concurrent users, throughput).", "high")

        # Security details missing
        if any("security" in n.get("category", "").lower() for n in state.non_functional):
            add("missing_detail",
                "Security NFR present but specifics missing: auth mechanism (OTP/SSO/OAuth), "
                "RBAC roles, encryption standard, audit logging.", "high")

        # Role permission gaps
        actors = {a for fr in state.functional for a in fr.get("actors", [])}
        if len(actors) > 1:
            add("missing_detail",
                f"Multiple actors detected ({', '.join(sorted(actors))}) but role-based "
                "permissions and access boundaries are not defined.", "high")

        # No acceptance criteria
        missing_ac = [fr["id"] for fr in state.functional
                      if not fr.get("acceptance_criteria") and not fr.get("acceptanceCriteria")]
        if missing_ac:
            add("missing_detail",
                f"Acceptance criteria are missing for: {', '.join(missing_ac)}.", "medium")

        # Email notification details
        if any("email" in fr.get("title", "").lower() for fr in state.functional):
            add("missing_detail",
                "Email notifications requested but trigger events, templates, "
                "and delivery SLA are not specified.", "medium")

        # Mobile ambiguity
        if any("mobile" in a.get("description", "").lower() for a in state.assumptions_list):
            add("implicit_requirement",
                "Mobile support is referenced but platform scope (responsive web, iOS, Android) "
                "is not decided.", "medium")

        # Integration points vague
        integrations = re.findall(r"integrat\w+ with (\w[\w\s]+?)[\.,]", text)
        for integ in integrations:
            add("missing_detail",
                f"Integration with '{integ.strip()}' mentioned but API, auth, and data contract "
                "are unspecified.", "high")

        state.gaps = gaps


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    return raw.strip()

