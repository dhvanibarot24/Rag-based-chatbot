import streamlit as st
import websocket
import uuid
import json
import requests

# -----------------------------------
# Backend URL
# -----------------------------------
LOCAL = True

if LOCAL:
    WS_URL = "ws://127.0.0.1:8000/ws"
else:
    WS_URL = "wss://scaller-bot.onrender.com/ws"

# -----------------------------------
# Page Config
# -----------------------------------
st.set_page_config(
    page_title="Scaller AI Assistant",
    page_icon="🤖",
    layout="centered"
)

# -----------------------------------
# Session ID
# -----------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# -----------------------------------
# Chat History
# -----------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

# -----------------------------------
# Styling
# -----------------------------------
st.markdown("""
<style>

.stApp{
    background: linear-gradient(135deg,#EEF6FF,#D9EFFF);
}

h1{
    text-align:center;
    color:#1E3A8A;
}

</style>
""", unsafe_allow_html=True)

st.markdown(
    "<h1>🤖 Scaller Technologies AI Assistant</h1>",
    unsafe_allow_html=True
)
# -----------------------------------
# Clear Chat Button
# -----------------------------------
if st.button("🗑️ Clear Chat"):

    try:
        requests.delete(
            "http://127.0.0.1:8000/clear-session",
            json={
                "session_id": st.session_state.session_id
            }
        )
    except:
        pass

    st.session_state.messages = []

    st.session_state.session_id = str(uuid.uuid4())

    st.rerun()
# -----------------------------------
# Display Previous Messages
# -----------------------------------
for message in st.session_state.messages:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# -----------------------------------
# Chat Input
# -----------------------------------
question = st.chat_input("Ask anything about Scaller Technologies...")


# -----------------------------------
# Send Question
# -----------------------------------
if question:

    # Show user message
    st.session_state.messages.append(
        {
            "role": "user",
            "content": question
        }
    )

    with st.chat_message("user"):
        st.markdown(question)

    # Get bot response
    with st.spinner("Thinking..."):

        try:

            # Connect to WebSocket
            ws = websocket.create_connection(WS_URL)

            # Send question
            ws.send(
                json.dumps(
                    {
                        "session_id": st.session_state.session_id,
                        "question": question
                    }
                )
            )

            # Receive response
            response = json.loads(ws.recv())

            ws.close()

            answer = response["answer"]

        except Exception as e:

            answer = f"Connection Error: {e}"

    # Save bot response
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer
        }
    )

    with st.chat_message("assistant"):
        st.markdown(answer)