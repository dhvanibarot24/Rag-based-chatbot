from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    UploadFile,
    File
)

from pydantic import BaseModel
from collections import deque
from rag import search

from groq import Groq
from dotenv import load_dotenv

import tempfile
import os
app = FastAPI()

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

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

class Session(BaseModel):
    session_id: str


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
# Speech To Text
# -----------------------------------

@app.post("/speech-to-text")
async def speech_to_text(audio: UploadFile = File(...)):

    temp_path = None

    try:

        extension = os.path.splitext(audio.filename)[1]

        if extension == "":
            extension = ".webm"

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension
        ) as temp:

            contents = await audio.read()

            temp.write(contents)

            temp_path = temp.name

        with open(temp_path, "rb") as file:

            transcription = client.audio.transcriptions.create(

                file=(audio.filename, file),

                model="whisper-large-v3-turbo",

                response_format="verbose_json",

                language="en",

                temperature=0

            )

        return {
            "text": transcription.text
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
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