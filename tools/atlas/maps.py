# MIT License
"""The one table describing every map the atlas can produce.

Pure Python: no bpy, no numpy. Every other module in the package reads from here,
so adding a map is one row in ``SPECS`` plus its scene toggle, UI row and
translations, rather than an edit in five files that each carried a slice of it.
"""
from typing import Dict, NamedTuple, Optional, Tuple


class MapSpec(NamedTuple):
    """Everything the pipeline needs to know about one map kind.

    Attributes:
        colorspace: Colour space role written onto the output image, ``'color'``
            or ``'data'`` (``tools/colorspace.py`` resolves it for the active OCIO
            config). Getting this wrong is silent: the atlas looks plausible in the
            viewport and exports with the wrong gamma.
        neutral: Straight RGBA fill for a material that contributes nothing, and the
            value a composed canvas is compared against to decide whether the map is
            worth writing at all.
        suffix: Appended to the atlas image name. Albedo keeps the bare name so
            existing builds keep their datablock.
        bake_pass: Cycles bake type, or ``None`` when Cycles has no pass for it and
            the map stays copy-only whatever the bake toggle says.
        scene_prop: Scene property gating the map, or ``None`` when it is always
            generated.
    """

    colorspace: str
    neutral: Tuple[float, float, float, float]
    suffix: str
    bake_pass: Optional[str]
    scene_prop: Optional[str]


# Insertion order is build order, which is what keeps output deterministic. Albedo
# drives the layout, so it is always first and has no toggle.
SPECS: Dict[str, MapSpec] = {
    'albedo': MapSpec('color', (1.0, 1.0, 1.0, 1.0), '', 'DIFFUSE', None),
    'normal': MapSpec('data', (0.5, 0.5, 1.0, 1.0), '_Normal', 'NORMAL', 'cats_atlas_map_normal'),
    'emission': MapSpec('color', (0.0, 0.0, 0.0, 1.0), '_Emission', 'EMIT', 'cats_atlas_map_emission'),
    'roughness': MapSpec('data', (1.0, 1.0, 1.0, 1.0), '_Roughness', 'ROUGHNESS', 'cats_atlas_map_roughness'),
    'metallic': MapSpec('data', (0.0, 0.0, 0.0, 1.0), '_Metallic', None, 'cats_atlas_map_metallic'),
    'ao': MapSpec('data', (1.0, 1.0, 1.0, 1.0), '_AO', 'AO', 'cats_atlas_map_ao'),
    'height': MapSpec('data', (0.5, 0.5, 0.5, 1.0), '_Height', None, 'cats_atlas_map_height'),
}

# Derived from metallic and roughness after composing, so it is never detected,
# baked or toggled on its own. Kept out of MAPS for that reason.
PACKED_METALLIC_SMOOTHNESS = 'metallic_smoothness'
PACKED_SPEC = MapSpec('data', (0.0, 0.0, 0.0, 1.0), '_MetallicSmoothness', None, None)

# Every map that can be resolved from a material, in build order.
MAPS = tuple(SPECS)

# Convenience views, kept because the lookups are hot in call sites and tests.
NEUTRAL = {name: spec.neutral for name, spec in SPECS.items()}


def spec(map_kind: str) -> MapSpec:
    """The spec for a map, including the packed MetallicSmoothness output."""
    if map_kind == PACKED_METALLIC_SMOOTHNESS:
        return PACKED_SPEC
    return SPECS[map_kind]
