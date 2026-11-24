---
name: product-walkthrough
description: "Builds and maintains customer-facing Product Walkthroughs and optional narrated presentations from verified application screenshots and frozen evidence manifests. Use when creating, updating, or auditing an end-to-end product walkthrough, chapter-based visual documentation, screenshot refresh, release-boundary cutoff, or voice narration with synced subtitles for any web application. Not for live page annotation/review feedback (use live-page-feedback), destructive production transactions, fabricating test results, or deploying application code."
---

# Product Walkthrough

Turn real, verified application screens into a clean, chapter-based **Product Walkthrough** (written visual report) and an optional **Narrated Presentation** driven by the exact same frozen manifest.

This skill distills a proven, project-agnostic architecture: **immutable evidence source → uniform viewport capture → clean two-level projection → optional audio/subtitle synthesis → real browser verification**.

> For interactive stakeholder comments and element/area annotations on running web pages, use the dedicated `live-page-feedback` skill instead—keep Walkthrough deliverables read-only and uncluttered.

---

## Core Architecture

Separate **evidence**, **projection**, and **delivery**:

1. **Frozen Evidence Manifest (Read-Only Source of Truth)**
   - Never mutate raw test runs or fabricate execution statuses when editing walkthrough copy, reordering display chapters, or locking unreleased stages.
   - Record every step's stable `id`, `role`, `status` (`pass` / `action` / `simulation` / `blocked` / `failed`), `capturedAt`, original `sourceSha256`, and `displaySha256` separately.
   - Rebuilding a walkthrough is a presentation update, **not** a new test pass.

2. **Two Deliverables, One Source**
   - **Written Walkthrough (`index.html`)**: Fast async review — minimal unboxed masthead, sticky top navigation tabs, collapsible two-level right outline (Chapters → Operations), 4-column thumbnail grid, and keyboard lightbox.
   - **Narrated Presentation (optional)**: Guided playback — shares the exact same ordered screenshots, driven by real audio duration (`audio.ended`), with synchronized subtitles.

3. **Reversible Release Boundary**
   - Control which chapters are exposed to customers in the projection layer (`releaseBoundary.maxChapter`), never by deleting source steps or relabeling locked stages as "unimplemented".

---

## When to Read References

Load only the reference needed for the active task:

- [Layout & Interaction Spec](./references/layout-spec.md): Visual tokens, masthead, sticky tabs, two-level outline, 4-column grid, lightbox, caption writing rules, and uniform aspect-ratio canvas rules.
- [Presentation & Narration](./references/presentation-and-narration.md): Optional audio-driven slide player, TTS audition/measurement/ASR alignment/numeric gates, and reversible release cutoffs.
- [Verification Checklist](./references/verification.md): Pre-publish automated checks, hash/dimension integrity, shared-browser acceptance, and honest reporting boundaries.

Starter assets ready to copy into any project live in `assets/`:

- [Manifest Schema](./assets/walkthrough.schema.json)
- [Example Manifest](./assets/example-manifest.json)
- [Zero-Dependency Viewer Template](./assets/walkthrough-template.html)
- [Zero-Dependency Static Builder](./assets/build-walkthrough.mjs)

---

## Non-Negotiable Guardrails

1. **Single Uniform Viewport Across the Entire Walkthrough**
   - Capture every business screen in desktop light theme at **one fixed CSS viewport** (recommended `1920 × 1080` 16:9, or one fixed ratio such as `1440 × 900` / `1443 × 965` consistently across 100% of captures).
   - Export all display images to a uniform **1920 × 1080** (16:9) canvas. If source captures use a non-16:9 desktop ratio, proportionally fit and center them on a neutral `#eef0f2` canvas without cropping UI edges.
   - **Hard gate**: Reject any batch that mixes square-ish and widescreen source captures.

2. **Full-Viewport Captures Only**
   - Capture the complete application viewport (`fullPage: false`, `animations: 'disabled'`). Never crop partial cards or hide broken surrounding layout.
   - Wait for all loading spinners, independent queries, and dialog entrance animations (`opacity: 1`) to finish before capturing.

3. **Honest Provenance & Clear Status Separation**
   - Clearly separate **real persisted writes**, **local simulations**, **read-only inspections**, **blocked**, and **failed** steps.
   - Never label a local mock, simulated email, or configuration check as verified external delivery.
   - Never use placeholder/empty screenshots or mix historical bug captures into a normal-flow customer sequence.

4. **Zero Meta-Commentary in Captions**
   - Each card shows only: **status indicator + concise step title** (location, action, visible result) + **role** (optional subtle metadata).
   - Strip defensive filler (*"unchanged functionality retained for verification"*, *"not a rerun"*, *"original capture"*), redundant intro blocks, and raw internal test-case codes from the customer-facing flow.

5. **Private Runtime vs. Public Output**
   - Keep credentials, raw browser snapshots, capture scripts, TTS intermediates, and feedback SQLite databases in a Git-ignored private directory (e.g., `.local-runtime/`).
   - Publish only sanitized static HTML, JSON metadata, and display images to the read-only walkthrough directory (e.g., `docs/walkthrough/` or `evidence/walkthrough/`).

---

## 5-Step Execution Workflow

### Step 1: Design the Story Outline
- Organize the product into **business workflow chapters** (typically 5–9 chapters in real user order), not internal database tables or code modules.
- Under each chapter, group into **2–4 concrete operations** (two-level outline: Chapter → Operation). Do not add a third subsection or test-code layer.
- Select the **fewest sufficient screenshots** per operation to show: context → user action → persisted result. Avoid repeating identical screens for multiple records.

### Step 2: Capture Clean, Uniform Screens
- Lock the browser viewport once before capturing (`1920 × 1080` or one agreed desktop size).
- For every screenshot, write a sidecar receipt JSON containing: `id`, `role`, `url`, `viewport: [w, h]`, `capturedAt`, and `sha256`.
- Inspect the rendered PNGs visually—DOM element counts alone never prove visual layout quality.

### Step 3: Freeze the Manifest
- Populate a declarative `walkthrough.json` conforming to [walkthrough.schema.json](./assets/walkthrough.schema.json).
- Point each step to its raw capture path and receipt. Keep the manifest versioned or immutable per release refresh.

### Step 4: Build Static Output
Run the zero-dependency builder from `assets/build-walkthrough.mjs`:

```sh
node <skill-dir>/assets/build-walkthrough.mjs \
  --manifest ./walkthrough.json \
  --out ./walkthrough-dist \
  --canvas 1920x1080
```

What the builder enforces automatically:
- Verifies every referenced raw PNG exists and shares the exact same source aspect ratio (fails fast on mixed square/wide captures).
- Fits images to `1920 × 1080` (using ImageMagick `magick` when available, or validates existing 1920×1080 files) and records separate `sourceSha256` and `displaySha256`.
- Applies any `releaseBoundary` lock cleanly via inert `<template>` storage rather than CSS-only hiding.
- Emits standalone `index.html`, `screenshots/*.png`, and `report-data/results.json`.

### Step 5: Verify in a Real Browser
- Open the generated `index.html` over the project's existing local server (do not spin up redundant ports if one already serves static files).
- Verify 100% of images decode with HTTP 200 and zero console errors.
- Test sticky chapter tabs, collapsible right outline, deep-link hashes, 4-column thumbnail grid alignment, lightbox open/next/prev/Escape, and any release-boundary locks.
- Follow [verification.md](./references/verification.md) before declaring completion.
