import streamlit as st
import websocket
import uuid
import json

# -----------------------------
# WebSocket URL
# -----------------------------
LOCAL = True

if LOCAL:
    WS_URL = "ws://127.0.0.1:8000/ws"
else:
    WS_URL = "wss://scaller-bot.onrender.com/ws"

# -----------------------------
# Streamlit Page Config
# -----------------------------
st.set_page_config(
    page_title="Scaller AI Assistant",
    page_icon="🤖",
    layout="centered"
)

# -----------------------------
# Session ID
# -----------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
st.write("Session ID:", st.session_state.session_id)

# -----------------------------
# CSS
# -----------------------------
st.markdown("""
<style>

.stApp{
    background: linear-gradient(135deg,#EEF6FF,#D9EFFF);
}

h1{
    text-align:center;
    color:#1E3A8A;
}

p{
    text-align:center;
    font-size:18px;
}

div.stButton > button{
    width:100%;
    height:50px;
    border-radius:12px;
    font-size:18px;
    font-weight:bold;
    background-color:#2563EB;
    color:white;
}

</style>
""", unsafe_allow_html=True)

# -----------------------------
# Heading
# -----------------------------
st.markdown(
    "<h1>🤖 Scaller Technologies AI Assistant</h1>",
    unsafe_allow_html=True
)

st.markdown(
    "<p>Ask anything about Scaller Technologies</p>",
    unsafe_allow_html=True
)

# -----------------------------
# Question Input
# -----------------------------
question = st.text_input("Enter your question")

# -----------------------------
# Ask Button
# -----------------------------
if st.button("Ask"):

    if question.strip() == "":
        st.warning("Please enter your question.")

    else:

        with st.spinner("Generating answer..."):

            try:

                # Connect to WebSocket
                ws = websocket.create_connection(WS_URL)

                # Send session id + question
                ws.send(json.dumps({
                    "session_id": st.session_state.session_id,
                    "question": question
                }))

                # Receive response
                response = ws.recv()

                # Convert JSON string to dictionary
                response = json.loads(response)

                # Get answer
                answer = response["answer"]

                # Close WebSocket
                ws.close()

                # Display answer
                st.subheader("Answer")
                st.info(answer)

            except Exception as e:
                st.error(f"Error: {e}")