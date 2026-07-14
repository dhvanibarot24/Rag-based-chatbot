from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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

@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):

    await websocket.accept()

    session_memory = deque(maxlen=4)

    try:

        while True:

            question = await websocket.receive_text()

            history = list(session_memory)

            answer = search(question, history)

         
            session_memory.append({
                "question": question,
                "answer": answer
            })

            
            await websocket.send_text(answer)

    except WebSocketDisconnect:

        print("Client disconnected")

        session_memory.clear()