from groq import Groq
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import os

load_dotenv()

# Load Groq API
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Read company data
with open("data.txt", "r", encoding="utf-8") as file:
    documents = file.read().split("--------------------------------")

# Create TF-IDF vectors
vectorizer = TfidfVectorizer()
document_vectors = vectorizer.fit_transform(documents)


def search(question):
    # Convert question into TF-IDF vector
    question_vector = vectorizer.transform([question])

    # Find similarity with all documents
    similarity = cosine_similarity(question_vector, document_vectors)

    # Get the most relevant document
    index = similarity.argmax()
    context = documents[index]

    prompt = f"""
You are an AI assistant for Scaller Technologies.

Answer the question only using the information given below.

If the answer is not available, reply:
I don't have that information.

Information:
{context}

Question:
{question}
"""

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