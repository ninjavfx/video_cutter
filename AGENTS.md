# AGENTS.md — Video Cutter Project

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install PySide6
python main.py
```

**Prerequisites:** Python 3.10+, ffmpeg (homebrew: `brew install ffmpeg`), PySide6>=6.6.0

## Architecture Overview

```
main.py                    # Entry point, creates QApplication + MainWindow
├── core/
│   ├── segment.py         # Data model: Segment(in_time, out_time) + SegmentsModel
│   └── ffmpeg.py          # External process wrappers: probe, thumbnails, export
└── ui/
    ├── video_widget.py    # QMediaPlayer wrapper with transport controls
    ├── timeline.py        # Thumbnail strip widget with segment overlays
    ├── segment_list.py    # Segment list panel: thumbnails, seek, delete
    └── main_window.py     # QMainWindow: layout, menus, shortcuts, orchestration
```

## Key Components

### `core/segment.py` — Data Model
- `Segment`: dataclass with `in_time`, `out_time` (floats in seconds)
- `SegmentsModel`: manages list of segments + pending IN point state machine
  - `set_in_point(t)` → stores pending IN
  - `set_out_point(t)` → creates Segment from pending IN, clears pending
  - `has_pending_in` / `pending_in_time` for UI feedback
  - `remove_segment(index)`, `clear_all()`, `get_total_duration()`

### `core/ffmpeg.py` — External Process Wrappers
- `probe_video(path)`: ffprobe JSON output → dict with duration, width, height, fps, codec
- `generate_thumbnails(path, dir, interval)`: ffmpeg frame extraction → list of .jpg paths
- `has_audio_stream(path)`: checks for audio stream (critical: videos without audio must be handled separately)
- `export_segments_reencode(...)`: complex filter graph with trim+concat; conditionally includes audio processing based on `has_audio_stream()`
- All functions raise `FFmpegError` on failure

### `ui/video_widget.py` — Player
- `VideoPlayerWidget`: wraps QMediaPlayer + QAudioOutput + QVideoWidget
- Signals: `play_requested`, `pause_requested`, `seek_requested(seconds)`
- `TransportControls`: seek slider with timecode labels (current / total)
- Frame stepping: `step_forward()`, `step_backward()` using frame duration from video FPS
- Uses `QUrl.fromLocalFile()` for loading (NOT `Qt.Url`)

### `ui/timeline.py` — Thumbnail Strip
- `TimelineStrip`: custom paintEvent draws thumbnails horizontally, segment overlays (blue bars), pending IN marker (red line)
- Scrollable via mouse wheel or QScrollBar
- Click on strip → emits `seek_requested(time)`
- Time ↔ pixel mapping is proportional to video duration

### `ui/segment_list.py` — Segment List Panel
- `SegmentListWidget`: scrollable list of segment items with thumbnails, timecodes, duration, DEL button
- Thumbnails sourced from timeline thumbnail cache (closest frame to IN point)
- Click item → emits `seek_requested(in_time)`
- DEL button → emits `delete_requested(index)`
- `update_segments(segments)` rebuilds the entire list

### `ui/main_window.py` — Orchestration
- Two-column layout: player+timeline on left, segment list panel on right (240-320px wide)
- `ExportWorker(QThread)`: runs export in background, signals `finished` / `error(str)`
- Keyboard shortcuts: Space (play/pause), Enter (IN/OUT toggle), Left/Right (±5s seek), `,`/`.` (frame step), Escape (clear pending IN)
- Menu: File → Open Video, Export Segments, Quit; Edit → Clear All Segments

## Important Gotchas

1. **PySide6 URL API**: Use `QUrl.fromLocalFile(path)`, NOT `Qt.Url.fromLocalFile()` — the latter doesn't exist in PySide6 6.6+
2. **Audio-less videos**: ffmpeg complex filter `[0:a]` fails if no audio stream exists. Always check with `has_audio_stream()` before building audio filters
3. **Thumbnails are blocking**: `generate_thumbnails()` runs synchronously on main thread — for long videos this freezes the UI temporarily (known limitation)
4. **Export is async**: Uses QThread to avoid freezing UI during re-encoding
5. **macOS menu bar**: On macOS with Fusion style, Qt moves menus to system menu bar at top of screen

## Conventions

- No comments in code unless explaining non-obvious logic
- Time values are always floats in seconds throughout the codebase
- Qt signals use snake_case, slots use `@Slot` decorator where needed for type hints
- All ffmpeg subprocess calls capture stderr and raise FFmpegError on failure
