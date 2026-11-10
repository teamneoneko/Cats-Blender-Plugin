# MIT License
import math
from typing import Dict, NamedTuple, Sequence, Tuple

import numpy as np

Bounds = Tuple[float, float, float, float]


class Transform(NamedTuple):
    """An affine UV transform: ``uv_out = uv_in * scale + offset``."""

    scale_x: float
    scale_y: float
    offset_x: float
    offset_y: float


def uv_bounds(uvs: np.ndarray) -> Tuple[float, float, float, float]:
    """Axis-aligned bounds of a ``(n, 2)`` UV array, as ``(min_u, min_v, max_u, max_v)``.

    NaNs are ignored. Meshes imported from some formats carry them on degenerate
    faces, and letting one through would poison the whole material's bounds.
    """
    if uvs.size == 0:
        return (0.0, 0.0, 1.0, 1.0)

    finite = uvs[np.isfinite(uvs).all(axis=1)]
    if finite.size == 0:
        return (0.0, 0.0, 1.0, 1.0)

    min_u, min_v = finite.min(axis=0)
    max_u, max_v = finite.max(axis=0)
    return (float(min_u), float(min_v), float(max_u), float(max_v))


def union_bounds(a: Bounds, b: Bounds) -> Bounds:
    """Smallest bounds containing both, for a material spread over several objects."""
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def whole_tiles(bounds: Bounds) -> Bounds:
    """Round UV bounds outward to whole tiles, for the crop-disabled case."""
    return (
        float(math.floor(bounds[0])),
        float(math.floor(bounds[1])),
        float(math.ceil(bounds[2])),
        float(math.ceil(bounds[3])),
    )


def snap_bounds(bounds: Bounds, size: Tuple[int, int]) -> Bounds:
    """Widen ``bounds`` outward to the texel grid of a ``size`` texture."""
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    min_u, min_v, max_u, max_v = bounds
    x0 = math.floor(min_u * width + 1e-3)
    y0 = math.floor(min_v * height + 1e-3)
    x1 = max(x0 + 1, math.ceil(max_u * width - 1e-3))
    y1 = max(y0 + 1, math.ceil(max_v * height - 1e-3))
    return (x0 / float(width), y0 / float(height), x1 / float(width), y1 / float(height))


def uv_span(bounds: Bounds, max_tiles: int = 8) -> Tuple[float, float]:
    """How many texture widths the UVs cover, clamped to ``max_tiles``."""
    min_u, min_v, max_u, max_v = bounds
    span_u = max(1e-6, max_u - min_u)
    span_v = max(1e-6, max_v - min_v)
    return (min(span_u, float(max_tiles)), min(span_v, float(max_tiles)))


def cell_transform(
    cell_x: int,
    cell_y: int,
    cell_w: int,
    cell_h: int,
    atlas_w: int,
    atlas_h: int,
    bounds: Tuple[float, float, float, float],
    span: Tuple[float, float],
    padding: int = 0,
) -> Transform:
    """Map a material's source UV range onto its content rectangle in the atlas.

    Args:
        cell_x: Cell origin in atlas pixels, padding ring included.
        cell_y: Cell origin in atlas pixels, padding ring included.
        cell_w: Content width in pixels, padding excluded.
        cell_h: Content height in pixels, padding excluded.
        atlas_w: Full atlas width.
        atlas_h: Full atlas height.
        bounds: Source UV bounds from :func:`uv_bounds`.
        span: Tile counts from :func:`uv_span`.
        padding: Dilation ring width, added to the cell origin to reach the content.

    Returns:
        The affine transform to feed :func:`apply_transform`.
    """
    if atlas_w <= 0 or atlas_h <= 0:
        raise ValueError("atlas size must be positive")

    min_u, min_v = bounds[0], bounds[1]
    span_u, span_v = span
    content_x = cell_x + padding
    content_y = cell_y + padding

    scale_x = cell_w / (span_u * atlas_w)
    scale_y = cell_h / (span_v * atlas_h)
    offset_x = (content_x - min_u * cell_w / span_u) / atlas_w
    offset_y = (content_y - min_v * cell_h / span_v) / atlas_h
    return Transform(scale_x, scale_y, offset_x, offset_y)


def apply_transform(uvs: np.ndarray, transform: Transform, mask=None) -> None:
    """Apply ``transform`` in place to an ``(n, 2)`` UV array.

    Args:
        uvs: UV array, modified in place.
        transform: From :func:`cell_transform`.
        mask: Optional boolean array selecting which rows to touch. Rows outside
            the mask belong to other materials and must not move.
    """
    target = uvs if mask is None else uvs[mask]
    target[:, 0] = target[:, 0] * transform.scale_x + transform.offset_x
    target[:, 1] = target[:, 1] * transform.scale_y + transform.offset_y
    if mask is not None:
        uvs[mask] = target

def _uv_layer(mesh, layer_name: str):
    """The named UV layer, or the active one when no name is given."""
    return mesh.uv_layers.get(layer_name) if layer_name else mesh.uv_layers.active


def render_uv_layer_name(mesh) -> str:
    """Name of the layer an image texture with no Vector input samples."""
    for layer in mesh.uv_layers:
        if getattr(layer, 'active_render', False):
            return layer.name

    active = mesh.uv_layers.active
    if active is not None:
        return active.name
    return mesh.uv_layers[0].name if len(mesh.uv_layers) else ''


def read_uv_layer(mesh, layer_name: str) -> np.ndarray:
    """Read a whole UV layer into an ``(n, 2)`` float array in one call."""
    layer = _uv_layer(mesh, layer_name)
    if layer is None:
        return np.zeros((0, 2), dtype=np.float32)

    flat = np.empty(len(layer.uv) * 2, dtype=np.float32)
    layer.uv.foreach_get("vector", flat)
    return flat.reshape(-1, 2)


def write_uv_layer(mesh, layer_name: str, uvs: np.ndarray) -> None:
    """Write an ``(n, 2)`` array back to a UV layer in one call."""
    layer = _uv_layer(mesh, layer_name)
    if layer is None:
        return
    layer.uv.foreach_set("vector", np.ascontiguousarray(uvs, dtype=np.float32).reshape(-1))


def read_loop_materials(mesh) -> np.ndarray:
    """Per-loop material slot index for every loop in the mesh. """
    polygon_count = len(mesh.polygons)
    if polygon_count == 0:
        return np.zeros(0, dtype=np.int32)

    # int32 matches Blender's storage, so foreach_get copies in one go instead of
    # falling back to per-item conversion.
    material_indices = np.empty(polygon_count, dtype=np.int32)
    mesh.polygons.foreach_get("material_index", material_indices)

    loop_totals = np.empty(polygon_count, dtype=np.int32)
    mesh.polygons.foreach_get("loop_total", loop_totals)

    return np.repeat(material_indices, loop_totals)


def slot_uv_bounds(
    uvs: np.ndarray, loop_materials: np.ndarray, slot_indices: Sequence[int]
) -> Dict[int, Tuple[float, float, float, float]]:
    if uvs.size == 0 or loop_materials.size != uvs.shape[0]:
        return {}

    result = {}
    for slot in dict.fromkeys(slot_indices):
        mask = loop_materials == slot
        if not mask.any():
            continue
        result[slot] = uv_bounds(uvs[mask])
    return result
