"""
gap_engine.py
-------------
Iterative Gap Detection Engine.

After each conversation turn, scans the accumulated state to find
what ESSENTIAL information is still missing, assigns priority,
and generates targeted follow-up questions.

The loop continues until ALL critical gates are satisfied.

Gap scoring:
  critical   - blocks PRD generation (score weight 1.0)
  important  - degrades PRD quality (score weight 0.5)
  nice_to_have - optional enrichment (score weight 0.1)

Completion is defined as:
  - All critical gaps resolved
  - Completion score >= threshold (default 0.75)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REF_PATH = Path(__file__).resolve().parent / "master_reference.json"


def _ref() -> Dict[str, Any]:
    with open(_REF_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class Gap:
    id: str
    gate: str
    priority: str            # "critical" | "important" | "nice_to_have"
    question: str
    why_matters: str = ""
    resolved: bool = False
    resolution_hint: str = "" # partial answer detected

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GapReport:
    total_gaps: int = 0
    critical_open: int = 0
    important_open: int = 0
    nice_to_have_open: int = 0
    completion_score: float = 0.0
    is_complete: bool = False
    open_gaps: List[Gap] = field(default_factory=list)
    resolved_gaps: List[str] = field(default_factory=list)   # gate names
    next_question: Optional[str] = None
    next_gate: Optional[str] = None
    prd_type_detected: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


# ── Detectors ─────────────────────────────────────────────────────────────────

def _detect_prd_type(text: str) -> str:
    """Match free text against PRD type keywords."""
    ref = _ref()
    text_lower = text.lower()
    scores: Dict[str, int] = {}
    for key, meta in ref["prd_types"].items():
        kws = meta.get("keywords", [])
        score = sum(1 for kw in kws if kw in text_lower)
        if score:
            scores[key] = score
    return max(scores, key=scores.get) if scores else "saas_web"


def _has_users_defined(text: str) -> bool:
    actors = ["user", "admin", "customer", "manager", "patient", "buyer", "seller",
              "operator", "agent", "client", "employee", "developer", "tenant", "vendor"]
    return any(a in text.lower() for a in actors)


def _has_scale_number(text: str) -> bool:
    return bool(re.search(r"\d[\d,]*\s*(?:k|m|users|concurrent|simultaneous|people|customers)", text.lower()))


def _has_perf_number(text: str) -> bool:
    return bool(re.search(r"\d+\s*(?:ms|milliseconds|seconds?)\b|\d+\s*(?:req|rps|tps)", text.lower()))


def _has_auth_method(text: str) -> bool:
    tokens = ["jwt", "oauth", "saml", "sso", "mfa", "otp", "2fa", "basic auth", "api key", "session"]
    return any(t in text.lower() for t in tokens)


def _has_compliance(text: str) -> bool:
    tokens = ["gdpr", "pci", "hipaa", "sox", "iso 27001", "nist", "fedramp", "ccpa", "hitech"]
    return any(t in text.lower() for t in tokens)


def _has_sla(text: str) -> bool:
    return bool(re.search(r"99\.?\d*\s*%|uptime|sla|rto|rpo", text.lower()))


def _has_date(text: str) -> bool:
    return bool(re.search(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b|\d{4}|\bq[1-4]\b|month|quarter|deadline|launch", text.lower()))


def _has_features_count(frlist: List[Any], text: str = "") -> bool:
    """Resolve if ≥2 features mentioned — checks extracted list OR raw text."""
    if len(frlist) >= 2:
        return True
    # Detect feature-like nouns in conversation text even before full extraction
    feature_tokens = [
        r"\b(login|sign[\s-]?up|register|auth(?:entication)?|dashboard|profile|search|filter|"
        r"upload|download|payment|checkout|notif(?:ication)?s?|message|chat|report|"
        r"analytics|admin|onboard|game|play|match|score|leaderboard|level|map|"
        r"inventory|order|booking|schedule|appointment|review|rating|feed|post|"
        r"comment|share|follow|like|transaction|wallet|subscription|settings|"
        r"user management|role|permission|export|import|api|integration|webhook)\b"
    ]
    import re as _re
    matches: set = set()
    for p in feature_tokens:
        matches.update(_re.findall(p, text.lower()))
    return len(matches) >= 2


def _has_acceptance_criteria(frlist: List[Any]) -> bool:
    return any(bool(fr.get("acceptance_criteria") or fr.get("acceptanceCriteria")) for fr in frlist)


def _has_integrations(text: str) -> bool:
    tokens = ["payment", "stripe", "paypal", "email", "sms", "twilio", "maps", "google",
              "aws", "slack", "webhook", "api", "erp", "crm", "salesforce", "sendgrid"]
    return any(t in text.lower() for t in tokens)


def _has_data_entity(text: str) -> bool:
    entities = ["user record", "order", "transaction", "profile", "document", "ticket",
                "product", "account", "invoice", "patient record", "sensor data", "message"]
    return any(e in text.lower() for e in entities)


# ── Main gap analysis ─────────────────────────────────────────────────────────

def analyze_gaps(
    raw_text: str,
    functional: List[Dict],
    non_functional: List[Dict],
    conversation_history: List[Dict] = None,
    completion_threshold: float = 0.80,
) -> GapReport:
    """
    Analyse the current state of a session and return what's still missing.

    :param raw_text:  Full accumulated conversation text
    :param functional:  Extracted functional requirements
    :param non_functional:  Extracted non-functional requirements
    :param conversation_history:  [{role, text}] messages
    :param completion_threshold:  Score 0-1 needed for 'complete'
    :return:  GapReport with open gaps and next question to ask
    """
    ref = _ref()
    full_text = raw_text + " " + " ".join(
        m.get("text", "") for m in (conversation_history or [])
    )
    full_lower = full_text.lower()

    prd_type = _detect_prd_type(full_text)
    checklist = ref["gap_checklist"]

    # ── Evaluate each critical gate ───────────────────────────────────────────
    gate_evaluators = {
        "problem":      lambda: bool(re.search(r"solv|help|enable|allow|built for|designed to|problem|build|create|develop|want", full_lower)),
        "users":        lambda: _has_users_defined(full_text),
        "features":     lambda: _has_features_count(functional, full_text),
        "scale":        lambda: _has_scale_number(full_text),
        "auth":         lambda: _has_auth_method(full_text),
        "data":         lambda: _has_data_entity(full_text),
        "security":     lambda: _has_auth_method(full_text) and (bool(re.search(r"encrypt|aes|tls|ssl", full_lower)) or _has_compliance(full_text)),
        "performance":  lambda: _has_perf_number(full_text),
        "availability": lambda: _has_sla(full_text),
        "timeline":     lambda: _has_date(full_text),
    }

    important_evaluators = {
        "integrations":   lambda: _has_integrations(full_text),
        "roles":          lambda: len(set(re.findall(r"\b(admin|user|manager|operator|agent|buyer|seller|tenant)\b", full_lower))) >= 2,
        "acceptance":     lambda: _has_acceptance_criteria(functional),
        "data_retention": lambda: bool(re.search(r"retain|retention|keep data|delete|year|month", full_lower)),
        "error_handling": lambda: bool(re.search(r"fail|error|fallback|retry|recover|timeout|offline", full_lower)),
        "notifications":  lambda: bool(re.search(r"notif|email|sms|push|alert|remind", full_lower)),
        "scope_boundary": lambda: bool(re.search(r"out of scope|not include|phase 2|future|later|won't|wont", full_lower)),
        "reporting":      lambda: bool(re.search(r"report|analytics|dashboard|chart|export|metrics", full_lower)),
    }

    # ── Score and collect open gaps ───────────────────────────────────────────
    open_gaps: List[Gap] = []
    resolved_gates: List[str] = []

    total_weight = 0.0
    resolved_weight = 0.0

    for item in checklist["critical"]:
        gate = item["gate"]
        weight = 1.0
        total_weight += weight
        evaluator = gate_evaluators.get(gate)
        resolved = evaluator() if evaluator else False
        if resolved:
            resolved_weight += weight
            resolved_gates.append(gate)
        else:
            open_gaps.append(Gap(
                id=item["id"], gate=gate, priority="critical",
                question=item["question"],
                why_matters=f"Critical gate — blocks PRD generation if missing.",
            ))

    for item in checklist["important"]:
        gate = item["gate"]
        weight = 0.5
        total_weight += weight
        evaluator = important_evaluators.get(gate)
        resolved = evaluator() if evaluator else False
        if resolved:
            resolved_weight += weight
            resolved_gates.append(gate)
        else:
            open_gaps.append(Gap(
                id=item["id"], gate=gate, priority="important",
                question=item["question"],
                why_matters="Impacts PRD quality and architecture decisions.",
            ))

    for item in checklist["nice_to_have"]:
        gate = item["gate"]
        weight = 0.1
        total_weight += weight
        # These are opt-in — only flag if the domain warrants it
        if prd_type in ("mobile", "iot") or "offline" in gate:
            # Only ask offline if it's relevant
            pass
        resolved_weight += weight * 0.5   # assume partially answered
        resolved_gates.append(gate)

    # Completion score
    score = round(resolved_weight / total_weight, 2) if total_weight else 0.0
    critical_open = sum(1 for g in open_gaps if g.priority == "critical")
    important_open = sum(1 for g in open_gaps if g.priority == "important")
    is_complete = critical_open == 0 and score >= completion_threshold

    # ── De-duplicate: skip gates already asked in recent AI turns ─────────────
    # Look at the last 10 AI messages to see which gate questions were already asked
    ai_turns = [
        m.get("text", "").lower()
        for m in (conversation_history or [])
        if m.get("role") == "ai"
    ][-10:]
    recently_asked_gates: set = set()
    for gap in open_gaps:
        q_lower = gap.question.lower()
        # If key words from the question appear in any recent AI message, it was already asked
        # Use the first 6 words of the question as a fingerprint
        fingerprint_words = [w for w in q_lower.split()[:8] if len(w) > 3]
        for ai_msg in ai_turns:
            matched = sum(1 for w in fingerprint_words if w in ai_msg)
            if matched >= 3:  # ≥3 content words match → already asked
                recently_asked_gates.add(gap.gate)
                break

    # Pick the highest-priority gap NOT recently asked
    next_gap: Optional[Gap] = None
    for gap in open_gaps:
        if gap.gate not in recently_asked_gates:
            next_gap = gap
            break
    # If ALL open gaps were recently asked, rotate to the first one (unavoidable)
    if next_gap is None and open_gaps:
        next_gap = open_gaps[0]

    return GapReport(
        total_gaps=len(open_gaps),
        critical_open=critical_open,
        important_open=important_open,
        nice_to_have_open=len([g for g in open_gaps if g.priority == "nice_to_have"]),
        completion_score=score,
        is_complete=is_complete,
        open_gaps=open_gaps,
        resolved_gaps=resolved_gates,
        next_question=next_gap.question if next_gap else None,
        next_gate=next_gap.gate if next_gap else None,
        prd_type_detected=prd_type,
    )


def get_type_specific_gates(prd_type: str) -> List[str]:
    """Return the required gates for a specific PRD type."""
    ref = _ref()
    meta = ref["prd_types"].get(prd_type, {})
    return meta.get("required_gates", [])


def get_followup_for_vague_term(term: str, feature_name: str = "") -> str:
    """Get the appropriate follow-up question for a vague term in context."""
    ref = _ref()
    # Find which SMART category this vague term belongs to
    for cat, criteria in ref["smart_criteria"].items():
        if term.lower() in [v.lower() for v in criteria.get("vague_terms", [])]:
            fu = criteria.get("follow_up", "")
            if feature_name:
                fu = f"For '{feature_name}': {fu}"
            return fu
    return f"Can you quantify '{term}' with a specific, measurable value?"

