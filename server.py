"""
server.py  -  Agentic Requirements Engine (ARE) v3
FastAPI backend.

New in v3:
  POST /api/gap-check        - Iterative gap analysis (keeps asking until complete)
  POST /api/transcribe       - Audio file -> transcript text
  POST /api/update-prd       - Refine existing PRD version with user type context
  POST /api/new-from-version - Generate fresh PRD based on an existing version
  GET  /api/versions         - Version history (all projects)
  GET  /api/prd-types        - Available PRD types from master_reference
  GET  /api/nfr-templates    - SMART NFR templates
"""

from __future__ import annotations

import json
import os
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
    root = Path(__file__).resolve().parent
    load_dotenv(dotenv_path=root / ".env")
    load_dotenv(dotenv_path=root / ".venv" / ".env")
except Exception:
    pass

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Agentic Requirements Engine", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_ref() -> Dict[str, Any]:
    with open(Path(__file__).resolve().parent / "master_reference.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _build_llm(provider: str):
    if provider == "mock":
        class _Mock:
            _is_mock = True
            def generate_text(self, sp="", up="", system_prompt="", user_prompt=""): return ""
        return _Mock()

    if provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise HTTPException(400, "GROQ_API_KEY not set. Add it to .env or run with provider=mock")
        from groq import Groq  # type: ignore
        client = Groq(api_key=api_key)
        model  = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        fallbacks = ["llama-3.3-70b-versatile", "llama3-70b-8192", "llama3-8b-8192"]

        class _Groq:
            def generate_text(self, sp: str = "", up: str = "",
                              system_prompt: str = "", user_prompt: str = "") -> str:
                sp = system_prompt or sp
                up = user_prompt or up
                for m in list(dict.fromkeys([model] + fallbacks)):
                    try:
                        r = client.chat.completions.create(
                            model=m, temperature=0.2,
                            messages=[{"role": "system", "content": sp},
                                      {"role": "user",   "content": up}],
                        )
                        return (r.choices[0].message.content or "").strip()
                    except Exception as e:
                        msg = str(e).lower()
                        if "invalid api key" in msg or "401" in msg:
                            raise HTTPException(401, "Invalid Groq API key.")
                        if "decommissioned" not in msg:
                            raise HTTPException(500, str(e))
                raise HTTPException(500, "All Groq models failed.")
        return _Groq()

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(400, "GEMINI_API_KEY not set.")
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=api_key)
        gmodel = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))

        class _Gemini:
            def generate_text(self, sp: str, up: str) -> str:
                r = gmodel.generate_content(up)
                return (r.text or "").strip()
        return _Gemini()

    raise HTTPException(400, f"Unknown provider: {provider}")


# ── Request / Response models ─────────────────────────────────────────────────

class CalibrateRequest(BaseModel):
    message: str
    stated_level: Optional[str] = None

class GapCheckRequest(BaseModel):
    raw_text: str
    functional: List[Dict[str, Any]] = []
    non_functional: List[Dict[str, Any]] = []
    messages: List[Dict[str, Any]] = []
    completion_threshold: float = 0.80

class AnalyzeRequest(BaseModel):
    conversation: str
    provider: str = "mock"
    persona: str = "PM"
    project_name: str = "Untitled Project"
    client_name: str = ""
    domain: str = "General"
    signals: Dict[str, Any] = {}

class AuditRequest(BaseModel):
    functional: List[Dict[str, Any]]
    non_functional: List[Dict[str, Any]]
    raw_text: str = ""
    domain: str = "general"
    signals: Dict[str, Any] = {}

class GeneratePRDRequest(BaseModel):
    conversation: str
    provider: str = "mock"
    persona: str = "PM"
    project_name: str = "Untitled Project"
    client_name: str = ""
    domain: str = "General"
    signals: Dict[str, Any] = {}
    audit_report: Optional[Dict[str, Any]] = None
    architecture: Optional[Dict[str, Any]] = None

class UpdatePRDRequest(BaseModel):
    version_id: int
    new_conversation: str
    user_type: str = "PM"          # persona / user type as context
    provider: str = "mock"
    project_name: str = ""
    change_type: str = "refine"    # "refine" | "new"

class MessageFeedRequest(BaseModel):
    """Incremental chat message + current state for real-time gap tracking."""
    message: str
    role: str = "user"
    current_raw_text: str = ""
    functional: List[Dict[str, Any]] = []
    non_functional: List[Dict[str, Any]] = []
    messages: List[Dict[str, Any]] = []
    provider: str = "mock"


# ── Health check endpoint ─────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    """Health check endpoint for Streamlit frontend"""
    return {"status": "ok", "message": "Requirements Engine API is running"}

# ── Static knowledge endpoints ────────────────────────────────────────────────

@app.get("/api/personas")
def list_personas():
    from persona_config import PERSONAS
    return {
        "personas": [
            {"name": k, "tone": v.tone, "focus": v.focus, "format": v.output_format}
            for k, v in PERSONAS.items()
        ]
    }


@app.get("/api/prd-types")
def get_prd_types():
    ref = _load_ref()
    return {
        "types": [
            {"id": k, "label": v["label"], "keywords": v.get("keywords", [])[:6],
             "required_gates": v.get("required_gates", [])}
            for k, v in ref["prd_types"].items()
        ]
    }


@app.get("/api/nfr-templates")
def get_nfr_templates():
    ref = _load_ref()
    return {"templates": ref.get("nfr_templates", {})}


@app.get("/api/discovery-questions")
def get_discovery_questions():
    ref = _load_ref()
    return {"questions": ref["discovery_questions"]["sequence"]}


@app.get("/api/versions")
def get_versions():
    from database import PRDDatabase
    db = PRDDatabase()
    rows = db.list_all()
    db.close()
    return rows


@app.get("/api/versions/{version}")
def get_version(version: int):
    from database import PRDDatabase
    try:
        db = PRDDatabase()
        state = db.load(version)
        db.close()
        return {
            "version": state.version,
            "project_name": state.project_name,
            "prd_markdown": state.prd_markdown,
            "completion": state.completion_status.__dict__,
            "functional_count": len(state.functional),
            "nfr_count": len(state.non_functional),
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


# ── Core intelligence endpoints ───────────────────────────────────────────────

@app.post("/api/calibrate")
def calibrate(req: CalibrateRequest):
    from decision_engine import detect_technical_level
    detected, count = detect_technical_level(req.message)
    upgrade = (req.stated_level == "business" and detected == "technical")
    ref = _load_ref()
    prd_type = None
    if req.message:
        from gap_engine import _detect_prd_type
        prd_type = _detect_prd_type(req.message)

    return {
        "detected_level":     detected,
        "jargon_count":       count,
        "stated_level":       req.stated_level or detected,
        "auto_upgrade":       upgrade,
        "upgrade_message":    ("I noticed technical vocabulary — upgrading to architect-depth discussion." if upgrade else None),
        "recommended_persona": "CTO" if detected == "technical" else "PM",
        "detected_prd_type":  prd_type,
        "prd_type_label":     ref["prd_types"].get(prd_type or "", {}).get("label", ""),
    }


@app.post("/api/detect-tone")
def detect_tone(req: CalibrateRequest):
    from decision_engine import detect_technical_level
    from gap_engine import _detect_prd_type
    detected, count = detect_technical_level(req.message)
    prd_type = _detect_prd_type(req.message)
    return {"detected_level": detected, "jargon_count": count, "prd_type_hint": prd_type}


@app.post("/api/gap-check")
def gap_check(req: GapCheckRequest):
    """
    Analyse current session state for missing information.
    Returns:
      - list of open gaps (critical/important)
      - next question to ask
      - completion score
      - is_complete flag
    Called after EVERY user message to drive the iterative interview loop.
    """
    try:
        from gap_engine import analyze_gaps
        report = analyze_gaps(
            raw_text=req.raw_text,
            functional=req.functional,
            non_functional=req.non_functional,
            conversation_history=req.messages,
            completion_threshold=req.completion_threshold,
        )
        return report.to_dict()
    except Exception as e:
        raise HTTPException(500, f"Gap check failed: {e}\n{traceback.format_exc()}")


@app.post("/api/message")
def process_message(req: MessageFeedRequest):
    """
    Process a single chat message:
    1. Run gap check on accumulated state
    2. Extract any new signals from the message
    3. Return next question + gap status
    """
    try:
        from gap_engine import analyze_gaps
        new_messages = req.messages + [{"role": req.role, "text": req.message}]
        full_text = req.current_raw_text + "\n" + req.message

        # Snapshot resolved gates BEFORE this message (for delta celebration)
        prev_report = analyze_gaps(
            raw_text=req.current_raw_text,
            functional=req.functional,
            non_functional=req.non_functional,
            conversation_history=req.messages,
        )
        resolved_before = list(prev_report.resolved_gaps)

        report = analyze_gaps(
            raw_text=full_text,
            functional=req.functional,
            non_functional=req.non_functional,
            conversation_history=new_messages,
        )

        # Generate contextual AI response
        ai_response = _generate_ai_response(req.message, report, resolved_before)

        return {
            "ai_response":  ai_response,
            "gap_report":   report.to_dict(),
            "accumulated_text": full_text.strip(),
        }
    except Exception as e:
        raise HTTPException(500, f"Message processing failed: {e}\n{traceback.format_exc()}")


def _generate_ai_response(user_msg: str, gap_report, resolved_gates_before: list = None) -> str:
    """Generate contextual AI response based on gap status."""
    import random

    # Gate-specific acknowledgements that reference what the user just said
    generic_acks = [
        "Got it.", "Understood.", "Good.", "Perfect.", "Makes sense.",
        "Noted.", "That's helpful.", "Clear.", "Excellent.", "Great detail."
    ]
    ack = random.choice(generic_acks)

    # Celebrate newly resolved gates
    newly_resolved = []
    if resolved_gates_before:
        current_resolved = set(gap_report.resolved_gaps)
        newly_resolved = [g for g in current_resolved if g not in resolved_gates_before]

    resolved_note = ""
    if newly_resolved:
        resolved_note = f" ✓ {', '.join(newly_resolved).replace('_',' ').title()} captured."

    if gap_report.is_complete:
        return (
            f"{ack}{resolved_note} I now have everything I need to generate "
            "a comprehensive PRD. Starting the generation pipeline now..."
        )

    if gap_report.critical_open == 0 and gap_report.important_open > 0:
        score_pct = int(gap_report.completion_score * 100)
        return (
            f"{ack}{resolved_note} Critical requirements are complete ({score_pct}%). "
            f"A few more details will make the PRD richer — "
            f"{gap_report.next_question}"
        )

    if gap_report.next_question:
        score_pct = int(gap_report.completion_score * 100)
        remaining = gap_report.critical_open
        remaining_note = f"{remaining} critical item{'s' if remaining != 1 else ''} left. " if remaining else ""
        return f"{ack}{resolved_note} {remaining_note}{gap_report.next_question}"

    return f"{ack}{resolved_note} Tell me more about what the system needs to do."


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    try:
        from state_schema import AgentState
        from agents import TranscriptionAgent, RequirementAnalyzerAgent
        from persona_config import get_persona
        from gap_engine import analyze_gaps, _detect_prd_type

        state = AgentState(project_name=req.project_name, client_name=req.client_name, domain=req.domain)
        state.persona = get_persona(req.persona)
        llm = _build_llm(req.provider)

        TranscriptionAgent().run_from_text(state, req.conversation)
        RequirementAnalyzerAgent(llm=llm).run(state)

        # Run gap check after extraction
        gap_report = analyze_gaps(
            raw_text=req.conversation,
            functional=state.functional,
            non_functional=state.non_functional,
        )

        return {
            "success": True,
            "functional":      state.functional,
            "non_functional":  state.non_functional,
            "constraints":     state.constraints_list,
            "assumptions":     state.assumptions_list,
            "extracted_signals": state.extracted_signals.__dict__,
            "gap_report":      gap_report.to_dict(),
            "prd_type":        gap_report.prd_type_detected,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"{e}\n{traceback.format_exc()}")


@app.post("/api/audit")
def audit(req: AuditRequest):
    try:
        from agents.auditor import AuditorAgent
        from decision_engine import make_decisions

        report   = AuditorAgent().run(req.functional, req.non_functional)
        signals  = dict(req.signals)
        signals["raw_text"] = req.raw_text
        arch     = make_decisions(signals, domain=req.domain)

        return {
            "success":        True,
            "audit":          report.to_dict(),
            "architecture":   arch.to_dict(),
            "all_gates_clear": report.is_clear(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"{e}\n{traceback.format_exc()}")


@app.post("/api/generate-prd")
def generate_prd(req: GeneratePRDRequest):
    try:
        from state_schema import AgentState
        from agents import (TranscriptionAgent, RequirementAnalyzerAgent,
                            AmbiguityDetectionAgent, QuestionGenerationAgent, DocumentationAgent)
        from agents.auditor import AuditorAgent
        from persona_config import get_persona
        from completion_engine import evaluate
        from prd_generator import PRDGenerator
        from state_manager import save_version
        from database import PRDDatabase
        from decision_engine import make_decisions
        from gap_engine import analyze_gaps

        state   = AgentState(project_name=req.project_name, client_name=req.client_name, domain=req.domain)
        persona = get_persona(req.persona)
        state.persona = persona
        llm = _build_llm(req.provider)

        TranscriptionAgent().run_from_text(state, req.conversation)
        RequirementAnalyzerAgent(llm=llm).run(state)
        AmbiguityDetectionAgent(llm=llm).run(state)
        QuestionGenerationAgent(llm=llm).run(state)
        DocumentationAgent(llm=llm).run(state)

        audit_rpt = AuditorAgent(llm=llm).run(state.functional, state.non_functional)

        signals = dict(req.signals)
        signals["raw_text"] = req.conversation
        arch = req.architecture or make_decisions(signals, domain=req.domain).to_dict()

        gap_rpt = analyze_gaps(req.conversation, state.functional, state.non_functional)

        status = evaluate(state)

        gen = PRDGenerator(llm=None)
        base_md = gen.generate(state, persona)
        arch_md = _arch_section(arch, audit_rpt.to_dict())
        state.prd_markdown = base_md + "\n\n" + arch_md

        save_version(state)
        db = PRDDatabase()
        db.save(state)
        db.close()

        return {
            "success":            True,
            "version":            state.version,
            "persona":            persona.name,
            "prd_markdown":       state.prd_markdown,
            "functional":         state.functional,
            "non_functional":     state.non_functional,
            "constraints":        state.constraints_list,
            "assumptions":        state.assumptions_list,
            "gaps":               [g.__dict__ for g in state.gaps],
            "follow_up_questions": state.follow_up_questions,
            "completion":         {**state.completion_status.__dict__, "is_complete": status.is_complete()},
            "architecture":       arch,
            "audit":              audit_rpt.to_dict(),
            "gap_report":         gap_rpt.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"{e}\n{traceback.format_exc()}")


@app.post("/api/update-prd")
def update_prd(req: UpdatePRDRequest):
    """
    Refine an existing PRD version with new conversation context.
    user_type is passed as context to tailor the update focus.
    change_type: 'refine' = update existing | 'new' = generate fresh v+1
    """
    try:
        from database import PRDDatabase
        from persona_config import get_persona
        from decision_engine import make_decisions
        from gap_engine import analyze_gaps
        from agents.auditor import AuditorAgent
        from state_schema import AgentState
        from agents import (TranscriptionAgent, RequirementAnalyzerAgent,
                            AmbiguityDetectionAgent, QuestionGenerationAgent, DocumentationAgent)
        from completion_engine import evaluate
        from prd_generator import PRDGenerator
        from state_manager import save_version

        # Load previous version
        db = PRDDatabase()
        try:
            prev_state = db.load(req.version_id)
        except ValueError as e:
            db.close()
            raise HTTPException(404, str(e))

        llm = _build_llm(req.provider)
        persona = get_persona(req.user_type)

        # Build context from previous state
        prev_summary = _summarize_version(prev_state)

        # Merge old conversation + new conversation
        merged_convo = prev_state.raw_input + "\n\n[UPDATE CONTEXT]:\n" + req.new_conversation

        # Re-run pipeline on merged or new conversation
        target_convo = merged_convo if req.change_type == "refine" else req.new_conversation

        state = AgentState(
            project_name=req.project_name or prev_state.project_name,
            client_name=prev_state.client_name,
            domain=prev_state.domain,
        )
        state.persona = persona

        TranscriptionAgent().run_from_text(state, target_convo)
        RequirementAnalyzerAgent(llm=llm).run(state)
        AmbiguityDetectionAgent(llm=llm).run(state)
        QuestionGenerationAgent(llm=llm).run(state)
        DocumentationAgent(llm=llm).run(state)

        audit_rpt = AuditorAgent(llm=llm).run(state.functional, state.non_functional)
        arch = make_decisions({"raw_text": target_convo}, domain=state.domain).to_dict()
        gap_rpt = analyze_gaps(target_convo, state.functional, state.non_functional)
        status = evaluate(state)

        # Get update context prompt from master reference
        ref = _load_ref()
        update_hint = ref["persona_update_prompts"].get(req.user_type, "")

        # PRD with change diff annotation
        gen = PRDGenerator(llm=None)
        new_md = gen.generate(state, persona)

        # Prepend change summary
        change_header = _build_change_header(
            prev_version=prev_state.version,
            new_version=prev_state.version + 1,
            change_type=req.change_type,
            user_type=req.user_type,
            update_hint=update_hint,
            prev_fr_count=len(prev_state.functional),
            new_fr_count=len(state.functional),
        )

        state.prd_markdown = change_header + "\n\n" + new_md + "\n\n" + _arch_section(arch, audit_rpt.to_dict())
        save_version(state)
        db.save(state)
        db.close()

        return {
            "success":        True,
            "version":        state.version,
            "previous_version": req.version_id,
            "change_type":    req.change_type,
            "persona":        persona.name,
            "prd_markdown":   state.prd_markdown,
            "completion":     {**state.completion_status.__dict__, "is_complete": status.is_complete()},
            "architecture":   arch,
            "gap_report":     gap_rpt.to_dict(),
            "changes_summary": {
                "fr_added":   max(0, len(state.functional)    - len(prev_state.functional)),
                "fr_removed": max(0, len(prev_state.functional) - len(state.functional)),
                "nfr_added":  max(0, len(state.non_functional) - len(prev_state.non_functional)),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"{e}\n{traceback.format_exc()}")


@app.post("/api/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    provider: str = Form(default="gemini"),
):
    """
    Transcribe an uploaded audio file to text.
    Uses Gemini 1.5 Flash multimodal for best results.
    Falls back to returning an error message if Gemini not available.
    """
    try:
        audio_bytes = await file.read()
        mime_type   = file.content_type or "audio/wav"

        if provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise HTTPException(400, "GEMINI_API_KEY required for audio transcription. Add to .env")
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            resp  = model.generate_content([
                {
                    "role": "user",
                    "parts": [
                        {"inline_data": {"mime_type": mime_type, "data": audio_bytes}},
                        {"text": (
                            "Transcribe this audio recording verbatim. "
                            "Format as a conversation transcript. "
                            "Prefix each speaker with 'Client: ' or 'Interviewer: '. "
                            "Do not summarise — transcribe every word."
                        )}
                    ]
                }
            ])
            transcript = (resp.text or "").strip()
        elif provider == "mock":
            transcript = (
                "Client: We need a web application for managing loan applications.\n"
                "Client: The system should handle about 5000 concurrent users.\n"
                "Client: It needs to be secure and fast, with OAuth 2.0 authentication.\n"
                "Client: We need dashboards for loan officers and an admin panel.\n"
                "Client: The app must comply with RBI guidelines and have audit trails.\n"
                "Client: Response time should be under 500ms for 95% of requests.\n"
                "Client: We need it live by Q3 2025."
            )
        else:
            raise HTTPException(400, f"Provider '{provider}' not supported for audio transcription. Use 'gemini' or 'mock'.")

        # Run initial gap check on the transcript
        from gap_engine import analyze_gaps, _detect_prd_type
        prd_type = _detect_prd_type(transcript)
        gap_rpt  = analyze_gaps(raw_text=transcript, functional=[], non_functional=[])

        return {
            "success":    True,
            "transcript": transcript,
            "word_count": len(transcript.split()),
            "prd_type":   prd_type,
            "gap_report": gap_rpt.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Transcription failed: {e}\n{traceback.format_exc()}")


# ── Markdown helpers ──────────────────────────────────────────────────────────

def _arch_section(arch: Dict, audit: Dict) -> str:
    lines = [
        "---",
        "## Appendix A: Autonomous Architecture Decisions",
        f"> **Scale Tier**: {arch.get('scale_tier','?').upper()} | "
        f"**Est. Peak Users**: {arch.get('peak_users_estimated',0):,} | "
        f"**Pattern**: {arch.get('architecture_pattern','')}",
        "",
        "| Category | Decision | Rationale |",
        "|---|---|---|",
    ]
    for e in arch.get("decision_log", []):
        lines.append(f"| {e.get('category','')} | `{e.get('choice','')}` | {e.get('reason','')} |")

    if arch.get("compliance_standards"):
        lines += ["", f"**Compliance Standards**: {', '.join(arch['compliance_standards'])}"]

    lines += [
        "",
        "---",
        "## Appendix B: SMART Audit Summary",
        f"| Metric | Value |",
        f"|---|---|",
        f"| SMART Score | {round(audit.get('overall_smart_score',0)*100)}% |",
        f"| Passed | {audit.get('passed',0)} |",
        f"| Rejected | {audit.get('rejected',0)} |",
        f"| Warned | {audit.get('warned',0)} |",
        "",
    ]
    rejected = [f for f in audit.get("findings", []) if f.get("verdict") == "REJECT"]
    if rejected:
        lines.append("### Open SMART Items (resolve before sign-off)")
        for f in rejected:
            lines.append(f"- **{f['item_id']}** `[{f['category'].upper()}]` — {f['clarification_question']}")
            if f.get("smart_rewrite_example"):
                lines.append(f"  > **SMART example**: {f['smart_rewrite_example']}")
    return "\n".join(lines)


def _summarize_version(state) -> str:
    return (
        f"Previous PRD v{state.version}: {state.project_name}\n"
        f"FRs: {len(state.functional)}, NFRs: {len(state.non_functional)}, "
        f"Score: {getattr(state.completion_status, 'overall_score', 0)*100:.0f}%"
    )


def _build_change_header(prev_version, new_version, change_type, user_type,
                          update_hint, prev_fr_count, new_fr_count) -> str:
    action = "Refined" if change_type == "refine" else "New version generated from"
    delta_fr = new_fr_count - prev_fr_count
    delta_str = f"+{delta_fr}" if delta_fr >= 0 else str(delta_fr)
    return (
        f"<!-- ARE-GENERATED v{new_version} | {action} v{prev_version} | Persona: {user_type} -->\n\n"
        f"> **Version**: v{new_version}  | **Based on**: v{prev_version}  | "
        f"**Perspective**: {user_type}  | **FR Delta**: {delta_str}\n\n"
        f"> *{update_hint}*\n\n---"
    )


# ── Essential questions for simple user flow ─────────────────────────────────

def _auto_provider() -> str:
    """Use Groq if key is present, otherwise fall back to mock."""
    return "groq" if os.getenv("GROQ_API_KEY") else "mock"


# ── Domain detection + dynamic question engine ───────────────────────────────

# Core gates always asked (domain-independent, ordered)
_CORE_GATES = [
    "project_identity",
    "users_roles",
    "features_detail",
    "platform",
    "scale",
    "timeline",
    "integrations",
    "security",
]

def _detect_domain(description: str, ref: dict):
    """Return (prd_type_key, prd_type_data) or ('general', None)."""
    if not description:
        return "general", None
    dl = description.lower()
    for ptype, data in ref.get("prd_types", {}).items():
        for kw in data.get("keywords", []):
            if kw.lower() in dl:
                return ptype, data
    return "general", None


def _build_gate_list(prd_data: Optional[dict]) -> List[str]:
    """Merge core gates + domain-specific required_gates, capped at 9."""
    domain_gates: List[str] = prd_data.get("required_gates", []) if prd_data else []
    seen: set = set()
    ordered: List[str] = []
    for g in _CORE_GATES + domain_gates:
        if g not in seen:
            seen.add(g)
            ordered.append(g)
    return ordered[:9]


def _get_gate_question(gate: str, domain: str, prd_data: Optional[dict], ref: dict) -> str:
    """
    Priority:
      1. domain override in gate_questions._domain_overrides
      2. gate_questions map (includes LLM-cached entries)
      3. universal_gates first question
      4. LLM-generated → saved to master_reference for future use
    """
    gate_q: dict = ref.get("gate_questions", {})

    # 1. Domain-specific override
    override = gate_q.get("_domain_overrides", {}).get(domain, {}).get(gate)
    if override:
        return override

    # 2. Flat gate_questions map
    entry = gate_q.get(gate)
    if entry and isinstance(entry, str):
        return entry
    if entry and isinstance(entry, list) and entry:
        return entry[0]

    # 3. universal_gates
    ug = ref.get("universal_gates", {}).get(gate, {})
    qs = ug.get("questions", [])
    if qs:
        return qs[0]

    # 4. LLM-generate and cache
    domain_label = prd_data.get("label", "software") if prd_data else "software"
    try:
        llm = _build_llm(_auto_provider())
        generated = llm.generate_text(
            system_prompt=(
                "You are a business analyst interviewing a product owner. "
                "Generate ONE short, friendly, jargon-free question to gather "
                "the requirement for the given aspect of their product. "
                "Max 2 sentences. No bullet points."
            ),
            user_prompt=(
                f"Product domain: {domain_label}\n"
                f"Requirement aspect: {gate.replace('_', ' ')}\n"
                "Write the question:"
            ),
        ).strip()
    except Exception:
        generated = ""

    if not generated:
        generated = f"Can you describe the {gate.replace('_', ' ')} requirements for your product?"

    # Persist back to master_reference
    try:
        ref_path = Path(__file__).resolve().parent / "master_reference.json"
        gate_q[gate] = generated
        ref["gate_questions"] = gate_q
        with open(ref_path, "w", encoding="utf-8") as fout:
            json.dump(ref, fout, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return generated


def _maybe_add_domain(domain: str, description: str, prd_data: Optional[dict], ref: dict) -> None:
    """If domain is new ('general'), ask LLM to suggest a prd_type entry and save it."""
    if domain != "general" or not description.strip():
        return
    try:
        llm = _build_llm(_auto_provider())
        raw = llm.generate_text(
            system_prompt=(
                "You are a software architect. Given a product description, "
                "output ONLY valid JSON (no markdown) with keys: "
                '"label", "keywords" (array of 5), "required_gates" (array of 6-8 snake_case strings).'
            ),
            user_prompt=f"Product description:\n{description[:500]}",
        ).strip()
        # strip fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        new_type = json.loads(raw)
        # derive a key
        key = new_type.get("label", "custom").lower().replace(" ", "_").replace("/", "_")[:30]
        ref.setdefault("prd_types", {})[key] = new_type
        ref_path = Path(__file__).resolve().parent / "master_reference.json"
        with open(ref_path, "w", encoding="utf-8") as fout:
            json.dump(ref, fout, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ── Auth / user management ────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    name:    str
    role:    str = "user"    # "user" | "admin"
    email:   str = ""
    picture: str = ""
    pin:     str = ""        # required when role=admin and email not whitelisted


def _is_admin_email(email: str) -> bool:
    """Check if email is in ADMIN_EMAILS whitelist."""
    raw = os.getenv("ADMIN_EMAILS", "").strip()
    if not raw or not email:
        return False
    whitelist = [e.strip().lower() for e in raw.split(",") if e.strip()]
    return email.strip().lower() in whitelist


@app.post("/api/login")
def login(req: LoginRequest):
    if not req.name.strip():
        raise HTTPException(400, "Name is required.")
    if req.role not in ("user", "admin"):
        raise HTTPException(400, "Role must be 'user' or 'admin'.")

    resolved_role = req.role

    if req.role == "admin":
        # Path 1: Google email on whitelist → auto-approved
        if req.email and _is_admin_email(req.email):
            resolved_role = "admin"
        else:
            # Path 2: Must supply correct PIN
            correct_pin = os.getenv("ADMIN_PIN", "").strip()
            if not correct_pin:
                raise HTTPException(403,
                    "Admin access is not configured. Set ADMIN_PIN in .env")
            if req.pin.strip() != correct_pin:
                raise HTTPException(403,
                    "Incorrect admin PIN. Contact your system administrator.")

    from database import PRDDatabase
    db = PRDDatabase()
    user = db.upsert_user(req.name.strip(), resolved_role,
                          email=req.email.strip(),
                          picture=req.picture.strip())
    db.close()
    return user


@app.get("/api/check-admin-email")
def check_admin_email(email: str = ""):
    """
    Called by the frontend after Google sign-in to know if this email
    is a whitelisted admin — so the UI can skip the role selector.
    """
    if not email:
        return {"is_admin": False}
    return {"is_admin": _is_admin_email(email)}


# ── Simple user flow ──────────────────────────────────────────────────────────

class NextQuestionRequest(BaseModel):
    answers: List[Dict[str, Any]] = []          # [{id, gate, text, answer}]
    initial_description: str = ""              # product description (passed every call)


@app.post("/api/next-question")
def next_question(req: NextQuestionRequest):
    """
    Dynamic interview engine.
    1. Detect domain from description using master_reference keywords.
    2. Build ordered gate list (core + domain-specific).
    3. Return next unanswered gate question (from master_reference or LLM-generated).
    4. If a genuinely new domain is detected, ask LLM to generate a prd_type entry
       and persist it to master_reference.
    """
    ref = _load_ref()

    domain, prd_data = _detect_domain(req.initial_description, ref)

    # If completely unknown domain, try to enrich master_reference asynchronously
    if domain == "general" and req.initial_description.strip():
        try:
            _maybe_add_domain(domain, req.initial_description, prd_data, ref)
            # Reload after potential update
            ref = _load_ref()
            domain, prd_data = _detect_domain(req.initial_description, ref)
        except Exception:
            pass

    all_gates = _build_gate_list(prd_data)
    answered_gates = {
        a.get("gate") for a in req.answers
        if a.get("answer", "").strip()
    }

    for gate in all_gates:
        if gate not in answered_gates:
            question_text = _get_gate_question(gate, domain, prd_data, ref)
            return {
                "done": False,
                "question": {"id": gate, "gate": gate, "text": question_text},
                "answered": len(answered_gates),
                "total": len(all_gates),
                "detected_domain": domain,
                "domain_label": (
                    prd_data.get("label", "General Software") if prd_data
                    else "General Software"
                ),
            }

    return {
        "done": True,
        "answered": len(answered_gates),
        "total": len(all_gates),
        "detected_domain": domain,
        "domain_label": (
            prd_data.get("label", "General Software") if prd_data else "General Software"
        ),
    }


class SubmitRequirementsRequest(BaseModel):
    user_name: str = "Anonymous User"  # Made optional with default
    project_name: str = "My Project"
    answers: List[Dict[str, Any]] = []   # [{id, gate, text (question), answer}]
    initial_description: str = ""


@app.post("/api/submit-requirements")
def submit_requirements(req: SubmitRequirementsRequest):
    """
    Build a conversation string from the user's answers and run the full pipeline.
    Stores the PRD in the database and returns the PRD id.
    """
    try:
        from state_schema import AgentState
        from agents import (TranscriptionAgent, RequirementAnalyzerAgent,
                            AmbiguityDetectionAgent, QuestionGenerationAgent, DocumentationAgent)
        from persona_config import get_persona
        from completion_engine import evaluate
        from prd_generator import PRDGenerator
        from state_manager import save_version
        from database import PRDDatabase
        from decision_engine import make_decisions

        # Build conversation text from answers
        lines = []
        if req.initial_description.strip():
            lines.append(f"Client: {req.initial_description.strip()}")
        for a in req.answers:
            lines.append(f"Interviewer: {a.get('text', a.get('gate', ''))}")
            lines.append(f"Client: {a.get('answer', '').strip()}")
        conversation = "\n".join(lines)

        provider = _auto_provider()
        llm = _build_llm(provider)
        persona = get_persona("PM")

        state = AgentState(project_name=req.project_name, client_name=req.user_name)
        state.persona = persona

        TranscriptionAgent().run_from_text(state, conversation)
        RequirementAnalyzerAgent(llm=llm).run(state)
        AmbiguityDetectionAgent(llm=llm).run(state)
        QuestionGenerationAgent(llm=llm).run(state)
        DocumentationAgent(llm=llm).run(state)

        arch = make_decisions({"raw_text": conversation}).to_dict()
        status = evaluate(state)

        gen = PRDGenerator(llm=None)
        state.prd_markdown = gen.generate(state, persona)

        save_version(state)
        db = PRDDatabase()
        prd_id = db.save(state, user_name=req.user_name)
        db.close()

        # Return the DB row id (last insert)
        db2 = PRDDatabase()
        rows = db2.list_all(user_name=req.user_name)
        db2.close()
        latest_id = rows[0]["id"] if rows else prd_id

        return {
            "success": True,
            "prd_id": latest_id,
            "version": state.version,
            "project_name": state.project_name,
            "prd_markdown": state.prd_markdown,
            "completion": state.completion_status.__dict__,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"PRD generation failed: {e}\n{traceback.format_exc()}")


# ── Admin endpoints ───────────────────────────────────────────────────────────

@app.get("/api/admin/prds")
def admin_list_prds():
    """All PRDs across all users."""
    from database import PRDDatabase
    db = PRDDatabase()
    rows = db.list_all()
    db.close()
    return {"prds": rows}


@app.get("/api/admin/prd/{prd_id}")
def admin_get_prd(prd_id: int):
    from database import PRDDatabase
    db = PRDDatabase()
    prd = db.get_prd_full(prd_id)
    if not prd:
        raise HTTPException(404, f"PRD {prd_id} not found.")
    shares = db.get_shares_for_prd(prd_id)
    thread = db.get_discussion(prd_id)
    db.close()
    return {**prd, "discussion": thread, "shares": shares}


@app.get("/api/admin/users")
def admin_list_users():
    from database import PRDDatabase
    db = PRDDatabase()
    users = db.list_users(role="user")
    db.close()
    return {"users": users}


# ── Discussion (works for both admin and user) ────────────────────────────────

class SendMessageRequest(BaseModel):
    prd_id: int
    sender_name: str
    sender_role: str = "user"
    message: str


@app.post("/api/discussion/send")
def send_discussion_message(req: SendMessageRequest):
    if not req.message.strip():
        raise HTTPException(400, "Message cannot be empty.")
    from database import PRDDatabase
    db = PRDDatabase()
    msg_id = db.add_message(req.prd_id, req.sender_name, req.sender_role, req.message.strip())
    thread = db.get_discussion(req.prd_id)
    db.close()
    return {"success": True, "message_id": msg_id, "thread": thread}


@app.get("/api/discussion/{prd_id}")
def get_discussion(prd_id: int):
    from database import PRDDatabase
    db = PRDDatabase()
    thread = db.get_discussion(prd_id)
    db.close()
    return {"prd_id": prd_id, "thread": thread}


# ── PRD update from discussion (admin action) ─────────────────────────────────

class UpdateFromDiscussionRequest(BaseModel):
    prd_id: int
    admin_name: str
    change_instructions: str   # plain text of what to change


@app.post("/api/admin/update-from-discussion")
def update_prd_from_discussion(req: UpdateFromDiscussionRequest):
    """
    Load existing PRD, merge discussion context, generate updated version.
    Old version is preserved; new version gets a new DB id.
    """
    try:
        from database import PRDDatabase
        from state_schema import AgentState
        from agents import (TranscriptionAgent, RequirementAnalyzerAgent,
                            AmbiguityDetectionAgent, QuestionGenerationAgent, DocumentationAgent)
        from persona_config import get_persona
        from completion_engine import evaluate
        from prd_generator import PRDGenerator
        from state_manager import save_version
        from decision_engine import make_decisions

        db = PRDDatabase()
        original = db.get_prd_full(req.prd_id)
        if not original:
            db.close()
            raise HTTPException(404, "PRD not found.")
        thread = db.get_discussion(req.prd_id)

        # Build an update conversation from discussion + change instructions
        discussion_text = "\n".join(
            f"{m['sender_role'].upper()} ({m['sender_name']}): {m['message']}"
            for m in thread
        )
        merged = (
            f"[ORIGINAL PRD v{original['version']}]\n{original['prd_md'][:2000]}\n\n"
            f"[DISCUSSION]\n{discussion_text}\n\n"
            f"[CHANGE INSTRUCTIONS]\n{req.change_instructions}"
        )

        provider = _auto_provider()
        llm = _build_llm(provider)
        persona = get_persona("PM")

        state = AgentState(
            project_name=original["project_name"],
            client_name=original["user_name"],
            version=original["version"] + 1,
        )
        state.persona = persona

        TranscriptionAgent().run_from_text(state, merged)
        RequirementAnalyzerAgent(llm=llm).run(state)
        DocumentationAgent(llm=llm).run(state)

        evaluate(state)
        gen = PRDGenerator(llm=None)
        state.prd_markdown = (
            f"> **Updated v{state.version}** — based on discussion by {req.admin_name}\n\n"
            + gen.generate(state, persona)
        )

        save_version(state)
        new_id = db.save(state, user_name=original["user_name"])

        # Post an automated discussion message
        db.add_message(req.prd_id, req.admin_name, "admin",
                       f"Updated PRD created (v{state.version}). Changes: {req.change_instructions[:200]}")
        db.close()

        return {
            "success": True,
            "new_prd_id": new_id,
            "new_version": state.version,
            "original_prd_id": req.prd_id,
            "prd_markdown": state.prd_markdown,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"{e}\n{traceback.format_exc()}")


# ── PRD sharing & approval ────────────────────────────────────────────────────

class SharePRDRequest(BaseModel):
    prd_id: int
    user_names: List[str]
    note: str = ""


@app.post("/api/admin/share-prd")
def share_prd(req: SharePRDRequest):
    from database import PRDDatabase
    db = PRDDatabase()
    share_ids = []
    for uname in req.user_names:
        sid = db.share_prd(req.prd_id, uname, req.note)
        share_ids.append({"user_name": uname, "share_id": sid})
    db.close()
    return {"success": True, "shares": share_ids}


@app.get("/api/user/shares/{user_name}")
def user_get_shares(user_name: str):
    from database import PRDDatabase
    db = PRDDatabase()
    shares = db.get_shares_for_user(user_name)
    db.close()
    return {"shares": shares}


class RespondShareRequest(BaseModel):
    share_id: int
    status: str   # "approved" | "changes_requested"
    comment: str = ""


@app.post("/api/user/respond-share")
def respond_to_share(req: RespondShareRequest):
    if req.status not in ("approved", "changes_requested"):
        raise HTTPException(400, "status must be 'approved' or 'changes_requested'.")
    from database import PRDDatabase
    db = PRDDatabase()
    db.respond_to_share(req.share_id, req.status, req.comment)
    db.close()
    return {"success": True}


# ── User PRD list ─────────────────────────────────────────────────────────────

@app.get("/api/user/prds/{user_name}")
def user_prds(user_name: str):
    from database import PRDDatabase
    db = PRDDatabase()
    rows = db.list_all(user_name=user_name)
    db.close()
    return {"prds": rows}


# ── Enhanced Agentic AI Endpoints ─────────────────────────────────────────────

class DocumentUploadResponse(BaseModel):
    session_id: str
    processed_documents: int
    enhanced_patterns: Dict[str, Any]
    status: str

class ConversationStartRequest(BaseModel):
    context: Dict[str, Any] = {}
    stakeholders: List[Dict[str, Any]] = []
    domain: str = "general"

class ConversationStreamRequest(BaseModel):
    session_id: str
    input_text: str = ""
    input_type: str = "text"  # "text", "audio", "answer"
    question_id: str = ""
    answer: str = ""

class ConversationStatusResponse(BaseModel):
    session_id: str
    phase: str
    completeness_scores: Dict[str, float]
    active_gaps: List[Dict[str, Any]]
    next_questions: List[Dict[str, Any]]
    recommendations: List[str]

# Global coordinator instance
_coordinator = None

def get_coordinator():
    global _coordinator
    if _coordinator is None:
        llm_client = _build_llm("groq")  # Use Groq by default
        from agents.coordinator import AgentCoordinator
        _coordinator = AgentCoordinator(llm_client)
    return _coordinator

@app.post("/api/documents/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    """Upload user documents to enhance knowledge base"""
    try:
        coordinator = get_coordinator()
        
        # Process uploaded files
        documents = []
        for file in files:
            content = await file.read()
            # Simple text extraction (in production, would handle different file types)
            try:
                text_content = content.decode('utf-8')
            except UnicodeDecodeError:
                # Skip binary files or handle them appropriately
                continue
            
            documents.append({
                'filename': file.filename,
                'content': text_content
            })
        
        # Process documents
        enhanced_kb = coordinator.agents['document_processor'].process_user_documents(documents)
        
        # Create a session with enhanced knowledge
        session = await coordinator.initialize_conversation(
            context={'source': 'document_upload'},
            documents=documents
        )
        
        return DocumentUploadResponse(
            session_id=session.session_id,
            processed_documents=len(documents),
            enhanced_patterns=enhanced_kb.get_summary(),
            status="success"
        )
        
    except Exception as e:
        raise HTTPException(500, f"Document upload failed: {str(e)}")

@app.post("/api/conversation/start")
async def start_conversation(request: ConversationStartRequest):
    """Initialize conversation with context and stakeholder profiles"""
    try:
        coordinator = get_coordinator()
        
        session = await coordinator.initialize_conversation(
            context=request.context,
            stakeholders=request.stakeholders,
            domain=request.domain
        )
        
        return {
            "session_id": session.session_id,
            "status": "initialized",
            "phase": session.phase.value,
            "stakeholder_profile": session.stakeholder_profile
        }
        
    except Exception as e:
        raise HTTPException(500, f"Conversation initialization failed: {str(e)}")

@app.post("/api/conversation/stream")
async def stream_conversation(request: ConversationStreamRequest):
    """Process streaming conversation input with real-time agent coordination"""
    try:
        coordinator = get_coordinator()
        
        # Simulate input stream (in production, this would handle real streaming)
        input_data = {
            'text': request.input_text,
            'type': request.input_type,
            'question_id': request.question_id,
            'answer': request.answer
        }
        
        # Process conversation
        update = await coordinator.process_conversation_stream(
            session_id=request.session_id,
            input_stream=input_data
        )
        
        return {
            "session_id": update.session_id,
            "timestamp": update.timestamp,
            "phase": update.phase.value,
            "agent_results": update.agent_results,
            "next_questions": [q.to_dict() if hasattr(q, 'to_dict') else q for q in update.next_questions],
            "completeness_scores": update.completeness_scores,
            "flow_decision": update.flow_decision.to_dict() if hasattr(update.flow_decision, 'to_dict') else update.flow_decision,
            "recommendations": update.recommendations,
            "status": "processed"
        }
        
    except Exception as e:
        raise HTTPException(500, f"Conversation processing failed: {str(e)}")

@app.get("/api/conversation/status/{session_id}")
async def get_conversation_status(session_id: str):
    """Get current conversation completeness and agent insights"""
    try:
        coordinator = get_coordinator()
        
        status = coordinator.get_conversation_status(session_id)
        if 'error' in status:
            raise HTTPException(404, status['error'])
        
        active_gaps = coordinator.get_active_ambiguities(session_id)
        next_questions = coordinator.get_next_questions(session_id)
        
        return ConversationStatusResponse(
            session_id=session_id,
            phase=status.get('phase', 'unknown'),
            completeness_scores=status.get('completeness_scores', {}),
            active_gaps=active_gaps,
            next_questions=next_questions,
            recommendations=[]  # Could be enhanced with more recommendations
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Status retrieval failed: {str(e)}")

@app.post("/api/conversation/continuous")
async def continuous_conversation(request: ConversationStreamRequest):
    """Continuous conversation with gap detection and questioning"""
    try:
        coordinator = get_coordinator()
        
        # Get current conversation state
        conversation_state = coordinator.active_sessions.get(request.session_id)
        if not conversation_state:
            raise HTTPException(404, f"Session {request.session_id} not found")
        
        # Add new input to conversation
        if request.answer and request.question_id:
            # This is an answer to a previous question
            conversation_state.answers_received.append({
                'question_id': request.question_id,
                'answer': request.answer,
                'timestamp': time.time()
            })
        elif request.input_text:
            # This is new input text
            # In a full implementation, this would be processed by transcription agent
            pass
        
        # Process through agent coordination
        input_data = {
            'text': request.input_text,
            'answer': request.answer,
            'question_id': request.question_id
        }
        
        update = await coordinator.process_conversation_stream(
            session_id=request.session_id,
            input_stream=input_data
        )
        
        # Determine response based on flow decision
        if update.flow_decision.decision_type.value == "generate_prd":
            # Generate final PRD
            try:
                # Use existing PRD generation logic
                conversation_text = " ".join([ans.get('answer', '') for ans in conversation_state.answers_received])
                
                prd_request = GeneratePRDRequest(
                    conversation=conversation_text,
                    provider="groq",
                    persona="PM",
                    project_name="Generated Project",
                    client_name="Client",
                    domain="General"
                )
                
                # Call existing generate_prd function
                prd_result = generate_prd(prd_request)
                
                return {
                    "status": "complete",
                    "prd": prd_result,
                    "session_id": request.session_id,
                    "final_scores": update.completeness_scores
                }
                
            except Exception as e:
                print(f"PRD generation failed: {e}")
                return {
                    "status": "prd_generation_failed",
                    "error": str(e),
                    "session_id": request.session_id
                }
        else:
            # Continue with questions
            return {
                "status": "needs_clarification",
                "questions": [q.to_dict() if hasattr(q, 'to_dict') else q for q in update.next_questions],
                "completeness_scores": update.completeness_scores,
                "gaps_found": update.agent_results.get('gap_analysis', {}).get('gaps', []),
                "recommendations": update.recommendations,
                "session_id": request.session_id,
                "phase": update.phase.value
            }
        
    except HTTPException:
        raise
    except Exception as e:
        import time
        raise HTTPException(500, f"Continuous conversation failed: {str(e)}")

@app.get("/api/ambiguities/active/{session_id}")
async def get_active_ambiguities(session_id: str):
    """Get current unresolved ambiguities for a session"""
    try:
        coordinator = get_coordinator()
        ambiguities = coordinator.get_active_ambiguities(session_id)
        
        return {
            "session_id": session_id,
            "active_ambiguities": ambiguities,
            "count": len(ambiguities)
        }
        
    except Exception as e:
        raise HTTPException(500, f"Ambiguity retrieval failed: {str(e)}")

@app.post("/api/questions/adaptive")
async def get_adaptive_questions(request: ConversationStreamRequest):
    """Get next adaptive question based on current context"""
    try:
        coordinator = get_coordinator()
        
        # Get conversation state
        conversation_state = coordinator.active_sessions.get(request.session_id)
        if not conversation_state:
            raise HTTPException(404, f"Session {request.session_id} not found")
        
        # Get next questions
        next_questions = coordinator.get_next_questions(request.session_id)
        
        return {
            "session_id": request.session_id,
            "questions": next_questions,
            "question_count": len(next_questions),
            "phase": conversation_state.phase.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Adaptive question generation failed: {str(e)}")

@app.get("/api/requirements/trace/{session_id}")
async def get_traceability_matrix(session_id: str):
    """Get traceability matrix linking requirements to conversation sources"""
    try:
        coordinator = get_coordinator()
        
        conversation_state = coordinator.active_sessions.get(session_id)
        if not conversation_state:
            raise HTTPException(404, f"Session {session_id} not found")
        
        # Build traceability matrix
        traceability = []
        for i, req in enumerate(conversation_state.requirements_discovered):
            trace_entry = {
                "requirement_id": req.get('id', f"req_{i+1}"),
                "requirement_text": req.get('description', ''),
                "source_questions": [],
                "source_answers": [],
                "confidence_score": 0.8  # Placeholder
            }
            
            # Link to related questions and answers
            for j, question in enumerate(conversation_state.questions_asked):
                if hasattr(question, 'linked_gaps') and question.linked_gaps:
                    trace_entry["source_questions"].append({
                        "question_id": question.id if hasattr(question, 'id') else f"q_{j+1}",
                        "question_text": question.text if hasattr(question, 'text') else str(question)
                    })
            
            for answer in conversation_state.answers_received:
                if answer.get('question_id') in [q.get('question_id', '') for q in trace_entry["source_questions"]]:
                    trace_entry["source_answers"].append(answer)
            
            traceability.append(trace_entry)
        
        return {
            "session_id": session_id,
            "traceability_matrix": traceability,
            "total_requirements": len(traceability)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Traceability matrix generation failed: {str(e)}")


# ── Dynamic Interview API (no fixed question limit) ──────────────────────

_interview_sessions: Dict[str, Dict[str, Any]] = {}

# Patterns that signal the user doesn't know / wants to skip
_NO_IDEA_PATTERNS = [
    "i don't know", "i do not know", "don't know", "no idea", "not sure",
    "i'm not sure", "i am not sure", "no clue", "idk", "not applicable",
    "n/a", "na", "skip", "pass", "later", "tbd", "to be decided",
    "haven't thought", "have not thought", "we'll decide", "will decide",
    "unsure", "unclear", "don't have", "cant say", "can't say",
    "no preference", "no requirement", "dont know", "dono", "dunno",
]

# Fallback questions if LLM fails (keyed by focus area)
_FALLBACK_Q_MAP: Dict[str, str] = {
    "features":          "What are the core features this product must have at launch?",
    "features_detail":   "Walk me through a typical user journey — what steps does the user go through?",
    "roles":             "Who are the different types of users, and what is each allowed to do?",
    "users_roles":       "What permissions should each user role have in the system?",
    "performance":       "How fast should the system respond, and how many users need to be supported simultaneously?",
    "security":          "How should users log in, and what data needs to be kept secure?",
    "scalability":       "What is your expected user base in year 1 and year 3?",
    "scale":             "What is the expected transaction or data volume per day?",
    "integrations":      "Does this need to connect with any external services, payment gateways, or APIs?",
    "data_model":        "What are the main pieces of data the system needs to store and manage?",
    "billing":           "How will customers pay, and what pricing model will you use?",
    "timeline":          "When do you need this delivered, and what are the must-have features for the first release?",
    "platform":          "Should this be a web app, mobile app, or both?",
    "project_identity":  "What is the project called and what is its single most important goal?",
    "edge_cases":        "Are there any unusual situations or error cases the system must handle gracefully?",
    "ui_ux":             "Do you have any design preferences, branding guidelines, or example apps you like?",
    "reporting":         "What reports or dashboards do stakeholders need to see?",
    "compliance":        "Are there any legal, regulatory, or industry standards the product must comply with?",
    "deployment":        "Where will this be hosted — cloud (AWS/Azure/GCP), on-premise, or does it not matter?",
    "general":           "What other important details about this product haven't we covered yet?",
}

# Generic extras when domain gates are exhausted
_GENERIC_GAP_QS = [
    "Are there any edge cases or unusual scenarios the system must handle?",
    "What business rules or constraints does the system need to enforce?",
    "Do you have any UI/UX preferences or design guidelines?",
    "What reporting or analytics do stakeholders need?",
    "Are there compliance or regulatory requirements (GDPR, HIPAA, etc.)?",
    "How should the system handle errors and notify users?",
    "Is there a disaster recovery or data backup strategy needed?",
    "What is the expected data retention policy?",
]


class InterviewStartRequest(BaseModel):
    description: str
    doc_knowledge: str = ""


class InterviewAnswerRequest(BaseModel):
    session_id: str
    answer: str


class InterviewGenerateRequest(BaseModel):
    session_id: str


# ── Tech-level signals ────────────────────────────────────────────────────────

_TECH_KEYWORDS = [
    "api", "rest", "graphql", "sql", "nosql", "mongodb", "postgres", "mysql",
    "redis", "kafka", "docker", "kubernetes", "aws", "azure", "gcp", "s3",
    "microservice", "monolith", "react", "angular", "vue", "node", "python",
    "django", "fastapi", "flask", "typescript", "java", "springboot",
    "authentication", "oauth", "jwt", "ssl", "tls", "cdn", "load balancer",
    "cache", "sharding", "replication", "webhook", "websocket", "grpc",
    "ci/cd", "devops", "terraform", "ansible", "lambda", "serverless",
    "firebase", "supabase", "prisma", "orm", "http", "https", "endpoint",
]

# Patterns where user is asking for a recommendation / doesn't know tech choice
import re as _global_re
_RECOMMENDATION_PATTERNS = [
    r"should (i|we|it) use\b",
    r"which (is|would be|one is) better\b",
    r"what do you recommend",
    r"not sure (which|what|whether|if)\b",
    r"\bsql or no.?sql\b",
    r"\bno.?sql or sql\b",
    r"\b(mongo|postgres|mysql|firebase|supabase)\b.*\b(or|vs|versus)\b",
    r"\b(or|vs|versus)\b.*\b(mongo|postgres|mysql|firebase|supabase)\b",
    r"which (database|db|framework|language|technology|stack|cloud|hosting)\b",
    r"\b(aws|azure|gcp)\b.*\b(or|vs)\b",
    r"\b(or|vs)\b.*\b(aws|azure|gcp)\b",
    r"react or angular|angular or react|vue or react|react or vue",
    r"rest or graphql|graphql or rest",
    r"(microservices?|monolith|serverless)\b",
    r"should (it|this) be (a|an)?\s*(mobile|web|desktop|native|hybrid)\b",
    r"(relational|document|graph|key.value) (db|database)\b",
    r"what (kind|type) of (database|server|cloud|storage|architecture)\b",
    r"need (a )?(recommendation|suggestion|advice)\b",
    r"(i )?don.t know (which|what) (to use|is better|database|framework|technology)",
    r"(not sure|unsure) (about|which|what) (database|framework|technology|platform|stack)",
]


def _estimate_tech_level(text: str) -> int:
    """
    Heuristic tech-level score 1-10 (fast, no LLM needed).
    1-3 = non-technical, 4-6 = semi-technical, 7-10 = technical.
    """
    t = text.lower()
    hits = sum(1 for kw in _TECH_KEYWORDS if kw in t)
    if hits == 0:
        return 2
    if hits == 1:
        return 4
    if hits <= 3:
        return 6
    if hits <= 5:
        return 8
    return 10


def _needs_recommendation(text: str) -> bool:
    """Return True when user is asking for a tech recommendation or seems confused about a choice."""
    t = text.lower()
    for pat in _RECOMMENDATION_PATTERNS:
        if _global_re.search(pat, t):
            return True
    return False


def _make_tech_recommendation(
    llm, question: str, answer: str,
    description: str, domain_label: str,
) -> Optional[Dict[str, str]]:
    """
    Uses Groq to produce a concrete technology/architecture recommendation
    when the user doesn't know which option to pick.
    Returns: {title, recommendation, rationale, category} or None on failure.
    """
    user_prompt = (
        f"Product: {description[:400]}\n"
        f"Domain: {domain_label}\n"
        f"Question asked: {question}\n"
        f"User response (shows uncertainty): {answer}\n\n"
        "The user is unsure about a technical choice. "
        "Give a concrete recommendation for their specific product. "
        "Return ONLY this JSON object (no markdown, no explanation):\n"
        "{\"title\":\"Database Choice\","
        "\"recommendation\":\"Use PostgreSQL, a relational database.\","
        "\"rationale\":\"It suits your structured menu and order data perfectly.\","
        "\"category\":\"database\"}"
    )
    try:
        raw = llm.generate_text(
            system_prompt=(
                "You are a senior software architect. When a user is unsure about a technical "
                "choice, recommend the best option for their specific product. Use plain language. "
                "Return ONLY a JSON object with keys: title, recommendation, rationale, category."
            ),
            user_prompt=user_prompt,
        ).strip()
        # Strip markdown fences
        raw = _global_re.sub(r'^```[a-z]*\n?', '', raw)
        raw = _global_re.sub(r'\n?```$', '', raw).strip()
        obj_m = _global_re.search(r'\{[^{}]+\}', raw, _global_re.DOTALL)
        data = json.loads(obj_m.group() if obj_m else raw)
        rec = str(data.get("recommendation", "")).strip()
        if rec:
            return {
                "title":          str(data.get("title", "Technical Recommendation")),
                "recommendation": rec,
                "rationale":      str(data.get("rationale", "")),
                "category":       str(data.get("category", "other")),
            }
    except Exception as e:
        print(f"[Recommendation] LLM failed: {e}")
    return None


# ── Answer quality gate ───────────────────────────────────────────────────────

def _classify_answer(text: str) -> str:
    """
    AND/OR gate — classify the user's raw answer.
    Returns: 'useful' | 'partial' | 'no_idea' | 'skip'
    """
    t = text.strip().lower()
    if len(t) <= 2:
        return "skip"
    for pat in _NO_IDEA_PATTERNS:
        if pat in t:
            return "no_idea"
    if len(t) < 15:
        return "partial"
    return "useful"


def _rephrase_question(llm, original_question: str, description: str,
                        focus_area: str, domain_label: str) -> str:
    """
    OR-gate: user said they don't know — rephrase the question more simply
    with a concrete example hint drawn from the product description.
    """
    try:
        raw = llm.generate_text(
            system_prompt=(
                "You are a friendly product requirements coach helping a non-technical founder. "
                "Rephrase the given question in simpler, more concrete terms. "
                "Give a short illustrative example relevant to their specific product. "
                "Keep it to 2-3 sentences. Do not use jargon. "
                "Return ONLY the rephrased question text, nothing else."
            ),
            user_prompt=(
                f"Product: {description[:300]}\n"
                f"Domain: {domain_label}\n"
                f"Topic: {focus_area}\n"
                f"Original question: {original_question}\n\n"
                "Rephrase this question more simply with a product-specific example hint:"
            ),
        ).strip()
        if raw and len(raw) > 20:
            return raw
    except Exception:
        pass
    # fallback: just prepend a helpful hint
    return (
        f"No worries — let me rephrase. For a product like yours, {focus_area} means: "
        f"{_FALLBACK_Q_MAP.get(focus_area, original_question)} "
        f"(Even a rough idea or a similar product you've seen works!)"
    )


# ── Core LLM question engine ──────────────────────────────────────────────────

def _interview_llm_question(
    llm, description: str, answers: List[Dict],
    domain: str, domain_label: str, doc_knowledge: str = "",
    tbd_areas: Optional[List[str]] = None,
    questions_asked: Optional[List[str]] = None,
    tech_level: int = 3,
) -> Dict[str, Any]:
    """
    Analyze the conversation, identify the most critical uncovered gap,
    and return the next contextual question.

    Anti-repetition: passes the full list of asked questions to the LLM.
    Context-driven: grounds questions in the specific product description.
    Tech-adaptive: tunes question language to user's detected technical level.
    """
    import re as _re

    tbd_areas = tbd_areas or []
    questions_asked = questions_asked or []

    # Build conversation history
    conv_parts: List[str] = [f"PRODUCT DESCRIPTION:\n{description}\n\nDomain: {domain_label}"]
    for i, a in enumerate(answers, 1):
        quality_note = " [USER SAID: UNKNOWN — marked TBD]" if a.get("is_tbd") else ""
        rec_note = f" [AI RECOMMENDED: {a['recommendation']['title']}]" if a.get("recommendation") else ""
        conv_parts.append(
            f"Q{i}: {a['question']}\n"
            f"A{i}: {a['answer']}{quality_note}{rec_note}"
        )
    conv_text = "\n\n".join(conv_parts)

    ref = _load_ref()
    prd_data = ref.get("prd_types", {}).get(domain, {})
    required_gates = prd_data.get("required_gates", [])
    doc_ctx = f"\nREFERENCE DOCUMENTS (use as context):\n{doc_knowledge[:2000]}" if doc_knowledge else ""

    # Build explicit forbidden list to prevent repeats
    forbidden = "\n".join(f"  - {q}" for q in questions_asked[-20:]) if questions_asked else "  (none yet)"
    tbd_note = (
        f"\nAREAS MARKED TBD (user couldn't answer — skip these, note them as TBD in PRD):\n"
        + "\n".join(f"  - {a}" for a in tbd_areas)
    ) if tbd_areas else ""

    # Adapt tone to technical level
    if tech_level <= 3:
        tone_instruction = (
            "USER IS NON-TECHNICAL: Use plain English, avoid all jargon. "
            "Frame questions in business/product terms (e.g. 'how should customers log in?' not 'what auth mechanism?'). "
            "Give concrete examples from everyday apps."
        )
    elif tech_level <= 6:
        tone_instruction = (
            "USER IS SEMI-TECHNICAL: Use simple technical terms but explain where needed. "
            "You can mention common options (e.g. 'web or mobile app?') but don't require deep tech knowledge."
        )
    else:
        tone_instruction = (
            "USER IS TECHNICAL: You can use technical terminology freely. "
            "Ask specific technical questions about architecture, performance targets, tech stack, APIs, etc."
        )

    system_prompt = (
        "You are a senior requirements analyst conducting a gap-driven interview. "
        "Your goal: identify what information is MISSING for a complete PRD and ask ONE focused question. "
        "Base every question on the specific product described — never ask generic questions. "
        f"{tone_instruction} "
        "NEVER repeat or paraphrase a question that has already been asked."
    )

    user_prompt = f"""Analyze this requirements conversation and return ONLY valid JSON.

{conv_text}

DOMAIN AREAS TO COVER: {json.dumps(required_gates)}
{doc_ctx}
{tbd_note}

QUESTIONS ALREADY ASKED (DO NOT repeat or rephrase any of these):
{forbidden}

PRD COMPLETENESS AREAS:
- Core features & user workflows
- User roles & permissions
- Non-functional requirements (performance, security, scalability)
- Integrations & third-party services
- Data model & entities
- Business rules & constraints
- Timeline & release priorities
- Edge cases & error handling
- UI/UX preferences
- Deployment & infrastructure
- Compliance & regulations

INSTRUCTIONS:
1. Deeply read the product description to understand the SPECIFIC domain and use-case.
2. Identify the single MOST CRITICAL gap not yet answered and not in the TBD list.
3. Frame the question specifically for THIS product (e.g. for a restaurant app say "How should customers browse the menu?" not "What are the features?").
4. If completeness >= 85 and all critical areas are covered, set ready_for_prd to true.

Respond with ONLY this JSON (no markdown, no explanation):
{{
  "completeness": <integer 0-100 reflecting how complete the requirements are>,
  "areas_covered": ["list of areas that have enough info"],
  "areas_missing": ["list of areas still needing info, excluding TBD areas"],
  "ready_for_prd": <true only if completeness >= 85>,
  "next_question": "<one highly specific, product-grounded question targeting the biggest gap, or empty string if ready>",
  "focus_area": "<snake_case label for the area this question targets>"
}}"""

    try:
        raw = llm.generate_text(system_prompt=system_prompt, user_prompt=user_prompt)
        json_match = _re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw, _re.DOTALL)
        data = json.loads(json_match.group() if json_match else raw)

        next_q = str(data.get("next_question", "")).strip()
        focus = str(data.get("focus_area", "general")).strip() or "general"

        # Safety: if LLM returned a repeated question, fall back
        if next_q and any(
            next_q.lower()[:60] == q.lower()[:60] for q in questions_asked
        ):
            next_q = ""  # will trigger fallback below

        return {
            "completeness":   min(max(int(data.get("completeness", 30)), 0), 100),
            "areas_covered":  list(data.get("areas_covered", [])),
            "areas_missing":  list(data.get("areas_missing", [])),
            "ready_for_prd":  bool(data.get("ready_for_prd", False)) or not next_q,
            "next_question":  next_q,
            "focus_area":     focus,
        }
    except Exception as exc:
        print(f"[LLM Question] parse failed: {exc} — using fallback")
        return _interview_fallback(answers, required_gates, questions_asked, tbd_areas)


def _interview_fallback(
    answers: List[Dict], required_gates: List[str],
    questions_asked: Optional[List[str]] = None,
    tbd_areas: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Rule-based fallback when LLM fails. Avoids repetition via questions_asked set."""
    questions_asked = questions_asked or []
    tbd_areas = tbd_areas or []
    covered_areas = {a.get("focus_area", "") for a in answers}

    asked_lower = {q.lower()[:60] for q in questions_asked}

    def _not_repeated(q: str) -> bool:
        return q.lower()[:60] not in asked_lower

    for gate in required_gates:
        if gate in covered_areas or gate in tbd_areas:
            continue
        q = _FALLBACK_Q_MAP.get(gate, f"Can you describe the {gate.replace('_', ' ')} requirements?")
        if _not_repeated(q):
            return {
                "completeness":  min(max(15, len(answers) * 8), 80),
                "areas_covered": list(covered_areas),
                "areas_missing": [g for g in required_gates if g not in covered_areas and g not in tbd_areas],
                "ready_for_prd": False,
                "next_question": q,
                "focus_area":    gate,
            }

    # Domain gates done — try generic questions
    for gq in _GENERIC_GAP_QS:
        if _not_repeated(gq):
            idx = _GENERIC_GAP_QS.index(gq)
            return {
                "completeness":  min(75 + idx * 4, 95),
                "areas_covered": list(covered_areas),
                "areas_missing": [],
                "ready_for_prd": False,
                "next_question": gq,
                "focus_area":    "general",
            }

    return {
        "completeness":  90,
        "areas_covered": list(covered_areas),
        "areas_missing": [],
        "ready_for_prd": True,
        "next_question": "",
        "focus_area":    "",
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/api/interview/start")
def interview_start(req: InterviewStartRequest):
    import uuid
    ref = _load_ref()
    domain, prd_data = _detect_domain(req.description, ref)
    label = prd_data.get("label", "General Software") if prd_data else "General Software"

    # Estimate initial tech level from the description itself
    init_tech = _estimate_tech_level(req.description)

    session_id = str(uuid.uuid4())
    session: Dict[str, Any] = {
        "description":      req.description,
        "domain":           domain,
        "domain_label":     label,
        "doc_knowledge":    req.doc_knowledge,
        "answers":          [],
        "completeness":     0,
        "current_question": "",
        "current_focus":    "",
        "questions_asked":  [],
        "tbd_areas":        [],
        "rephrase_count":   {},
        "tech_level":       init_tech,       # 1-10, updated each round
        "tech_level_label": "non-technical" if init_tech <= 3 else ("semi-technical" if init_tech <= 6 else "technical"),
        "recommendations":  [],              # AI-generated tech recommendations
    }

    try:
        llm = _build_llm(_auto_provider())
        result = _interview_llm_question(
            llm, req.description, [], domain, label, req.doc_knowledge,
            tbd_areas=[], questions_asked=[], tech_level=init_tech)
    except Exception:
        gates = prd_data.get("required_gates", []) if prd_data else []
        result = _interview_fallback([], gates)

    first_q = result.get("next_question") or \
        "What are the core features and user workflows for your product?"
    session["current_question"] = first_q
    session["current_focus"]    = result.get("focus_area", "features")
    session["completeness"]     = result.get("completeness", 10)
    session["questions_asked"].append(first_q)
    _interview_sessions[session_id] = session

    return {
        "session_id":       session_id,
        "first_question":   first_q,
        "focus_area":       result.get("focus_area", "features"),
        "completeness":     result.get("completeness", 10),
        "domain_label":     label,
        "areas_covered":    result.get("areas_covered", []),
        "areas_missing":    result.get("areas_missing", []),
        "tech_level":       init_tech,
        "tech_level_label": session["tech_level_label"],
    }


@app.post("/api/interview/answer")
def interview_answer(req: InterviewAnswerRequest):
    session = _interview_sessions.get(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found. Please start a new interview.")

    raw_answer    = req.answer.strip()
    current_q     = session["current_question"]
    current_focus = session["current_focus"]
    quality       = _classify_answer(raw_answer)

    # ── Update running tech level (exponential moving average) ───────────────
    new_tech = _estimate_tech_level(raw_answer)
    old_tech = session.get("tech_level", 3)
    session["tech_level"] = round(old_tech * 0.6 + new_tech * 0.4)
    session["tech_level_label"] = (
        "non-technical" if session["tech_level"] <= 3
        else ("semi-technical" if session["tech_level"] <= 6 else "technical")
    )

    # ── AND / OR GATE ─────────────────────────────────────────────────────────
    if quality in ("no_idea", "skip"):
        rephrase_count = session["rephrase_count"].get(current_focus, 0)

        if rephrase_count == 0:
            session["rephrase_count"][current_focus] = 1
            try:
                llm = _build_llm(_auto_provider())
                rephrased = _rephrase_question(
                    llm, current_q, session["description"],
                    current_focus, session["domain_label"])
            except Exception:
                rephrased = (
                    f"No problem! To put it another way — {_FALLBACK_Q_MAP.get(current_focus, current_q)} "
                    "(Even a rough answer or 'not needed' helps!)"
                )
            session["current_question"] = rephrased
            session["questions_asked"].append(rephrased)
            return {
                "completeness":    session["completeness"],
                "areas_covered":   [],
                "areas_missing":   session.get("tbd_areas", []),
                "ready_for_prd":   False,
                "next_question":   rephrased,
                "focus_area":      current_focus,
                "rephrased":       True,
                "tech_level":      session["tech_level"],
                "tech_level_label": session["tech_level_label"],
            }

        tbd_note = f"[TBD] {current_focus.replace('_', ' ').title()} — not specified by client"
        session["answers"].append({
            "question":       current_q,
            "answer":         tbd_note,
            "focus_area":     current_focus,
            "is_tbd":         True,
            "answer_quality": "no_idea",
            "recommendation": None,
        })
        if current_focus not in session["tbd_areas"]:
            session["tbd_areas"].append(current_focus)
    else:
        # Good / partial answer — check if user needs a recommendation
        recommendation = None
        if _needs_recommendation(raw_answer):
            try:
                llm_rec = _build_llm(_auto_provider())
                recommendation = _make_tech_recommendation(
                    llm_rec, current_q, raw_answer,
                    session["description"], session["domain_label"])
                if recommendation:
                    session["recommendations"].append({
                        **recommendation,
                        "question": current_q,
                        "focus_area": current_focus,
                    })
            except Exception as e:
                print(f"[interview_answer] recommendation failed: {e}")

        session["answers"].append({
            "question":       current_q,
            "answer":         raw_answer,
            "focus_area":     current_focus,
            "is_tbd":         False,
            "answer_quality": quality,
            "recommendation": recommendation,
        })
        session["rephrase_count"].pop(current_focus, None)

    # ── Safety cap ────────────────────────────────────────────────────────────
    if len(session["answers"]) >= 30:
        return {
            "next_question": "", "completeness": 95, "ready_for_prd": True,
            "areas_covered": [], "areas_missing": [], "focus_area": "",
            "tech_level": session["tech_level"],
            "tech_level_label": session["tech_level_label"],
        }

    # ── Generate next contextual question ─────────────────────────────────────
    try:
        llm = _build_llm(_auto_provider())
        result = _interview_llm_question(
            llm, session["description"], session["answers"],
            session["domain"], session["domain_label"], session["doc_knowledge"],
            tbd_areas=session["tbd_areas"],
            questions_asked=session["questions_asked"],
            tech_level=session["tech_level"],
        )
    except Exception:
        ref = _load_ref()
        pd  = ref.get("prd_types", {}).get(session["domain"], {})
        result = _interview_fallback(
            session["answers"], pd.get("required_gates", []),
            questions_asked=session["questions_asked"],
            tbd_areas=session["tbd_areas"],
        )

    next_q = result.get("next_question", "")
    session["completeness"]     = result["completeness"]
    session["current_question"] = next_q
    session["current_focus"]    = result.get("focus_area", "general")
    if next_q:
        session["questions_asked"].append(next_q)

    result["tbd_areas"]         = session["tbd_areas"]
    result["tech_level"]        = session["tech_level"]
    result["tech_level_label"]  = session["tech_level_label"]
    # Return the latest recommendation if one was just made
    result["recommendation"]    = session["answers"][-1].get("recommendation") if session["answers"] else None
    return result


@app.post("/api/interview/generate")
def interview_generate(req: InterviewGenerateRequest):
    session = _interview_sessions.get(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found.")

    import re as _re

    # Build conversation transcript
    lines = [f"Client: {session['description']}"]
    for a in session["answers"]:
        lines.append(f"Interviewer: {a['question']}")
        lines.append(f"Client: {a['answer']}")
    if session.get("doc_knowledge"):
        lines.append(f"\n[Reference Documents]\n{session['doc_knowledge'][:3000]}")
    conversation = "\n".join(lines)

    # Extract a concise project name from description
    raw_desc = session["description"]
    m = _re.search(
        r'\b(?:build|create|develop|launch|make)\s+(?:a|an\s+)?([\w\s\-]{3,30}?)(?:\s+(?:for|where|that|which|so|with|to)\b|[,.!?\n]|$)',
        raw_desc, _re.I)
    if m:
        project_name = m.group(1).strip().title()
    else:
        # fallback: first 4 meaningful words
        words = [w for w in raw_desc.split() if len(w) > 2][:4]
        project_name = " ".join(words).title() or "My Project"

    tbd_areas: List[str] = session.get("tbd_areas", [])
    recommendations: List[Dict] = session.get("recommendations", [])
    tech_level: int = session.get("tech_level", 3)
    tech_level_label: str = session.get("tech_level_label", "non-technical")

    try:
        from state_schema import AgentState
        from agents import (TranscriptionAgent, RequirementAnalyzerAgent,
                            AmbiguityDetectionAgent, QuestionGenerationAgent,
                            DocumentationAgent)
        from persona_config import get_persona
        from completion_engine import evaluate
        from prd_generator import PRDGenerator
        from state_manager import save_version
        from database import PRDDatabase
        from decision_engine import make_decisions

        llm    = _build_llm(_auto_provider())
        persona = get_persona("PM")

        state = AgentState(project_name=project_name, client_name="User",
                           domain=session["domain_label"])
        state.persona = persona

        # Run each agent with independent error isolation
        try:
            TranscriptionAgent().run_from_text(state, conversation)
        except Exception as e:
            print(f"[Generate] TranscriptionAgent failed: {e} — using raw text")
            state.raw_input = conversation

        try:
            RequirementAnalyzerAgent(llm=llm).run(state)
        except Exception as e:
            print(f"[Generate] RequirementAnalyzerAgent failed: {e} — using mock")
            RequirementAnalyzerAgent(llm=None).run(state)

        try:
            AmbiguityDetectionAgent(llm=llm).run(state)
        except Exception as e:
            print(f"[Generate] AmbiguityDetectionAgent failed: {e} — using mock")
            AmbiguityDetectionAgent(llm=None).run(state)

        try:
            QuestionGenerationAgent(llm=llm).run(state)
        except Exception as e:
            print(f"[Generate] QuestionGenerationAgent failed: {e} — using mock")
            QuestionGenerationAgent(llm=None).run(state)

        try:
            DocumentationAgent(llm=llm).run(state)
        except Exception as e:
            print(f"[Generate] DocumentationAgent failed: {e}")

        try:
            arch = make_decisions({"raw_text": conversation}).to_dict()
        except Exception:
            arch = {}

        try:
            evaluate(state)
        except Exception:
            pass

        gen = PRDGenerator(llm=None)
        state.prd_markdown = gen.generate(state, persona)

        # ── Append AI Recommendations section ────────────────────────────────
        if recommendations:
            rec_lines = [
                "\n\n---\n## 💡 AI Architecture & Technology Recommendations\n",
                f"> *These recommendations were generated based on the product context.*"
                f" *Client tech level: **{tech_level_label}** (score {tech_level}/10)*\n",
            ]
            by_cat: Dict[str, List] = {}
            for r in recommendations:
                cat = r.get("category", "other").replace("_", " ").title()
                by_cat.setdefault(cat, []).append(r)
            for cat, recs in by_cat.items():
                rec_lines.append(f"\n### {cat}")
                for r in recs:
                    rec_lines.append(f"\n**{r.get('title','Recommendation')}**")
                    rec_lines.append(f"- **Recommended**: {r.get('recommendation','')}")
                    rec_lines.append(f"- **Rationale**: {r.get('rationale','')}")
            state.prd_markdown += "\n".join(rec_lines)

        # ── Append TBD section if any areas were unknown ──────────────────────
        if tbd_areas:
            tbd_lines = [
                "\n\n---\n## ⚠ Areas Requiring Client Clarification (TBD)\n",
                "The following areas were not specified during the interview. "
                "They must be defined before development begins:\n",
            ]
            for i, area in enumerate(tbd_areas, 1):
                label = area.replace("_", " ").title()
                tbd_lines.append(
                    f"- **TBD-{i:02d} — {label}**: Client was unable to provide details. "
                    "Please schedule a follow-up to define this requirement."
                )
            state.prd_markdown += "\n".join(tbd_lines)

        try:
            save_version(state)
            db = PRDDatabase()
            db.save(state, user_name="User")
            db.close()
        except Exception as e:
            print(f"[Generate] DB save failed: {e}")

        _interview_sessions.pop(req.session_id, None)

        return {
            "success":       True,
            "project_name":  state.project_name,
            "prd_markdown":  state.prd_markdown,
            "functional":    state.functional,
            "non_functional": state.non_functional,
            "constraints":   state.constraints_list,
            "assumptions":   state.assumptions_list,
            "gaps":          [g.__dict__ for g in state.gaps] if state.gaps else [],
            "follow_up":     state.follow_up_questions,
            "tbd_areas":        tbd_areas,
            "recommendations":  recommendations,
            "tech_level":       tech_level,
            "tech_level_label": tech_level_label,
            "completion":       (state.completion_status.__dict__
                                 if hasattr(state.completion_status, "__dict__") else {}),
        }
    except Exception as e:
        raise HTTPException(500,
                            f"PRD generation failed: {e}\n{traceback.format_exc()}")


@app.post("/api/interview/transcribe")
async def interview_transcribe(file: UploadFile = File(...)):
    try:
        import io
        import speech_recognition as sr

        audio_bytes = await file.read()
        recognizer = sr.Recognizer()
        transcript = ""

        for attempt_convert in [False, True]:
            try:
                if attempt_convert:
                    from pydub import AudioSegment
                    seg = AudioSegment.from_file(io.BytesIO(audio_bytes))
                    buf = io.BytesIO()
                    seg.export(buf, format="wav")
                    buf.seek(0)
                    raw = buf.read()
                else:
                    raw = audio_bytes

                with sr.AudioFile(io.BytesIO(raw)) as source:
                    audio_data = recognizer.record(source)
                transcript = recognizer.recognize_google(audio_data)
                break
            except Exception:
                if attempt_convert:
                    return {"success": False, "transcript": "",
                            "error": "Could not transcribe audio."}
                continue

        return {"success": True, "transcript": transcript}
    except ImportError:
        raise HTTPException(
            500, "speech_recognition not installed. Run: pip install SpeechRecognition")
    except Exception as e:
        raise HTTPException(500, f"Transcription failed: {e}")


# ── Serve built React app ─────────────────────────────────────────────────────

_dist = Path(__file__).resolve().parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="assets")

    @app.get("/")
    def _root():
        return FileResponse(str(_dist / "index.html"))

    @app.get("/{full_path:path}")
    def _spa(full_path: str):
        f = _dist / full_path
        return FileResponse(str(f) if f.exists() else str(_dist / "index.html"))
