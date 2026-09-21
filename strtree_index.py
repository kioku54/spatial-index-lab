"""
STRtree — Sort-Tile-Recursive R-tree
"""

from __future__ import annotations

import heapq
import itertools
import math
from dataclasses import dataclass, field
from typing import Any, Iterable


# ----------------------------------------------------------------------------
# 1. ENVELOPE
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Envelope:
    minx: float
    miny: float
    maxx: float
    maxy: float

    def __post_init__(self):
        if any(math.isnan(v) for v in (self.minx, self.miny, self.maxx, self.maxy)):
            raise ValueError("Envelope chứa NaN")
        if self.minx > self.maxx or self.miny > self.maxy:
            raise ValueError(f"Envelope không hợp lệ: {self}")

    @property
    def cx(self) -> float:
        return (self.minx + self.maxx) / 2

    @property
    def cy(self) -> float:
        return (self.miny + self.maxy) / 2

    def intersects(self, other: Envelope) -> bool:
        """
        Kiểm tra xem 2 envelope có giao nhau hay không.
        Hai envelope giao nhau nếu chúng có ít nhất 1 điểm chung.
        """
        return not (
            other.minx > self.maxx
            or other.maxx < self.minx
            or other.miny > self.maxy
            or other.maxy < self.miny
        )

    def union(self, other: Envelope) -> Envelope:
        """
        Trả về envelope bao ngoài hai envelope.
        """
        return Envelope(
            min(self.minx, other.minx),
            min(self.miny, other.miny),
            max(self.maxx, other.maxx),
            max(self.maxy, other.maxy),
        )
    
    @staticmethod
    def union_all(envs: Iterable[Envelope]) -> Envelope:
        """
        Trả về envelope bao ngoài tất cả các input envelope.
        """
        envs = iter(envs)
        result = next(envs)
        for e in envs:
            result = result.union(e)
        return result

    @staticmethod
    def distance(self, other: Envelope) -> float:
        """
        Khoảng cách ngắn nhất giữa 2 hình chữ nhật (0 nếu chúng giao nhau).
        """
        dx = max(0.0, other.minx - self.maxx, self.minx - other.maxx)
        dy = max(0.0, other.miny - self.maxy, self.miny - other.maxy)
        return math.hypot(dx, dy)

# ----------------------------------------------------------------------------
# 2. TREE: ITEM, NODE
#
#                  Node level 2  (root)
#                /             \
#        Node level 1        Node level 1
#        /        \          /        \
#   Node L0    Node L0    Node L0    Node L0      <- node lá
#   /  |  \     ...
# Item Item Item                                   <- dữ liệu thật
#
#    - ITEM : Một phần tử dữ liệu gốc (vd: một đối tượng không gian), có envelope và value.
#             Nằm dưới đáy, không chứa gì, và không được tính là một tầng của cây.
#
#    - NODE : Một node của cây, gom các con lại; envelope = hợp envelope của các con.
#        + Node lá   (level == 0): con là các Item.
#        + Node trong (level >= 1): con là các Node ở level - 1.
#        + Root: node ở level cao nhất, không có cha. Cây nhỏ (<= M item) chỉ có
#          1 node, vừa là lá vừa là root.
# ---------------------------------------------------------------------------
@dataclass
class Item:
    envelope: Envelope
    value: Any

@dataclass
class Node:
    level: int
    children: list[Node | Item]
    envelope: Envelope = field(init=False)

    def __post_init__(self):
        self.envelope = Envelope.union_all(
            child.envelope for child in self.children
        )

    @property
    def is_leaf(self) -> bool:
        return self.level == 0

# ----------------------------------------------------------------------------
# 3. STRtree
# M - node_capacity: Số con tối đa của một node. Nó ảnh hưởng đến hình dạng của cây:
#
#   - node_capacity nhỏ:
#       - Số Node: Nhiều
#       - Chiều cao cây: Cao
#       - Mỗi Node: Vùng bao nhỏ, ít overlap
#       - Mỗi lần duyệt: loop nhiều tầng
#       - Ưu điểm: Node bao vùng chặt, ít overlap, pruning tốt. Mỗi node chỉ phải so sánh vài con.
#       - Nhược điểm: Cây cao, nhiều node, tốn bộ nhớ cho con trỏ. Nhiều lần nhảy giữa các node.
#
#   - node_capacity lớn
#       - Số Node: Ít
#       - Chiều cao cây: Thấp
#       - Mỗi Node: Bao vùng rộng, quét nhiều entry hơn
#       - Mỗi lần duyệt: Ít tầng nhưng phải kiểm tra nhiều con mỗi node
#       - Ưu điểm: Cây thấp, ít node, tốn ít bộ nhớ hơn. Ít lần nhảy con trỏ.
#       - Nhược điểm: Mỗi node phải quét nhiều con. Envelope node rộng và overlap, nên pruning kém.
#
#   - (*) pruning: Hiểu là sẽ bỏ qua toàn bộ cả một nhánh của cây mà không cần duyệt bên trong nó,
#         vì đã biết chắc bên trong không có kết quả nào.
#
#   - Cách đưa ra quyết định: 
#.    - Trong bộ nhớ, M từ 8 đến 20 thường tốt nhất
#.    - Thực hiện chạy với nhiều kịch bản để calibrate
# ---------------------------------------------------------------------------
class STRtree:
    def __init__(self, items: Iterable[tuple[Envelope, Any]], node_capacity: int = 10):
        if node_capacity < 2:
            raise ValueError("node_capacity phải >= 2")
        
        self.M = node_capacity
        entries = [Item(env, val) for env, val in items]
        self.size = len(entries)
        self.root: Node | None = self._build(entries) if entries else None
        self.last_query_visits = 0  # để quan sát hiệu quả cắt tỉa

    def _build(self, entries: list) -> Node:
        """
        Xây dựng STRtree từ danh sách entry.
        Xây từ dưới lên, đóng gói các entry thành các node lá, rồi đóng gói các node lá thành node cha, lặp lại cho đến khi còn 1 node gốc.
            Entry  --pack-->  lá (L0)  --pack-->  L1  --pack-->  ...  -->  root
        """
        level = 0
        nodes = self._pack(entries, level)
        while len(nodes) > 1:
            level += 1
            nodes = self._pack(nodes, level)
        return nodes[0]

    def _pack(self, entries: list, level: int) -> list[Node]:
        """
        Nhận 1 danh sách entry và trả về danh sách Node ở tầng nó đang thực thi. 
        Nó được sử dụng tại mọi tầng:
            - Bắt đầu với các Item để tạo node Lá
            - Rồi gom các Node vừa tạo để tạo tầng cha
            - Thực hiện cho đến khi chỉ còn một Node là Root

        Ý tưởng:
            - Thực hiện chia n entry thành các nhóm M entry sao cho mỗi nhóm nằm gần
            nhau nhất trong không gian. Cách làm là xếp các nhóm thành 1 lưới gần vuông:
            Sắp theo X để cắt thành các lát dọc, rồi trong mỗi lát sắp theo Y để cắt thành các ô.
        
        Step by Step:

            Chuẩn bị:
                - P: Số Node cần tạo. Mỗi node chứa tối đa M entry nên cần ceil(n / M) node
                - S: Số lát dọc: Muốn P node xếp thành lưới gần vuông thì cần khoảng √P cột và √P hàng, nên S = ceil(√P).
                - slice_size: Số entry trong một lát. Mỗi lát (một cột) có khoảng S node, mỗi node M entry, nên S * M.

            B1: Cắt lát dọc
                - Sắp toàn bộ entry theo tâm X, từ trái sang phải. Dùng tâm của envelope vì entry có thể là 
                hình chữ nhật chứ không chỉ là điểm.
                - Cứ slice_size entry liên tiếp thì thành một lát. Mỗi lát là một dải dọc, gồm các entry có X gần nhau.

            B2: Sắp theo Y trong từng lát
                - Trong mỗi lát, sắp lại các entry theo tâm Y, từ dưới lên trên.

            B3: Cắt thành node
                - Trong lát đã sắp theo Y, cứ M entry liên tiếp thì thành một Node.
                Các entry này gần nhau cả về X (cùng lát) lẫn Y (liên tiếp) nên envelope của node nhỏ gọn, ít chồng lấn.

        Lưu ý:
            - Node cuối của lát cuối có thể ít hơn M entry (khi n không chia hết), cây vẫn đúng.
            - Cùng một hàm cho mọi tầng: chỉ dùng e.envelope.cx / cy nên không cần biết
            entry là Item hay Node.
        """

        M = self.M
        n = len(entries)
        P = math.ceil(n / M)
        S = math.ceil(math.sqrt(P))
        slice_size = S * M

        # B1: sắp theo X rồi cắt lát dọc
        by_x = sorted(entries, key=lambda e: e.envelope.cx)

        nodes: list[Node] = []
        for i in range(0, n, slice_size):
            vertical_slice = by_x[i : i + slice_size]

            # B2: trong lát, sắp theo Y
            by_y = sorted(vertical_slice, key=lambda e: e.envelope.cy)

            # B3: cắt thành từng nhóm M -> node
            for j in range(0, len(by_y), M):
                nodes.append(Node(level, by_y[j : j + M]))

        return nodes

    def query(self, search: Envelope) -> list:
        """
        Tìm mọi đối tượng có intersect với 1 vùng input
        """
        result = []
        self.last_query_visits = 0

        if self.root is None:
            return result

        if not self.root.envelope.intersects(search):
            self.last_query_visits = 1
            return result

        stack = [self.root]
        while stack:
            node = stack.pop()
            self.last_query_visits += 1
            if node.is_leaf:
                for item in node.children:
                    if item.envelope.intersects(search):
                        result.append(item.value)
            else:
                stack.extend(c for c in node.children if c.envelope.intersects(search))

        return result

    def nearest(self, target: Envelope, k: int = 1) -> list[tuple[float, Any]]:
        """
        Tìm k Item (đối tượng dữ liệu) gần `target` nhất.
        Trả về list[(khoảng cách, value)], xếp từ gần đến xa.         
        """
        if self.root is None:
            return []
        tie = itertools.count() 
        heap = [(0.0, next(tie), self.root)]
        results = []
        
        while heap and len(results) < k:
            dist, _, obj = heapq.heappop(heap)
            if isinstance(obj, Item):
                results.append((dist, obj.value))
                continue
            for child in obj.children:
                heapq.heappush(heap, (child.envelope.distance(target), next(tie), child))
        return results
        