from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from collections import deque
from rag import search

app = FastAPI()

# -----------------------------------
# REST API Memory
# -----------------------------------
chat_memory = {}

# -----------------------------------
# WebSocket Memory
# -----------------------------------
ws_memory = {}


class Chat(BaseModel):
    session_id: str
    question: str


# -----------------------------------
# REST Endpoint
# -----------------------------------
@app.post("/chat")
def chat(data: Chat):

    if data.session_id not in chat_memory:
        chat_memory[data.session_id] = deque(maxlen=4)

    history = list(chat_memory[data.session_id])

    answer = search(
        data.question,
        history
    )

    chat_memory[data.session_id].append(
        {
            "question": data.question,
            "answer": answer
        }
    )

    return {
        "answer": answer
    }
# -----------------------------------
# WebSocket Endpoint
# -----------------------------------
@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):

    await websocket.accept()

    try:

        while True:

            # Receive JSON from Streamlit
            data = await websocket.receive_json()

            session_id = data["session_id"]
            question = data["question"]

            # Create memory for new session
            if session_id not in ws_memory:
                ws_memory[session_id] = deque(maxlen=4)

            # Get previous conversation
            history = list(ws_memory[session_id])

            # Generate answer
            answer = search(
                question,
                history
            )

            # Save current interaction
            ws_memory[session_id].append(
                {
                    "question": question,
                    "answer": answer
                }
            )

            # Send response back
            await websocket.send_json(
                {
                    "answer": answer
                }
            )

    except WebSocketDisconnect:

        # Connection closed
        pass