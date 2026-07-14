import streamlit as st
import websocket
import uuid


LOCAL = True

if LOCAL:
    WS_URL = "ws://127.0.0.1:8000/ws"
else:
    WS_URL = "wss://scaller-bot.onrender.com/ws"


st.set_page_config(
    page_title="Scaller AI Assistant",
    page_icon="🤖",
    layout="centered"
)


if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())


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


st.markdown(
    "<h1>🤖 Scaller Technologies AI Assistant</h1>",
    unsafe_allow_html=True
)

st.markdown(
    "<p>Ask anything about Scaller Technologies</p>",
    unsafe_allow_html=True
)

question = st.text_input("Enter your question")


if st.button("Ask"):

    if question.strip() == "":
        st.warning("Please enter a question.")

    else:
        with st.spinner("Generating answer..."):
            try:
                st.write("Connecting to:", WS_URL)

                ws = websocket.create_connection(WS_URL)

                st.success("Connected to WebSocket")

                st.write("Sending:", question)

                ws.send(question)

                answer = ws.recv()

                st.write("Received:", answer)

                ws.close()

                st.subheader("Answer")
                st.info(answer)

            except Exception as e:
                st.error(f"Error: {e}")