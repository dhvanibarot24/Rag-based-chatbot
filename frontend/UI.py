import streamlit as st
import requests

st.title("Company Chatbot")

q = st.text_input("Ask a Question")

if st.button("Ask"):

    r = requests.post(
        "http://127.0.0.1:8000/chat",
        json={"question": q}
    )

    a = r.json()

    st.write("Answer")

    st.write(a["answer"])