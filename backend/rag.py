import os

from dotenv import load_dotenv
from groq import Groq
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Groq Client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Load Company Data
with open(os.path.join(BASE_DIR, "data.txt"), "r", encoding="utf-8") as file:
    documents = file.read().split("--------------------------------")

# Create TF-IDF Vector Database
vectorizer = TfidfVectorizer()
document_vectors = vectorizer.fit_transform(documents)


def search(question, history):
    original_question = question

    # -----------------------------
    # Normalize Question
    # -----------------------------
    question = question.lower()

    if "team" in question:
        question += " ceo cto hr manager project manager leadership"

    if "staff" in question:
        question += " team employees"

    if "employee" in question or "employees" in question:
        question += " team staff"

    if "management" in question:
        question += " ceo cto leadership"

    # -----------------------------
    # Build Search Query
    # -----------------------------
    search_query = question

    if history:

        previous_context = ""

        for chat in history:
            previous_context += chat["question"] + " "
            previous_context += chat["answer"] + " "

        search_query = previous_context + " " + question

    # -----------------------------
    # Retrieve Documents
    # -----------------------------
    question_vector = vectorizer.transform([search_query])

    similarity = cosine_similarity(question_vector, document_vectors)[0]

    # Retrieve top 5 chunks
    top_indices = similarity.argsort()[-5:][::-1]

    context = ""

    for index in top_indices:
        context += documents[index] + "\n\n"

    # -----------------------------
    # Conversation History
    # -----------------------------
    history_text = ""

    for chat in history:
        history_text += f"User: {chat['question']}\n"
        history_text += f"Assistant: {chat['answer']}\n\n"

    # -----------------------------
    # Prompt
    # -----------------------------
    prompt = f"""
You are a precise AI assistant for Scaller Technologies.

Use the conversation history only to understand follow-up questions.

Answer using only the company information below.

Rules:
- Give the direct answer first.
- Do not mention "database", "provided information", "company information", "context", or "data".
- Do not explain retrieval or limitations unless the answer is missing.
- Do not invent facts, names, dates, numbers, or services.
- If the user asks about the team, list the known team members and their roles clearly.
- If the answer is completely missing, reply exactly: I don't have that information.

Conversation History:
{history_text}

Company Information:
{context}

Current Question:
{original_question}
"""

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
