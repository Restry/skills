# Verification & Acceptance Checklist

Scale verification to the change. A documentation-only edit does not require re-capturing screenshots or re-synthesizing audio. Always run automated checks first, then verify the built artifact in a real browser.

---

## 1. Build & Integrity Checks

- [ ] **Manifest valid**: Every chapter has at least one operation (or is explicitly locked via `releaseBoundary`); every step has a unique `id`, valid `status`, and existing raw image path.
- [ ] **Uniform source aspect ratio**: All raw business captures share one consistent viewport/aspect ratio (no mixed square and widescreen shots).
- [ ] **Uniform display dimensions**: Every published business screenshot under `screenshots/` is `1920 × 1080` PNG.
- [ ] **Dual hashes recorded**: `report-data/results.json` stores `sourceSha256` (raw capture) and `displaySha256` (published 1920×1080 asset) separately, along with original `capturedAt` and `role`.
- [ ] **No stale counts**: Masthead counts, outline counters, and `results.json` summary counts all match the actual rendered DOM figures.
- [ ] **No private leakage**: No credentials, internal tokens, raw `.local-runtime` paths, or test-only debug dumps appear in published HTML/JSON.

---

## 2. Browser Acceptance (Desktop Light Theme)

Reload the rebuilt page cleanly over HTTP/HTTPS (hard reload—hash-only navigation can keep a cached DOM).

### Written Walkthrough
- [ ] **100% image decode**: Every `<img>` returns HTTP 200 and `naturalWidth === 1920 && naturalHeight === 1080`; zero console errors or 404s.
- [ ] **Navigation**: Clicking each sticky top tab switches cleanly; scrolling/chevron buttons work when tabs overflow; keyboard arrow keys work on the tablist.
- [ ] **Two-level right outline**: Expands/collapses chapters; clicking an operation scrolls to the exact heading without jumping the outline away; toggling the Outline button collapses/reopens cleanly.
- [ ] **4-column grid**: Operations with 1, 2, 3, and 4+ images all keep identical thumbnail widths and consistent aspect ratio—no stretched single images, no uneven square vs. rectangular frames.
- [ ] **Lightbox**: Clicking a thumbnail opens the modal; `←` / `→` navigate across steps; `Esc` and backdrop click close and restore focus to the thumbnail button.
- [ ] **Release boundary (if enabled)**: Locked tabs/chapters are visibly disabled; deep-linking to a locked hash does not reveal hidden content.

### Narrated Presentation (When Included)
- [ ] **Real playback**: Play a clip, observe synchronized subtitle progression, pause, seek within and across clips, change playback speed, and confirm automatic advance on `audio.ended`.
- [ ] **Keyboard isolation**: Pressing `Space` while focused on a `<summary>` or `<button>` activates that control without toggling global playback.
- [ ] **Clean separation**: Walkthrough deliverables remain read-only without injected comment forms (live page annotation belongs to `live-page-feedback`).

---

## 3. Honest Completion Reporting

Always separate what was verified from what remains outside scope:
- State exact counts verified (`N` chapters, `M` operations, `K` steps, `K/K` images decoded).
- Explicitly note if any step represents a **local simulation** or **read-only view** rather than an external third-party integration.
- Never claim a walkthrough refresh re-executed backend business tests or deployed code.
