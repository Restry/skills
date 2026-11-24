# Walkthrough Layout & Interaction Specification

This specification captures the visual grammar and interaction rules that make a product walkthrough scannable, trustworthy, and effortless to review on desktop screens.

---

## 1. Visual Design Language

- **Restrained light editorial canvas**: Pure white background (`#ffffff`), soft neutral accents (`#f8fafc`), hairline dividers (`#e2e8f0` / `#eef2f6`), deep slate ink (`#0f172a`), and one restrained brand primary (`#005aa9` or the host product's primary color).
- **Unboxed hierarchy**: Do not wrap every section or thumbnail caption in heavy drop-shadow cards. Use whitespace, hairlines, and typographic contrast.
- **Thin scrollbars**: `scrollbar-width: thin` with subtle translucent thumbs so the right outline and main pane scroll independently without heavy chrome.

## 2. Three-Zone Desktop Shell

```
┌──────────────────────────────────────────────────────────────────────┐
│ Minimal Masthead: Product Walkthrough Title · Subtitle · Counts      │
├────────────────────────────────────────────────────────┬─────────────┤
│ Sticky Top Tabs: [Ch 1] [Ch 2] [Ch 3] ...              │ Outline (N) │
├────────────────────────────────────────────────────────┼─────────────┤
│                                                        │  Outline    │
│  Main Content (independent scroll)                     │  (sticky,   │
│                                                        │   308px)    │
│  Operation Heading                                     │  ▾ Ch 1     │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐          │    · Op 1.1 │
│  │  16:9  │ │  16:9  │ │  16:9  │ │  16:9  │          │    · Op 1.2 │
│  └────────┘ └────────┘ └────────┘ └────────┘          │  ▸ Ch 2     │
│  ● Step 1   ● Step 2   ● Step 3   ● Step 4            │    ...      │
│                                                        │             │
└────────────────────────────────────────────────────────┴─────────────┘
```

### Zone A: Minimal Borderless Masthead
- Single compact horizontal band (`padding: 14px 32px 6px`).
- Contains only: **Walkthrough title** (`22px` bold), subtle product/release eyebrow, and concise counts (e.g., `9 chapters · 55 steps`).
- No giant hero banner, no marketing fluff, no redundant version dropdown inside the report page.

### Zone B: Sticky Top Navigation Bar
- `position: sticky; top: 0; z-index: 30; background: rgba(255,255,255,0.96); backdrop-filter: blur(8px);`
- **Horizontal chapter/category tabs**: Scrollable with left/right fade chevrons on overflow, subtle status dot per tab, `2px` bottom active indicator.
- **Outline toggle button** on the right (`Outline · N`), borderless ghost style with `aria-expanded`.

### Zone C: Collapsible Two-Level Right Outline
- Fixed width `308px`, `position: sticky; top: 45px; height: calc(100vh - 45px);` on wide desktop (`>= 1360px`), sliding drawer overlay below `1360px`.
- **Exactly two levels**:
  1. **Chapter** (collapsible row with status dot and step count)
  2. **Operation** (direct clickable anchor links with active highlight)
- Never insert intermediate subsection layers or raw test-ID codes (`SIT-XX-01`) into the customer outline.
- Keep the active link scrolled into view inside the outline container only—never trigger page-wide `scrollIntoView` jumps.

## 3. Main Content & 4-Column Thumbnail Grid

- **Chapter body**: Show chapter heading directly above operation headings and their screenshot grids.
- **Fixed 4-column desktop grid**: `grid-template-columns: repeat(4, minmax(0, 1fr))` with `gap: 24px 20px`.
  - Even when an operation has only 1 or 2 screenshots, each thumbnail stays in its 1-column slot (never stretch a single image to 100% width and distort visual rhythm).
  - Below `1100px`, gracefully step down to 2 columns.
- **Thumbnail frame**:
  - Clean `1px solid var(--line)` border, `6px` radius, `aspect-ratio: 16 / 9`, `object-fit: contain`.
  - Hover overlay: subtle step counter (`3/7`) in top-left and zoom hint in bottom-right; never obscure the UI permanently.
- **Compact caption**:
  - Single status dot (`pass` green, `action` neutral slate, `simulation` blue, `blocked` amber, `failed` red) with accessible `title` / `sr-only` label.
  - Numbered concise `h3` title (`1. Select template and recipient`).
  - Subtle role tag (`Sales`, `Admin`, `Customer`) aligned cleanly without crowding the title.

## 4. Lightbox Image Viewer

- Clicking any thumbnail opens a native `<dialog>` (or accessible modal) displaying the full `1920 × 1080` image cleanly fitted to the viewport.
- Controls: **Previous** (`←`), **Next** (`→`), **Close** (`Esc`), step index (`12 / 55`), role badge, status badge, and step title.
- Clicking the backdrop closes the viewer and restores focus to the triggering thumbnail button.

## 5. Screenshot Aspect-Ratio & Canvas Rule

- **Source uniformity**: Every capture in a walkthrough must share the same desktop viewport dimensions (e.g., all `1920 × 1080` or all `1443 × 965`). Mixing `1271 × 1092` (near-square) with `1440 × 900` (widescreen) produces visibly uneven letterboxing inside a 4-column grid.
- **Display normalization**: Export all display images as `1920 × 1080` PNGs. If source ratio differs from 16:9, center-fit proportionally on a neutral `#eef0f2` canvas:
  ```sh
  magick input.png -resize 1920x1080 -background '#eef0f2' -gravity center -extent 1920x1080 output.png
  ```
- Never stretch, crop, or upscale blurry low-resolution captures.

## 6. Copywriting Discipline

- Write in the target customer language consistently across static headings, tabs, buttons, empty states, and lightbox controls.
- Keep titles short, concrete, and action-oriented (`Filter customer 2059252 in Link Activity`, `Confirm Renew closure in Sales follow-up`).
- **Forbidden copy**: Defensive or meta-commentary such as *"This feature was unchanged"*, *"Retained for verification"*, *"Not a new business rerun"*, or internal ticket IDs.
