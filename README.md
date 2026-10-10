# Video Cutter

A keyboard-friendly desktop video cutter for macOS and Linux. Load a video, mark the parts you want to keep, reorder them, and export them as one clean MP4 or MKV.

Video Cutter is built with Python, PySide6, and the system `ffmpeg` tools. Exports are re-encoded so cuts are accurate rather than limited to source keyframes.

## Features

- Mark IN and OUT points with `Enter`
- Review segments in a thumbnail list, seek to a segment, delete it, or drag to reorder it
- Frame-step with `,` and `.`
- Browse a thumbnail timeline with a live, auto-following playhead
- Export one combined video, including videos with no audio stream
- Generate thumbnails and export video without freezing the application window
- Show export progress

## Requirements

- Python 3.10 or newer
- [ffmpeg](https://ffmpeg.org/) and `ffprobe` available on your `PATH`
- PySide6 6.6 or newer

On macOS, install ffmpeg with Homebrew:

```bash
brew install ffmpeg
```

## Install and run

```bash
git clone https://github.com/YOUR-USERNAME/video-cutter.git
cd video-cutter
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Usage

1. Choose **File → Open Video**.
2. Seek to the start of a clip and press `Enter` to set its IN point.
3. Seek to the end and press `Enter` again to add the segment.
4. Repeat for each clip. Drag segments in the right panel to set their export order.
5. Choose **File → Export Segments** or press `Ctrl+E`.

The source file is never modified.

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Space` | Play / pause |
| `Enter` | Set IN point / complete segment |
| `Escape` | Clear pending IN point |
| `Left` / `Right` | Seek 5 seconds backward / forward |
| `,` / `.` | Step one frame backward / forward |
| `Ctrl+E` | Export segments |
| `Ctrl+Shift+C` | Clear all segments |

## Project layout

```text
main.py              Application entry point
core/segment.py      Segment model and ordering operations
core/ffmpeg.py       ffprobe, thumbnails, and export helpers
ui/video_widget.py   Qt media player and transport controls
ui/timeline.py       Thumbnail timeline, overlays, and playhead
ui/segment_list.py   Scrollable, reorderable segment list
ui/main_window.py    Application orchestration and worker threads
```

## Development notes

- Thumbnail files are generated in the operating system temporary directory and cleaned up when another video is opened.
- ffmpeg runs outside the UI thread for thumbnail generation and export.
- The project currently has no automated test suite. At minimum, run `python3 -m compileall -q .` before submitting changes.

## License

Add a license before publishing if you want others to use, modify, or distribute this project under defined terms.
