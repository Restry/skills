# Pattern Playbook

Concrete shapes that have worked. Pick the one that matches the content; adapt freely.

---

## 1. Annotated diff (code review)

Two-column layout: left = code with line numbers, right = margin notes pinned to line ranges.

```
+-------------------------------+----------------------+
| 12  function foo() {          | [bug] foo can throw  |
| 13    return bar();           |   when bar is null   |
| 14  }                         |                      |
+-------------------------------+----------------------+
```

- Severity tags as colored pills: `bug` (red), `nit` (gray), `praise` (green), `question` (amber).
- Anchor each note to its line range — `<a href="#L12">` jump links work fine.
- Diff lines: `background: rgba(46,160,67,.15)` for added, `rgba(248,81,73,.15)` for removed.

## 2. Module map

Inline SVG with rectangles for modules and arrows for dependencies.

- Group related modules into a translucent rounded `<rect>` background to show clusters.
- Highlight the entry point with a thicker stroke or accent color.
- Use `<marker id="arrow">` for arrowheads; draw paths between box-edge midpoints.
- Always label every box; truncate long names with title tooltips.

```html
<svg viewBox="0 0 800 500">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M0,0 L10,5 L0,10 Z" fill="#475569"/>
    </marker>
  </defs>
  <rect x="40" y="40" width="140" height="60" rx="8" fill="#f1f5f9" stroke="#0f172a"/>
  <text x="110" y="75" text-anchor="middle">api/router</text>
  <path d="M180,70 L320,70" stroke="#475569" fill="none" marker-end="url(#arrow)"/>
</svg>
```

## 3. Comparison grid (N approaches)

CSS grid, equal columns, one option per column.

- Header row: option name + one-line tagline.
- Body rows: dimensions to compare (e.g., "complexity", "perf", "rollback story"). Same row index = same dimension across columns.
- Use a fixed left rail for the dimension labels so eyes track across.
- Highlight the recommended column with a subtle background tint and a "Recommended" pill.

```css
.compare { display: grid; grid-template-columns: 160px repeat(3, 1fr); gap: 12px; }
```

## 4. Timeline (implementation plan, incident)

Vertical rail with timestamped events.

- Left: timestamp (or week/phase label).
- Middle: a colored dot on the rail; color = phase or severity.
- Right: card with title + 1–2 lines of detail. Click to expand for full detail.
- For incidents: include log excerpts in a `<details>` block under each event.

## 5. PR writeup

A long single-column doc, but with **structured sections** that look distinct:

- **Motivation** — short prose card with an accent border on the left.
- **Before / After** — two-column code blocks side by side.
- **Files touched** — a table: path | what changed | risk level (colored pill).
- **How to review** — a checklist with checkboxes.
- **Risks / followups** — bullet list with amber/red icons.

## 6. Flowchart

Inline SVG with decision diamonds and rectangles, similar to the module map but flowing top-to-bottom.

- Success path: solid arrow, neutral color.
- Failure / fallback paths: dashed arrow, red.
- Click a node to expand a side panel with the actual command / step detail (vanilla JS `onclick` toggling a `<aside>`).

## 7. Catalog (design tokens, component variants)

CSS grid of cells; each cell shows one specimen + its name + value.

- Color tokens: a 60×60 swatch + hex code + token name.
- Spacing tokens: a horizontal bar of the actual width + token name.
- Component variants: render the component in each cell with its props labeled below.
- Include a "click to copy" affordance for token values.

## 8. Dashboard / status

A few headline numbers at the top, sections below.

- Grid of KPI cards: big number, label, delta (with arrow).
- Color delta: green = better, red = worse, gray = flat.
- Sparkline as inline SVG inside each KPI card if relevant.
- Below: status rows with colored dots (green/amber/red).

## 9. Explainer

Reading-first layout with embedded visuals.

- **TL;DR** card at the top, accent background.
- Main content in prose with inline SVG figures interspersed.
- Glossary terms get `<abbr title="...">` or a hover popover for definitions.
- **FAQ** at the bottom in `<details>` accordions.

## 10. Slide deck (single file)

One `<section class="slide">` per slide, only one visible at a time.

- `body { overflow: hidden }` and absolute-positioned slides, or `display: none` + show only the active one.
- Listen for `keydown` Left/Right/Space to navigate.
- Show "n / total" counter in a corner.
- Print stylesheet (`@media print`) shows all slides stacked for PDF export.

## 11. Board / kanban

CSS grid of columns; cards as draggable list items.

- Columns: Now / Next / Later / Won't do (or whatever the task asks for).
- Drag with HTML5 drag-and-drop API; persist to `localStorage` if interactive.
- Cards have a colored left border for priority or owner.

---

## Cross-cutting tips

- **Print friendly:** add `@media print` rules so the file exports cleanly to PDF — typically `body { background: white } .card { break-inside: avoid }`.
- **结构化可视化的主题**：只有用户明确要求暗色/自适应主题，或工程桌面场景确需高对比时才使用 `prefers-color-scheme: dark`；它不是全局默认。
- **Anchors:** every section gets an `id` so the user can deep-link or jump from a TOC.
- **Tables:** for data tables, use `position: sticky; top: 0` on `<th>` so headers stay visible when scrolling.
