import streamlit as st
import websocket
import uuid
import json
import requests
from streamlit_mic_recorder import speech_to_text

# -----------------------------------
# Backend URL
# -----------------------------------
LOCAL = True

if LOCAL:
    WS_URL = "ws://127.0.0.1:8000/ws"
    API_URL = "http://127.0.0.1:8000"
else:
    WS_URL = "wss://scaller-bot.onrender.com/ws"
    API_URL = "https://scaller-bot.onrender.com"

# -----------------------------------
# Page Config
# -----------------------------------
st.set_page_config(
    page_title="Scaller AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------
# Session State
# -----------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

# -----------------------------------
# Custom CSS
# -----------------------------------
st.markdown("""
<style>

/* Hide Streamlit Menu */
#MainMenu{
    visibility:hidden;
}

footer{
    visibility:hidden;
}

header{
    visibility:hidden;
}

/* Background */
.stApp{
    background:linear-gradient(135deg,#EEF5FF,#DDEEFF);
}

/* Main Container */
.block-container{
    max-width:1000px;
    padding-top:1.5rem;
    padding-bottom:2rem;
}

/* Header Card */
.header-card{
    background:white;
    border-radius:18px;
    padding:25px;
    text-align:center;
    box-shadow:0px 4px 15px rgba(0,0,0,0.08);
    margin-bottom:25px;
}

.header-title{
    font-size:34px;
    font-weight:bold;
    color:#1D4ED8;
}

.header-subtitle{
    font-size:17px;
    color:#6B7280;
    margin-top:8px;
}

/* Sidebar */
section[data-testid="stSidebar"]{
    background:#1E3A8A;
}

section[data-testid="stSidebar"] *{
    color:white;
}

/* Buttons */
.stButton>button{
    width:100%;
    border-radius:12px;
    height:46px;
    border:none;
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

.header-title{
    font-size:26px;
}

.header-subtitle{
    font-size:15px;
}

}

</style>
""", unsafe_allow_html=True)

# -----------------------------------
# Sidebar
# -----------------------------------
with st.sidebar:

    st.title("🤖 Scaller AI")

    st.success("🟢 Online")

    st.write("---")

    st.markdown("### Session")

    st.caption("Active Conversation")

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
        st.session_state.session_id = str(uuid.uuid4())

        st.rerun()

    st.write("---")

    st.caption("Scaller Technologies AI Assistant")

# -----------------------------------
# Header
# -----------------------------------
st.markdown("""
<div class="header-card">

<div class="header-title">
🤖 Scaller AI Assistant
</div>

<div class="header-subtitle">
Ask anything about Scaller Technologies
</div>

</div>
""", unsafe_allow_html=True)
# -----------------------------------
# Display Chat History
# -----------------------------------
for message in st.session_state.messages:

    avatar = "👤" if message["role"] == "user" else "🤖"

    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])


# -----------------------------------
# Input Area
# -----------------------------------
col1, col2 = st.columns([6,1])

with col1:

    question = st.chat_input(
        "Ask anything about Scaller Technologies..."
    )

with col2:

    st.write("")

    st.write("")

    voice_text = speech_to_text(
    language="en",
    use_container_width=True,
    just_once=True,
    key="voice_input"
)

if voice_text:
    question = voice_text


# -----------------------------------
# Process Question
# -----------------------------------
if question:

    # Show User Message
    st.session_state.messages.append(
        {
            "role":"user",
            "content":question
        }
    )

    with st.chat_message("user", avatar="👤"):

        st.markdown(question)

    # Assistant Thinking
    with st.chat_message("assistant", avatar="🤖"):

        thinking = st.empty()

        thinking.markdown("⏳ **Thinking...**")

        try:

            ws = websocket.create_connection(WS_URL)

            ws.send(
                json.dumps(
                    {
                        "session_id":st.session_state.session_id,
                        "question":question
                    }
                )
            )

            response = json.loads(
                ws.recv()
            )

            ws.close()

            answer = response["answer"]

        except Exception as e:

            answer = f"❌ Connection Error\n\n{e}"

        thinking.empty()

        st.markdown(answer)

    # Save Assistant Response
    st.session_state.messages.append(
        {
            "role":"assistant",
            "content":answer
        }
    )

# -----------------------------------
# Footer
# -----------------------------------
st.markdown("---")

left,right = st.columns([1,1])

with left:

    st.caption("🟢 Connected")

with right:

    st.caption("Powered by FastAPI • Groq • WebSocket")