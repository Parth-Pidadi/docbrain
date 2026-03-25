# 🧠 DocBrain — AI-Powered Document Intelligence Platform

<div align="center">

![DocBrain Banner](https://img.shields.io/badge/DocBrain-AI%20Document%20Intelligence-6366f1?style=for-the-badge&logo=brain&logoColor=white)

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Railway](https://img.shields.io/badge/Railway-Deployed-0B0D0E?style=flat-square&logo=railway&logoColor=white)](https://railway.app/)
[![Vercel](https://img.shields.io/badge/Vercel-Deployed-000000?style=flat-square&logo=vercel&logoColor=white)](https://vercel.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

**Upload any financial or legal document. Ask anything about it. Get instant answers.**

[🌐 Live Demo](https://docbrainai.vercel.app) · [📖 API Docs](https://docbrain-backend.up.railway.app/docs) · [💻 GitHub](https://github.com/Parth-Pidadi/docbrain)

</div>

---

## 📌 Overview

DocBrain is a full-stack AI document intelligence platform that transforms unstructured financial and legal documents into queryable, structured knowledge. Upload a receipt, invoice, bank statement, or contract — DocBrain automatically extracts structured data using a hybrid OCR pipeline, classifies the document with an LLM, stores embeddings in a vector database, and lets you ask natural language questions answered by LLaMA 3.3 70B via tool-calling and RAG.

> Built for real-world document workflows: multi-user isolation, deduplication, GPU-accelerated OCR, and SQL-powered spending analytics — all in one platform.

---

## ✨ Features

| # | Feature | Description |
|---|---------|-------------|
| 🔐 | **Multi-User Auth** | JWT tokens + Argon2 password hashing, complete per-user data isolation |
| 📤 | **Smart Document Upload** | PDF, PNG, JPG, TIFF, WEBP — up to 20 MB, SHA-256 deduplication |
| 🔍 | **Hybrid OCR Pipeline** | Donut GPU (images) → pdfplumber (text PDFs) → Tesseract (fallback) |
| 🏷️ | **LLM Classification** | Auto-detects: receipt, invoice, bank statement, or contract |
| 🧾 | **Structured Extraction** | Specialized prompts per doc type — line items, transactions, red flags |
| 🤖 | **LLM Tool Calling** | 6 tools: spending, vendors, transactions, receipt items, contracts, search |
| 🗂️ | **RAG Q&A** | ChromaDB vector search with per-user embedding isolation |
| 📊 | **Insights Dashboard** | SQL-powered analytics — vendor breakdowns, spending by month |
| ✏️ | **Document Management** | Rename & delete — cleans PostgreSQL, disk storage, and ChromaDB vectors |
| ⚠️ | **Contract Analysis** | Auto-flags red flags, liability clauses, auto-renewals, indemnification |

---

## 🏗️ Architecture

```mermaid
flowchart TD
    A([👤 User]) -->|Upload Document| B[FastAPI Backend]

    B --> C{File Type?}
    C -->|Image: PNG/JPG/TIFF/WEBP| D[🖥️ Donut OCR\nGoogle Colab GPU]
    C -->|Text PDF| E[📄 pdfplumber]
    D -->|OCR Failed| F[🔡 Tesseract Fallback]
    E --> G[Raw Text]
    D --> G
    F --> G

    G --> H[🦙 LLaMA 3.3 70B\nvia Groq API]
    H -->|Classify| I{Document Type}

    I -->|Receipt| J1[Extract: vendor, items,\ntotal, date, tax]
    I -->|Invoice| J2[Extract: line items,\ndue date, parties]
    I -->|Bank Statement| J3[Extract: transactions,\nbalances, dates]
    I -->|Contract| J4[Extract: red flags,\nliability, auto-renewal]

    J1 & J2 & J3 & J4 --> K[(🐘 PostgreSQL\nStructured Data)]

    G --> L[BGE-small-en\nEmbeddings\nGoogle Colab GPU]
    L --> M[(🔮 ChromaDB\nVector Store)]

    K & M --> N[Q&A Engine]
    N -->|SQL Tool Calls| K
    N -->|Semantic Search| M
    N --> O[💬 LLaMA 3.3 70B\nTool Calling]

    K --> P[📊 Insights Engine\nSQL Analytics]

    O --> Q([✅ Natural Language\nAnswer])
    P --> R([📈 Spending Charts\n& Vendor Breakdown])
```

### Data Flow Summary

```
Upload → OCR (Donut / pdfplumber / Tesseract)
       → LLM Classification (LLaMA 3.3 70B)
       → Structured Extraction → PostgreSQL
       → BGE Embeddings → ChromaDB
       → Q&A (Tool Calling: SQL + RAG)
       → Insights Dashboard (SQL Analytics)
```

---

## 🛠️ Tech Stack

### Backend
| Technology | Role |
|-----------|------|
| **FastAPI** (Python 3.11) | REST API framework |
| **SQLAlchemy** | ORM + database migrations |
| **PostgreSQL** | Structured document data storage |
| **ChromaDB** | Vector embeddings store (per-user isolation) |
| **LLaMA 3.3 70B via Groq** | Classification, extraction, tool calling |
| **Donut (Document Understanding Transformer)** | GPU-accelerated image OCR |
| **pdfplumber** | Text PDF extraction |
| **Tesseract OCR** | Fallback OCR engine |
| **BGE-small-en** | Sentence embeddings (Google Colab GPU) |
| **JWT + Argon2** | Authentication & password hashing |

### Frontend
| Technology | Role |
|-----------|------|
| **React 18 + Vite** | UI framework + build tool |
| **React Router** | Client-side routing |
| **Axios** | HTTP client for API calls |
| **Recharts** | Spending insights charts |

### Infrastructure
| Service | Purpose |
|---------|---------|
| **Railway** | Backend deployment (Nixpacks, auto-deploy from GitHub) |
| **Vercel** | Frontend deployment (SPA routing via `vercel.json`) |
| **Google Colab (GPU)** | Donut OCR + BGE embeddings processing |
| **ngrok** | Tunnel Colab GPU worker to backend |

---

## 🤖 LLM Tool Calling — 6 Tools

DocBrain's Q&A engine uses structured tool calling so LLaMA 3.3 70B can query live data rather than hallucinate:

| Tool | Description |
|------|-------------|
| `get_spending` | Aggregate total spending by category or time range |
| `get_vendors` | List vendors with spend totals and transaction counts |
| `get_transactions` | Fetch bank statement transactions with filters |
| `get_receipt_items` | Retrieve itemized line items from receipts |
| `analyze_contract` | Surface red flags, clauses, and risk areas from contracts |
| `search_documents` | Semantic RAG search across all user documents |

---

## 🚀 Local Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Docker (optional)

### 1. Clone the Repository

```bash
git clone https://github.com/Parth-Pidadi/docbrain.git
cd docbrain
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in `backend/`:

```env
DATABASE_URL=postgresql://user:pass@localhost:5432/docbrain
GROQ_API_KEY=your_groq_api_key
SECRET_KEY=your_jwt_secret_key
COLAB_URL=https://your-ngrok-url.ngrok.io   # Optional: for GPU OCR
```

Run the backend:

```bash
uvicorn app.main:app --reload
```

API docs available at: `http://localhost:8000/docs`

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend available at: `http://localhost:5173`

### 4. (Optional) PostgreSQL with Docker

```bash
docker run --name docbrain-db \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=pass \
  -e POSTGRES_DB=docbrain \
  -p 5432:5432 \
  -d postgres:16
```

---

## 🔑 Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ Yes | PostgreSQL connection string |
| `GROQ_API_KEY` | ✅ Yes | Groq API key for LLaMA 3.3 70B |
| `SECRET_KEY` | ✅ Yes | JWT signing secret (use a long random string) |
| `COLAB_URL` | ⬜ Optional | ngrok URL for Colab GPU OCR worker |

> **Note:** Without `COLAB_URL`, the system falls back to Tesseract OCR for images and pdfplumber for PDFs.

---

## ☁️ Deployment

### Backend — Railway

1. Connect your GitHub repository to [Railway](https://railway.app/)
2. Add a PostgreSQL plugin to your Railway project
3. Set environment variables in the Railway dashboard
4. Railway uses `nixpacks.toml` for system-level packages (Tesseract, Poppler)
5. Auto-deploys on every push to `main`

### Frontend — Vercel

1. Connect your GitHub repository to [Vercel](https://vercel.com/)
2. Set the root directory to `frontend/`
3. Vercel auto-detects Vite — no build config needed
4. `vercel.json` handles SPA routing (all paths → `index.html`)
5. Auto-deploys on every push to `main`

### Google Colab GPU Worker

- Open the provided Colab notebook
- Run the cell to start the OCR + embedding server
- Copy the ngrok URL and set it as `COLAB_URL` in your backend environment

---

## 📸 Screenshots

> _Screenshots coming soon — add images to `/assets/screenshots/` and update paths below._

| View | Preview |
|------|---------|
| Dashboard / Upload | `![Upload](assets/screenshots/upload.png)` |
| Document List | `![Documents](assets/screenshots/documents.png)` |
| Q&A Interface | `![QA](assets/screenshots/qa.png)` |
| Insights Charts | `![Insights](assets/screenshots/insights.png)` |
| Contract Analysis | `![Contract](assets/screenshots/contract.png)` |

---

## 📁 Project Structure

```
docbrain/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── routers/             # API route handlers
│   │   ├── services/            # OCR, LLM, embedding services
│   │   └── utils/               # Auth, hashing, helpers
│   ├── requirements.txt
│   └── nixpacks.toml            # Railway system deps
├── frontend/
│   ├── src/
│   │   ├── components/          # Reusable UI components
│   │   ├── pages/               # Route-level page components
│   │   └── api/                 # Axios API client
│   ├── vercel.json              # SPA routing config
│   └── vite.config.js
└── README.md
```

---

## 🔒 Security

- Passwords hashed with **Argon2** (winner of Password Hashing Competition)
- All API routes protected by **JWT Bearer tokens**
- Per-user data isolation enforced at the database query and ChromaDB collection level
- SHA-256 document deduplication prevents redundant storage
- No raw document text stored beyond what is needed for extraction

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">

Built with ❤️ using FastAPI, React, LLaMA 3.3 70B, and a lot of document uploads.

[🌐 Live Demo](https://docbrainai.vercel.app) · [📖 API Docs](https://docbrain-backend.up.railway.app/docs) · [💻 GitHub](https://github.com/Parth-Pidadi/docbrain)

</div>
