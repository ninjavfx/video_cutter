from PySide6.QtCore import Qt, Signal, Slot, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class TransportControls(QWidget):
    position_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._duration = 0.0
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.time_current = QLabel("00:00:00")
        self.time_current.setMinimumWidth(70)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setValue(0)
        self.seek_slider.sliderMoved.connect(self._on_seek)

        self.time_total = QLabel("00:00:00")
        self.time_total.setMinimumWidth(70)
        self.time_total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(self.time_current, 0)
        layout.addWidget(self.seek_slider, 1)
        layout.addWidget(self.time_total, 0)

    def set_duration(self, duration_ms: int):
        self._duration = duration_ms / 1000.0
        self.seek_slider.setRange(0, max(duration_ms, 1))
        self.time_total.setText(format_timecode(self._duration))

    def set_position(self, position_ms: int):
        pos = position_ms / 1000.0
        self.seek_slider.setValue(position_ms)
        self.time_current.setText(format_timecode(pos))

    @Slot(int)
    def _on_seek(self, value: int):
        self.position_changed.emit(value / 1000.0)


class VideoPlayerWidget(QWidget):
    """Video display with transport controls."""

    play_requested = Signal()
    pause_requested = Signal()
    seek_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)
        self._video_widget = QVideoWidget()
        self._player.setVideoOutput(self._video_widget)

        self._frame_duration_ms = 33  # default ~30fps

        self._transport = TransportControls()
        self._transport.position_changed.connect(self._on_seek)

        self._play_btn = QPushButton("Play")
        self._play_btn.setFixedWidth(60)
        self._play_btn.clicked.connect(self._on_play_click)

        self._step_back_btn = QPushButton("<|")
        self._step_back_btn.setFixedWidth(32)
        self._step_back_btn.setToolTip("Step backward 1 frame (,)")
        self._step_back_btn.clicked.connect(self.step_backward)

        self._step_fwd_btn = QPushButton("|>")
        self._step_fwd_btn.setFixedWidth(32)
        self._step_fwd_btn.setToolTip("Step forward 1 frame (.)")
        self._step_fwd_btn.clicked.connect(self.step_forward)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)

        # Video area with fixed aspect ratio placeholder
        video_container = QWidget()
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.addWidget(self._video_widget)
        self._video_widget.adjustSize()

        main_layout.addWidget(video_container, 1)

        # Controls row
        controls_layout = QHBoxLayout()
        controls_layout.addStretch()
        controls_layout.addWidget(self._step_back_btn)
        controls_layout.addWidget(self._play_btn)
        controls_layout.addWidget(self._step_fwd_btn)
        controls_layout.addStretch()

        main_layout.addLayout(controls_layout)
        main_layout.addWidget(self._transport)

    def _connect_signals(self):
        self._player.positionChanged.connect(self._transport.set_position)
        self._player.durationChanged.connect(self._transport.set_duration)

    def load_video(self, filepath: str):
        self._player.setSource(QUrl.fromLocalFile(filepath))
        # Don't auto-play on load

    @Slot()
    def _on_play_click(self):
        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self.pause_requested.emit()
        else:
            self.play_requested.emit()

    def play(self):
        self._player.play()
        self._play_btn.setText("Pause")

    def pause(self):
        self._player.pause()
        self._play_btn.setText("Play")

    def stop(self):
        self._player.stop()
        self._play_btn.setText("Play")

    @Slot(float)
    def _on_seek(self, seconds: float):
        self.seek_requested.emit(seconds)

    def seek(self, seconds: float):
        self._player.setPosition(int(seconds * 1000))

    def current_position(self) -> float:
        return self._player.position() / 1000.0

    def duration(self) -> float:
        return self._player.duration() / 1000.0

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlayingState

    def set_frame_rate(self, fps: float):
        """Set frame rate for frame-by-frame stepping."""
        if fps > 0:
            self._frame_duration_ms = int(1000 / fps)

    def step_forward(self):
        """Step forward one frame."""
        current = self._player.position()
        new_pos = min(current + self._frame_duration_ms, self._player.duration())
        self._player.setPosition(new_pos)

    def step_backward(self):
        """Step backward one frame."""
        current = self._player.position()
        new_pos = max(current - self._frame_duration_ms, 0)
        self._player.setPosition(new_pos)


def format_timecode(seconds: float) -> str:
    """Format seconds as HH:MM:SS timecode."""
    total_secs = int(seconds)
    hours = total_secs // 3600
    minutes = (total_secs % 3600) // 60
    secs = total_secs % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
