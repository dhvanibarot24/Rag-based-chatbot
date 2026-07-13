from sentence_transformers import SentenceTransformer
from groq import Groq
from dotenv import load_dotenv
import chromadb
import os

load_dotenv()

model = SentenceTransformer("all-MiniLM-L6-v2")

db = chromadb.PersistentClient(path="chroma_db")

try:
    col = db.get_collection("company")
except:
    import embed
    col = db.get_collection("company")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def search(question):

    embedding = model.encode(question).tolist()

    result = col.query(
        query_embeddings=[embedding],
        n_results=1
    )

    context = result["documents"][0][0]

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