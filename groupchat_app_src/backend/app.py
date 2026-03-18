import os
import asyncio
from typing import Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Request, File, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
import shutil
import pdfplumber

from db import SessionLocal, init_db, User, Message
from auth import get_password_hash, verify_password, create_access_token, get_current_user_token
from websocket_manager import ConnectionManager
from llm import chat_completion
from langchain.text_splitter import CharacterTextSplitter
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory

load_dotenv()

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
UPLOAD_DIR = "uploaded_files"
VECTOR_DB_DIR = "vector_db"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VECTOR_DB_DIR, exist_ok=True)

app = FastAPI(title="Group Chat with LLM Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()

# --------- Schemas ---------
class AuthPayload(BaseModel):
    username: str
    password: str

class MessagePayload(BaseModel):
    content: str

# --------- Dependencies ---------
async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

# --------- Utilities ---------
async def broadcast_message(session: AsyncSession, msg: Message):
    username = None
    if msg.user_id:
        u = await session.get(User, msg.user_id)
        username = u.username if u else "unknown"
    await manager.broadcast({
        "type": "message",
        "message": {
            "id": msg.id,
            "username": username if not msg.is_bot else "LLM Bot",
            "content": msg.content,
            "is_bot": msg.is_bot,
            "created_at": str(msg.created_at)
        }
    })

async def maybe_answer_with_llm(session: AsyncSession, content: str):
    if "?" not in content:
        return
    system_prompt = (
        "You are a helpful assistant participating in a small group chat. "
        "Provide concise, accurate answers suitable for a shared chat context. "
        "Cite facts succinctly when helpful and avoid extremely long messages."
    )
    try:
        reply_text = await chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ])
    except Exception as e:
        reply_text = f"(LLM error) {e}"
    bot_msg = Message(user_id=None, content=reply_text, is_bot=True)
    session.add(bot_msg)
    await session.commit()
    await session.refresh(bot_msg)
    await broadcast_message(session, bot_msg)

# --------- Routes ---------
@app.on_event("startup")
async def on_startup():
    await init_db()

@app.post("/api/signup")
async def signup(payload: AuthPayload, session: AsyncSession = Depends(get_db)):
    existing = await session.execute(select(User).where(User.username == payload.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")
    u = User(username=payload.username, password_hash=get_password_hash(payload.password))
    session.add(u)
    await session.commit()
    token = create_access_token({"sub": u.username})
    return {"ok": True, "token": token}

@app.post("/api/login")
async def login(payload: AuthPayload, session: AsyncSession = Depends(get_db)):
    res = await session.execute(select(User).where(User.username == payload.username))
    u = res.scalar_one_or_none()
    if not u or not verify_password(payload.password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": u.username})
    return {"ok": True, "token": token}

@app.get("/api/messages")
async def get_messages(limit: int = 50, session: AsyncSession = Depends(get_db)):
    res = await session.execute(select(Message).order_by(desc(Message.created_at)).limit(limit))
    items = list(reversed(res.scalars().all()))
    out = []
    for m in items:
        username = None
        if not m.is_bot and m.user_id:
            u = await session.get(User, m.user_id)
            username = u.username if u else "unknown"
        out.append({
            "id": m.id,
            "username": "LLM Bot" if m.is_bot else (username or "unknown"),
            "content": m.content,
            "is_bot": m.is_bot,
            "created_at": str(m.created_at)
        })
    return {"messages": out}

@app.post("/api/messages")
async def post_message(payload: MessagePayload, username: str = Depends(get_current_user_token), session: AsyncSession = Depends(get_db)):
    res = await session.execute(select(User).where(User.username == username))
    u = res.scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=401, detail="Invalid user")
    m = Message(user_id=u.id, content=payload.content, is_bot=False)
    session.add(m)
    await session.commit()
    await session.refresh(m)
    await broadcast_message(session, m)
    asyncio.create_task(maybe_answer_with_llm(session, payload.content))
    return {"ok": True, "id": m.id}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "ack", "echo": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# -------------------------------
# Part 3: PDF/Text Upload & Embeddings
# -------------------------------

# Helper functions
def extract_text_from_pdf(folder=UPLOAD_DIR):
    texts = []
    for filename in os.listdir(folder):
        path = os.path.join(folder, filename)
        if filename.lower().endswith(".pdf"):
            with pdfplumber.open(path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                texts.append(text)
        elif filename.lower().endswith(".txt"):
            with open(path, "r", encoding="utf-8") as f:
                texts.append(f.read())
    return texts

def chunk_texts(texts, chunk_size=500, chunk_overlap=50):
    splitter = CharacterTextSplitter(
        separator="\n",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    chunks = []
    for text in texts:
        chunks.extend(splitter.split_text(text))
    return chunks

def create_vector_store(chunks):
    embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
    vectordb = Chroma.from_texts(chunks, embeddings, persist_directory=VECTOR_DB_DIR)
    vectordb.persist()
    return vectordb

# Upload endpoint
@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    saved_files = 0
    for file in files:
        path = os.path.join(UPLOAD_DIR, file.filename)
        with open(path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        saved_files += 1
    return {"message": f"{saved_files} file(s) uploaded successfully!"}

# Process embeddings
@app.post("/api/process_embeddings")
async def process_embeddings():
    texts = extract_text_from_pdf()
    if not texts:
        raise HTTPException(status_code=400, detail="No uploaded files found")
    chunks = chunk_texts(texts)
    create_vector_store(chunks)
    return {"message": f"Processed {len(chunks)} chunks and stored embeddings."}

# Ask questions via LLM (optional integration)
vectordb = None
conversation_chain = None

def get_conversation_chain():
    global vectordb, conversation_chain
    if vectordb is None:
        if not os.path.exists(VECTOR_DB_DIR):
            raise HTTPException(status_code=400, detail="Vector DB not found. Upload files first.")
        vectordb = Chroma(persist_directory=VECTOR_DB_DIR, embedding_function=OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY))
    if conversation_chain is None:
        retriever = vectordb.as_retriever()
        memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0, openai_api_key=OPENAI_API_KEY)
        conversation_chain = ConversationalRetrievalChain.from_llm(llm, retriever, memory=memory)
    return conversation_chain

@app.post("/api/ask")
async def ask_question(question: str = Form(...)):
    chain = get_conversation_chain()
    answer = await asyncio.to_thread(chain.run, question)
    return JSONResponse({"answer": answer})

# Serve frontend
app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")
app.mount("/.well-known", StaticFiles(directory="../frontend/.well-known"), name="well_known")

if __name__ == "__main__":
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)
