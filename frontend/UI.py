import streamlit as st
import requests

# Backend API URL
API_URL = "https://scaller-bot.onrender.com/chat"

st.set_page_config(
    page_title="Scaller AI Assistant",
    page_icon="🤖",
    layout="centered"
)

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

st.markdown("<h1>🤖 Scaller Technologies AI Assistant</h1>", unsafe_allow_html=True)

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
                response = requests.post(
                    API_URL,
                    json={"question": question}
                )

                if response.status_code == 200:
                    answer = response.json()["answer"]
                    st.subheader("Answer")
                    st.info(answer)
                else:
                    st.error(f"Server Error: {response.status_code}")

            except Exception as e:
                st.error(f"Error: {e}")