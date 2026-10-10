# TASKS.md — Video Cutter

## Done (MVP + v1)

- [x] Project structure with venv + requirements.txt
- [x] Segment data model (`core/segment.py`)
- [x] ffmpeg wrappers: probe, thumbnails, export (`core/ffmpeg.py`)
- [x] Video player widget with transport controls (`ui/video_widget.py`)
- [x] Thumbnail timeline strip with segment overlays (`ui/timeline.py`)
- [x] Main window layout, menus, keyboard shortcuts (`ui/main_window.py`)
- [x] Entry point wiring everything together (`main.py`)
- [x] Background export via QThread
- [x] Handle videos without audio streams (fixed `has_audio_stream` check)
- [x] Segment list panel with thumbnails, seek on click, DEL button (`ui/segment_list.py`)
- [x] Frame-by-frame stepping: buttons `<|` / `|>` + keyboard `,` / `.`
- [x] Two-column layout: player+timeline left, segment list right
- [x] Live playhead with automatic timeline follow
- [x] Drag-to-reorder segments before export
- [x] Async thumbnail generation with temporary-file cleanup
- [x] Export progress bar and worker error reporting

## Known Issues / Bugs

No known MVP-blocking issues. Manual GUI testing is still recommended for each supported platform and multimedia backend.

## Next Priority (MVP+)

### 1. Export cancellation
- Allow canceling an in-progress ffmpeg export safely.

### 2. Incremental thumbnails
- Populate the timeline in batches and show thumbnail-generation progress.

## Future Features

- [ ] Segment preview — play only the selected segment loop
- [ ] Trim within segments — adjust IN/OUT points after marking by dragging edges on timeline
- [ ] Multiple video files — load more than one source, pick segments from different clips
- [ ] Export format options — codec selection, quality presets, resolution scaling
- [ ] Undo/redo for segment operations
- [ ] Zoom timeline — show more/fewer thumbnails per screen width
- [ ] Save/load project files with segment markers
