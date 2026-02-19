"""
decision_engine.py
------------------
Autonomous Decision Engine — makes architectural choices based on:
  - User-provided scale signals (peak_users, data_volume, growth_rate)
  - Domain / compliance requirements
  - Feature signals (real-time, payments, media, etc.)
  - Master Reference Knowledge Base (master_reference.json)

Returns a fully-resolved ArchitectureDecision that is injected into
the PRD and shown in the UI as "why the system chose X".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REF_PATH = Path(__file__).resolve().parent / "master_reference.json"


def _load_ref() -> Dict[str, Any]:
    with open(_REF_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Output dataclass ──────────────────────────────────────────────────────────

@dataclass
class ArchitectureDecision:
    scale_tier: str = "small"
    peak_users_estimated: int = 0

    # Database
    database_primary: str = ""
    database_cache: str = ""
    database_reason: str = ""

    # Hosting
    hosting_platform: str = ""
    hosting_reason: str = ""
    high_availability: bool = False

    # Auth
    auth_method: str = ""

    # API
    api_style: str = "REST"

    # Frontend
    frontend_stack: str = ""

    # Architecture pattern
    architecture_pattern: str = ""
    pattern_reason: str = ""

    # Compliance
    compliance_standards: List[str] = field(default_factory=list)

    # Autonomous choice log (shown to user as explanations)
    decision_log: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Scale tier detection ──────────────────────────────────────────────────────

def _detect_scale(peak_users: int) -> str:
    if peak_users <= 1000:
        return "small"
    elif peak_users <= 50_000:
        return "medium"
    elif peak_users <= 500_000:
        return "large"
    return "enterprise"


def _extract_user_count(text: str) -> int:
    """Best-effort extraction of user count from free text."""
    import re
    # patterns: "10000 users", "10k users", "10,000 users", "10M users"
    patterns = [
        (r"(\d[\d,]*)\s*k\s*(?:users|concurrent|people|customers)", lambda m: int(m.group(1).replace(",","")) * 1_000),
        (r"(\d[\d,]*)\s*m\s*(?:users|concurrent|people|customers)", lambda m: int(m.group(1).replace(",","")) * 1_000_000),
        (r"(\d[\d,]+)\s*(?:users|concurrent|people|customers)",      lambda m: int(m.group(1).replace(",",""))),
    ]
    text_lower = text.lower()
    for pattern, converter in patterns:
        m = re.search(pattern, text_lower)
        if m:
            return converter(m)
    return 0


# ── Main decision function ────────────────────────────────────────────────────

def make_decisions(
    signals: Dict[str, Any],
    domain: str = "general",
) -> ArchitectureDecision:
    """
    signals keys (all optional):
      peak_users      int  — concurrent user count
      data_type       str  — "structured" | "unstructured" | "mixed"
      has_realtime    bool — WebSocket / live updates needed
      has_payments    bool — payment processing
      has_media       bool — file/media uploads
      mobile_required bool — native mobile needed
      dashboard_heavy bool — analytics / charts heavy
      has_search      bool — full-text search needed
      raw_text        str  — raw conversation for user-count heuristics
    """
    ref = _load_ref()
    dec = ArchitectureDecision()
    log: List[Dict[str, str]] = []

    def note(category: str, choice: str, reason: str) -> None:
        log.append({"category": category, "choice": choice, "reason": reason})

    # ── 1. Determine scale ───────────────────────────────────────────────────
    peak_users = signals.get("peak_users", 0)
    if peak_users == 0 and signals.get("raw_text"):
        peak_users = _extract_user_count(signals["raw_text"])
    if peak_users == 0:
        peak_users = 1_000  # default assumption

    scale = _detect_scale(peak_users)
    dec.scale_tier = scale
    dec.peak_users_estimated = peak_users
    note("Scale", scale.capitalize(), f"Estimated {peak_users:,} peak concurrent users.")

    # ── 2. Database ──────────────────────────────────────────────────────────
    db_ref = ref["autonomous_decisions"]["database"][scale]
    dec.database_primary = db_ref["primary"]
    dec.database_cache   = db_ref.get("cache", "")
    dec.database_reason  = db_ref["reason"]

    # Override for unstructured data
    if signals.get("data_type") == "unstructured" and scale in ("small", "medium"):
        dec.database_primary = "MongoDB"
        dec.database_reason  = "Unstructured data (documents/media) benefits from a flexible document store."
        note("Database", "MongoDB", dec.database_reason)
    else:
        note("Database", dec.database_primary, dec.database_reason)

    # ── 3. Hosting ───────────────────────────────────────────────────────────
    host_ref = ref["autonomous_decisions"]["hosting"][scale]
    dec.hosting_platform = host_ref["platform"]
    dec.hosting_reason   = host_ref["reason"]
    dec.high_availability = host_ref["ha"]
    note("Hosting", dec.hosting_platform, dec.hosting_reason)

    # ── 4. Auth ──────────────────────────────────────────────────────────────
    auth_ref = ref["autonomous_decisions"]["auth"]
    dec.auth_method = auth_ref["default"]
    if scale == "enterprise":
        dec.auth_method = auth_ref["if_enterprise"]
        note("Auth", dec.auth_method, "Enterprise scale requires SSO/SAML for centralised identity management.")
    elif signals.get("has_payments") or domain in ("fintech", "healthtech"):
        dec.auth_method = auth_ref["if_fintech"]
        note("Auth", dec.auth_method, "Financial/health data requires MFA + OAuth 2.0 + comprehensive audit logging.")
    elif signals.get("has_pii"):
        dec.auth_method = auth_ref["if_pii_data"]
        note("Auth", dec.auth_method, "PII data detected — MFA is mandatory.")
    else:
        note("Auth", dec.auth_method, "JWT + Refresh tokens are the industry standard for stateless authentication.")

    # ── 5. API Style ─────────────────────────────────────────────────────────
    api_ref = ref["autonomous_decisions"]["api_style"]
    if scale in ("large", "enterprise"):
        dec.api_style = api_ref["microservices"]
        note("API", dec.api_style, "Microservices at this scale require gRPC for efficient inter-service communication.")
    elif signals.get("has_realtime"):
        dec.api_style = api_ref["real_time"]
        note("API", dec.api_style, "Real-time features (live updates, notifications) require WebSocket alongside REST.")
    elif signals.get("dashboard_heavy"):
        dec.api_style = api_ref["complex_queries"]
        note("API", dec.api_style, "Dashboard-heavy apps benefit from GraphQL to reduce over-fetching.")
    else:
        dec.api_style = api_ref["simple_crud"]
        note("API", "REST", "REST is the standard for CRUD-oriented APIs with broad client compatibility.")

    # ── 6. Frontend ──────────────────────────────────────────────────────────
    fe_ref = ref["autonomous_decisions"]["frontend"]
    if signals.get("mobile_required"):
        dec.frontend_stack = fe_ref["mobile_required"]
        note("Frontend", dec.frontend_stack, "Shared React Native codebase covers both iOS/Android + web.")
    elif signals.get("dashboard_heavy"):
        dec.frontend_stack = fe_ref["dashboard_heavy"]
        note("Frontend", dec.frontend_stack, "Recharts/D3 integration with React for data visualisation.")
    else:
        dec.frontend_stack = fe_ref["web_only"]
        note("Frontend", dec.frontend_stack, "React + TypeScript is the industry standard for maintainable web UIs.")

    # ── 7. Architecture Pattern ──────────────────────────────────────────────
    patterns = ref["architecture_patterns"]
    if peak_users <= 5_000:
        dec.architecture_pattern = "Monolith"
        dec.pattern_reason = patterns["monolith"]["pros"][0] + " — ideal for MVP phase."
    elif peak_users <= 50_000:
        dec.architecture_pattern = "Modular Monolith"
        dec.pattern_reason = "Structured for future service extraction without premature microservice complexity."
    elif peak_users <= 500_000:
        dec.architecture_pattern = "Microservices"
        dec.pattern_reason = "Independent scaling per service; fault isolation critical at this scale."
    else:
        dec.architecture_pattern = "Microservices + Event-Driven"
        dec.pattern_reason = "Kafka/event bus for async workflows; critical for enterprise-grade resilience."
    note("Architecture", dec.architecture_pattern, dec.pattern_reason)

    # ── 8. Compliance ────────────────────────────────────────────────────────
    compliance_ref = ref["compliance_map"]
    domain_key = domain.lower().replace("-", "").replace(" ", "")
    domain_map = {
        "fintech": "fintech", "finance": "fintech", "banking": "fintech",
        "health": "healthtech", "healthcare": "healthtech", "medical": "healthtech",
        "ecommerce": "ecommerce", "retail": "ecommerce", "shop": "ecommerce",
        "government": "government", "gov": "government",
    }
    mapped = domain_map.get(domain_key, "general")
    dec.compliance_standards = compliance_ref.get(mapped, compliance_ref["general"])
    note("Compliance", ", ".join(dec.compliance_standards),
         f"Detected domain '{domain}' maps to {mapped} compliance requirements.")

    # Search engine
    if signals.get("has_search") and scale in ("large", "enterprise"):
        note("Search", "Elasticsearch / OpenSearch",
             "Full-text search at scale requires a dedicated search engine alongside the primary DB.")

    dec.decision_log = log
    return dec


# ── Persona / Tone detection ──────────────────────────────────────────────────

def detect_technical_level(text: str) -> Tuple[str, int]:
    """
    Returns (level, jargon_count) where level is 'business' or 'technical'.
    Used by the Tone Screener to auto-upgrade persona mid-conversation.
    """
    ref = _load_ref()
    jargon = ref.get("tech_jargon_signals", [])
    text_lower = text.lower()
    count = sum(1 for j in jargon if j in text_lower)
    level = "technical" if count >= 3 else "business"
    return level, count

