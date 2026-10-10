# CODEX.md — Video Cutter Project Context

## What This Is

A desktop video cutting application (similar to vidcutter) built with Python + PySide6 + ffmpeg. Load a movie, mark IN/OUT points by pressing Enter while scrubbing or playing, then export the selected segments as a single file.

## How to Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install PySide6
python main.py
```

Requires: Python 3.10+, ffmpeg installed on system PATH.

## File Map

| File | Purpose | Lines |
|---|---|---|
| `main.py` | Entry point, creates QApplication + MainWindow | ~20 |
| `core/segment.py` | Segment dataclass + SegmentsModel state machine | ~50 |
| `core/ffmpeg.py` | ffprobe probe, thumbnail gen, export via ffmpeg subprocess | ~240 |
| `ui/video_widget.py` | QMediaPlayer wrapper with transport controls (play/pause/seek/frame step) | ~185 |
| `ui/timeline.py` | Thumbnail strip widget with segment overlays + scroll bar | ~205 |
| `ui/segment_list.py` | Segment list panel: thumbnails, timecodes, seek on click, DEL button | ~175 |
| `ui/main_window.py` | QMainWindow: two-column layout, menus, shortcuts, export orchestration | ~340 |

## Current State (October 9, 2026)

MVP + v1 functional. Core workflow works end-to-end: open video → mark segments with Enter → see them in segment list panel on right → delete or seek to any segment → export to MP4. Frame-by-frame stepping available via buttons and `,`/`.` keys. Fixed audio-less video crash by adding `has_audio_stream()` check before building ffmpeg filter graph.

The timeline follows the live playhead, thumbnail generation runs in a worker thread, and segments can be reordered by drag and drop. Export progress is displayed while ffmpeg runs.

## Key Conventions

- Time values are always floats in seconds
- Use `QUrl.fromLocalFile(path)`, never `Qt.Url`
- All ffmpeg calls capture stderr and raise `FFmpegError` on failure
- No inline comments unless explaining non-obvious logic
- Qt signals use snake_case, slots decorated with `@Slot`
