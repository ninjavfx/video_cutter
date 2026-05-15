from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QSize, QRect
from PySide6.QtGui import QColor, QPainter, QPixmap, QFont, QMouseEvent
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollBar,
    QVBoxLayout,
    QWidget,
)

from core.segment import Segment


class SegmentItemWidget(QWidget):
    """Single segment row: thumbnail + timecodes + delete button."""

    seek_requested = Signal(float)
    delete_requested = Signal(int)

    def __init__(self, index: int, segment: Segment, thumb_pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._index = index
        self._segment = segment
        self._thumb = thumb_pixmap.scaled(120, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        self._hovered = False
        self._dragging = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(6)

        # Thumbnail
        thumb_label = QLabel()
        thumb_label.setPixmap(self._thumb)
        thumb_label.setMinimumSize(120, 68)
        thumb_label.setMaximumSize(120, 68)
        thumb_label.setStyleSheet("border: 1px solid #555; background: #1a1a1a;")

        # Info column
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        label = QLabel(f"S{self._index + 1}")
        label.setFont(QFont("Arial", 10, QFont.Bold))

        time_label = QLabel(
            f"{format_tc(self._segment.in_time)} → {format_tc(self._segment.out_time)}"
        )
        time_label.setStyleSheet("color: #aaa;")

        dur_label = QLabel(f"Duration: {self._segment.duration:.2f}s")
        dur_label.setStyleSheet("color: #888; font-size: 10px;")

        info_layout.addWidget(label)
        info_layout.addWidget(time_label)
        info_layout.addWidget(dur_label)
        info_layout.addStretch()

        layout.addWidget(thumb_label, 0)
        layout.addLayout(info_layout, 1)

        # Delete button
        del_btn = QPushButton("DEL")
        del_btn.setFixedWidth(42)
        del_btn.setStyleSheet("""
            QPushButton {
                background: #c0392b; color: white; border: none;
                border-radius: 3px; padding: 4px 8px; font-weight: bold;
            }
            QPushButton:hover { background: #e74c3c; }
        """)
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self._index))
        layout.addWidget(del_btn, 0)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and not self._dragging:
            self.seek_requested.emit(self._segment.in_time)

    def set_index(self, index: int):
        self._index = index


def format_tc(seconds: float) -> str:
    total_secs = int(seconds)
    mins = total_secs // 60
    secs = total_secs % 60
    ms = int((seconds - int(seconds)) * 100)
    return f"{mins:02d}:{secs:02d}.{ms:02d}"


class SegmentListWidget(QWidget):
    """Scrollable list of segments with drag-to-reorder support."""

    seek_requested = Signal(float)
    delete_requested = Signal(int)
    reorder_requested = Signal(int, int)  # from_index, to_index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[SegmentItemWidget] = []
        self._segments: List[Segment] = []
        self._all_thumbs: List[QPixmap] = []  # timeline thumbnails for lookup

        self._drag_start_index: Optional[int] = None
        self._drag_pos: Optional[float] = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel("Segments")
        header.setFont(QFont("Arial", 11, QFont.Bold))
        header.setStyleSheet("padding: 6px 8px;")
        layout.addWidget(header)

        self._scroll = QScrollBar(Qt.Vertical)
        scroll_layout = QHBoxLayout()
        scroll_layout.addStretch()
        scroll_layout.addWidget(self._scroll, 0)

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(4, 2, 4, 2)
        self._container_layout.setSpacing(2)
        self._container_layout.addStretch()

        # Scroll area
        self._scroll_area = QWidget()
        scroll_layout_inner = QVBoxLayout(self._scroll_area)
        scroll_layout_inner.setContentsMargins(0, 0, 0, 0)
        scroll_layout_inner.addWidget(self._container)

        layout.addWidget(self._scroll_area, 1)
        layout.addLayout(scroll_layout)

        self._empty_label = QLabel("No segments yet.\nPress ENTER to mark IN/OUT points.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #666; padding: 20px;")
        self._container_layout.insertWidget(0, self._empty_label)

    def set_thumbnails(self, pixmaps: List[QPixmap]):
        """Store timeline thumbnails for segment thumbnail lookup."""
        self._all_thumbs = pixmaps

    def _get_thumb_for_time(self, time: float) -> QPixmap:
        """Find the closest timeline thumbnail to a given time."""
        if not self._all_thumbs or not hasattr(self, '_video_duration') or self._video_duration <= 0:
            return QPixmap()
        idx = int((time / self._video_duration) * len(self._all_thumbs))
        idx = max(0, min(idx, len(self._all_thumbs) - 1))
        return self._all_thumbs[idx]

    def set_duration(self, duration: float):
        self._video_duration = duration

    def update_segments(self, segments: List[Segment]):
        self._segments = list(segments)
        # Remove old items (keep empty label and stretch)
        while len(self._items):
            item = self._items.pop()
            self._container_layout.removeWidget(item)
            item.deleteLater()

        self._empty_label.setVisible(len(segments) == 0)

        for i, seg in enumerate(segments):
            thumb = self._get_thumb_for_time(seg.in_time)
            item = SegmentItemWidget(i, seg, thumb)
            item.seek_requested.connect(self.seek_requested.emit)
            item.delete_requested.connect(self._handle_delete)
            item.setMouseTracking(True)
            self._items.append(item)
            # Insert before the stretch (which is at end)
            self._container_layout.insertWidget(
                self._container_layout.count() - 1, item
            )

        self._update_scroll_range()

    def _handle_delete(self, index: int):
        # Re-index in case segments shifted
        if 0 <= index < len(self._segments):
            self.delete_requested.emit(index)

    def _update_scroll_range(self):
        total_height = sum(item.height() for item in self._items) + len(self._items) * 2
        visible = self._scroll_area.height()
        max_val = max(0, total_height - visible)
        self._scroll.setRange(0, max_val)
        self._scroll.setPageStep(visible // 40)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scroll_range()
