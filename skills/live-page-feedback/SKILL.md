---
name: live-page-feedback
description: "Adds a self-contained Live Page Annotation & Review Feedback overlay to any running web application (dev or review environment) so stakeholders can pin comments directly onto live UI elements, areas, or open modals, track open → ready → resolved status, and deep-link reviewers back to exact routes. Use when implementing in-app review feedback, visual UI annotation overlays, element-anchored comment threads, or a dev/review feedback inbox. Not for production customer support widgets, static walkthrough generation (use product-walkthrough), or mutating business application data."
---

# Live Page Feedback

Attach a single, unified **real-time page annotation system** directly onto any running web application (React, Vue, Next.js, or plain HTML) in **development or review environments**.

Instead of maintaining a separate screenshot-commenting tool, reviewers annotate the live running UI directly—capturing semantic element anchors, active filters, route query/hash, and served frontend build so developers and agents can jump straight to the exact screen and verify fixes.

---

## Core Design Principles

1. **One Unified Live-Page Feedback System**
   - Review happens on the real running app, not on stale exported screenshots.
   - Reviewers click **Add feedback (`C`)** to hover-pick any live UI control or drag-select an area—even inside open modal dialogs—and post threaded feedback with zero page reload.

2. **Semantic Anchoring (Zero Brittle Selectors)**
   - Never persist minified CSS class names, Tailwind utility strings, or React fiber internals.
   - Anchor element annotations using semantic identity: `{ tag, label (accessible name), key (data-feedback-target or stable id), scope (nearest dialog/section/table heading) }`, plus a normalized `[0..1]` fallback box relative to the page container.
   - Automatically capture active page filters, route query/hash, language, and served frontend build version.

3. **Works Inside Open Modals & Drawers**
   - Detect open native `<dialog:modal>` and ARIA `[role="dialog"][data-state="open"]` containers.
   - Reparent the feedback chrome inside the active dialog's focus scope and promote it with `popover="manual"` + `showPopover()` so controls and highlights stay interactive **above modal backdrops**.

4. **3-State Verification Lifecycle (`open → ready → resolved`)**
   - **`open`**: Newly reported by reviewer (or reopened if a fix is insufficient).
   - **`ready`**: Maintainer (or author) marks the fix ready for verification, attaching a short review note, timestamp, and the exact served frontend `build` identifier.
   - **`resolved`**: Only the thread **author** closes the thread after verifying the fix on the live review build.
   - Enforce optimistic concurrency (`version`) and idempotent `POST` creation by client-generated UUID.

5. **Strict Dev / Review Isolation**
   - Mount **only** in local development or review environments; **never** enable in production builds or expose to unauthenticated public traffic.
   - Exclude `input[type="password"]` and `input[type="hidden"]` from element picking and filter snapshots.
   - Render all user-submitted comments and author names as plain text (`textContent`), never `innerHTML`.

---

## When to Read References

- [Element Anchoring & Modal Layering](./references/anchoring-and-modals.md): Semantic target resolution, `data-feedback-target` opt-in hooks, normalized box fallback, SPA navigation hooks, and top-layer Popover dialog support.
- [REST API Contract & Review Lifecycle](./references/api-and-lifecycle.md): Endpoints, payload schemas, `open → ready → resolved` state rules, optimistic locking, CSRF/origin checks, and private storage conventions.

Runnable zero-dependency starter assets live in `assets/`:

- [Semantic Target Helper](./assets/feedback-targets.js): Framework-agnostic element picker, locator, box normalizer, and filter snapshotter.
- [Drop-In Browser Overlay](./assets/feedback-overlay.js): Self-contained vanilla JS/CSS widget (`Add feedback (C)` + `Feedback (N)` drawer, hover highlight, drag-box, modal popover support, markers, replies, deep links, plain-text export).
- [Reference Dev/Review Server](./assets/feedback-server.mjs): Zero-dependency Node server & reusable request handler implementing the full REST contract and serving the overlay script.

---

## Quick Integration Workflow

### Step 1: Mount the Dev/Review Feedback Backend
- Gate mounting behind an explicit dev/review environment flag (never production).
- Store feedback privately in `.local-runtime/live-page-feedback.sqlite3` (or JSON store via `assets/feedback-server.mjs`), strictly Git-ignored.
- Expose the standard API prefix (default `/api/live-page-feedback`) and serve `feedback-overlay.js` at `/live-page-feedback.js` with `Cache-Control: no-cache`.

### Step 2: Inject the Overlay Script in Dev/Review HTML
Add a single script tag (configured via `data-*` attributes or `window.__LIVE_FEEDBACK_CONFIG__`):

```html
<script
  src="/live-page-feedback.js"
  data-endpoint="/api/live-page-feedback"
  data-container="main"
  defer
></script>
```

Optional semantic hooks on host app elements (improves anchor stability across copy changes):
- `data-feedback-target="export-csv"` on key controls
- `data-feedback-section="Invoice summary"` on major panels
- `data-feedback-filter="Status"` on custom filter widgets

### Step 3: Verify in a Real Browser
1. Confirm the bottom-right `Add feedback (C)` and `Feedback (0)` buttons appear only on authenticated app pages (hidden on `/login`).
2. Press `C`, hover a button or drag a box, submit a test note, reload the page, and verify the numbered marker stays pinned to the element.
3. Open a modal dialog in the app, click `Add feedback`, and verify the highlight and composer work above the dialog backdrop without focus traps.
4. Test `open → ready → resolved` state transitions, reply posting, `?feedback=<id>` deep-link navigation, and clean up the disposable test thread.
