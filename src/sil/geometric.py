"""
Geometric data type cho spatial index: Point and Envelope
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, NamedTuple, Optional

EARTH_RADIUS_M = 6_371_000.0  # in meters

# ===============================================
# Point
# ===============================================
class Point(NamedTuple):
    x: float  # Longitude
    y: float  # Latitude

def euclidean(p: Point, q: Point) -> float:
    """
        Khoảng cách Euclidean.
        Tính khoảng cách giữa hai điểm trong không gian 2D.
        Công thức: sqrt((x2 - x1)² + (y2 - y1)²)
    """
    return math.hypot(p.x - q.x, p.y - q.y)

def haversine(p: Point, q: Point) -> float:
    """
        Khoảng cách Haversine.
        Tính khoảng cách giữa hai điểm trên bề mặt của một hình cầu (trái đất).
        Công thức: 2 * R * arcsin(sqrt(sin²((lat2 - lat1)/2) + cos(lat1) * cos(lat2) * sin²((lon2 - lon1)/2)))
    """
    lat1, lon1 = math.radians(p.y), math.radians(p.x)
    lat2, lon2 = math.radians(q.y), math.radians(q.x)
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    return EARTH_RADIUS_M * c

# ===============================================
# Envelope
# ===============================================

@dataclass(frozen=True, slots=True)
class Envelope:
    """
    Envelope - Bounding Box - MBR của một hay nhiều đối tượng không gian

        max_y ┌────────┐
              │   ╱╲   │
              │  ╱  ╲  │   ← Đối tượng không gian
              │ ╱____╲ │
        min_y └────────┘
            min_x       max_x

    """
    minx: float
    miny: float
    maxx: float
    maxy: float

    def __post_init__(self):
            if self.minx > self.maxx or self.miny > self.maxy:
                raise ValueError(f"Invalid Envelope: {self}")

    # ===============================================
    # Construction
    # ===============================================

    @classmethod
    def from_point(cls, p: Point) -> Envelope:
        """Tạo một Envelope từ một điểm duy nhất."""
        return cls(p.x, p.y, p.x, p.y)

    @classmethod
    def from_points(cls, points: Iterable[Point]) -> Envelope:
        """Tạo một Envelope từ một tập hợp các điểm."""
        pts = list(points)
        if not pts:
            raise ValueError("Need at least 1 point")
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        return cls(min(xs), min(ys), max(xs), max(ys))

    # ===============================================
    # Metrics
    # ===============================================

    @property
    def width(self) -> float:
        return self.maxx - self.minx

    @property
    def height(self) -> float:
        return self.maxy - self.miny

    @property
    def center(self) -> Point:
        return Point(
            (self.minx + self.maxx) / 2,
            (self.miny + self.maxy) / 2
        )

    def area(self) -> float:
        return self.width * self.height

    def margin(self) -> float:
        return 2 * (self.width + self.height)

    # ===============================================
    # Audit
    # ===============================================
    
    def is_contains_point(self, p: Point) -> bool:
        """
        Kiểm tra Envelope của đối tượng này có chứa điểm p input không.
        """
        return self.minx <= p.x <= self.maxx and self.miny <= p.y <= self.maxy

    def is_contains(self, other: Envelope) -> bool:
        """Kiểm tra Envelope của đối tượng này có chứa Envelope input không"""
        return (
            self.minx <= other.minx
            and self.miny <= other.miny
            and other.maxx <= self.maxx
            and other.maxy <= self.maxy
        )

    def is_intersects(self, other: Envelope) -> bool:
        """Kiểm tra Envelope của đối tượng này có giao Envelope input không"""
        return not (
            other.minx > self.maxx
            or other.maxx < self.minx
            or other.miny > self.maxy
            or other.maxy < self.miny
        )

    # ===============================================
    # Operations
    # ===============================================
    
    def union(self, other: Envelope) -> Envelope:
        """Hợp nhất Envelope của đối tượng này với Envelope input"""
        return Envelope(
            min(self.minx, other.minx),
            min(self.miny, other.miny),
            max(self.maxx, other.maxx),
            max(self.maxy, other.maxy),
        )

    @staticmethod
    def union_all(envs: Iterable[Envelope]) -> Envelope:
        """Hợp nhất tất cả Envelope trong Iterable"""
        it = iter(envs)
        try:
            result = next(it)
        except StopIteration:
            raise ValueError("Cần ít nhất 1 envelope") from None
        for e in it:
            result = result.union(e)
        return result

    def intersection(self, other: Envelope) -> Optional[Envelope]:
        """Trả về Envelope mới là phần giao nhau của Envelope của đối tượng này và Envelope input"""
        if not self.is_intersects(other):
            return None
        return Envelope(
            max(self.minx, other.minx),
            max(self.miny, other.miny),
            min(self.maxx, other.maxx),
            min(self.maxy, other.maxy),
        )

    def overlap_area(self, other: Envelope) -> float:
        """Tính diện tích giao nhau của Envelope của đối tượng này với Envelope input"""

        inter = self.intersection(other)
        return inter.area() if inter else 0.0

    def enlargement(self, other: Envelope) -> float:
        """Tính diện tích cần thiết để mở rộng Envelope của đối tượng này để bao phủ Envelope khác."""
        return self.union(other).area() - self.area()

    # ===============================================
    # Distance
    # ===============================================

    def min_distance(self, other: Envelope) -> float:
        """Khoảng cách tối thiểu từ Envelope của đối tượng này đến Envelope input"""
        dx = max(0.0, other.minx - self.maxx, self.minx - other.maxx)
        dy = max(0.0, other.miny - self.maxy, self.miny - other.maxy)
        return math.hypot(dx, dy)

    def min_distance_point(self, p: Point) -> float:
        """Khoảng cách tối thiểu từ Envelope của đối tượng này đến điểm input"""
        return self.min_distance(Envelope.from_point(p))
