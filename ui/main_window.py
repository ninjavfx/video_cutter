import os
import tempfile
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, QTimer, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from core.ffmpeg import probe_video, generate_thumbnails, export_segments_reencode, FFmpegError
from core.segment import SegmentsModel
from ui.video_widget import VideoPlayerWidget, format_timecode
from ui.timeline import TimelineWidget
from ui.segment_list import SegmentListWidget


class ExportWorker(QThread):
    """Background thread for video export."""

    progress = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, input_path: str, segments, output_path: str):
        super().__init__()
        self._input_path = input_path
        self._segments = segments
        self._output_path = output_path

    def run(self):
        try:
            export_segments_reencode(
                self._input_path,
                self._segments,
                self._output_path,
            )
            self.finished.emit()
        except FFmpegError as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Cutter")
        self.resize(1024, 768)

        self._current_file: Optional[str] = None
        self._segments_model = SegmentsModel()
        self._video_meta: dict = {}

        self._player = VideoPlayerWidget()
        self._timeline = TimelineWidget()
        self._segment_list = SegmentListWidget()
        self._status_label = QLabel("Open a video file to begin")

        self._export_worker: Optional[ExportWorker] = None

        self._setup_ui()
        self._setup_menu()
        self._setup_shortcuts()
        self._connect_signals()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Left column: player + timeline
        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        left_col.addWidget(self._player, 1)
        self._timeline.setMaximumHeight(160)
        left_col.addWidget(self._timeline, 0)

        main_layout.addLayout(left_col, 1)

        # Right column: segment list panel
        self._segment_list.setMinimumWidth(240)
        self._segment_list.setMaximumWidth(320)
        self._segment_list.setStyleSheet("background: #222; border-left: 1px solid #444;")
        main_layout.addWidget(self._segment_list, 0)

        # Status bar area (below everything via a separate approach)
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 4, 0, 0)
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()

        # We need to restructure: put status at bottom of left column
        left_col.addWidget(status_container, 0)

    def _setup_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")

        open_action = QAction("Open Video...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._open_video)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        export_action = QAction("Export Segments...", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._export_segments)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = menubar.addMenu("Edit")

        clear_action = QAction("Clear All Segments", self)
        clear_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        clear_action.triggered.connect(self._clear_segments)
        edit_menu.addAction(clear_action)

    def _setup_shortcuts(self):
        # Space: play/pause
        space_act = QAction(self)
        space_act.setShortcut(QKeySequence(Qt.Key_Space))
        space_act.triggered.connect(self._toggle_play_pause)
        self.addAction(space_act)

        # Enter: mark in/out points
        enter_act = QAction(self)
        enter_act.setShortcut(QKeySequence(Qt.Key_Return))
        enter_act.triggered.connect(self._mark_point)
        self.addAction(enter_act)

        # Also handle Enter from numpad
        enter2_act = QAction(self)
        enter2_act.setShortcut(QKeySequence(Qt.Key_Enter))
        enter2_act.triggered.connect(self._mark_point)
        self.addAction(enter2_act)

        # Left/Right: seek +/- 5 seconds
        left_act = QAction(self)
        left_act.setShortcut(QKeySequence(Qt.Key_Left))
        left_act.triggered.connect(lambda: self._seek_delta(-5))
        self.addAction(left_act)

        right_act = QAction(self)
        right_act.setShortcut(QKeySequence(Qt.Key_Right))
        right_act.triggered.connect(lambda: self._seek_delta(5))
        self.addAction(right_act)

        # Escape: clear pending IN point
        esc_act = QAction(self)
        esc_act.setShortcut(QKeySequence(Qt.Key_Escape))
        esc_act.triggered.connect(self._clear_pending)
        self.addAction(esc_act)

        # Frame stepping: , and . keys
        step_back_act = QAction(self)
        step_back_act.setShortcut(QKeySequence(Qt.Key_Comma))
        step_back_act.triggered.connect(self._player.step_backward)
        self.addAction(step_back_act)

        step_fwd_act = QAction(self)
        step_fwd_act.setShortcut(QKeySequence(Qt.Key_Period))
        step_fwd_act.triggered.connect(self._player.step_forward)
        self.addAction(step_fwd_act)

    def _connect_signals(self):
        self._player.play_requested.connect(self._on_play)
        self._player.pause_requested.connect(self._on_pause)
        self._player.seek_requested.connect(self._on_seek)
        self._timeline.seek_requested.connect(self._on_seek)
        self._segment_list.seek_requested.connect(self._on_seek)
        self._segment_list.delete_requested.connect(self._delete_segment)

    # --- File operations ---

    def _open_video(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            "",
            "Video Files (*.mp4 *.mov *.avi *.mkv *.mpg *.mpeg *.webm);;All Files (*)",
        )
        if not filepath:
            return

        try:
            meta = probe_video(filepath)
            self._current_file = filepath
            self._video_meta = meta
            self._segments_model.clear_all()

            # Load into player
            self._player.load_video(filepath)
            self._player.set_frame_rate(meta.get("fps", 30))

            # Generate thumbnails
            self._status_label.setText("Generating thumbnails...")
            QApplication.processEvents()

            thumb_dir = tempfile.mkdtemp(prefix="vcut_thumbs_")
            interval = max(1.0, meta["duration"] / 300)  # ~300 thumbs max
            thumbs = generate_thumbnails(filepath, thumb_dir, interval=interval)

            self._timeline.set_thumbnails(thumbs, interval=interval)
            self._timeline.set_duration(meta["duration"])
            self._timeline.update_segments([])

            # Pass thumbnail pixmaps to segment list for lookup
            from PySide6.QtGui import QPixmap
            pixmaps = [QPixmap(p) for p in thumbs if not QPixmap(p).isNull()]
            self._segment_list.set_thumbnails(pixmaps)
            self._segment_list.set_duration(meta["duration"])
            self._segment_list.update_segments([])

            self.setWindowTitle(f"Video Cutter - {os.path.basename(filepath)}")
            self._status_label.setText(
                f"Loaded: {meta['width']}x{meta['height']}  "
                f"{format_timecode(meta['duration'])}  "
                f"Codec: {meta['codec']}"
            )

        except FFmpegError as e:
            QMessageBox.critical(self, "Error", f"Failed to load video:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error:\n{e}")

    def _export_segments(self):
        segments = self._segments_model.segments
        if not segments:
            QMessageBox.information(
                self, "No Segments", "Mark some segments first (press ENTER to set IN/OUT points)."
            )
            return

        if self._segments_model.has_pending_in:
            QMessageBox.warning(
                self,
                "Incomplete Segment",
                "You have a pending IN point. Press ENTER again to complete it, or ESC to discard.",
            )
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Video",
            os.path.join(os.getcwd(), "export.mp4"),
            "MP4 Video (*.mp4);;MKV Video (*.mkv)",
        )
        if not output_path:
            return

        self._status_label.setText("Exporting... please wait")
        self._player.pause()

        self._export_worker = ExportWorker(
            self._current_file, segments, output_path
        )
        self._export_worker.finished.connect(self._on_export_done)
        self._export_worker.error.connect(self._on_export_error)
        self._export_worker.start()

    def _on_export_done(self):
        self._status_label.setText("Export complete!")
        QMessageBox.information(
            self, "Done", f"Video exported successfully:\n{self._export_worker._output_path}"
        )

    def _on_export_error(self, error_msg: str):
        self._status_label.setText("Export failed")
        QMessageBox.critical(self, "Export Error", f"Failed to export:\n{error_msg}")

    # --- Playback controls ---

    def _toggle_play_pause(self):
        if self._player.is_playing():
            self._on_pause()
        else:
            self._on_play()

    def _on_play(self):
        self._player.play()

    def _on_pause(self):
        self._player.pause()

    @Slot(float)
    def _on_seek(self, seconds: float):
        if not self._current_file:
            return
        self._player.seek(seconds)

    def _seek_delta(self, delta: float):
        current = self._player.current_position()
        new_pos = max(0.0, current + delta)
        self._on_seek(new_pos)

    # --- Segment marking ---

    def _mark_point(self):
        if not self._current_file:
            return

        current_time = self._player.current_position()

        if self._segments_model.has_pending_in:
            # Mark OUT point
            self._segments_model.set_out_point(current_time)
            segs = self._segments_model.segments
            self._timeline.update_segments(segs)
            self._segment_list.update_segments(segs)
            self._timeline.set_pending_in(None)
            self._status_label.setText(
                f"Segment marked: {format_timecode(self._segments_model.pending_in_time or 0)} -> "
                f"{format_timecode(current_time)}  "
                f"({len(self._segments_model.segments)} total)"
            )
        else:
            # Mark IN point
            self._segments_model.set_in_point(current_time)
            self._timeline.set_pending_in(current_time)
            self._status_label.setText(
                f"IN point set at {format_timecode(current_time)}. "
                f"Scrub forward and press ENTER for OUT."
            )

    def _clear_pending(self):
        if self._segments_model.has_pending_in:
            self._segments_model.clear_pending()
            self._timeline.set_pending_in(None)
            self._status_label.setText("Pending IN point cleared")

    def _delete_segment(self, index: int):
        self._segments_model.remove_segment(index)
        segs = self._segments_model.segments
        self._timeline.update_segments(segs)
        self._segment_list.update_segments(segs)
        self._status_label.setText(f"Segment deleted. {len(segs)} remaining.")

    def _clear_segments(self):
        self._segments_model.clear_all()
        self._timeline.update_segments([])
        self._segment_list.update_segments([])
        self._timeline.set_pending_in(None)
        self._status_label.setText("All segments cleared")
