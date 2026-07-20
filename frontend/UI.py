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

DEFAULT_API_URL = "https://scaller-bot.onrender.com"
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


def logout() -> None:
    st.session_state.auth_token = ""
    st.session_state.user = None
    st.session_state.session_id = ""
    st.session_state.messages = []
    st.session_state.chat_sessions = []
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

    with st.spinner("Scaller AI is thinking..."):
        answer = send_question(question)

    st.session_state.messages.append({"role": "assistant", "content": answer})
    load_sessions()
    st.rerun()


# ==========================================================
# Styling
# ==========================================================

st.markdown(
    """
    <style>
    #MainMenu,
    header,
    footer {
        visibility: hidden;
    }

    .stApp {
        background: #eef5ff;
    }

    .block-container {
        max-width: 980px;
        padding: 1.5rem 1rem 2rem;
    }

    section[data-testid="stSidebar"] {
        background: #123c7c;
    }

    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span {
        color: #ffffff;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #ffffff;
        border: 1px solid #dbeafe;
        border-radius: 18px;
        box-shadow: 0 10px 28px rgba(37, 99, 235, 0.08);
    }

    [data-testid="stChatMessage"] {
        background: #ffffff;
        border: 1px solid #dbeafe;
        border-radius: 18px;
        box-shadow: 0 6px 18px rgba(37, 99, 235, 0.06);
        margin-bottom: 0.75rem;
    }

    [data-testid="stChatMessageContent"] {
        color: #0f172a;
    }

    .stTextInput input {
        min-height: 54px;
        border: 1px solid #bfdbfe;
        border-radius: 14px;
        background: #f8fbff;
        color: #0f172a;
        font-size: 1rem;
        padding: 0 1rem;
    }

    .stTextInput input:focus {
        border-color: #2563eb;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.14);
    }

    .stButton > button,
    .stFormSubmitButton > button {
        min-height: 48px;
        border: 0;
        border-radius: 14px;
        background: #2563eb;
        color: #ffffff;
        font-weight: 700;
    }

    .stButton > button:hover,
    .stFormSubmitButton > button:hover {
        background: #1d4ed8;
        color: #ffffff;
    }

    iframe {
        border-radius: 14px;
    }

    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.75rem;
            padding-right: 0.75rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==========================================================
# Authentication pages
# ==========================================================

def render_login() -> None:
    with st.sidebar:
        st.title("Scaller AI")
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
            except RequestException:
                set_notice("error", "Login failed because the backend could not be reached.")
                st.rerun()
            except (ValueError, KeyError):
                set_notice("error", "Login returned an unexpected response.")
                st.rerun()

        if st.button("Create a new account", use_container_width=True):
            st.session_state.auth_page = "signup"
            st.rerun()


def render_signup() -> None:
    with st.sidebar:
        st.title("Scaller AI")
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
        st.title("Scaller AI")
        st.success("Online")
        st.divider()
        st.subheader(user.get("full_name", "User"))
        st.caption(user.get("email", ""))

        if st.button("Logout", use_container_width=True):
            logout()
            st.rerun()

        st.divider()
        if st.button("New Chat", use_container_width=True, type="primary"):
            start_new_chat()
            st.rerun()

        if st.button("Clear Chat", use_container_width=True):
            clear_chat()
            st.rerun()

        st.divider()
        st.subheader("Current Session")
        st.caption(st.session_state.session_id[:8])

        st.subheader("Chat History")
        if not st.session_state.chat_sessions:
            st.caption("No previous chats yet.")
        else:
            for session in st.session_state.chat_sessions:
                session_id = session["session_id"]
                button_type = "primary" if session_id == st.session_state.session_id else "secondary"
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
