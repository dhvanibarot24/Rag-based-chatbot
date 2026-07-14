from groq import Groq
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import os

load_dotenv()

# Groq Client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Load Company Data
with open("data.txt", "r", encoding="utf-8") as file:
    documents = file.read().split("--------------------------------")

# Create TF-IDF Vector Database
vectorizer = TfidfVectorizer()
document_vectors = vectorizer.fit_transform(documents)


def search(question, history):

    # -----------------------------
    # Build Search Query
    # -----------------------------
    search_query = question

    if history:

        previous_context = ""

        for chat in history:

            previous_context += chat["question"] + " "
            previous_context += chat["answer"] + " "

        search_query = previous_context + question

    # -----------------------------
    # Retrieve Documents
    # -----------------------------
    question_vector = vectorizer.transform([search_query])

    similarity = cosine_similarity(
        question_vector,
        document_vectors
    )[0]
        # -----------------------------
    # Get Top 3 Matching Chunks
    # -----------------------------
    top_indices = similarity.argsort()[-3:][::-1]

    context = ""

    for index in top_indices:
        context += documents[index] + "\n\n"

    # -----------------------------
    # Format Conversation History
    # -----------------------------
    history_text = ""

    for chat in history:
        history_text += f"User: {chat['question']}\n"
        history_text += f"Assistant: {chat['answer']}\n\n"

    # -----------------------------
    # Prompt
    # -----------------------------
    prompt = f"""
You are an AI assistant for Scaller Technologies.

Use the conversation history to understand follow-up questions.

Answer ONLY using the company information provided below.

If the answer is not available in the company information,
reply exactly:

I don't have that information.

Conversation History:
{history_text}

Company Information:
{context}

Current Question:
{question}
"""

    # -----------------------------
    # Generate Response
    # -----------------------------
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response.choices[0].message.content