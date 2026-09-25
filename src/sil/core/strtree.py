"""
STRtree - Sort-Tile-Recursive R-tree
"""

from __future__ import annotations
 
import math
from dataclasses import dataclass, field
from typing import Union

from sil.geometric import Envelope
from sil.base import Item
from sil.core.tree_base import TreeIndex

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

class STRtree(TreeIndex):
    """
    STRtree - Sort-Tile-Recursive (Static index):
        - Build: 1 lần từ dưới lên: sắp theo X -> cắt lát dọc -> sắp theo Y -> gom M entry thành node
        - Insert/Delete: không hỗ trợ, muốn thay đổi dữ liệu phải build lại
    """

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
