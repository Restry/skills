# Optional Narrated Presentation & Audio Pipeline

Use this reference when a project extends its written Product Walkthrough into an **audio-driven Narrated Presentation** or needs **staged release cutoffs**.

> For interactive review annotations and stakeholder comment threads, use the separate `live-page-feedback` skill on the running application rather than adding a second feedback system to static screenshots.

---

## 1. Narrated Presentation Player

The presentation consumes the **exact same frozen manifest and ordered screenshots** as the written Walkthrough—never maintain a second divergent step list.

### Playback & Timeline Contract
- **Real media clock**: Advance slides on `audio.ended`, never on hardcoded timers or estimated reading speeds.
- **Synchronized captions**: Drive active subtitle cues from `audio.currentTime` against word-aligned cue bounds.
- **Race-safe async playback**: Track a monotonic play-request token so a cancelled or rejected earlier `audio.play()` promise cannot pause or override a newly selected slide.
- **Tab visibility & gesture safety**: Pause cleanly when `document.visibilityState === 'hidden'` and respect browser autoplay gesture policies without leaving the UI falsely stuck in "Playing".
- **Keyboard isolation**: Global shortcuts (`Space` play/pause, `←`/`→` prev/next) must ignore events originating inside native `<button>`, `<input>`, `<textarea>`, `<summary>`, or open `<dialog>` elements.
- **Outline sync**: Keep the "All steps" panel open by default on desktop and scroll only the outline container to keep the current step visible.

---

## 2. TTS Audition, Synthesis & Alignment Gates

When generating narration audio for presentation steps:

1. **Audition First**
   - Synthesize **one real step** with the target provider, voice, and pace.
   - Verify actual browser playback and wait for stakeholder sign-off before running a full batch.
   - A regeneration request must hit the TTS engine fresh—never pass off a cached old file as a new audition.

2. **Measure Actual Audio (Never Trust Container Headers Alone)**
   - Streaming WAV headers often report placeholder/unlimited frame counts. Compute true duration from raw PCM bytes (`byteLength / (sampleRate * channels * sampleWidth)`) and rewrite clean headers before MP3/AAC encoding.
   - Measure peak and RMS amplitude; reject silent, severely quiet, clipped, or unexpectedly long clips before activation.

3. **Align Fresh Speech, Never Stretch Old Subtitles**
   - Run local word-level alignment (e.g., `faster-whisper`) against the newly synthesized audio and map timestamps back to the approved script sentences—always display the **approved script text**, not raw ASR spelling.
   - Disable aggressive VAD/initial prompts if they clip opening sentences; verify both the **first sentence** and **final word** align.
   - **Independent numeric gate**: High overall word coverage must not mask wrong numbers or currencies (e.g., *"40 euros"* vs *"45 euros"*). Normalize spoken numbers (`num2words` / decimal parsing) and check every figure independently.

4. **Atomic Staging & Rollback**
   - Generate serially and resumable with profile-aware content hashes (`sha256(script + voice + pace + model)`).
   - Validate 100% of clips (decode, hashes, durations, coverage, numeric checks, cue bounds) before switching the active manifest.
   - Retain previous audio and backup manifests so rollback is an instant manifest swap without re-synthesis.

---

## 3. Reversible Release Boundaries

When a project delivers in phases and later chapters are not ready for customer preview:

- Configure a release cutoff (e.g., `releaseBoundary: { maxChapter: 5 }`) in the walkthrough manifest—never delete later steps or change their status to `unimplemented`.
- **Written Walkthrough**: Grey out and disable locked top tabs and outline entries; store locked chapter HTML inside inert `<template>` elements (not CSS `display: none`) so locked content cannot leak via filters, search, or keyboard tabbing.
- **Narrated Presentation**: Derive `visibleSteps` from `releaseBoundary` while keeping full narration generation on `allSteps`. Guard deep-link hashes (`#step-48`) so out-of-range links safely clamp or redirect to the last permitted step.
- **Honest framing**: Treat a release boundary as a **UI presentation boundary**, not an authentication or security control.
