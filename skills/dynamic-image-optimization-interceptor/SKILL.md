---
name: dynamic-image-optimization-interceptor
description: Design, implement, review, or test a transparent authenticated static-image optimization interceptor that reuses existing image routes, responds to width parameters such as `w`, produces resized WebP output, and maintains a bounded 1 GiB local LRU disk cache. Use for Python, Node.js, Java, or PHP applications when dynamic image resizing must be added without introducing a new public API.
---

# Dynamic Image Optimization Interceptor

Implement image optimization inside the application's existing protected static-image delivery path. Do not create a new public endpoint, controller, route, or externally visible service.

## Required workflow

1. Inspect the existing image route, static-file handler, authorization layer, configuration, response streaming, and tests.
2. Place the interceptor after authentication and authorization but before the original image response is committed.
3. Fall through unchanged when the request is not an eligible image transformation request.
4. Resolve the source safely under allowlisted roots; never turn a raw request value into a filesystem path.
5. Build the canonical transformation descriptor and lowercase MD5 cache key exactly as defined in [references/mechanics.md](references/mechanics.md).
6. On cache hit, explicitly update atime and stream the WebP artifact.
7. On cache miss, use a per-key lock, recheck, enforce quota, transform to a same-filesystem temporary file, enforce final quota, atomically publish, and stream.
8. Keep cache usage at or below 1 GiB. When cleanup triggers, evict oldest-atime artifacts until usage reaches the 80% low watermark.
9. Map the implementation to the target runtime using [references/adaptation_matrix.md](references/adaptation_matrix.md).
10. Exercise the real authenticated route and verify every acceptance criterion before claiming completion.

## Non-negotiable invariants

- Authorize the original asset on every request, including cache hits.
- Do not add or document a new public API.
- Do not use MD5 for authentication, signatures, or integrity security; it is cache addressing only.
- Include a source-version fingerprint in the key so replaced originals invalidate old derivatives.
- Do not trust extensions, implicit filesystem atime behavior, client-provided cache keys, or raw paths.
- Write through temporary files and atomic rename. Never expose partial output.
- Use consistent lock ordering: per-key generation lock, then global eviction lock.
- Scan and evict only valid `.webp` artifacts inside the configured cache root.
- Ignore temporary files, lock files, symlinks, directories, and unknown files.
- Preserve existing authorization, tenant boundaries, anti-hotlinking, errors, and security headers.
- On processing failure, use an authorized fallback; never weaken authorization.

## References

- Read [references/architecture.md](references/architecture.md) for the request state machine, pipeline, concurrency, and failure paths.
- Read [references/mechanics.md](references/mechanics.md) for parameter contracts, source resolution, canonical hashing, quota enforcement, LRU eviction, locking, and tests.
- Read [references/adaptation_matrix.md](references/adaptation_matrix.md) only for the selected language and framework.
- Use [prompts/system_prompt.json](prompts/system_prompt.json) when delegating implementation to a coding Agent.

## Acceptance criteria

- No `w` parameter follows the original response path unchanged.
- A valid authenticated `w` request returns correctly resized WebP bytes.
- Repeating the same request produces a cache hit and explicit atime update.
- Parameter or source-version changes produce a different key.
- Concurrent identical misses publish one complete artifact.
- Unauthorized callers cannot infer or retrieve cached derivatives.
- LRU cleanup evicts oldest-atime files first and lowers usage to the configured watermark.
- Final cache usage never exceeds 1,073,741,824 bytes.
- No new public route appears in route listings.
- Real integration tests pass in the target stack.
