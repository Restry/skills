---
name: drawio
description: "Use when authoring, exporting or verifying draw.io diagrams."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [drawio, diagrams, architecture, workflow, swimlane, verification]
    related_skills: [architecture-diagram, c4-architecture-diagram, send-images-to-dad-compress-first]
---

# Draw.io Diagrams

## When to Use

Use whenever the user requests a `.drawio` diagram (architecture/evolution diagrams, business workflow swimlanes, Azure icon topologies, or screenshot-enriched evidence diagrams), or asks to export, render, or verify an existing `.drawio` file.

For official renderer protocols, local offline fallback, Azure icon traps, hyperlink XML, and roundtrip verification scripts, read `references/renderer-and-verification.md`.

## 1. Core Deliverable Rules

- Deliver a **real editable `.drawio` mxGraph XML file** plus a **compact image preview** (compress preview before sending in chat per `send-images-to-dad-compress-first`; keep full-resolution PNG/SVG locally). Never substitute a flattened SVG/PNG with a renamed `.drawio` extension.
- Generate UTF-8 XML with an XML library (`xml.etree.ElementTree`): `mxfile → diagram → mxGraphModel → root`, cells `0` and `1`, then editable vertex and edge cells. Escape labels via the XML library rather than raw string interpolation.
- **No emoji icons in nodes**: the user considers emoji cheap; use clean vector SVG icons (`<img src="data:image/svg+xml;base64,...">` inside HTML labels) or official Draw.io library icons (`img/lib/azure2/...svg`).
- Keep replies to one sentence summarizing what changed plus the editable file and preview—do not narrate the whole diagram in prose.

## 2. Layout, Swimlanes & Visual Discipline

- **One clear question per page**: at most two comparison bands for current-vs-target views; one swimlane per responsible role (including external customers, systems, and unassigned downstream operators) for end-to-end workflows or Agent interaction diagrams.
- **Native containers & relative geometry**: use native Draw.io `swimlane`/container cells and set child components' `parent` to the lane ID with relative coordinates so components stay attached when a lane moves. Keep cross-lane connectors under a common ancestor with explicit ports and waypoints.
- **Concise overview cards**: put only component name + 1–2 short hint lines in overview nodes, and action/protocol on edges. Move source evidence, capability inventories, detailed findings, and rollout checklists onto separate pages or companion docs instead of shrinking overview text.
- **Evolution & status semantics**: distinguish "current implementation" vs "target plan", and implemented links vs intended links with a legend. For workflow reviews, draw the full target flow and highlight missing/partial/unresolved nodes in yellow with a short reason; green means only the explicitly verified evidence level.
- **Reuse approved layouts**: once the user accepts a swimlane layout, preserve it during follow-up iterations.
- **Explicit routing gutters & waypoints**: reserve routing channels before placing nodes; increase lane spacing instead of letting return loops and downstream branches collide. Give assignment vs return loops separate ports/channels and route terminal paths outside intermediate nodes. Persist explicit waypoints and entry/exit ports in XML; check both box-to-segment intersections and shared collinear segments, then visually inspect dense regions at readable zoom.

## 3. Screenshot-Enriched & Online Read-Only Diagrams

- Run the real application against its actual database and embed real operation screenshots as full-resolution thumbnails inside native boxes without altering original nodes or connectors. Caption scope limits honestly (single-item vs bulk, existing vs newly submitted, simulated associations).
- **Card internal layout**: reserve a native editable full-width badge on top, a bounded wrapping editable text cell on the LEFT, and full-resolution image cells on the RIGHT (leave the parent value empty to avoid uncapped native label extents). For stacked screenshots, reserve a text/image gutter and expose a clickable rim on every layer. Cards without evidence give text the full body width.
- **Data URI syntax**: use `image=data:image/png,<base64>;` in `mxCell` style (omit `;base64` inside the style string because `;` splits style tokens; the native renderer restores `;base64` in SVG output).
- **Clickable online viewer**: wrap clickable image cells in `<object id="..." label="" link="https://..." linkTarget="_blank">` (never rely on a plain `mxCell` `link` attribute) and publish via `https://viewer.diagrams.net/?lightbox=1&nav=1&title=TITLE#U<encoded_url>`. Never inline screenshot-heavy `.drawio` files into the URL fragment.

## 4. Verification & Stop Conditions

- Prefer exporting previews from the **actual Draw.io renderer** (official `embed.diagrams.net` JSON protocol or local `jgraph/drawio` fallback). Custom self-drawn previews may assist checks but never prove native import/export integrity; if an approximate preview omits captions or native routing, label it explicitly.
- **Multi-page verification**: export and inspect **every page** separately (never trust multi-page batch export filenames blindly); verify unique page titles and no blank clipping or font fallback.
- **Roundtrip & hash integrity**: decode compressed XML (`base64 → raw deflate wbits=-15 → URL decode → XML parse`), normalize cell IDs across `mxCell` and wrapping `<object>` elements, and verify all original IDs, labels, parents, connector endpoints, and embedded PNG SHA-256 hashes survive after any layout rebuild.
- **Overflow & click proof**: inspect native text bounding boxes and enlarged dense-region crops (never fix overflow by clipping/hiding); for online viewers, click each exposed thumbnail rim in a real browser and verify the opened original image URL and bytes match the manifest.
