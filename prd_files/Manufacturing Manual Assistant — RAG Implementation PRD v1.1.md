# Product Requirements Document (PRD)

## Manufacturing Manual Assistant — RAG Implementation

**Version:** 1.1 **Project:** Manufacturing Manual Assistant **Module:** Retrieval-Augmented Generation (RAG) — *this PRD covers the RAG module only. Authentication, role enforcement (Administrator / Engineer / Supervisor), machine registration, and manual-upload workflows are specified in a separate application-level PRD.* **Backend:** Python + Django REST Framework **Status:** Development Specification

---

## 1. Product Overview

### 1.1 Objective

Build a Retrieval-Augmented Generation (RAG) system that allows engineers to ask natural-language questions about manufacturing machines and receive accurate, context-aware answers based exclusively on the supplied PDF manuals.

The system must retrieve relevant information from the correct machine's manuals, generate answers using an LLM, and provide verifiable citations containing:

- Document name
- Document revision
- PDF page number
- Supporting text passage
- Clickable link to the original PDF page

If the manuals do not contain sufficient information, the system must explicitly communicate that it cannot answer the question.

### 1.2 Core Principle

The LLM must never answer using its general knowledge. All technical answers must be grounded in passages retrieved from the selected machine's manuals.

### 1.3 Scope Boundary

This PRD specifies retrieval, grounding, generation, and citation integrity only. It assumes the calling application has already authenticated the user and confirmed they are permitted to ask questions. Manual ingestion triggered by an Administrator upload is referenced here only as a pipeline entry point (§5.1); the upload endpoint itself, its permissions, and machine-registration flows belong to the application-level PRD.

---

## 2. Technology Stack

| Component | Technology |
| --- | --- |
| Programming language | Python |
| PDF extraction | PyMuPDF |
| Text chunking | Custom Python implementation |
| Embedding model | Google Gemini Embedding API (`gemini-embedding-001`) |
| LLM | Google Gemini Flash API |
| Vector database | ChromaDB |
| Main database | PostgreSQL |
| Backend integration | Django REST Framework |
| Configuration | Python dotenv |
| Frontend integration | HTML, Bootstrap, JavaScript |

No LangChain, LangGraph, multi-agent framework, or autonomous agents are required. The RAG pipeline must be implemented using modular Python functions.

---

## 3. Input Documents

The system must process exactly three supplied PDF manuals.

| Document | Machine ID | Content |
| --- | --- | --- |
| HP200\_Operations\_Rev1\_0.pdf | M-HP200 | Operations, operating limits and alarms |
| HP200\_Maintenance\_Rev1\_0.pdf | M-HP200 | Inspection schedules and maintenance troubleshooting |
| AC90\_Operations\_Maintenance\_Rev1\_0.pdf | M-AC90 | Operations, limits, alarms and maintenance |

The `machine_manual_index.csv` file must only be used as machine registration metadata. It must not be indexed as a source of maintenance guidance. The challenge brief and START\_HERE.txt must not be included in the vector database.

**Page numbering:** PDF page 1 corresponds to page number 1. Printed page numbers match PDF page numbers.

---

## 4. Functional Requirements

### FR-01: PDF Text Extraction

The system must:

1. Accept PDF documents.
2. Extract text using PyMuPDF.
3. Process documents page by page.
4. Preserve the original PDF page number.
5. Ignore empty pages and near-empty pages — a page is treated as empty if, after stripping whitespace, it contains fewer than 20 characters of extractable text (e.g., a page with only a header/footer or page number). This threshold prevents gaps in chunk `page_number` sequences from being mistaken for extraction failures during QA.
6. Retain document and machine metadata for every extracted page.

Each extracted page must contain:

- Machine ID
- Manual ID
- Document name
- Revision
- PDF page number
- Extracted text

### FR-02: Text Chunking

Extracted text must be divided into smaller passages suitable for semantic retrieval.

Initial configuration:

| Parameter | Value |
| --- | --- |
| Chunk size | Approximately 500 tokens |
| Chunk overlap | Approximately 100 tokens |
| Chunk boundary | Must not cross PDF pages |
| Chunk ID | Unique and deterministic |

Each chunk must retain its original source metadata.

Example:

```json
{
  "chunk_id": "HP200_OP_P008_C001",
  "machine_id": "M-HP200",
  "manual_id": 1,
  "document_name": "HP200_Operations_Rev1_0.pdf",
  "revision": "1.0",
  "page_number": 8,
  "text": "Extracted manual passage..."
}
```

### FR-03: Embedding Generation

The system must use the hosted Gemini Embedding API.

Requirements:

1. Generate embeddings for every document chunk.
2. Use `RETRIEVAL_DOCUMENT` for manual passages.
3. Use `QUESTION_ANSWERING` for user questions (the documented Gemini pairing for QA-style retrieval: document side uses `RETRIEVAL_DOCUMENT`, query side uses `QUESTION_ANSWERING`).
4. Generate document embeddings during ingestion.
5. Generate query embeddings when an engineer asks a question.
6. Do not regenerate existing embeddings unnecessarily.
7. Handle API errors and rate limits gracefully (retry with backoff; surface a controlled error, never a silent failure).

Embedding generation must not require a locally hosted model or GPU.

### FR-04: Vector Database

Use a persistent ChromaDB collection named `manufacturing_manuals`.

Store:

- Unique chunk ID
- Chunk text
- Embedding vector
- Machine ID
- Manual ID
- Document name
- Revision
- PDF page number

Use deterministic IDs and upsert operations to prevent duplicate records during repeated ingestion. The collection must persist between application restarts.

### FR-05: Semantic Retrieval

When an engineer asks a question:

1. Receive the question and selected machine ID.
2. Validate the machine ID against PostgreSQL.
3. Generate the question embedding.
4. Search ChromaDB using semantic similarity, with the machine ID metadata filter applied **before** the similarity search (not as a post-hoc filter), so excluded-machine chunks are never scored against the query.
5. Retrieve the top five relevant chunks initially.
6. Return their text, metadata, IDs and similarity distances.
7. **Evidence sufficiency gate (two layers):**
   - **Layer 1 — retrieval-level cutoff:** discard any of the top-5 chunks whose similarity distance falls outside a calibrated threshold. This threshold must be derived empirically by running the supplied sample questions (§11) and recording the distance distribution for known-answerable vs. known-unanswerable questions, then setting the cutoff between the two clusters. If zero chunks survive this cutoff, skip LLM generation entirely and return `INSUFFICIENT` directly — this avoids asking the LLM to judge sufficiency from passages that are already known to be irrelevant.
   - **Layer 2 — LLM-level judgment:** for chunks that pass Layer 1, the LLM (FR-07) still independently decides `ANSWERED` vs `INSUFFICIENT`, since a chunk can be topically similar but not actually contain the answer.
8. Log the calibrated threshold value and the date/method of calibration in the retriever module's configuration, so it can be re-tuned if chunking or embedding parameters change.

The retrieval system must support multiple manuals belonging to the same machine. For example, an HP-200 question must be able to retrieve information from both HP-200 manuals. It must never retrieve AC-90 passages.

### FR-06: Context Construction

Retrieved passages must be assembled into a structured context before being sent to the LLM. Each passage must have a source identifier.

Example:

```text
[S1]

Document: HP200_Operations_Rev1_0.pdf
Revision: 1.0
Page: 8

Passage:
Extracted supporting text...

[S2]

Document: HP200_Maintenance_Rev1_0.pdf
Revision: 1.0
Page: 14

Passage:
Extracted supporting text...
```

Source identifiers must map to the actual retrieved chunk records.

### FR-07: LLM Answer Generation

Use Gemini Flash to generate answers.

The LLM must:

1. Answer only using supplied manual passages.
2. Avoid external knowledge.
3. Never invent technical specifications.
4. Cite supporting passages using source IDs.
5. Cite multiple sources when required.
6. Return an insufficient-evidence response when the manuals do not support an answer.
7. Follow a structured JSON response format.

Expected response:

```json
{
  "status": "ANSWERED",
  "answer": "The supported answer is ... [S1]",
  "used_sources": ["S1"]
}
```

Insufficient response:

```json
{
  "status": "INSUFFICIENT",
  "answer": "The available manuals do not contain sufficient information to answer this question.",
  "used_sources": []
}
```

The application must validate the JSON structure and all source identifiers before displaying the answer.

### FR-08: Citation Validation

Citation validation is mandatory. The backend must:

1. Receive source IDs returned by the LLM.
2. Verify that every source ID exists in the current retrieval result.
3. Resolve source IDs to trusted ChromaDB metadata.
4. Retrieve document name, revision, page number and manual ID from trusted records.
5. Reject invalid or fabricated source references.
6. Ensure displayed citations belong to the selected machine.

The LLM must never be trusted to generate document names, revisions or page numbers independently. A citation must always reference a passage actually retrieved for the current question.

### FR-09: PDF Source Access

Each citation must provide a clickable link to its original PDF.

Expected URL pattern: `/api/manuals/{manual_id}/pdf/#page={page_number}`

**Implementation note:** the `#page=N` fragment is a client-side PDF open parameter — it is never sent to the server, so it only auto-navigates when the rendering layer honors it. This works out of the box with a browser-native PDF.js viewer (e.g., rendering the PDF directly in an `<iframe>`/`<object>` pointed at the endpoint, relying on the browser's built-in PDF.js). If the frontend instead embeds a custom PDF viewer component, that component must explicitly support a page-navigation API and the fragment must be translated into that component's own page-jump call — do not assume `#page=N` works universally. This distinction should be confirmed early, since it directly affects whether TC-07 passes during demonstration.

Requirements:

- Open the correct PDF.
- Navigate to the cited PDF page.
- Require authentication.
- Enforce document access permissions.
- Use inline PDF rendering.
- Do not expose protected manuals through unrestricted public media URLs.

### FR-10: Question History Integration

The Django application must persist every question, including questions that cannot be answered.

Store:

- User ID
- Machine ID
- Question
- Generated answer
- Answer status
- Citation metadata
- Timestamp

Possible statuses: `ANSWERED`, `INSUFFICIENT`.

Citation metadata must be stored in PostgreSQL using a JSONField. (Review of saved history by a Supervisor role is handled by the application-level PRD; this module only guarantees the record is persisted and queryable.)

---

## 5. System Architecture

### 5.1 Document Ingestion Pipeline

PDF Manuals → PyMuPDF Extraction → Page-wise Text Chunking → Gemini Embedding API → ChromaDB Storage

This pipeline should execute during initial document ingestion or when a manual is newly supplied (triggered by the application-level upload flow, out of scope here).

### 5.2 Question Answering Pipeline

Engineer Question → Django API → Machine Validation → Gemini Query Embedding → Machine-filtered ChromaDB Retrieval → Evidence Sufficiency Gate (Layer 1 cutoff) → Context Construction → Gemini Flash → LLM Sufficiency Judgment (Layer 2) → Citation Validation → PostgreSQL History → Answer and Source Display

---

## 6. Module Structure

The RAG implementation must remain independent of Django-specific business logic wherever practical.

```text
rag/
│
├── __init__.py
├── embeddings.py
├── vector_store.py
├── retriever.py
├── generator.py
├── prompts.py
└── pipeline.py

manuals/
│
├── pdf_extractor.py
├── chunker.py
└── ingestion.py
```

| File | Responsibility |
| --- | --- |
| pdf\_extractor.py | Extract text and page numbers |
| chunker.py | Generate page-aware chunks |
| ingestion.py | Orchestrate manual ingestion |
| embeddings.py | Generate document and query embeddings |
| vector\_store.py | Manage ChromaDB operations |
| retriever.py | Retrieve relevant machine-specific passages; owns the Layer 1 similarity-cutoff logic and its calibrated threshold value |
| prompts.py | Maintain LLM instructions |
| generator.py | Generate structured answers; owns the Layer 2 sufficiency judgment |
| pipeline.py | Coordinate the complete RAG workflow |

---

## 7. API Requirements

The RAG module must expose a reusable Python function:

```python
answer_question(
    question="What does E17 mean?",
    machine_id="M-HP200"
)
```

Expected response:

```json
{
  "status": "ANSWERED",
  "answer": "The manual states that ... [S1]",
  "sources": [
    {
      "chunk_id": "HP200_OP_P012_C001",
      "manual_id": 1,
      "document_name": "HP200_Operations_Rev1_0.pdf",
      "revision": "1.0",
      "page_number": 12,
      "passage": "Supporting passage..."
    }
  ]
}
```

Django REST API: `POST /api/assistant/ask/`

Request:

```json
{
  "machine_id": "M-HP200",
  "question": "What does E17 mean?"
}
```

The endpoint must:

- Require authentication (role enforcement itself is defined in the application-level PRD; this endpoint assumes the caller has already been authorized to ask questions).
- Validate the selected machine.
- Call the RAG pipeline.
- Save the result and citations.
- Return the structured response.

---

## 8. Frontend Citation Requirements

The engineer interface must display:

1. Original question.
2. Generated answer.
3. Answer status.
4. Source document name.
5. Document revision.
6. PDF page number.
7. Supporting passage.
8. Clickable PDF link.

Example:

**Answer:** The machine's alarm indicates ... \[S1\]

**Sources**

- HP200\_Operations\_Rev1\_0.pdf
- Revision 1.0
- Page 12
- Supporting passage
- Open PDF at page 12

When the answer is insufficient, display a clear message instead of generating a speculative answer.

---

## 9. Non-Functional Requirements

**Accuracy**

- All factual answers must be grounded in retrieved passages.
- No fabricated citations.
- No cross-machine information leakage.
- No unsupported technical specifications.

**Performance**

- Embeddings must be generated once during ingestion.
- Avoid unnecessary API requests.
- Use persistent vector storage.
- Keep the initial retrieval count at five, subject to evaluation.

**Reliability**

- Handle embedding API failures.
- Handle LLM API failures.
- Handle malformed LLM responses.
- Handle empty retrieval results.
- Prevent duplicate ingestion.
- Do not mark failed ingestion as completed.

**Security**

- Keep API keys in environment variables.
- Never expose API keys in frontend code.
- Enforce machine-level retrieval filters.
- Validate all returned citation identifiers.
- (User-permission validation and PDF access control are enforced by the application-level PRD; this module exposes the hooks they rely on — the `machine_id` filter and the authenticated-caller assumption.)

---

## 10. Testing and Acceptance Criteria

The RAG module is considered complete only when the following tests pass.

| ID | Test case | Expected result |
| --- | --- | --- |
| TC-01 | Ask a supported HP-200 question | Correct grounded answer |
| TC-02 | Ask a question requiring both HP-200 manuals | Both relevant manuals cited |
| TC-03 | Ask an AC-90 question | AC-90 sources retrieved |
| TC-04 | Ask an HP-200 question while selecting AC-90 | No HP-200 passages retrieved |
| TC-05 | Ask a question absent from the selected machine's manuals | INSUFFICIENT |
| TC-06 | Return a fabricated source ID from the LLM | Citation rejected |
| TC-07 | Open a citation | Correct PDF and page (verify against the viewer approach chosen per FR-09) |
| TC-08 | Repeat document ingestion | No duplicate chunks |
| TC-09 | Gemini API fails | Controlled error response |
| TC-10 | Save an insufficient question | History record persisted |
| TC-11 *(new)* | Ask a question where top-5 retrieval distances all fall outside the calibrated cutoff | `INSUFFICIENT` returned without calling the LLM (Layer 1 short-circuit) |

### Mandatory automated tests

**Test 1 — Machine Isolation** Insert HP-200 and AC-90 chunks into a test ChromaDB collection. Retrieve using `M-HP200` and assert that every returned chunk belongs to HP-200.

**Test 2 — Citation Integrity** Provide retrieved source IDs and verify that the system rejects any source identifier not present in the retrieval result.

**Test 3 — Insufficient Evidence** Ask a question whose answer is not present in the selected machine's manuals. Confirm that the system does not generate an unsupported answer, including the Layer 1 short-circuit path (TC-11).

*(The application-level PRD owns the two role-based automated checks — "Engineers cannot upload manuals" and any corresponding permission tests — since upload and role enforcement are out of scope here.)*

---

## 11. Sample Evaluation Questions

Use the supplied challenge questions to validate the implementation, and to calibrate the FR-05 Layer 1 threshold (answerable vs. unanswerable distance clustering):

1. What does E17 mean?
2. What is the normal operating pressure range?
3. How often is the filter checked?
4. What should be recorded before escalation?
5. How often should the AC-90 AF-10 filter indicator be checked, and when is the planned filter replacement due?

The user must select a machine before asking each question. Expected answers must be evaluated against the actual PDF content, not assumptions.

---

## 12. Implementation Priorities

**Phase 1 — Core Ingestion**

- PDF extraction (with near-empty-page handling per FR-01)
- Page-wise chunking
- Embedding generation
- ChromaDB storage

**Phase 2 — Retrieval**

- Query embedding
- Semantic search
- Machine-specific filtering
- Layer 1 threshold calibration and evidence-sufficiency gate

**Phase 3 — Answer Generation**

- Context construction
- Gemini Flash integration
- Structured JSON output
- Layer 2 LLM sufficiency judgment
- Citation validation

**Phase 4 — Django Integration**

- Ask endpoint
- Question history
- Citation cards
- PDF page navigation (viewer approach confirmed per FR-09)

**Phase 5 — Testing**

- Machine isolation
- Supported answers
- Insufficient evidence (including Layer 1 short-circuit)
- Citation integrity
- API failure handling

---

## 13. Out of Scope

- Multiple AI agents
- LangGraph workflows
- Autonomous tool calling
- Internet search
- External knowledge retrieval
- Fine-tuning an LLM
- Training custom embedding models
- OCR for scanned documents unless required by the supplied PDFs
- Voice-based interaction
- General-purpose conversational memory
- Multi-stage autonomous reasoning
- Authentication, role enforcement, manual upload workflows, and machine registration (covered by the application-level PRD)

---

## 14. Definition of Done

The RAG implementation is complete when:

1. All three PDFs have been successfully ingested.
2. Every stored chunk has accurate source metadata.
3. Embeddings are generated through the hosted API.
4. Machine-specific semantic retrieval works, with the Layer 1 threshold calibrated against the sample questions.
5. Gemini generates grounded answers.
6. Unsupported questions return an insufficient-evidence response, at both the retrieval gate and the LLM judgment layer.
7. Every displayed citation maps to a real retrieved passage.
8. Citations open the correct PDF page, using a confirmed viewer navigation approach.
9. Questions, answers and sources are saved in PostgreSQL.
10. Mandatory automated tests, including TC-11, pass.

**Final Deliverable:** A modular, machine-aware RAG engine integrated with Django REST Framework, capable of answering manufacturing questions using the supplied manuals and displaying verifiable PDF citations.

---

**Implementation principle:** Prioritise retrieval accuracy, machine isolation and citation integrity over framework complexity. The system should be simple enough to build quickly, but reliable enough to demonstrate that every technical answer is supported by the original manuals.

---
