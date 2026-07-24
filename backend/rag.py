import os

from dotenv import load_dotenv
from groq import Groq

from embedding import embed_query
from vector_store import query_user_chunks, user_has_documents

load_dotenv()

# Groq Client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

TOP_K_CHUNKS = 5

NO_DOCUMENTS_MESSAGE = (
    "You haven't uploaded any documents yet. Please upload a PDF, DOCX, "
    "or TXT file so I can answer questions about it."
)


def build_prompt(question: str, context: str, history_text: str) -> str:
    """Assemble the grounded RAG prompt sent to Groq."""
    return f"""
You are Scaller AI.

Answer ONLY using the retrieved document context below.

Rules:
- If the answer is not present inside the uploaded documents, clearly say:
  "I couldn't find this information in your uploaded documents."
- Do not hallucinate.
- Do not invent information.
- Use the conversation history only to understand follow-up questions.
- Give the direct answer first, without mentioning "context", "chunks", or "database".

Conversation History:
{history_text}

Retrieved Document Context:
{context}

Current Question:
{question}
"""


def search(question: str, history, user_id: int) -> str:
    """Answer a question using only the requesting user's uploaded documents.

    history: list of {"question": ..., "answer": ...} dicts (most recent last).
    user_id: the authenticated user's id, used to scope retrieval so a user
             never sees another user's document chunks.
    """
    if not user_has_documents(user_id):
        return NO_DOCUMENTS_MESSAGE

    # -----------------------------
    # Retrieve relevant chunks (embeddings generated only for the query;
    # stored chunk embeddings were already computed once at upload time)
    # -----------------------------
    query_embedding = embed_query(question)
    retrieved_chunks = query_user_chunks(user_id, query_embedding, top_k=TOP_K_CHUNKS)

    if not retrieved_chunks:
        return "I couldn't find this information in your uploaded documents."

    context = "\n\n".join(
        f"[From {chunk['filename']}]\n{chunk['text']}" for chunk in retrieved_chunks
    )

    # -----------------------------
    # Conversation history
    # -----------------------------
    history_text = ""
    for chat in history:
        history_text += f"User: {chat['question']}\n"
        history_text += f"Assistant: {chat['answer']}\n\n"

    prompt = build_prompt(question, context, history_text)

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0,
    )

    return response.choices[0].message.content