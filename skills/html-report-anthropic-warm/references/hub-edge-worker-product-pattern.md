# Hub / Edge / Web / Worker Product Pattern

Use this reference when a product moves its source of truth from a desktop application to an always-on home/server Hub, while the desktop remains valuable for compute-heavy work and operational visibility.

## Role allocation

| Role | Owns | Must not own |
|---|---|---|
| Hub | catalog, media truth, job queue, API, auth, recovery | GPU-heavy analysis by necessity |
| Host-local Edge | capture buffers, device health, VAD/triggering, source sealing | independent catalog or user-facing truth |
| Web/PWA | timeline, search, corrections, settings | primary DB or background capture |
| Native TV | playback and lightweight confirmation | jobs, database, capture |
| Desktop Worker App | image/video analysis, transcode, local models, transparent operations panel | source-of-truth DB, direct SMB mutation, self-certified completion |
| Direct-attached sensor | raw audio/video input and hardware identity | network service or compute node unless it actually has one |

## Physical topology before logical architecture

Always establish the physical facts first:

- Where is each device physically located?
- Is a camera/microphone USB-attached to the Hub host, or is it a network node?
- Do Edge Runtime and Hub run on the same machine?
- Which arrows are USB/local process calls versus LAN/Internet traffic?

A direct-attached peripheral must not be drawn as an independent network box. Use a chain such as:

```text
USB camera/mic → host-local Edge Runtime → Hub services
```

If Edge and Hub are software roles on one host, put them inside the same host boundary or label them “same host, logical separation.” Do not draw parallel arrows that imply the peripheral uploads to the Hub over the network.

## Desktop Worker App

The desktop Worker has two product surfaces:

### Transparent operations

Show human-readable state, not raw logs:

- Hub connection latency/auth/version;
- host-local Edge and sensor health;
- Worker heartbeat and online/busy/degraded state;
- queue depth, active lease, progress, recent successes and last error;
- compute slots, CPU/GPU/memory/cache/network;
- pause accepting work, retry, cancel lease and clear cache controls.

### Heavy compute

Typical capabilities:

- video scene segmentation and activity windows;
- image understanding, OCR and quality scoring;
- keyframe/cover selection and similarity deduplication;
- HLS/proxy/thumbnail/audio transcode;
- private local-model execution;
- batch re-analysis after algorithm upgrades.

## Lease protocol

The Hub remains authoritative:

1. Worker registers version, capabilities and concurrency slots.
2. Worker sends heartbeats; Hub derives node status.
3. Worker claims a bounded lease carrying job ID, idempotency key and expiry.
4. Worker downloads only authorized source/rendition bytes through API/Range.
5. Work happens in a disposable local sandbox/cache.
6. Worker uploads temporary output with source digest, output hash, model/version, parameters and source-time mapping.
7. Hub validates and atomically creates the DerivedArtifact plus final job state.

Worker never writes Hub SQLite directly, modifies originals through SMB, or marks its own result accepted.

## Failure contract

- **Worker offline:** Hub/Edge/Web continue; leases expire and jobs requeue.
- **Late result:** old lease completion is rejected.
- **Duplicate result:** idempotency key and artifact hash prevent duplicates.
- **Worker crash:** temporary output is not truth; Hub keeps the job recoverable.
- **Cache pressure:** local cache is visible, bounded and disposable.
- **Version change:** new analysis creates a new artifact version; it never overwrites source/history.
- **Backpressure:** Worker claims only within declared slots; Hub may assign light versus heavy classes.

## HTML deliverable structure

A useful architecture HTML should include all of these, not just a generic box diagram:

1. Main Web/PWA user experience.
2. Native TV thin-client concept when relevant.
3. Physical + logical architecture with transport labels.
4. Capture/noise algorithm when the system records continuously.
5. Worker App mock: connection/nodes, queue/progress, compute/capabilities.
6. Worker lease/data flow and failure contract.
7. Data/file boundaries.
8. Dependency-ordered work packages and Gates.

## Verification checklist

- [ ] Direct-attached devices are not shown as network nodes.
- [ ] Same-host Edge and Hub are visibly marked as logical roles.
- [ ] Web is primary UI once Hub is the source of truth.
- [ ] Worker can be offline without stopping capture or history.
- [ ] Worker has no direct DB/original-media write path.
- [ ] Lease expiry, duplicate completion and late results are defined.
- [ ] Derived artifacts carry source digest + algorithm/model version.
- [ ] UI shows user-readable node and task state.
- [ ] Work-package numbering matches the project STATUS document.
- [ ] Browser visual check confirms arrows do not cross cards and every tab is reachable.
