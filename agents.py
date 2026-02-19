import os
import json
import re
from dataclasses import asdict
from typing import List, Optional, Dict, Any, Protocol

from schemas import (
    ConversationSegment,
    PipelineState,
    FunctionalRequirement,
    NonFunctionalRequirement,
    Constraint,
    Assumption,
    Ambiguity,
    FollowUpQuestion,
)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")


class LLMClient(Protocol):
    def generate_text(self, system_prompt: str, user_prompt: str) -> str: ...


class GeminiLLMClient:
    """
    Real Gemini client (lazy imports so the project can run in --mock mode without any key).
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = MODEL_NAME) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY environment variable is not set. "
                "Set it, or run with --mock."
            )
        self.model_name = model_name

        # Lazy import to avoid warnings/requirements when running in mock mode
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=self.api_key)
        self._genai = genai
        self._model = genai.GenerativeModel(self.model_name)

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        resp = self._model.generate_content(
            [
                {"role": "system", "parts": [system_prompt]},
                {"role": "user", "parts": [user_prompt]},
            ]
        )
        return (resp.text or "").strip()


class GroqLLMClient:
    """
    Groq chat-completions client.

    Uses environment variables:
    - GROQ_API_KEY (required)
    - GROQ_MODEL (optional)
    """

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "GROQ_API_KEY environment variable is not set. "
                "Set it, or run with --provider mock."
            )
        # NOTE: Groq model names can be deprecated over time. Users can override via GROQ_MODEL.
        # We keep a modern default plus runtime fallbacks in generate_text().
        self.model_name = model_name or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

        # Lazy import: only required when you actually use Groq provider
        from groq import Groq  # type: ignore

        self._client = Groq(api_key=self.api_key)

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        # Try primary model first, then fall back if Groq decommissions a model.
        candidate_models = [
            self.model_name,
            # Common alternative model names (best-effort fallbacks)
            "llama-3.3-70b-versatile",
            "llama3-70b-8192",
            "llama3-8b-8192",
        ]

        last_err: Optional[Exception] = None
        for model in list(dict.fromkeys(candidate_models)):  # de-dup preserving order
            try:
                resp = self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                )
                return (resp.choices[0].message.content or "").strip()
            except Exception as e:
                last_err = e
                msg = str(e).lower()
                # Common auth failure: make it explicit
                if ("invalid api key" in msg) or ("invalid_api_key" in msg) or ("error code: 401" in msg):
                    raise RuntimeError(
                        "Groq authentication failed (invalid API key). "
                        "Rotate your Groq key and set it as GROQ_API_KEY (prefer E:\\BTP FINAL\\.env), then rerun."
                    ) from e
                # If this is not a model decommission/missing model issue, stop early.
                if ("decommissioned" not in msg) and ("model" not in msg or "not supported" not in msg):
                    break

        if last_err is not None:
            raise last_err
        raise RuntimeError("Groq call failed for an unknown reason.")


class MockLLMClient:
    """
    Offline fallback that produces deterministic, reasonable outputs so you can run end-to-end
    without any API key.
    """

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        # Not used directly; agents below have explicit mock implementations.
        return ""


class TranscriptionAgent:
    """
    Handles conversation transcription.

    - run_from_text: use an existing plain-text transcript.
    - run_from_audio: use Gemini multimodal to transcribe an audio file.
    """

    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        self._llm = llm

    def _segments_from_text(self, transcript_text: str) -> List[ConversationSegment]:
        # Simple single-speaker segmentation for demo purposes
        segments: List[ConversationSegment] = []
        for line in transcript_text.splitlines():
            line = line.strip()
            if not line:
                continue
            segments.append(ConversationSegment(speaker="Client", text=line))
        if not segments and transcript_text.strip():
            # Fallback: treat whole transcript as a single segment
            segments.append(ConversationSegment(speaker="Client", text=transcript_text.strip()))
        return segments

    def run_from_text(self, transcript_text: str) -> List[ConversationSegment]:
        return self._segments_from_text(transcript_text)

    def run_from_audio(self, audio_path: str, mime_type: str = "audio/wav") -> List[ConversationSegment]:
        """
        Transcribe an audio file using Gemini multimodal capabilities.

        Adjust mime_type (e.g., 'audio/mp3') to match your actual file format.
        """
        if not isinstance(self._llm, GeminiLLMClient):
            raise RuntimeError("Audio transcription requires real Gemini mode (no --mock).")

        # We intentionally re-initialize a model that can accept raw bytes parts.
        # The google.generativeai SDK supports passing inline_data parts with mime_type/data.
        genai = self._llm._genai
        model = genai.GenerativeModel(self._llm.model_name)
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        resp = model.generate_content(
            [
                {
                    "mime_type": mime_type,
                    "data": audio_bytes,
                }
            ]
        )
        text = (resp.text or "").strip()
        return self._segments_from_text(text)


class RequirementAnalyzerAgent:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def run(self, state: PipelineState) -> None:
        conversation_text = "\n".join(
            f"{seg.speaker}: {seg.text}" for seg in state.conversation
        )

        system_prompt = """
You are a senior business analyst. Extract structured software requirements from the given client conversation.

Return ONLY valid JSON with this structure:
{
  "functional": [ { ... } ],
  "nonFunctional": [ { ... } ],
  "constraints": [ { ... } ],
  "assumptions": [ { ... } ]
}

Where:
- functional[].id is like "FR-01"
- nonFunctional[].id is like "NFR-01"
- constraints[].id is like "CON-01"
- assumptions[].id is like "ASM-01"
- Each functional requirement includes: id, title, description, priority, actors, preconditions, postconditions, acceptanceCriteria, sourceQuotes
- Each non-functional requirement includes: id, title, description, category, priority, sourceQuotes
- Each constraint includes: id, description, type
- Each assumption includes: id, description

Do not add any extra keys.
If you need to infer something, include it under assumptions.
"""

        # Mock path: lightweight extraction without LLM
        if isinstance(self._llm, MockLLMClient):
            self._run_mock(state, conversation_text)
            return

        raw = self._llm.generate_text(
            system_prompt=system_prompt,
            user_prompt="Client conversation:\n\n" + conversation_text,
        ).strip()
        # Attempt to extract JSON if the model wrapped it in markdown fences
        if raw.startswith("```"):
            raw = raw.strip("`")
            # remove possible language hint
            if raw.startswith("json"):
                raw = raw[len("json") :].lstrip()

        data = json.loads(raw)

        state.requirements.functional = [
            FunctionalRequirement(
                id=item["id"],
                title=item.get("title", ""),
                description=item.get("description", ""),
                priority=item.get("priority", "Medium").capitalize(),
                actors=item.get("actors", []),
                preconditions=item.get("preconditions", []),
                postconditions=item.get("postconditions", []),
                acceptance_criteria=item.get("acceptanceCriteria", []),
                source_quotes=item.get("sourceQuotes", []),
            )
            for item in data.get("functional", [])
        ]

        state.requirements.non_functional = [
            NonFunctionalRequirement(
                id=item["id"],
                title=item.get("title", ""),
                description=item.get("description", ""),
                category=item.get("category", ""),
                priority=item.get("priority", "Medium").capitalize(),
                source_quotes=item.get("sourceQuotes", []),
            )
            for item in data.get("nonFunctional", [])
        ]

        state.requirements.constraints = [
            Constraint(
                id=item["id"],
                description=item.get("description", ""),
                type=item.get("type", ""),
            )
            for item in data.get("constraints", [])
        ]

        state.requirements.assumptions = [
            Assumption(
                id=item["id"],
                description=item.get("description", ""),
            )
            for item in data.get("assumptions", [])
        ]

    def _run_mock(self, state: PipelineState, conversation_text: str) -> None:
        text = conversation_text.lower()

        frs: List[FunctionalRequirement] = []
        nfrs: List[NonFunctionalRequirement] = []
        cons: List[Constraint] = []
        asms: List[Assumption] = []

        fr_id = 1
        nfr_id = 1
        con_id = 1
        asm_id = 1

        def add_fr(title: str, description: str, priority: str = "Medium", actors: Optional[List[str]] = None):
            nonlocal fr_id
            frs.append(
                FunctionalRequirement(
                    id=f"FR-{fr_id:02d}",
                    title=title,
                    description=description,
                    priority=priority,  # type: ignore
                    actors=actors or [],
                    acceptance_criteria=[
                        "Behavior is implemented as described and validated in UAT.",
                        "Errors are handled with user-friendly messages.",
                    ],
                    source_quotes=[{"speaker": "Client", "text": title}],
                )
            )
            fr_id += 1

        if "log in" in text or "login" in text or "sign in" in text:
            add_fr(
                "User authentication",
                "Users can log in to access the system.",
                priority="High",
                actors=["Customer"],
            )

        if "admin" in text and ("approve" in text or "reject" in text or "review" in text):
            add_fr(
                "Admin review workflow",
                "Admins can review, approve, or reject submissions/requests.",
                priority="High",
                actors=["Admin"],
            )

        if "email" in text and ("notify" in text or "notification" in text):
            add_fr(
                "Email notifications",
                "Send email notifications when important status changes occur.",
                priority="Medium",
                actors=["Customer"],
            )

        if "loan" in text and "status" in text:
            add_fr(
                "View loan status",
                "Customers can view the current status of their loan/application.",
                priority="High",
                actors=["Customer"],
            )

        if "secure" in text:
            nfrs.append(
                NonFunctionalRequirement(
                    id=f"NFR-{nfr_id:02d}",
                    title="Security",
                    description="The system must follow security best practices (authentication, authorization, secure storage, secure transport).",
                    category="Security",
                    priority="High",  # type: ignore
                    source_quotes=[{"speaker": "Client", "text": "secure"}],
                )
            )
            nfr_id += 1

        if "fast" in text or "performance" in text:
            nfrs.append(
                NonFunctionalRequirement(
                    id=f"NFR-{nfr_id:02d}",
                    title="Performance",
                    description="The system should respond quickly for common user actions (targets to be confirmed).",
                    category="Performance",
                    priority="High",  # type: ignore
                    source_quotes=[{"speaker": "Client", "text": "fast"}],
                )
            )
            nfr_id += 1

        # Platform hints
        if "web" in text:
            cons.append(Constraint(id=f"CON-{con_id:02d}", description="Initial delivery includes a web application.", type="platform"))
            con_id += 1
        if "mobile" in text:
            asms.append(Assumption(id=f"ASM-{asm_id:02d}", description="Mobile support may be responsive web first; native apps to be confirmed."))
            asm_id += 1

        state.requirements.functional = frs
        state.requirements.non_functional = nfrs
        state.requirements.constraints = cons
        state.requirements.assumptions = asms


class AmbiguityDetectionAgent:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def run(self, state: PipelineState) -> None:

        requirements_summary = {
            "functional": [fr.__dict__ for fr in state.requirements.functional],
            "nonFunctional": [nfr.__dict__ for nfr in state.requirements.non_functional],
            "constraints": [c.__dict__ for c in state.requirements.constraints],
            "assumptions": [a.__dict__ for a in state.requirements.assumptions],
        }

        system_prompt = """
You are a requirements quality reviewer.
Given the structured requirements, find any ambiguity, conflict, or missing critical detail
that would block implementation.

Return ONLY valid JSON:
[
  {
    "id": "AMB-01",
    "type": "missing_detail | conflict | vague_term | implicit_requirement",
    "description": "",
    "severity": "low | medium | high",
    "section": "functional | nonFunctional | constraints | assumptions | other",
    "evidence": [
      { "source": "FR-01", "excerpt": "..." }
    ]
  }
]
"""

        if isinstance(self._llm, MockLLMClient):
            self._run_mock(state)
            return

        raw = self._llm.generate_text(
            system_prompt=system_prompt,
            user_prompt="Structured requirements JSON:\n" + json.dumps(requirements_summary, indent=2),
        ).strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[len("json") :].lstrip()

        data = json.loads(raw)

        state.ambiguities = [
            Ambiguity(
                id=item["id"],
                type=item["type"],
                description=item.get("description", ""),
                severity=item.get("severity", "medium"),
                section=item.get("section", ""),
                evidence=item.get("evidence", []),
            )
            for item in data
        ]

    def _run_mock(self, state: PipelineState) -> None:
        ambiguities: List[Ambiguity] = []
        amb_id = 1

        def add_amb(a_type: str, desc: str, severity: str = "medium", section: str = "other", evidence: Optional[List[Dict[str, Any]]] = None):
            nonlocal amb_id
            ambiguities.append(
                Ambiguity(
                    id=f"AMB-{amb_id:02d}",
                    type=a_type,  # type: ignore
                    description=desc,
                    severity=severity,  # type: ignore
                    section=section,
                    evidence=evidence or [],
                )
            )
            amb_id += 1

        # Vague NFRs
        nfr_texts = " ".join(n.description.lower() + " " + n.title.lower() for n in state.requirements.non_functional)
        if "quickly" in nfr_texts or "fast" in nfr_texts:
            add_amb(
                "vague_term",
                "Performance is mentioned but no measurable targets are specified (e.g., response time, throughput, concurrent users).",
                severity="high",
                section="nonFunctional",
            )
        if "best practices" in nfr_texts or "secure" in nfr_texts:
            add_amb(
                "missing_detail",
                "Security requirements need specifics (auth method, roles/permissions, encryption, compliance, audit logs).",
                severity="high",
                section="nonFunctional",
            )

        # Roles / permissions
        has_admin = any("admin" in (a.lower() if isinstance(a, str) else "") for fr in state.requirements.functional for a in fr.actors)
        has_customer = any("customer" in (a.lower() if isinstance(a, str) else "") for fr in state.requirements.functional for a in fr.actors)
        if has_admin and has_customer:
            add_amb(
                "missing_detail",
                "User roles exist (Admin, Customer) but permission boundaries and role capabilities are not fully defined.",
                severity="high",
                section="functional",
            )

        # Notifications details
        if any("notification" in fr.title.lower() or "email" in fr.title.lower() for fr in state.requirements.functional):
            add_amb(
                "missing_detail",
                "Email notifications are requested but triggers, templates, and deliverability requirements are not specified.",
                severity="medium",
                section="functional",
            )

        # Mobile scope uncertainty
        if any("mobile" in a.description.lower() for a in state.requirements.assumptions):
            add_amb(
                "missing_detail",
                "Mobile support is mentioned, but platform choice (responsive web vs native iOS/Android) and scope are unclear.",
                severity="medium",
                section="constraints",
            )

        state.ambiguities = ambiguities


class QuestionGenerationAgent:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def run(self, state: PipelineState) -> None:

        ambiguities_payload = [a.__dict__ for a in state.ambiguities]

        system_prompt = """
You generate concise, professional clarification questions for a client.
Given a list of ambiguities, propose questions that would resolve them.

Return ONLY valid JSON:
[
  {
    "id": "Q-01",
    "question": "",
    "priority": "low | medium | high",
    "linkedAmbiguities": ["AMB-01"]
  }
]
"""

        if isinstance(self._llm, MockLLMClient):
            self._run_mock(state)
            return

        raw = self._llm.generate_text(
            system_prompt=system_prompt,
            user_prompt="Ambiguities JSON:\n" + json.dumps(ambiguities_payload, indent=2),
        ).strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[len("json") :].lstrip()

        data = json.loads(raw)

        state.follow_up_questions = [
            FollowUpQuestion(
                id=item["id"],
                question=item.get("question", ""),
                priority=item.get("priority", "medium"),
                linked_ambiguities=item.get("linkedAmbiguities", []),
            )
            for item in data
        ]

    def _run_mock(self, state: PipelineState) -> None:
        questions: List[FollowUpQuestion] = []
        q_id = 1

        def add_q(question: str, priority: str, linked: List[str]):
            nonlocal q_id
            questions.append(
                FollowUpQuestion(
                    id=f"Q-{q_id:02d}",
                    question=question,
                    priority=priority,  # type: ignore
                    linked_ambiguities=linked,
                )
            )
            q_id += 1

        for amb in state.ambiguities:
            if "Performance" in amb.description or amb.type == "vague_term":
                add_q(
                    "What are the performance targets (e.g., p95 response time for key screens, expected concurrent users, peak load)?",
                    "high",
                    [amb.id],
                )
            elif "Security" in amb.description or amb.type == "missing_detail":
                add_q(
                    "What authentication method should be used (email/password, OTP, SSO)? What roles exist and what permissions should each role have?",
                    "high",
                    [amb.id],
                )
            elif "email" in amb.description.lower():
                add_q(
                    "Which events should trigger email notifications, and what should each email contain (template/content, subject, links)?",
                    "medium",
                    [amb.id],
                )
            elif "mobile" in amb.description.lower():
                add_q(
                    "Should mobile support be responsive web only, or do you need native iOS/Android apps? What is the MVP scope for mobile?",
                    "medium",
                    [amb.id],
                )
            else:
                add_q("Can you clarify this requirement so it is implementable and testable?", "medium", [amb.id])

        # Deduplicate by question text
        dedup: Dict[str, FollowUpQuestion] = {}
        for q in questions:
            if q.question not in dedup:
                dedup[q.question] = q
            else:
                dedup[q.question].linked_ambiguities = sorted(
                    set(dedup[q.question].linked_ambiguities + q.linked_ambiguities)
                )

        state.follow_up_questions = list(dedup.values())


class DocumentationAgent:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def run(self, state: PipelineState) -> str:

        payload = {
            "metadata": state.metadata.__dict__,
            "requirements": {
                "functional": [fr.__dict__ for fr in state.requirements.functional],
                "nonFunctional": [nfr.__dict__ for nfr in state.requirements.non_functional],
                "constraints": [c.__dict__ for c in state.requirements.constraints],
                "assumptions": [a.__dict__ for a in state.requirements.assumptions],
            },
            "followUpQuestions": [q.__dict__ for q in state.follow_up_questions],
        }

        system_prompt = """
You are a technical writer drafting a Software Requirements Specification (SRS).
Given the structured JSON, write a clear, well-structured Markdown document with sections:

1. Project Overview
2. Scope
3. Functional Requirements
4. Non-Functional Requirements
5. Constraints & Assumptions
6. Open Points & Clarification Questions

Use the IDs provided (e.g., FR-01, NFR-01, CON-01).
Return ONLY the Markdown content (no JSON, no backticks).
"""

        if isinstance(self._llm, MockLLMClient):
            return self._render_markdown(state)

        return self._llm.generate_text(
            system_prompt=system_prompt,
            user_prompt="Structured pipeline state JSON:\n" + json.dumps(payload, indent=2),
        )

    def _render_markdown(self, state: PipelineState) -> str:
        md: List[str] = []
        meta = state.metadata

        md.append("## 1. Project Overview")
        md.append(f"- **Project**: {meta.project_name or 'TBD'}")
        md.append(f"- **Client**: {meta.client_name or 'TBD'}")
        md.append(f"- **Domain**: {meta.domain or 'TBD'}")
        md.append("")

        md.append("## 2. Scope")
        md.append("- **In-scope**: Features explicitly mentioned in the conversation transcript.")
        md.append("- **Out-of-scope**: Anything not stated; to be confirmed during clarification.")
        md.append("")

        md.append("## 3. Functional Requirements")
        if not state.requirements.functional:
            md.append("- No functional requirements extracted.")
        for fr in state.requirements.functional:
            md.append(f"### {fr.id}: {fr.title}")
            md.append(fr.description)
            md.append(f"- **Priority**: {fr.priority}")
            if fr.actors:
                md.append(f"- **Actors**: {', '.join(fr.actors)}")
            if fr.acceptance_criteria:
                md.append("- **Acceptance Criteria**:")
                for ac in fr.acceptance_criteria:
                    md.append(f"  - {ac}")
            md.append("")

        md.append("## 4. Non-Functional Requirements")
        if not state.requirements.non_functional:
            md.append("- No non-functional requirements extracted.")
        for nfr in state.requirements.non_functional:
            md.append(f"### {nfr.id}: {nfr.title}")
            md.append(f"- **Category**: {nfr.category or 'General'}")
            md.append(f"- **Priority**: {nfr.priority}")
            md.append(nfr.description)
            md.append("")

        md.append("## 5. Constraints & Assumptions")
        if state.requirements.constraints:
            md.append("### Constraints")
            for c in state.requirements.constraints:
                md.append(f"- **{c.id}**: {c.description}")
        if state.requirements.assumptions:
            md.append("### Assumptions")
            for a in state.requirements.assumptions:
                md.append(f"- **{a.id}**: {a.description}")
        if not state.requirements.constraints and not state.requirements.assumptions:
            md.append("- None captured.")
        md.append("")

        md.append("## 6. Open Points & Clarification Questions")
        if state.follow_up_questions:
            for q in state.follow_up_questions:
                linked = f" (links: {', '.join(q.linked_ambiguities)})" if q.linked_ambiguities else ""
                md.append(f"- **{q.id} [{q.priority}]**: {q.question}{linked}")
        else:
            md.append("- No open questions.")

        md.append("")
        return "\n".join(md)


