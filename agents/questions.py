"""Agent 4 — Question Generation: produces follow-up questions from gaps."""
from __future__ import annotations

import json
import re
from typing import Dict, List

from state_schema import AgentState, GapEntry


_GAP_QUESTION_MAP = {
    "vague_term": [
        ("performance", "high",
         "What are the performance targets? (e.g. p95 response time, max concurrent users, throughput)"),
        ("security", "high",
         "What authentication method is required (OTP, OAuth, SSO)? "
         "What encryption standards apply?"),
    ],
    "missing_detail": [
        ("permission|role|access", "high",
         "Can you define each user role and their exact permissions within the system?"),
        ("email|notification", "medium",
         "Which events trigger email notifications? "
         "What should the email content/template include?"),
        ("mobile|platform", "medium",
         "Should mobile support be responsive web or native iOS/Android? What is the MVP scope?"),
        ("integration|api", "high",
         "Can you provide the API documentation and authentication method for the integration?"),
        ("acceptance|criteria|ac", "medium",
         "Can you define the acceptance criteria for this requirement so it is testable in UAT?"),
    ],
    "conflict": [
        ("", "high",
         "There appears to be a conflict in the requirements. "
         "Can you clarify the intended behaviour?"),
    ],
    "implicit_requirement": [
        ("", "medium",
         "This requirement was inferred from context. "
         "Can you confirm it is in scope and provide details?"),
    ],
}


class QuestionGenerationAgent:
    def __init__(self, llm=None) -> None:
        self._llm = llm

    def run(self, state: AgentState) -> None:
        from agents import _llm_is_mock
        if self._llm is None or _llm_is_mock(self._llm):
            self._run_mock(state)
        else:
            self._run_llm(state)
        print(f"[QuestionAgent] {len(state.follow_up_questions)} follow-up questions generated.")

    def _run_llm(self, state: AgentState) -> None:
        gaps_payload = [g.__dict__ for g in state.gaps]
        system_prompt = """You generate concise, professional clarification questions for a client.

Return ONLY valid JSON:
[{
  "id": "Q-01",
  "question": "",
  "priority": "low|medium|high",
  "linked_ambiguities": ["AMB-01"]
}]"""
        try:
            raw = self._llm.generate_text(
                system_prompt=system_prompt,
                user_prompt=f"Gaps:\n{json.dumps(gaps_payload, indent=2)}"
            ).strip()
            raw = _strip_fences(raw)
            if not raw:
                raise ValueError("Empty LLM response")
            arr_match = re.search(r'\[.*\]', raw, re.DOTALL)
            data = json.loads(arr_match.group()) if arr_match else json.loads(raw)
            if not isinstance(data, list):
                raise ValueError("Expected JSON array")
            state.follow_up_questions = data
        except Exception as e:
            print(f"[QuestionAgent] LLM parse failed ({e}), falling back to rule-based.")
            self._run_mock(state)

    def _run_mock(self, state: AgentState) -> None:
        questions: List[Dict] = []
        seen: Dict[str, List[str]] = {}  # question_text → linked gap ids

        for gap in state.gaps:
            question = _match_question(gap)
            if question:
                q_text, priority = question
                if q_text in seen:
                    seen[q_text].append(gap.id)
                else:
                    seen[q_text] = [gap.id]
                    questions.append({
                        "id": f"Q-{len(questions)+1:02d}",
                        "question": q_text,
                        "priority": priority,
                        "linked_ambiguities": [gap.id],
                    })

        # Update linked_ambiguities for merged questions
        for q in questions:
            q["linked_ambiguities"] = seen[q["question"]]

        state.follow_up_questions = questions


def _match_question(gap: GapEntry):
    """Return (question_text, priority) or None."""
    rules = _GAP_QUESTION_MAP.get(gap.category, [])
    desc = gap.description.lower()
    for pattern, priority, question in rules:
        if not pattern or re.search(pattern, desc):
            return question, priority
    # fallback
    return f"Can you clarify the following: {gap.description[:120]}?", gap.severity


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    return raw.strip()

