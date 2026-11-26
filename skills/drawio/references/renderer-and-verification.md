# Draw.io Official Renderer, Azure Icons & Verification Protocol

Reference procedures for `drawio` skill. Reference: https://www.drawio.com/doc/faq/embed-mode.

## 1. Official Embed JSON Protocol (No Desktop App Needed)

1. Load `https://embed.diagrams.net/?embed=1&proto=json&returnbounds=1` in an iframe (keeps diagram in browser memory; never uploads to cloud drives unless authorized).
2. Accept `postMessage` events only from the expected iframe/origin:
   - On `init`: send `{action: 'load', xml: sourceXml, autosave: 0}`.
   - On `load`: send `{action: 'export', format: 'png', scale: 1, border: 0, size: 'page', grid: false, withSvg: true}`.
3. **Select export payload by `event.format`, not `event.xml`**: official SVG/PNG export events can include both `data` and `xml`. Treating them as XML-only silently leaves old preview files untouched while roundtrip checks pass.
4. **Chunk large IPC payloads**: large XML/PNG/SVG payloads can exceed browser harness IPC limits. Append XML into a page variable in ≤20–22KB chunks and retrieve exported payloads in ≤20KB chunks; never print full base64 strings.

### Local Official Renderer Fallback

If `embed.diagrams.net` is blocked:

1. Sparse-clone `jgraph/drawio` into scratch:
   ```sh
   git clone --depth 1 --filter=blob:none --sparse https://github.com/jgraph/drawio.git
   git -C drawio sparse-checkout set src/main/webapp
   ```
2. Serve its parent directory on loopback with Python's HTTP server.
3. Load `src/main/webapp/index.html?embed=1&proto=json&offline=1&local=1&gapi=0&db=0&od=0&gl=0&tr=0` in a same-origin harness iframe using the identical `init` / `load` / `export` JSON protocol.

## 2. Multi-Page Export & Crop Traps

- **Import each page separately** when exporting SVG/PNG/roundtrip XML: some embed renderer versions return the active page's SVG even when `pageId` is supplied. Verify a unique title in every exported SVG instead of trusting the output filename; keep the complete editable multi-page `.drawio` source separately.
- **Export translation offsets**: derive crop offsets from actual export bounds or visible coordinates—SVG and PNG export translations can differ. Inspect full-page exports before modifying layout based on a crop.

## 3. Azure Icon Topology Diagrams

- Use Draw.io's actual `img/lib/azure2/...svg` shapes (verify exact asset names against `jgraph/drawio` rather than guessing or using generic cards/emoji).
- Preserve real PaaS/VNet boundaries: Web App VNet integration does not mean the app runs inside the subnet; Private Link endpoints and outbound integration are distinct relations. Do not copy Hub/Firewall/VPN/Bastion from visual references unless observed in the target environment.
- Build topology edges from real ARM resource ID references (`privateLinkServiceId`, `serverFarmId`, subnet IDs), not similar names. Group private-endpoint counts by the referenced target's owner and label aggregations explicitly.
- SVG export deduplicates repeated icons into `<defs><image>` plus `<use>` instances: count icon-bearing cell groups, resolve every `use` `href` to an existing definition, and confirm `data:` image assets are embedded.

## 4. Clickable Screenshots in Official Read-Only Viewer

1. Publish native-resolution PNGs to the authorized static host after inspecting for secrets/PII; deduplicate by content hash while keeping the node-to-screenshot manifest.
2. Wrap each clickable image cell in `<object>` (the viewer's `getLinkForCell` reads `cell.value.getAttribute('link')`; a plain `mxCell` `link` attribute does not create a click target):

```xml
<object id="step__image_1" label="" link="https://static.example/project/images/screen.png" linkTarget="_blank">
  <mxCell vertex="1" parent="step" style="shape=image;image=data:image/png,BASE64;">
    <mxGeometry x="20" y="80" width="220" height="150" as="geometry"/>
  </mxCell>
</object>
```

3. Publish the complete multi-page `.drawio` file at a stable HTTPS URL and build:
   ```text
   https://viewer.diagrams.net/?lightbox=1&nav=1&title=TITLE#U<urllib.parse.quote(source_url, safe='')>
   ```
   Use a temporary cache-busting query on `source_url` before encoding when verifying an update while preserving the canonical published filename.
4. When scaling geometry to make room for thumbnails inside native boxes, scale absolute geometry and explicit waypoints uniformly, but preserve fractional edge-label `mxGeometry` `x`/`y` when `relative="1"`.

## 5. Roundtrip & Browser Verification Checklist

- **Decompress & normalize**: decode compressed diagram XML (`base64` → raw deflate `wbits=-15` → URL decode → XML parse). Resolve every cell identity from `mxCell.id` or its wrapping `object.id` before building maps so wrapped screenshot cells never collapse under `null`.
- **Semantic preservation**: assert original IDs, values/labels, parents, vertex/edge flags, and connector source/target endpoints match. Count business statuses from the fixed-reference inventory and native shape fill colors, not from screenshot presence.
- **Image hash audit**: compare every embedded image ID and decoded PNG SHA-256 against the embedding manifest (a composite panel with multiple UI views is one embedded PNG). After any layout rebuild, regenerate all exports and verify exported SVG image hashes match the final embedded PNG inventory and that output files were actually written.
- **Real browser click check**: resolve thumbnail targets via `graph.view.getState(graph.model.getCell(stableId)).shape.node` (not SVG image ordinal, which can differ from manifest order). Scroll the shape into view, perform a real pointer click on each exposed stack rim (not a covered center or programmatic selection), and assert the opened original image URL and decoded bytes match the manifest. Counting `<a>` anchors is insufficient because the viewer handles links through graph click events.
- Keep native SVG/PNG, small previews, roundtrip XML, manifest hashes, and a concise verification README together. Distinguish diagram verification from broad application functional testing.
