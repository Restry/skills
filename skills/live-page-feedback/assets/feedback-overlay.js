/**
 * Self-contained Live Page Feedback overlay for dev & review environments.
 *
 * Drop-in usage:
 *   <script src="/live-page-feedback.js"
 *           data-endpoint="/api/live-page-feedback"
 *           data-container="main"
 *           defer></script>
 *
 * Features:
 * - Floating bottom-right Add feedback (C) + Feedback (N) controls
 * - Semantic element picking (hover highlight) + drag-to-box area + page pin
 * - Top-layer Popover compatibility above open native/ARIA modal dialogs
 * - Numbered page markers, threaded replies, open -> ready -> resolved lifecycle
 * - Deep-link ?feedback=<id> jump, search/filter drawer, and plain-text export
 * - XSS-safe DOM rendering (textContent only, zero innerHTML for user content)
 */
(() => {
  if (window.__livePageFeedbackMounted) return;
  window.__livePageFeedbackMounted = true;

  const currentScript = document.currentScript;
  const cfg = {
    endpoint:
      currentScript?.dataset.endpoint ||
      window.__LIVE_FEEDBACK_CONFIG__?.endpoint ||
      "/api/live-page-feedback",
    containerSelector:
      currentScript?.dataset.container ||
      window.__LIVE_FEEDBACK_CONFIG__?.containerSelector ||
      "main",
    csrfHeader:
      currentScript?.dataset.csrfHeader ||
      window.__LIVE_FEEDBACK_CONFIG__?.csrfHeader ||
      "X-Feedback-CSRF",
    excludePaths: (
      currentScript?.dataset.excludePaths ||
      window.__LIVE_FEEDBACK_CONFIG__?.excludePaths ||
      "/login"
    )
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  };

  // --- Inject Scoped Styles ---
  const style = document.createElement("style");
  style.textContent = `
:root {
  --lfb-ink: #0f172a;
  --lfb-body: #334155;
  --lfb-muted: #64748b;
  --lfb-line: #e2e8f0;
  --lfb-wash: #f8fafc;
  --lfb-surface: #ffffff;
  --lfb-blue: #005aa9;
  --lfb-blue-soft: #eff6ff;
  --lfb-green: #15803d;
  --lfb-green-soft: #f0fdf4;
  --lfb-danger: #b91c1c;
  --lfb-shadow: 0 0 0 1px rgba(15,23,42,.08), 0 16px 36px -10px rgba(15,23,42,.18);
}
#lfb-chrome { font: 13px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: var(--lfb-ink); }
#lfb-chrome * { box-sizing: border-box; }
#lfb-chrome:popover-open {
  position: fixed; inset: 0; width: auto; height: auto; margin: 0; padding: 0;
  border: 0; background: transparent; overflow: visible; pointer-events: none;
}
#lfb-chrome :is(.lfb-controls, .lfb-banner, .lfb-composer, .lfb-drawer) { pointer-events: auto; }
.lfb-controls {
  position: fixed; right: 16px; bottom: 16px; z-index: 900;
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px; border-radius: 10px; background: var(--lfb-surface); box-shadow: var(--lfb-shadow);
}
.lfb-controls[hidden] { display: none; }
.lfb-btn {
  display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 11px;
  border: 1px solid transparent; border-radius: 7px; background: transparent;
  color: var(--lfb-body); font: 500 12.5px/1 inherit; cursor: pointer; white-space: nowrap;
}
.lfb-btn:hover:not(:disabled) { background: var(--lfb-wash); color: var(--lfb-ink); }
.lfb-btn:disabled { opacity: .45; cursor: not-allowed; }
.lfb-btn-primary { background: var(--lfb-blue); color: #fff; }
.lfb-btn-primary:hover:not(:disabled) { background: #044a8a; color: #fff; }
.lfb-btn-outline { border-color: var(--lfb-line); background: var(--lfb-surface); color: var(--lfb-ink); }
.lfb-btn-danger { color: var(--lfb-danger); }
.lfb-kbd {
  font: 600 10.5px/1 ui-monospace, SFMono-Regular, monospace;
  padding: 2px 5px; border-radius: 4px; background: var(--lfb-wash); border: 1px solid var(--lfb-line); color: var(--lfb-muted);
}
.lfb-count {
  min-width: 18px; height: 18px; padding: 0 5px; border-radius: 999px;
  background: var(--lfb-blue-soft); color: var(--lfb-blue); font: 600 11px/18px inherit; text-align: center;
}
.lfb-banner {
  position: fixed; right: 16px; bottom: 64px; z-index: 905;
  display: flex; align-items: center; gap: 10px; padding: 8px 12px;
  border-radius: 9px; background: var(--lfb-ink); color: #fff; font-size: 12.5px; box-shadow: var(--lfb-shadow);
}
.lfb-banner[hidden] { display: none; }
.lfb-capture {
  position: fixed; inset: 0; z-index: 895; cursor: crosshair; touch-action: none; pointer-events: auto;
}
.lfb-capture[hidden] { display: none; }
.lfb-highlight, .lfb-dragbox {
  position: fixed; pointer-events: none; z-index: 898; border-radius: 4px;
  outline: 2px solid #2563eb; outline-offset: 1px; background: rgba(37, 99, 235, 0.10);
}
.lfb-highlight[hidden], .lfb-dragbox[hidden] { display: none; }
.lfb-layer {
  position: absolute; left: 0; top: 0; width: 100%; pointer-events: none; z-index: 25;
}
.lfb-marker {
  position: absolute; pointer-events: auto; transform: translate(-50%, -50%);
  width: 24px; height: 24px; border-radius: 999px; border: 2px solid #fff;
  background: var(--lfb-blue); color: #fff; font: 700 11px/20px inherit;
  text-align: center; cursor: pointer; box-shadow: 0 2px 8px rgba(15,23,42,.28);
  padding: 0;
}
.lfb-marker[data-status="ready"] { background: #1d4ed8; }
.lfb-marker[data-status="resolved"] { background: var(--lfb-green); opacity: .7; }
.lfb-marker[data-selected="true"] { transform: translate(-50%, -50%) scale(1.18); box-shadow: 0 0 0 3px rgba(37,99,235,.35); }
.lfb-box-outline {
  position: absolute; pointer-events: none; border: 2px solid rgba(0, 90, 169, 0.65);
  background: rgba(0, 90, 169, 0.06); border-radius: 4px;
}
.lfb-composer {
  position: fixed; z-index: 910; width: min(360px, calc(100vw - 24px));
  padding: 14px; border-radius: 12px; background: var(--lfb-surface); box-shadow: var(--lfb-shadow);
  display: flex; flex-direction: column; gap: 10px;
}
.lfb-composer[hidden] { display: none; }
.lfb-composer textarea, .lfb-composer input, .lfb-drawer textarea, .lfb-drawer input {
  width: 100%; padding: 8px 10px; border: 1px solid var(--lfb-line); border-radius: 7px;
  font: inherit; color: var(--lfb-ink); background: var(--lfb-surface);
}
.lfb-composer textarea { min-height: 76px; resize: vertical; }
.lfb-drawer {
  position: fixed; top: 12px; right: 12px; bottom: 64px; z-index: 908;
  width: min(420px, calc(100vw - 24px)); border-radius: 12px;
  background: var(--lfb-surface); box-shadow: var(--lfb-shadow);
  display: flex; flex-direction: column; overflow: hidden;
}
.lfb-drawer[hidden] { display: none; }
.lfb-drawer-head {
  padding: 12px 14px; border-bottom: 1px solid var(--lfb-line);
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
}
.lfb-drawer-filters {
  padding: 10px 14px; border-bottom: 1px solid var(--lfb-line);
  display: flex; flex-direction: column; gap: 8px; background: var(--lfb-wash);
}
.lfb-filter-row { display: flex; align-items: center; justify-content: space-between; gap: 6px; flex-wrap: wrap; }
.lfb-drawer-list { flex: 1; overflow-y: auto; padding: 12px 14px; display: flex; flex-direction: column; gap: 10px; }
.lfb-thread {
  border: 1px solid var(--lfb-line); border-radius: 9px; padding: 11px 12px;
  background: var(--lfb-surface); display: flex; flex-direction: column; gap: 8px;
}
.lfb-thread[data-selected="true"] { border-color: var(--lfb-blue); box-shadow: 0 0 0 2px rgba(0,90,169,.12); }
.lfb-thread-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.lfb-pill {
  display: inline-flex; align-items: center; padding: 2px 7px; border-radius: 999px;
  font-size: 11px; font-weight: 600; background: var(--lfb-wash); color: var(--lfb-body); border: 1px solid var(--lfb-line);
}
.lfb-pill[data-status="ready"] { background: var(--lfb-blue-soft); color: var(--lfb-blue); border-color: #bfdbfe; }
.lfb-pill[data-status="resolved"] { background: var(--lfb-green-soft); color: var(--lfb-green); border-color: #bbf7d0; }
.lfb-comment { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--lfb-ink); }
.lfb-meta { font-size: 11.5px; color: var(--lfb-muted); display: flex; flex-wrap: wrap; gap: 6px 10px; }
.lfb-ctx {
  padding: 7px 9px; border-radius: 6px; background: var(--lfb-wash); font-size: 11.5px; color: var(--lfb-body);
  display: flex; flex-wrap: wrap; gap: 4px 10px;
}
.lfb-replies {
  border-top: 1px solid var(--lfb-line); padding-top: 8px; display: flex; flex-direction: column; gap: 6px;
}
.lfb-reply { padding: 6px 8px; border-radius: 6px; background: var(--lfb-wash); font-size: 12px; }
.lfb-err { color: var(--lfb-danger); font-size: 12px; }
`;
  document.head.append(style);

  // --- DOM Helpers ---
  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "className") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2).toLowerCase(), v);
      else node.setAttribute(k, v === true ? "" : String(v));
    }
    for (const child of children) {
      if (child !== null && child !== undefined && child !== false) node.append(child);
    }
    return node;
  }

  // --- Inline fallback target helper if feedback-targets.js wasn't loaded separately ---
  function makeTargets(opts) {
    if (typeof window.createLiveFeedbackTargets === "function") {
      return window.createLiveFeedbackTargets(opts);
    }
    const sel =
      '[data-feedback-target], button, a[href], input, select, textarea, th, td, [role="button"], [role="combobox"], [role="tab"], [role="checkbox"]';
    const excl = 'input[type="password"], input[type="hidden"], [data-feedback-private]';
    const compact = (v, m = 160) => String(v ?? "").replace(/\s+/g, " ").trim().slice(0, m);
    const accName = (n) =>
      compact(
        n.getAttribute("aria-label") ||
          n.labels?.[0]?.textContent ||
          n.getAttribute("title") ||
          n.getAttribute("placeholder") ||
          (n.matches('button, a, th, td, [role="button"], [role="tab"]') ? n.textContent : "")
      );
    const anchor = (n) => {
      const area = n.closest('dialog, [role="dialog"], [data-feedback-section], table, section');
      const scope = area && (area.dataset.feedbackSection || area.getAttribute("aria-label") || area.querySelector("h1,h2,h3")?.textContent);
      return {
        tag: n.localName,
        label: accName(n),
        key: compact(n.dataset.feedbackTarget || (/^[A-Za-z][\w.-]*$/.test(n.id) ? n.id : ""), 120) || null,
        scope: compact(scope) || null,
      };
    };
    const isCtrl = (n) => {
      const root = opts.getActiveDialog() || opts.getHost();
      return !!root && root.contains(n) && !opts.layer.contains(n) && !opts.chrome.contains(n) && !n.matches(excl);
    };
    const boxForRect = (rect) => {
      const b = opts.layer.getBoundingClientRect();
      if (!b.width || !b.height) return null;
      const cl = (v) => Math.max(0, Math.min(1, v));
      const x = cl((rect.left - b.left) / b.width);
      const y = cl((rect.top - b.top) / b.height);
      const width = cl((rect.right - b.left) / b.width) - x;
      const height = cl((rect.bottom - b.top) / b.height) - y;
      return width >= 0.002 && height >= 0.002 ? { x, y, width, height } : null;
    };
    const cleanRoute = () => {
      const p = new URLSearchParams(location.search);
      p.delete("feedback");
      const q = p.toString();
      return (q ? `?${q}` : "") + (location.hash || "");
    };
    return {
      pick: (x, y) => {
        for (const n of document.elementsFromPoint(x, y)) {
          if (opts.layer.contains(n) || opts.chrome.contains(n)) continue;
          const c = n.closest(sel);
          if (c && isCtrl(c)) return c;
        }
        return null;
      },
      locate: (saved) => {
        if (!saved || (!saved.key && !saved.label)) return null;
        const root = opts.getActiveDialog() || opts.getHost();
        if (!root) return null;
        const all = [...root.querySelectorAll(sel)].filter((n) => isCtrl(n) && n.getClientRects().length);
        const keyed = saved.key ? all.filter((n) => anchor(n).key === saved.key) : [];
        if (keyed.length === 1 && (!saved.label || accName(keyed[0]) === saved.label)) return keyed[0];
        const sem = (keyed.length ? keyed : all).filter((n) => {
          const f = anchor(n);
          return f.tag === saved.tag && f.label === saved.label && f.scope === saved.scope;
        });
        return sem.length === 1 ? sem[0] : null;
      },
      box: (n) => boxForRect(n.getBoundingClientRect()),
      boxForRect,
      build: () => document.querySelector('script[type="module"][src]')?.getAttribute("src") || null,
      cleanRoute,
      snapshot: (mode, n) => ({
        mode,
        target: n ? anchor(n) : null,
        filters: [],
        language: document.documentElement.lang || "en",
        build: document.querySelector('script[type="module"][src]')?.getAttribute("src") || null,
        route: cleanRoute(),
      }),
    };
  }

  // --- State ---
  let host = null;
  let currentPath = "";
  let csrfToken = "";
  let defaultAuthor = "Reviewer";
  let canMarkReady = false;
  let items = [];
  let markingMode = false;
  let selectedId = null;
  let scopeFilter = "page"; // "page" | "all"
  let showClosed = false;
  let searchTerm = "";
  let draftMark = null;
  let businessDialog = null;
  let dragStart = null;
  let hoveredEl = null;

  // --- Chrome Elements ---
  const layer = el("div", { className: "lfb-layer", "aria-label": "Live page feedback markers" });
  const chrome = el("div", { id: "lfb-chrome" });
  const capture = el("div", { className: "lfb-capture", hidden: true, "aria-hidden": "true" });
  const highlight = el("div", { className: "lfb-highlight", hidden: true, "aria-hidden": "true" });
  const dragBox = el("div", { className: "lfb-dragbox", hidden: true, "aria-hidden": "true" });

  const addBtn = el(
    "button",
    { type: "button", className: "lfb-btn", onClick: () => setMarking(!markingMode) },
    el("span", { text: "Add feedback" }),
    el("span", { className: "lfb-kbd", text: "C" })
  );
  const countBadge = el("span", { className: "lfb-count", text: "0" });
  const openDrawerBtn = el(
    "button",
    { type: "button", className: "lfb-btn", onClick: () => toggleDrawer() },
    el("span", { text: "Feedback" }),
    countBadge
  );
  const controls = el("div", { className: "lfb-controls", hidden: true }, addBtn, openDrawerBtn);

  const banner = el(
    "div",
    { className: "lfb-banner", hidden: true },
    el("span", { text: "Click any UI element or drag an area to annotate · Esc to cancel" }),
    el("button", { type: "button", className: "lfb-btn lfb-btn-outline", text: "Cancel", onClick: () => setMarking(false) })
  );

  // Composer
  const composerTarget = el("div", { className: "lfb-meta" });
  const composerText = el("textarea", { placeholder: "Describe the issue or suggestion…" });
  const composerAuthor = el("input", { type: "text", placeholder: "Your name", maxLength: 80 });
  const composerErr = el("div", { className: "lfb-err", hidden: true });
  const composerSubmit = el("button", { type: "button", className: "lfb-btn lfb-btn-primary", text: "Post feedback", onClick: () => void submitDraft() });
  const composer = el(
    "div",
    { className: "lfb-composer", role: "dialog", "aria-label": "New page feedback", hidden: true },
    el("strong", { text: "Add feedback" }),
    composerTarget,
    composerText,
    composerAuthor,
    composerErr,
    el(
      "div",
      { style: "display:flex;justify-content:flex-end;gap:8px" },
      el("button", { type: "button", className: "lfb-btn lfb-btn-outline", text: "Cancel", onClick: () => closeComposer() }),
      composerSubmit
    )
  );

  // Drawer
  const drawerStatus = el("div", { className: "lfb-meta" });
  const searchInput = el("input", {
    type: "search",
    placeholder: "Search feedback…",
    onInput: () => {
      searchTerm = searchInput.value.trim().toLowerCase();
      renderDrawer();
    },
  });
  const tabPageBtn = el("button", {
    type: "button",
    className: "lfb-btn lfb-btn-outline",
    text: "This page",
    onClick: () => { scopeFilter = "page"; renderDrawer(); },
  });
  const tabAllBtn = el("button", {
    type: "button",
    className: "lfb-btn",
    text: "All pages",
    onClick: () => { scopeFilter = "all"; renderDrawer(); },
  });
  const closedCheckbox = el("input", {
    type: "checkbox",
    style: "width:auto",
    onChange: () => { showClosed = closedCheckbox.checked; renderDrawer(); renderMarkers(); },
  });
  const drawerList = el("div", { className: "lfb-drawer-list" });
  const drawer = el(
    "aside",
    { className: "lfb-drawer", "aria-label": "Feedback list", hidden: true },
    el(
      "div",
      { className: "lfb-drawer-head" },
      el("strong", { text: "Page feedback" }),
      el(
        "div",
        { style: "display:flex;gap:6px" },
        el("button", { type: "button", className: "lfb-btn", text: "Export", onClick: () => exportText() }),
        el("button", { type: "button", className: "lfb-btn", text: "Reload", onClick: () => void fetchItems() }),
        el("button", { type: "button", className: "lfb-btn", text: "Close", onClick: () => { drawer.hidden = true; } })
      )
    ),
    el(
      "div",
      { className: "lfb-drawer-filters" },
      searchInput,
      el(
        "div",
        { className: "lfb-filter-row" },
        el("div", { style: "display:flex;gap:4px" }, tabPageBtn, tabAllBtn),
        el("label", { style: "display:inline-flex;align-items:center;gap:5px;font-size:12px;color:var(--lfb-muted);cursor:pointer" }, closedCheckbox, el("span", { text: "Show closed" }))
      ),
      drawerStatus
    ),
    drawerList
  );

  chrome.append(capture, highlight, dragBox, controls, banner, composer, drawer);
  document.body.append(chrome);

  const targets = makeTargets({
    getHost: () => host,
    layer,
    getActiveDialog: () => businessDialog,
    chrome,
  });

  // --- Modal Top-Layer Support ---
  function syncDialogLayer() {
    if (typeof chrome.showPopover !== "function") return;
    const dialogs = document.querySelectorAll('dialog:modal, [role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"]');
    const next = host && [...dialogs].reverse().find((d) => !chrome.contains(d) && d.getClientRects().length) || null;
    if (next === businessDialog && chrome.isConnected) return;
    businessDialog = next;
    if (chrome.matches(":popover-open")) chrome.hidePopover();
    if (next) {
      next.append(chrome);
      chrome.setAttribute("popover", "manual");
      chrome.showPopover();
    } else {
      chrome.removeAttribute("popover");
      document.body.append(chrome);
    }
    capture.hidden = !markingMode;
  }

  function syncGeometry() {
    if (!host) return;
    if (getComputedStyle(host).position === "static") host.style.position = "relative";
    if (!host.contains(layer)) host.append(layer);
    layer.style.height = "0px";
    layer.style.height = host.scrollHeight + "px";
  }

  // --- API ---
  async function apiFetch(path, init = {}) {
    const headers = { ...(init.headers || {}) };
    if (init.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
    if (init.method && init.method !== "GET" && csrfToken) headers[cfg.csrfHeader] = csrfToken;
    const res = await fetch(cfg.endpoint + path, { credentials: "same-origin", cache: "no-store", ...init, headers });
    if (!res.ok) {
      let msg = `Request failed (${res.status})`;
      try { const j = await res.json(); if (j.detail || j.error) msg = j.detail || j.error; } catch {}
      throw new Error(msg);
    }
    return res.status === 204 ? null : res.json();
  }

  async function fetchItems() {
    try {
      const data = await apiFetch("");
      items = Array.isArray(data.items) ? data.items : [];
      csrfToken = data.csrfToken || csrfToken;
      defaultAuthor = data.author || defaultAuthor;
      canMarkReady = data.canMarkReady === true;
      if (!composerAuthor.value) composerAuthor.value = localStorage.getItem("lfb:author") || defaultAuthor;
      updateCounts();
      renderMarkers();
      renderDrawer();
      openDeepLinkIfNeeded();
    } catch {
      controls.hidden = true;
    }
  }

  // --- Filtering & Rendering ---
  function visibleForPage() {
    return items.filter((it) => it.page === currentPath && (showClosed || it.status !== "resolved"));
  }

  function updateCounts() {
    const openOnPage = items.filter((it) => it.page === currentPath && it.status !== "resolved").length;
    countBadge.textContent = String(openOnPage);
    tabPageBtn.textContent = `This page (${items.filter((it) => it.page === currentPath).length})`;
    tabAllBtn.textContent = `All pages (${items.length})`;
  }

  function resolveBox(item) {
    if (item.context?.mode === "element") {
      const node = targets.locate(item.context.target);
      return node ? targets.box(node) : null;
    }
    if (item.context?.build && targets.build() && item.context.build !== targets.build()) return null;
    return item.box || null;
  }

  function renderMarkers() {
    layer.replaceChildren();
    if (!host) return;
    syncGeometry();
    const list = visibleForPage();
    list.forEach((item, idx) => {
      const box = resolveBox(item);
      if (!box) return;
      if (box.width > 0.015 && box.height > 0.015) {
        layer.append(
          el("div", {
            className: "lfb-box-outline",
            style: `left:${box.x * 100}%;top:${box.y * 100}%;width:${box.width * 100}%;height:${box.height * 100}%`,
          })
        );
      }
      const pin = el("button", {
        type: "button",
        className: "lfb-marker",
        text: String(idx + 1),
        "data-status": item.status,
        "data-selected": item.id === selectedId ? "true" : "false",
        "aria-label": `Feedback #${idx + 1}: ${item.comment.slice(0, 60)}`,
        style: `left:${(box.x + box.width) * 100}%;top:${box.y * 100}%`,
        onClick: (e) => {
          e.stopPropagation();
          selectedId = item.id;
          drawer.hidden = false;
          renderMarkers();
          renderDrawer();
        },
      });
      layer.append(pin);
    });
  }

  function renderDrawer() {
    drawerList.replaceChildren();
    tabPageBtn.className = scopeFilter === "page" ? "lfb-btn lfb-btn-outline" : "lfb-btn";
    tabAllBtn.className = scopeFilter === "all" ? "lfb-btn lfb-btn-outline" : "lfb-btn";

    const filtered = items.filter((it) => {
      if (scopeFilter === "page" && it.page !== currentPath) return false;
      if (!showClosed && it.status === "resolved") return false;
      if (searchTerm) {
        const hay = `${it.comment} ${it.author} ${it.page} ${it.context?.target?.label || ""}`.toLowerCase();
        if (!hay.includes(searchTerm)) return false;
      }
      return true;
    });

    if (filtered.length === 0) {
      drawerList.append(el("div", { className: "lfb-meta", text: "No feedback matches this view." }));
      return;
    }

    for (const item of filtered) {
      const card = el("article", {
        className: "lfb-thread",
        "data-selected": item.id === selectedId ? "true" : "false",
      });

      const actions = el("div", { style: "display:flex;gap:4px;flex-wrap:wrap" });
      actions.append(
        el("button", { type: "button", className: "lfb-btn", text: "Jump", onClick: () => jumpTo(item) })
      );
      if ((canMarkReady || item.mine) && item.status === "open") {
        actions.append(
          el("button", {
            type: "button",
            className: "lfb-btn lfb-btn-outline",
            text: "Mark ready",
            onClick: () => void transition(item, "ready"),
          })
        );
      }
      if (item.mine && item.status === "ready") {
        actions.append(
          el("button", {
            type: "button",
            className: "lfb-btn lfb-btn-primary",
            text: "Resolve",
            onClick: () => void transition(item, "resolved"),
          })
        );
      }
      if (item.mine && item.status !== "open") {
        actions.append(
          el("button", {
            type: "button",
            className: "lfb-btn",
            text: "Reopen",
            onClick: () => void transition(item, "open"),
          })
        );
      }
      if (item.mine) {
        actions.append(
          el("button", {
            type: "button",
            className: "lfb-btn lfb-btn-danger",
            text: "Delete",
            onClick: () => void deleteThread(item),
          })
        );
      }

      card.append(
        el(
          "div",
          { className: "lfb-thread-top" },
          el("span", { className: "lfb-pill", "data-status": item.status, text: item.status }),
          el("span", { className: "lfb-meta", text: `${item.page} · ${item.author}` })
        ),
        el("div", { className: "lfb-comment", text: item.comment })
      );

      if (item.context?.target?.label || item.review?.note) {
        const ctx = el("div", { className: "lfb-ctx" });
        if (item.context?.target?.label) {
          ctx.append(el("span", { text: `Target: ${item.context.target.tag} "${item.context.target.label}"` }));
        }
        if (item.review?.note) {
          ctx.append(el("span", { text: `Ready note: ${item.review.note}` }));
        }
        card.append(ctx);
      }

      card.append(actions);

      const repliesBox = el("div", { className: "lfb-replies" });
      for (const r of item.comments || []) {
        repliesBox.append(
          el("div", { className: "lfb-reply" }, el("strong", { text: `${r.author}: ` }), el("span", { text: r.comment }))
        );
      }
      const replyInput = el("input", { type: "text", placeholder: "Add a reply…" });
      const replyForm = el(
        "form",
        {
          style: "display:flex;gap:6px",
          onSubmit: async (e) => {
            e.preventDefault();
            const text = replyInput.value.trim();
            if (!text) return;
            replyInput.disabled = true;
            try {
              const updated = await apiFetch(`/${encodeURIComponent(item.id)}/comments`, {
                method: "POST",
                body: JSON.stringify({ id: crypto.randomUUID(), comment: text, author: composerAuthor.value.trim() || defaultAuthor }),
              });
              items = items.map((x) => (x.id === item.id ? updated : x));
              renderDrawer();
            } finally {
              replyInput.disabled = false;
            }
          },
        },
        replyInput,
        el("button", { type: "submit", className: "lfb-btn lfb-btn-outline", text: "Reply" })
      );
      repliesBox.append(replyForm);
      card.append(repliesBox);
      drawerList.append(card);
    }
  }

  async function transition(item, status) {
    const body = { version: item.version, status };
    if (status === "ready") {
      const note = window.prompt("Optional note describing the fix for verification:", "") ?? "";
      body.note = note.trim();
    }
    try {
      const updated = await apiFetch(`/${encodeURIComponent(item.id)}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      items = items.map((x) => (x.id === item.id ? updated : x));
      updateCounts();
      renderMarkers();
      renderDrawer();
    } catch (err) {
      drawerStatus.textContent = err.message;
    }
  }

  async function deleteThread(item) {
    try {
      await apiFetch(`/${encodeURIComponent(item.id)}?version=${item.version}`, { method: "DELETE" });
      items = items.filter((x) => x.id !== item.id);
      if (selectedId === item.id) selectedId = null;
      updateCounts();
      renderMarkers();
      renderDrawer();
    } catch (err) {
      drawerStatus.textContent = err.message;
    }
  }

  function jumpTo(item) {
    selectedId = item.id;
    if (item.page !== currentPath) {
      const route = item.context?.route || "";
      const sep = route.includes("?") ? "&" : "?";
      history.pushState({}, "", `${item.page}${route}${sep}feedback=${encodeURIComponent(item.id)}`);
      window.dispatchEvent(new PopStateEvent("popstate"));
      return;
    }
    const targetEl = item.context?.mode === "element" ? targets.locate(item.context.target) : null;
    if (targetEl) {
      targetEl.scrollIntoView({ behavior: "smooth", block: "center" });
      drawerStatus.textContent = "";
    } else if (!resolveBox(item)) {
      drawerStatus.textContent = "The original target has moved or was removed. Review the current page below.";
    }
    renderMarkers();
    renderDrawer();
  }

  let handledDeepLink = "";
  function openDeepLinkIfNeeded() {
    const id = new URLSearchParams(location.search).get("feedback");
    if (!id || id === handledDeepLink) return;
    const found = items.find((it) => it.id === id);
    if (!found) return;
    handledDeepLink = id;
    drawer.hidden = false;
    jumpTo(found);
  }

  function exportText() {
    const lines = items.map(
      (it, i) =>
        `#${i + 1} [${it.status.toUpperCase()}] ${it.page} (${it.author})\n  ${it.comment}${
          it.context?.target?.label ? `\n  Target: ${it.context.target.tag} "${it.context.target.label}"` : ""
        }`
    );
    const blob = new Blob([lines.join("\n\n") + "\n"], { type: "text/plain;charset=utf-8" });
    const a = el("a", { href: URL.createObjectURL(blob), download: "live-page-feedback.txt" });
    a.click();
    URL.revokeObjectURL(a.href);
  }

  // --- Marking & Composer ---
  function setMarking(active) {
    markingMode = active;
    banner.hidden = !active;
    capture.hidden = !active;
    highlight.hidden = true;
    dragBox.hidden = true;
    dragStart = null;
    hoveredEl = null;
    if (active) closeComposer();
  }

  function openComposer(mark, anchorX, anchorY) {
    draftMark = mark;
    setMarking(false);
    composerText.value = "";
    composerErr.hidden = true;
    composerTarget.textContent =
      mark.context.mode === "element"
        ? `Element: ${mark.context.target.tag} "${mark.context.target.label}"`
        : mark.context.mode === "area"
          ? "Selected area on page"
          : `Page: ${currentPath}`;
    composer.hidden = false;
    const left = Math.max(12, Math.min(window.innerWidth - 376, anchorX + 12));
    const top = Math.max(12, Math.min(window.innerHeight - 280, anchorY + 12));
    composer.style.left = `${left}px`;
    composer.style.top = `${top}px`;
    composerText.focus();
  }

  function closeComposer() {
    composer.hidden = true;
    draftMark = null;
  }

  async function submitDraft() {
    const text = composerText.value.trim();
    if (!text) {
      composerErr.textContent = "Please enter a comment.";
      composerErr.hidden = false;
      return;
    }
    const author = composerAuthor.value.trim() || defaultAuthor;
    localStorage.setItem("lfb:author", author);
    composerSubmit.disabled = true;
    composerErr.hidden = true;
    try {
      const created = await apiFetch("", {
        method: "POST",
        body: JSON.stringify({
          id: draftMark.id,
          page: currentPath,
          box: draftMark.box,
          comment: text,
          author,
          context: draftMark.context,
        }),
      });
      items = [created, ...items.filter((x) => x.id !== created.id)];
      selectedId = created.id;
      closeComposer();
      updateCounts();
      renderMarkers();
      renderDrawer();
    } catch (err) {
      composerErr.textContent = err.message;
      composerErr.hidden = false;
    } finally {
      composerSubmit.disabled = false;
    }
  }

  function toggleDrawer() {
    drawer.hidden = !drawer.hidden;
    if (!drawer.hidden) renderDrawer();
  }

  // --- Capture Pointer Events ---
  capture.addEventListener("pointermove", (e) => {
    if (dragStart) {
      const left = Math.min(dragStart.x, e.clientX);
      const top = Math.min(dragStart.y, e.clientY);
      const w = Math.abs(e.clientX - dragStart.x);
      const h = Math.abs(e.clientY - dragStart.y);
      dragBox.hidden = w < 6 && h < 6;
      Object.assign(dragBox.style, { left: `${left}px`, top: `${top}px`, width: `${w}px`, height: `${h}px` });
      highlight.hidden = true;
      return;
    }
    capture.style.pointerEvents = "none";
    hoveredEl = targets.pick(e.clientX, e.clientY);
    capture.style.pointerEvents = "auto";
    if (hoveredEl) {
      const r = hoveredEl.getBoundingClientRect();
      highlight.hidden = false;
      Object.assign(highlight.style, { left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, height: `${r.height}px` });
    } else {
      highlight.hidden = true;
    }
  });

  capture.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    dragStart = { x: e.clientX, y: e.clientY };
  });

  capture.addEventListener("pointerup", (e) => {
    if (!dragStart) return;
    const dx = Math.abs(e.clientX - dragStart.x);
    const dy = Math.abs(e.clientY - dragStart.y);
    let mode = "page";
    let targetEl = null;
    let rect;
    if (dx >= 10 || dy >= 10) {
      mode = "area";
      rect = {
        left: Math.min(dragStart.x, e.clientX),
        top: Math.min(dragStart.y, e.clientY),
        right: Math.max(dragStart.x, e.clientX),
        bottom: Math.max(dragStart.y, e.clientY),
      };
    } else if (hoveredEl) {
      mode = "element";
      targetEl = hoveredEl;
      rect = hoveredEl.getBoundingClientRect();
    } else {
      rect = { left: e.clientX - 10, top: e.clientY - 10, right: e.clientX + 10, bottom: e.clientY + 10 };
    }
    const box = targets.boxForRect(rect) || { x: 0.5, y: 0.1, width: 0.02, height: 0.02 };
    openComposer({ id: crypto.randomUUID(), box, context: targets.snapshot(mode, targetEl) }, e.clientX, e.clientY);
  });

  // --- Global Keyboard Shortcut (`C` to mark, `Esc` to cancel) ---
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (markingMode) setMarking(false);
      else if (!composer.hidden) closeComposer();
      return;
    }
    if (
      e.key.toLowerCase() === "c" &&
      !e.metaKey &&
      !e.ctrlKey &&
      !e.altKey &&
      host &&
      !e.target.closest("input, textarea, select, [contenteditable='true']")
    ) {
      e.preventDefault();
      setMarking(!markingMode);
    }
  });

  // --- Attach Lifecycle ---
  function attach() {
    const path = location.pathname;
    const excluded = cfg.excludePaths.some((p) => path === p || path.startsWith(p + "/"));
    const nextHost = excluded ? null : document.querySelector(cfg.containerSelector) || document.body;
    if (nextHost !== host || path !== currentPath) {
      host = nextHost;
      currentPath = path;
      controls.hidden = !host;
      if (host) {
        syncGeometry();
        updateCounts();
        renderMarkers();
        renderDrawer();
      }
    }
    syncDialogLayer();
  }

  new MutationObserver(() => attach()).observe(document.body, { childList: true, subtree: true });
  window.addEventListener("popstate", attach);
  window.addEventListener("hashchange", attach);
  window.addEventListener("resize", () => { syncGeometry(); renderMarkers(); });

  attach();
  void fetchItems();
})();
