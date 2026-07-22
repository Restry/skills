# Mechanics

## Constants

Use binary units:

```text
MIB               = 1,048,576 bytes
CACHE_HIGH_BYTES  = 1,024 × MIB = 1,073,741,824 bytes
CACHE_LOW_BYTES   = floor(819.2 × MIB) = 858,993,459 bytes
```

The completed cache must never exceed `CACHE_HIGH_BYTES`.

## Eligibility and parameters

A request is eligible only when it matches an existing protected static-image route, passes existing authorization, contains `w`, resolves to an allowed raster source, and has not committed a response.

| Parameter | Contract | Canonical form |
|---|---|---|
| `w` | Required trigger; strict base-10 integer `1..4096` | Decimal, no leading zeros |
| `q` | Only if already public; integer `1..100`, default `80` | Decimal |
| `h` | Only if already public; integer `1..4096` | Decimal or `-` |
| `fit` | Only if already public; `contain` or `cover` | Lowercase |
| `dpr` | Only if already public; explicit allowlist | Normalized decimal |
| `format` | Must resolve to WebP | `webp` |

Do not add new public parameters solely for this interceptor. Reject decimals, exponent notation, whitespace padding, overflow, zero, negatives, and conflicting duplicates.

When only `w` exists:

```text
target_width  = min(w, source_width)
target_height = round(source_height × target_width / source_width)
```

Do not upscale by default. Apply EXIF orientation before dimension calculation. Never stretch pixels.

## Source resolution

1. Use the framework's canonical decoded request path.
2. Reject NUL bytes and traversal after normalization.
3. Resolve against allowlisted static roots.
4. Resolve symlinks before checking root containment.
5. Require a regular file and configured input-size limit.
6. Detect type from decoded bytes, not extension alone.
7. Enforce maximum pixel count and decompression-bomb protection.
8. Do not fetch arbitrary remote URLs.

Baseline inputs: JPEG, PNG, and static WebP. Bypass or reject animation unless explicitly supported. Do not rasterize SVG by default.

## Source identity and invalidation

Use an application-relative path or immutable asset ID, never an absolute path.

```text
source_id      = normalized application-owned identity
source_version = source_size + ":" + highest-resolution mtime
```

Prefer an immutable storage version, content digest, or ETag when available. A source change must produce a different cache key. Old derivatives become unreachable and are later removed by LRU.

## Canonical descriptor

Build UTF-8 text with LF separators, fixed field order, and no trailing newline:

```text
version=1
source=<source_id>
source_version=<source_version>
w=<normalized_width>
q=80
format=webp
```

If existing public parameters are supported, append in this order:

```text
h=<height-or-dash>
fit=<normalized-fit>
dpr=<normalized-dpr>
```

Never serialize an unordered map.

## MD5 addressing

```text
cache_key = lowercase_hex(MD5(UTF8(canonical_descriptor)))
cache_path = <cache_root>/<key[0:2]>/<key>.webp
```

The key must be exactly 32 lowercase hexadecimal characters. MD5 is cache addressing only, not a security primitive.

## Cache hit

```text
if final path is a regular valid .webp artifact:
    open for reading
    set atime = now explicitly
    preserve mtime
    stream response
else:
    treat as miss
```

Do not trust implicit atime updates because filesystems may use `noatime`, `relatime`, or delayed metadata writes.

## Cache miss

```text
acquire per-key lock
try:
    recheck final artifact
    if present: touch atime and return

    under global eviction lock:
        usage = sum valid artifact lengths
        if usage >= HIGH:
            evict oldest-atime artifacts until usage <= LOW

    decode source
    apply orientation
    resize without enlargement
    encode WebP to same-filesystem temp
    close and flush temp
    candidate_size = stat(temp).size

    if candidate_size > HIGH:
        stream temp without caching
        delete temp
        return

    under global eviction lock:
        usage = remeasure
        if usage + candidate_size > HIGH:
            evict until usage <= LOW
            continue if needed until usage + candidate_size <= HIGH
        atomic rename temp → final
        touch final atime

    stream final
finally:
    remove abandoned temp
    release key lock
```

Decode outside the global eviction lock. Reacquire it for final accounting and publication.

## Usage calculation

Count only paths matching:

```text
<cache_root>/<two-lowercase-hex>/<32-lowercase-hex>.webp
```

Exclude directories, symlinks, temp files, locks, metadata, and unknown files. Do not follow symlinks. Sum actual file lengths. The filesystem remains the final source of truth even if an index is used.

## LRU eviction

Candidate tuple:

```text
(atime_ns, stable_relative_path, size_bytes)
```

Sort by access time ascending, then path ascending. Skip the current key, active-generation targets, locked files, and files that disappear during scanning.

When high-water cleanup triggers, target `CACHE_LOW_BYTES`, not merely one byte below the high watermark.

If `LOW + candidate_size > HIGH`, continue below LOW until the candidate fits. If the candidate itself exceeds HIGH, do not cache it.

## Lock files

```text
<cache_root>/.locks/<cache_key>.lock
<cache_root>/.locks/eviction.lock
```

Use OS-backed advisory locks or a maintained runtime library. Require bounded acquisition, stale-lock recovery, process-exit release, and consistent lock ordering.

## WebP encoding

Baseline:

```text
format: WebP
quality: 80
color space: sRGB
metadata: stripped
upscale: disabled
```

Apply EXIF orientation, preserve alpha, enforce decoder memory/pixel bounds, strip EXIF/GPS/application metadata, and close native image handles promptly.

## Security

- Authenticate and authorize before every cache lookup.
- Preserve tenant boundaries in `source_id`.
- Never accept a client cache key or output path.
- Never use raw request paths as filesystem paths.
- Never follow cache-root symlinks.
- Never publish partial files.
- Never clean outside the configured root.
- Never expose paths or confidential query values in logs.
- Never weaken authorization during fallback.

## Required tests

### Contract

- no `w` falls through;
- minimum, maximum, malformed, duplicate, zero, negative, and overflowing widths;
- no upscaling;
- EXIF orientation and alpha preservation;
- unsupported and animated inputs.

### Hashing

- deterministic lowercase MD5;
- fixed field order;
- source version, width, quality, and tenant changes alter the key.

### Cache

- miss then hit;
- hit updates atime;
- corrupt final file rejected;
- temp never served;
- atomic publication;
- source replacement invalidation;
- oversized candidate not cached.

### LRU

- oldest atime first;
- stable tie-breaker;
- cleanup reaches 80%;
- current/locked artifacts skipped;
- final usage never exceeds 1 GiB.

### Concurrency and authorization

- identical misses generate once;
- distinct keys may generate concurrently;
- failed workers release locks;
- unauthorized hit remains unauthorized;
- cross-tenant cache access denied.

### Integration

Exercise the real authenticated route, verify valid WebP bytes and dimensions, restart the application and reuse cache, and confirm no new public endpoint exists.
