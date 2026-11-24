#!/usr/bin/env node
/**
 * Zero-dependency reference dev/review backend for Live Page Feedback.
 *
 * Implements the full REST contract:
 *   GET    /api/live-page-feedback
 *   POST   /api/live-page-feedback
 *   PATCH  /api/live-page-feedback/:id
 *   DELETE /api/live-page-feedback/:id?version=N
 *   POST   /api/live-page-feedback/:id/comments
 *   DELETE /api/live-page-feedback/:id/comments/:commentId
 *   GET    /live-page-feedback.js
 *
 * Usage (standalone dev server):
 *   node feedback-server.mjs --port 4321 --db ./.local-runtime/live-page-feedback.json --origin http://localhost:4321
 *
 * Or import `createFeedbackHandler` into an existing Node HTTP/Express/Vite dev server.
 */

import fs from "node:fs";
import path from "node:path";
import http from "node:http";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function jsonResponse(res, status, data, extraHeaders = {}) {
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    ...extraHeaders,
  });
  res.end(JSON.stringify(data));
}

async function readJsonBody(req, maxBytes = 64 * 1024) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > maxBytes) throw Object.assign(new Error("Payload too large"), { status: 413 });
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
  } catch {
    throw Object.assign(new Error("Invalid JSON body"), { status: 400 });
  }
}

export class JsonFeedbackStore {
  constructor(filePath) {
    this.filePath = path.resolve(filePath);
    fs.mkdirSync(path.dirname(this.filePath), { recursive: true, mode: 0o700 });
    if (!fs.existsSync(this.filePath)) {
      this._write({ items: [] });
    }
  }

  _read() {
    return JSON.parse(fs.readFileSync(this.filePath, "utf8"));
  }

  _write(data) {
    const tmp = `${this.filePath}.tmp-${process.pid}-${Date.now()}`;
    fs.writeFileSync(tmp, JSON.stringify(data, null, 2) + "\n", { mode: 0o600 });
    fs.renameSync(tmp, this.filePath);
  }

  _project(item, ownerId) {
    return {
      ...item,
      owner: undefined,
      mine: item.owner === ownerId,
      comments: (item.comments || []).map((c) => ({ ...c, owner: undefined, mine: c.owner === ownerId })),
    };
  }

  list(ownerId) {
    const { items } = this._read();
    return items.map((it) => this._project(it, ownerId));
  }

  create(payload, ownerId) {
    if (!UUID_RE.test(String(payload.id || ""))) throw Object.assign(new Error("Valid UUID id required"), { status: 422 });
    const comment = String(payload.comment || "").trim();
    if (!comment || comment.length > 2000) throw Object.assign(new Error("Comment must be 1..2000 characters"), { status: 422 });
    const page = String(payload.page || "").trim();
    if (!page.startsWith("/") || page.includes("..")) throw Object.assign(new Error("Invalid page path"), { status: 422 });

    const data = this._read();
    const existing = data.items.find((it) => it.id === payload.id);
    if (existing) {
      if (existing.page === page && existing.comment === comment && existing.owner === ownerId) {
        return this._project(existing, ownerId);
      }
      throw Object.assign(new Error("Submission identifier is already in use"), { status: 409 });
    }

    const now = new Date().toISOString();
    const record = {
      id: payload.id,
      page,
      box: payload.box || { x: 0.5, y: 0.1, width: 0.02, height: 0.02 },
      comment,
      author: String(payload.author || "Reviewer").trim().slice(0, 80) || "Reviewer",
      owner: ownerId,
      status: "open",
      version: 1,
      context: payload.context || null,
      review: null,
      comments: [],
      createdAt: now,
      updatedAt: now,
    };
    data.items.unshift(record);
    this._write(data);
    return this._project(record, ownerId);
  }

  edit(id, ownerId, payload, { isMaintainer = false, build = "dev" } = {}) {
    const data = this._read();
    const item = data.items.find((it) => it.id === id);
    if (!item) throw Object.assign(new Error("Feedback not found"), { status: 404 });
    if (item.version !== payload.version) {
      throw Object.assign(new Error("This feedback changed. Refresh first."), { status: 409 });
    }
    const isAuthor = item.owner === ownerId;
    if ((payload.comment !== undefined || payload.status === "open" || payload.status === "resolved") && !isAuthor) {
      throw Object.assign(new Error("Only the author can edit, close, or reopen this thread"), { status: 403 });
    }
    if (payload.status === "resolved" && item.status !== "ready") {
      throw Object.assign(new Error("Mark the thread ready before resolving it"), { status: 409 });
    }
    const now = new Date().toISOString();
    if (payload.status === "ready") {
      if (!isAuthor && !isMaintainer) throw Object.assign(new Error("Only the author or maintainer can mark ready"), { status: 403 });
      if (item.status === "resolved") throw Object.assign(new Error("Reopen the thread before marking ready"), { status: 409 });
      item.review = { note: String(payload.note || "").trim().slice(0, 500), build, readyAt: now };
    }
    if (payload.comment !== undefined) {
      const next = String(payload.comment).trim();
      if (!next || next.length > 2000) throw Object.assign(new Error("Invalid comment"), { status: 422 });
      item.comment = next;
    }
    if (payload.status) item.status = payload.status;
    item.version += 1;
    item.updatedAt = now;
    this._write(data);
    return this._project(item, ownerId);
  }

  remove(id, ownerId, version) {
    const data = this._read();
    const idx = data.items.findIndex((it) => it.id === id);
    if (idx < 0) throw Object.assign(new Error("Feedback not found"), { status: 404 });
    const item = data.items[idx];
    if (item.owner !== ownerId) throw Object.assign(new Error("Only the author can delete this thread"), { status: 403 });
    if (item.version !== version) throw Object.assign(new Error("Stale version"), { status: 409 });
    data.items.splice(idx, 1);
    this._write(data);
  }

  addComment(id, ownerId, payload) {
    if (!UUID_RE.test(String(payload.id || ""))) throw Object.assign(new Error("Valid UUID comment id required"), { status: 422 });
    const comment = String(payload.comment || "").trim();
    if (!comment || comment.length > 2000) throw Object.assign(new Error("Reply must be 1..2000 characters"), { status: 422 });
    const data = this._read();
    const item = data.items.find((it) => it.id === id);
    if (!item) throw Object.assign(new Error("Feedback not found"), { status: 404 });
    if (!item.comments.some((c) => c.id === payload.id)) {
      item.comments.push({
        id: payload.id,
        author: String(payload.author || "Reviewer").trim().slice(0, 80) || "Reviewer",
        owner: ownerId,
        comment,
        createdAt: new Date().toISOString(),
      });
      item.updatedAt = new Date().toISOString();
      this._write(data);
    }
    return this._project(item, ownerId);
  }

  removeComment(id, commentId, ownerId) {
    const data = this._read();
    const item = data.items.find((it) => it.id === id);
    if (!item) throw Object.assign(new Error("Feedback not found"), { status: 404 });
    const idx = item.comments.findIndex((c) => c.id === commentId);
    if (idx < 0) throw Object.assign(new Error("Reply not found"), { status: 404 });
    if (item.comments[idx].owner !== ownerId) throw Object.assign(new Error("Only the author can delete this reply"), { status: 403 });
    item.comments.splice(idx, 1);
    item.updatedAt = new Date().toISOString();
    this._write(data);
    return this._project(item, ownerId);
  }
}

export function createFeedbackHandler({
  dbPath,
  prefix = "/api/live-page-feedback",
  widgetPath = "/live-page-feedback.js",
  allowedOrigin,
  getActor = () => ({ id: "local-reviewer", name: "Reviewer", isMaintainer: true }),
  getBuild = () => "local-dev",
}) {
  const store = new JsonFeedbackStore(dbPath);
  const csrfSecret = crypto.randomBytes(24).toString("hex");
  const csrfFor = (actorId) => crypto.createHmac("sha256", csrfSecret).update(actorId).digest("hex");
  const overlayBytes = Buffer.concat([
    fs.readFileSync(path.join(__dirname, "feedback-targets.js")),
    Buffer.from("\n"),
    fs.readFileSync(path.join(__dirname, "feedback-overlay.js")),
  ]);

  return async function handle(req, res) {
    const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);
    if (req.method === "GET" && url.pathname === widgetPath) {
      res.writeHead(200, { "Content-Type": "text/javascript; charset=utf-8", "Cache-Control": "no-cache" });
      res.end(overlayBytes);
      return true;
    }
    if (!url.pathname.startsWith(prefix)) return false;

    const actor = await getActor(req);
    const csrf = csrfFor(actor.id);
    const sub = url.pathname.slice(prefix.length);

    try {
      if (req.method !== "GET") {
        if (req.headers["sec-fetch-site"] === "cross-site") {
          throw Object.assign(new Error("Cross-site write forbidden"), { status: 403 });
        }
        if (allowedOrigin && req.headers.origin && req.headers.origin !== allowedOrigin) {
          throw Object.assign(new Error("Origin mismatch"), { status: 403 });
        }
        if (req.headers["x-feedback-csrf"] !== csrf) {
          throw Object.assign(new Error("Missing or invalid CSRF token"), { status: 403 });
        }
      }

      if (req.method === "GET" && (sub === "" || sub === "/")) {
        jsonResponse(res, 200, {
          items: store.list(actor.id),
          csrfToken: csrf,
          author: actor.name,
          canMarkReady: Boolean(actor.isMaintainer),
          build: getBuild(),
        });
        return true;
      }
      if (req.method === "POST" && (sub === "" || sub === "/")) {
        const created = store.create(await readJsonBody(req), actor.id);
        jsonResponse(res, 201, created);
        return true;
      }
      const idMatch = /^\/([^/]+)$/.exec(sub);
      if (idMatch && req.method === "PATCH") {
        const updated = store.edit(idMatch[1], actor.id, await readJsonBody(req), {
          isMaintainer: Boolean(actor.isMaintainer),
          build: getBuild(),
        });
        jsonResponse(res, 200, updated);
        return true;
      }
      if (idMatch && req.method === "DELETE") {
        const version = Number(url.searchParams.get("version"));
        store.remove(idMatch[1], actor.id, version);
        res.writeHead(204, { "Cache-Control": "no-store" });
        res.end();
        return true;
      }
      const commentsMatch = /^\/([^/]+)\/comments$/.exec(sub);
      if (commentsMatch && req.method === "POST") {
        const updated = store.addComment(commentsMatch[1], actor.id, await readJsonBody(req));
        jsonResponse(res, 201, updated);
        return true;
      }
      const commentDelMatch = /^\/([^/]+)\/comments\/([^/]+)$/.exec(sub);
      if (commentDelMatch && req.method === "DELETE") {
        const updated = store.removeComment(commentDelMatch[1], commentDelMatch[2], actor.id);
        jsonResponse(res, 200, updated);
        return true;
      }
      jsonResponse(res, 404, { detail: "Not found" });
      return true;
    } catch (err) {
      jsonResponse(res, err.status || 500, { detail: err.message || "Internal error" });
      return true;
    }
  };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const args = Object.fromEntries(
    process.argv.slice(2).reduce((acc, cur, idx, arr) => {
      if (cur.startsWith("--")) acc.push([cur.slice(2), arr[idx + 1]]);
      return acc;
    }, [])
  );
  const port = Number(args.port || 4321);
  const dbPath = args.db || ".local-runtime/live-page-feedback.json";
  const handler = createFeedbackHandler({ dbPath, allowedOrigin: args.origin });
  http
    .createServer(async (req, res) => {
      const handled = await handler(req, res);
      if (!handled) jsonResponse(res, 404, { detail: "Not found" });
    })
    .listen(port, "127.0.0.1", () => {
      console.log(`Live Page Feedback dev server listening on http://127.0.0.1:${port}`);
    });
}
