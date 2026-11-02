# Product Requirements Document (PRD)

## Manufacturing Manual Assistant — Web Application

**Version:** 1.0 **Project:** Manufacturing Manual Assistant **Module:** Full Application (Django + DRF + PostgreSQL + Frontend). The RAG retrieval/generation/citation engine is specified in a companion document, *Manufacturing Manual Assistant — RAG Implementation PRD*, and is consumed here as a single function, `answer_question(question, machine_id)`. **Backend:** Python + Django REST Framework **Status:** Development Specification

---

## 1. Product Overview

### 1.1 Objective

Build a web application that lets engineers ask natural-language questions about manufacturing machines and get answers grounded in the machine's PDF manuals, with verifiable citations back to the source page. Administrators register machines and upload manuals; Engineers ask questions and review their own history; Supervisors review all question history, including unanswered queries, read-only.

### 1.2 Users and Roles

| Role | Capabilities |
| --- | --- |
| Administrator | Log in; register machines; upload manuals with model and revision metadata; trigger ingestion |
| Engineer | Log in; select a machine; ask questions; view own question history; open cited PDF pages |
| Supervisor | Log in; read-only review of all question history across engineers, including unanswered queries |

Roles are mutually exclusive per user for this build (one role per account) and are enforced on the server on every request, never inferred from frontend state alone.

### 1.3 Core Principles

- Every technical answer must be grounded in retrieved manual passages; the LLM must never answer from general knowledge (enforced by the RAG module; see the companion PRD).
- Only Administrators may upload manuals or register machines.
- Engineers can only ask questions and see their own history; they cannot upload manuals.
- Supervisors have read-only access to all history; they cannot ask questions or upload manuals (unless also granted the Engineer role).
- All role checks happen server-side in Django views and permissions, never solely in the frontend.

---

## 2. Technology Stack

| Component | Technology |
| --- | --- |
| Programming language | Python |
| Backend framework | Django |
| API layer | Django REST Framework |
| Database | PostgreSQL |
| Authentication | Django's built-in auth (session or token-based DRF auth) |
| Authorization | Django permission classes and groups, mapped to Administrator, Engineer, Supervisor |
| PDF extraction | PyMuPDF (via the RAG module) |
| Vector database | ChromaDB (via the RAG module) |
| Embedding model | Google Gemini Embedding API (via the RAG module) |
| LLM | Google Gemini Flash API (via the RAG module) |
| Configuration | Python dotenv |
| Frontend | HTML, Bootstrap, JavaScript |

---

## 3. User Workflows

### 3.1 Administrator

1. Log in.
2. Register a machine: machine ID (e.g. M-HP200), model name, description.
3. Upload one or more manuals for that machine: PDF file, document name, revision.
4. System triggers the RAG ingestion pipeline (extraction, chunking, embedding, vector storage) for the uploaded manual.
5. See ingestion status (pending, complete, or failed) per manual.

### 3.2 Engineer

1. Log in.
2. Select a machine from the registered list.
3. Ask a question in natural language.
4. Read the generated answer, its status (ANSWERED or INSUFFICIENT), and its citations (document, revision, page, passage).
5. Open a citation to view the source PDF at the cited page.
6. View their own question history.

### 3.3 Supervisor

1. Log in.
2. View a read-only list of all questions asked across all engineers: question, machine, answer, status, citations, timestamp, asking engineer.
3. Filter or sort by status to identify unanswered (INSUFFICIENT) queries.

---

## 4. Functional Requirements

### FR-A01: Authentication

1. Users log in with username and password (Django auth).
2. Each user account has exactly one role: Administrator, Engineer, or Supervisor.
3. Unauthenticated requests to any API endpoint other than login are rejected with 401.
4. Session or token expiry follows Django/DRF defaults unless otherwise specified.

### FR-A02: Role Enforcement

1. Every API endpoint declares the roles permitted to call it, enforced via a DRF permission class (e.g. IsAdministrator, IsEngineer, IsSupervisor).
2. A request from a user whose role is not permitted for that endpoint returns 403, with no partial data leaked.
3. Role is read from the authenticated user's server-side record, never from a request header, query parameter, or frontend-supplied field.
4. This is independently testable: see TC-A01 and TC-A02 in §10.

### FR-A03: Machine Registration

Administrator-only. The system must:

1. Accept a machine ID, model name, and optional description.
2. Reject duplicate machine IDs.
3. Persist the machine record in PostgreSQL.
4. Make the machine selectable by Engineers only after at least one manual has been successfully ingested for it (confirm in §12).

### FR-A04: Manual Upload

Administrator-only. The system must:

1. Accept a PDF file, the target machine ID, document name, and revision string.
2. Reject the upload if the machine ID does not exist.
3. Store the PDF in protected storage, not a public media URL (see FR-A07).
4. Create a manual record: manual ID, machine ID, document name, revision, upload timestamp, ingestion status.
5. Trigger the RAG ingestion pipeline (synchronously or asynchronously, per implementation choice) and update ingestion status to complete or failed.
6. Never mark a manual as ingested if extraction, chunking, or embedding failed partway, matching the RAG PRD's reliability requirement that failed ingestion is never marked complete.
7. Re-uploading the same document name and revision for the same machine must not create duplicate chunks, delegating to the RAG module's deterministic-ID upsert behavior.

### FR-A05: Question Answering Endpoint

Engineer-only (confirm whether Administrators may also ask questions in §12). The system must:

1. Accept a machine ID and a question from an authenticated Engineer.
2. Validate the machine ID exists and has at least one ingested manual.
3. Call the RAG module's answer\_question(question, machine\_id).
4. Persist the question, answer, status, citations, asking user, and timestamp (FR-A06).
5. Return the structured response (status, answer, sources) to the frontend.
6. Return a clear error, not a silent failure, if the RAG module itself fails (e.g. a Gemini API outage). The question is still persisted with a system-error status distinct from INSUFFICIENT, so Supervisors can tell a lack of evidence apart from a system error.

### FR-A06: Question History Persistence

The system must store, per question asked:

- Asking user (foreign key)
- Machine ID
- Question text
- Generated answer text
- Status (ANSWERED, INSUFFICIENT, or a system-error status per FR-A05.6)
- Citation metadata (JSONField: document name, revision, page number, passage, per source)
- Timestamp

Engineers can list and view only their own history. Supervisors can list and view all history, read-only.

### FR-A07: Protected PDF Access

1. PDFs are served through an authenticated endpoint, not a public media URL.
2. The endpoint checks that the requesting user is authenticated and, where access is further restricted, authorized to view that manual.
3. The endpoint renders the PDF inline, navigable to the cited page. See the RAG PRD's FR-09 implementation note on viewer compatibility for the page-fragment approach.

### FR-A08: Frontend — Administrator

- Machine registration form.
- Manual upload form (file, machine, document name, revision) with ingestion status feedback.
- List of registered machines and their manuals, with ingestion status.

### FR-A09: Frontend — Engineer

- Machine selector.
- Question input and submit.
- Answer display: status, answer text, citation cards (document, revision, page, passage, open-PDF link).
- A clear insufficient-evidence message state, visually distinct from a normal answer.
- Own question history list.

### FR-A10: Frontend — Supervisor

- Read-only table of all questions: engineer, machine, question, status, timestamp.
- Filter or sort by status, surfacing INSUFFICIENT and error-status rows for easy review.
- Click-through to full detail (answer, citations) per row.

---

## 5. System Architecture

```text
Browser (HTML/Bootstrap/JS)
  |
  v
Django REST Framework API
  - Auth and Role Permission Layer
  - Machine Registration (Admin)
  - Manual Upload -> RAG Ingestion Pipeline (Admin)
  - Ask Endpoint -> RAG Question-Answering Pipeline (Engineer)
  - History Endpoints (Engineer: own; Supervisor: all, read-only)
  - Protected PDF Endpoint
  |
  v
PostgreSQL (users, roles, machines, manuals, question history)
  |
  v
RAG Module (separate PRD): PyMuPDF -> Chunking -> Gemini Embeddings -> ChromaDB -> Gemini Flash -> Citation Validation
```

---

## 6. Data Model (indicative)

| Model | Key fields |
| --- | --- |
| User | username, password (Django auth), role (Administrator, Engineer, or Supervisor) |
| Machine | machine\_id (unique), model\_name, description, created\_at |
| Manual | manual\_id, machine (FK), document\_name, revision, file (protected storage), ingestion\_status, uploaded\_by (FK User), uploaded\_at |
| Question | id, user (FK), machine (FK), question\_text, answer\_text, status, citations (JSONField), created\_at |

---

## 7. API Requirements

| Endpoint | Method | Role | Purpose |
| --- | --- | --- | --- |
| /api/auth/login/ | POST | Any | Authenticate, return session or token |
| /api/machines/ | GET | Any authenticated | List registered machines |
| /api/machines/ | POST | Administrator | Register a machine |
| /api/manuals/ | POST | Administrator | Upload a manual (multipart: file plus metadata) |
| /api/manuals/{manual\_id}/pdf/ | GET | Any authenticated, access-checked | Inline PDF, navigable to the cited page |
| /api/assistant/ask/ | POST | Engineer | Ask a question; returns structured answer and citations |
| /api/assistant/history/ | GET | Engineer | List the requesting engineer's own question history |
| /api/assistant/history/all/ | GET | Supervisor | List all question history, read-only |

Every endpoint except login must reject unauthenticated requests with 401 and requests from a role not listed above with 403.

---

## 8. Non-Functional Requirements

**Security**

- API keys (Gemini, etc.) kept server-side in environment variables, never exposed to the frontend.
- Role checks on every request, server-side only.
- PDF files never served through unauthenticated or public media URLs.
- Passwords handled through Django's standard hashing, never stored or logged in plain text.

**Reliability**

- Manual upload failures (extraction, embedding, or storage) must leave the manual marked failed, not complete.
- Re-uploading a manual must not duplicate chunks or history records.
- RAG module failures (FR-A05.6) must be distinguishable from a lack of evidence, both in the stored record and in the frontend display.

**Usability**

- Engineers must always see a clear, unambiguous state: answered, insufficient evidence, or system error, never a blank or ambiguous result.
- Supervisors must be able to find unanswered queries without manually reading every row (status filter, FR-A10).

---

## 9. Testing and Acceptance Criteria

| ID | Test case | Expected result |
| --- | --- | --- |
| TC-A01 | Engineer attempts POST /api/manuals/ | 403 Forbidden; no manual created |
| TC-A02 | Engineer attempts GET /api/assistant/history/all/ | 403 Forbidden; no cross-engineer data returned |
| TC-A03 | Administrator registers a machine, then uploads a manual for it | Machine and manual persisted; ingestion status transitions to complete |
| TC-A04 | Administrator uploads a manual for a non-existent machine ID | Upload rejected with a clear error |
| TC-A05 | Engineer asks a question, views it in their own history | Record appears with correct status and citations |
| TC-A06 | Supervisor views history | Sees the Engineer's question from TC-A05, read-only, cannot edit or delete |
| TC-A07 | Unauthenticated request to any protected endpoint | 401 Unauthorized |
| TC-A08 | Re-upload of the same manual (same document name and revision) | No duplicate chunks, no duplicate manual record |
| TC-A09 | RAG module unreachable (simulated Gemini API failure) during /ask/ | Controlled error status returned and persisted, distinct from INSUFFICIENT |
| TC-A10 | Engineer opens a citation link | Correct PDF opens at the cited page |

### Mandatory automated tests (brief requirement)

**Test A — Upload Restriction** As an authenticated Engineer, call POST /api/manuals/. Assert the response is 403 and no manual record was created.

**Test B — Machine Isolation** (owned by the RAG module; re-asserted here at the API layer) Ask a question against M-HP200 via /api/assistant/ask/ and assert no AC-90 citations appear in the response.

---

## 10. Implementation Priorities

**Phase 1 — Auth and Roles**

- User model with role field
- Login endpoint
- DRF permission classes per role

**Phase 2 — Administrator Flows**

- Machine registration endpoint and frontend form
- Manual upload endpoint and frontend form
- Wire upload to the RAG ingestion pipeline; ingestion status tracking

**Phase 3 — Engineer Flow**

- Ask endpoint wired to the RAG module's answer\_question
- Citation display and protected PDF endpoint
- Own-history endpoint and frontend list

**Phase 4 — Supervisor Flow**

- Read-only all-history endpoint and frontend table with status filter

**Phase 5 — Testing**

- Role-restriction tests (TC-A01, TC-A02, Test A)
- End-to-end flow per role
- Failure-mode tests (TC-A04, TC-A08, TC-A09)

---

## 11. Out of Scope

- Multi-role accounts (one role per user in this build)
- Password reset or email verification flows, unless the environment requires them
- Editing or deleting question history, by any role
- Anything listed as out of scope in the companion RAG Implementation PRD: multi-agent frameworks, autonomous tool calling, internet search, fine-tuning, OCR beyond what the supplied PDFs need, voice interaction

---

## 12. Open Questions

1. Can an Administrator also ask questions, i.e. does the Ask endpoint permit Administrator in addition to Engineer, or is asking strictly Engineer-only as the brief implies?
2. Should a machine be selectable by Engineers before any manual has been ingested for it, or only after, as FR-A03.4 assumes?
3. Is a Supervisor permitted to also hold the Engineer role on the same account, or must every account be single-role for the demo?

---

## 13. Definition of Done

The web application is complete when:

1. All three roles can log in and are restricted to their own capabilities, enforced server-side.
2. An Administrator can register a machine and upload a manual, which is successfully ingested by the RAG module.
3. An Engineer can select a machine, ask a question, and receive a grounded, cited answer or a clear insufficient-evidence message.
4. An Engineer cannot upload manuals (TC-A01 and Test A pass).
5. A Supervisor can review all question history, including unanswered queries, read-only.
6. Citations open the correct PDF at the correct page.
7. All endpoints reject unauthenticated and wrong-role requests.
8. Mandatory automated tests (Test A here; Tests 1 through 3 in the RAG PRD) pass.

**Final Deliverable:** A Django REST Framework web application with PostgreSQL persistence, role-enforced Administrator, Engineer, and Supervisor workflows, and a Bootstrap/JS frontend, integrating the separately specified RAG module to answer manufacturing questions with verifiable PDF citations.
