import hashlib
import json
import os
import uuid

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
    "session_id": str(uuid.uuid4()),
    "messages": [],
    "message_text": "",
    "last_audio_hash": "",
    "submit_message": False,
    "notice": "",
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
    elif level == "warning":
        st.warning(message)
    else:
        st.info(message)

    st.session_state.notice = ""


def set_notice(level: str, message: str) -> None:
    st.session_state.notice = f"{level}:{message}"


def request_submit() -> None:
    """Called when Enter is pressed inside the single textbox."""
    st.session_state.submit_message = True


def reset_chat_state() -> None:
    st.session_state.messages = []
    st.session_state.message_text = ""
    st.session_state.last_audio_hash = ""
    st.session_state.submit_message = False
    st.session_state.session_id = str(uuid.uuid4())


def clear_chat() -> None:
    """Clear backend and frontend chat memory."""
    try:
        response = requests.delete(
            f"{API_URL}/clear-session",
            json={"session_id": st.session_state.session_id},
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

    reset_chat_state()


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
                }
            )
        )
        response = json.loads(ws.recv())
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
# Sidebar
# ==========================================================

with st.sidebar:
    st.title("Scaller AI")
    st.success("Online")
    st.divider()
    st.subheader("Current Session")
    st.caption(st.session_state.session_id[:8])

    if st.button("Clear Chat", use_container_width=True, type="primary"):
        clear_chat()
        st.rerun()


# ==========================================================
# Header
# ==========================================================

with st.container(border=True):
    st.title("🤖 Scaller AI Assistant")
    st.caption("Ask anything about Scaller Technologies using text or voice.")

show_notice()


# ==========================================================
# Chat history
# ==========================================================

st.subheader("Chat History")

if not st.session_state.messages:
    with st.chat_message("assistant", avatar="🤖"):
        st.markdown("Hi, I am ready to help with Scaller Technologies.")

for message in st.session_state.messages:
    avatar = "👤" if message["role"] == "user" else "🤖"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])


# ==========================================================
# Input area
# ==========================================================

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


# ==========================================================
# Footer
# ==========================================================

st.divider()
st.caption("Powered by FastAPI • Groq Whisper • Streamlit • WebSocket")
