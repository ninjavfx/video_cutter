# DECISIONS.md — Video Cutter

## Tech Stack: Python + PySide6 (Qt 6)

**Why:** Native desktop experience with built-in multimedia support via QMediaPlayer. Similar to vidcutter's approach. Avoids Electron overhead and Tauri complexity for video integration.

**Trade-off:** Requires shipping Python runtime or bundling with PyInstaller for distribution.

## Platform: macOS + Linux

**Why:** User's primary platform is macOS, plus Linux support requested. Both have good Qt multimedia backend support (VLC/ffmpeg plugins). Windows not in MVP scope but would work with same codebase.

## ffmpeg as External Process (NOT pyav or Qt-only)

**Decision:** All video operations use subprocess calls to system ffmpeg/ffprobe rather than Python bindings.

**Why:**
- System ffmpeg is already installed and supports all codecs
- No binary compatibility issues across platforms
- Easier to debug — can copy-paste commands into terminal
- pyav has known issues with Qt integration on macOS

**Trade-off:** Slightly slower due to process spawning overhead, but negligible for this use case.

## Export Strategy: Re-encode (NOT stream copy)

**Decision:** `export_segments_reencode()` using ffmpeg complex filter graph with trim+concat is the primary export path. The older `export_segments()` (stream-copy concat demuxer approach) exists as fallback.

**Why:** Stream copy (`-c copy`) can produce artifacts at cut points due to keyframe alignment issues. Re-encoding guarantees clean cuts and consistent output format.

**Trade-off:** Slower for large files, but produces reliable results.

## Audio Handling: Conditional Processing

**Decision:** Check `has_audio_stream()` before building audio filters in the export command. Videos without audio skip audio processing entirely.

**Why:** Discovered during testing — `[0:a]` stream specifier fails with "matches no streams" error on silent videos. This is a common edge case (AI-generated clips, screen recordings).

## Segment Marking: IN/OUT Toggle Pattern

**Decision:** Single Enter key toggles between setting IN point and OUT point. Pending IN shown as red line on timeline. Completed segments shown as blue bars.

**Why:** Matches vidcutter's workflow — minimal clicks, keyboard-driven. Status bar provides clear feedback about current state.

## Timeline: Thumbnail Strip (NOT waveform or scrub-only)

**Decision:** Generate actual frame thumbnails at ~1fps interval, displayed horizontally with scroll support.

**Why:** Visual context is essential for finding cut points. Waveform alone isn't enough for visual content. Pure seek slider lacks spatial overview.

**Trade-off:** Thumbnail generation takes time and disk space (temp directory). Capped at ~300 thumbnails max by adjusting interval based on video duration.

## UI Framework: Custom PaintEvent for Timeline

**Decision:** `TimelineStrip` uses QPainter in paintEvent() rather than a QListView or QGraphicsView.

**Why:** Full control over rendering, segment overlays, and scroll behavior. Simpler architecture for this specific use case.

**Trade-off:** No built-in item selection or drag-and-drop support — would need to be implemented manually if added later.

## Threading: QThread for Export Only

**Decision:** Export runs in a background `ExportWorker(QThread)`. Thumbnail generation and video probing run on the main thread (known limitation).

**Why:** Export is the longest-running operation (minutes for large files). Thumbnails typically complete within seconds. Main-thread thumbnail gen was accepted as MVP trade-off.

## Layout: Two-Column (Player Left, Segment List Right)

**Decision:** Horizontal split layout — video player and timeline on left (stretch), segment list panel fixed 240-320px on right with dark background.

**Why:** Keeps the primary workspace (video + timeline) prominent while giving quick access to segment management without obscuring content. Matches vidcutter's general layout philosophy.

## Frame Stepping: Actual Frame Duration from Video FPS

**Decision:** Step size is calculated from video frame rate (`1000 / fps` ms), not a fixed value. Set via `set_frame_rate()` when loading a video.

**Why:** Videos have varying frame rates (24, 30, 60 fps). Stepping by actual frame duration gives precise control regardless of source material.
