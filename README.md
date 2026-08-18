# DocQA — Chat With Your Docs

A fullstack Retrieval-Augmented Generation (RAG) application: upload PDF, Markdown, DOCX or text
files and ask questions about them. Built with **React 19 + TypeScript**, **FastAPI (Python 3.11+)**,
**Google Gemini**, **PostgreSQL 16** and **ChromaDB**.

Answers stream token-by-token over SSE with per-chunk source citations and relevance scores,
grounded by a measured relevance threshold, scoped to the authenticated tenant, and indexed
asynchronously so a large upload never blocks the request.

```
make docker-up   # full stack
make test        # 66 tests, no external services required
make eval        # retrieval quality against a golden set
```

---

## Quick Setup & How to Run

### Prerequisites
- [Docker & Docker Compose](https://docs.docker.com/get-docker/)
- Google Gemini API Key ([Get one from Google AI Studio](https://aistudio.google.com/apikey))

### 1. Run via Docker Compose (Recommended)

```bash
# 1. Clone repository
git clone <repo-url> && cd docqa

# 2. Configure environment
cp .env.example .env
# Edit .env and set your GEMINI_API_KEY

# 3. Build and launch all services
make docker-up
# or: docker compose up --build
```

**Services will be live at:**
- **Frontend UI:** [http://localhost:3000](http://localhost:3000)
- **FastAPI Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **PostgreSQL Database:** `localhost:5433` (`docqa` / `docqa_secret`)

---

### 2. Run Locally for Development

```bash
# Terminal 1: Start PostgreSQL container
docker compose up -d postgres

# Terminal 2: Run Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head          # create the schema (or: make migrate)
uvicorn src.main:app --reload --port 8000

# Terminal 3: Run Frontend
cd frontend
npm install
npm run dev # Available on http://localhost:5173
```

---

### 3. Available Makefile Commands

```bash
make help          # Show all available commands
make docker-up     # Build and start the full stack in Docker
make docker-down   # Stop containers
make migrate       # Apply database migrations (alembic upgrade head)
make migration m="add x"   # Autogenerate a new migration revision
make seed          # Seed the demo users
make test          # Backend (47 pytest) + frontend (19 vitest) suites
make lint          # ruff + oxlint + tsc
make eval          # RAG quality evaluation against the golden set (uses live API)
```

---

## System Architecture & End-to-End RAG Flow

```
   ┌────────────────────────────────────────────────────────┐
   │                   React 19 Frontend                    │
   │  - AuthModal (JWT Bearer)    - SSE Stream Client (JSON)│
   │  - ReactMarkdown (GFM / XSS) - Expandable Source Cards │
   └───────────────────────────┬────────────────────────────┘
                               │  REST & SSE (HTTP/1.1)
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │                   FastAPI Backend                      │
   │  - RequestLoggingMiddleware (X-Request-ID, latency ms) │
   │  - JWT bearer auth + per-tenant ownership checks       │
   │  - Sliding-window rate limits (chat / upload / auth)   │
   │  - BackgroundTasks: async ingest -> ready | failed     │
   │  - Blocking Chroma + embedding calls -> thread pool    │
   └─────────────┬───────────────────────────┬──────────────┘
                 │                           │
                 ▼                           ▼
   ┌───────────────────────────┐   ┌───────────────────────────┐
   │  PostgreSQL 16 (Alembic)  │   │   ChromaDB (vector store) │
   │  - users (bcrypt)         │   │  - cosine HNSW index      │
   │  - documents + status     │   │  - RETRIEVAL_DOCUMENT     │
   │  - conversations & msgs   │   │  - RETRIEVAL_QUERY        │
   │  - user_id indexed, FK    │   │  - where: {user_id}       │
   │    ON DELETE CASCADE      │   │  - relevance gate >= 0.60 │
   └───────────────────────────┘   └─────────────┬─────────────┘
                                                 │
                                                 ▼
                                   ┌───────────────────────────┐
                                   │      Google Gemini AI     │
                                   │  - gemini-embedding-001   │
                                   │  - gemini-3.5-flash LLM   │
                                   └───────────────────────────┘
```

### Document Ingestion Pipeline (asynchronous)

Upload returns **`202 Accepted`** immediately; parsing, chunking and embedding run detached from the
request. The `status` column is the contract with the client: `processing` → `ready` | `failed`.
The UI polls until it settles and surfaces the failure reason inline. This is what keeps a large PDF
from holding a worker (and the user) hostage for the length of an embedding run.

1. **Validation** (synchronous, in-request): extension allow-list, size cap (20MB), non-empty check.
   Rejections are immediate and specific — there is no point queueing work that cannot succeed.
2. **Extraction**: `pypdf`, `python-docx`, or UTF-8 decoding, selected by suffix.
3. **Recursive character splitting** along `\n\n` → `\n` → `. ` → ` `, so a chunk boundary lands on a
   paragraph break before it lands mid-sentence.
4. **Token-aware windowing**: 500 tokens with 50-token overlap, counted with `cl100k_base`. The
   overlap exists so a fact spanning a boundary survives in at least one chunk intact.
5. **Asymmetric document embeddings**: `task_type="RETRIEVAL_DOCUMENT"`, indexed with `user_id` and
   `document_id` metadata.
6. **Terminal state written back**: `ready` with a chunk count, or `failed` with the reason.

### Retrieval & Generation Pipeline
1. **Asymmetric Query Embedding**: The user's query is embedded with `task_type="RETRIEVAL_QUERY"`.
2. **Multi-Tenant Filtered Vector Search**: Chroma searches top-$K$ chunks with `where={"user_id": current_user.id}` to guarantee no cross-tenant leakage.
3. **Relevance Threshold Guardrail**: Chunks below `min_relevance_score = 0.60` (cosine similarity) are filtered out. That number is measured, not guessed — see *RAG Quality Evaluation* below. If no chunk meets the threshold, the system immediately returns a grounded fallback instead of hallucinating.
4. **Context Construction & Conversational History**: The retrieved chunks and the recent conversation history are injected into the prompt.
5. **Lossless SSE Streaming**: Each event is emitted as `event: <type>` plus a **JSON-encoded** `data:` payload, so newlines inside a token survive as `\n` escapes instead of breaking the SSE framing. The browser splits on the `\n\n` event boundary and `JSON.parse`s the payload, which keeps markdown lists, code blocks, and indentation intact.

---

### Prompt & Context Management

- **Fixed system instruction**: the model is told to answer *only* from supplied context, to name the documents it used, and to say plainly when the context is insufficient. It is kept separate from user input (`system_instruction`) so a question can never overwrite the rules.
- **Structured context block**: retrieved chunks are injected as `[Source N: filename]` blocks. Numbering them is what makes the model's citations checkable against the source cards in the UI.
- **Bounded conversation history**: only the last 6 turns are replayed. Enough for "what about the second one?" follow-ups, small enough that history never crowds out retrieved context.
- **Deterministic-leaning decoding**: `temperature=0.3` and `max_output_tokens=1500` — for grounded Q&A, reproducibility matters more than variety.
- **Retrieval budget**: `TOP_K=5` chunks of 500 tokens caps context at roughly 2.5k tokens, which keeps latency and cost predictable.

---

## Key Technical Decisions & Architectural Trade-offs

| Decision Area | Chosen Approach | Considered Alternatives | Rationale |
|---|---|---|---|
| **Relational Database** | **PostgreSQL 16 + asyncpg** | SQLite (aiosqlite) | Real concurrent writes, relational constraints (`ON DELETE CASCADE`), robust connection lifecycle, and production readiness. |
| **Vector Index** | **ChromaDB (Embedded Persistent)** | pgvector, Pinecone, Qdrant | Zero external cluster overhead for local evaluation, fast cosine HNSW index, simple metadata filtering per `user_id`. |
| **Embedding Strategy** | **Asymmetric GenAI Embeddings** (`gemini-embedding-001`) | Symmetric text embeddings | Asymmetric embeddings (`RETRIEVAL_DOCUMENT` vs `RETRIEVAL_QUERY`) significantly boost retrieval precision by modeling query-document semantic relationships. |
| **LLM Model** | **`gemini-3.5-flash`** | GPT-4o, Claude 3.5 Sonnet | Ultra-fast Time-To-First-Token (TTFT), native long-context support, highly cost-effective for document Q&A. |
| **Streaming Protocol** | **Server-Sent Events (SSE)** | WebSockets | Unidirectional HTTP/1.1 streaming is simpler, works seamlessly through HTTP proxies/load balancers, and has native client reconnect support. |
| **Frontend Styling** | **Modern Modular CSS (Design Tokens)** | TailwindCSS, SCSS | Clean CSS custom properties in runtime, zero preprocessor build overhead, easy maintainability without class explosion. |
| **Schema Management** | **Alembic migrations**, applied by the container entrypoint | `create_all()` on startup | A schema change should be an explicit, reviewable, reversible deploy step — not a side effect of a process restart. |
| **Ingestion Model** | **`BackgroundTasks` + status column** | Synchronous in-request indexing; Celery/SQS | Keeps upload responsive and makes failure a first-class state, without adding a broker to a prototype. The queue is the next step, not this step. |
| **Rate Limiting** | **In-process sliding window** | Redis counters, API gateway | Bounds spend and brute-force on a single instance with zero extra infrastructure. Explicitly wrong for multiple replicas — noted below. |
| **Markdown Security** | **`react-markdown` + `remark-gfm`** | `dangerouslySetInnerHTML` | Complete immunity against stored XSS attacks while rendering GitHub Flavored Markdown (tables, code blocks, bullet points). |

---

## Security & Multi-Tenant Isolation Model

1. **Authentication (Bcrypt + JWT)**:
   - Passwords hashed with `bcrypt` (work factor 12).
   - Stateless JWT Bearer tokens signed with `HS256`.
2. **Multi-Tenant Data Isolation**:
   - **SQL Level**: Every database query (`documents`, `conversations`, `chat_messages`) filters strictly on `where(user_id == current_user.id)`. Direct ID queries verify ownership and return `404 Not Found` if accessed by unauthorized users.
   - **Vector Store Level**: Chroma search applies `where={"user_id": current_user.id}`. Chunks are never shared between tenants.
   - **Deletion Safety**: Document deletion uses targeted metadata filters `collection.delete(where={"document_id": doc_id})` without loading entire collections into memory.
3. **Abuse & Cost Controls**:
   - Sliding-window rate limits per authenticated user on chat (20/min) and upload (10/min), and
     per client address on login/register (10/min) to blunt credential stuffing.
   - `429` responses carry `Retry-After`.
   - Upstream `429`/`5xx` from Gemini are retried with exponential backoff and jitter; streaming
     retries only before the first token, since restarting mid-stream would duplicate text.
4. **Observability & Request Tracing**:
   - `RequestLoggingMiddleware` assigns/propagates `X-Request-ID` and logs `duration_ms` for every HTTP interaction in structured JSON, and echoes both back as the `X-Request-ID` and `X-Process-Time-Ms` response headers.

---

## Production Scalability (AWS / GCP / Azure Blueprint)

To scale DocQA to thousands of concurrent enterprise users:

```
[Route 53 / Cloudflare DNS] ──> [AWS ALB / GCP Cloud Load Balancer]
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
          [ECS Fargate / Cloud Run]                       [S3 / Cloud Storage]
             Backend API Pods                                Document Files
             (Autoscaling 2-20)
                      │
     ┌────────────────┼────────────────────────┐
     ▼                ▼                        ▼
[AWS RDS Postgres] [Managed Qdrant/Pinecone] [SQS / Celery Worker]
  Primary + Read      Distributed Vector DB      Asynchronous Parsing
     Replicas          with Tenant Sharding        & Chunk Embeddings
```

1. **Database Tier**: AWS Aurora PostgreSQL / GCP Cloud SQL with read replicas for conversation queries and connection pooling (PgBouncer).
2. **Vector Database**: Migrate embedded ChromaDB to distributed **Qdrant** or **Pinecone** with payload-based tenant sharding and HNSW cosine indexing.
3. **Asynchronous Ingestion Queue**: the status model (`processing` → `ready` | `failed`) and the
   detached ingestion path already exist; production swaps `BackgroundTasks` for Celery/ARQ on
   SQS so the work survives a process restart and gains retries and dead-lettering.
4. **Object Storage**: Store original uploaded files in AWS S3 or GCP Cloud Storage with pre-signed URLs and server-side encryption (`SSE-S3`).
5. **Security Hardening**: Move JWT tokens from `localStorage` to `httpOnly`, `SameSite=Strict` cookies with short-lived access tokens (15m) and rotating refresh tokens.

---

## Testing & Quality Assurance

DocQA includes a comprehensive test suite covering unit logic and full multi-tenant integration flows:

```bash
# Run pytest test suite
make test
```

### Test Coverage Breakdown (66 tests)

**Backend — 47 pytest tests.** The suite is **hermetic**: `conftest.py` repoints the app at a
throwaway SQLite file and temp Chroma/upload directories before `src.config` is imported, and stubs
the embedding-backed vector store. `make test` passes on a clean checkout with **no PostgreSQL, no
Docker, and no API key**, and never writes to a developer's database.

- *Unit*: JWT lifecycle and bcrypt verification; PDF/DOCX/MD/TXT extraction; recursive chunking and
  token bounds; context assembly, relevance scoring and the below-threshold fallback; the rate
  limiter's window, per-key independence and expiry; LLM retry policy (transient retried, permanent
  not, retries bounded), prompt construction, and that upstream provider payloads never leak into a
  user-facing error.
- *Integration (real HTTP through the ASGI app)*: 401 on every protected route; register → login →
  `/me`; duplicate email, wrong password, tampered token; **conversation isolation** and **document
  isolation** between tenants, including that a cross-tenant delete returns 404 and leaves the
  owner's data intact; ingestion lifecycle (`202` → `ready`, `202` → `failed` with a reason, a failed
  document not poisoning later uploads); upload validation; health reporting healthy and degraded.

**Frontend — 19 vitest tests.** Focused on the parts that actually broke:

- *SSE parsing*: multi-line markdown, code fences and blank lines survive byte-exact; events split
  across arbitrary network chunk boundaries (down to 1 byte per read) reassemble correctly; meta,
  sources, error and failed-request paths.
- *Message rendering*: markdown becomes real DOM (lists, tables, `<strong>`, `<code>`); HTML in model
  output is inert — the stored-XSS regression guard; sources appear only once streaming ends; source
  cards are numbered to match the `[Source N]` markers the model cites, and expand to their chunk text.
- *Document polling*: polls while indexing, stops once settled, reports ready and failed outcomes,
  fetches nothing while signed out.

---

## RAG Quality Evaluation

`make eval` scores retrieval and grounding against `backend/evals/golden_set.json` — 12 cases: 9
answerable from the sample documents, 3 deliberately out-of-scope. `--retrieval-only` skips
generation, which makes it cheap enough to run in CI.

| Metric | Result | What it measures |
|---|---|---|
| **Recall@5** | **100%** | The document holding the answer was retrieved |
| **MRR** | **1.000** | It was ranked first, every time |
| **Refusal accuracy** | **100%** | Out-of-scope questions are refused, not answered |

**This harness earned its keep immediately.** I originally set the relevance threshold to `0.35` by
intuition and documented it as though it were considered. The first eval run reported **refusal
accuracy of 0%** — every out-of-scope question ("what's the weather in Kyiv?") still cleared the bar
and reached the model. Dumping the score distribution showed the real separation:

```
in-scope  top-1 similarity: 0.632 – 0.747
out-scope top-1 similarity: 0.530 – 0.582   ← comfortably below
```

The threshold moved to `0.60`, sitting in the gap, and refusal accuracy went to 100% with recall
unchanged. The guardrail is a deterministic gate that runs *before* the model is called — I would
rather enforce that in code than ask a prompt to be disciplined.

Caveat worth stating: two documents is a small corpus, and MRR of 1.000 says more about the corpus
than about the retriever. The value here is the loop, not the number.

---

## Engineering Standards Followed — and Consciously Skipped

**Followed**
- Layered structure (`routes → services → stores`) with dependency injection, so the RAG pipeline is
  testable without HTTP and the vector store is stubbable without network.
- `ruff` lint + format across `src/`, `tests/`, `evals/`; `oxlint` and strict `tsc` (`noUnusedLocals`,
  `noUnusedParameters`) on the frontend. `make lint` gates all of it.
- Typed boundaries end to end: Pydantic schemas on the API, explicit TS interfaces on the client,
  `DocumentStatus` as a real enum on both sides rather than a loose string.
- Schema owned by Alembic and applied by the container entrypoint — never by application code.
- Structured JSON logging with request IDs and latency; no `print`, no bare `except` that silently
  swallows a failure.
- Multi-tenant isolation enforced in code **and pinned by integration tests** for both documents and
  conversations — a claim in a README is not a guarantee, a failing test is.
- Retrieval quality measured against a golden set, with thresholds that fail the run.
- Fail-fast config: `APP_ENV=production` refuses a default `JWT_SECRET` or a missing API key.
- Containers run as non-root with `.dockerignore` on both images; the dependency manifest is complete
  (verified by diffing actual imports against `pyproject.toml`).
- Resilience where the network is: retry with exponential backoff and jitter on transient upstream
  failures, rate limits on the expensive and brute-forceable endpoints.

**Skipped, deliberately**
- **No message broker.** Ingestion uses FastAPI `BackgroundTasks`: correct status model, responsive
  upload, but the work dies with the process — no retries, no cross-process visibility. Real queue
  (SQS/Celery) is the next step, and the status column is already the interface it would plug into.
- **Rate limiting is process-local.** Correct for one instance, wrong behind a load balancer. Shared
  counters or gateway-level limiting is the production answer; I did not want a Redis dependency
  carrying this little weight.
- **No refresh tokens.** A single 24h access token in `localStorage`. With XSS closed at the render
  layer, the added CSRF surface of cookie auth was not worth it here — but httpOnly cookies with
  short-lived rotated tokens is the right production answer, not this.
- **No OCR.** Scanned, image-only PDFs yield no text and correctly land in `failed` rather than
  indexing silently as empty.
- **No E2E browser tests.** Component and hook level only; Playwright would be the next layer.

---

## Known Limitations

- ChromaDB runs embedded, so the backend is effectively single-node; concurrent replicas would each
  hold their own index.
- Chunking is structure-agnostic — a metrics table can be split across chunks.
- Retrieval is dense-only: exact identifiers like `REL-2026-Q2-V4` are a weak spot until BM25 is
  fused in.
- The golden set is small (12 cases over 2 documents). It catches regressions; it does not prove
  general quality.
- Conversation history is truncated at 6 turns with no summarisation, so very long threads lose
  early context.

---

## How I Used AI Tools

Claude Code and Cursor are how I write software day to day, and this project was built that way
throughout. What does not get delegated is the decision. The tenant isolation model, the SSE wire
format, where the async boundary sits between the upload request and indexing, what the retrieval
contract between the pipeline and the vector store is — I decide those, then hand them to the
model as constraints to execute against.

That distinction is the whole job. A model will produce a confident, clean, working implementation
of the wrong design, and that is the failure you do not notice in review, because nothing about it
looks broken. Choosing 404 over 403 for another tenant's resource, refusing to add Redis for a
cache nothing needed, putting the refusal guardrail in deterministic code instead of in the prompt
— none of those are things I would want inferred. They are decided, stated up front, and then the
model is very good at carrying them through consistently.

So the interesting question is not how much I delegated. It is what I built around the model so
that working this way stays safe, repeatable, and reviewable by someone else.

### The model writes; the harness decides what survives

Speed of generation stopped being the constraint a while ago. The constraint is how fast I can
*tell whether the output is correct*. Everything below exists to shorten that loop, because a
short loop is what turns review from a bottleneck into something that keeps up with the work.

Three things do the deciding, and none of them is my opinion:

- **`make lint`** — ruff, oxlint and a strict `tsc` absorb the entire class of stylistic
  argument, so review time goes to logic instead of formatting.
- **`make test`** — 66 tests, hermetic by construction: no PostgreSQL, no Docker, no API key.
  That matters specifically for AI-assisted work, because a suite that needs a live environment
  is a suite you stop running mid-session, and the moment you stop running it you are accepting
  generated code on faith.
- **`make eval`** — retrieval scored against a golden set with thresholds that fail the run.
  Prompt and retrieval changes are exactly where a model's output is most confident and least
  verifiable, so that is where an automated measure earns the most.

"Make the tests pass" is a far better instruction than "make it cleaner", because it is
checkable. Most of my prompting is arranging for the checkable version of the request to exist.

### Context engineering — what actually determines output quality

- **Invariants before the task.** Before asking for a route I state the constraints that must
  hold: every query filters on `current_user.id`, services never import routes, no bare `except`,
  ownership failures return 404 rather than 403. Constraints given up front are honoured;
  the same constraints given afterwards as corrections get applied halfway.
- **The repository is the prompt.** Once `documents.py` demonstrates the ownership-check pattern,
  "add a delete endpoint for X" produces the right shape without restating the rules. Time spent
  on internal consistency pays back as fewer corrections later — this is the main thing that makes
  the workflow repeatable rather than a sequence of lucky sessions.
- **A stale working set is a bug.** When output starts drifting toward code that no longer exists,
  that is a context problem, not a model problem. I clear it and re-seed with the current files
  rather than arguing with it.
- **Small diffs.** Not because the model cannot produce large ones, but because I cannot review
  large ones honestly, and an unreviewed diff is where the expensive mistakes hide.

### Prompt engineering inside the product

The same discipline applies to the prompts this application ships (`llm_service.py`):

- Rules live in `system_instruction`, separate from user input, so a question cannot restate the
  rules. Retrieved context is injected as numbered `[Source N: filename]` blocks — the numbering
  is what makes a citation checkable against the source cards in the UI rather than merely
  plausible.
- The refusal path is not left to the prompt's good intentions. "Say when you don't know" is a
  suggestion; the relevance threshold in `rag_pipeline.py` is a gate that runs before the model is
  called at all. Anything that matters gets enforced in deterministic code, not requested politely.
- History is capped at six turns, output at 1500 tokens, temperature at 0.3. Bounded context is a
  correctness property, not only a cost one — an unbounded history quietly pushes retrieved chunks
  out of the model's attention.

### Where the output was wrong, and what caught it

Three from this build. None was caught by reading the diff:

1. **A dependency the code imported but the manifest never declared.** Tests passed locally
   because the package was still in the virtualenv; a clean container would have crashed on
   import. Found by diffing actual imports against `pyproject.toml`.
2. **A Docker healthcheck importing a dev-only dependency.** It would have kept the backend
   permanently unhealthy, and the frontend — which waits on `service_healthy` — would never have
   started.
3. **The relevance threshold was wrong.** `0.35` was a plausible number, and I documented it as
   though it were considered. The eval harness reported 0% refusal accuracy: out-of-scope
   questions were still clearing the bar. Measuring the score distribution gave in-scope
   0.63–0.75 against out-of-scope 0.53–0.58, so it moved to `0.60` and refusal accuracy went
   to 100%.

The third is the honest lesson. It was plausible, documented, and wrong — and no amount of code
review would have found it. That is the argument for building the measurement before trusting
the judgement, mine or the model's.

### My do's and don'ts

**Do:** state invariants before asking; keep diffs small enough to actually read; make the model
prove its claims by running something rather than asserting it; treat a stale-context session as
disposable; let lint and types own the whole class of nitpicks; write the check first when the
change touches retrieval or prompts.

**Don't:** accept a green suite as proof the tests are meaningful — the integration tests here
passed while writing to a live dev database and failing on any machine without it; let generated
prose into a README unchecked, because it will confidently describe a feature that does not exist
(this one claimed a Redis cache that was never wired to anything); delegate anything
security-shaped without reading every line, since that is the one area where a plausible-looking
answer and a correct one are indistinguishable without close reading.

## What I'd Do Differently With More Time

1. **Hybrid retrieval (BM25 + dense) with Reciprocal Rank Fusion.** Dense embeddings are weak on
   exact identifiers — `REL-2026-Q2-V4` is a token soup to an embedding model but trivial for
   keyword search. The golden set would tell me immediately whether it helps.
2. **A cross-encoder reranker** over top-15 → top-5. The current MRR of 1.000 is on a two-document
   corpus; at a realistic corpus size ranking is where quality actually goes.
3. **Extend the eval into a proper RAG triad** (faithfulness / answer relevance / context precision,
   via Ragas), and run the retrieval half in CI on every PR — it is cheap and needs no generation.
4. **Structure-aware chunking.** The release notes contain a metrics table that the current splitter
   can cut in half. Parsing tables as units, and carrying section headings into chunk metadata,
   is the highest-value retrieval fix left.
5. **Move ingestion to a real queue** (SQS/Celery). `BackgroundTasks` gives a correct status model
   and a responsive upload, but the work still dies with the process — no retries, no visibility.
6. **httpOnly cookie auth with short-lived access tokens and rotation.** Deliberately skipped here:
   with XSS closed and a 24h token, the added CSRF surface was not worth it for a demo — but it is
   the right production answer.
7. **Token and cost telemetry per request**, exported as OpenTelemetry spans alongside the existing
   request IDs, so latency and spend are attributable per tenant.
