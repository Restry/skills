# Architecture

## Scope

The interceptor augments an existing protected static-image path. It is not a standalone image service and must not create a new public endpoint. Run it after request identity and authorization are established and before the original static-file response is committed.

## Request pipeline

```text
Existing image request: /assets/photo.jpg?w=960
  │
  ├─ route not eligible / no w ──────────────► existing handler
  ▼
existing authentication and authorization
  ├─ denied ─────────────────────────────────► existing 401/403
  ▼
safe source resolution under allowlisted root
  ├─ missing/unsafe/unsupported ─────────────► existing 404/415 policy
  ▼
strict parameter normalization
  ├─ malformed ──────────────────────────────► 400
  ▼
canonical descriptor → MD5 → sharded cache path
  │
  ├─ cache hit → explicit atime update → stream WebP
  ▼
acquire per-key generation lock
  ▼
recheck cache
  ├─ appeared → explicit atime update → stream WebP
  ▼
quota preflight under global eviction lock
  ▼
decode → orient → resize → WebP encode to same-filesystem temp
  ▼
final quota check using actual candidate size
  ▼
atomic rename → explicit atime update → stream WebP
```

## State machine

| State | Purpose | Valid next states |
|---|---|---|
| `RECEIVED` | Request entered existing image path | `INELIGIBLE`, `AUTHORIZING` |
| `INELIGIBLE` | No transform trigger or unsupported method | `FALLTHROUGH` |
| `AUTHORIZING` | Execute existing policy | `DENIED`, `RESOLVING_SOURCE` |
| `DENIED` | Existing policy rejected request | `TERMINAL` |
| `RESOLVING_SOURCE` | Resolve application-owned asset under allowed roots | `SOURCE_ERROR`, `VALIDATING` |
| `VALIDATING` | Parse and normalize transform contract | `INVALID`, `HASHING` |
| `HASHING` | Build descriptor, MD5, and final path | `CACHE_LOOKUP` |
| `CACHE_LOOKUP` | Check complete published artifact | `CACHE_HIT`, `LOCKING` |
| `CACHE_HIT` | Valid artifact exists | `TOUCHING` |
| `LOCKING` | Acquire per-key lock | `RECHECKING` |
| `RECHECKING` | Avoid duplicate work after lock wait | `CACHE_HIT`, `QUOTA_PREFLIGHT` |
| `QUOTA_PREFLIGHT` | Measure and optionally evict | `TRANSFORMING`, `CACHE_ERROR` |
| `TRANSFORMING` | Decode, orient, and resize | `ENCODING`, `PROCESSING_ERROR` |
| `ENCODING` | Write WebP to temporary file | `FINAL_QUOTA`, `PROCESSING_ERROR` |
| `FINAL_QUOTA` | Use actual output size to enforce cap | `PUBLISHING`, `UNCACHEABLE` |
| `PUBLISHING` | Atomically rename temp to final | `TOUCHING`, `CACHE_ERROR` |
| `TOUCHING` | Explicitly set atime to now while preserving mtime | `RESPONDING` |
| `RESPONDING` | Stream optimized response | `TERMINAL` |
| `UNCACHEABLE` | Candidate cannot safely fit | `RESPONDING_TEMP`, `CLEANUP` |
| `PROCESSING_ERROR` | Image operation failed | `SAFE_FALLBACK`, `TERMINAL` |
| `CACHE_ERROR` | Cache operation failed | `SAFE_FALLBACK`, `TERMINAL` |

## Authorization boundary

Run authorization before:

- cache existence checks;
- derivative streaming;
- source metadata exposure;
- image decoding;
- cache-key generation based on protected source identity.

A cache hit is an optimization, never an authorization result. Tenant-scoped assets must use tenant-scoped source identities.

## Concurrency

### Per-key generation lock

Use one lock per MD5 key. The required sequence is:

```text
lookup → miss → acquire key lock → lookup again → generate if still missing
```

This prevents duplicate conversions and competing writers.

### Global eviction lock

Use one lock per cache root. Hold it only while measuring usage, selecting candidates, deleting artifacts, and publishing a candidate whose size affects quota.

Use a single lock order everywhere:

```text
per-key lock → global eviction lock
```

Never acquire a per-key lock while holding the global lock.

## Atomic publication

Create the temporary file in the final shard directory:

```text
cache/7a/.7af83d28.<unique>.tmp
  ↓ close/flush
cache/7a/7af83d28e55369dce65e3884f732afb1.webp
```

Publish using atomic same-filesystem rename. Readers may see no final file or one complete file; never a partial artifact.

## Response contract

Optimized responses should provide:

```text
Content-Type: image/webp
Content-Length: <exact bytes>
ETag: "<md5-key>"
X-Content-Type-Options: nosniff
```

Preserve existing authorization and cache-control headers when semantically valid. Support `HEAD` with equivalent headers and no body.

## Failure behavior

- Invalid parameters: use existing validation behavior or return `400`.
- Unsupported image: fall through or use existing `415` policy.
- Conversion failure after authorization: serve the authorized original or use the application's standard processing error.
- Cache failure: log internally, remove temporary files, and use non-cached transformed output or an authorized fallback.
- Never reveal source paths, cache roots, lock names, or internal exceptions.

## Observability

Emit structured internal events without adding a public API:

- `image_interceptor_cache_hit`
- `image_interceptor_cache_miss`
- `image_interceptor_transform_ms`
- `image_interceptor_output_bytes`
- `image_interceptor_evicted_files`
- `image_interceptor_evicted_bytes`
- `image_interceptor_lock_wait_ms`
- `image_interceptor_fallback`
- `image_interceptor_error`

Do not log credentials, authorization headers, signed URLs, or raw local paths.
