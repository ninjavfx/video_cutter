import os
from typing import List, Optional

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QSize
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPixmap,
    QPen,
    QFont,
    QImageReader,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollBar,
    QVBoxLayout,
    QWidget,
)

from core.segment import Segment


class TimelineStrip(QWidget):
    """Horizontal thumbnail strip with segment markers."""

    seek_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thumbnails: List[str] = []  # file paths
        self._pixmaps: List[QPixmap] = []
        self._segments: List[Segment] = []
        self._video_duration: float = 0.0
        self._pending_in: Optional[float] = None
        self._thumb_interval: float = 1.0
        self._scroll_offset: int = 0

        self._strip_height = 120
        self._margin = 2

    def set_thumbnails(self, paths: List[str], interval: float = 1.0):
        """Load thumbnail images."""
        self._thumbnails = paths
        self._thumb_interval = interval
        self._pixmaps.clear()
        for path in paths:
            pm = QPixmap(path)
            if not pm.isNull():
                self._pixmaps.append(pm)
        self.update_segments()

    def set_duration(self, duration: float):
        self._video_duration = duration

    def set_pending_in(self, time: Optional[float]):
        self._pending_in = time
        self.update()

    def update_segments(self, segments: Optional[List[Segment]] = None):
        if segments is not None:
            self._segments = segments
        self.update()

    def _time_to_x(self, time: float) -> float:
        """Map video time to x coordinate in the strip."""
        if not self._pixmaps or self._video_duration <= 0:
            return 0.0
        total_thumbs = len(self._pixmaps)
        total_width = total_thumbs * (self._pixmaps[0].width() + self._margin)
        fraction = time / self._video_duration
        return fraction * total_width

    def _x_to_time(self, x: float) -> float:
        """Map x coordinate to video time."""
        if not self._pixmaps or self._video_duration <= 0:
            return 0.0
        total_thumbs = len(self._pixmaps)
        total_width = total_thumbs * (self._pixmaps[0].width() + self._margin)
        fraction = x / total_width
        return fraction * self._video_duration

    def set_size_hint(self):
        if self._pixmaps:
            tw = self._pixmaps[0].width() + self._margin
            th = self._pixmaps[0].height()
            total_w = len(self._pixmaps) * tw
            self.setMinimumHeight(th + 40)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._pixmaps:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        thumb_w = self._pixmaps[0].width() + self._margin
        start_idx = max(0, self._scroll_offset)
        visible_width = self.width()

        x = 0.0
        for i in range(start_idx, len(self._pixmaps)):
            if x > visible_width:
                break
            painter.drawPixmap(int(x), 2, self._pixmaps[i])
            x += thumb_w

        # Draw segment overlays
        overlay_height = 16
        overlay_y = self.height() - overlay_height - 4

        for idx, seg in enumerate(self._segments):
            x1 = self._time_to_x(seg.in_time) - (self._scroll_offset * thumb_w)
            x2 = self._time_to_x(seg.out_time) - (self._scroll_offset * thumb_w)

            color = QColor(0, 170, 255, 140)
            painter.fillRect(int(x1), overlay_y, int(x2 - x1), overlay_height, color)

            # Segment label
            if (x2 - x1) > 30:
                painter.setPen(QColor(Qt.white))
                font = QFont("Arial", 9)
                painter.setFont(font)
                cx = (x1 + x2) / 2
                cy = overlay_y + overlay_height / 2 + 4
                painter.drawText(int(cx), int(cy), Qt.AlignCenter, f"S{idx + 1}")

        # Draw pending IN marker
        if self._pending_in is not None:
            in_x = self._time_to_x(self._pending_in) - (self._scroll_offset * thumb_w)
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.drawLine(int(in_x), 0, int(in_x), overlay_y)

        # Draw current playhead position indicator area
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._pixmaps:
            thumb_w = self._pixmaps[0].width() + self._margin
            click_x = event.position().x() + (self._scroll_offset * thumb_w)
            time = self._x_to_time(click_x)
            time = max(0.0, min(time, self._video_duration))
            self.seek_requested.emit(time)

    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        if angle > 0:
            self._scroll_offset = max(0, self._scroll_offset - 3)
        else:
            self._scroll_offset = min(
                len(self._pixmaps) - 1, self._scroll_offset + 3
            )
        self.update()


class TimelineWidget(QWidget):
    """Timeline with scroll bar and info label."""

    seek_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._strip = TimelineStrip()
        self._strip.seek_requested.connect(self.seek_requested.emit)

        self._scroll_bar = QScrollBar(Qt.Horizontal)
        self._scroll_bar.valueChanged.connect(self._on_scroll)

        self._info_label = QLabel("No video loaded")
        self._info_label.setStyleSheet("padding: 2px 8px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.addWidget(self._strip)
        controls = QHBoxLayout()
        controls.addWidget(self._info_label, 1)
        controls.addWidget(self._scroll_bar)
        layout.addLayout(controls)

    def set_thumbnails(self, paths: List[str], interval: float = 1.0):
        self._strip.set_thumbnails(paths, interval)
        self._update_scroll_range()

    def _on_scroll(self, value: int):
        self._strip._scroll_offset = value
        self._strip.update()

    def _update_scroll_range(self):
        max_val = max(0, len(self._strip._pixmaps) - 5)
        self._scroll_bar.setRange(0, max_val)

    def set_duration(self, duration: float):
        self._strip.set_duration(duration)

    def update_segments(self, segments: List[Segment]):
        self._strip.update_segments(segments)
        total = sum(s.duration for s in segments)
        self._info_label.setText(
            f"Segments: {len(segments)}  |  Total: {total:.1f}s"
        )

    def set_pending_in(self, time):
        self._strip.set_pending_in(time)
