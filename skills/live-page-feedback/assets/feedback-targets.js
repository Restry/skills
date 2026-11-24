/**
 * Framework-agnostic semantic element targeting and context snapshotting
 * for Live Page Feedback. Stores zero CSS class names or React internals.
 */
(function (global) {
  function createFeedbackTargets(options) {
    const getHost = options.getHost;
    const layer = options.layer;
    const getActiveDialog = options.getActiveDialog;
    const chrome = options.chrome;

    const CONTROL_SELECTOR =
      '[data-feedback-target], button, a[href], input, select, textarea, th, td, [role="button"], [role="combobox"], [role="tab"], [role="checkbox"]';
    const FILTER_SELECTOR =
      '[data-feedback-filter], input[type="search"], input[type="date"], select, button[role="combobox"], [role="tab"][aria-selected="true"]';
    const INTERACTIVE_SELECTOR =
      'button, a[href], input, select, textarea, [role="button"], [role="combobox"], [role="tab"], [role="checkbox"]';
    const EXCLUDED_INPUT = 'input[type="password"], input[type="hidden"], [data-feedback-private]';

    function compact(value, max = 160) {
      return String(value ?? "").replace(/\s+/g, " ").trim().slice(0, max);
    }

    function accessibleName(el) {
      const labelledBy = (el.getAttribute("aria-labelledby") || "")
        .split(/\s+/)
        .filter(Boolean)
        .map((id) => document.getElementById(id)?.textContent || "")
        .join(" ");
      const label =
        el.getAttribute("aria-label") ||
        labelledBy ||
        el.labels?.[0]?.textContent ||
        el.getAttribute("title") ||
        el.getAttribute("placeholder");
      if (label) return compact(label);
      if (el.matches('button, a, th, td, [role="button"], [role="tab"]')) {
        return compact(el.textContent);
      }
      return "";
    }

    function anchor(el) {
      const area = el.closest('dialog, [role="dialog"], [data-feedback-section], table, section');
      const scope =
        area &&
        (area.dataset.feedbackSection ||
          area.getAttribute("aria-label") ||
          area.querySelector('caption, h1, h2, h3, [role="heading"]')?.textContent);
      const rawKey =
        el.dataset.feedbackTarget || (/^[A-Za-z][\w.-]*$/.test(el.id) ? el.id : "");
      return {
        tag: el.localName,
        label: accessibleName(el),
        key: compact(rawKey, 120) || null,
        scope: compact(scope) || null,
      };
    }

    function isBusinessControl(el) {
      const scopeRoot = getActiveDialog() || getHost();
      return (
        !!scopeRoot &&
        scopeRoot.contains(el) &&
        !layer.contains(el) &&
        !chrome.contains(el) &&
        !el.matches(EXCLUDED_INPUT)
      );
    }

    function pick(clientX, clientY) {
      for (const node of document.elementsFromPoint(clientX, clientY)) {
        if (layer.contains(node) || chrome.contains(node)) continue;
        const el = node.closest(CONTROL_SELECTOR);
        if (el && isBusinessControl(el)) return el;
      }
      return null;
    }

    function locate(saved) {
      if (!saved || (!saved.key && !saved.label)) return null;
      const scopeRoot = getActiveDialog() || getHost();
      if (!scopeRoot) return null;
      const candidates = [...scopeRoot.querySelectorAll(CONTROL_SELECTOR)].filter(
        (el) => isBusinessControl(el) && el.getClientRects().length > 0
      );
      const keyed = saved.key
        ? candidates.filter((el) => anchor(el).key === saved.key)
        : [];
      if (keyed.length === 1 && (!saved.label || accessibleName(keyed[0]) === saved.label)) {
        return keyed[0];
      }
      const pool = keyed.length ? keyed : candidates;
      const semantic = pool.filter((el) => {
        const found = anchor(el);
        return (
          found.tag === saved.tag &&
          found.label === saved.label &&
          found.scope === saved.scope
        );
      });
      return semantic.length === 1 ? semantic[0] : null;
    }

    function boxForRect(rect) {
      const bounds = layer.getBoundingClientRect();
      if (!bounds.width || !bounds.height) return null;
      const clamp = (v) => Math.max(0, Math.min(1, v));
      const x = clamp((rect.left - bounds.left) / bounds.width);
      const y = clamp((rect.top - bounds.top) / bounds.height);
      const width = clamp((rect.right - bounds.left) / bounds.width) - x;
      const height = clamp((rect.bottom - bounds.top) / bounds.height) - y;
      if (width < 0.002 || height < 0.002) return null;
      return { x, y, width, height };
    }

    function box(el) {
      return boxForRect(el.getBoundingClientRect());
    }

    function filters() {
      const host = getHost();
      if (!host) return [];
      const values = new Map();
      for (const el of host.querySelectorAll(FILTER_SELECTOR)) {
        if (layer.contains(el) || chrome.contains(el) || !el.getClientRects().length || el.matches(EXCLUDED_INPUT)) {
          continue;
        }
        const label = compact(el.getAttribute("data-feedback-filter") || accessibleName(el), 120);
        const value = compact(el.selectedOptions?.[0]?.textContent ?? el.value ?? el.textContent);
        if (label && value) values.set(label, { label, value });
        if (values.size >= 16) break;
      }
      return [...values.values()];
    }

    function build() {
      const script = document.querySelector('script[type="module"][src]');
      if (!script) return null;
      try {
        const url = new URL(script.src, location.href);
        if (url.origin === location.origin) return url.pathname.slice(0, 160);
      } catch {
        // ignore invalid src
      }
      return null;
    }

    function cleanRoute(search = location.search, hash = location.hash) {
      const params = new URLSearchParams(search);
      params.delete("feedback");
      const q = params.toString();
      return (q ? `?${q}` : "") + (hash || "");
    }

    function snapshot(mode, element) {
      return {
        mode,
        target: element ? anchor(element) : null,
        filters: filters(),
        language: document.documentElement.lang || "en",
        build: build(),
        route: cleanRoute(),
      };
    }

    return {
      pick,
      locate,
      box,
      boxForRect,
      filters,
      build,
      anchor,
      cleanRoute,
      snapshot,
      isInteractive: (el) =>
        el instanceof Element && isBusinessControl(el) && el.matches(INTERACTIVE_SELECTOR),
    };
  }

  global.createLiveFeedbackTargets = createFeedbackTargets;
})(typeof window !== "undefined" ? window : globalThis);
