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

## Known Issues / Bugs

- **Thumbnails block main thread** — `generate_thumbnails()` in `_open_video()` runs synchronously, freezing UI for large files. Should move to a worker thread with progress signal.
- **No export progress feedback** — `ExportWorker.progress` signal exists but isn't wired up; status label just says "Exporting... please wait"
- **Timeline playhead not live-updated** — the red IN marker draws, but there's no moving playhead that follows playback position during video play

## Next Priority (MVP+)

### 1. Live Playhead on Timeline
- Track `QMediaPlayer.positionChanged` signal
- Draw a vertical playhead line on the timeline strip that updates during playback
- Requires calling `timeline.update()` periodically or using a QTimer

### 2. Drag-to-Reorder Segments
- Implement drag-and-drop in `SegmentListWidget` to reorder segments before export
- Update `SegmentsModel._segments` list order accordingly

### 3. Async Thumbnail Generation
- Move `generate_thumbnails()` to a QThread worker
- Show progress bar or spinner while generating
- Enable player controls immediately, populate timeline as thumbnails arrive in batches

### 4. Export Progress Bar
- Parse ffmpeg output for time/percentage info
- Wire `ExportWorker.progress` signal to a QProgressBar
- Allow canceling export mid-process (terminate subprocess)

## Future Features

- [ ] Segment preview — play only the selected segment loop
- [ ] Trim within segments — adjust IN/OUT points after marking by dragging edges on timeline
- [ ] Multiple video files — load more than one source, pick segments from different clips
- [ ] Export format options — codec selection, quality presets, resolution scaling
- [ ] Undo/redo for segment operations
- [ ] Zoom timeline — show more/fewer thumbnails per screen width
- [ ] Save/load project files with segment markers
