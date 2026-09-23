"""
STRtree - Sort-Tile-Recursive R-tree
"""

from __future__ import annotations
 
import heapq
import itertools
import math
from dataclasses import dataclass, field
from typing import Iterator, Union

from sil.geometric import Envelope, Point
from sil.base import Item, Neighbor, Region, SpatialIndex

@dataclass
class Node:
    level: int
    children: list
    envelope: Envelope = field(init=False)

    def __post_init__(self):
        self.envelope = Envelope.union_all(c.envelope for c in self.children)
    
    @property
    def is_leaf(self) -> bool:
        return self.level == 0

Entry = Union[Node, Item]

class STRtree(SpatialIndex):
    """"""

    def __init__(self, items=(), node_capacity: int = 10):
        if node_capacity < 2:
            raise ValueError("node_capacity phải >= 2")
        self.M = node_capacity
        self.root: Node | None = None
        super().__init__(items)

    def _build(self, items: list[Item]) -> None:
        """
        Build STRtree từ list items input
        Cơ chế:
            - Xây dựng từ đáy lên (đi từ Items)
            - Items --pack-> Node/Leaf (L0) --pack-> Node (L1) --pack-> ... --> root
        """
        if not items:
            return
        
        level = 0
        nodes = self._pack(items, level)
        while len(nodes) > 1:
            level += 1
            nodes = self._pack(nodes, level)

        self.root = nodes[0]

    def _pack(self, entries: list[Entry], level: int) -> list[Node]:
        """
        Core Algorithm:
        
        Nhận vào danh sách entries và level cần xử lý, xử lý và trả về danh sách Node:
            - Entries có thể là Item (level 0) hoặc Node (level cao hơn).
            - Thực hiện gom nhóm Item/Node (gần nhau theo không gian) vào các Nodes mới (Mỗi Node có node_capacity phần tử)
            - Thực hiện đệ quy liên tục cho đến khi chỉ còn một Node được gọi là Root
        
        """
        M = self.M
        n = len(entries)
        P = math.ceil(n / M)
        S = math.ceil(math.sqrt(P))
        slice_size = S * M

        # B1: Sắp theo X rồi cắt lát dọc
        by_x = sorted(entries, key=lambda e: e.envelope.center.x)

        nodes: list[Node] = []
        for i in range(0, n, slice_size):
            vertical_slice = by_x[i : i + slice_size]

            # B2: sắp xếp theo tâm Y trong lát dọc, chia thành các nhóm M entry liên tiếp
            by_y = sorted(vertical_slice, key=lambda e: e.envelope.center.y)  # B2

            # B3: chia thành các nhóm M entry liên tiếp -> mỗi nhóm một node
            for j in range(0, len(by_y), M):
                nodes.append(Node(level, by_y[j : j + M]))
        return nodes

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
        "Tìm k đối tượng (Item, Distance) gần với điểm input nhất. Xắp xếp từ gần đến xa"
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

