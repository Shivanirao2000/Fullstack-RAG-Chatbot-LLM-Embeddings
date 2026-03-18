# 🤖 Fullstack RAG Chatbot — LLM + Embeddings + Android

> A production-grade, domain-specific AI chatbot powered by Retrieval-Augmented Generation (RAG), built on a microservices architecture with a real-time FastAPI backend, vector similarity search, and a cross-platform Android interface.

---

## 🧠 Architecture Overview

```
 ┌─────────────────────────────────────────────────────────────┐
 │                        CLIENT LAYER                         │
 │         React Web App  ──────  Android TWA (APK)            │
 └──────────────────────────────┬──────────────────────────────┘
                                │ REST + WebSocket
 ┌──────────────────────────────▼──────────────────────────────┐
 │                      FASTAPI BACKEND                        │
 │    Auth (JWT)  │  Chat API  │  PDF Ingestion  │  Streaming  │
 └──────────┬──────────────────────────┬───────────────────────┘
            │                          │
 ┌──────────▼──────────┐     ┌──────────▼──────────────────────┐
 │      MySQL DB       │     │         RAG PIPELINE            │
 │  Users │ Sessions   │     │  PDF → Chunks → Embeddings      │
 │  Chat History       │     │  FAISS Vector Index             │
 └─────────────────────┘     │  Similarity Search → LLM Prompt │
                             │  LLM Response (Llama 3 / GPT)   │
                             └─────────────────────────────────┘
```

---

## 🎥 Demo

### Web Interface

https://github.com/user-attachments/assets/4274ce4c-ff24-48bc-a6ad-107490690a19



### Mobile App Interface

https://github.com/user-attachments/assets/3eda89e1-ab37-4cd6-a4b5-a636e6040acb

---


## ✨ Key Features

| Feature | Details |
|---|---|
| 🔍 **RAG Pipeline** | Document ingestion → chunking → OpenAI embeddings → FAISS vector store → LLM synthesis |
| 📄 **PDF Ingestion** | Upload single or multiple PDFs via web UI; automatic text extraction and chunking |
| 🧩 **Text Chunking** | LangChain `CharacterTextSplitter` with configurable chunk size and overlap for optimal context retrieval |
| 🗂️ **Vector Search** | FAISS-powered approximate nearest-neighbor search over high-dimensional embedding space |
| 💬 **Conversation Memory** | LangChain `ConversationBufferMemory` maintains multi-turn context across sessions |
| 🌐 **Real-Time Streaming** | WebSocket-based live message broadcast for instant LLM response delivery |
| 🤖 **LLM Flexibility** | Supports self-hosted Llama 3 via `llama.cpp` or `vLLM`, or OpenAI-compatible API |
| 📱 **Android App** | Android Trusted Web Activity (TWA) wrapping the web frontend as a native APK |
| 🔐 **Auth** | JWT-based authentication with configurable token expiry |
| 🐳 **Containerized** | Docker + Docker Compose for consistent, reproducible deployment across environments |

---

## 🛠️ Tech Stack

**Backend**
- `Python 3.10+` · `FastAPI` · `LangChain` · `asyncmy`
- `OpenAI API` (embeddings + chat completions)
- `FAISS` (vector similarity search)
- `llama.cpp` / `vLLM` (self-hosted LLM inference)
- `MySQL 8` (user data, chat history, session management)
- `JWT` (stateless authentication)

**Frontend**
- `React.js` (web interface)
- `WebSocket` (real-time messaging)
- `Android Studio` · `TWA` (Android app)

**Infrastructure**
- `Docker` · `Docker Compose`
- `uvicorn` (ASGI server)
- Linux / cloud-native deployment

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Node.js + npm
- MySQL 8+
- Docker (optional but recommended)
- Android Studio Flamingo+ (for mobile build)

### 1. Clone the repo
```bash
git clone https://github.com/Shivanirao2000/Fullstack-RAG-Chatbot-LLM-Embeddings.git
cd Fullstack-RAG-Chatbot-LLM-Embeddings
git submodule update --init --recursive   # pulls llama.cpp
```

### 2. Set up the database
```sql
CREATE DATABASE groupchat CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'chatuser'@'localhost' IDENTIFIED BY 'chatpass';
GRANT ALL PRIVILEGES ON groupchat.* TO 'chatuser'@'localhost';
FLUSH PRIVILEGES;
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your DB credentials, JWT secret, and LLM endpoint
```

```env
DATABASE_URL=mysql+asyncmy://chatuser:chatpass@localhost:3306/groupchat
JWT_SECRET=<your-long-random-secret>
LLM_API_BASE=http://localhost:8001/v1
LLM_MODEL=llama-3-8b-instruct
LLM_API_KEY=
APP_HOST=0.0.0.0
APP_PORT=8000
```

### 4. Run the backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

### 5. (Optional) Run with Docker
```bash
docker-compose up --build
```

---

## 🧬 RAG Pipeline Deep Dive

```
1. INGEST    → Upload PDFs via web UI
2. EXTRACT   → PyPDF2 / pdfplumber parses raw text
3. CHUNK     → LangChain CharacterTextSplitter (chunk_size=500, overlap=50)
4. EMBED     → OpenAI text-embedding-ada-002 converts chunks to dense vectors
5. INDEX     → FAISS stores and indexes all embedding vectors
6. QUERY     → User question → embedding → top-k FAISS similarity search
7. RERANK    → Retrieved chunks ranked by relevance to query
8. SYNTHESIZE→ Top chunks + question injected into LLM prompt
9. RESPOND   → LLM generates grounded, context-aware answer
```

> Messages containing `?` automatically trigger the RAG pipeline through the LLM bot.

---

## 🤖 LLM Options

### Option A — Self-Hosted via llama.cpp
```bash
cd llama.cpp/build/bin
./llama-server -m /path/to/model.gguf --host 0.0.0.0 --port 8001 --ctx-size 4096
```

### Option B — Self-Hosted via vLLM (GPU)
```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Meta-Llama-3-8B-Instruct \
  --host 0.0.0.0 --port 8001
```

### Option C — OpenAI API
Set `LLM_API_BASE=https://api.openai.com/v1` and add your `OPENAI_API_KEY` in `.env`.

---

## 📱 Android App

The Android app is built as a **Trusted Web Activity (TWA)** — a Chrome Custom Tab that renders the web frontend as a native Android app with no visible URL bar.

1. Open `twa_android_src` in Android Studio
2. Set your deployed URL in `res/values/strings.xml`
3. Generate signing key and configure `assetlinks.json` on your server
4. Build APK and deploy to device or emulator

---

## 📁 Project Structure

```
├── backend/                  # FastAPI app
│   ├── app.py               # Main application entrypoint
│   ├── requirements.txt
│   └── ...
├── frontend/                 # Static HTML/CSS/JS + React
│   └── .well-known/
│       └── assetlinks.json  # Android TWA asset linking
├── twa_android_src/          # Android Studio project
├── sql/
│   └── schema.sql           # DB schema
├── llama.cpp/               # Git submodule — self-hosted LLM inference
├── docker-compose.yml
├── .env.example
└── README.md
```

---
