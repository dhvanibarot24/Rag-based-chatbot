import streamlit as st
import websocket
import uuid
import json
import requests
from streamlit_mic_recorder import speech_to_text

# ==========================================================
# BACKEND CONFIG
# ==========================================================

LOCAL = True

if LOCAL:
    WS_URL = "ws://127.0.0.1:8000/ws"
    API_URL = "http://127.0.0.1:8000"
else:
    WS_URL = "wss://scaller-bot.onrender.com/ws"
    API_URL = "https://scaller-bot.onrender.com"

# ==========================================================
# PAGE CONFIG
# ==========================================================

st.set_page_config(
    page_title="Scaller AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================================
# SESSION STATE
# ==========================================================

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "chat_input" not in st.session_state:
    st.session_state.chat_input = ""

# ✅ Fixed missing session state
if "voice_text" not in st.session_state:
    st.session_state.voice_text = ""

# ==========================================================
# CUSTOM CSS
# ==========================================================

st.markdown("""
<style>

/* Hide Streamlit UI */

#MainMenu{
    visibility:hidden;
}

header{
    visibility:hidden;
}

footer{
    visibility:hidden;
}

/* Background */

.stApp{
    background:linear-gradient(135deg,#EEF5FF,#DCEEFF);
}

/* Main Width */

.block-container{
    max-width:950px;
    padding-top:20px;
    padding-bottom:20px;
}

/* Sidebar */

section[data-testid="stSidebar"]{
    background:#1E3A8A;
}

section[data-testid="stSidebar"] *{
    color:white;
}

/* Header */

.header{
    background:white;
    padding:25px;
    border-radius:18px;
    box-shadow:0px 5px 18px rgba(0,0,0,.08);
    margin-bottom:25px;
    text-align:center;
}

.header h1{
    color:#2563EB;
    margin-bottom:8px;
}

.header p{
    color:#6B7280;
    font-size:17px;
}

/* Chat */

[data-testid="stChatMessage"]{
    background:white;
    border-radius:18px;
    padding:12px;
    margin-bottom:10px;
    box-shadow:0px 2px 8px rgba(0,0,0,.05);
}

/* Textbox */

.stTextInput input{
    height:56px;
    border-radius:16px;
    border:2px solid #D9E2F2 !important;
    background:#F9FBFF;
    font-size:16px;
    padding-left:18px;
    transition:all .25s;
}

.stTextInput input:focus{
    border:2px solid #2563EB !important;
    background:white;
    box-shadow:0px 0px 12px rgba(37,99,235,.18);
}

/* Buttons */

.stButton button{
    height:56px;
    border-radius:16px;
    background:#2563EB;
    color:white;
    font-size:22px;
    font-weight:700;
    border:none;
    transition:.25s;
}

.stButton button:hover{
    background:#1D4ED8;
    transform:translateY(-2px);
}

/* Mobile */

@media(max-width:768px){

.block-container{
padding-left:15px;
padding-right:15px;
}

.header h1{
font-size:28px;
}

.header p{
font-size:15px;
}

}

</style>
""", unsafe_allow_html=True)

# ==========================================================
# SIDEBAR
# ==========================================================

with st.sidebar:

    st.title("🤖 Scaller AI")

    st.success("🟢 Online")

    st.write("")

    st.markdown("### Session")

    st.caption("Conversation Active")

    if st.button("🗑️ Clear Chat"):

        try:
            requests.delete(
                f"{API_URL}/clear-session",
                json={
                    "session_id": st.session_state.session_id
                }
            )

        except Exception:
            pass

        st.session_state.messages = []
        st.session_state.chat_input = ""
        st.session_state.voice_text = ""
        st.session_state.session_id = str(uuid.uuid4())

        st.rerun()
# ==========================================================
# HEADER
# ==========================================================

st.markdown("""
<div class="header">
    <h1>🤖 Scaller AI Assistant</h1>
    <p>
        Ask anything about Scaller Technologies using text or voice.
    </p>
</div>
""", unsafe_allow_html=True)

# ==========================================================
# CHAT HISTORY
# ==========================================================

for message in st.session_state.messages:

    avatar = "👤" if message["role"] == "user" else "🤖"

    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])


# ==========================================================
# VOICE INPUT
# ==========================================================

st.markdown("""
<div style="
font-size:15px;
font-weight:600;
color:#2563EB;
margin-bottom:8px;
">
🎤 Voice Input
</div>
""", unsafe_allow_html=True)

voice = speech_to_text(
    language="en",
    start_prompt="Start Speaking",
    stop_prompt="⏹ Stop Recording",
    just_once=True,
    use_container_width=False,
    key="voice"
)

if voice:
    st.session_state.voice_text = voice

# ==========================================================
# CHAT FORM
# ==========================================================

st.subheader("💬 Ask your question")

with st.form("chat_form", clear_on_submit=True):

    col1, col2 = st.columns([9, 1])

    with col1:

        question = st.text_input(
            "",
            value=st.session_state.get("voice_text", ""),
            placeholder="Ask anything about Scaller Technologies...",
            label_visibility="collapsed"
        )

    with col2:

        send = st.form_submit_button("➤", use_container_width=True)

    if send:

        question = question.strip()

        if not question:

            st.warning("Please enter a question.")

        else:

            st.session_state.messages.append(
                {
                    "role": "user",
                    "content": question
                }
            )

            ws = None

            try:

                with st.spinner("🤖 Thinking..."):

                    ws = websocket.create_connection(WS_URL)

                    ws.send(
                        json.dumps(
                            {
                                "session_id": st.session_state.session_id,
                                "question": question
                            }
                        )
                    )

                    response = json.loads(ws.recv())

                    answer = response.get(
                        "answer",
                        "I don't have an answer."
                    )

            except Exception as e:

                answer = (
                    "⚠️ Unable to connect to the server.\n\n"
                    "Please make sure the FastAPI backend is running.\n\n"
                    f"Error: {e}"
                )

            finally:

                if ws:
                    ws.close()

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer
                }
            )

            st.session_state.voice_text = ""

            st.rerun()
# ==========================================================
# FOOTER
# ==========================================================

st.markdown("---")

st.markdown(
    """
    <div style="
        text-align:center;
        color:#6B7280;
        font-size:14px;
        padding-bottom:15px;
    ">

    🤖 <b>Scaller AI Assistant</b><br>

    Powered by FastAPI • Streamlit • WebSocket

    </div>
    """,
    unsafe_allow_html=True
)