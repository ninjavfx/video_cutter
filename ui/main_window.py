import os
import shutil
import tempfile
from typing import Optional

from PySide6.QtCore import QSettings, Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QProgressBar, QVBoxLayout, QWidget

from core.ffmpeg import export_segments, export_segments_reencode, generate_thumbnails, probe_video
from core.segment import SegmentsModel
from ui.segment_list import SegmentListWidget
from ui.timeline import TimelineWidget
from ui.video_widget import VideoPlayerWidget, format_timecode


class ExportWorker(QThread):
    progress = Signal(float)
    completed = Signal()
    error = Signal(str)

    def __init__(self, input_path: str, segments, output_path: str, fast_export: bool):
        super().__init__()
        self._input_path = input_path
        self._segments = list(segments)
        self._output_path = output_path
        self._fast_export = fast_export

    def run(self):
        try:
            export = export_segments if self._fast_export else export_segments_reencode
            export(self._input_path, self._segments, self._output_path, self.progress.emit)
            self.completed.emit()
        except Exception as error:
            self.error.emit(str(error))


class ThumbnailWorker(QThread):
    completed = Signal(int, list, str)
    error = Signal(int, str, str)

    def __init__(self, request_id: int, filepath: str, output_dir: str, interval: float):
        super().__init__()
        self._request_id = request_id
        self._filepath = filepath
        self._output_dir = output_dir
        self._interval = interval

    def run(self):
        try:
            paths = generate_thumbnails(self._filepath, self._output_dir, self._interval)
            self.completed.emit(self._request_id, paths, self._output_dir)
        except Exception as error:
            self.error.emit(self._request_id, str(error), self._output_dir)


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
        self._export_progress = QProgressBar()
        self._export_progress.setRange(0, 100)
        self._export_progress.setVisible(False)
        self._export_worker: Optional[ExportWorker] = None
        self._thumbnail_workers: dict[int, ThumbnailWorker] = {}
        self._thumbnail_request_id = 0
        self._timeline_thumbnail_request = 0
        self._thumbnail_dir: Optional[str] = None
        self._settings = QSettings("Video Cutter", "Video Cutter")
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
        left_col = QVBoxLayout()
        left_col.setSpacing(6)
        left_col.addWidget(self._player, 1)
        self._timeline.setMaximumHeight(160)
        left_col.addWidget(self._timeline)
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 4, 0, 0)
        status_layout.addWidget(self._status_label, 1)
        status_layout.addWidget(self._export_progress)
        left_col.addWidget(status_container)
        main_layout.addLayout(left_col, 1)
        self._segment_list.setMinimumWidth(240)
        self._segment_list.setMaximumWidth(320)
        self._segment_list.setStyleSheet("background: #222; border-left: 1px solid #444;")
        main_layout.addWidget(self._segment_list)

    def _setup_menu(self):
        file_menu = self.menuBar().addMenu("File")
        open_action = QAction("Open Video...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._open_video)
        file_menu.addAction(open_action)
        export_action = QAction("Export Segments...", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._export_segments)
        file_menu.addAction(export_action)
        self._fast_export_action = QAction("Fast export (skip re-encoding)", self)
        self._fast_export_action.setCheckable(True)
        self._fast_export_action.setChecked(self._settings.value("fast_export", False, type=bool))
        self._fast_export_action.setToolTip("Faster, but cuts may start or end on nearby keyframes.")
        self._fast_export_action.toggled.connect(self._save_fast_export_setting)
        file_menu.addAction(self._fast_export_action)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        edit_menu = self.menuBar().addMenu("Edit")
        clear_action = QAction("Clear All Segments", self)
        clear_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        clear_action.triggered.connect(self._clear_segments)
        edit_menu.addAction(clear_action)

    @Slot(bool)
    def _save_fast_export_setting(self, enabled: bool):
        self._settings.setValue("fast_export", enabled)

    def _setup_shortcuts(self):
        bindings = [
            (Qt.Key_Space, self._toggle_play_pause),
            (Qt.Key_Return, self._mark_point),
            (Qt.Key_Enter, self._mark_point),
            (Qt.Key_Left, lambda: self._seek_delta(-5)),
            (Qt.Key_Right, lambda: self._seek_delta(5)),
            (Qt.Key_Escape, self._clear_pending),
            (Qt.Key_Comma, self._player.step_backward),
            (Qt.Key_Period, self._player.step_forward),
        ]
        for key, handler in bindings:
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(handler)
            self.addAction(action)

    def _connect_signals(self):
        self._player.play_requested.connect(self._player.play)
        self._player.pause_requested.connect(self._player.pause)
        self._player.seek_requested.connect(self._on_seek)
        self._player.position_changed.connect(self._timeline.set_playhead_position)
        self._timeline.seek_requested.connect(self._on_seek)
        self._timeline.thumbnails_loaded.connect(self._on_timeline_thumbnails_loaded)
        self._segment_list.seek_requested.connect(self._on_seek)
        self._segment_list.delete_requested.connect(self._delete_segment)
        self._segment_list.reorder_requested.connect(self._reorder_segments)

    def _open_video(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Open Video", "", "Video Files (*.mp4 *.mov *.avi *.mkv *.mpg *.mpeg *.webm);;All Files (*)")
        if not filepath:
            return
        try:
            meta = probe_video(filepath)
        except Exception as error:
            QMessageBox.critical(self, "Error", f"Failed to load video:\n{error}")
            return
        self._current_file = filepath
        self._video_meta = meta
        self._segments_model.clear_all()
        self._cleanup_thumbnail_dir()
        self._player.load_video(filepath)
        self._player.set_frame_rate(meta.get("fps", 30))
        self._timeline.set_duration(meta["duration"])
        self._timeline.set_thumbnails([])
        self._timeline.update_segments([])
        self._timeline.set_playhead_position(0.0)
        self._segment_list.set_thumbnails([])
        self._segment_list.set_duration(meta["duration"])
        self._segment_list.update_segments([])
        self.setWindowTitle(f"Video Cutter - {os.path.basename(filepath)}")
        self._status_label.setText("Generating thumbnails in background...")
        thumb_dir = tempfile.mkdtemp(prefix="vcut_thumbs_")
        interval = max(1.0, meta["duration"] / 300)
        self._thumbnail_request_id += 1
        request_id = self._thumbnail_request_id
        worker = ThumbnailWorker(request_id, filepath, thumb_dir, interval)
        worker.completed.connect(self._on_thumbnails_ready)
        worker.error.connect(self._on_thumbnail_error)
        self._thumbnail_workers[request_id] = worker
        worker.start()

    @Slot(int, list, str)
    def _on_thumbnails_ready(self, request_id: int, paths: list, output_dir: str):
        self._thumbnail_workers.pop(request_id, None)
        if request_id != self._thumbnail_request_id:
            shutil.rmtree(output_dir, ignore_errors=True)
            return
        self._cleanup_thumbnail_dir()
        self._thumbnail_dir = output_dir
        interval = max(1.0, self._video_meta["duration"] / 300)
        self._timeline_thumbnail_request = request_id
        self._timeline.set_thumbnails(paths, interval)
        self._status_label.setText("Loading thumbnail preview...")

    @Slot(list)
    def _on_timeline_thumbnails_loaded(self, pixmaps: list):
        if self._timeline_thumbnail_request != self._thumbnail_request_id:
            return
        self._segment_list.set_thumbnails(pixmaps)
        self._segment_list.update_segments(self._segments_model.segments)
        self._status_label.setText(
            f"Loaded: {self._video_meta['width']}x{self._video_meta['height']}  "
            f"{format_timecode(self._video_meta['duration'])}  "
            f"Codec: {self._video_meta['codec']}"
        )

    @Slot(int, str, str)
    def _on_thumbnail_error(self, request_id: int, error: str, output_dir: str):
        self._thumbnail_workers.pop(request_id, None)
        shutil.rmtree(output_dir, ignore_errors=True)
        if request_id == self._thumbnail_request_id:
            self._status_label.setText("Loaded video, but thumbnail generation failed")
            QMessageBox.warning(self, "Thumbnail Error", f"Could not generate thumbnails:\n{error}")

    def _cleanup_thumbnail_dir(self):
        if self._thumbnail_dir:
            shutil.rmtree(self._thumbnail_dir, ignore_errors=True)
            self._thumbnail_dir = None

    def _export_segments(self):
        if self._export_worker and self._export_worker.isRunning():
            QMessageBox.information(self, "Export in Progress", "Wait for the current export to finish.")
            return
        segments = self._segments_model.segments
        if not segments:
            QMessageBox.information(self, "No Segments", "Mark some segments first (press ENTER to set IN/OUT points).")
            return
        if self._segments_model.has_pending_in:
            QMessageBox.warning(self, "Incomplete Segment", "You have a pending IN point. Press ENTER again to complete it, or ESC to discard.")
            return
        output_path, _ = QFileDialog.getSaveFileName(self, "Export Video", os.path.join(os.getcwd(), "export.mp4"), "MP4 Video (*.mp4);;MKV Video (*.mkv)")
        if not output_path:
            return
        fast_export = self._fast_export_action.isChecked()
        self._status_label.setText("Fast exporting..." if fast_export else "Exporting...")
        self._export_progress.setValue(0)
        self._export_progress.setVisible(True)
        self._player.pause()
        self._export_worker = ExportWorker(self._current_file, segments, output_path, fast_export)
        self._export_worker.completed.connect(self._on_export_done)
        self._export_worker.error.connect(self._on_export_error)
        self._export_worker.progress.connect(self._on_export_progress)
        self._export_worker.start()

    def _on_export_done(self):
        output_path = self._export_worker._output_path
        self._export_progress.setVisible(False)
        self._status_label.setText("Export complete!")
        QMessageBox.information(self, "Done", f"Video exported successfully:\n{output_path}")

    def _on_export_error(self, error_msg: str):
        self._export_progress.setVisible(False)
        self._status_label.setText("Export failed")
        QMessageBox.critical(self, "Export Error", f"Failed to export:\n{error_msg}")

    @Slot(float)
    def _on_export_progress(self, progress: float):
        self._export_progress.setValue(round(progress * 100))

    def _toggle_play_pause(self):
        self._player.pause() if self._player.is_playing() else self._player.play()

    @Slot(float)
    def _on_seek(self, seconds: float):
        if self._current_file:
            self._player.seek(seconds)

    def _seek_delta(self, delta: float):
        self._on_seek(min(self._player.duration(), max(0.0, self._player.current_position() + delta)))

    def _mark_point(self):
        if not self._current_file:
            return
        current_time = self._player.current_position()
        if self._segments_model.has_pending_in:
            in_time = self._segments_model.pending_in_time
            if not self._segments_model.set_out_point(current_time):
                self._status_label.setText("OUT point must be after the IN point.")
                return
            segments = self._segments_model.segments
            self._timeline.update_segments(segments)
            self._segment_list.update_segments(segments)
            self._timeline.set_pending_in(None)
            self._status_label.setText(f"Segment marked: {format_timecode(in_time or 0)} → {format_timecode(current_time)} ({len(segments)} total)")
            return
        self._segments_model.set_in_point(current_time)
        self._timeline.set_pending_in(current_time)
        self._status_label.setText(f"IN point set at {format_timecode(current_time)}. Scrub forward and press ENTER for OUT.")

    def _clear_pending(self):
        if self._segments_model.has_pending_in:
            self._segments_model.clear_pending()
            self._timeline.set_pending_in(None)
            self._status_label.setText("Pending IN point cleared")

    def _delete_segment(self, index: int):
        self._segments_model.remove_segment(index)
        self._timeline.update_segments(self._segments_model.segments)
        self._segment_list.update_segments(self._segments_model.segments)
        self._status_label.setText(f"Segment deleted. {len(self._segments_model.segments)} remaining.")

    def _reorder_segments(self, from_index: int, to_index: int):
        self._segments_model.move_segment(from_index, to_index)
        self._timeline.update_segments(self._segments_model.segments)
        self._segment_list.update_segments(self._segments_model.segments)
        self._status_label.setText("Segment order updated.")

    def _clear_segments(self):
        self._segments_model.clear_all()
        self._timeline.update_segments([])
        self._segment_list.update_segments([])
        self._timeline.set_pending_in(None)
        self._status_label.setText("All segments cleared")
