---
name: html-visualizer
description: Produce a self-contained HTML file when the answer carries spatial or relational structure — diffs with reviewer notes, module/architecture maps, side-by-side option comparisons, timelines, flowcharts, kanban boards, design-token catalogs, status reports, before/after writeups, or anything where layout itself is part of the meaning. Markdown flattens that structure into prose; HTML keeps it visible. Use this skill whenever the user asks for "a diagram", "module map", "PR review writeup", "comparison of approaches", "timeline", "flowchart", "dashboard", "explainer", "design exploration", "before/after", or any output where the user would benefit from seeing layout, color, and position carry meaning — even if they don't explicitly say "HTML". Err on the side of triggering when the topic is structural and would be hard to read as a wall of text.
---

# HTML Visualizer

## Why this skill exists

A lot of what we explain — diffs, call graphs, before/after, multi-option tradeoffs, timelines, deployment flows — is **spatial information**. Markdown flattens it into a single column of paragraphs and bullets, and the reader has to mentally reconstruct the structure. HTML can keep position, color, and grouping visible, so the reader sees the structure instead of decoding it.

When the task is "describe a relationship" or "compare options" or "show what changed and why", a single self-contained HTML file is almost always more effective than the equivalent markdown.

## When to reach for it

Trigger on any output where **layout itself is information**. Common shapes:

| Shape | Examples |
|---|---|
| Annotated diff / code review | PR reviewer notes in the margin, severity tags, jump links |
| Architecture / module map | Boxes-and-arrows showing dependencies, entry points, hot paths |
| Side-by-side comparison | "Approach A vs B vs C", before/after, option tradeoffs |
| Timeline | Implementation plan, incident timeline, release schedule |
| Flowchart | Deployment steps, decision tree, state machine |
| Catalog | Design tokens, component variants, SVG figure sheet |
| Structured writeup | PR description with motivation/diff/files-touched/risks |
| Dashboard / status | Weekly status, KPIs, traffic-light health view |
| Explainer | Concept walkthrough with diagram + glossary + FAQ |
| Slides / deck | Keyboard-navigable slides in one file |
| Board / grid | Kanban triage, matrix layouts |

If the user asks for "a doc", "a writeup", "a report", "an explanation" — check whether the answer has any of these shapes. If yes, default to HTML.

If the user explicitly wants markdown / plain text / a code block / a terminal-paste-friendly answer, follow that.

## Output contract

Produce **one self-contained HTML file**. The user should be able to open it in any modern browser with no build step, no server, no external assets.

- All CSS inline in a `<style>` tag in `<head>`. No CDN links, no `<link rel="stylesheet">` to external files.
- All JS inline in `<script>` tags if interactive. No external scripts.
- All images as inline SVG, or `data:` URLs, or omitted. No `<img src="https://...">`.
- Use system font stack so it renders the same everywhere: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif` for prose, `ui-monospace, "SF Mono", Menlo, Consolas, monospace` for code.
- Save it to a file path you tell the user about (e.g. `~/Downloads/<slug>.html` or wherever the conversation is rooted), then briefly say what you put in it. Don't paste the entire HTML back into the chat — that defeats the point.

If the task is small enough to fit in a quick markdown reply (one short paragraph, no comparison, no layout), do that instead — don't over-reach for HTML when prose is fine.

## Design rules

The point is clarity. Make the structure obvious at a glance; visual style is in service of that.

**Layout**

- Pick a layout that mirrors the shape of the content. Side-by-side comparison → CSS grid with equal columns. Timeline → vertical stack with a left rail. Module map → grid or absolutely-positioned SVG boxes with arrows. Don't reach for a sidebar+main layout if the content doesn't have a primary/secondary split.
- Generous whitespace. 16–24px gutters between cards, 8–16px internal padding. Cramped layouts hide structure.
- Constrain max-width on prose blocks (~70ch). Full-bleed only for diagrams and tables.

**Color**

- Use color to encode meaning, not decorate. Severity (red/amber/green), state (added/removed/changed in green/red/blue), grouping (one accent per cluster). If a color doesn't tell the reader something, drop it.
- Stick to a small palette. One neutral (slate/gray), one accent, plus semantic colors as needed.
- Make sure text on colored backgrounds passes contrast (WCAG AA ≈ 4.5:1 for body text).

**Typography**

- One body size (15–16px), one heading scale (clear hierarchy, not too many levels). Don't use more than 3 font sizes in the whole document unless you have a real reason.
- Code goes in monospace, with a subtle background tint, and `tab-size: 2`.

**Interactivity (use when it pays for itself)**

- Click-to-expand for long blocks (file contents in a PR, log excerpts in an incident).
- Hover for definitions / cross-references.
- Sliders/toggles only when the user genuinely benefits from tweaking — not for decoration.
- Keep all state in vanilla JS. No frameworks.

**Diagrams**

- Inline SVG, drawn by hand in the markup with explicit coordinates. Don't pull in mermaid/d3 — they need external scripts.
- Arrows: use a `<marker>` for arrowheads, draw `<path>` or `<line>` between box centers.
- Label everything. A box with no label is noise.

## Pattern playbook

Reference `references/patterns.md` for ~10 concrete patterns (annotated diff, module map, comparison grid, timeline, flowchart, etc.) — each with the HTML/CSS shape that has worked well. Read it when you're picking a pattern for a new task. You don't need to load it for every invocation; load it when the task doesn't obviously match a pattern you've already used.

## Workflow

1. **Recognize the shape.** Before writing HTML, name the pattern (annotated diff? comparison grid? timeline?). If you can't name it, the output probably wants prose, not a diagram.
2. **Pick a layout that fits the shape.** Look at `references/patterns.md` if you're not sure.
3. **Draft the content first as a rough outline** — what goes in each box/column/row. Don't start with CSS.
4. **Write the HTML in one pass.** Inline everything. Test the styling by reading it back — does the structure jump out?
5. **Save to a file** in a place the user can open. Tell them the path and one or two sentences about what you put inside. Don't dump the whole file to chat.

## What "good" looks like

- Open the file. Within 3 seconds, the reader sees the structure (columns? timeline? boxes-and-arrows?).
- Color usage is consistent — same hue means the same thing throughout.
- No external requests in the network tab.
- Resizing the window doesn't break the layout (use flex/grid, not fixed pixel widths for content areas).
- Reading the source: the HTML structure is roughly the same shape as the visual — semantic, not div-soup.

## What to avoid

- Calling out to Tailwind CDN or any external stylesheet. Inline the styles.
- Frameworks (React, Vue, Alpine). Vanilla HTML/CSS/JS only.
- Five colors with no meaning. Decoration without information.
- Dumping the entire HTML file into the chat reply. Save it; describe it.
- Defaulting to a markdown reply for tasks where the user clearly wanted a diagram or comparison. If layout matters, use this skill.
