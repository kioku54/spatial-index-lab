from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, Iterable, Iterator, TypeVar

from sil.geometric import Envelope, Point


T = TypeVar("T")

@dataclass(frozen=True, slots=True)
class Item(Generic[T]):
    """Một đối tượng khi được đánh chỉ mục không gian"""
    envelope: Envelope
    value: T

    @classmethod
    def point(cls, x: float, y: float, value: T) -> Item[T]:
        return cls(Envelope(x, y, x, y), value)


@dataclass(frozen=True, slots=True)
class Neighbor(Generic[T]):
    """Thông tin của nearest neighbor"""
    distance: float
    item: Item[T]


@dataclass(frozen=True, slots=True)
class Region(Generic[T]):
    """Khu vực mà index tạo ra"""
    envelope: Envelope
    level: int = 0

@dataclass
class QueryStats:
    """
    Metric thống kê:
        - nodes_visited : số node/ô/bucket đã mở ra xem
        - envelope_tests: số lần gọi intersects()/min_distance() lên node HOẶC item
        - items_checked : số item ở tầng lá đã được xem xét
    """
    nodes_visited: int = 0
    envelope_tests: int = 0
    items_checked: int = 0
    

# ===============================================
# Spatial Index
# ===============================================
class SpatialIndex(ABC, Generic[T]):
    """
    Base Class cho Spatial Index
    """

    def __init__(self, items: Iterable[Item[T]] = ()):
        self.stats = QueryStats()
        self._size = 0

        items = list(items)

        self._build(items)
        self._size = len(items)

    # ===============================================
    # Public
    # ===============================================
    
    def query(self, envelope: Envelope) -> list[Item[T]]:
        """
        Trả ra mọi Item có envelope GIAO với envelope tìm kiếm
        """
        self.stats = QueryStats()
        return self._query(envelope)

    def nearest(self, point: Point, k: int = 1) -> list[Neighbor[T]]:
        """
        Trả ra k đối tượng (Item, Distance) gần với điểm input nhất. Xắp xếp từ gần đến xa"
        """
        if k < 1:
            raise ValueError("k phải >= 1")
        self.stats = QueryStats()
        result = self._nearest(point, k)
        return sorted(result, key=lambda n: n.distance)[:k]

    def regions(self) -> Iterator[Region]:
        """
        Trả ra Region (envelope + level) của từng Node, kể cả leaf
        """
        return iter(())
    
    # ===============================================
    # Abstract
    # ===============================================

    @abstractmethod
    def _build(self, items: list[Item[T]]) -> None: ...
    
    @abstractmethod
    def _query(self, envelope: Envelope) -> list[Item[T]]: ...

    @abstractmethod
    def _nearest(self, point: Point, k: int) -> list[Neighbor[T]]: ...

    # ===============================================
    # Other
    # ===============================================
    @property
    def name(self) -> str:
        return type(self).__name__

    def __len__(self) -> int:
        return self._size

    def __repr__(self) -> str:
        return f"<{self.name} size={len(self)}>"