from sentence_transformers import SentenceTransformer
import chromadb

model = SentenceTransformer("all-MiniLM-L6-v2")

db = chromadb.PersistentClient(path="chroma_db")

col = db.get_collection("company")


def search(question):
    e = model.encode(question).tolist()

    result = col.query(
        query_embeddings=[e],
        n_results=1
    )

    return result["documents"][0][0]