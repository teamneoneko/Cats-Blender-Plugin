# MIT License
from typing import Dict, NamedTuple, Optional

import bpy

from .maps import MAPS, NEUTRAL

# Group node tree names that identify an importer's shader.
GROUP_SHADERS = {
    'MToon_unversioned': 'vrm',
    'XPS Shader': 'xnalara',
    'Mtoon1Material.Mtoon1Output': 'mtoon',
}

# Named texture nodes that importers reliably produce for the albedo slot.
NAMED_ALBEDO_NODES = (
    'mmd_base_tex',
    'Mtoon1BaseColorTexture.Image',
)

MMD_SHADER_NODE = 'mmd_shader'

# Socket names that carry albedo, in the order they should be tried.
ALBEDO_INPUTS = (
    'Base Color',
    'Color',
    'Diffuse Color',
    'BaseColor',
    'Diffuse',
)

MAP_INPUTS = {
    'emission': ('Emission Color', 'Emission'),
    'roughness': ('Roughness',),
    'metallic': ('Metallic',),
}

SHADER_TYPES = {
    'ShaderNodeBsdfPrincipled': 'principled',
    'ShaderNodeBsdfDiffuse': 'diffuse',
    'ShaderNodeEmission': 'emission',
    'ShaderNodeBsdfToon': 'toon',
}

WHITE = (1.0, 1.0, 1.0, 1.0)

# Words that mark an image texture as belonging to a particular map. Used only for
# ambient occlusion, which has no Principled input to trace, and as a negative
# filter for the albedo last-resort sweep.
AO_HINTS = ('ambient_occlusion', 'ambientocclusion', 'occlusion', '_ao', 'ao_', 'aomap')

CONFIDENCE_HIGH = 'HIGH'
CONFIDENCE_LOW = 'LOW'
CONFIDENCE_NONE = 'NONE'


class TextureSet(NamedTuple):
    """What a material contributes to one map of the atlas.

    Attributes:
        image: Source image, or ``None`` when the material only has a constant.
        tint: Linear RGBA. Multiplied into the texture for albedo; used as the flat
            cell fill when there is no image. Scalar maps replicate their float
            across RGB.
        uv_layer: UV layer the texture samples, or ``''`` for the object's active
            one. Only the albedo set's value is used, since every map shares one
            layout.
        confidence: ``HIGH`` when found on a recognised shader input, ``LOW`` from a
            fallback sweep, ``NONE`` when there is no image at all.
    """

    image: Optional[bpy.types.Image]
    tint: tuple
    uv_layer: str
    confidence: str


def _output_node(node_tree):
    for node in node_tree.nodes:
        if node.bl_idname == 'ShaderNodeOutputMaterial' and node.is_active_output:
            return node
    for node in node_tree.nodes:
        if node.bl_idname == 'ShaderNodeOutputMaterial':
            return node
    return None


def _surface_shader(output_node, depth: int = 0):
    if output_node is None or depth > 16:
        return None, None

    surface = output_node.inputs.get('Surface')
    if surface is None or not surface.links:
        return None, None

    return _classify(surface.links[0].from_node, depth)


def _classify(node, depth: int = 0):
    """Identify a shader node, stepping through mixers and unrecognised groups."""
    if node is None or depth > 16:
        return None, None

    kind = SHADER_TYPES.get(node.bl_idname)
    if kind:
        return node, kind

    if node.bl_idname == 'ShaderNodeGroup' and node.node_tree:
        kind = GROUP_SHADERS.get(node.node_tree.name)
        if kind:
            return node, kind
    if node.name == MMD_SHADER_NODE:
        return node, 'mmd'

    for socket in node.inputs:
        if socket.links:
            found, kind = _classify(socket.links[0].from_node, depth + 1)
            if found is not None:
                return found, kind
    return None, None


def _image_node_upstream(socket, depth: int = 0):
    """First image texture node reachable by walking inputs back from ``socket``.

    Inputs only. Material Combiner's equivalent follows outputs as well, so from any
    node it can reach the whole connected graph and return a texture from a
    completely unrelated branch.
    """
    if socket is None or not socket.links or depth > 24:
        return None

    node = socket.links[0].from_node
    if node.bl_idname == 'ShaderNodeTexImage' and node.image is not None:
        return node

    for upstream in node.inputs:
        if upstream.links:
            found = _image_node_upstream(upstream, depth + 1)
            if found is not None:
                return found
    return None


def _uv_layer_for(image_node) -> str:
    """UV layer the texture node samples, or ``''`` when it uses the active one."""
    if image_node is None:
        return ''
    vector = image_node.inputs.get('Vector')
    if vector is None or not vector.links:
        return ''

    node = vector.links[0].from_node
    if node.bl_idname == 'ShaderNodeUVMap' and node.uv_map:
        return node.uv_map
    if node.bl_idname == 'ShaderNodeAttribute' and node.attribute_name:
        return node.attribute_name
    return ''


def _socket_colour(socket) -> tuple:
    """A socket's default value as RGBA, whatever its type.

    Float sockets -- roughness, metallic -- replicate across RGB so a material with a
    constant roughness of 0.4 still contributes a meaningful flat cell rather than
    falling back to the neutral.
    """
    if socket is None or not hasattr(socket, 'default_value'):
        return WHITE
    value = socket.default_value
    if isinstance(value, (int, float)):
        scalar = float(value)
        return (scalar, scalar, scalar, 1.0)
    try:
        value = tuple(value)
    except TypeError:
        return WHITE
    if len(value) == 3:
        return value + (1.0,)
    return value[:4] if len(value) >= 4 else WHITE


def _first_socket(shader_node, names):
    """The first input socket on ``shader_node`` whose name is in ``names``."""
    if shader_node is None:
        return None
    for name in names:
        socket = shader_node.inputs.get(name)
        if socket is not None:
            return socket
    return None


def _named_albedo_node(node_tree):
    for name in NAMED_ALBEDO_NODES:
        node = node_tree.nodes.get(name)
        if node is not None and getattr(node, 'image', None) is not None:
            return node
    return None


def _node_haystack(node) -> str:
    image_name = node.image.name if getattr(node, 'image', None) is not None else ''
    return (node.name + node.label + image_name).lower()


def _any_image_node(node_tree):
    """Last-resort albedo sweep, skipping the obvious non-albedo maps.

    Name matching is crude, but a texture called ``normal`` is never the albedo and
    returning it would be worse than returning nothing.
    """
    skip = ('normal', 'sphere', 'toon', 'spa', 'sph', 'emission', 'roughness',
            'metallic', 'occlusion', 'height', 'bump')
    candidates = [
        node for node in node_tree.nodes
        if node.bl_idname == 'ShaderNodeTexImage' and node.image is not None
    ]
    for node in candidates:
        if not any(term in _node_haystack(node) for term in skip):
            return node
    return candidates[0] if candidates else None


def _normal_image_node(shader_node):
    """Image behind the Normal input, seen through a Normal Map or Bump node."""
    socket = _first_socket(shader_node, ('Normal',))
    if socket is None or not socket.links:
        return None

    node = socket.links[0].from_node
    if node.bl_idname in ('ShaderNodeNormalMap', 'ShaderNodeBump'):
        for name in ('Color', 'Height'):
            inner = node.inputs.get(name)
            found = _image_node_upstream(inner)
            if found is not None:
                return found
        return None
    return _image_node_upstream(socket)


def _height_image_node(node_tree, shader_node):
    """Image behind a Displacement or Bump height input."""
    output = _output_node(node_tree)
    if output is not None:
        displacement = output.inputs.get('Displacement')
        if displacement is not None and displacement.links:
            node = displacement.links[0].from_node
            inner = node.inputs.get('Height')
            if inner is not None:
                found = _image_node_upstream(inner)
                if found is not None:
                    return found
            return _image_node_upstream(displacement)

    socket = _first_socket(shader_node, ('Normal',))
    if socket is not None and socket.links:
        node = socket.links[0].from_node
        if node.bl_idname == 'ShaderNodeBump':
            return _image_node_upstream(node.inputs.get('Height'))
    return None


def _ao_image_node(node_tree):
    """Ambient occlusion, found by name.

    Principled has no AO input, so unlike every other map there is no connection to
    trace. Anything found this way is reported as low confidence.
    """
    for node in node_tree.nodes:
        if node.bl_idname != 'ShaderNodeTexImage' or node.image is None:
            continue
        if any(hint in _node_haystack(node) for hint in AO_HINTS):
            return node
    return None


def principled_shader(material):
    """The Principled BSDF feeding the material's surface, or ``None``."""
    if material is None or material.node_tree is None:
        return None
    shader_node, kind = _surface_shader(_output_node(material.node_tree))
    return shader_node if kind == 'principled' else None


def albedo(material) -> TextureSet:
    """Resolve a material's albedo texture, tint and UV layer.

    Kept as a named entry point because albedo drives the layout: its UV layer
    decides which coordinates every other map is packed against.
    """
    if material is None or material.node_tree is None:
        return TextureSet(None, WHITE, '', CONFIDENCE_NONE)

    node_tree = material.node_tree
    shader_node, kind = _surface_shader(_output_node(node_tree))
    socket = _first_socket(
        shader_node, ('Diffuse Color',) if kind == 'mmd' else ALBEDO_INPUTS
    )

    image_node = _image_node_upstream(socket)
    confidence = CONFIDENCE_HIGH

    if image_node is None:
        image_node = _named_albedo_node(node_tree)

    if image_node is None:
        image_node = _any_image_node(node_tree)
        if image_node is not None:
            confidence = CONFIDENCE_LOW

    socket_is_linked = socket is not None and bool(socket.links)
    tint = WHITE if socket_is_linked else _socket_colour(socket)

    if kind == 'mmd' and shader_node is not None and not socket_is_linked:
        ambient = _socket_colour(shader_node.inputs.get('Ambient Color'))
        # The first step inside the mmd_shader group node, matching what
        # tools/common.py bakes when it adds a Principled shader.
        tint = tuple(
            min(1.0, max(0.0, ambient[i] + tint[i] * 0.6)) for i in range(3)
        ) + (tint[3],)

    if image_node is None:
        return TextureSet(None, tint, '', CONFIDENCE_NONE)

    return TextureSet(image_node.image, tint, _uv_layer_for(image_node), confidence)


def _emission_is_off(shader_node) -> bool:
    """Whether an *untextured* emission colour should be ignored."""
    if shader_node is None:
        return False
    strength = shader_node.inputs.get('Emission Strength')
    if strength is None or strength.links:
        return False
    try:
        return float(strength.default_value) == 0.0
    except (TypeError, ValueError):
        return False


def _secondary(material, map_kind: str) -> TextureSet:
    """Resolve one of the non-albedo maps."""
    node_tree = material.node_tree
    shader_node, _kind = _surface_shader(_output_node(node_tree))

    if map_kind == 'normal':
        node = _normal_image_node(shader_node)
    elif map_kind == 'height':
        node = _height_image_node(node_tree, shader_node)
    elif map_kind == 'ao':
        node = _ao_image_node(node_tree)
    else:
        node = _image_node_upstream(_first_socket(shader_node, MAP_INPUTS[map_kind]))

    if node is not None:
        confidence = CONFIDENCE_LOW if map_kind == 'ao' else CONFIDENCE_HIGH
        return TextureSet(node.image, WHITE, _uv_layer_for(node), confidence)

    # No image. Fall back to the socket's constant where one exists, so a material
    # set to roughness 0.4 contributes 0.4 rather than the neutral 1.0.
    if map_kind in MAP_INPUTS and not (
        map_kind == 'emission' and _emission_is_off(shader_node)
    ):
        socket = _first_socket(shader_node, MAP_INPUTS[map_kind])
        if socket is not None and not socket.links:
            return TextureSet(None, _socket_colour(socket), '', CONFIDENCE_NONE)

    return TextureSet(None, NEUTRAL[map_kind], '', CONFIDENCE_NONE)


def texture_sets(material, wanted=MAPS) -> Dict[str, TextureSet]:
    """Resolve every requested map for a material.

    Args:
        material: Material to inspect.
        wanted: Map names to resolve. Albedo is always included, because the layout
            is derived from it.

    Returns:
        ``{map_kind: TextureSet}`` for albedo plus each requested map.
    """
    resolved = {'albedo': albedo(material)}
    if material is None or material.node_tree is None:
        for map_kind in wanted:
            resolved.setdefault(
                map_kind, TextureSet(None, NEUTRAL[map_kind], '', CONFIDENCE_NONE)
            )
        return resolved

    for map_kind in wanted:
        if map_kind == 'albedo':
            continue
        resolved[map_kind] = _secondary(material, map_kind)
    return resolved


def is_usable(image) -> bool:
    """Whether an image has pixel data we can actually read.

    Images can be present but unloaded -- a missing file, or a datablock whose source
    was removed. Reading ``pixels`` on one returns an empty buffer rather than
    raising, so it has to be checked up front.
    """
    if image is None:
        return False
    try:
        if not image.has_data:
            return False
    except (ReferenceError, AttributeError):
        return False
    return image.size[0] > 0 and image.size[1] > 0


def set_has_data(texture_set: TextureSet, map_kind: str) -> bool:
    """Whether this material contributes anything to ``map_kind``.

    A map where every material returns false is skipped entirely rather than written
    out as a full-size image of one constant. Avatar Toolkit emits all six maps
    unconditionally; most avatars only carry two or three.
    """
    if is_usable(texture_set.image):
        return True
    neutral = NEUTRAL.get(map_kind, WHITE)
    return any(abs(a - b) > 1e-4 for a, b in zip(texture_set.tint, neutral))


def duplicate_key(sets: Dict[str, TextureSet], multiply_diffuse: bool, wanted=MAPS):
    """Grouping key for materials that would produce an identical atlas cell.

    Keyed across *every* enabled map: two materials sharing an albedo texture but
    carrying different normal maps must not collapse into one cell. Keyed on the
    image datablock rather than Material Combiner's ``PackedFile`` identity, which
    forces it to pack every texture into the .blend just to compare them.
    """
    parts = []
    for map_kind in wanted:
        texture_set = sets.get(map_kind)
        if texture_set is None:
            parts.append((map_kind, None))
            continue

        tint = texture_set.tint
        if map_kind == 'albedo' and not multiply_diffuse:
            tint = WHITE
        rounded = tuple(round(channel, 4) for channel in tint)

        if texture_set.image is None:
            parts.append((map_kind, 'colour', rounded))
        else:
            parts.append(
                (map_kind, 'image', texture_set.image.name_full, rounded,
                 texture_set.uv_layer)
            )
    return tuple(parts)
