# MIT License
import bpy
from bpy.props import BoolProperty, IntProperty, PointerProperty

from ..register import register_wrap
from ..translations import t

# Row kinds in the combine list. Mirrors Material Combiner's integer `type` field so
# a migrated selection maps across without translation.
ITEM_OBJECT = 0
ITEM_MATERIAL = 1
ITEM_SEPARATOR = 2

# Names given to generated atlases. Defined here rather than in build.py because
# build_list needs them to recognise a previous run's output.
ATLAS_IMAGE_PREFIX = 'Cats_Atlas_'
ATLAS_MATERIAL_PREFIX = 'Cats_Atlas_Mat_'

MIN_DIMENSION = 8
MAX_DIMENSION = 8192


@register_wrap
class CatsAtlasItem(bpy.types.PropertyGroup):
    """One row of the combine list: an object header, a material, or a separator."""

    ob: PointerProperty(
        name=t('CatsAtlas.item.ob.label'),
        description=t('CatsAtlas.item.ob.desc'),
        type=bpy.types.Object,
    )

    ob_id: IntProperty(
        name=t('CatsAtlas.item.ob_id.label'),
        description=t('CatsAtlas.item.ob_id.desc'),
        default=0,
    )

    mat: PointerProperty(
        name=t('CatsAtlas.item.mat.label'),
        description=t('CatsAtlas.item.mat.desc'),
        type=bpy.types.Material,
    )

    item_type: IntProperty(
        name=t('CatsAtlas.item.item_type.label'),
        description=t('CatsAtlas.item.item_type.desc'),
        default=ITEM_MATERIAL,
    )

    include: BoolProperty(
        name=t('CatsAtlas.item.include.label'),
        description=t('CatsAtlas.item.include.desc'),
        default=True,
    )

    layer: IntProperty(
        name=t('CatsAtlas.item.layer.label'),
        description=t('CatsAtlas.item.layer.desc'),
        min=1,
        max=99,
        default=1,
    )

    low_confidence: BoolProperty(
        name=t('CatsAtlas.item.low_confidence.label'),
        description=t('CatsAtlas.item.low_confidence.desc'),
        default=False,
    )


@register_wrap
class CatsAtlasMaterialSettings(bpy.types.PropertyGroup):
    """Per-material atlas settings, reached as ``material.cats_atlas``.

    Grouped rather than added flat to ``bpy.types.Material`` so unregistering removes
    one attribute instead of six, and so a future settings dump can serialise the
    group whole.
    """

    bake: BoolProperty(
        name=t('CatsAtlas.mat.bake.label'),
        description=t('CatsAtlas.mat.bake.desc'),
        default=False,
    )

    multiply_diffuse: BoolProperty(
        name=t('CatsAtlas.mat.multiply_diffuse.label'),
        description=t('CatsAtlas.mat.multiply_diffuse.desc'),
        default=True,
    )

    size_override: BoolProperty(
        name=t('CatsAtlas.mat.size_override.label'),
        description=t('CatsAtlas.mat.size_override.desc'),
        default=False,
    )

    size_width: IntProperty(
        name=t('CatsAtlas.mat.size_width.label'),
        description=t('CatsAtlas.mat.size_width.desc'),
        min=MIN_DIMENSION,
        max=MAX_DIMENSION // 2,
        default=2048,
    )

    size_height: IntProperty(
        name=t('CatsAtlas.mat.size_height.label'),
        description=t('CatsAtlas.mat.size_height.desc'),
        min=MIN_DIMENSION,
        max=MAX_DIMENSION // 2,
        default=2048,
    )


def _is_low_confidence(material) -> bool:
    """Whether this material's albedo was only found by a fallback sweep.

    A low-confidence result usually means the graph is not a plain image feeding
    Base Color procedural, heavily mixed, or vertex coloured, which is exactly
    the case baking exists for. The list hints at it so the user can flip the bake
    toggle instead of discovering the problem in the finished atlas.
    """
    from . import detect

    if material is None:
        return False
    return detect.albedo(material).confidence == detect.CONFIDENCE_LOW


def material_settings(material):
    """Settings group for a material, or ``None`` before registration completes."""
    return getattr(material, 'cats_atlas', None)


def build_list(scene) -> int:
    """Rebuild the combine list from the meshes currently in the scene.

    Selections already made are preserved by ``(object name, material name)``, so
    refreshing after adding a mesh does not reset the user's choices.

    Returns:
        Number of material rows in the rebuilt list.
    """
    previous = {}
    for item in scene.cats_atlas_items:
        if item.item_type == ITEM_MATERIAL and item.ob and item.mat:
            previous[(item.ob.name, item.mat.name)] = (item.include, item.layer)

    scene.cats_atlas_items.clear()

    material_rows = 0
    ob_id = 0
    for ob in sorted(scene.objects, key=lambda o: o.name.lower()):
        if ob.type != 'MESH' or not ob.data.materials:
            continue

        materials = [slot.material for slot in ob.material_slots if slot.material]
        if not materials:
            continue

        header = scene.cats_atlas_items.add()
        header.item_type = ITEM_OBJECT
        header.ob = ob
        header.ob_id = ob_id
        header.include = True

        seen = set()
        for material in materials:
            if material.name in seen:
                continue
            seen.add(material.name)

            row = scene.cats_atlas_items.add()
            row.item_type = ITEM_MATERIAL
            row.ob = ob
            row.ob_id = ob_id
            row.mat = material
            row.low_confidence = _is_low_confidence(material)
            remembered = previous.get((ob.name, material.name))
            if remembered:
                row.include, row.layer = remembered
            else:
                row.include = not material.name.startswith(ATLAS_MATERIAL_PREFIX)
                row.layer = 1
            material_rows += 1

        ob_id += 1

    scene.cats_atlas_active = 0
    return material_rows


def active_material(scene):
    """The material on the highlighted list row, or ``None`` on a header row."""
    items = scene.cats_atlas_items
    index = scene.cats_atlas_active
    if not 0 <= index < len(items):
        return None
    item = items[index]
    if item.item_type != ITEM_MATERIAL:
        return None
    return item.mat


def selected_materials(scene):
    layers = {}
    for item in scene.cats_atlas_items:
        if item.item_type != ITEM_MATERIAL or not item.include:
            continue
        if not item.ob or not item.mat:
            continue
        if item.ob.name not in bpy.data.objects:
            continue
        by_object = layers.setdefault(item.layer, {})
        by_object.setdefault(item.ob, [])
        if item.mat not in by_object[item.ob]:
            by_object[item.ob].append(item.mat)
    return layers
