# Adaptation Matrix

## Cross-language map

| Concern | Python | Node.js | Java | PHP |
|---|---|---|---|---|
| Interceptor hook | ASGI/WSGI middleware; Django protected media wrapper; Flask `before_request`; FastAPI/Starlette middleware | Express/Koa/Fastify middleware before static handler; Nest middleware/interceptor; existing route wrapper | Servlet `Filter`; Spring `OncePerRequestFilter`; resource-handler wrapper | PSR-15 middleware; Laravel middleware; Symfony request/response subscriber |
| Required ordering | After auth, before static response | After auth/session, before `express.static` equivalent | After security context, before resource commit | After auth, before binary/static response |
| Preferred image library | `pyvips`; Pillow baseline | `sharp` | Thumbnailator + WebP ImageIO plugin; libvips binding where supported | Imagick; GD only with verified WebP |
| MD5 | `hashlib.md5(...).hexdigest()` | `createHash("md5").update(...).digest("hex")` | `MessageDigest.getInstance("MD5")` | `md5($descriptor)` |
| Path safety | `Path.resolve`, `relative_to` | `path.resolve`, `realpath` | `Path.toRealPath`, `startsWith(root)` | `realpath` + prefix containment |
| Metadata | `os.stat`, `Path.stat` | `fs.promises.stat` | `Files.readAttributes` | `stat`, `filesize`, `fileatime` |
| Explicit atime | `os.utime(..., ns=(now, mtime))` | `fs.promises.utimes(path, now, mtime)` | `BasicFileAttributeView.setTimes(mtime, atime, null)` | `touch($path, filemtime($path), time())` |
| Temp file | `tempfile.NamedTemporaryFile(dir=shard)` | exclusive `wx` temp in shard | `Files.createTempFile(shard, ...)` | `tempnam($shard, ...)` |
| Atomic publish | `os.replace` | `fs.promises.rename` | `Files.move(..., ATOMIC_MOVE, REPLACE_EXISTING)` | same-filesystem `rename` |
| Locking | `fcntl.flock`; `portalocker` | `proper-lockfile` or native lock library | `FileChannel.lock` | `flock` |
| Directory scan | `os.scandir` | `fs.promises.opendir` | `Files.newDirectoryStream` | `FilesystemIterator` |
| File response | Framework file response / sendfile | `stream.pipeline(createReadStream, response)` | `Resource`, `StreamingResponseBody`, input stream | `BinaryFileResponse`, `response()->file`, `fpassthru` |
| Logging | stdlib logging / structlog | pino / Winston | SLF4J | Monolog |
| Metrics | Prometheus/OpenTelemetry | prom-client/OpenTelemetry | Micrometer/OpenTelemetry | Prometheus/OpenTelemetry |

## Python

Place middleware after authentication. Prefer wrapping the existing protected media view when generic middleware cannot safely replace a committed response.

Use `pyvips` for high concurrency and large images. Pillow baseline:

```python
from PIL import Image, ImageOps

with Image.open(source_path) as image:
    image = ImageOps.exif_transpose(image)
    image.thumbnail((target_width, target_height))
    image.save(temp_path, format="WEBP", quality=80, method=6, exif=b"")
```

Configure `Image.MAX_IMAGE_PIXELS` and bounded workers.

```python
cache_key = hashlib.md5(descriptor.encode("utf-8")).hexdigest()
info = os.stat(artifact, follow_symlinks=False)
os.utime(artifact, ns=(time.time_ns(), info.st_mtime_ns), follow_symlinks=False)
os.replace(temp_path, final_path)
```

Use `fcntl.flock` on Unix or `portalocker` for cross-platform operation.

## Node.js

Install after authentication and before the existing static middleware:

```text
authenticate → authorizeImage → imageInterceptor → existingStaticHandler
```

Use `sharp`:

```javascript
await sharp(sourcePath, { failOn: "error", limitInputPixels: MAX_PIXELS })
  .rotate()
  .resize({ width, height, fit, withoutEnlargement: true })
  .webp({ quality: 80 })
  .toFile(tempPath);
```

```javascript
const key = createHash("md5").update(descriptor, "utf8").digest("hex");
const info = await stat(artifact);
await utimes(artifact, new Date(), info.mtime);
await rename(tempPath, finalPath);
```

Do not perform synchronous scans or image work on the event loop. Stream cached files.

## Java

For Spring, use `OncePerRequestFilter` after the security context is populated, or wrap the existing `ResourceHttpRequestHandler`. Use bounded workers for expensive decoding.

Standard ImageIO does not guarantee WebP. Verify a writer at startup:

```java
if (!ImageIO.getImageWritersByFormatName("webp").hasNext()) {
    throw new IllegalStateException("WebP writer unavailable");
}
```

Use Thumbnailator with a maintained WebP ImageIO plugin, or a supported libvips binding.

```java
MessageDigest md5 = MessageDigest.getInstance("MD5");
String key = HexFormat.of().formatHex(md5.digest(descriptor.getBytes(UTF_8)));
BasicFileAttributes a = Files.readAttributes(path, BasicFileAttributes.class, NOFOLLOW_LINKS);
Files.getFileAttributeView(path, BasicFileAttributeView.class, NOFOLLOW_LINKS)
    .setTimes(a.lastModifiedTime(), FileTime.from(Instant.now()), null);
Files.move(temp, target, ATOMIC_MOVE, REPLACE_EXISTING);
```

Use `FileChannel.lock()` for generation and eviction locks.

## PHP

Use PSR-15 or framework middleware after authorization. If Nginx/Apache serves the original without entering PHP, route only the existing protected image path through the application; do not add a new public image endpoint.

Prefer Imagick:

```php
$image = new Imagick($sourcePath);
$image->autoOrient();
$image->setImageColorspace(Imagick::COLORSPACE_SRGB);
$image->thumbnailImage($width, 0, true, true);
$image->stripImage();
$image->setImageFormat('webp');
$image->setImageCompressionQuality(80);
$image->writeImage($tempPath);
$image->clear();
$image->destroy();
```

Verify GD WebP support before fallback use.

```php
$key = md5($descriptor);
$info = stat($artifact);
touch($artifact, $info['mtime'], time());
rename($tempPath, $finalPath);
```

Use `flock()` and release it in `finally`. PHP-FPM amplifies concurrent memory use, so enforce pixel limits and worker bounds.

## Internal boundaries

Implement equivalents of:

```text
EligibilityPolicy
AuthorizationAdapter
SourceResolver
TransformParameterParser
CanonicalDescriptorBuilder
CachePathResolver
CacheRepository
CacheQuotaManager
ImageTransformer
ResponseStreamer
```

These are internal code boundaries, not public HTTP APIs.
