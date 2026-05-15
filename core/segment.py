from dataclasses import dataclass, field
from typing import List


@dataclass
class Segment:
    in_time: float = 0.0
    out_time: float = 0.0

    @property
    def duration(self) -> float:
        return self.out_time - self.in_time


class SegmentsModel:
    def __init__(self):
        self._segments: List[Segment] = []
        self._pending_in: float | None = None

    @property
    def segments(self) -> List[Segment]:
        return self._segments

    @property
    def has_pending_in(self) -> bool:
        return self._pending_in is not None

    @property
    def pending_in_time(self) -> float | None:
        return self._pending_in

    def set_in_point(self, time: float):
        self._pending_in = time

    def set_out_point(self, time: float):
        if self._pending_in is not None and time > self._pending_in:
            seg = Segment(in_time=self._pending_in, out_time=time)
            self._segments.append(seg)
            self._pending_in = None

    def clear_pending(self):
        self._pending_in = None

    def remove_segment(self, index: int):
        if 0 <= index < len(self._segments):
            self._segments.pop(index)

    def clear_all(self):
        self._segments.clear()
        self._pending_in = None

    def get_total_duration(self) -> float:
        return sum(s.duration for s in self._segments)
