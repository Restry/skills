# Element Anchoring, SPA Navigation & Modal Layering

Live web pages scroll, resize, reflow, and open modals. These mechanics keep feedback pins accurate without coupling to any frontend framework.

---

## 1. Semantic Element Anchoring (Never Store CSS Classes)

Storing `div.flex.gap-3 > button:nth-child(2)` breaks on the next Tailwind refactor. Instead, capture a four-field semantic anchor:

```json
{
  "tag": "button",
  "label": "Export CSV",
  "key": "export-csv",
  "scope": "Link & follow-up activity"
}
```

### Resolution Order When Re-Locating a Saved Target
1. Gather visible business controls inside the active container (`activeDialog() || host`), excluding `input[type="password"]`, `input[type="hidden"]`, and any node inside the feedback chrome itself.
2. **Exact key match**: If `saved.key` (`data-feedback-target` or stable `id`) matches exactly 1 visible element (and its accessible name still matches if recorded), bind to it.
3. **Semantic match**: Otherwise filter by exact `(tag, label, scope)`. Only bind when there is a **unique** match (`matches.length === 1`).
4. **Honest fallback**:
   - If the element cannot be uniquely re-located (e.g., it was moved, renamed, or is on a different filter/tab), fall back to the recorded normalized box **only if** the current served frontend `build` matches the recorded `build`; otherwise render the thread in the drawer with an explicit notice: *"The original target has moved or was removed. Review the current page below."*

### Accessible Name Extraction Priority
1. `aria-label`
2. `aria-labelledby` referenced text
3. Associated `<label>` text (`element.labels[0]`)
4. `title` or `placeholder`
5. Trimmed `textContent` for `button`, `a`, `th`, `td`, `[role="button"]`, `[role="tab"]`

---

## 2. Three Annotation Modes

| Mode | Trigger | Stored Anchor |
| :--- | :--- | :--- |
| **`element`** | Hover highlights control (`elementsFromPoint`), single click selects it | `target` + normalized `box` |
| **`area`** | Pointer down + drag ≥ 10 px draws spotlight selection rectangle | `target: null` + normalized `box` |
| **`page`** | Click on non-interactive blank area or choose "Whole page" | `target: null` + click pin `box` |

### Normalized Box Coordinates
Store `box: { x, y, width, height }` in `[0..1]` relative to the scrollable main container's full content box (`width: host.clientWidth`, `height: host.scrollHeight`), clamping `width >= 0.002` and `height >= 0.002`.

---

## 3. Top-Layer Popover Compatibility With Open Modals

Native `<dialog>.showModal()` and Radix/ARIA focus-trapped modals block pointer events and focus on sibling elements appended to `document.body`.

**Verified Pattern**:
1. Observe DOM mutations for open dialogs: `dialog:modal, [role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"]` (ignoring the feedback widget's own surfaces).
2. When a business dialog opens:
   - Move the `#live-feedback-chrome` wrapper **inside** the topmost open business dialog (so Radix/focus-trap allows keyboard focus inside the feedback composer).
   - Set `popover="manual"` and call `feedbackChrome.showPopover()` so the browser paints it in the **Top Layer** above the dialog backdrop and `z-index` stacking contexts.
   - Give `#live-feedback-chrome:popover-open` `position: fixed; inset: 0; pointer-events: none; background: transparent;` and re-enable `pointer-events: auto` only on interactive buttons, markers, and open drawers.
3. When the business dialog closes, call `hidePopover()`, remove `popover`, and move `#live-feedback-chrome` back to `document.body`.

---

## 4. SPA Route Sync & Deep-Link Jumping

- Patch or listen to `popstate`, `hashchange`, and a throttled `MutationObserver` / `ResizeObserver` on the app root so route changes (`history.pushState` in React Router / Next / Vue Router) automatically re-attach markers and update the `This page (N)` counter.
- Strip the `feedback` query parameter when recording `context.route` so deep links don't recursively nest `?feedback=...`.
- Clicking **Jump** or opening `?feedback=<id>` navigates to `page + recordedRoute`, waits for the target route container to mount, scrolls the anchored element smoothly to center (`scrollIntoView({ block: 'center' })`), pulses the highlight, and opens the thread in the drawer.
