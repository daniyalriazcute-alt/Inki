from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from agent import run_aura
from firebase_service import (
    firebase_available,
    login_user,
    register_user,
    send_login_notification,
)
from memory import ConversationMemory
from rag import retrieve_context
from security import sanitize_output, validate_user_input

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"


def _first_existing(*paths: Path) -> Path:
    """Return the first file that exists (assets/ folder or repo root)."""
    for path in paths:
        if path.exists():
            return path
    return paths[0]


AVATAR = _first_existing(
    ASSETS_DIR / "aura_avatar.jpg",
    BASE_DIR / "aura_avatar.jpg",
    ASSETS_DIR / "AI_Agent_Avatar.jpg",
    BASE_DIR / "AI_Agent_Avatar.jpg",
)
BACKGROUND = _first_existing(
    ASSETS_DIR / "abstract_blue_liquid.svg",
    BASE_DIR / "abstract_blue_liquid.svg",
)

st.set_page_config(
    page_title="AuraAI — AI Career & Skills Navigator",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -----------------------------------------------------------------------------
# Session state
# -----------------------------------------------------------------------------
defaults = {
    "authenticated": False,
    "user": None,
    "page": "Home",
    "chat_open": False,
    "messages": [],
    "memory": ConversationMemory(max_turns=8),
    "pending_approval": None,
    "last_approval": None,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


def _asset_data_uri(path: Path) -> str:
    """Return a safe data URI. Missing assets never crash the app."""
    if not path.exists():
        return ""
    mime = {
        ".svg": "image/svg+xml",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }.get(path.suffix.lower(), "image/png")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


try:
    # Preferred: avatar embedded in avatar_data.py (no folder needed).
    from avatar_data import AVATAR_B64

    AVATAR_URI = f"data:image/jpeg;base64,{AVATAR_B64}"
except ImportError:
    AVATAR_URI = _asset_data_uri(AVATAR)
BG_URI = _asset_data_uri(BACKGROUND)


def inject_css() -> None:
    background_layer = (
        f'url("{BG_URI}") center/cover fixed,' if BG_URI else ""
    )
    st.markdown(
        f"""
        <style>
        :root {{
            --navy: #06162d;
            --navy2: #091d3a;
            --blue: #2e8cff;
            --blue2: #65baff;
            --text: #f3f7ff;
            --muted: #a9bddb;
            --line: rgba(113, 183, 255, .22);
            --glass: rgba(7, 24, 49, .70);
        }}

        .stApp {{
            background:
                {background_layer}
                radial-gradient(circle at 82% 40%, rgba(21, 91, 178, .24), transparent 34%),
                radial-gradient(circle at 15% 75%, rgba(23, 91, 160, .12), transparent 30%),
                linear-gradient(135deg, #020b1b 0%, #06162d 50%, #071a36 100%);
            color: var(--text);
        }}

        .stApp::before {{
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            background:
                radial-gradient(circle at 50% 0%, rgba(46,140,255,.08), transparent 28%),
                linear-gradient(180deg, rgba(1,8,20,.10), rgba(1,8,20,.30));
            z-index: 0;
        }}

        .block-container {{
            max-width: 1380px;
            padding: 0 2.2rem 3rem;
            position: relative;
            z-index: 1;
        }}

        /* Hide Streamlit chrome for a website-like UI. */
        #MainMenu, footer, header {{ visibility: hidden; }}
        [data-testid="stSidebar"] {{ display: none; }}
        [data-testid="stToolbar"] {{ display: none; }}

        /* Top navigation */
        .topbar {{
            min-height: 88px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(120, 180, 255, .07);
            margin: 0 -2.2rem 0;
            padding: 0 3.6rem;
            background: rgba(4, 16, 36, .66);
            backdrop-filter: blur(18px);
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
            white-space: nowrap;
        }}
        .brand-mark {{
            width: 42px;
            height: 42px;
            display: grid;
            place-items: center;
            color: #55aaff;
            font-size: 34px;
            font-weight: 800;
            line-height: 1;
            text-shadow: 0 0 18px rgba(70,160,255,.65);
        }}
        .brand-name {{
            font-size: 28px;
            font-weight: 800;
            letter-spacing: -.7px;
        }}
        .brand-name span {{ color: #55aaff; }}
        .brand-divider {{
            width: 1px;
            height: 30px;
            background: rgba(175,205,255,.35);
            margin: 0 4px 0 2px;
        }}
        .brand-sub {{ color: #a9bde0; font-size: 17px; }}

        /* Website navigation */
        .site-nav {{
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 48px;
            width: 100%;
            box-sizing: border-box;
            padding: 0 14px;
            border-radius: 11px;
            color: #eaf3ff !important;
            text-decoration: none !important;
            font-size: 16px;
            font-weight: 600;
            transition: .2s ease;
            white-space: nowrap;
        }}
        .site-nav:hover {{ background: rgba(52,129,232,.16); color: white !important; }}
        .site-nav.active {{ background: rgba(52,129,232,.48); }}
        .auth-link {{ border: 1px solid rgba(181,211,255,.65); }}
        .register-link {{
            background: linear-gradient(135deg,#2d83f4,#368cff);
            border: 1px solid #4499ff;
            box-shadow: 0 8px 28px rgba(38,129,245,.22);
        }}

        /* Navigation buttons (real Streamlit buttons: same tab, session kept) */
        [class*="st-key-nav"] button {{
            width: 100%;
            min-height: 48px;
            border-radius: 11px !important;
            background: transparent !important;
            border: 1px solid transparent !important;
            color: #eaf3ff !important;
            font-size: 16px !important;
            font-weight: 600 !important;
            white-space: nowrap;
            box-shadow: none !important;
            transition: .2s ease;
        }}
        [class*="st-key-nav"] button:hover {{
            background: rgba(52,129,232,.16) !important;
            color: white !important;
        }}
        [class*="st-key-navactive_"] button {{ background: rgba(52,129,232,.48) !important; }}
        [class*="st-key-navauth_"] button {{ border: 1px solid rgba(181,211,255,.65) !important; }}
        [class*="st-key-navreg_"] button {{
            background: linear-gradient(135deg,#2d83f4,#368cff) !important;
            border: 1px solid #4499ff !important;
            box-shadow: 0 8px 28px rgba(38,129,245,.22) !important;
        }}

        /* Hero */
        .hero-wrap {{
            padding: 62px 0 38px;
        }}
        .hero-grid {{
            display: grid;
            grid-template-columns: 1.05fr .95fr;
            gap: 48px;
            align-items: center;
        }}
        .eyebrow {{
            display: inline-flex;
            align-items: center;
            gap: 9px;
            padding: 10px 18px;
            border: 1px solid #2c78db;
            border-radius: 999px;
            color: #67b9ff;
            background: rgba(9,32,67,.38);
            font-size: 16px;
            font-weight: 600;
        }}
        .hero-title {{
            margin: 26px 0 18px;
            font-size: clamp(3.1rem, 6vw, 5.45rem);
            line-height: .98;
            letter-spacing: -3.6px;
            font-weight: 850;
        }}
        .hero-title .gradient {{
            background: linear-gradient(90deg,#2d9dff 0%,#6e8cff 52%,#c58aff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .hero-copy-wrap {{ padding-top: 42px; }}
        .hero-copy {{
            max-width: 680px;
            color: #b9c9e3;
            font-size: 19px;
            line-height: 1.7;
        }}
        .st-key-enter_aura button {{
            margin-top: 20px;
            background: linear-gradient(135deg,#2d8df5,#3988f1) !important;
            border: 0 !important;
            color: white !important;
            font-size: 18px !important;
            font-weight: 750 !important;
            border-radius: 18px !important;
            padding: .85rem 1.55rem !important;
            box-shadow: 0 14px 35px rgba(30,128,245,.24) !important;
        }}

        /* Aura panel */
        .aura-stage {{
            min-height: 500px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }}
        .aura-stage::before {{
            content: "";
            position: absolute;
            width: 410px;
            height: 410px;
            border-radius: 50%;
            border: 2px solid rgba(44,157,255,.72);
            box-shadow: 0 0 45px rgba(44,157,255,.18), inset 0 0 55px rgba(44,157,255,.09);
        }}
        .aura-stage::after {{
            content: "";
            position: absolute;
            width: 310px;
            height: 310px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(35,130,255,.20), transparent 66%);
            filter: blur(10px);
        }}
        .aura-img {{
            position: relative;
            z-index: 2;
            width: 370px;
            height: 370px;
            max-width: 88%;
            border-radius: 50%;
            object-fit: cover;
            object-position: center 20%;
            border: 3px solid rgba(70,170,255,.55);
            box-shadow: 0 20px 50px rgba(0,0,0,.45), 0 0 40px rgba(44,157,255,.25);
        }}
        .aura-bubble {{
            position: absolute;
            z-index: 4;
            bottom: 18px;
            right: 0;
            width: 360px;
            max-width: 88%;
            border: 1px solid #2e8eff;
            border-radius: 22px;
            padding: 16px 22px;
            background: rgba(9,34,68,.90);
            box-shadow: 0 15px 35px rgba(0,0,0,.28);
        }}
        .aura-bubble b {{ font-size: 18px; }}
        .aura-bubble span {{ display: block; color: #9dbbe1; margin-top: 5px; }}

        /* Feature row */
        .features {{
            display: grid;
            grid-template-columns: repeat(4,1fr);
            gap: 48px;
            margin: 0 0 30px;
        }}
        .feature-icon {{
            width: 64px;
            height: 64px;
            border-radius: 16px;
            display: grid;
            place-items: center;
            background: linear-gradient(145deg,rgba(28,75,141,.58),rgba(11,31,64,.8));
            border: 1px solid rgba(72,153,247,.12);
            color: #59b9ff;
            font-size: 28px;
            margin-bottom: 13px;
        }}
        .feature h3 {{ margin: 0 0 7px; font-size: 18px; }}
        .feature p {{ margin: 0; color: #9fb5d3; line-height: 1.5; font-size: 15px; }}

        /* Content / auth / chat */
        .glass {{
            border: 1px solid var(--line);
            background: var(--glass);
            border-radius: 24px;
            padding: 30px;
            backdrop-filter: blur(16px);
            box-shadow: 0 20px 55px rgba(0,0,0,.22);
        }}
        .page-title {{ font-size: 40px; font-weight: 800; letter-spacing: -1px; margin: 48px 0 20px; }}
        .approval {{
            border: 1px solid #e3bd50;
            border-radius: 18px;
            padding: 18px;
            background: rgba(94,73,15,.24);
            margin: 15px 0;
        }}
        .chat-shell {{
            max-width: 980px;
            margin: 35px auto 0;
            border: 1px solid var(--line);
            border-radius: 24px;
            padding: 20px;
            background: rgba(4,16,34,.74);
        }}
        .auth-card {{ max-width: 600px; margin: 60px auto; }}
        .small-muted {{ color: #9db6d0; }}

        @media (max-width: 900px) {{
            .topbar {{ padding: 0; }}
            .brand-sub, .brand-divider {{ display: none; }}
            .hero-grid {{ grid-template-columns: 1fr; }}
            .hero-wrap {{ padding-top: 52px; }}
            .aura-stage {{ min-height: 420px; }}
            .features {{ grid-template-columns: repeat(2,1fr); gap: 28px; }}
            .block-container {{ padding: 0 1rem 2rem; }}
        }}
        @media (max-width: 560px) {{
            .brand-name {{ font-size: 23px; }}
            .features {{ grid-template-columns: 1fr; }}
            .hero-title {{ font-size: 3rem; }}
            .aura-stage::before {{ width: 310px; height: 310px; }}
            .aura-img {{ width: 270px; height: 270px; }}
            .aura-bubble {{ right: 0; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def go(page: str) -> None:
    st.session_state.page = page
    if page != "Home":
        st.session_state.chat_open = False
    st.rerun()


def logout() -> None:
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.messages = []
    st.session_state.pending_approval = None
    st.session_state.last_approval = None
    st.session_state.memory = ConversationMemory(max_turns=8)
    st.session_state.page = "Home"
    st.session_state.chat_open = False
    st.rerun()


def render_nav() -> None:
    # Use one Streamlit column row so the navigation stays inside the same
    # top bar instead of dropping into a separate row.
    cols = st.columns([3.6, 1.0, 1.0, 1.0, 0.78, 0.9], gap="small")
    with cols[0]:
        st.markdown(
            """
            <div class="brand">
              <div class="brand-mark">✦</div>
              <div class="brand-name">Aura<span>AI</span></div>
              <div class="brand-divider"></div>
              <div class="brand-sub">AI Career &amp; Skills Navigator</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    nav = [(1, "Home"), (2, "About"), (3, "Contact")]
    for idx, label in nav:
        with cols[idx]:
            prefix = "navactive" if st.session_state.page == label else "nav"
            if st.button(label, key=f"{prefix}_{label}", use_container_width=True):
                go(label)

    if st.session_state.authenticated:
        with cols[4]:
            if st.button("Logout", key="navauth_Logout", use_container_width=True):
                logout()
    else:
        with cols[4]:
            if st.button("Login", key="navauth_Login", use_container_width=True):
                go("Login")
        with cols[5]:
            if st.button("Register", key="navreg_Register", use_container_width=True):
                go("Register")


def home_page() -> None:
    if st.session_state.authenticated and st.session_state.chat_open:
        render_chat()
        return

    # Real two-column layout: Streamlit columns keep the hero text and Aura
    # artwork side-by-side rather than stacking HTML fragments vertically.
    left, right = st.columns([1.08, 0.92], gap="large")
    with left:
        st.markdown('<div class="hero-copy-wrap">', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="eyebrow">✦ &nbsp; Your AI Career Coach</div>
            <div class="hero-title">Navigate your next move<br>with <span class="gradient">clarity.</span></div>
            <div class="hero-copy">
              AI Career &amp; Skills Navigator helps you identify skill gaps,
              find free learning resources, and explore real-time job market
              trends — all in one place.
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("💬  Enter Aura   →", key="enter_aura", type="primary"):
            if st.session_state.authenticated:
                st.session_state.chat_open = True
            else:
                st.session_state.page = "Login"
                st.session_state.login_notice = True
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        avatar = AVATAR_URI
        if avatar:
            st.markdown(
                f"""
                <div class="aura-stage">
                  <div class="aura-ring"></div>
                  <img class="aura-img" src="{avatar}" alt="Aura AI career coach">
                  <div class="aura-bubble"><b>✦ &nbsp; Hi, I’m Aura!</b><span>Your AI Career &amp; Skills Navigator</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="aura-stage"><div class="aura-bubble"><b>✦ &nbsp; Hi, I’m Aura!</b><span>Your AI Career &amp; Skills Navigator</span></div></div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        """
        <div class="features">
          <div class="feature"><div class="feature-icon">◎</div><h3>Find Skill Gaps</h3><p>Discover what skills to build next.</p></div>
          <div class="feature"><div class="feature-icon">▣</div><h3>Learn for Free</h3><p>Get curated free resources &amp; courses.</p></div>
          <div class="feature"><div class="feature-icon">↗</div><h3>Market Trends</h3><p>Explore real-time job opportunities.</p></div>
          <div class="feature"><div class="feature-icon">◈</div><h3>Build Your Future</h3><p>Get personalized career guidance.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def auth_page(register: bool) -> None:
    title = "Create your Aura account" if register else "Welcome back"
    subtitle = "Create your account to start your career journey with Aura." if register else "Sign in to continue with Aura."
    st.markdown(
        f'<div class="auth-card glass"><div class="page-title" style="margin-top:0">{title}</div><p class="small-muted">{subtitle}</p>',
        unsafe_allow_html=True,
    )
    if st.session_state.pop("login_notice", False) and not register:
        st.info("Please sign in to enter Aura.")
    if not firebase_available():
        st.warning("Firebase is not configured yet. Add your Firebase settings to Streamlit Secrets before using authentication.")

    with st.form("auth_form"):
        name = st.text_input("Name") if register else ""
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm password", type="password") if register else ""
        fcm_token = st.text_input(
            "Optional FCM registration token",
            type="password",
            help="Optional Firebase Cloud Messaging registration token.",
        )
        submitted = st.form_submit_button("Create account" if register else "Sign in", type="primary", use_container_width=True)

    if submitted:
        if not email or not password:
            st.error("Email and password are required.")
        elif register and password != confirm:
            st.error("Passwords do not match.")
        else:
            try:
                result = register_user(name, email, password, fcm_token) if register else login_user(email, password)
                st.session_state.authenticated = True
                st.session_state.user = result
                st.session_state.page = "Home"
                st.session_state.chat_open = False
                if fcm_token and not register:
                    send_login_notification(fcm_token, result.get("name") or "Aura user")
                st.success("Authentication successful.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    st.markdown('</div>', unsafe_allow_html=True)


def render_chat() -> None:
    st.markdown('<div class="chat-shell">', unsafe_allow_html=True)
    left, right = st.columns([5, 1])
    with left:
        st.markdown("## ✦ Aura Chat")
        st.caption("AI Career & Skills Navigator")
    with right:
        if st.button("Close", use_container_width=True):
            st.session_state.chat_open = False
            st.session_state.pending_approval = None
            st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(
            message["role"],
            avatar=AVATAR_URI if message["role"] == "assistant" and AVATAR_URI else None,
        ):
            st.markdown(message["content"])

    pending = st.session_state.pending_approval
    if pending:
        st.markdown(
            f"""
            <div class="approval">
              <b>Human approval checkpoint</b><br><br>
              Aura identified this as a potentially consequential or preference-sensitive request.
              Please confirm before proceeding.<br><br>
              <b>Reason:</b> {pending['reason']}<br>
              <b>Requested action:</b> {pending['action']}
            </div>
            """,
            unsafe_allow_html=True,
        )
        a, b = st.columns(2)
        with a:
            if st.button("✓ Approve and continue", type="primary", use_container_width=True):
                st.session_state.last_approval = {"approved": True, **pending}
                st.session_state.pending_approval = None
                _execute_pending(pending)
                st.rerun()
        with b:
            if st.button("✕ Reject / revise", use_container_width=True):
                st.session_state.last_approval = {"approved": False, **pending}
                st.session_state.pending_approval = None
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "No problem. I will not proceed with that action. Tell me how you would like to adjust the request.",
                })
                st.rerun()

    prompt = st.chat_input("Ask Aura about your career, skills, learning plan, or market...")
    st.markdown('</div>', unsafe_allow_html=True)
    if prompt:
        _handle_user_message(prompt)


def _handle_user_message(prompt: str) -> None:
    prompt = validate_user_input(prompt)
    if not prompt:
        return
    st.session_state.messages.append({"role": "user", "content": prompt})
    decision = requires_approval(prompt)
    if decision["required"]:
        st.session_state.pending_approval = {
            "query": prompt,
            "reason": decision["reason"],
            "action": decision["action"],
        }
        st.rerun()
    _run_and_store(prompt, approved=False)
    st.rerun()


def _execute_pending(pending: dict) -> None:
    _run_and_store(pending["query"], approved=True)


def _run_and_store(prompt: str, approved: bool) -> None:
    with st.spinner("Aura is working through the request..."):
        try:
            retrieved = retrieve_context(prompt, k=4)
            result = run_aura(
                user_query=prompt,
                memory=st.session_state.memory,
                retrieved_context=retrieved,
                human_approved=approved,
            )
            safe = sanitize_output(result)
            st.session_state.memory.add("user", prompt)
            st.session_state.memory.add("assistant", safe)
            st.session_state.messages.append({"role": "assistant", "content": safe})
        except Exception as exc:
            safe_error = sanitize_output(
                "I couldn't complete that request. Please try again. "
                f"Technical detail: {exc}"
            )
            st.session_state.messages.append({"role": "assistant", "content": safe_error})


def requires_approval(prompt: str) -> dict:
    text = prompt.lower().strip()
    consequential = [
        "should i quit", "should i resign", "should i leave my job",
        "should i accept", "should i reject", "which career should i choose",
        "which career should i pursue", "choose a career for me",
        "tell me what career i should", "should i switch careers",
        "should i change careers", "which certification should i take",
        "should i spend", "should i pay", "should i relocate",
        "should i move", "should i apply", "make the decision for me",
    ]
    preference_sensitive = [
        "based on my situation", "based on my experience",
        "personalized recommendation", "what should i do",
        "what would you choose for me", "recommend one for me",
        "which one is right for me",
    ]
    if any(p in text for p in consequential):
        return {
            "required": True,
            "reason": "This request asks Aura to support a consequential personal career decision.",
            "action": "Review the relevant options, trade-offs and evidence before Aura provides a personalized recommendation.",
        }
    if any(p in text for p in preference_sensitive):
        return {
            "required": True,
            "reason": "This request depends on an important personal preference or situation.",
            "action": "Use the conversation context to prepare a personalized comparison and practical next step.",
        }
    return {"required": False, "reason": "", "action": ""}


def about_page() -> None:
    st.markdown('<div class="page-title">About Aura</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="glass">
        <b>Aura is a single-agent career and skills navigator.</b><br><br>
        CrewAI provides agent orchestration. Groq provides the LLM. FAISS and
        sentence-transformers provide RAG. Short-term memory preserves recent
        conversation context. Four controlled external tools provide research,
        public API data and arithmetic. A selective human-in-the-loop checkpoint
        pauses consequential or preference-sensitive requests for explicit user approval.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="page-title" style="font-size:28px">Agent loop</div>', unsafe_allow_html=True)
    st.code("GOAL → DECIDE → [HUMAN APPROVAL when needed] → ACT → OBSERVE → CONTINUE/COMPLETE → RETRY ONCE", language="text")
    st.markdown('<div class="page-title" style="font-size:28px">Security controls</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="glass">Prompt-injection defense · system-prompt confidentiality · untrusted-tool-data handling · restricted HTTP hosts · safe arithmetic parsing · output sanitization · secret separation · human approval checkpoints.</div>',
        unsafe_allow_html=True,
    )


def contact_page() -> None:
    st.markdown('<div class="page-title">Contact</div>', unsafe_allow_html=True)
    st.markdown('<div class="glass"><b>Email</b><br><br>daniyalriazcute@gmail.com</div>', unsafe_allow_html=True)


if "page" in st.query_params:
    st.query_params.clear()

inject_css()
render_nav()

if st.session_state.page == "Home":
    home_page()
elif st.session_state.page == "About":
    about_page()
elif st.session_state.page == "Contact":
    contact_page()
elif st.session_state.page == "Login":
    auth_page(register=False)
elif st.session_state.page == "Register":
    auth_page(register=True)
