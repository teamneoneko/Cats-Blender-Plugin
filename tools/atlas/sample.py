# MIT License
import os
from typing import Dict, Optional, Tuple

import bpy
import numpy as np

from . import compose, detect, maps
from .. import colorspace


class _Cache:
    """Per-build cache of decoded images, keyed by datablock name."""

    def __init__(self) -> None:
        self._store: Dict[str, np.ndarray] = {}

    def clear(self) -> None:
        self._store.clear()

    def discard(self, image: bpy.types.Image) -> None:
        """Drop one decoded image, once nothing in the build needs it any more."""
        try:
            self._store.pop(image.name_full, None)
        except ReferenceError:
            pass

    def read(self, image: bpy.types.Image) -> Optional[np.ndarray]:
        key = image.name_full
        cached = self._store.get(key)
        if cached is not None:
            return cached

        decoded = _read_image(image)
        if decoded is not None:
            self._store[key] = decoded
        return decoded


CACHE = _Cache()


def _read_image(image: bpy.types.Image) -> Optional[np.ndarray]:
    """Decode a Blender image into an ``(h, w, 4)`` float32 array."""
    try:
        width, height = image.size
    except (ReferenceError, AttributeError):
        return None

    if width <= 0 or height <= 0:
        return None

    expected = width * height * 4
    flat = np.empty(expected, dtype=np.float32)
    try:
        image.pixels.foreach_get(flat)
    except (RuntimeError, ValueError, TypeError):
        return None

    return flat.reshape(height, width, 4)


def cell_source(
    texture_set,
    width: int,
    height: int,
    multiply_diffuse: bool,
    bounds=(0.0, 0.0, 1.0, 1.0),
    pixel_art: bool = False,
    colour: bool = False,
) -> np.ndarray:
    """Build the content tile for one material's cell.

    Args:
        texture_set: From :func:`detect.texture_sets`.
        width: Target content width in pixels, padding excluded.
        height: Target content height in pixels, padding excluded.
        multiply_diffuse: Multiply the material's tint into the texture.
        bounds: The UV rectangle this cell covers, ``(min_u, min_v, max_u, max_v)``.
            The tile holds exactly the texels under it: a crop when the material
            uses part of its texture, repeats when its UVs run past 0-1.
        pixel_art: Use nearest-neighbour resampling.
        colour: The atlas is an sRGB colour map (albedo, emission) rather than data.

    Returns:
        An ``(height, width, 4)`` float32 tile, ready for :func:`compose.place`.
        Materials without a usable texture come back as a flat tint.
    """
    image = texture_set.image
    source = CACHE.read(image) if detect.is_usable(image) else None
    if source is None:
        fill = tuple(texture_set.tint)
        if colour:
            # Socket colours are linear, the atlas stores sRGB-encoded values
            fill = tuple(compose.linear_to_srgb(fill[:3]).tolist()) + fill[3:]
        return compose.new_canvas(width, height, fill)
    source = compose.crop_wrapped(source, bounds)

    tile = compose.resize(source, width, height, pixel_art=pixel_art)
    tint = texture_set.tint if multiply_diffuse else None
    return _to_atlas_encoding(tile, is_srgb_encoded(image), colour, tint)


def is_srgb_encoded(image: bpy.types.Image) -> bool:
    """Whether ``image.pixels`` holds sRGB-encoded values rather than linear ones.

    Byte images return their stored values; float images (EXR, HDR, 16-bit PNG)
    are already converted to linear by Blender.
    """
    return not image.is_float and colorspace.is_srgb(image)


def _to_atlas_encoding(tile, encoded, colour, tint=None) -> np.ndarray:
    """Convert a tile's RGB to the atlas's encoding, applying ``tint`` in linear space.

    Never modifies ``tile`` in place: it may be a view into the decoded-image cache.
    """
    if tint is not None and tuple(tint[:3]) == (1.0, 1.0, 1.0):
        tint = None

    if colour:
        if encoded and tint is None:
            return tile
        rgb = compose.srgb_to_linear(tile[:, :, :3]) if encoded else tile[:, :, :3]
        if tint is not None:
            rgb = rgb * np.asarray(tint[:3], dtype=np.float32)
        out = tile.copy()
        out[:, :, :3] = compose.linear_to_srgb(rgb)
        return out

    # Data maps store raw values, which is what the shader sees after decoding.
    if not encoded and tint is None:
        return tile
    out = tile.copy()
    if encoded:
        out[:, :, :3] = compose.srgb_to_linear(out[:, :, :3])
    if tint is not None:
        out[:, :, :3] *= np.asarray(tint[:3], dtype=np.float32)
    return out


def write_atlas(
    name: str,
    canvas: np.ndarray,
    map_kind: str = 'albedo',
    colorspace_from: Optional[bpy.types.Image] = None,
) -> bpy.types.Image:
    """Create a Blender image from a canvas, tagged with the right colorspace.

    An existing datablock of the same name is reused and resized rather than
    replaced, so repeated builds do not leave a trail of ``Atlas.001`` images.

    ``colorspace_from`` is an sRGB-encoded source texture whose exact colour space
    the atlas copies, so its pixels decode the same way the source's did.
    """
    height, width = canvas.shape[:2]

    image = bpy.data.images.get(name)
    if image is not None and tuple(image.size) != (width, height):
        bpy.data.images.remove(image)
        image = None
    if image is None:
        image = bpy.data.images.new(name=name, width=width, height=height, alpha=True)

    colorspace.set_role(image, maps.spec(map_kind).colorspace)
    if colorspace_from is not None:
        try:
            image.colorspace_settings.name = colorspace_from.colorspace_settings.name
        except (TypeError, ValueError, ReferenceError):
            pass
    image.alpha_mode = 'STRAIGHT'
    image.pixels.foreach_set(compose.to_blender_buffer(canvas))
    image.update()
    return image


def save_atlas(image: bpy.types.Image, directory: str) -> str:
    """Write an atlas image to disk as PNG.

    Returns:
        The path written, or ``''`` when saving was not possible. Failure to save is
        never fatal: the image still exists inside the .blend, so the build succeeds
        either way and the caller reports the path it could not write.
    """
    if not directory:
        return ''

    directory = bpy.path.abspath(directory)
    if not os.path.isdir(directory):
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError:
            return ''

    path = os.path.join(directory, '{}.png'.format(image.name))
    number = 2
    while os.path.exists(path):
        path = os.path.join(directory, '{}_{}.png'.format(image.name, number))
        number += 1
    try:
        image.filepath_raw = path
        image.file_format = 'PNG'
        image.save()
    except (RuntimeError, OSError):
        return ''
    return path


def source_size(texture_set, fallback: int) -> Tuple[int, int]:
    """Native size of a material's texture, or a square fallback for colour-only."""
    if detect.is_usable(texture_set.image):
        return (texture_set.image.size[0], texture_set.image.size[1])
    return (fallback, fallback)
