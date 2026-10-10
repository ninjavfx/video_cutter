from typing import List

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal, QSize
from PySide6.QtGui import QDrag, QFont, QMouseEvent, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from core.segment import Segment


class SegmentItemWidget(QWidget):
    seek_requested = Signal(float)
    delete_requested = Signal(int)
    drag_requested = Signal(int)

    def __init__(self, index: int, segment: Segment, thumb_pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._index = index
        self._segment = segment
        self._thumb = thumb_pixmap.scaled(120, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._drag_start: QPoint | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(6)
        thumb_label = QLabel()
        thumb_label.setPixmap(self._thumb)
        thumb_label.setFixedSize(120, 68)
        thumb_label.setStyleSheet("border: 1px solid #555; background: #1a1a1a;")
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        label = QLabel(f"S{self._index + 1}")
        label.setFont(QFont("Arial", 10, QFont.Bold))
        time_label = QLabel(f"{format_tc(self._segment.in_time)} → {format_tc(self._segment.out_time)}")
        time_label.setStyleSheet("color: #aaa;")
        duration_label = QLabel(f"Duration: {self._segment.duration:.2f}s")
        duration_label.setStyleSheet("color: #888; font-size: 10px;")
        info_layout.addWidget(label)
        info_layout.addWidget(time_label)
        info_layout.addWidget(duration_label)
        info_layout.addStretch()
        delete_button = QPushButton("DEL")
        delete_button.setFixedWidth(42)
        delete_button.setStyleSheet(
            "QPushButton { background: #c0392b; color: white; border: none; "
            "border-radius: 3px; padding: 4px 8px; font-weight: bold; } "
            "QPushButton:hover { background: #e74c3c; }"
        )
        delete_button.clicked.connect(lambda: self.delete_requested.emit(self._index))
        layout.addWidget(thumb_label)
        layout.addLayout(info_layout, 1)
        layout.addWidget(delete_button)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.position().toPoint()
            self.seek_requested.emit(self._segment.in_time)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_start and event.buttons() & Qt.LeftButton:
            if (event.position().toPoint() - self._drag_start).manhattanLength() >= 10:
                self.drag_requested.emit(self._index)
                self._drag_start = None
        super().mouseMoveEvent(event)


def format_tc(seconds: float) -> str:
    total_secs = int(seconds)
    minutes = total_secs // 60
    secs = total_secs % 60
    centiseconds = int((seconds - total_secs) * 100)
    return f"{minutes:02d}:{secs:02d}.{centiseconds:02d}"


class SegmentListView(QListWidget):
    reorder_requested = Signal(int, int)
    _mime_type = "application/x-video-cutter-segment"

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(self._mime_type):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(self._mime_type):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat(self._mime_type):
            source = int(bytes(event.mimeData().data(self._mime_type)).decode())
            target = self.indexAt(event.position().toPoint()).row()
            if target < 0:
                target = self.count() - 1
            if source != target:
                self.reorder_requested.emit(source, target)
            event.acceptProposedAction()
            return
        super().dropEvent(event)


class SegmentListWidget(QWidget):
    """Scrollable, drag-reorderable list of selected segments."""

    seek_requested = Signal(float)
    delete_requested = Signal(int)
    reorder_requested = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._segments: List[Segment] = []
        self._all_thumbs: List[QPixmap] = []
        self._video_duration = 0.0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QLabel("Segments — drag to reorder")
        header.setFont(QFont("Arial", 11, QFont.Bold))
        header.setStyleSheet("padding: 6px 8px;")
        layout.addWidget(header)
        self._list = SegmentListView()
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._list.setAcceptDrops(True)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.reorder_requested.connect(self.reorder_requested)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list, 1)
        self._empty_label = QLabel("No segments yet.\nPress ENTER to mark IN/OUT points.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #666; padding: 20px;")
        layout.addWidget(self._empty_label)

    def set_thumbnails(self, pixmaps: List[QPixmap]):
        self._all_thumbs = pixmaps

    def set_duration(self, duration: float):
        self._video_duration = duration

    def _get_thumb_for_time(self, time: float) -> QPixmap:
        if not self._all_thumbs or self._video_duration <= 0:
            return QPixmap()
        index = int((time / self._video_duration) * len(self._all_thumbs))
        return self._all_thumbs[max(0, min(index, len(self._all_thumbs) - 1))]

    def update_segments(self, segments: List[Segment]):
        self._segments = list(segments)
        self._list.clear()
        for index, segment in enumerate(self._segments):
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 76))
            self._list.addItem(item)
            widget = SegmentItemWidget(index, segment, self._get_thumb_for_time(segment.in_time))
            widget.seek_requested.connect(self.seek_requested)
            widget.delete_requested.connect(self._handle_delete)
            widget.drag_requested.connect(self._start_drag)
            self._list.setItemWidget(item, widget)
        self._empty_label.setVisible(not self._segments)

    def _handle_delete(self, index: int):
        if 0 <= index < len(self._segments):
            self.delete_requested.emit(index)

    def _on_item_clicked(self, item: QListWidgetItem):
        index = self._list.row(item)
        if 0 <= index < len(self._segments):
            self.seek_requested.emit(self._segments[index].in_time)

    def _start_drag(self, index: int):
        drag = QDrag(self._list)
        mime = QMimeData()
        mime.setData(SegmentListView._mime_type, str(index).encode())
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)
