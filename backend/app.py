from fastapi import FastAPI
from pydantic import BaseModel
from rag import search
from collections import deque

app = FastAPI()


# Stores memory for each session
chat_memory = {}


class Chat(BaseModel):
    session_id: str
    question: str


@app.post("/chat")
def chat(data: Chat):

    # Create memory for new session
    if data.session_id not in chat_memory:
        chat_memory[data.session_id] = deque(maxlen=4)

    # Get previous conversation
    history = list(chat_memory[data.session_id])

    # Get answer
    answer = search(data.question, history)

    # Save current interaction
    chat_memory[data.session_id].append({
        "question": data.question,
        "answer": answer
    })

    return {"answer": answer}