import hashlib
import json
import os

import requests
import streamlit as st
import websocket
from requests import RequestException
from streamlit_mic_recorder import mic_recorder
from websocket import WebSocketException, WebSocketTimeoutException


# ==========================================================
# Backend configuration
# ==========================================================

DEFAULT_API_URL = "http://127.0.0.1:8000"
API_URL = os.getenv("SCALLER_API_URL", DEFAULT_API_URL).rstrip("/")
DEFAULT_WS_URL = (
    API_URL.replace("https://", "wss://").replace("http://", "ws://") + "/ws"
)
WS_URL = os.getenv("SCALLER_WS_URL", DEFAULT_WS_URL)


# ==========================================================
# Page configuration
# ==========================================================

st.set_page_config(
    page_title="Scaller AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ==========================================================
# Session state
# ==========================================================

DEFAULT_STATE = {
    "session_id": "",
    "messages": [],
    "message_text": "",
    "last_audio_hash": "",
    "submit_message": False,
    "notice": "",
    "auth_token": "",
    "user": None,
    "auth_page": "login",
    "chat_sessions": [],
    "documents": [],
    "last_uploaded_key": "",
    "uploader_key": 0,
    "dark_mode": False,
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ==========================================================
# Helper functions
# ==========================================================

def show_notice() -> None:
    """Display one friendly notice from the previous action."""
    if not st.session_state.notice:
        return

    level, message = st.session_state.notice.split(":", 1)
    if level == "error":
        st.error(message)
    elif level == "success":
        st.success(message)
    elif level == "warning":
        st.warning(message)
    else:
        st.info(message)

    st.session_state.notice = ""


def set_notice(level: str, message: str) -> None:
    st.session_state.notice = f"{level}:{message}"


def auth_headers() -> dict:
    if not st.session_state.auth_token:
        return {}
    return {"Authorization": f"Bearer {st.session_state.auth_token}"}


def friendly_error(response: requests.Response, fallback: str) -> str:
    try:
        detail = response.json().get("detail")
        return detail or fallback
    except ValueError:
        return fallback


def reset_chat_inputs() -> None:
    st.session_state.message_text = ""
    st.session_state.last_audio_hash = ""
    st.session_state.submit_message = False


def set_logged_in(payload: dict) -> None:
    st.session_state.auth_token = payload["token"]
    st.session_state.user = payload["user"]
    st.session_state.session_id = payload["session_id"]
    st.session_state.messages = []
    reset_chat_inputs()
    load_sessions()
    load_documents()


def logout() -> None:
    st.session_state.auth_token = ""
    st.session_state.user = None
    st.session_state.session_id = ""
    st.session_state.messages = []
    st.session_state.chat_sessions = []
    st.session_state.documents = []
    st.session_state.last_uploaded_key = ""
    st.session_state.auth_page = "login"
    reset_chat_inputs()
    set_notice("info", "You have been logged out.")


def request_submit() -> None:
    """Called when Enter is pressed inside the single textbox."""
    st.session_state.submit_message = True


def load_sessions() -> None:
    if not st.session_state.auth_token:
        st.session_state.chat_sessions = []
        return

    try:
        response = requests.get(f"{API_URL}/sessions", headers=auth_headers(), timeout=8)
        response.raise_for_status()
        st.session_state.chat_sessions = response.json().get("sessions", [])
    except RequestException:
        set_notice("warning", "Chat history could not be loaded right now.")
    except ValueError:
        set_notice("warning", "Chat history returned an unexpected response.")


def load_messages(session_id: str) -> None:
    try:
        response = requests.get(
            f"{API_URL}/sessions/{session_id}/messages",
            headers=auth_headers(),
            timeout=8,
        )
        response.raise_for_status()
        saved_messages = response.json().get("messages", [])
        st.session_state.messages = [
            {"role": item["sender"], "content": item["message"]}
            for item in saved_messages
            if item.get("sender") in {"user", "assistant"}
        ]
        st.session_state.session_id = session_id
        reset_chat_inputs()
    except RequestException:
        set_notice("error", "This chat could not be opened. Please try again.")
    except (ValueError, KeyError):
        set_notice("error", "This chat returned an unexpected response.")


def start_new_chat() -> None:
    try:
        response = requests.post(
            f"{API_URL}/sessions",
            headers=auth_headers(),
            json={},
            timeout=8,
        )
        response.raise_for_status()
        st.session_state.session_id = response.json()["session_id"]
        st.session_state.messages = []
        reset_chat_inputs()
        load_sessions()
        set_notice("success", "New chat started.")
    except RequestException:
        set_notice("error", "A new chat could not be started right now.")
    except (ValueError, KeyError):
        set_notice("error", "The backend returned an unexpected response.")


def clear_chat() -> None:
    """Clear backend and frontend chat memory."""
    try:
        response = requests.delete(
            f"{API_URL}/clear-session",
            json={"session_id": st.session_state.session_id},
            headers=auth_headers(),
            timeout=8,
        )
        if response.status_code >= 400:
            set_notice(
                "warning",
                "Chat was cleared here, but the backend did not confirm the session reset.",
            )
    except RequestException:
        set_notice(
            "warning",
            "Chat was cleared here. The backend could not be reached for session reset.",
        )

    st.session_state.messages = []
    reset_chat_inputs()
    load_sessions()


def send_question(question: str) -> str:
    """Send one chat turn through the existing WebSocket endpoint."""
    ws = None

    try:
        ws = websocket.create_connection(WS_URL, timeout=25)
        ws.send(
            json.dumps(
                {
                    "session_id": st.session_state.session_id,
                    "question": question,
                    "token": st.session_state.auth_token,
                }
            )
        )
        response = json.loads(ws.recv())
        if response.get("error"):
            return response["error"]
        answer = response.get("answer", "").strip()
        return answer or "I do not have an answer for that yet."

    except WebSocketTimeoutException:
        return "The server took too long to answer. Please try again in a moment."
    except (ConnectionRefusedError, WebSocketException, OSError):
        return "I could not connect to the backend right now. Please make sure the FastAPI server is running."
    except json.JSONDecodeError:
        return "The backend returned an unexpected response. Please try again."
    finally:
        if ws is not None:
            try:
                ws.close()
            except WebSocketException:
                pass


def load_documents() -> None:
    if not st.session_state.auth_token:
        st.session_state.documents = []
        return

    try:
        response = requests.get(f"{API_URL}/documents", headers=auth_headers(), timeout=8)
        response.raise_for_status()
        st.session_state.documents = response.json().get("documents", [])
    except RequestException:
        set_notice("warning", "Your documents could not be loaded right now.")
    except ValueError:
        set_notice("warning", "Documents returned an unexpected response.")


def upload_document(uploaded_file) -> None:
    """Upload a document through the existing FastAPI endpoint."""
    if uploaded_file is None:
        return

    try:
        with st.spinner(f"Processing {uploaded_file.name}... this can take a moment for larger files."):
            response = requests.post(
                f"{API_URL}/documents",
                headers=auth_headers(),
                files={
                    "file": (
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        uploaded_file.type or "application/octet-stream",
                    )
                },
                timeout=120,
            )
        if response.status_code >= 400:
            set_notice("error", friendly_error(response, "Document upload failed."))
            return

        set_notice("success", "Document uploaded successfully.")
        load_documents()
    except RequestException:
        set_notice("error", "Document upload failed because the backend could not be reached.")
    except (ValueError, KeyError):
        set_notice("error", "Document upload returned an unexpected response.")


def delete_document(document_id: int) -> None:
    try:
        response = requests.delete(
            f"{API_URL}/documents/{document_id}",
            headers=auth_headers(),
            timeout=8,
        )
        if response.status_code >= 400:
            set_notice("error", friendly_error(response, "The document could not be deleted."))
        else:
            set_notice("success", "Document deleted.")
    except RequestException:
        set_notice("error", "Deletion failed because the backend could not be reached.")
    except (ValueError, KeyError):
        set_notice("error", "Deletion returned an unexpected response.")
    finally:
        load_documents()


def document_icon(file_type: str) -> str:
    file_type = (file_type or "").lower().lstrip(".")
    return {"pdf": "📄", "docx": "📝", "txt": "📃"}.get(file_type, "📄")


def audio_mime_type(audio_format: str) -> str:
    clean_format = (audio_format or "webm").lower().lstrip(".")
    if clean_format == "wav":
        return "audio/wav"
    if clean_format == "mp3":
        return "audio/mpeg"
    return "audio/webm"


def transcribe_audio(audio: dict) -> None:
    """Upload a new recording to the existing speech endpoint."""
    audio_bytes = audio.get("bytes") if audio else None

    if not audio_bytes:
        set_notice("warning", "I did not receive any audio. Please record again.")
        return

    audio_hash = hashlib.sha256(audio_bytes).hexdigest()
    if audio_hash == st.session_state.last_audio_hash:
        return

    st.session_state.last_audio_hash = audio_hash
    audio_format = audio.get("format", "webm")
    filename = f"voice.{audio_format}"

    try:
        with st.spinner("Transcribing your voice..."):
            response = requests.post(
                f"{API_URL}/speech-to-text",
                files={
                    "audio": (
                        filename,
                        audio_bytes,
                        audio_mime_type(audio_format),
                    )
                },
                timeout=45,
            )
        response.raise_for_status()
        text = response.json().get("text", "").strip()

        if not text:
            set_notice("warning", "I could not hear any words in that recording.")
            return

        st.session_state.message_text = text
        set_notice("info", "Voice transcription is ready. You can edit it before sending.")
        st.rerun()

    except requests.Timeout:
        set_notice("error", "Speech recognition timed out. Please try a shorter recording.")
    except RequestException:
        set_notice("error", "Speech recognition failed because the backend could not be reached.")
    except (ValueError, KeyError):
        set_notice("error", "Speech recognition returned an unexpected response.")


def submit_current_message() -> None:
    """Send the current textbox value and clear it after the reply."""
    st.session_state.submit_message = False
    question = st.session_state.message_text.strip()

    if not question:
        set_notice("warning", "Please enter a question before sending.")
        return

    st.session_state.messages.append({"role": "user", "content": question})
    st.session_state.message_text = ""
    st.session_state.last_audio_hash = ""

    thinking_placeholder = st.empty()
    with thinking_placeholder:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(
                '<div class="typing-dots"><span></span><span></span><span></span></div>',
                unsafe_allow_html=True,
            )

    answer = send_question(question)
    thinking_placeholder.empty()

    st.session_state.messages.append({"role": "assistant", "content": answer})
    load_sessions()
    st.rerun()


# ==========================================================
# Styling
# ==========================================================

def build_theme_css(dark: bool) -> str:
    """Return the full <style> block for the current theme.

    DESIGN SYSTEM
    Palette: deep ink-navy + indigo, with a single warm amber "signal"
    color reserved only for live/active states (online status, the
    thinking indicator, avatar accents) -- one deliberate accent used
    consistently rather than color scattered everywhere.
    Type: Sora (brand/headings), IBM Plex Sans (body/chat), IBM Plex
    Mono (filenames, session ids, timestamps).
    The sidebar stays a constant dark ink in both light and dark mode,
    for a stronger brand identity; only the content area's palette
    switches with the toggle.
    """
    if dark:
        colors = {
            "app_bg": "#0b1220",
            "sidebar_bg": "#05070d",
            "card_bg": "#141b2e",
            "card_border": "#232b42",
            "text": "#e5e9f5",
            "text_muted": "#8a93ae",
            "input_bg": "#141b2e",
            "input_border": "#2b334a",
            "primary": "#6366f1",
            "primary_hover": "#818cf8",
            "primary_soft": "#1e2444",
        }
    else:
        colors = {
            "app_bg": "#f5f7fb",
            "sidebar_bg": "#0b1220",
            "card_bg": "#ffffff",
            "card_border": "#e3e8f0",
            "text": "#101828",
            "text_muted": "#667085",
            "input_bg": "#ffffff",
            "input_border": "#d0d5dd",
            "primary": "#4338ca",
            "primary_hover": "#3730a3",
            "primary_soft": "#eef0ff",
        }

    # Constant across both themes -- the one deliberate accent color.
    spark = "#f59e0b" if not dark else "#fbbf24"
    sidebar_text = "#f5f7fb"
    sidebar_muted = "#8a93ae"
    sidebar_hover = "rgba(255, 255, 255, 0.06)"
    sidebar_active = "rgba(99, 102, 241, 0.22)"

    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    #MainMenu,
    header,
    footer {{
        visibility: hidden;
    }}

    html, body, [class*="css"] {{
        font-family: 'IBM Plex Sans', sans-serif;
    }}

    .stApp {{
        background: {colors["app_bg"]};
    }}

    .block-container {{
        padding: 1rem 1rem 1.5rem;
    }}

    div[data-testid="stVerticalBlock"] {{
        gap: 0.6rem;
    }}

    h1, h2, h3, .stApp [data-testid="stMarkdownContainer"] h1,
    .stApp [data-testid="stMarkdownContainer"] h2,
    .stApp [data-testid="stMarkdownContainer"] h3 {{
        font-family: 'Sora', sans-serif;
        letter-spacing: -0.01em;
    }}

    /* ---------------- Sidebar: constant dark ink, both themes ---------------- */

    section[data-testid="stSidebar"] {{
        background: {colors["sidebar_bg"]};
        border-right: 1px solid rgba(255, 255, 255, 0.06);
    }}

    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] label {{
        color: {sidebar_text};
    }}

    section[data-testid="stSidebar"] hr {{
        border-color: rgba(255, 255, 255, 0.08);
    }}

    .brand-lockup {{
        display: flex;
        align-items: center;
        gap: 0.6rem;
        margin: 0.2rem 0 0.9rem 0;
    }}

    .brand-mark {{
        width: 36px;
        height: 36px;
        border-radius: 10px;
        background: linear-gradient(135deg, {colors["primary"]}, {spark});
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Sora', sans-serif;
        font-weight: 700;
        font-size: 1.1rem;
        color: #ffffff;
        flex-shrink: 0;
    }}

    .brand-name {{
        font-family: 'Sora', sans-serif;
        font-weight: 700;
        font-size: 1.25rem;
        color: {sidebar_text};
    }}

    .status-pill {{
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        padding: 0.3rem 0.7rem;
        border-radius: 999px;
        background: rgba(245, 158, 11, 0.14);
        color: {spark};
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        margin-bottom: 0.6rem;
    }}

    .pulse-dot {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: {spark};
        box-shadow: 0 0 0 rgba(245, 158, 11, 0.5);
        animation: pulse-glow 2s infinite;
    }}

    @keyframes pulse-glow {{
        0% {{ box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.45); }}
        70% {{ box-shadow: 0 0 0 7px rgba(245, 158, 11, 0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }}
    }}

    .user-card {{
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding: 0.6rem 0.7rem;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.05);
        margin-bottom: 0.6rem;
    }}

    .user-avatar {{
        width: 34px;
        height: 34px;
        border-radius: 50%;
        background: {colors["primary"]};
        color: #ffffff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: 'Sora', sans-serif;
        font-weight: 700;
        font-size: 0.85rem;
        flex-shrink: 0;
    }}

    .user-name {{
        font-weight: 600;
        font-size: 0.9rem;
        color: {sidebar_text};
        line-height: 1.2;
    }}

    .user-email {{
        font-size: 0.75rem;
        color: {sidebar_muted};
        font-family: 'IBM Plex Mono', monospace;
    }}

    .sidebar-label {{
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: {sidebar_muted};
        margin: 0.9rem 0 0.35rem 0;
    }}

    .session-id-tag {{
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75rem;
        color: {sidebar_muted};
        background: rgba(255, 255, 255, 0.05);
        padding: 0.25rem 0.55rem;
        border-radius: 6px;
        display: inline-block;
    }}

    /* Sidebar nav-style buttons (New Chat / Clear Chat / session list) */
    section[data-testid="stSidebar"] .stButton > button {{
        background: transparent;
        border: 1px solid rgba(255, 255, 255, 0.10);
        color: {sidebar_text};
        font-weight: 500;
        text-align: left;
        justify-content: flex-start;
        border-radius: 10px;
        transition: background 0.15s ease, border-color 0.15s ease;
    }}

    section[data-testid="stSidebar"] .stButton > button:hover {{
        background: {sidebar_hover};
        border-color: rgba(255, 255, 255, 0.18);
        color: {sidebar_text};
    }}

    section[data-testid="stSidebar"] .stButton > button[kind="primary"] {{
        background: {sidebar_active};
        border: 1px solid {colors["primary"]};
        border-left: 3px solid {spark};
        color: #ffffff;
        font-weight: 600;
    }}

    section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {{
        background: {sidebar_active};
        border-color: {colors["primary"]};
    }}

    /* ---------------- Main content cards & chat ---------------- */

    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background: {colors["card_bg"]};
        border: 1px solid {colors["card_border"]};
        border-radius: 18px;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
    }}

    [data-testid="stChatMessage"] {{
        background: {colors["card_bg"]};
        border: 1px solid {colors["card_border"]};
        border-radius: 18px;
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
        margin-bottom: 0.5rem;
        padding: 0.6rem 1rem;
    }}

    [data-testid="stChatMessageContent"] {{
        color: {colors["text"]};
        font-family: 'IBM Plex Sans', sans-serif;
    }}

    /* Assistant messages get a soft indigo tint; user messages stay neutral */
    [data-testid="stChatMessage"]:has([data-testid*="Assistant"]) {{
        background: {colors["primary_soft"]};
        border-color: {colors["primary_soft"]};
    }}

    .typing-dots {{
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 0.2rem 0;
    }}

    .typing-dots span {{
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: {colors["primary"]};
        display: inline-block;
        animation: typing-bounce 1.1s infinite ease-in-out;
    }}

    .typing-dots span:nth-child(2) {{ animation-delay: 0.15s; }}
    .typing-dots span:nth-child(3) {{ animation-delay: 0.3s; }}

    @keyframes typing-bounce {{
        0%, 60%, 100% {{ transform: translateY(0); opacity: 0.5; }}
        30% {{ transform: translateY(-5px); opacity: 1; }}
    }}

    @media (prefers-reduced-motion: reduce) {{
        .pulse-dot, .typing-dots span {{
            animation: none !important;
        }}
    }}

    .stTextInput input {{
        min-height: 54px;
        border: 1px solid {colors["input_border"]};
        border-radius: 14px;
        background: {colors["input_bg"]};
        color: {colors["text"]};
        font-family: 'IBM Plex Sans', sans-serif;
        font-size: 1rem;
        padding: 0 1rem;
    }}

    .stTextInput input:focus {{
        border-color: {colors["primary"]};
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.16);
    }}

    .stButton > button,
    .stFormSubmitButton > button {{
        min-height: 48px;
        border: 0;
        border-radius: 14px;
        background: {colors["primary"]};
        color: #ffffff;
        font-weight: 600;
        font-family: 'IBM Plex Sans', sans-serif;
    }}

    .stButton > button:hover,
    .stFormSubmitButton > button:hover {{
        background: {colors["primary_hover"]};
        color: #ffffff;
    }}

    iframe {{
        border-radius: 14px;
        min-height: 48px;
    }}

    div[data-testid="stHorizontalBlock"] {{
        align-items: center;
    }}

    @media (max-width: 768px) {{
        .block-container {{
            padding-left: 0.75rem;
            padding-right: 0.75rem;
        }}
    }}

    .document-card{{
    background:{colors["card_bg"]};
    border:1px solid {colors["card_border"]};
    border-radius:10px;
    padding:6px 10px;
    margin-bottom:4px;
    border-left: 3px solid {colors["primary"]};
        }}

    .document-name{{
    font-size:14px;
    font-weight:500;
    font-family: 'IBM Plex Mono', monospace;
    color:{colors["text"]};
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    }}

    div[data-testid="column"] button[kind="secondary"] {{
        min-height: 34px;
        padding: 0 0.5rem;
    }}

    [data-testid="stExpander"] {{
        background: {colors["card_bg"]};
        border: 1px solid {colors["card_border"]};
        border-radius: 14px;
    }}

    [data-testid="stExpander"] summary {{
        font-family: 'Sora', sans-serif;
        font-weight: 600;
    }}
    </style>
    """


st.markdown(build_theme_css(st.session_state.dark_mode), unsafe_allow_html=True)


def render_theme_toggle() -> None:
    """Dark mode switch shown at the top of the sidebar on every page."""
    dark = st.toggle(
        "🌙 Dark Mode",
        value=st.session_state.dark_mode,
        key="dark_mode_toggle",
    )
    if dark != st.session_state.dark_mode:
        st.session_state.dark_mode = dark
        st.rerun()


def render_brand() -> None:
    """Sidebar logo lockup: mark + wordmark, shown on every page."""
    st.markdown(
        """
        <div class="brand-lockup">
            <div class="brand-mark">S</div>
            <div class="brand-name">Scaller AI</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def initials(name: str) -> str:
    """First letters of up to two words in a name, for the avatar circle."""
    parts = [part for part in (name or "").split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


# ==========================================================
# Authentication pages
# ==========================================================

def render_login() -> None:
    with st.sidebar:
        render_theme_toggle()
        render_brand()
        st.info("Please log in to continue.")

    with st.container(border=True):
        st.title("🤖 Scaller AI Assistant")
        st.caption("Log in to continue your private Scaller Technologies chats.")

    show_notice()

    with st.container(border=True):
        st.subheader("Login")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True, type="primary")

        if submitted:
            try:
                response = requests.post(
                    f"{API_URL}/login",
                    json={"email": email, "password": password},
                    timeout=10,
                )
                if response.status_code >= 400:
                    set_notice("error", friendly_error(response, "Login failed. Please try again."))
                    st.rerun()
                set_logged_in(response.json())
                set_notice("success", "Welcome back.")
                st.rerun()
            except Exception as e:
                st.exception(e)
                st.rerun()
            except (ValueError, KeyError):
                set_notice("error", "Login returned an unexpected response.")
                st.rerun()

        if st.button("Create a new account", use_container_width=True):
            st.session_state.auth_page = "signup"
            st.rerun()


def render_signup() -> None:
    with st.sidebar:
        render_theme_toggle()
        render_brand()
        st.info("Create your account.")

    with st.container(border=True):
        st.title("🤖 Scaller AI Assistant")
        st.caption("Sign up to keep your chat history private and available later.")

    show_notice()

    with st.container(border=True):
        st.subheader("Sign Up")
        with st.form("signup_form"):
            full_name = st.text_input("Full Name")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submitted = st.form_submit_button("Sign Up", use_container_width=True, type="primary")

        if submitted:
            try:
                response = requests.post(
                    f"{API_URL}/signup",
                    json={
                        "full_name": full_name,
                        "email": email,
                        "password": password,
                        "confirm_password": confirm_password,
                    },
                    timeout=10,
                )
                if response.status_code >= 400:
                    set_notice("error", friendly_error(response, "Signup failed. Please try again."))
                    st.rerun()
                set_logged_in(response.json())
                set_notice("success", "Your account is ready.")
                st.rerun()
            except RequestException:
                set_notice("error", "Signup failed because the backend could not be reached.")
                st.rerun()
            except (ValueError, KeyError):
                set_notice("error", "Signup returned an unexpected response.")
                st.rerun()

        if st.button("Already have an account? Login", use_container_width=True):
            st.session_state.auth_page = "login"
            st.rerun()


# ==========================================================
# Chat page
# ==========================================================

def session_label(session: dict) -> str:
    preview = (session.get("last_message") or "New chat").strip().replace("\n", " ")
    if len(preview) > 34:
        preview = preview[:31] + "..."
    return preview


def render_sidebar() -> None:
    user = st.session_state.user or {}

    with st.sidebar:
        render_theme_toggle()
        render_brand()

        st.markdown(
            '<div class="status-pill"><span class="pulse-dot"></span>Online</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <div class="user-card">
                <div class="user-avatar">{initials(user.get("full_name", "User"))}</div>
                <div>
                    <div class="user-name">{user.get("full_name", "User")}</div>
                    <div class="user-email">{user.get("email", "")}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("Logout", use_container_width=True):
            logout()
            st.rerun()

        st.divider()

        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            start_new_chat()
            st.rerun()

        if st.button("🧹 Clear Chat", use_container_width=True):
            clear_chat()
            st.rerun()

        st.markdown('<div class="sidebar-label">Current Session</div>', unsafe_allow_html=True)
        st.markdown(
            f'<span class="session-id-tag">{st.session_state.session_id[:8]}</span>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="sidebar-label">Chat History</div>', unsafe_allow_html=True)

        if not st.session_state.chat_sessions:
            st.caption("No previous chats yet.")
        else:
            for session in st.session_state.chat_sessions:
                session_id = session["session_id"]
                button_type = (
                    "primary"
                    if session_id == st.session_state.session_id
                    else "secondary"
                )

                if st.button(
                    session_label(session),
                    key=f"session_{session_id}",
                    use_container_width=True,
                    type=button_type,
                ):
                    load_messages(session_id)
                    st.rerun()


def render_chat() -> None:
    if not st.session_state.session_id:
        start_new_chat()

    render_sidebar()

    with st.container(border=True):
        st.title("🤖 Scaller AI Assistant")
        st.caption("Ask anything about Scaller Technologies using text or voice.")

    show_notice()

    st.subheader("Chat History")

    if not st.session_state.messages:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown("Hi, I am ready to help with Scaller Technologies.")

    for message in st.session_state.messages:
        avatar = "👤" if message["role"] == "user" else "🤖"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    # =====================================================
    # Uploaded Documents
    # =====================================================

    with st.expander(
        f"📎 Knowledge Base — {len(st.session_state.documents)} file(s)",
        expanded=True,
    ):
        uploaded_file = st.file_uploader(
            "📤 Upload Document",
            type=["pdf", "docx", "txt"],
            key=f"document_uploader_{st.session_state.uploader_key}",
        )

        if uploaded_file is not None:
            upload_key = f"{uploaded_file.name}:{uploaded_file.size}"

            if st.session_state.last_uploaded_key != upload_key:
                st.session_state.last_uploaded_key = upload_key

                upload_document(uploaded_file)

                st.session_state.uploader_key += 1
                st.session_state.last_uploaded_key = ""

                st.rerun()

        if not st.session_state.documents:
            st.info("No documents uploaded. Add a PDF, DOCX or TXT to build your knowledge base.")
        else:
            for document in st.session_state.documents:
                doc_id = document["document_id"]

                left, right = st.columns([20, 1], vertical_alignment="center")

                with left:
                    st.markdown(
                        f"""
                        <div class="document-card">
                            <div class="document-name">
                                {document_icon(document["file_type"])} {document["original_filename"]}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                with right:
                    if st.button(
                        "🗑️",
                        key=f"delete_doc_{doc_id}",
                        help="Delete document",
                    ):
                        delete_document(doc_id)
                        st.rerun()

    # =====================================================
    # Ask Question
    # =====================================================

    with st.container(border=True):
        st.subheader("💬 Ask your question")

        input_placeholder = st.empty()
        controls_container = st.container()

        with controls_container:
            voice_col, send_col = st.columns(2, gap="small")

            with voice_col:
                audio_result = mic_recorder(
                    start_prompt="🎤 Voice",
                    stop_prompt="Stop",
                    just_once=True,
                    use_container_width=True,
                    format="webm",
                    key="voice_recorder",
                )

            with send_col:
                send_clicked = st.button(
                    "➤ Send",
                    use_container_width=True,
                    type="primary",
                )

        if audio_result:
            transcribe_audio(audio_result)

        if send_clicked or st.session_state.submit_message:
            submit_current_message()

        show_notice()

        with input_placeholder:
            st.text_input(
                "Question",
                key="message_text",
                placeholder="Ask anything about Scaller Technologies...",
                label_visibility="collapsed",
                on_change=request_submit,
            )

    st.divider()
    st.caption("Powered by FastAPI • Groq Whisper • Streamlit • WebSocket")


if st.session_state.user and st.session_state.auth_token:
    render_chat()
elif st.session_state.auth_page == "signup":
    render_signup()
else:
    render_login()