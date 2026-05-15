# Session — 2026-05-15: MVP Build

## What Was Built

Greenfield project. Created complete MVP video cutter application from scratch in a single session.

### Files Created (8)
- `main.py` — app entry point with Fusion style
- `requirements.txt` — PySide6>=6.6.0
- `core/__init__.py`, `ui/__init__.py` — package markers
- `core/segment.py` — Segment dataclass + SegmentsModel (IN/OUT state machine)
- `core/ffmpeg.py` — probe_video, generate_thumbnails, export_segments_reencode, has_audio_stream
- `ui/video_widget.py` — VideoPlayerWidget wrapping QMediaPlayer + TransportControls with seek slider
- `ui/timeline.py` — TimelineStrip (custom paintEvent thumbnails) + TimelineWidget (scroll bar wrapper)
- `ui/main_window.py` — MainWindow with ExportWorker thread, menu bar, keyboard shortcuts

### Files Created (docs)
- `AGENTS.md`, `TASKS.md`, `DECISIONS.md`, `CODEX.md`

## Bugs Fixed During Session

1. **`Qt.Url` doesn't exist in PySide6 6.6+** → Changed to `QUrl.fromLocalFile()` in video_widget.py:125
2. **Missing `_on_scroll` method on TimelineWidget** → Added handler at timeline.py:186-188
3. **Export crashes on videos without audio** (`[0:a] matches no streams`) → Added `has_audio_stream()` check, conditionally builds audio filter graph in export_segments_reencode()

## User Decisions Made

- Tech stack: Python + PySide6 (recommended option)
- MVP scope: Core only — load video, mark segments with Enter, export
- Platforms: macOS + Linux (not Windows for now)

---

# Session — 2026-05-15: Segment List Panel + Frame Stepping

## What Was Added

### `ui/segment_list.py` — New File (~175 lines)
- `SegmentItemWidget`: individual segment row with thumbnail, timecodes (MM:SS.ms), duration, DEL button
- `SegmentListWidget`: scrollable container with header, vertical scrollbar, empty state message
- Thumbnails sourced from timeline's cached pixmaps (closest frame to segment IN point)
- Signals: `seek_requested(float)`, `delete_requested(int)`

### Layout Change in `main_window.py`
- Changed from single-column vertical layout to two-column horizontal layout
- Left column (stretch): video player + timeline strip
- Right column (240-320px fixed): segment list panel with dark background
- Status bar moved below left column

### Frame-by-Frame Stepping in `video_widget.py`
- Removed unused `step_forward`/`step_backward` signals
- Added `set_frame_rate(fps)` to calculate step size from video FPS
- Added `step_forward()` / `step_backward()` methods that seek by ±1 frame duration
- Wired `<|` and `|>` buttons directly to these methods

### Keyboard Shortcuts in `main_window.py`
- `,` (comma) → step backward 1 frame
- `.` (period) → step forward 1 frame

### Signal Wiring
- Segment list click → `_on_seek()` → player seeks to segment IN point
- Segment list DEL → `_delete_segment(index)` → removes from model, refreshes timeline + list
- On video load: passes thumbnail pixmaps and duration to segment list for lookup

## What's Working Now

Everything from MVP plus:
- Segment list panel with thumbnails, timecodes, delete
- Click-to-seek on any segment in the list
- Frame-by-frame stepping via buttons or keyboard (`, ` / `.`)
- Two-column layout with proper sizing
