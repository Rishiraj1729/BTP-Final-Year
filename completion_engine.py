"""
completion_engine.py
--------------------
Evaluates how complete the extracted requirements are and
returns a CompletionStatus with per-section scores (0.0 – 1.0).

Criteria checked per section:
  Functional       - has items, all have title+description+acceptance_criteria+actors
  Non-Functional   - has items, all have title+description+category
  Constraints      - at least one item present
  Assumptions      - at least one item present
  Actors defined   - at least one unique actor across all FRs
  Acceptance crit  - all FRs have at least one acceptance criterion
"""

from __future__ import annotations

from typing import List, Dict, Any

from state_schema import AgentState, CompletionStatus


def _score_functional(items: List[Dict[str, Any]]) -> float:
    if not items:
        return 0.0
    scores = []
    for fr in items:
        s = 0
        if fr.get("title"): s += 1
        if fr.get("description"): s += 1
        if fr.get("actors"): s += 1
        if fr.get("acceptance_criteria") or fr.get("acceptanceCriteria"): s += 1
        if fr.get("priority"): s += 1
        scores.append(s / 5)
    return round(sum(scores) / len(scores), 2)


def _score_non_functional(items: List[Dict[str, Any]]) -> float:
    if not items:
        return 0.0
    scores = []
    for nfr in items:
        s = 0
        if nfr.get("title"): s += 1
        if nfr.get("description"): s += 1
        if nfr.get("category"): s += 1
        scores.append(s / 3)
    return round(sum(scores) / len(scores), 2)


def _score_section(items: List[Dict[str, Any]], required_fields: List[str]) -> float:
    if not items:
        return 0.0
    scores = []
    for item in items:
        present = sum(1 for f in required_fields if item.get(f))
        scores.append(present / len(required_fields))
    return round(sum(scores) / len(scores), 2)


def evaluate(state: AgentState) -> CompletionStatus:
    """
    Compute a CompletionStatus for the given AgentState.
    Updates state.completion_status in-place and returns it.
    """
    f_score = _score_functional(state.functional)
    nf_score = _score_non_functional(state.non_functional)
    con_score = _score_section(state.constraints_list, ["id", "description"])
    asm_score = _score_section(state.assumptions_list, ["id", "description"])

    # Actors defined check
    all_actors = set()
    for fr in state.functional:
        for a in fr.get("actors", []):
            if a:
                all_actors.add(a.strip().lower())
    actors_defined = len(all_actors) > 0

    # Acceptance criteria check
    ac_present = all(
        bool(fr.get("acceptance_criteria") or fr.get("acceptanceCriteria"))
        for fr in state.functional
    ) if state.functional else False

    # Overall: weighted average
    weights = [
        (f_score, 0.40),
        (nf_score, 0.25),
        (con_score, 0.10),
        (asm_score, 0.10),
        (1.0 if actors_defined else 0.0, 0.10),
        (1.0 if ac_present else 0.0, 0.05),
    ]
    overall = round(sum(score * w for score, w in weights), 2)

    status = CompletionStatus(
        functional=f_score,
        non_functional=nf_score,
        constraints=con_score,
        assumptions=asm_score,
        actors_defined=actors_defined,
        acceptance_criteria_present=ac_present,
        overall_score=overall,
    )
    state.completion_status = status
    return status


def report(status: CompletionStatus) -> str:
    """Return a human-readable completeness report string."""
    lines = [
        "-- Completeness Report ------------------",
        f"  Functional requirements :  {status.functional * 100:.0f}%",
        f"  Non-functional          :  {status.non_functional * 100:.0f}%",
        f"  Constraints             :  {status.constraints * 100:.0f}%",
        f"  Assumptions             :  {status.assumptions * 100:.0f}%",
        f"  Actors defined          :  {'YES' if status.actors_defined else 'NO'}",
        f"  Acceptance criteria     :  {'YES' if status.acceptance_criteria_present else 'NO'}",
        f"  -------------------------------------",
        f"  Overall score           :  {status.overall_score * 100:.0f}%",
        f"  Status                  :  {'[COMPLETE]' if status.is_complete() else '[INCOMPLETE < 70%]'}",
        "-----------------------------------------",
    ]
    return "\n".join(lines)

