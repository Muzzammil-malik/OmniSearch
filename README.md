# OmniSearch

> **Academic Project Title:** Multifile Search Index Searcher  
> **Tagline:** One search. Your entire digital world.

OmniSearch is a professional, local-first, AI-powered multifile search and personal knowledge discovery desktop application engineered for Windows. It provides fast, privacy-preserving search across heterogeneous file formats (documents, spreadsheets, presentations, and text notes) using both exact keyword matching and natural-language queries—all without sending user files to the cloud.

---

## 1. Technology Stack

### Backend
- **Python 3.11+** (Tested on Python 3.15.1 Windows AMD64)
- **FastAPI** — High-performance ASGI web framework
- **Pydantic & Pydantic Settings** — Strongly-typed validation and centralized environment configuration
- **SQLite (sqlite3)** — Canonical persistent database (WAL mode, foreign key cascades, migrations)
- **Uvicorn** — Production ASGI server
- **PyMuPDF (1.28.2)** — High-performance PDF document and page text extraction
- **python-docx (1.2.0)** — Word (.docx) paragraph and table extraction
- **python-pptx (1.0.2)** — PowerPoint (.pptx) slide and shape extraction
- **openpyxl (3.1.5)** — Excel (.xlsx) sheet and row data extraction
- **BeautifulSoup4 (4.15.0)** — Clean text and semantic element extraction from HTML
- **charset-normalizer (3.5.2)** — Robust charset detection across text, code, and CSV formats
- **ChromaDB (1.5.9)** — Persistent local dense vector database for semantic chunk retrieval
- **PyTorch (2.15.0+cpu) & Transformers (5.22.1)** — Local inference engine for Google EmbeddingGemma 2

### Frontend
- **Next.js 15 (App Router)** — Modern React application framework
- **React 19 & TypeScript** — Type-safe, component-driven user interface
- **Tailwind CSS** — Restrained dark navy design system with subtle cyan accents
- **Lucide React** — Minimalist UI iconography

### Architecture Roadmap (Future Phases)
- **Desktop Shell:** Electron (Phase 8)

---

## 2. Project Structure

```text
OmniSearch/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── folders.py         # Folder registration & management endpoints (Phase 7)
│   │   │       │   ├── health.py          # Health check route handler
│   │   │       │   ├── indexing.py        # Indexing lifecycle & status endpoints (Phase 7)
│   │   │       │   ├── search.py          # Keyword, Semantic, Hybrid & Unified search endpoints (Phases 4–7)
│   │   │       │   └── system.py          # System telemetry & diagnostics endpoints (Phase 7)
│   │   │       ├── __init__.py
│   │   │       └── router.py              # V1 API router aggregator
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py                  # Pydantic Settings & storage directory configs
│   │   │   ├── exceptions.py              # Centralized domain exception hierarchy (Phase 7)
│   │   │   └── logging.py                 # Centralized logging setup
│   │   ├── database/                      # Canonical persistence layer (Phase 3 & 4)
│   │   │   ├── repositories/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── chunks.py              # Chunks repository
│   │   │   │   ├── embeddings.py          # Chunk embedding tracking repository (Phase 5)
│   │   │   │   ├── files.py               # Files repository & reconciliation
│   │   │   │   ├── folders.py             # Folders repository & aggregated metrics (Phases 3 & 7)
│   │   │   │   ├── fts.py                 # FTS5 index maintenance repository (Phase 4)
│   │   │   │   ├── jobs.py                # Index jobs repository
│   │   │   │   └── settings.py            # Key-value settings repository
│   │   │   ├── connection.py              # Connection lifecycle & WAL transactions
│   │   │   ├── initialization.py          # DB initialization & interrupted job recovery
│   │   │   ├── migrations.py              # Versioned schema migrations (v1 canonical, v2 FTS5, v3 embeddings)
│   │   │   └── __init__.py
│   │   ├── embeddings/                    # Local Embedding Engine (Phase 5)
│   │   │   ├── __init__.py
│   │   │   ├── base.py                    # BaseEmbedder abstract interface
│   │   │   ├── configuration.py           # EmbeddingConfig & Matryoshka dimension validation
│   │   │   ├── embedder.py                # EmbeddingGemmaEmbedder (PyTorch + Transformers)
│   │   │   ├── exceptions.py              # Subsystem exception hierarchy
│   │   │   ├── model_manager.py           # Lazy model loading & resource lifecycle
│   │   │   ├── prompts.py                 # Official EmbeddingGemma 2 task prompt formatters
│   │   │   └── test_embedder.py           # Offline deterministic test double
│   │   ├── ingestion/                     # Multi-format ingestion engine (Phase 2)
│   │   │   ├── extractors/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py                # BaseExtractor interface
│   │   │   │   ├── csv.py                 # CSV/TSV reader extractor
│   │   │   │   ├── docx.py                # Word document extractor
│   │   │   │   ├── html.py                # HTML BeautifulSoup extractor
│   │   │   │   ├── pdf.py                 # PDF PyMuPDF extractor
│   │   │   │   ├── pptx.py                # PPTX slide extractor
│   │   │   │   ├── text.py                # TXT, Code & Markdown extractor
│   │   │   │   └── xlsx.py                # Excel openpyxl extractor
│   │   │   ├── coordinator.py             # Batch coordinator & fault isolation
│   │   │   ├── file_detector.py           # Signature validation & executable blocker
│   │   │   ├── hashing.py                 # Streaming SHA-256 chunked hasher
│   │   │   ├── registry.py                # Extractor registry
│   │   │   ├── scanner.py                 # Recursive folder scanner
│   │   │   └── __init__.py
│   │   ├── models/                        # Domain models
│   │   ├── processing/                    # Content processing & chunking (Phase 3)
│   │   │   ├── chunker.py                 # Intelligent boundary-preserving chunker
│   │   │   ├── normalizer.py              # Format-aware Unicode & whitespace normalizer
│   │   │   ├── pipeline.py                # Content transformation pipeline
│   │   │   ├── token_counter.py           # Replaceable token estimation interface
│   │   │   └── __init__.py
│   │   ├── schemas/                       # Pydantic API & domain schemas
│   │   │   ├── __init__.py
│   │   │   ├── errors.py                  # Standardized error response schema (Phase 7)
│   │   │   ├── extraction.py              # ExtractedDocument & ExtractedSegment schemas
│   │   │   ├── folder.py                  # Folder CRUD & metric schemas (Phase 7)
│   │   │   ├── health.py                  # HealthResponse schema
│   │   │   ├── indexing.py                # Indexing control & statistics schemas (Phase 7)
│   │   │   ├── processing.py              # DocumentChunk & DB entity schemas
│   │   │   ├── search.py                  # Keyword, Semantic, Hybrid & Unified search schemas (Phases 4–7)
│   │   │   └── system.py                  # System diagnostics & telemetry schemas (Phase 7)
│   │   ├── search/                        # Search subsystems (Phases 4, 5, 6)
│   │   │   ├── __init__.py
│   │   │   ├── hybrid_search.py           # Unified hybrid search engine (Phase 6)
│   │   │   ├── keyword_search.py          # SQLite FTS5 + BM25 ranked search engine
│   │   │   ├── query_parser.py            # Safe query parser & syntax sanitizer
│   │   │   ├── rrf.py                     # Reciprocal Rank Fusion algorithm & ranking (Phase 6)
│   │   │   ├── semantic_search.py         # ChromaDB vector similarity search engine (Phase 5)
│   │   │   └── snippets.py                # HTML snippet formatting & XSS-safe highlighter
│   │   ├── services/                      # Application business logic (Phase 7)
│   │   │   ├── __init__.py
│   │   │   ├── folder_service.py          # Folder management service (Phase 7)
│   │   │   ├── indexer.py                 # Persistent IndexingService (Phases 3 & 7)
│   │   │   ├── search_service.py          # Unified search application service (Phase 7)
│   │   │   ├── semantic_pipeline.py       # Embedding generation & ChromaDB sync (Phase 5)
│   │   │   └── system_service.py          # System status telemetry service (Phase 7)
│   │   ├── vector_store/                  # Vector database abstraction (Phase 5)
│   │   │   ├── __init__.py
│   │   │   └── chroma.py                  # ChromaDB PersistentClient & cosine metric client
│   │   ├── utils/                         # Reusable utilities
│   │   ├── __init__.py
│   │   └── main.py                        # FastAPI application entry point
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                    # Pytest test fixtures
│   │   ├── test_chunker.py                # Chunking & token counting tests
│   │   ├── test_cli.py                    # Folder indexing CLI automated tests
│   │   ├── test_coordinator.py            # Coordinator batch & failure tests
│   │   ├── test_database.py               # SQLite tables, cascades & transactions tests
│   │   ├── test_embeddings.py             # Embedding config, prompts & embedder tests (Phase 5)
│   │   ├── test_error_handling.py         # Error response contracts & security tests (Phase 7)
│   │   ├── test_extractors.py             # Multi-format genuine extraction tests
│   │   ├── test_file_detector.py          # Security & signature tests
│   │   ├── test_folders_api.py            # Folder registration, cascade & metric tests (Phase 7)
│   │   ├── test_fts.py                    # SQLite FTS5 triggers & synchronization tests
│   │   ├── test_hashing.py                # Streaming SHA-256 tests
│   │   ├── test_health.py                 # Health endpoint automated tests
│   │   ├── test_hybrid_search.py          # Hybrid search engine & fusion API tests (Phase 6)
│   │   ├── test_indexer.py                # Persistent indexing service tests
│   │   ├── test_indexing_api.py           # Indexing control, conflict & status tests (Phase 7)
│   │   ├── test_normalizer.py             # Unicode & formatting normalization tests
│   │   ├── test_query_parser.py           # Query parsing & escaping tests
│   │   ├── test_rrf.py                    # Reciprocal Rank Fusion unit tests (Phase 6)
│   │   ├── test_scanner.py                # Recursive folder scanner tests
│   │   ├── test_search.py                 # FTS5 keyword search engine & API tests
│   │   ├── test_semantic_pipeline.py      # Semantic chunk embedding & sync tests (Phase 5)
│   │   ├── test_semantic_search.py        # ChromaDB semantic search engine & API tests (Phase 5)
│   │   ├── test_system_api.py             # System telemetry & lazy model tests (Phase 7)
│   │   ├── test_unified_search_api.py     # Multi-mode unified search API tests (Phase 7)
│   │   └── test_vector_store.py           # Chroma persistent storage & query tests (Phase 5)
│   ├── pyproject.toml                     # Backend project & dependency metadata
│   └── .env.example                       # Environment variable template
│
├── scripts/
│   ├── index_folder.py                    # Manual folder indexing CLI utility
│   └── verify_semantic_search.py          # Semantic search pipeline verification test
│
├── frontend/
│   ├── app/
│   │   ├── globals.css                 # Dark navy theme styling
│   │   ├── layout.tsx                  # Root HTML layout with metadata
│   │   └── page.tsx                    # Minimalist foundation homepage
│   ├── components/                     # Reusable UI components
│   ├── lib/                            # Frontend utility functions
│   ├── public/                         # Static assets
│   ├── package.json                    # Frontend dependencies and scripts
│   ├── tsconfig.json                   # TypeScript configuration
│   ├── tailwind.config.ts              # Tailwind CSS design system config
│   ├── postcss.config.mjs              # PostCSS plugins
│   ├── eslint.config.mjs               # ESLint configuration
│   └── next.config.mjs                 # Next.js configuration
│
├── docs/
│   ├── ARCHITECTURE.md                 # System architecture & component responsibilities
│   └── DEVELOPMENT.md                  # Development environment and testing guide
│
├── scripts/                            # Operational and automation scripts
├── .gitignore                          # Git exclusions for Python, Node, OS, & secrets
├── README.md                           # Project overview and quickstart
└── LICENSE                             # MIT License
```

---

## 3. Prerequisites

- **Python:** 3.11 or later
- **Node.js:** 20 or later
- **npm:** 10 or later
- **Git:** 2.x or later

---

## 4. Quickstart Guide

### 4.1 Backend Setup & Execution

1. **Navigate to the backend directory and activate your virtual environment:**
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install dependencies:**
   ```powershell
   python -m pip install -e ".[dev]"
   ```

3. **Set up local environment configuration:**
   ```powershell
   copy .env.example .env
   ```

4. **Start the FastAPI server:**
   ```powershell
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

5. **Verify operation:**
   - Health check: `http://127.0.0.1:8000/api/v1/health`
   - Unified search: `http://127.0.0.1:8000/api/v1/search/unified`
   - Folders: `http://127.0.0.1:8000/api/v1/folders`
   - Indexing: `http://127.0.0.1:8000/api/v1/indexing/status`
   - System Diagnostics: `http://127.0.0.1:8000/api/v1/system/status`
   - API Docs: `http://127.0.0.1:8000/docs`

### 4.2 Frontend Setup & Execution

1. **Navigate to the frontend directory:**
   ```powershell
   cd frontend
   npm install
   ```

2. **Start the Next.js development server:**
   ```powershell
   npm run dev
   ```

3. **Open the interface in your browser:**
   - URL: `http://localhost:3000`

---

## 5. Running Automated Tests

Run the full backend test suite using `pytest`:

```powershell
.\backend\.venv\Scripts\pytest backend\tests -v
```

160 automated tests covering ingestion, normalization, chunking, hashing, database cascades, FTS5 BM25 search, EmbeddingGemma 2 local inference, ChromaDB vectors, RRF hybrid fusion, folder management, indexing control, unified search, system telemetry, and consistent error handling.

---

## 6. Architecture & Engineering Rules

- **Strict Local-First:** Original files never leave the host system.
- **Loopback Binding:** Backend binds to `127.0.0.1` by default, never `0.0.0.0`.
- **Clean Separation:** Presentation (Next.js) is strictly decoupled from the core engine (FastAPI).
- **No Mock Functionality:** No fake search results or mock progress bars are introduced. Features are built iteratively according to project phase scope.

For deeper architectural details, refer to [ARCHITECTURE.md](docs/ARCHITECTURE.md). For development guidelines, see [DEVELOPMENT.md](docs/DEVELOPMENT.md).

---

## 7. License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
