#!/usr/bin/env node
/**
 * Zero-dependency static builder for Product Walkthrough.
 *
 * Usage:
 *   node build-walkthrough.mjs --manifest ./walkthrough.json --out ./dist [--canvas 1920x1080] [--allow-mixed-ratio]
 *
 * Enforces:
 * - Every referenced raw PNG exists and is a valid PNG.
 * - Single uniform aspect ratio across all raw captures (unless --allow-mixed-ratio is explicitly passed).
 * - Uniform 1920x1080 (or --canvas WxH) output via ImageMagick `magick` when source differs from target.
 * - Separate sourceSha256 and displaySha256 provenance in report-data/results.json.
 * - Reversible releaseBoundary via inert <template> tags (never CSS-only hiding).
 */

import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PNG_MAGIC = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

function parseArgs(argv) {
  const args = { canvas: "1920x1080", allowMixedRatio: false };
  for (let i = 0; i < argv.length; i++) {
    const flag = argv[i];
    if (flag === "--manifest") args.manifest = argv[++i];
    else if (flag === "--out") args.out = argv[++i];
    else if (flag === "--canvas") args.canvas = argv[++i];
    else if (flag === "--allow-mixed-ratio") args.allowMixedRatio = true;
    else if (flag === "--help" || flag === "-h") args.help = true;
    else throw new Error(`Unknown argument: ${flag}`);
  }
  return args;
}

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function readPngDimensions(bytes, filePath) {
  if (bytes.length < 24 || !bytes.subarray(0, 8).equals(PNG_MAGIC)) {
    throw new Error(`Invalid PNG file: ${filePath}`);
  }
  return [bytes.readUInt32BE(16), bytes.readUInt32BE(20)];
}

function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function chapterState(chapter) {
  const statuses = chapter.operations.flatMap(op => op.steps.map(s => s.status || "pass"));
  if (statuses.includes("failed")) return "failed";
  if (statuses.includes("blocked")) return "blocked";
  if (statuses.every(s => s === "simulation")) return "simulation";
  return "pass";
}

function fitToCanvas(srcPath, rawBytes, rawDim, targetW, targetH, bgColor) {
  if (rawDim[0] === targetW && rawDim[1] === targetH) {
    return rawBytes;
  }
  try {
    return execFileSync(
      "magick",
      [
        srcPath,
        "-resize",
        `${targetW}x${targetH}`,
        "-background",
        bgColor,
        "-gravity",
        "center",
        "-extent",
        `${targetW}x${targetH}`,
        "PNG:-",
      ],
      { maxBuffer: 25 * 1024 * 1024 }
    );
  } catch (err) {
    throw new Error(
      `Source ${srcPath} is ${rawDim[0]}x${rawDim[1]} (target ${targetW}x${targetH}), and ImageMagick 'magick' failed: ${err.message}`
    );
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || !args.manifest || !args.out) {
    console.log("Usage: node build-walkthrough.mjs --manifest <manifest.json> --out <output-dir> [--canvas 1920x1080]");
    process.exit(args.help ? 0 : 1);
  }

  const canvasMatch = /^(\d+)x(\d+)$/.exec(args.canvas);
  if (!canvasMatch) throw new Error(`Invalid --canvas format: ${args.canvas}`);
  const targetW = Number(canvasMatch[1]);
  const targetH = Number(canvasMatch[2]);

  const manifestPath = path.resolve(args.manifest);
  const manifestDir = path.dirname(manifestPath);
  const outDir = path.resolve(args.out);
  const manifestBytes = fs.readFileSync(manifestPath);
  const manifest = JSON.parse(manifestBytes.toString("utf8"));

  if (!manifest.title || !Array.isArray(manifest.chapters) || manifest.chapters.length === 0) {
    throw new Error("Manifest must include non-empty 'title' and 'chapters'.");
  }

  const bgColor = manifest.canvasBackground || "#eef0f2";
  const brandColor = manifest.brandColor || "#005aa9";
  const lang = manifest.lang || "en";
  const maxChapter = manifest.releaseBoundary?.maxChapter ?? Infinity;
  const lockedLabel = manifest.releaseBoundary?.lockedLabel || "Planned release";

  // 1. Validate unique IDs & uniform aspect ratio across all raw captures
  const seenStepIds = new Set();
  const rawMeta = new Map();
  let baselineRatio = null;
  let baselineDim = null;

  for (const chapter of manifest.chapters) {
    for (const op of chapter.operations) {
      for (const step of op.steps) {
        if (seenStepIds.has(step.id)) throw new Error(`Duplicate step id: ${step.id}`);
        seenStepIds.add(step.id);
        const srcPath = path.resolve(manifestDir, step.source);
        if (!fs.existsSync(srcPath)) throw new Error(`Missing screenshot for step '${step.id}': ${srcPath}`);
        const bytes = fs.readFileSync(srcPath);
        const dim = readPngDimensions(bytes, srcPath);
        const ratio = dim[0] / dim[1];
        if (baselineRatio === null) {
          baselineRatio = ratio;
          baselineDim = dim;
        } else if (!args.allowMixedRatio && Math.abs(ratio - baselineRatio) > 0.04) {
          throw new Error(
            `Aspect ratio mismatch on step '${step.id}' (${dim[0]}x${dim[1]}, ratio ${ratio.toFixed(3)}) vs baseline (${baselineDim[0]}x${baselineDim[1]}, ratio ${baselineRatio.toFixed(3)}). Recapture at a uniform viewport or pass --allow-mixed-ratio.`
          );
        }
        rawMeta.set(step.id, { srcPath, bytes, dim, sourceSha256: sha256(bytes) });
      }
    }
  }

  // 2. Prepare output directories and render uniform display PNGs
  fs.mkdirSync(path.join(outDir, "screenshots"), { recursive: true });
  fs.mkdirSync(path.join(outDir, "report-data"), { recursive: true });

  const stepsManifest = [];
  let visibleChapterCount = 0;
  let visibleOperationCount = 0;
  let visibleStepCount = 0;

  const tabsHtml = [];
  const outlineHtml = [];
  const panelsHtml = [];
  const lockedTemplatesHtml = [];

  manifest.chapters.forEach((chapter, chapterIdx) => {
    const chapterNum = chapterIdx + 1;
    const locked = chapterNum > maxChapter;
    const state = chapterState(chapter);
    const chapterStepTotal = chapter.operations.reduce((acc, op) => acc + op.steps.length, 0);

    if (!locked) {
      visibleChapterCount += 1;
      visibleOperationCount += chapter.operations.length;
      visibleStepCount += chapterStepTotal;
    }

    tabsHtml.push(
      `<button type="button" class="tab-btn" role="tab" data-chapter="${esc(chapter.id)}" data-state="${esc(state)}" aria-selected="false"${locked ? ` disabled title="${esc(lockedLabel)}"` : ""}>${esc(chapter.tabLabel || chapter.title)}</button>`
    );

    const opsOutline = [];
    const opsHtml = [];
    let chapterStepCursor = 0;

    for (const op of chapter.operations) {
      const opAnchor = `op-${chapter.id}-${op.id}`;
      if (!locked) {
        opsOutline.push(
          `<li><a class="outline-op-link" href="#${esc(opAnchor)}" data-chapter="${esc(chapter.id)}" data-operation="${esc(opAnchor)}">${esc(op.title)}</a></li>`
        );
      }

      const figuresHtml = [];
      op.steps.forEach((step, stepIdx) => {
        chapterStepCursor += 1;
        const meta = rawMeta.get(step.id);
        const displayBytes = fitToCanvas(meta.srcPath, meta.bytes, meta.dim, targetW, targetH, bgColor);
        const displayDim = readPngDimensions(displayBytes, step.id);
        const displaySha = sha256(displayBytes);
        const relPath = `screenshots/${step.id}-${displaySha.slice(0, 10)}.png`;
        fs.writeFileSync(path.join(outDir, relPath), displayBytes);

        const status = step.status || "pass";
        const statusLabel = step.statusLabel || status;
        const numberedTitle = `${stepIdx + 1}. ${step.title}`;

        stepsManifest.push({
          id: step.id,
          chapterId: chapter.id,
          chapterTitle: chapter.title,
          operationId: op.id,
          operationTitle: op.title,
          title: step.title,
          role: step.role || null,
          status,
          statusLabel,
          locked,
          capturedAt: step.capturedAt || null,
          url: step.url || null,
          source: step.source,
          sourceViewport: meta.dim,
          sourceSha256: meta.sourceSha256,
          screenshot: relPath,
          displayViewport: displayDim,
          displaySha256: displaySha,
          narration: step.narration || null,
        });

        figuresHtml.push(`<figure data-step-id="${esc(step.id)}" data-title="${esc(step.title)}" data-role="${esc(step.role || "")}" data-status="${esc(status)}" data-status-label="${esc(statusLabel)}" data-source-hash="${meta.sourceSha256}" data-display-hash="${displaySha}">
  <button type="button" class="shot-button" aria-label="Open screenshot: ${esc(step.title)}">
    <img src="${esc(relPath)}" alt="${esc(step.title)}" width="${displayDim[0]}" height="${displayDim[1]}" loading="lazy">
    <span class="shot-overlay">${chapterStepCursor}/${chapterStepTotal}</span>
    <span class="zoom-badge">Zoom</span>
  </button>
  <figcaption>
    <div class="caption-row">
      <span class="status-dot ${esc(status)}" title="${esc(statusLabel)}"><span class="sr-only">${esc(statusLabel)}</span></span>
      <h4>${esc(numberedTitle)}</h4>
    </div>
    ${step.role ? `<div class="shot-role">${esc(step.role)}</div>` : ""}
  </figcaption>
</figure>`);
      });

      opsHtml.push(`<section class="operation" id="${esc(opAnchor)}">
  <div class="operation-head"><h3>${esc(op.title)}</h3></div>
  <div class="shots">${figuresHtml.join("\n")}</div>
</section>`);
    }

    outlineHtml.push(`<li data-expanded="${locked ? "false" : "true"}">
  <div class="outline-ch-row">
    <button type="button" class="outline-ch-btn" data-chapter="${esc(chapter.id)}" data-state="${esc(state)}"${locked ? ` disabled title="${esc(lockedLabel)}"` : ""}>
      <span>${esc(chapter.title)}</span>
      <span class="outline-ch-count">${locked ? esc(lockedLabel) : chapterStepTotal}</span>
    </button>
    ${locked ? "" : `<button type="button" class="outline-fold" aria-label="Toggle chapter" aria-expanded="true"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="m6 9 6 6 6-6"/></svg></button>`}
  </div>
  ${locked ? "" : `<ol class="outline-ops">${opsOutline.join("\n")}</ol>`}
</li>`);

    const panelMarkup = `<section class="chapter-panel" role="tabpanel" data-chapter="${esc(chapter.id)}" hidden>
  <div class="chapter-header">
    <h2>${esc(chapter.title)}</h2>
    <span class="chapter-count">${chapterStepTotal} ${chapterStepTotal === 1 ? "step" : "steps"}</span>
  </div>
  ${opsHtml.join("\n")}
</section>`;

    if (locked) {
      lockedTemplatesHtml.push(`<template data-locked-chapter="${esc(chapter.id)}">${panelMarkup}</template>`);
    } else {
      panelsHtml.push(panelMarkup);
    }
  });

  const summaryCounts = `${visibleChapterCount} ${visibleChapterCount === 1 ? "chapter" : "chapters"} · ${visibleStepCount} ${visibleStepCount === 1 ? "step" : "steps"}`;
  const pageTitle = manifest.product ? `${manifest.title} · ${manifest.product}` : manifest.title;
  const productEyebrow = manifest.product ? `<span class="eyebrow">${esc(manifest.product)}</span>` : "";

  const template = fs.readFileSync(path.join(__dirname, "walkthrough-template.html"), "utf8");
  const html = template
    .replaceAll("__LANG__", esc(lang))
    .replaceAll("__PAGE_TITLE__", esc(pageTitle))
    .replaceAll("__BRAND_COLOR__", brandColor)
    .replaceAll("__TITLE__", esc(manifest.title))
    .replaceAll("__PRODUCT_EYEBROW__", productEyebrow)
    .replaceAll("__SUMMARY_COUNTS__", esc(summaryCounts))
    .replaceAll("__TOTAL_STEPS__", String(visibleStepCount))
    .replaceAll("__TABS_HTML__", tabsHtml.join("\n        "))
    .replaceAll("__PANELS_HTML__", panelsHtml.join("\n    "))
    .replaceAll("__LOCKED_TEMPLATES_HTML__", lockedTemplatesHtml.join("\n    "))
    .replaceAll("__OUTLINE_HTML__", outlineHtml.join("\n        "));

  const results = {
    title: manifest.title,
    product: manifest.product || null,
    generatedAt: new Date().toISOString(),
    manifestSha256: sha256(manifestBytes),
    canvas: [targetW, targetH],
    releaseBoundary: manifest.releaseBoundary || null,
    counts: {
      chapters: visibleChapterCount,
      totalChapters: manifest.chapters.length,
      operations: visibleOperationCount,
      steps: visibleStepCount,
      totalSteps: stepsManifest.length,
    },
    steps: stepsManifest,
  };

  fs.writeFileSync(path.join(outDir, "index.html"), html, "utf8");
  fs.writeFileSync(path.join(outDir, "report-data/results.json"), JSON.stringify(results, null, 2) + "\n", "utf8");

  console.log(
    JSON.stringify({
      outDir,
      canvas: `${targetW}x${targetH}`,
      counts: results.counts,
      manifestSha256: results.manifestSha256.slice(0, 12),
    })
  );
}

main();
