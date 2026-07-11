from sentence_transformers import SentenceTransformer
import chromadb

model = SentenceTransformer("all-MiniLM-L6-v2")

db = chromadb.PersistentClient(path="chroma_db")

try:
    db.delete_collection("company")
except:
    pass

col = db.get_or_create_collection("company")


file = open("data.txt", "r", encoding="utf-8")
text = file.read()
file.close()

data = text.split("--------------------------------")

for i in range(len(data)):
    e = model.encode(data[i]).tolist()

    col.add(
        ids=[str(i)],
        documents=[data[i]],
        embeddings=[e]
    )

print("Data added successfully")