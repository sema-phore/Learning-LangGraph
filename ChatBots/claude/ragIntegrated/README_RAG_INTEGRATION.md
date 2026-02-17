# RAG Tool Integration - Complete Guide

## Overview
Your multi-utility chatbot now supports uploading PDF documents and asking questions about them using RAG (Retrieval-Augmented Generation).

---

## Files Structure

```
your_project/
├── backend_with_tools.py              # LangGraph backend with tools
├── utility_tools.py                   # Tool definitions (search, stock, calculator, RAG)
├── rag_utility.py                     # PDF processing & ChromaDB management
├── sqlite_db.py                       # Database setup & thread metadata
├── streamlit_utility_functions.py     # Helper functions for Streamlit
├── streamlit_app.py                   # Main Streamlit application
├── .env                               # API keys (OPENAI_API_KEY)
├── chatbot.db                         # SQLite database (auto-created)
└── chatbot_chroma/                    # Vector stores (auto-created)
    └── {thread_id}/
        └── chroma.sqlite3
```

---

## How It Works

### 1. **PDF Upload**
- User uploads PDF in sidebar
- `ingest_pdf()` processes the PDF:
  - Loads PDF pages
  - Splits into 800-character chunks (150 overlap)
  - Creates embeddings using OpenAI `text-embedding-3-small`
  - Stores in ChromaDB with thread-specific collection
- Retriever stored in memory for quick access

### 2. **RAG Tool Usage**
- When user asks a question, LLM decides which tools to use
- If question is about the PDF, LLM calls `rag_tool`
- `set_rag_thread_id()` injects the current thread_id
- `rag_tool` retrieves relevant chunks from ChromaDB
- Context is added to LLM prompt
- LLM generates answer using PDF context

### 3. **Thread-Specific PDFs**
- Each conversation thread can have its own PDF
- PDFs persist in `chatbot_chroma/{thread_id}/`
- When switching threads, PDF data automatically loads
- No cross-contamination between conversations

---

## Key Features

✅ **PDF Upload per Thread** - Each chat has its own document  
✅ **Persistent Storage** - PDFs survive app restarts  
✅ **Automatic Retrieval** - LLM decides when to use RAG  
✅ **Visual Feedback** - Status shows "🔍 Searching document..."  
✅ **MMR Search** - Maximum Marginal Relevance for diverse results  
✅ **Thread Isolation** - PDFs don't mix between conversations

---

## Usage Examples

### Example 1: Upload and Query Resume

1. **Upload PDF**
   ```
   Sidebar → Upload PDF → Select resume.pdf
   Status: Processing document...
   ✅ resume.pdf
   📄 2 pages | ✂️ 15 chunks
   ```

2. **Ask Question**
   ```
   User: What programming languages do I know?
   🔍 Searching document...
   ✅ Tool finished
   
   Assistant: Based on your resume, you have experience with:
   - Python (Django, FastAPI)
   - JavaScript (React, Node.js)
   - SQL (PostgreSQL, MySQL)
   ```

### Example 2: Multi-Tool Conversation

```
User: What's the stock price of Apple and tell me about my iOS experience?

🔧 Using `get_stock_price`...
🔍 Searching document...
✅ Tool finished