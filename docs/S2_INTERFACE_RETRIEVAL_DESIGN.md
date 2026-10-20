# Sprint 2 Interface and Retrieval Design

**Owner:** Nguyễn Việt Anh
**Documentation task:** CAPONE-68
**Evidence baseline:** `origin/dev` at `5bb1f807ca13a5c66fd49e5518bf329f23bc0327`
**Last checked:** 2026-10-20

This document records the interface and retrieval boundary that is actually
available on the official `dev` branch. The Sprint 2 draft note
`docs/S2_KNOWLEDGE_RAG_LEARNING.md` is used as design context, but draft-only
routes and models are marked pending here until their implementation is merged
into `dev`.

## 1. Implemented interface on `dev`

The following UI and API contracts are present in the official branch:

| Area | Current implementation | Contract evidence |
| --- | --- | --- |
| Registration | Register form and validation | `POST /api/auth/register`, HTTP 201 |
| Sign in | Login form and authenticated state | `POST /api/auth/login`, HTTP 200; session is held by the HttpOnly cookie |
| Session | Session restore and account view | `GET /api/auth/session` |
| Logout | Loading, success, and error handling | `POST /api/auth/logout` |
| Knowledge upload | TXT, Markdown, and text-only PDF upload UI | `POST /api/knowledge/upload`, HTTP 201; response has `id`, `filename`, `file_size`, `mime_type`, `status`, and `created_at` |
| Conversation workspace | Presentation shell with question input, result slot, and Simple Ask callback point | CAPONE-43, PR #17, merge `5bb1f807` |

The workspace does not call a chat endpoint. The result area remains an
integration slot until the Simple Ask and answer contracts are merged.

## 2. Sprint 2 status boundary

| Task | Status on `dev` | Interface or retrieval consequence |
| --- | --- | --- |
| CAPONE-44 — Simple Ask Input | **PENDING** | PR #25 is open. The UI preserves a pending question, exposes loading state, and blocks duplicate submits. No `/api/chat` call is included because the route is not present on `dev`. |
| CAPONE-45 — Answer and citation display | **BLOCKED_CONTRACT** | The draft implementation requires `RunRecord`, `TaskResult`, answer status, evidence IDs, and citation fields. No matching response contract or `/api/chat` route is present on `dev`. |
| CAPONE-50 — Retrieval query and metadata filtering | **SHARED_CONTRACT_PENDING** | PR #5 is open and conflicting. `backend/app/retrieval/contracts.py` is not in `dev`; no owner-scoped retrieval client can be integrated yet. |
| CAPONE-51 — Evidence and citation mapping | **SHARED_CONTRACT_PENDING** | The draft mapping depends on the same retrieval, evidence, and citation contracts from CAPONE-50/PR #5. No independent integration is claimed. |

## 3. Retrieval design boundary

The intended Sprint 2 retrieval design keeps PostgreSQL as the canonical
source and applies owner and source filters before any derived retrieval
candidate is accepted. Evidence IDs and citation locators must be validated
against the canonical owner-scoped evidence set.

That design is **not yet an implementation on `dev`**. The official branch
currently has no `backend/app/retrieval` or `backend/app/execution` contract
tree. PR #5 contains the shared `Evidence`/`Provenance` and execution files,
but remains `OPEN` and `CONFLICTING`. CAPONE-50 and CAPONE-51 therefore remain
pending and must not define duplicate models or client-side owner parameters.

## 4. Integration rules

- Authenticated identity comes from the server-managed session cookie.
- The frontend must not invent `/api/chat`, source-list, retrieval, or citation
  response shapes before their backend contract is merged.
- Workspace presentation may expose callback and result slots without claiming
  that a Simple Ask run, answer, citation, or retrieval engine is available.
- Draft-only Research Workspace modules, Inspector retrieval behavior, Qdrant
  filtering, Evidence/Provenance models, and citation mapping are excluded
  from the implemented `dev` surface until their dependencies are merged.

## 5. Evidence references

- CAPONE-9 / PR #8: registration UI merged.
- CAPONE-14 / PR #9: sign-in UI merged.
- CAPONE-17 / PR #10: logout UI merged.
- CAPONE-21 / PR #13: account and session view merged.
- CAPONE-25 / PR #14: knowledge upload UI merged.
- CAPONE-43 / PR #17: conversation workspace shell merged.
- CAPONE-44 / PR #25: Simple Ask input pending review.
- CAPONE-35 / PR #5: shared execution/retrieval foundation open and
  conflicting.
- Sprint 2 draft commits: `7196e40`, `4680606`, `eef57c3`, `3e918cb`,
  `2a69031`, and `4055fe2`.
