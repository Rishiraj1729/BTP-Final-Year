"""
Requirements Engine - Streamlit Frontend
Runs the full agentic pipeline in-process.
Questions are dynamic and gap-driven -- no fixed limit.
"""

import sys, os, json, re, io, time
from pathlib import Path
from typing import List, Dict, Any, Optional

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import streamlit as st

st.set_page_config(page_title="Requirements Engine", layout="wide")

# ── LLM client (cached) ─────────────────────────────────────────────────────

@st.cache_resource
def get_llm():
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return None
    from groq import Groq
    client = Groq(api_key=api_key)
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    fallbacks = ["llama-3.1-8b-instant", "llama3-8b-8192"]

    class _G:
        _is_mock = False
        def generate_text(self, sp="", up="", system_prompt="", user_prompt=""):
            sp = system_prompt or sp
            up = user_prompt or up
            for m in list(dict.fromkeys([model] + fallbacks)):
                try:
                    r = client.chat.completions.create(
                        model=m, temperature=0.3,
                        messages=[{"role": "system", "content": sp},
                                  {"role": "user",   "content": up}],
                    )
                    return (r.choices[0].message.content or "").strip()
                except Exception as e:
                    if "decommissioned" not in str(e).lower():
                        raise
            raise RuntimeError("All Groq models failed")
    return _G()

# ── Audio transcription ──────────────────────────────────────────────────────

def transcribe_audio(audio_bytes: bytes) -> str:
    import speech_recognition as sr
    recognizer = sr.Recognizer()
    audio_file = io.BytesIO(audio_bytes)
    with sr.AudioFile(audio_file) as source:
        audio_data = recognizer.record(source)
    try:
        return recognizer.recognize_google(audio_data)
    except sr.UnknownValueError:
        return ""
    except sr.RequestError:
        return ""


def transcribe_audio_wav(audio_bytes: bytes) -> str:
    try:
        return transcribe_audio(audio_bytes)
    except Exception:
        try:
            from pydub import AudioSegment
            audio_seg = AudioSegment.from_file(io.BytesIO(audio_bytes))
            wav_buf = io.BytesIO()
            audio_seg.export(wav_buf, format="wav")
            wav_buf.seek(0)
            return transcribe_audio(wav_buf.read())
        except Exception:
            return ""

# ── Master reference helpers ─────────────────────────────────────────────────

@st.cache_data
def load_ref():
    with open(ROOT / "master_reference.json", "r", encoding="utf-8") as f:
        return json.load(f)

def detect_domain(description: str, ref: dict):
    if not description:
        return "general", None
    dl = description.lower()
    for ptype, data in ref.get("prd_types", {}).items():
        for kw in data.get("keywords", []):
            if kw.lower() in dl:
                return ptype, data
    return "general", None

def _extract_project_name(desc: str) -> str:
    m = re.search(r'\b(build|create|develop|launch|make)\s+(?:a|an)?\s*([^,.!?]{3,30})', desc, re.I)
    return m.group(2).strip() if m else "My Project"

# ── Dynamic question generation (LLM-driven) ────────────────────────────────

_FALLBACK_GATE_QUESTIONS = {
    "features": "What are the core features your product must have at launch?",
    "features_detail": "Can you describe the main features and user workflows in detail?",
    "roles": "What types of users will use the system, and what can each type do?",
    "users_roles": "Who are the different user roles, and what permissions does each have?",
    "performance": "What are your performance expectations (response time, concurrent users)?",
    "security": "What security requirements are important (authentication, data encryption, compliance)?",
    "scalability": "How many users do you expect initially, and how should the system scale?",
    "scale": "What scale do you anticipate (users, data volume, transactions per day)?",
    "integrations": "Does this need to integrate with any existing systems or third-party services?",
    "data_model": "What are the key data entities and how do they relate to each other?",
    "billing": "How will billing and payments work?",
    "timeline": "What is your timeline and what are the priority milestones?",
    "platform": "What platforms should this run on (web, mobile, desktop)?",
    "project_identity": "What is the project name and its primary goal?",
    "offline_support": "Does the app need to work offline?",
    "push_notifications": "What kinds of notifications should users receive?",
    "endpoints": "What are the key API endpoints needed?",
    "auth": "How should authentication and authorization work?",
    "availability": "What uptime/availability requirements do you have?",
}

_GENERIC_FOLLOWUPS = [
    "Are there any edge cases or error scenarios we should handle specially?",
    "What are the business rules or constraints that the system must follow?",
    "Are there any UI/UX preferences or design guidelines to follow?",
    "What reporting or analytics capabilities do you need?",
    "How should data backup and disaster recovery work?",
    "Are there any regulatory or compliance requirements?",
    "What is the expected budget range for this project?",
    "Who are the primary competitors and how should this product differentiate?",
]


def generate_next_question(llm, description, answers, domain, domain_label, doc_knowledge=None):
    """
    Call the LLM with the full conversation context.
    Returns dict: completeness (0-100), ready_for_prd, next_question, focus_area,
                  areas_covered, areas_missing.
    """
    conv_parts = [f"Project Description: {description}\nDomain: {domain_label}"]
    for i, a in enumerate(answers, 1):
        conv_parts.append(f"Q{i}: {a['question']}\nA{i}: {a['answer']}")
    conv_text = "\n\n".join(conv_parts)

    ref = load_ref()
    prd_data = ref.get("prd_types", {}).get(domain, {})
    required_gates = prd_data.get("required_gates", [])

    doc_ctx = ""
    if doc_knowledge:
        doc_ctx = f"\nREFERENCE DOCUMENTS (use to spot extra gaps):\n{doc_knowledge[:2000]}"

    system_prompt = (
        "You are an expert requirements analyst conducting a requirements elicitation interview. "
        "Assess what has been gathered so far and decide what to ask next. "
        "Ask clear, specific questions a non-technical client can answer. "
        "Never repeat a question already asked. Focus on the most critical gap first."
    )

    user_prompt = f"""Analyze this requirements conversation and respond with ONLY valid JSON.

CONVERSATION:
{conv_text}

DOMAIN-SPECIFIC AREAS TO COVER: {json.dumps(required_gates)}
{doc_ctx}

KEY AREAS a good PRD needs:
- Core features and user workflows
- User roles and permissions
- Non-functional requirements (performance, security, scalability)
- Integrations and third-party services
- Data model and storage
- Business rules and constraints
- Timeline and priorities
- Edge cases and error handling
- UI/UX preferences
- Deployment and infrastructure

Number of questions answered so far: {len(answers)}

Respond with this exact JSON (no markdown fences, no explanation):
{{
  "completeness": <number 0 to 100>,
  "areas_covered": ["area1", "area2"],
  "areas_missing": ["area1", "area2"],
  "ready_for_prd": <true if completeness >= 85 and all critical areas covered>,
  "next_question": "<the single most important question to ask next, or empty string if ready>",
  "focus_area": "<which area this question targets>"
}}"""

    try:
        raw = llm.generate_text(system_prompt=system_prompt, user_prompt=user_prompt)
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(raw)

        return {
            "completeness": min(max(int(data.get("completeness", 30)), 0), 100),
            "areas_covered": data.get("areas_covered", []),
            "areas_missing": data.get("areas_missing", []),
            "ready_for_prd": bool(data.get("ready_for_prd", False)),
            "next_question": str(data.get("next_question", "")),
            "focus_area": str(data.get("focus_area", "general")),
        }
    except Exception:
        return _fallback_question(answers, required_gates, domain)


def _fallback_question(answers, required_gates, domain):
    asked_areas = {a.get("focus_area", "") for a in answers}

    for gate in required_gates:
        if gate not in asked_areas:
            q = _FALLBACK_GATE_QUESTIONS.get(
                gate, f"Can you describe the {gate.replace('_', ' ')} requirements?"
            )
            return {
                "completeness": max(15, len(answers) * 7),
                "areas_covered": list(asked_areas),
                "areas_missing": [g for g in required_gates if g not in asked_areas],
                "ready_for_prd": False,
                "next_question": q,
                "focus_area": gate,
            }

    idx = max(0, len(answers) - len(required_gates))
    if idx < len(_GENERIC_FOLLOWUPS):
        return {
            "completeness": min(70 + idx * 5, 95),
            "areas_covered": list(asked_areas),
            "areas_missing": [],
            "ready_for_prd": False,
            "next_question": _GENERIC_FOLLOWUPS[idx],
            "focus_area": "general",
        }

    return {
        "completeness": 90,
        "areas_covered": list(asked_areas),
        "areas_missing": [],
        "ready_for_prd": True,
        "next_question": "",
        "focus_area": "",
    }

# ── Build conversation text for pipeline ─────────────────────────────────────

def build_conversation_text(description, answers, doc_knowledge=None):
    lines = [f"Client: {description}"]
    for a in answers:
        lines.append(f"Interviewer: {a['question']}")
        lines.append(f"Client: {a['answer']}")
    if doc_knowledge:
        lines.append(f"\n[Reference Documents]\n{doc_knowledge[:3000]}")
    return "\n".join(lines)

# ── Pipeline runner ──────────────────────────────────────────────────────────

def run_pipeline(conversation: str, project_name: str, llm):
    from state_schema import AgentState
    from agents import (
        TranscriptionAgent, RequirementAnalyzerAgent,
        AmbiguityDetectionAgent, QuestionGenerationAgent, DocumentationAgent,
    )
    from persona_config import get_persona
    from completion_engine import evaluate
    from prd_generator import PRDGenerator

    state = AgentState(project_name=project_name, client_name="User")
    state.persona = get_persona("PM")

    TranscriptionAgent().run_from_text(state, conversation)
    RequirementAnalyzerAgent(llm=llm).run(state)
    AmbiguityDetectionAgent(llm=llm).run(state)
    QuestionGenerationAgent(llm=llm).run(state)
    DocumentationAgent(llm=llm).run(state)
    evaluate(state)

    gen = PRDGenerator(llm=llm)
    state.prd_markdown = gen.generate(state, state.persona)
    return state

# ── Session state ────────────────────────────────────────────────────────────

DEFAULTS = {
    "messages": [],
    "answers": [],          # [{"question": str, "answer": str, "focus_area": str}]
    "description": "",
    "phase": "describe",    # describe | interview | generating | done
    "domain": "general",
    "domain_label": "",
    "prd_md": "",
    "prd_state": None,
    "doc_knowledge": None,
    "completeness": 0,
    "areas_covered": [],
    "areas_missing": [],
    "current_question": "",
    "current_focus": "",
    "input_text": "",
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

def reset():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v


def handle_answer(text: str):
    """Process a user answer, then ask the LLM for the next question."""
    text = text.strip()
    if not text:
        return

    st.session_state.messages.append({"role": "user", "content": text})
    st.session_state.answers.append({
        "question": st.session_state.current_question,
        "answer": text,
        "focus_area": st.session_state.current_focus,
    })
    st.session_state.input_text = ""

    # Safety ceiling: after 30 answers, wrap up
    if len(st.session_state.answers) >= 30:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "We've covered a lot of ground! Let me generate your PRD now.",
        })
        st.session_state.phase = "generating"
        return

    llm = get_llm()
    if llm is None:
        st.session_state.phase = "generating"
        return

    result = generate_next_question(
        llm,
        st.session_state.description,
        st.session_state.answers,
        st.session_state.domain,
        st.session_state.domain_label,
        st.session_state.doc_knowledge,
    )

    st.session_state.completeness = result["completeness"]
    st.session_state.areas_covered = result["areas_covered"]
    st.session_state.areas_missing = result["areas_missing"]

    if result["ready_for_prd"] or not result["next_question"]:
        pct = result["completeness"]
        st.session_state.messages.append({
            "role": "assistant",
            "content": (
                f"I've gathered comprehensive requirements ({pct}% complete). "
                "Generating your PRD now!"
            ),
        })
        st.session_state.phase = "generating"
    else:
        q = result["next_question"]
        st.session_state.current_question = q
        st.session_state.current_focus = result.get("focus_area", "general")
        st.session_state.messages.append({"role": "assistant", "content": q})


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Configuration")
    llm = get_llm()
    if llm:
        st.success("Groq LLM connected")
    else:
        st.error("GROQ_API_KEY missing in .env")

    st.markdown("---")
    st.markdown("### Upload Reference Docs")
    st.caption("Upload existing PRDs, standards, or domain docs to improve analysis.")
    docs = st.file_uploader("Choose files", accept_multiple_files=True,
                            type=["txt", "md", "pdf"])
    if docs:
        combined = ""
        for d in docs:
            try:
                combined += d.read().decode("utf-8", errors="ignore") + "\n"
            except Exception:
                pass
        if combined.strip():
            st.session_state.doc_knowledge = combined
            st.success(f"{len(docs)} doc(s) loaded")

    if st.session_state.phase == "interview" and st.session_state.completeness > 0:
        st.markdown("---")
        st.markdown("### Completeness")
        st.progress(
            st.session_state.completeness / 100,
            text=f"{st.session_state.completeness}%",
        )
        if st.session_state.areas_covered:
            st.markdown("**Covered:**")
            for area in st.session_state.areas_covered[:8]:
                st.markdown(f"- {area}")
        if st.session_state.areas_missing:
            st.markdown("**Still needed:**")
            for area in st.session_state.areas_missing[:8]:
                st.markdown(f"- {area}")

    st.markdown("---")
    if st.button("Reset conversation"):
        reset()
        st.rerun()

    st.markdown("---")
    st.caption("Agents: Transcription | Analyzer | Ambiguity | Question Gen | Documentation")


# ── Header ───────────────────────────────────────────────────────────────────

st.markdown("## Requirements Engine")
st.caption("Describe your product idea. The AI will interview you and produce a professional PRD.")

# ══════════════════════════════════════════════════════════════════════════════
# PHASE: DESCRIBE
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.phase == "describe":
    st.markdown("### What do you want to build?")

    desc = st.text_area(
        "Describe your product idea",
        value=st.session_state.description,
        height=140,
        placeholder="e.g. I want to build a food delivery app where restaurants list menus, "
                    "customers order, drivers deliver...",
    )
    st.session_state.description = desc

    st.markdown("**Or record your idea:**")
    audio_val = st.audio_input("Click to record, click again to stop", key="desc_audio")
    if audio_val is not None:
        with st.spinner("Transcribing your recording..."):
            transcript = transcribe_audio_wav(audio_val.read())
        if transcript:
            st.success(f"Transcribed: *{transcript}*")
            st.session_state.description = (desc + " " + transcript).strip()
            st.rerun()
        else:
            st.warning("Could not transcribe audio. Please try again or type instead.")

    st.markdown("---")
    if st.button("Start Interview", type="primary",
                 disabled=not st.session_state.description.strip()):
        ref = load_ref()
        domain, prd_data = detect_domain(st.session_state.description, ref)
        label = prd_data.get("label", "General Software") if prd_data else "General Software"

        st.session_state.domain = domain
        st.session_state.domain_label = label
        st.session_state.answers = []
        st.session_state.completeness = 0

        llm = get_llm()
        first_q = ""
        focus = "features"
        if llm:
            with st.spinner("Analyzing your description..."):
                result = generate_next_question(
                    llm, st.session_state.description, [],
                    domain, label, st.session_state.doc_knowledge,
                )
            first_q = result.get("next_question", "")
            focus = result.get("focus_area", "features")
            st.session_state.completeness = result.get("completeness", 10)
            st.session_state.areas_missing = result.get("areas_missing", [])
            st.session_state.areas_covered = result.get("areas_covered", [])

        if not first_q:
            first_q = "What are the core features and user workflows for your product?"

        st.session_state.current_question = first_q
        st.session_state.current_focus = focus
        st.session_state.messages = [
            {"role": "user", "content": st.session_state.description},
            {"role": "assistant",
             "content": (
                 f"I've detected this is a **{label}** project. "
                 "I'll ask you questions to build complete requirements. "
                 "The interview continues until I have enough detail -- "
                 "there's no fixed limit.\n\n" + first_q
             )},
        ]
        st.session_state.phase = "interview"
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PHASE: INTERVIEW  (dynamic, gap-driven)
# ══════════════════════════════════════════════════════════════════════════════

elif st.session_state.phase == "interview":
    completeness = st.session_state.completeness
    q_count = len(st.session_state.answers)

    st.progress(
        min(completeness / 100, 1.0),
        text=(
            f"Completeness: {completeness}%  |  "
            f"Questions answered: {q_count}  |  "
            f"{st.session_state.domain_label}"
        ),
    )

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Input area ──
    st.markdown("---")

    col_input, col_send = st.columns([5, 1])
    with col_input:
        user_text = st.text_area(
            "Your answer",
            value=st.session_state.input_text,
            height=80,
            placeholder="Type your answer here...",
            label_visibility="collapsed",
            key="answer_box",
        )
    with col_send:
        st.markdown("<br>", unsafe_allow_html=True)
        send_clicked = st.button("Send", type="primary", use_container_width=True)

    col_mic, col_status = st.columns([1, 3])
    with col_mic:
        audio_val = st.audio_input(
            "Record answer", key=f"mic_{q_count}", label_visibility="collapsed",
        )
    with col_status:
        if audio_val is not None:
            with st.spinner("Transcribing..."):
                transcript = transcribe_audio_wav(audio_val.read())
            if transcript:
                st.success(f"Transcribed: *{transcript}*")
                with st.spinner("Analyzing your answer..."):
                    handle_answer(transcript)
                st.rerun()
            else:
                st.warning("Could not transcribe. Try again or type instead.")

    if send_clicked and user_text.strip():
        with st.spinner("Analyzing your answer..."):
            handle_answer(user_text)
        st.rerun()

    # ── Early PRD generation button (available after 3+ answers) ──
    if q_count >= 3:
        st.markdown("---")
        col_gen, col_info = st.columns([1, 3])
        with col_gen:
            if st.button("Generate PRD now"):
                st.session_state.phase = "generating"
                st.rerun()
        with col_info:
            if completeness < 70:
                st.caption(
                    "You can generate now, but more questions would improve quality."
                )
            else:
                st.caption(
                    "Good coverage! You can generate now or continue for more detail."
                )


# ══════════════════════════════════════════════════════════════════════════════
# PHASE: GENERATING
# ══════════════════════════════════════════════════════════════════════════════

elif st.session_state.phase == "generating":
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    with st.spinner(
        "Running 5-agent pipeline "
        "(Transcription -> Analyzer -> Ambiguity -> Questions -> Documentation)..."
    ):
        try:
            llm = get_llm()
            if llm is None:
                st.error("No LLM configured. Add GROQ_API_KEY to .env")
                st.stop()

            conversation = build_conversation_text(
                st.session_state.description,
                st.session_state.answers,
                st.session_state.doc_knowledge,
            )
            project_name = _extract_project_name(st.session_state.description)

            state = run_pipeline(conversation, project_name, llm)
            st.session_state.prd_md = state.prd_markdown
            st.session_state.prd_state = {
                "functional": state.functional,
                "non_functional": state.non_functional,
                "constraints": state.constraints_list,
                "assumptions": state.assumptions_list,
                "gaps": [g.__dict__ for g in state.gaps] if state.gaps else [],
                "follow_up": state.follow_up_questions,
                "completion": (
                    state.completion_status.__dict__
                    if hasattr(state.completion_status, "__dict__") else {}
                ),
                "project_name": state.project_name,
            }
            st.session_state.phase = "done"
            st.rerun()

        except Exception as e:
            st.error(f"Pipeline error: {e}")
            import traceback
            st.code(traceback.format_exc())


# ══════════════════════════════════════════════════════════════════════════════
# PHASE: DONE
# ══════════════════════════════════════════════════════════════════════════════

elif st.session_state.phase == "done":
    info = st.session_state.prd_state or {}
    project_name = info.get("project_name", "Project")

    completion = info.get("completion", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall Score", f"{completion.get('overall_score', 0):.0%}")
    c2.metric("Functional Reqs", len(info.get("functional", [])))
    c3.metric("Non-Functional", len(info.get("non_functional", [])))
    c4.metric("Open Gaps", len(info.get("gaps", [])))

    tab_prd, tab_analysis, tab_chat = st.tabs(
        ["PRD Document", "Analysis", "Conversation"])

    with tab_prd:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"### {project_name} -- PRD")
        with col2:
            st.download_button(
                "Download .md",
                data=st.session_state.prd_md,
                file_name=f"{project_name.replace(' ', '_')}_PRD.md",
                mime="text/markdown",
            )
        st.markdown("---")
        st.markdown(st.session_state.prd_md)

    with tab_analysis:
        st.markdown("#### Functional Requirements")
        for fr in info.get("functional", []):
            st.markdown(
                f"- **{fr.get('id', '?')}**: "
                f"{fr.get('title', fr.get('description', '')[:80])}")

        st.markdown("#### Non-Functional Requirements")
        for nfr in info.get("non_functional", []):
            st.markdown(
                f"- **{nfr.get('id', '?')}** [{nfr.get('category', '')}]: "
                f"{nfr.get('description', '')[:80]}")

        if info.get("gaps"):
            st.markdown("#### Open Gaps")
            for g in info["gaps"]:
                st.warning(f"**{g.get('category', '')}**: {g.get('description', '')}")

        if info.get("follow_up"):
            st.markdown("#### Suggested Follow-up Questions")
            for q in info["follow_up"]:
                text = q.get("text", q) if isinstance(q, dict) else q
                st.info(text)

    with tab_chat:
        st.markdown(f"**Questions answered:** {len(st.session_state.answers)}")
        st.markdown(f"**Final completeness:** {st.session_state.completeness}%")
        st.markdown("---")
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    st.markdown("---")
    if st.button("Start new project", type="primary"):
        reset()
        st.rerun()
