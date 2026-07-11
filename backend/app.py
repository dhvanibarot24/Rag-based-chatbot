from fastapi import FastAPI
from pydantic import BaseModel
from rag import search

app = FastAPI()


class Chat(BaseModel):
    question: str


@app.post("/chat")
def chat(data: Chat):

    answer = search(data.question)

    return {"answer": answer}