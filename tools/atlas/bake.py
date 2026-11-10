# MIT License
"""Cycles baking for materials a direct texture copy cannot resolve.

Opt-in per material. Copying a texture out of a node graph only works when there is
a texture to copy; a material built from procedural nodes, mixed layers, or vertex
colours has no single image that represents it. Baking renders the material as it
actually shades and atlases the result, which is the one thing Material Combiner
structurally cannot do.

Two limits worth knowing, both surfaced in the UI:

* **Cycles has no metallic or height bake pass.** Those two maps stay copy-only
  whatever the toggle says.
* **Baking uses the material's existing UV layout.** Mirrored geometry is fine --
  overlapping islands mean last-write-wins, which is the desired result there -- but
  genuinely overlapping distinct islands will fight over the same pixels.

Every render setting this module touches is restored, including on failure.
"""

import contextlib

import bpy

from . import compose, detect, maps, sample
from .. import colorspace

TEMP_NODE_LABEL = 'Cats Atlas Bake Target'
TEMP_IMAGE_PREFIX = 'Cats_Bake_'


class BakeError(Exception):
    """Raised when baking cannot proceed, with a message fit for the UI."""


@contextlib.contextmanager
def _bake_settings(scene, samples, margin):
    """Apply bake render settings, and put every one of them back afterwards.

    Restoring matters more than usual here: these are the user's own render
    settings, and a build that left the engine on Cycles with one sample would look
    like Cats had broken their scene.
    """
    render = scene.render
    bake = render.bake
    cycles = getattr(scene, 'cycles', None)

    saved = {
        'engine': render.engine,
        'target': bake.target,
        'use_pass_direct': bake.use_pass_direct,
        'use_pass_indirect': bake.use_pass_indirect,
        'use_pass_color': bake.use_pass_color,
        'use_selected_to_active': bake.use_selected_to_active,
        'margin': bake.margin,
        'use_clear': bake.use_clear,
    }
    saved_cycles = {}
    if cycles is not None:
        for name in ('samples', 'device', 'use_adaptive_sampling'):
            if hasattr(cycles, name):
                saved_cycles[name] = getattr(cycles, name)

    try:
        render.engine = 'CYCLES'
        bake.target = 'IMAGE_TEXTURES'
        bake.use_selected_to_active = False
        bake.use_clear = True
        bake.margin = max(0, int(margin))
        if cycles is not None:
            if 'samples' in saved_cycles:
                cycles.samples = max(1, int(samples))
            if 'device' in saved_cycles:
                # CPU is the only device guaranteed to exist. A headless CI runner
                # has no GPU, and falling back mid-bake is not something Cycles
                # does gracefully.
                cycles.device = 'CPU'
            if 'use_adaptive_sampling' in saved_cycles:
                cycles.use_adaptive_sampling = False
        yield bake
    finally:
        render.engine = saved['engine']
        bake.target = saved['target']
        bake.use_pass_direct = saved['use_pass_direct']
        bake.use_pass_indirect = saved['use_pass_indirect']
        bake.use_pass_color = saved['use_pass_color']
        bake.use_selected_to_active = saved['use_selected_to_active']
        bake.margin = saved['margin']
        bake.use_clear = saved['use_clear']
        for name, value in saved_cycles.items():
            setattr(cycles, name, value)


@contextlib.contextmanager
def _selection(view_layer, objects):
    """Make ``objects`` the only selected objects, the first one active, then restore."""
    previous_active = view_layer.objects.active
    previous_selected = [o for o in view_layer.objects if o.select_get()]

    try:
        for other in previous_selected:
            other.select_set(False)
        for obj in objects:
            try:
                obj.select_set(True)
            except RuntimeError as error:
                # Raised for objects outside the view layer, e.g. in an excluded collection
                raise BakeError('{} cannot be baked: {}'.format(obj.name, error))
        view_layer.objects.active = objects[0]
        yield
    finally:
        for obj in objects:
            try:
                obj.select_set(False)
            except RuntimeError:
                pass
        for other in previous_selected:
            try:
                other.select_set(True)
            except RuntimeError:
                pass
        view_layer.objects.active = previous_active


def _temp_image(material, map_kind, size):
    """A fresh bake target, sized square and tagged with the map's colorspace."""
    name = '{}{}_{}'.format(TEMP_IMAGE_PREFIX, material.name, map_kind)
    existing = bpy.data.images.get(name)
    if existing is not None:
        bpy.data.images.remove(existing)

    image = bpy.data.images.new(
        name=name, width=size, height=size, alpha=True, float_buffer=False
    )
    colorspace.set_role(image, maps.SPECS[map_kind].colorspace)
    return image


def _add_target_node(material, image):
    """Add an image texture node and make it the material's active bake target.

    Every material on the object needs one, not just the ones being baked: Cycles
    refuses the whole bake with "No active image found" if any material used by the
    object lacks a target.
    """
    tree = material.node_tree
    node = tree.nodes.new('ShaderNodeTexImage')
    node.image = image
    node.label = TEMP_NODE_LABEL
    node.location = (-900, -900)
    for other in tree.nodes:
        other.select = False
    node.select = True
    tree.nodes.active = node
    return node


def _remove_target_nodes(nodes_by_material):
    for material, node in nodes_by_material.items():
        try:
            material.node_tree.nodes.remove(node)
        except (ReferenceError, RuntimeError):
            pass


def _configure_pass(bake_settings, bake_type):
    """Set the pass flags that make each bake type mean what we want.

    DIFFUSE with direct and indirect left on bakes lighting into the albedo, which
    is never wanted for an atlas -- the result would have the scene's lamps burned
    into the avatar's skin.
    """
    if bake_type == 'DIFFUSE':
        bake_settings.use_pass_direct = False
        bake_settings.use_pass_indirect = False
        bake_settings.use_pass_color = True


def bake_object(context, obj, materials, wanted, size, samples, margin):
    """Bake one object's flagged materials. See :func:`bake_objects`."""
    return bake_objects(context, {obj: materials}, wanted, size, samples, margin)


def bake_objects(context, materials_by_object, wanted, size, samples, margin):
    """Bake the flagged materials of several objects into fresh images.

    All objects are baked together in one pass per map, so a material used on
    several objects gets one image holding every object's faces. Baking them one
    at a time would leave only the last object's faces in it.

    Args:
        context: Current context, for the view layer.
        materials_by_object: ``{mesh object: [materials that opted into baking]}``.
        wanted: Map kinds the build is generating.
        size: Square bake resolution in pixels.
        samples: Cycles samples.
        margin: Bake margin in pixels, normally the atlas padding.

    Returns:
        ``{material_name: {map_kind: Image}}`` for the materials that baked.

    Raises:
        BakeError: If any of the objects cannot be baked at all.
    """
    objects = list(materials_by_object)
    for obj in objects:
        if obj.type != 'MESH':
            raise BakeError('{} is not a mesh'.format(obj.name))
        if not obj.data.uv_layers:
            raise BakeError('{} has no UV map to bake into'.format(obj.name))

    passes = [(k, maps.SPECS[k].bake_pass) for k in wanted if maps.SPECS[k].bake_pass]
    if not objects or not passes:
        return {}

    scene = context.scene
    view_layer = context.view_layer
    materials = {m for flagged in materials_by_object.values() for m in flagged}
    all_materials = list(dict.fromkeys(
        slot.material for obj in objects for slot in obj.material_slots if slot.material
    ))
    targets = {m.name: {} for m in materials}

    with _bake_settings(scene, samples, margin) as bake_settings:
        with _selection(view_layer, objects):
            for map_kind, bake_type in passes:
                _configure_pass(bake_settings, bake_type)

                # Every material on the object needs a target or Cycles refuses the
                # whole bake, but only the flagged ones produce an image we keep.
                nodes = {}
                images = {}
                for material in all_materials:
                    images[material] = _temp_image(material, map_kind, size)
                    nodes[material] = _add_target_node(material, images[material])

                failure = None
                try:
                    bpy.ops.object.bake(
                        type=bake_type,
                        use_clear=True,
                        margin=max(0, int(margin)),
                    )
                except RuntimeError as error:
                    failure = error
                finally:
                    _remove_target_nodes(nodes)

                for material, image in images.items():
                    if failure is None and material in materials:
                        targets[material.name][map_kind] = image
                    else:
                        bpy.data.images.remove(image)

                if failure is not None:
                    cleanup(targets)
                    raise BakeError('{} bake failed on {}: {}'.format(
                        map_kind, ', '.join(obj.name for obj in objects), failure
                    ))

    return targets


def is_neutral_bake(image, map_kind) -> bool:
    """Whether a baked map came out as nothing but its neutral value."""
    if map_kind == 'albedo':
        # Albedo drives the layout and is always generated, and its alpha is real
        # data rather than coverage.
        return False

    canvas = sample.CACHE.read(image)
    if canvas is None:
        return True
    return compose.canvas_is_neutral(canvas, maps.NEUTRAL[map_kind][:3], atol=1.0 / 255.0)


def texture_sets_from_bake(baked, wanted):
    """Turn baked images into the TextureSet shape the rest of the pipeline expects.

    Maps Cycles cannot bake fall back to the neutral rather than to the material's
    own graph: mixing a baked albedo with a copied metallic would silently combine
    two different interpretations of the same material.
    """
    sets = {}
    for map_kind in wanted:
        image = baked.get(map_kind)
        if image is not None and not is_neutral_bake(image, map_kind):
            sets[map_kind] = detect.TextureSet(
                image, detect.WHITE, '', detect.CONFIDENCE_HIGH
            )
        else:
            sets[map_kind] = detect.TextureSet(
                None, maps.NEUTRAL[map_kind], '', detect.CONFIDENCE_NONE
            )
    return sets


def cleanup(baked_by_material):
    """Remove every temporary bake image once the atlas has been composed."""
    for baked_maps in baked_by_material.values():
        for image in baked_maps.values():
            try:
                bpy.data.images.remove(image)
            except (ReferenceError, RuntimeError):
                pass
