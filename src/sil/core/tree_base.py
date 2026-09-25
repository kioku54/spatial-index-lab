"""
Base class cho các index dạng cây (R-tree, STRtree, ...)
"""

from __future__ import annotations

import heapq
import itertools
from typing import Iterator, Protocol

from sil.geometric import Envelope, Point
from sil.base import Item, Neighbor, Region, SpatialIndex


class TreeNode(Protocol):
    """Node tối thiểu mà TreeIndex cần để duyệt cây"""
    level: int
    children: list
    envelope: Envelope

    @property
    def is_leaf(self) -> bool: ...


class TreeIndex(SpatialIndex):
    """
    Index dạng cây: root là TreeNode, mỗi node có children (node con hoặc Item) và envelope.
    Cung cấp query / nearest / regions dùng chung
    """

    root: TreeNode | None = None

    def _query(self, search: Envelope) -> list[Item]:
        """Tìm mọi đối tượng có intersect với 1 vùng input"""
        s = self.stats
        out: list[Item] = []
        if self.root is None:
            return out

        s.envelope_tests += 1
        if not self.root.envelope.is_intersects(search):
            return out

        stack = [self.root]
        while stack:
            node = stack.pop()
            s.nodes_visited += 1
            for child in node.children:
                s.envelope_tests += 1
                if node.is_leaf:
                    s.items_checked += 1
                if not child.envelope.is_intersects(search):
                    continue                      # CẮT TỈA: bỏ nguyên cây con
                if node.is_leaf:
                    out.append(child)
                else:
                    stack.append(child)
        return out

    def _nearest(self, point: Point, k: int) -> list[Neighbor]:
        """Best-first search theo min_distance tới envelope của node/item"""
        s = self.stats
        if self.root is None:
            return []

        tie = itertools.count()  # heapq không so sánh được Node/Item khi khoảng cách bằng nhau
        s.envelope_tests += 1
        heap = [(self.root.envelope.min_distance_point(point), next(tie), self.root)]
        result: list[Neighbor] = []

        while heap and len(result) < k:
            dist, _, entry = heapq.heappop(heap)
            if isinstance(entry, Item):
                result.append(Neighbor(dist, entry))
                continue
            s.nodes_visited += 1
            for child in entry.children:
                s.envelope_tests += 1
                if entry.is_leaf:
                    s.items_checked += 1
                d = child.envelope.min_distance_point(point)
                heapq.heappush(heap, (d, next(tie), child))
        return result

    def regions(self) -> Iterator[Region]:
        """Duyệt toàn bộ cây, trả ra Region (envelope + level) của từng node, kể cả leaf"""
        stack = [self.root] if self.root else []
        while stack:
            node = stack.pop()
            yield Region(node.envelope, node.level)
            if not node.is_leaf:
                stack.extend(node.children)
