"""
agents/auditor.py
-----------------
The Auditor Agent — "The Tamer."

Validates each extracted requirement against SMART criteria:
  S - Specific   (not vague)
  M - Measurable (has metrics/numbers)
  A - Achievable (not contradictory)
  R - Relevant   (tied to a stated business goal)
  T - Time-bound (deadline or phase mentioned)

For each vague item detected, the Auditor:
  1. Flags it as REJECTED with a reason
  2. Provides a SMART-compliant rewrite template
  3. Generates a targeted clarification question

The Question Agent then picks up these rejections and routes them
back to the user as a follow-up conversation turn.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REF_PATH = Path(__file__).resolve().parent.parent / "master_reference.json"


def _load_ref() -> Dict[str, Any]:
    with open(_REF_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Audit result types ────────────────────────────────────────────────────────

@dataclass
class AuditFinding:
    item_id: str                       # e.g. "NFR-01", "FR-03"
    item_title: str
    verdict: str                       # "PASS" | "REJECT" | "WARN"
    smart_failures: List[str] = field(default_factory=list)   # which SMART criteria failed
    vague_terms_found: List[str] = field(default_factory=list)
    clarification_question: str = ""
    smart_rewrite_template: str = ""
    smart_rewrite_example: str = ""
    category: str = ""                 # "performance" | "security" | "scalability" | "availability"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditReport:
    total_items: int = 0
    passed: int = 0
    rejected: int = 0
    warned: int = 0
    overall_smart_score: float = 0.0  # 0.0 – 1.0
    findings: List[AuditFinding] = field(default_factory=list)
    gate_status: Dict[str, str] = field(default_factory=dict)  # gate → "pass"|"fail"|"pending"

    def is_clear(self) -> bool:
        return self.rejected == 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Core audit logic ──────────────────────────────────────────────────────────

class AuditorAgent:
    """
    Audits requirements for SMART compliance.
    Operates on the list of FR / NFR dicts from AgentState.
    """

    def __init__(self, llm=None) -> None:
        self._llm = llm
        self._ref = _load_ref()

    def run(self, functional: List[Dict], non_functional: List[Dict]) -> AuditReport:
        findings: List[AuditFinding] = []
        gate_status: Dict[str, str] = {
            "performance":  "pending",
            "security":     "pending",
            "scalability":  "pending",
            "availability": "pending",
            "roles":        "pending",
            "features":     "pending",
        }

        # Audit NFRs (most vagueness lives here)
        for nfr in non_functional:
            finding = self._audit_item(nfr, item_type="nfr")
            findings.append(finding)
            cat = finding.category
            if cat and cat in gate_status:
                if finding.verdict == "PASS":
                    gate_status[cat] = "pass"
                elif finding.verdict == "REJECT":
                    gate_status[cat] = "fail"

        # Audit FRs (look for missing acceptance criteria / actors)
        for fr in functional:
            finding = self._audit_fr(fr)
            findings.append(finding)

        # Update gate for features
        fr_findings = [f for f in findings if f.item_id.startswith("FR")]
        if all(f.verdict == "PASS" for f in fr_findings):
            gate_status["features"] = "pass"
        elif any(f.verdict == "REJECT" for f in fr_findings):
            gate_status["features"] = "fail"

        # Role gate
        all_actors = set()
        for fr in functional:
            for a in fr.get("actors", []):
                if a: all_actors.add(a)
        gate_status["roles"] = "pass" if len(all_actors) > 0 else "fail"

        # Compute score
        total = len(findings)
        passed = sum(1 for f in findings if f.verdict == "PASS")
        rejected = sum(1 for f in findings if f.verdict == "REJECT")
        warned = sum(1 for f in findings if f.verdict == "WARN")
        score = round(passed / total, 2) if total else 0.0

        return AuditReport(
            total_items=total,
            passed=passed,
            rejected=rejected,
            warned=warned,
            overall_smart_score=score,
            findings=findings,
            gate_status=gate_status,
        )

    def _audit_item(self, item: Dict, item_type: str = "nfr") -> AuditFinding:
        smart_criteria = self._ref["smart_criteria"]
        text = (item.get("title", "") + " " + item.get("description", "")).lower()
        category = _detect_category(text)

        if category not in smart_criteria:
            return AuditFinding(
                item_id=item.get("id", "?"),
                item_title=item.get("title", ""),
                verdict="PASS",
                category=category,
            )

        criteria = smart_criteria[category]
        vague_found = [v for v in criteria["vague_terms"] if v in text]

        if not vague_found:
            return AuditFinding(
                item_id=item.get("id", "?"),
                item_title=item.get("title", ""),
                verdict="PASS",
                category=category,
            )

        # Check if measurable fields are explicitly mentioned
        required = criteria.get("required_fields", [])
        smart_failures = _check_measurable(text, required, category)

        verdict = "REJECT" if smart_failures else "WARN"

        clarification = _generate_question(category, vague_found, criteria)
        return AuditFinding(
            item_id=item.get("id", "?"),
            item_title=item.get("title", ""),
            verdict=verdict,
            smart_failures=smart_failures,
            vague_terms_found=vague_found,
            clarification_question=clarification,
            smart_rewrite_template=criteria.get("template", ""),
            smart_rewrite_example=criteria.get("example", ""),
            category=category,
        )

    def _audit_fr(self, fr: Dict) -> AuditFinding:
        failures = []
        if not fr.get("acceptance_criteria") and not fr.get("acceptanceCriteria"):
            failures.append("Missing acceptance criteria — not Measurable or Time-bound.")
        if not fr.get("actors"):
            failures.append("No actors defined — not Specific enough.")

        if failures:
            return AuditFinding(
                item_id=fr.get("id", "?"),
                item_title=fr.get("title", ""),
                verdict="WARN",
                smart_failures=failures,
                clarification_question=(
                    f"For '{fr.get('title', 'this feature')}': "
                    "Who uses it, and what is the exact condition under which it is considered done?"
                ),
                category="features",
            )

        return AuditFinding(
            item_id=fr.get("id", "?"),
            item_title=fr.get("title", ""),
            verdict="PASS",
            category="features",
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_category(text: str) -> str:
    keywords = {
        "performance":  ["fast", "quick", "slow", "latency", "response", "performance", "speed"],
        "security":     ["secure", "security", "safe", "encrypt", "auth", "password", "login"],
        "scalability":  ["scale", "scalab", "users", "concurrent", "traffic", "load"],
        "availability": ["uptime", "availab", "downtime", "reliable", "always", "sla"],
        "roles":        ["role", "admin", "permission", "access control", "rbac"],
    }
    for cat, terms in keywords.items():
        if any(t in text for t in terms):
            return cat
    return "general"


def _check_measurable(text: str, required_fields: List[str], category: str) -> List[str]:
    """Return list of SMART failures (missing measurable fields)."""
    failures = []
    checks = {
        "response_time_ms": lambda t: bool(re.search(r"\d+\s*ms|\d+\s*milliseconds|\d+\s*seconds?\b", t)),
        "percentile":       lambda t: bool(re.search(r"p\d{2}|percentile|\d+th", t)),
        "concurrent_users": lambda t: bool(re.search(r"\d[\d,]*\s*(?:concurrent|simultaneous|users|req)", t)),
        "auth_method":      lambda t: any(x in t for x in ["oauth", "jwt", "saml", "mfa", "otp", "sso", "2fa"]),
        "encryption_standard": lambda t: any(x in t for x in ["aes", "tls", "ssl", "256", "rsa"]),
        "compliance_standard": lambda t: any(x in t for x in ["gdpr", "pci", "hipaa", "iso", "sox", "nist"]),
        "uptime_sla_percent": lambda t: bool(re.search(r"99\.?\d*\s*%|uptime\s+sla", t)),
        "rto_minutes":      lambda t: bool(re.search(r"rto|recovery time", t)),
        "rpo_minutes":      lambda t: bool(re.search(r"rpo|recovery point", t)),
        "peak_concurrent_users": lambda t: bool(re.search(r"\d[\d,]*\s*(?:concurrent|simultaneous|users)", t)),
        "data_volume_gb":   lambda t: bool(re.search(r"\d+\s*(?:gb|tb|mb)\s+data", t)),
        "growth_rate_percent": lambda t: bool(re.search(r"\d+\s*%\s*(?:growth|annual|increase)", t)),
    }
    for field in required_fields:
        check_fn = checks.get(field)
        if check_fn and not check_fn(text):
            failures.append(f"Not Measurable: '{field.replace('_', ' ')}' is missing.")
    return failures


def _generate_question(category: str, vague_terms: List[str], criteria: Dict) -> str:
    term = vague_terms[0] if vague_terms else "this"
    questions = {
        "performance": (
            f"You mentioned '{term}' — can you give me a number? "
            "What is your target response time (ms) for the key user action, "
            "and how many users do you expect simultaneously?"
        ),
        "security": (
            f"You mentioned '{term}' — let's make it specific. "
            "Which authentication method do you need (OTP, OAuth, SSO)? "
            "Are you subject to any compliance standards (GDPR, PCI-DSS, HIPAA)?"
        ),
        "scalability": (
            f"You mentioned '{term}' — I need numbers. "
            "How many concurrent users in Year 1 and Year 3? "
            "What is your expected annual data growth in GB?"
        ),
        "availability": (
            f"You mentioned '{term}' — what does that mean in SLA terms? "
            "What is your acceptable downtime per month (e.g. 99.9% = ~43 min/month)? "
            "What is your Recovery Time Objective (RTO) if the system fails?"
        ),
    }
    return questions.get(category, f"Can you provide specific, measurable details for '{term}'?")
