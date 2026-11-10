# MIT License
import numpy as np


def new_canvas(width: int, height: int, fill=(0.0, 0.0, 0.0, 0.0)) -> np.ndarray:
    """Allocate an ``(height, width, 4)`` float32 canvas filled with ``fill``.

    Also the flat tile for a material that carries a colour but no texture.
    """
    if width <= 0 or height <= 0:
        raise ValueError("canvas size must be positive, got {}x{}".format(width, height))
    canvas = np.empty((height, width, 4), dtype=np.float32)
    canvas[:] = np.asarray(fill, dtype=np.float32)
    return canvas


def srgb_to_linear(rgb) -> np.ndarray:
    """Decode sRGB-encoded values to linear, the inverse of :func:`linear_to_srgb`."""
    rgb = np.asarray(rgb, dtype=np.float32)
    curve = ((np.maximum(rgb, 0.04045) + 0.055) / 1.055) ** 2.4
    return np.where(rgb <= 0.04045, rgb / 12.92, curve).astype(np.float32)


def linear_to_srgb(rgb) -> np.ndarray:
    """Encode linear values the way an sRGB image stores them."""
    rgb = np.maximum(np.asarray(rgb, dtype=np.float32), 0.0)
    curve = 1.055 * np.maximum(rgb, 0.0031308) ** (1.0 / 2.4) - 0.055
    return np.where(rgb < 0.0031308, rgb * 12.92, curve).astype(np.float32)


def crop_wrapped(source: np.ndarray, bounds) -> np.ndarray:
    """The texels of ``source`` under a UV rectangle, wrapping past the tile edges."""
    src_h, src_w = source.shape[:2]
    if src_h == 0 or src_w == 0:
        raise ValueError("cannot crop an empty source")
    min_u, min_v, max_u, max_v = bounds
    x0 = int(round(min_u * src_w))
    y0 = int(round(min_v * src_h))
    x1 = max(x0 + 1, int(round(max_u * src_w)))
    y1 = max(y0 + 1, int(round(max_v * src_h)))
    if 0 <= x0 and x1 <= src_w and 0 <= y0 and y1 <= src_h:
        # No wrapping needed, skip the full copy fancy indexing would make
        return source[y0:y1, x0:x1]
    cols = np.arange(x0, x1) % src_w
    rows = np.arange(y0, y1) % src_h
    return source[rows[:, None], cols[None, :]]


def resize(source: np.ndarray, width: int, height: int, pixel_art: bool = False) -> np.ndarray:
    """Resample ``source`` to ``width`` x ``height``.

    Box-averages on exact integer downscales, which is both the common case for
    avatar textures and the highest quality option for them. Other shrinks of 2x
    or more average every covered texel (bilinear would skip most of them and
    alias); smaller ratios and upscales are bilinear, which is what a slight shrink
    to keep an atlas on a power of two needs. Nearest-neighbour is reserved for
    ``pixel_art``, where blending is the wrong answer by definition.
    """
    if width <= 0 or height <= 0:
        raise ValueError("resize target must be positive, got {}x{}".format(width, height))

    src_h, src_w = source.shape[:2]
    if (src_w, src_h) == (width, height):
        return source

    if pixel_art:
        ys = (np.arange(height, dtype=np.float64) + 0.5) * (src_h / float(height))
        xs = (np.arange(width, dtype=np.float64) + 0.5) * (src_w / float(width))
        ys = np.clip(ys.astype(np.intp), 0, src_h - 1)
        xs = np.clip(xs.astype(np.intp), 0, src_w - 1)
        return source[ys[:, None], xs[None, :]]

    if src_w % width == 0 and src_h % height == 0 and src_w >= width and src_h >= height:
        factor_x = src_w // width
        factor_y = src_h // height
        reshaped = source.reshape(height, factor_y, width, factor_x, 4)
        return reshaped.mean(axis=(1, 3), dtype=np.float32)

    # Shrink the larger axis first so the second pass works on less data
    if src_w - width >= src_h - height:
        return _resample_axis(_resample_axis(source, width, 1), height, 0)
    return _resample_axis(_resample_axis(source, height, 0), width, 1)


def _resample_axis(source: np.ndarray, target: int, axis: int) -> np.ndarray:
    """Resample one axis: area average for shrinks of 2x or more, else linear."""
    length = source.shape[axis]
    if target == length:
        return source
    if length >= 2 * target:
        return _area_axis(source, target, axis)
    return _linear_axis(source, target, axis)


def _axis_shape(values: np.ndarray, ndim: int, axis: int) -> np.ndarray:
    """Reshape a 1D per-index array so it broadcasts along ``axis``."""
    shape = [1] * ndim
    shape[axis] = values.shape[0]
    return values.reshape(shape)


def _linear_axis(source: np.ndarray, target: int, axis: int) -> np.ndarray:
    """Linear resample along one axis, texel centres aligned, edges clamped."""
    length = source.shape[axis]
    centres = (np.arange(target, dtype=np.float32) + 0.5) * (length / float(target)) - 0.5
    lo = np.floor(centres)
    frac = _axis_shape((centres - lo).astype(np.float32), source.ndim, axis)
    lo = np.clip(lo.astype(np.intp), 0, length - 1)
    hi = np.clip(lo + 1, 0, length - 1)
    blended = np.take(source, lo, axis=axis) * (1.0 - frac) + np.take(source, hi, axis=axis) * frac
    return blended.astype(np.float32)


def _area_axis(source: np.ndarray, target: int, axis: int) -> np.ndarray:
    """Average every source texel each output texel covers, weighting partial ones."""
    length = source.shape[axis]
    step = length / float(target)
    zero_shape = list(source.shape)
    zero_shape[axis] = 1
    sums = np.concatenate(
        (np.zeros(zero_shape, dtype=np.float32), np.cumsum(source, axis=axis, dtype=np.float32)),
        axis=axis,
    )

    edges = np.arange(target + 1, dtype=np.float64) * step
    whole = np.minimum(np.floor(edges).astype(np.intp), length)
    frac = _axis_shape((edges - whole).astype(np.float32), source.ndim, axis)
    partial = np.take(source, np.minimum(whole, length - 1), axis=axis) * frac
    integral = np.take(sums, whole, axis=axis) + partial

    return (np.diff(integral, axis=axis) / step).astype(np.float32)


def place(
    canvas: np.ndarray,
    tile: np.ndarray,
    x: int,
    y: int,
    padding: int = 0,
    wrap: bool = False,
) -> None:
    """Blit ``tile`` into ``canvas`` and fill its padding ring.

    Args:
        canvas: Destination buffer, modified in place.
        tile: Source buffer, ``(h, w, 4)``.
        x: Cell origin within the canvas, including the padding ring.
        y: Cell origin within the canvas, including the padding ring.
        padding: Ring width on every side. The content lands at ``(x + padding,
            y + padding)``.
        wrap: Fill the ring by wrapping around to the opposite edge instead of
            replicating the nearest edge. Correct for tiling textures, where a
            clamped ring would show a false seam at the tile boundary.

    Raises:
        ValueError: If the cell would fall outside the canvas.
    """
    tile_h, tile_w = tile.shape[:2]
    cell_w = tile_w + 2 * padding
    cell_h = tile_h + 2 * padding

    if x < 0 or y < 0 or x + cell_w > canvas.shape[1] or y + cell_h > canvas.shape[0]:
        raise ValueError(
            "cell {}x{} at ({}, {}) does not fit canvas {}x{}".format(
                cell_w, cell_h, x, y, canvas.shape[1], canvas.shape[0]
            )
        )

    inner_x = x + padding
    inner_y = y + padding
    canvas[inner_y:inner_y + tile_h, inner_x:inner_x + tile_w] = tile

    if padding > 0:
        _fill_ring(canvas, tile, inner_x, inner_y, padding, wrap)


def _fill_ring(
    canvas: np.ndarray,
    tile: np.ndarray,
    inner_x: int,
    inner_y: int,
    padding: int,
    wrap: bool,
) -> None:
    """Extend the tile's border pixels outward into its padding ring."""
    tile_h, tile_w = tile.shape[:2]
    # Wrapping needs at least `padding` pixels to copy from; clamp rather than fail
    # on a tile smaller than its own ring.
    pad_x = min(padding, tile_w) if wrap else padding
    pad_y = min(padding, tile_h) if wrap else padding

    left = tile[:, -pad_x:] if wrap else np.repeat(tile[:, :1], padding, axis=1)
    right = tile[:, :pad_x] if wrap else np.repeat(tile[:, -1:], padding, axis=1)
    canvas[inner_y:inner_y + tile_h, inner_x - left.shape[1]:inner_x] = left
    canvas[inner_y:inner_y + tile_h, inner_x + tile_w:inner_x + tile_w + right.shape[1]] = right

    # Take the vertical strips from the canvas so the corners come along for free:
    # the horizontal ring is already written at this point.
    span_x0 = inner_x - (left.shape[1] if wrap else padding)
    span_x1 = inner_x + tile_w + (right.shape[1] if wrap else padding)
    band = canvas[inner_y:inner_y + tile_h, span_x0:span_x1]

    below = band[-pad_y:] if wrap else np.repeat(band[:1], padding, axis=0)
    above = band[:pad_y] if wrap else np.repeat(band[-1:], padding, axis=0)
    canvas[inner_y - below.shape[0]:inner_y, span_x0:span_x1] = below
    canvas[inner_y + tile_h:inner_y + tile_h + above.shape[0], span_x0:span_x1] = above


def multiply_rgb(tile: np.ndarray, colour) -> np.ndarray:
    """Multiply the RGB channels by a colour, leaving alpha untouched.

    This is the tint step: Material Combiner's "Multiply Color" per-material option.
    """
    out = tile.copy()
    out[:, :, :3] *= np.asarray(colour, dtype=np.float32)[:3]
    return out


def to_blender_buffer(canvas: np.ndarray) -> np.ndarray:
    """Flatten a canvas into the layout ``Image.pixels.foreach_set`` expects."""
    return np.ascontiguousarray(canvas, dtype=np.float32).reshape(-1)


def pack_metallic_smoothness(
    metallic: np.ndarray, roughness: np.ndarray
) -> np.ndarray:
    """Combine metallic and roughness into Unity's MetallicSmoothness layout."""
    if metallic.shape != roughness.shape:
        raise ValueError(
            "metallic {} and roughness {} must match".format(
                metallic.shape, roughness.shape
            )
        )

    packed = np.empty_like(metallic)
    packed[:, :, 0] = metallic[:, :, 0]
    packed[:, :, 1] = metallic[:, :, 0]
    packed[:, :, 2] = metallic[:, :, 0]
    packed[:, :, 3] = 1.0 - roughness[:, :, 0]
    return packed


def canvas_is_neutral(canvas: np.ndarray, colour, atol: float = 1e-5) -> bool:
    """Whether every pixel of ``canvas`` equals ``colour``."""
    reference = np.asarray(colour, dtype=np.float32)
    return bool(np.allclose(canvas[..., :reference.size], reference, atol=atol))
