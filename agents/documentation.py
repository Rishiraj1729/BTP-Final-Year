"""Agent 5 — Documentation: derives architecture hints and delegates to PRDGenerator."""
from __future__ import annotations

import re
from state_schema import AgentState, ArchitectureHint


class DocumentationAgent:
    """Derives architecture hints from signals, then triggers PRD generation."""

    def __init__(self, llm=None) -> None:
        self._llm = llm

    def run(self, state: AgentState) -> None:
        self._derive_architecture(state)
        print("[DocumentationAgent] Architecture hints derived.")

    @staticmethod
    def _derive_architecture(state: AgentState) -> None:
        text = state.raw_input.lower()
        arch = ArchitectureHint()

        # Layers
        if "web" in text or "website" in text:
            arch.suggested_layers.append("Web Frontend (HTML/CSS/JS)")
        if "mobile" in text or "app" in text:
            arch.suggested_layers.append("Mobile App (iOS/Android or Responsive Web)")
        if "api" in text or "backend" in text or "server" in text:
            arch.suggested_layers.append("REST API / Backend Service")
        if "database" in text or "db" in text or "store" in text or "data" in text:
            arch.suggested_layers.append("Database Layer")
        if not arch.suggested_layers:
            arch.suggested_layers = ["Web Frontend", "API Backend", "Database"]

        # Tech hints
        if "react" in text:
            arch.suggested_tech.append("React")
        if "angular" in text:
            arch.suggested_tech.append("Angular")
        if "node" in text:
            arch.suggested_tech.append("Node.js")
        if "python" in text or "django" in text or "fastapi" in text or "flask" in text:
            arch.suggested_tech.append("Python Backend")
        if "postgres" in text or "mysql" in text or "sql" in text:
            arch.suggested_tech.append("SQL Database")
        if "mongo" in text:
            arch.suggested_tech.append("MongoDB")
        if "redis" in text:
            arch.suggested_tech.append("Redis (Cache)")
        if "aws" in text or "azure" in text or "gcp" in text or "cloud" in text:
            arch.suggested_tech.append("Cloud Deployment")

        # Integrations
        integrations = re.findall(r"integrat\w+ with ([\w\s]+?)[\.,\n]", text)
        for integ in integrations:
            arch.integration_points.append(integ.strip().title())
        if "payment" in text or "stripe" in text or "razorpay" in text:
            arch.integration_points.append("Payment Gateway")
        if "sms" in text or "otp" in text:
            arch.integration_points.append("SMS / OTP Provider")
        if "email" in text:
            arch.integration_points.append("Email Service (SMTP / SendGrid / SES)")

        # Deployment
        if "docker" in text or "container" in text:
            arch.deployment_notes.append("Containerised deployment (Docker/Kubernetes)")
        if "ci" in text or "cd" in text or "pipeline" in text:
            arch.deployment_notes.append("CI/CD pipeline required")

        state.derived_architecture = arch

