"""Agent 2 — Requirement Analyzer: extracts structured requirements from state.raw_input."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from state_schema import AgentState


_MOCK_FR_RULES = [
    ("login|log in|sign in|authentication", "User Authentication",
     "Users can securely log in to access the system.", "High", ["User", "Customer"]),
    ("register|sign up|create account", "User Registration",
     "Users can create an account on the platform.", "High", ["User"]),
    ("admin.*approv|approv.*admin|reject.*admin|admin.*reject|admin.*review",
     "Admin Review Workflow",
     "Admins can review, approve, or reject submissions.", "High", ["Admin"]),
    ("email.*notif|notif.*email|send email", "Email Notifications",
     "The system sends email notifications on status changes.", "Medium", ["User", "Customer"]),
    ("loan.*status|status.*loan", "View Loan Status",
     "Customers can view the current status of their loan.", "High", ["Customer"]),
    ("dashboard", "User Dashboard",
     "Users can access a personalized dashboard after login.", "Medium", ["User"]),
    ("report|analytics", "Reporting & Analytics",
     "Administrators can generate reports and view analytics.", "Medium", ["Admin"]),
    ("search|filter", "Search & Filtering",
     "Users can search and filter records in the system.", "Medium", ["User"]),
    ("upload|attach|document", "Document Upload",
     "Users can upload supporting documents.", "Medium", ["User"]),
    ("payment|pay|billing|invoice", "Payment Processing",
     "The system supports payment or billing workflows.", "High", ["Customer"]),
]

_MOCK_NFR_RULES = [
    ("fast|performance|speed|quick|latency", "Performance",
     "The system must respond within acceptable time bounds (targets to be confirmed).", "High"),
    ("secure|security|encrypt|auth", "Security",
     "The system must implement authentication, authorisation, and secure data handling.", "High"),
    ("mobile|responsive", "Usability / Responsiveness",
     "The UI must be usable on mobile and desktop devices.", "Medium"),
    ("availab|uptime|99", "Availability",
     "The system should target high availability (uptime SLA to be confirmed).", "High"),
    ("scale|scalab|concurrent|load", "Scalability",
     "The system must handle expected peak load (targets to be confirmed).", "High"),
    ("comply|gdpr|hipaa|regulation", "Compliance",
     "The system must comply with applicable regulations.", "High"),
]


class RequirementAnalyzerAgent:
    def __init__(self, llm=None) -> None:
        self._llm = llm

    def run(self, state: AgentState) -> None:
        from agents import _llm_is_mock
        if self._llm is None or _llm_is_mock(self._llm):
            self._run_mock(state)
        else:
            self._run_llm(state)
        # Populate extracted_signals
        state.extracted_signals.features = [fr.get("title", "") for fr in state.functional]
        print(f"[AnalyzerAgent] {len(state.functional)} FR, {len(state.non_functional)} NFR extracted.")

    def _run_llm(self, state: AgentState) -> None:
        system_prompt = """You are a senior business analyst.
Extract structured software requirements from the conversation.

Return ONLY valid JSON:
{
  "functional": [{"id":"FR-01","title":"","description":"","priority":"High|Medium|Low",
                  "actors":[],"preconditions":[],"postconditions":[],
                  "acceptanceCriteria":[],"sourceQuotes":[]}],
  "nonFunctional": [{"id":"NFR-01","title":"","description":"","category":"","priority":"High"}],
  "constraints": [{"id":"CON-01","description":"","type":""}],
  "assumptions": [{"id":"ASM-01","description":""}]
}
Do not invent facts. Mark inferred items under assumptions."""

        try:
            raw = self._llm.generate_text(
                system_prompt=system_prompt,
                user_prompt=f"Conversation:\n\n{state.raw_input}"
            ).strip()
            raw = _strip_fences(raw)
            if not raw:
                raise ValueError("Empty LLM response")
            obj_match = re.search(r'\{.*\}', raw, re.DOTALL)
            data = json.loads(obj_match.group()) if obj_match else json.loads(raw)

            state.functional = data.get("functional", [])
            state.non_functional = data.get("nonFunctional", data.get("non_functional", []))
            state.constraints_list = data.get("constraints", [])
            state.assumptions_list = data.get("assumptions", [])
        except Exception as e:
            print(f"[AnalyzerAgent] LLM parse failed ({e}), falling back to rule-based.")
            self._run_mock(state)

    def _run_mock(self, state: AgentState) -> None:
        text = state.raw_input.lower()
        frs, nfrs, cons, asms = [], [], [], []

        fr_id = nfr_id = con_id = asm_id = 1
        for pattern, title, desc, priority, actors in _MOCK_FR_RULES:
            if re.search(pattern, text):
                frs.append({
                    "id": f"FR-{fr_id:02d}", "title": title,
                    "description": desc, "priority": priority, "actors": actors,
                    "preconditions": [], "postconditions": [],
                    "acceptance_criteria": [
                        "Functionality works as described.",
                        "Validated in UAT.",
                        "Error cases are handled gracefully.",
                    ],
                    "source_quotes": [],
                })
                fr_id += 1

        for pattern, title, desc, priority in _MOCK_NFR_RULES:
            if re.search(pattern, text):
                nfrs.append({
                    "id": f"NFR-{nfr_id:02d}", "title": title,
                    "description": desc, "category": title.split("/")[0].strip(),
                    "priority": priority, "source_quotes": [],
                })
                nfr_id += 1

        if "web" in text:
            cons.append({"id": f"CON-{con_id:02d}",
                         "description": "Delivery includes a web application.", "type": "platform"})
            con_id += 1
        if "mobile" in text:
            asms.append({"id": f"ASM-{asm_id:02d}",
                         "description": "Mobile scope (responsive web vs native) TBD."})
            asm_id += 1
        if not frs:
            frs.append({"id": "FR-01", "title": "Core Feature",
                        "description": "Implement the primary feature described by the client.",
                        "priority": "High", "actors": ["User"],
                        "preconditions": [], "postconditions": [],
                        "acceptance_criteria": ["Feature works as described."],
                        "source_quotes": []})

        state.functional = frs
        state.non_functional = nfrs
        state.constraints_list = cons
        state.assumptions_list = asms


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    return raw.strip()

