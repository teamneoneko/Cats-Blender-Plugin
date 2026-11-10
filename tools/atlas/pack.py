# MIT License
from typing import Dict, Iterable, List, NamedTuple, Sequence, Tuple

SIZE_MODES = ("PO2", "QUAD", "AUTO", "CUST", "STRICTCUST")


class PackError(Exception):
    """Raised when the input cannot be packed at all."""


class Cell(NamedTuple):
    """A packed rectangle, in atlas pixel coordinates with the origin bottom-left."""

    key: object
    x: int
    y: int
    w: int
    h: int


class _Node:
    """A free (or split) rectangle in the packing tree."""

    __slots__ = ("x", "y", "w", "h", "used", "right", "down")

    def __init__(self, x: int, y: int, w: int, h: int) -> None:
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.used = False
        self.right = None
        self.down = None


def _find(node: _Node, w: int, h: int):
    """Depth-first search for a free node at least ``w`` x ``h``.

    Iterative rather than recursive: a few thousand materials would otherwise be deep
    enough to matter against Python's recursion limit.
    """
    stack = [node]
    while stack:
        current = stack.pop()
        if current.used:
            # Right before down, matching the recursive form's evaluation order.
            if current.down is not None:
                stack.append(current.down)
            if current.right is not None:
                stack.append(current.right)
        elif w <= current.w and h <= current.h:
            return current
    return None


def _split(node: _Node, w: int, h: int) -> _Node:
    """Claim ``w`` x ``h`` from ``node``, leaving the remainder as two children."""
    node.used = True
    node.down = _Node(node.x, node.y + h, node.w, node.h - h)
    node.right = _Node(node.x + w, node.y, node.w - w, h)
    return node


def _sort_key(item: Tuple[object, int, int]) -> tuple:
    """Longest side first, then area, then width, then the key as a stable tiebreak.

    Longest-side-descending is what makes the grow step total: the root's larger
    dimension is set by the first item and only ever grows, so every later item fits
    at least one grow direction.
    """
    key, w, h = item
    return (-max(w, h), -(w * h), -w, repr(key))


class _Packer:
    def __init__(self) -> None:
        self.root = None

    def pack(self, items: Sequence[Tuple[object, int, int]]) -> List[Cell]:
        ordered = sorted(items, key=_sort_key)
        first_key, first_w, first_h = ordered[0]
        self.root = _Node(0, 0, first_w, first_h)

        cells = []
        for key, w, h in ordered:
            node = _find(self.root, w, h)
            node = _split(node, w, h) if node else self._grow(w, h)
            cells.append(Cell(key, node.x, node.y, w, h))
        return cells

    def _grow(self, w: int, h: int) -> _Node:
        can_right = h <= self.root.h
        can_down = w <= self.root.w

        # Prefer the direction that keeps the atlas closest to square.
        if can_right and self.root.h >= self.root.w + w:
            return self._grow_right(w, h)
        if can_down and self.root.w >= self.root.h + h:
            return self._grow_down(w, h)
        if can_right:
            return self._grow_right(w, h)
        if can_down:
            return self._grow_down(w, h)

        # Unreachable while the sort above holds. Kept so that changing the sort
        # degrades packing efficiency instead of raising AttributeError at runtime,
        # which is the failure mode both reference implementations ship with.
        return self._grow_both(w, h)

    def _grow_right(self, w: int, h: int) -> _Node:
        old = self.root
        self.root = _Node(0, 0, old.w + w, old.h)
        self.root.used = True
        self.root.down = old
        self.root.right = _Node(old.w, 0, w, old.h)
        node = _find(self.root, w, h)
        return _split(node, w, h)

    def _grow_down(self, w: int, h: int) -> _Node:
        old = self.root
        self.root = _Node(0, 0, old.w, old.h + h)
        self.root.used = True
        self.root.down = _Node(0, old.h, old.w, h)
        self.root.right = old
        node = _find(self.root, w, h)
        return _split(node, w, h)

    def _grow_both(self, w: int, h: int) -> _Node:
        """Widen and heighten at once, placing the item in a full-width new row.

        Wastes the sliver to the right of the old root, which is why it is a last
        resort rather than the general case.
        """
        old = self.root
        new_w = max(old.w, w)
        self.root = _Node(0, 0, new_w, old.h + h)
        self.root.used = True
        self.root.down = _Node(0, old.h, new_w, h)
        self.root.right = old
        node = _find(self.root, w, h)
        return _split(node, w, h)


def pack(items: Iterable[Tuple[object, int, int]]) -> List[Cell]:
    """Pack ``(key, width, height)`` triples into one bin.

    Args:
        items: Rectangles to place. Dimensions must be positive integers.

    Returns:
        One :class:`Cell` per input, ordered largest-first rather than in input
        order. Coordinates have their origin at the bottom left, matching Blender's
        image buffers and UV space.

    Raises:
        PackError: If any dimension is not a positive integer.
    """
    items = [(key, int(w), int(h)) for key, w, h in items]
    if not items:
        return []

    for key, w, h in items:
        if w <= 0 or h <= 0:
            raise PackError(
                "cannot pack {!r}: size {}x{} is not positive".format(key, w, h)
            )

    return _Packer().pack(items)


def bounds(cells: Sequence[Cell]) -> Tuple[int, int]:
    """Smallest ``(width, height)`` that contains every cell."""
    if not cells:
        return (0, 0)
    return (
        max(cell.x + cell.w for cell in cells),
        max(cell.y + cell.h for cell in cells),
    )


def occupancy(cells: Sequence[Cell], size: Tuple[int, int]) -> float:
    """Fraction of ``size`` covered by cells, in ``0.0`` to ``1.0``.

    Reported to the user after a build so a poor pack is visible rather than implied
    by an unexpectedly large output.
    """
    width, height = size
    if width <= 0 or height <= 0:
        return 0.0
    used = sum(cell.w * cell.h for cell in cells)
    return min(1.0, used / float(width * height))


def _next_power_of_two(value: int) -> int:
    if value < 1:
        return 1
    return 1 << (value - 1).bit_length()


def apply_size_mode(
    size: Tuple[int, int],
    mode: str,
    custom: Tuple[int, int] = (4096, 4096),
) -> Tuple[int, int]:
    """Expand a packed size according to the chosen sizing strategy.

    The identifiers match Material Combiner's ``smc_size`` enum so migrated settings
    carry across unchanged.

    Args:
        size: Packed bounds from :func:`bounds`.
        mode: One of :data:`SIZE_MODES`.
        custom: Target dimensions for the two custom modes.

    Returns:
        The atlas dimensions to allocate. ``CUST`` scales proportionally to fit
        within ``custom`` and never enlarges; ``STRICTCUST`` returns ``custom``
        exactly.
    """
    width, height = int(size[0]), int(size[1])
    if width <= 0 or height <= 0:
        return (0, 0)

    if mode == "PO2":
        return (_next_power_of_two(width), _next_power_of_two(height))
    if mode == "QUAD":
        side = max(width, height)
        return (side, side)
    if mode == "STRICTCUST":
        return (max(1, int(custom[0])), max(1, int(custom[1])))
    if mode == "CUST":
        target_w, target_h = max(1, int(custom[0])), max(1, int(custom[1]))
        scale = min(target_w / float(width), target_h / float(height), 1.0)
        return (max(1, int(width * scale)), max(1, int(height * scale)))
    return (width, height)


def cell_sizes_for_budget(
    requests: Dict[object, Tuple[int, int]],
    cap: Tuple[int, int],
    padding: int,
    min_side: int = 4,
) -> Dict[object, Tuple[int, int]]:
    """Shrink requested cell sizes until the pack fits inside ``cap``."""
    if not requests:
        return {}

    scale = 1.0
    for _ in range(64):
        scaled = {
            key: (
                max(min_side, int(w * scale)),
                max(min_side, int(h * scale)),
            )
            for key, (w, h) in requests.items()
        }
        cells = pack(
            (key, w + 2 * padding, h + 2 * padding)
            for key, (w, h) in scaled.items()
        )
        width, height = bounds(cells)
        if width <= cap[0] and height <= cap[1]:
            return scaled
        if all(
            w <= min_side and h <= min_side for w, h in scaled.values()
        ):
            return scaled
        scale *= min(cap[0] / float(width), cap[1] / float(height))

    return scaled
