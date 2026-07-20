from collections import deque
import base64
import hashlib
import hmac
import json
import os
import tempfile
import time
from typing import Optional

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    UploadFile,
    File,
    Header,
)
from groq import Groq
from pydantic import BaseModel

from database import (
    authenticate_user,
    create_chat_session,
    create_user,
    delete_messages,
    ensure_chat_session,
    get_messages,
    get_user_by_id,
    init_db,
    list_chat_sessions,
    recent_chat_pairs,
    save_message,
    user_owns_session,
    validate_email,
)
from rag import search

load_dotenv()

app = FastAPI()
init_db()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
AUTH_SECRET = os.getenv("AUTH_SECRET_KEY") or os.getenv("GROQ_API_KEY") or os.urandom(32).hex()
TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 7

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


class SignupRequest(BaseModel):
    full_name: str
    email: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class SessionCreateRequest(BaseModel):
    session_id: Optional[str] = None


def create_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "issued_at": int(time.time()),
        "nonce": base64.urlsafe_b64encode(os.urandom(12)).decode("utf-8"),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(payload_bytes).decode("utf-8")
    signature = hmac.new(
        AUTH_SECRET.encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded_payload}.{signature}"


def read_token(token: str) -> Optional[dict]:
    if not token or "." not in token:
        return None

    encoded_payload, signature = token.rsplit(".", 1)
    expected_signature = hmac.new(
        AUTH_SECRET.encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded_payload.encode("utf-8")))
    except (ValueError, json.JSONDecodeError):
        return None

    issued_at = int(payload.get("issued_at", 0))
    if int(time.time()) - issued_at > TOKEN_MAX_AGE_SECONDS:
        return None

    return payload


def token_from_header(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    prefix = "Bearer "
    if authorization.startswith(prefix):
        return authorization[len(prefix):].strip()
    return None


def get_authenticated_user(token: Optional[str]) -> Optional[dict]:
    payload = read_token(token or "")
    if payload is None:
        return None
    return get_user_by_id(int(payload.get("user_id", 0)))


def require_authenticated_user(token: Optional[str]) -> dict:
    user = get_authenticated_user(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in again.")
    return user


def auth_response(user: dict) -> dict:
    session_id = create_chat_session(int(user["id"]))
    return {
        "token": create_token(int(user["id"])),
        "user": user,
        "session_id": session_id,
    }


def validate_signup(data: SignupRequest) -> None:
    if not data.full_name.strip():
        raise HTTPException(status_code=400, detail="Please enter your full name.")
    if not validate_email(data.email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if data.password != data.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")


def load_memory_from_database(memory_store: dict, session_id: str) -> None:
    if session_id not in memory_store:
        memory_store[session_id] = deque(recent_chat_pairs(session_id), maxlen=4)


def safe_save_chat_turn(user: Optional[dict], session_id: str, question: str, answer: str) -> None:
    if user is None:
        return
    save_message(session_id, "user", question)
    save_message(session_id, "assistant", answer)


# -----------------------------------
# Authentication Endpoints
# -----------------------------------
@app.post("/signup")
def signup(data: SignupRequest):
    validate_signup(data)

    try:
        user = create_user(data.full_name, data.email, data.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Signup failed. Please try again.") from exc

    return auth_response(user)


@app.post("/login")
def login(data: LoginRequest):
    if not validate_email(data.email) or not data.password:
        raise HTTPException(status_code=400, detail="Please enter a valid email and password.")

    user = authenticate_user(data.email, data.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return auth_response(user)


@app.get("/me")
def me(authorization: Optional[str] = Header(default=None)):
    token = token_from_header(authorization)
    user = require_authenticated_user(token)
    return {"user": user}


@app.post("/sessions")
def create_session(
    data: SessionCreateRequest,
    authorization: Optional[str] = Header(default=None),
):
    token = token_from_header(authorization)
    user = require_authenticated_user(token)
    session_id = ensure_chat_session(int(user["id"]), data.session_id)
    return {"session_id": session_id}


@app.get("/sessions")
def sessions(authorization: Optional[str] = Header(default=None)):
    token = token_from_header(authorization)
    user = require_authenticated_user(token)
    return {"sessions": list_chat_sessions(int(user["id"]))}


@app.get("/sessions/{session_id}/messages")
def session_messages(session_id: str, authorization: Optional[str] = Header(default=None)):
    token = token_from_header(authorization)
    user = require_authenticated_user(token)

    if not user_owns_session(int(user["id"]), session_id):
        raise HTTPException(status_code=404, detail="Chat session was not found.")

    return {"messages": get_messages(session_id)}


# -----------------------------------
# REST Endpoint
# -----------------------------------
@app.post("/chat")
def chat(data: Chat, authorization: Optional[str] = Header(default=None)):
    token = token_from_header(authorization)
    user = get_authenticated_user(token)

    if token and user is None:
        raise HTTPException(status_code=401, detail="Please log in again.")

    if user is not None:
        if not user_owns_session(int(user["id"]), data.session_id):
            raise HTTPException(status_code=403, detail="You do not have access to this chat session.")
        load_memory_from_database(chat_memory, data.session_id)

    if data.session_id not in chat_memory:
        chat_memory[data.session_id] = deque(maxlen=4)

    history = list(chat_memory[data.session_id])
    answer = search(data.question, history)

    chat_memory[data.session_id].append(
        {
            "question": data.question,
            "answer": answer,
        }
    )
    safe_save_chat_turn(user, data.session_id, data.question, answer)

    return {"answer": answer}


# -----------------------------------
# Clear Session
# -----------------------------------
@app.delete("/clear-session")
def clear_session(data: Session, authorization: Optional[str] = Header(default=None)):
    token = token_from_header(authorization)
    user = get_authenticated_user(token)

    if token and user is None:
        raise HTTPException(status_code=401, detail="Please log in again.")

    if user is not None:
        if not user_owns_session(int(user["id"]), data.session_id):
            raise HTTPException(status_code=403, detail="You do not have access to this chat session.")
        delete_messages(data.session_id)

    chat_memory.pop(data.session_id, None)
    ws_memory.pop(data.session_id, None)
    return {"status": "cleared"}


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

        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp:
            contents = await audio.read()
            temp.write(contents)
            temp_path = temp.name

        with open(temp_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(audio.filename, file),
                model="whisper-large-v3-turbo",
                response_format="verbose_json",
                language="en",
                temperature=0,
            )

        return {"text": transcription.text}

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Speech transcription failed. Please try again.",
        ) from exc

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
            data = await websocket.receive_json()

            session_id = data["session_id"]
            question = data["question"]
            token = data.get("token")
            user = get_authenticated_user(token)

            if token and user is None:
                await websocket.send_json({"error": "Please log in again."})
                continue

            if user is not None:
                if not user_owns_session(int(user["id"]), session_id):
                    await websocket.send_json({"error": "You do not have access to this chat session."})
                    continue
                load_memory_from_database(ws_memory, session_id)

            if session_id not in ws_memory:
                ws_memory[session_id] = deque(maxlen=4)

            history = list(ws_memory[session_id])
            answer = search(question, history)

            ws_memory[session_id].append(
                {
                    "question": question,
                    "answer": answer,
                }
            )
            safe_save_chat_turn(user, session_id, question, answer)

            await websocket.send_json({"answer": answer})

    except WebSocketDisconnect:
        pass
