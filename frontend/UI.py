import streamlit as st
import requests

st.set_page_config(
    page_title="Scaller AI Assistant",
    page_icon="🤖"
)

st.title("🤖 Scaller Technologies AI Assistant")

st.write("Ask anything about Scaller Technologies.")

q = st.text_input("Enter your question")

if st.button("Ask"):

    if q == "":
        st.warning("Please enter a question.")

    else:

        with st.spinner("Generating answer..."):

            r = requests.post(
                "http://127.0.0.1:8000/chat",
                json={"question": q}
            )

            a = r.json()

        st.success("Answer Generated")

        st.subheader("Answer")

        st.write(a["answer"])