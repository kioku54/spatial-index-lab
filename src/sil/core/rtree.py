"""
R-tree
"""

from __future__ import annotations

from typing import Iterable, Union

from sil.geometric import Envelope
from sil.base import Item
from sil.core.tree_base import TreeIndex


class RNode:
    """
    Node của R-Tree
    Mutable vì envelope/children sẽ cập nhật khi insert/delete/split item
    """

    def __init__(self, level: int, children: list | None = None):
        self.level = level
        self.children: list[Entry] = []
        self.envelope: Envelope | None = None
        self.parent: RNode | None = None
        for c in children or ():
            self.add(c)

    @property
    def is_leaf(self) -> bool:
        return self.level == 0

    def add(self, entry: Entry) -> None:
        self.children.append(entry)
        if isinstance(entry, RNode):
            entry.parent = self

    def recompute(self) -> None:
        """Tính lại envelope từ các children"""
        self.envelope = (
            Envelope.union_all(
                c.envelope for c in self.children
            ) if self.children else None
        )


Entry = Union[RNode, Item]

DEFAULT_MAX_ENTRIES = 10

MIN_CAPACITY = 4  # giá trị nhỏ nhất cho phép của max_entries (M)
MIN_FILL = 2      # giá trị nhỏ nhất cho phép của min_entries (m)

assert MIN_CAPACITY >= 2 * MIN_FILL


class RTree(TreeIndex):
    """
    R-tree Guttman (Dynamic index):
        - Build: insert lần lượt từng item
        - Insert: ChooseLeaf (Enlargement nhỏ nhất) -> Split Quadratic nếu
            vượt quá max_entries -> AdjustTree
        - Delete: FindLeaf -> CondenseTree (node < m entry thì gỡ ra và reinsert)
    """

    dynamic = True

    def __init__(
        self,
        items: Iterable[Item] = (),
        max_entries: int = DEFAULT_MAX_ENTRIES,
        min_entries: int | None = None,
    ):
        if max_entries < MIN_CAPACITY:
            raise ValueError(f"max_entries phải >= {MIN_CAPACITY}, nhận {max_entries}")
        if min_entries is None:
            # ~40% theo khuyến nghị của Guttman, chặn trên bởi M // 2
            min_entries = min(max_entries // 2, max(MIN_FILL, max_entries * 4 // 10))
        if not MIN_FILL <= min_entries <= max_entries // 2:
            raise ValueError(
                f"min_entries phải nằm trong [{MIN_FILL}, {max_entries // 2}], nhận {min_entries}"
            )
        # Ký hiệu theo Guttman: M = số entry tối đa, m = số entry tối thiểu của node
        self.M = max_entries
        self.m = min_entries
        # Phải gán trước super().__init__ vì lớp cha có thể insert/build ngay
        self.root: RNode | None = None
        super().__init__(items)

    # ===============================================
    # Insert
    # ===============================================
    def _insert(self, item: Item) -> None:
        self._insert_entry(item, 0)

    def _insert_entry(self, entry: Entry, level: int) -> None:
        """
        Thêm 1 entry vào 1 node tại level xác đinh.
        """
        if self.root is None:
            self.root = RNode(0)

        node = self._choose_node(entry.envelope, level)
        node.add(entry)
        self._adjust_tree(node)

    def _choose_node(self, env: Envelope, level: int) -> RNode:
        """
        Duyệt từ root xuống tầng level input
        Mỗi bước chọn Node cần mở rộng ít nhất (hòa thì diện tích nhỏ hơn)
        """
        node = self.root
        while node.level > level:
            node = min(
                node.children,
                key=lambda c: (c.envelope.enlargement(env), c.envelope.area()),
            )
        return node

    def _adjust_tree(self, node: RNode) -> None:
        """
        Duyệt ngược lại lên root
        Thực hiện cập nhật envelope, Split node vượt quá max_entries, tăng chiều cao nếu root bị split
        """
        while node is not None:
            node.recompute()
            sibling = self._overflow(node) if len(node.children) > self.M else None
            parent = node.parent
            if parent is None:
                if sibling is not None:
                    self.root = RNode(node.level + 1, [node, sibling])
                    self.root.recompute()
                return
            if sibling is not None:
                parent.add(sibling)
            node = parent

    def _overflow(self, node: RNode) -> RNode | None:
        """
        Xử lý node node vượt quá max_entries
        Trả về sibling nếu split, None nếu đã xử lý xong tại chỗ
        """
        return self._split(node)
    
    # ===============================================
    # Split (Quadratic)
    # ===============================================
    def _split(self, node: RNode) -> RNode:
        """
        Core Algorithm (Quadratic Split):

        Nhận vào node bị vượt quá max_entries (M+1 entry), chia thành 2 nhóm, node giữ nhóm A và trả về sibling chứa nhóm B:
            - PickSeeds: Chọn 2 entry mà MBR của chúng lớn nhất làm hạt nhân của nhóm A và nhóm B.
            - Lặp lại cho tới khi hết entry còn lại:
                + Nếu một nhóm buộc phải nhận hết phần còn lại để đạt min_entries (m) thì gán hết cho nhóm đó.
                + Ngược lại PickNext chọn entry nghiêng rõ nhất về một nhóm, rồi gán vào nhóm cần mở rộng
                  envelope ít nhất (hòa thì xét diện tích nhỏ hơn, rồi số phần tử ít hơn).
            - Tính lại envelope của node và sibling.
        """
        rest = list(node.children)
        i, j = self._pick_seeds(rest)
        seed_a, seed_b = rest[i], rest[j]
        for idx in sorted((i, j), reverse=True):
            rest.pop(idx)

        group_a, group_b = [seed_a], [seed_b]
        env_a, env_b = seed_a.envelope, seed_b.envelope

        while rest:
            # Một nhóm buộc phải nhận hết phần còn lại để đạt min_entries
            if len(group_a) + len(rest) == self.m:
                group_a.extend(rest)
                break
            if len(group_b) + len(rest) == self.m:
                group_b.extend(rest)
                break

            idx = self._pick_next(rest, env_a, env_b)
            entry = rest.pop(idx)

            grow_a = env_a.enlargement(entry.envelope)
            grow_b = env_b.enlargement(entry.envelope)

            to_a = (grow_a, env_a.area(), len(group_a)) < (grow_b, env_b.area(), len(group_b))
            if to_a:
                group_a.append(entry)
                env_a = env_a.union(entry.envelope)
            else:
                group_b.append(entry)
                env_b = env_b.union(entry.envelope)
        
        node.children = []
        for e in group_a:
            node.add(e)
        
        node.recompute()
        sibling = RNode(node.level, group_b)
        sibling.recompute()
        
        return sibling

    @staticmethod
    def _pick_seeds(entries: list[Entry]) -> tuple[int, int]:
        """Xác định sặp entry mà diện tích envelope chung sẽ lớn nhất"""
        best, pair = float("-inf"), (0, 1)
        for i in range(len(entries) - 1):
            a = entries[i].envelope
            for j in range(i + 1, len(entries)):
                b = entries[j].envelope
                waste = a.union(b).area() - a.area() - b.area()
                if waste > best:
                    best, pair = waste, (i, j)
        return pair

    @staticmethod
    def _pick_next(entries: list[Entry], env_a: Envelope, env_b: Envelope) -> int:
        """
        Trả về chỉ số entry có chênh lệch enlargement giữa hai nhóm (A, B) lớn nhất
        """
        return max(
            range(len(entries)),
            key=lambda k: abs(
                env_a.enlargement(entries[k].envelope) - env_b.enlargement(entries[k].envelope)
            ),
        )

    # ===============================================
    # Delete
    # ===============================================
    def _delete(self, item: Item) -> bool:
        if self.root is None:
            return False
        
        leaf = self._find_leaf(item)
        if leaf is None:
            return False
        
        leaf.children.remove(item)
        self._condense_tree(leaf)
        return True

    def _find_leaf(self, item: Item) -> RNode | None:
        """Tìm lá chứa item, đi trực tiếp vào node có envelope bao trọn envelope của item"""
        stack = [self.root]
        while stack:
            node = stack.pop()
            if node.is_leaf:
                if item in node.children:
                    return node
                continue
            stack.extend(c for c in node.children if c.envelope.is_contains(item.envelope))
        return None

    def _condense_tree(self, leaf: RNode) -> None:
        """
        Duyệt ngược từ lá lên root:
            - Node thiếu entry (< m) sẽ được gở ra khỏi Parent của nó.
            - Các entry của nó được reinsert ở đúng tầng để cây luôn cân bằng
        """
        orphans: list[tuple[Entry, int]] = []
        node = leaf
        while node.parent is not None:
            parent = node.parent
            if len(node.children) < self.m:
                parent.children.remove(node)
                orphans.extend((e, node.level) for e in node.children)
            else:
                node.recompute()
            node = parent
        node.recompute()

        for entry, level in orphans:
            if isinstance(entry, RNode):
                entry.parent = None
            self._insert_entry(entry, level)

        root = self.root
        while not root.is_leaf and len(root.children) == 1:
            root = root.children[0]
            root.parent = None
        self.root = root if root.children else None
