# REST API Contract, Review Lifecycle & Security Guardrails

Use this contract when mounting Live Page Feedback into FastAPI, Express, Next.js, Go, or the included zero-dependency Node reference server (`assets/feedback-server.mjs`).

---

## 1. Endpoints (Default Prefix: `/api/live-page-feedback`)

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `GET` | `/` | List all visible threads (`items[]`), available `screens[]`, `csrfToken`, current `author`, `build`, and `canMarkReady`. |
| `POST` | `/` | Create a new feedback thread (idempotent by client `id` UUID). |
| `PATCH` | `/:id` | Edit comment text or transition status (`open` / `ready` / `resolved`). Requires matching `version`. |
| `DELETE` | `/:id?version=N` | Delete thread (author only). Requires matching `version`. |
| `POST` | `/:id/comments` | Append a threaded reply (idempotent by reply `id` UUID). |
| `DELETE` | `/:id/comments/:commentId` | Delete a reply (reply author only). |

All responses MUST set `Cache-Control: no-store`.

---

## 2. Thread Payload Schema

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "page": "/orders",
  "box": { "x": 0.42, "y": 0.18, "width": 0.12, "height": 0.04 },
  "comment": "Status dropdown clips the default value at 1440px width.",
  "author": "Alice",
  "status": "open",
  "version": 1,
  "mine": true,
  "createdAt": "2026-11-24T09:00:00Z",
  "updatedAt": "2026-11-24T09:00:00Z",
  "context": {
    "mode": "element",
    "target": {
      "tag": "button",
      "label": "Status",
      "key": "order-status-filter",
      "scope": "Orders"
    },
    "filters": [{ "label": "Status", "value": "All statuses" }],
    "roles": ["reviewer"],
    "language": "en",
    "build": "/assets/index-abc123.js",
    "route": "?tab=active"
  },
  "review": {
    "note": "Widened FilterSelect trigger to min-w-60 with truncation.",
    "build": "/assets/index-def456.js",
    "readyAt": "2026-11-24T10:15:00Z"
  },
  "comments": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "author": "Bob",
      "comment": "Confirmed on 1440x900 desktop.",
      "mine": false,
      "createdAt": "2026-11-24T10:20:00Z"
    }
  ]
}
```

---

## 3. State Machine & Ownership Rules

```
  [open] ──(maintainer or author + served build)──▶ [ready] ──(author only)──▶ [resolved]
     ▲                                                 │                            │
     └──────────────────(author only: reopen)──────────┴────────────────────────────┘
```

- **Create (`POST /`)**:
  - Client generates `id` (UUID v4). Replaying the exact same `(id, payload)` returns the existing record cleanly; reusing an `id` with different content returns `409 Conflict`.
- **Edit / Transition (`PATCH /:id`)**:
  - Must pass current `version`. Stale `version` returns `409 Conflict` (*"This feedback changed. Refresh first."*).
  - Editing `comment`, closing (`resolved`), or reopening (`open`) is restricted to the thread **author** (`403` otherwise).
  - Marking `ready` is allowed for **maintainers (`canMarkReady`) or the author**, requires an open/ready thread (cannot jump from `resolved`), and records `{ note, build, readyAt }` automatically.
  - Closing (`resolved`) requires current status to be `ready` (`409` otherwise)—preventing accidental premature closure before a fix is marked ready.
- **Delete (`DELETE /:id?version=N`)**:
  - Author only, version-checked.

---

## 4. Security & Privacy Guardrails

1. **Environment Gate**: Never mount the overlay or API when `NODE_ENV=production` / `ENVIRONMENT=production`.
2. **Origin & CSRF Verification**:
   - Reject cross-site write requests (`Sec-Fetch-Site: cross-site` or unexpected `Origin`).
   - Require a per-session CSRF header (`X-Feedback-CSRF` or host app's CSRF token) on all `POST`/`PATCH`/`DELETE` calls.
3. **Permission Parity**: If the host app has role-based page access, filter `GET` and guard `POST`/`PATCH`/`DELETE` so a user can only read or annotate pages they are authorized to visit.
4. **No Secret Capture**: Explicitly skip `input[type="password"]`, `input[type="hidden"]`, and fields marked `data-feedback-private` when snapshotting filters or picking targets.
5. **Private Persistence**: Keep the SQLite / JSON store inside `.local-runtime/` (Git-ignored, `0600` file permissions). Never commit review databases into the repository.
6. **XSS Safety**: Never inject reviewer text or replies using `innerHTML`; build all DOM nodes with `textContent`.
