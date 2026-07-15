import streamlit as st
import websocket
import uuid
import json
import requests
import streamlit.components.v1 as components
from streamlit_mic_recorder import speech_to_text
# ==========================================================
# BACKEND URL
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

# ==========================================================
# CSS
# ==========================================================

st.markdown("""
<style>

/* Hide Streamlit */
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

/* Main Container */
.block-container{
max-width:950px;
padding-top:20px;
padding-bottom:20px;
}

/* Header */

.main-header{
background:white;
border-radius:20px;
padding:25px;
box-shadow:0 5px 20px rgba(0,0,0,.08);
margin-bottom:20px;
text-align:center;
}

.title{
font-size:34px;
font-weight:700;
color:#2563EB;
}

.subtitle{
color:#6B7280;
font-size:17px;
margin-top:8px;
}

/* Sidebar */

section[data-testid="stSidebar"]{
background:#1E3A8A;
}

section[data-testid="stSidebar"] *{
color:white;
}

/* Chat */

[data-testid="stChatMessage"]{

border-radius:15px;
padding:5px;
margin-bottom:8px;

}

/* Buttons */

.stButton>button{

width:100%;
height:46px;

border:none;
border-radius:12px;

background:#2563EB;
color:white;

font-weight:bold;

}

.stButton>button:hover{

background:#1D4ED8;

}

/* Chat Input */

[data-testid="stChatInput"]{

position:sticky;
bottom:0;

}

/* Mobile */

@media(max-width:768px){

.block-container{

padding:15px;

}

.title{

font-size:27px;

}

.subtitle{

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
                    "session_id":st.session_state.session_id
                }

            )

        except:

            pass

        st.session_state.messages=[]

        st.session_state.session_id=str(uuid.uuid4())

        st.rerun()



# ==========================================================
# HEADER
# ==========================================================

st.markdown("""

<div class="main-header">

<div class="title">

🤖 Scaller AI Assistant

</div>

<div class="subtitle">

Ask anything about Scaller Technologies using text or voice.

</div>

</div>

""",unsafe_allow_html=True)

# ==========================================================
# CHAT HISTORY
# ==========================================================

for message in st.session_state.messages:

    avatar="👤" if message["role"]=="user" else "🤖"

    with st.chat_message(message["role"],avatar=avatar):

        st.markdown(message["content"])

# ==========================================================
# INPUT SECTION
# ==========================================================

# Store voice text separately
if "voice_text" not in st.session_state:
    st.session_state.voice_text = ""

# -----------------------------
# Voice Input
# -----------------------------

st.markdown("### 🎤 Speak")

voice = speech_to_text(
    language="en",
    start_prompt="🎤 Start Speaking",
    stop_prompt="⏹ Stop",
    just_once=True,
    use_container_width=True,
    key="voice"
)

# If speech is recognized,
# fill the textbox and rerun.
if voice:

    st.session_state.voice_text = voice

    st.rerun()

# -----------------------------
# Input Row
# -----------------------------

col1, col2 = st.columns([8,1])

with col1:

    typed_text = st.text_input(
        "",
        value=st.session_state.voice_text,
        key="chat_input",
        placeholder="Ask anything about Scaller Technologies...",
        label_visibility="collapsed"
    )

with col2:

    send = st.button(
        "➤",
        use_container_width=True
    )

question = None

if send:

    question = typed_text.strip()

    # Clear only our own variable
    st.session_state.voice_text = ""

# ==========================================================
# FOOTER
# ==========================================================

st.markdown("---")

c1 = st.columns(1)

with c1:
    st.caption("💬 Text & Voice Assistant")

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

        except:
            pass

        st.session_state.messages = []
        st.session_state.chat_input = ""
        st.session_state.session_id = str(uuid.uuid4())

        st.rerun()

# ==========================================================
# HEADER
# ==========================================================

st.markdown(
"""
<div class="main-header">

<div class="title">
🤖 Scaller AI Assistant
</div>

<div class="subtitle">
Ask anything about Scaller Technologies using text or voice.
</div>

</div>
""",
unsafe_allow_html=True
)

# ==========================================================
# CHAT HISTORY
# ==========================================================

for message in st.session_state.messages:

    avatar = "👤" if message["role"] == "user" else "🤖"

    with st.chat_message(message["role"], avatar=avatar):

        st.markdown(message["content"])

# ==========================================================
# INPUT SECTION
# ==========================================================

st.write("")

col1, col2, col3 = st.columns([8,1,1])

# -----------------------------
# TEXT INPUT
# -----------------------------

with col1:

    typed_text = st.text_input(
        "",
        key="chat_input",
        placeholder="Ask anything about Scaller Technologies...",
        label_visibility="collapsed"
    )

# -----------------------------
# MICROPHONE
# -----------------------------

with col2:

    voice = speech_to_text(
        language="en",
        start_prompt="🎤",
        stop_prompt="⏹",
        just_once=True,
        use_container_width=True,
        key="voice"
    )

# -----------------------------
# SEND BUTTON
# -----------------------------

with col3:

    send = st.button(
        "➤",
        use_container_width=True
    )

# ==========================================================
# VOICE UX
# ==========================================================

if voice:

    st.session_state.listening = True

    with st.spinner("🎙️ Recognizing your voice..."):

        st.session_state.chat_input = voice

    st.session_state.listening = False

    st.rerun()
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

        except:
            pass

        st.session_state.messages = []
        st.session_state.chat_input = ""
        st.session_state.session_id = str(uuid.uuid4())

        st.rerun()

# ==========================================================
# HEADER
# ==========================================================

st.markdown(
"""
<div class="main-header">

<div class="title">
🤖 Scaller AI Assistant
</div>

<div class="subtitle">
Ask anything about Scaller Technologies using text or voice.
</div>

</div>
""",
unsafe_allow_html=True
)

# ==========================================================
# CHAT HISTORY
# ==========================================================

for message in st.session_state.messages:

    avatar = "👤" if message["role"] == "user" else "🤖"

    with st.chat_message(message["role"], avatar=avatar):

        st.markdown(message["content"])

# ==========================================================
# INPUT SECTION
# ==========================================================

st.write("")

col1, col2, col3 = st.columns([8,1,1])

# -----------------------------
# TEXT INPUT
# -----------------------------

with col1:

    typed_text = st.text_input(
        "",
        key="chat_input",
        placeholder="Ask anything about Scaller Technologies...",
        label_visibility="collapsed"
    )

# -----------------------------
# MICROPHONE
# -----------------------------

with col2:

    voice = speech_to_text(
        language="en",
        start_prompt="🎤",
        stop_prompt="⏹",
        just_once=True,
        use_container_width=True,
        key="voice"
    )

# -----------------------------
# SEND BUTTON
# -----------------------------

with col3:

    send = st.button(
        "➤",
        use_container_width=True
    )

# ==========================================================
# VOICE UX
# ==========================================================

if voice:

    st.session_state.listening = True

    with st.spinner("🎙️ Recognizing your voice..."):

        st.session_state.chat_input = voice

    st.session_state.listening = False

    st.rerun()
# ==========================================================
# AUTO SCROLL
# ==========================================================

components.html(
    """
    <script>

    const chatContainer = window.parent.document.querySelector("section.main");

    if(chatContainer){
        chatContainer.scrollTo({
            top: chatContainer.scrollHeight,
            behavior: "smooth"
        });
    }

    </script>
    """,
    height=0,
)

# ==========================================================
# FOOTER
# ==========================================================

st.markdown("<br>", unsafe_allow_html=True)

st.markdown("---")

left, center, right = st.columns([1,2,1])

with center:

    st.markdown(
        """
        <div style="
        text-align:center;
        color:#6B7280;
        font-size:14px;
        ">

        🤖 <b>Scaller AI Assistant</b><br>

        Built using Streamlit & FastAPI

        </div>
        """,
        unsafe_allow_html=True
    )

# ==========================================================
# EXTRA CSS
# ==========================================================

st.markdown("""
<style>

/* Better Chat Bubble */

[data-testid="stChatMessage"]{

background:white;

padding:12px;

border-radius:18px;

margin-bottom:12px;

box-shadow:0 2px 10px rgba(0,0,0,.06);

}

/* Input Section */

.stTextInput{

margin-bottom:0px;

}

/* Send Button */

.stButton button{

height:52px !important;

border-radius:14px !important;

font-size:18px;

}

/* Mic Button */

button[kind="secondary"]{

height:52px !important;

border-radius:14px !important;

}

/* Chat Width */

.block-container{

max-width:900px;

}

/* Mobile */

@media (max-width:768px){

.block-container{

padding-left:15px;

padding-right:15px;

}

}

</style>
""",unsafe_allow_html=True)