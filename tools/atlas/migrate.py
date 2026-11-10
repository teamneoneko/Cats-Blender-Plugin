# MIT License
import bpy

from . import props
from ..register import register_wrap
from ..translations import t

# Material Combiner's atlas size enum uses the same identifiers as ours, which is
# deliberate: it makes this mapping a copy rather than a translation table.
_SCENE_MAP = (
    ('smc_size', 'cats_atlas_size_mode'),
    ('smc_size_width', 'cats_atlas_max_width'),
    ('smc_size_height', 'cats_atlas_max_height'),
    ('smc_crop', 'cats_atlas_crop_uv'),
    ('smc_pixel_art', 'cats_atlas_pixel_art'),
    ('smc_diffuse_size', 'cats_atlas_color_size'),
    ('smc_save_path', 'cats_atlas_save_path'),
)


def is_available() -> bool:
    """Whether Material Combiner's properties are registered on this scene."""
    return hasattr(bpy.types.Scene, 'smc_size')


@register_wrap
class CatsAtlasImportSMC(bpy.types.Operator):
    bl_idname = 'cats_atlas.import_smc_settings'
    bl_label = t('CatsAtlas.migrate.label')
    bl_description = t('CatsAtlas.migrate.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return is_available()

    def execute(self, context):
        scene = context.scene
        copied = 0
        notes = []

        for source, target in _SCENE_MAP:
            if not hasattr(scene, source):
                continue
            try:
                setattr(scene, target, getattr(scene, source))
                copied += 1
            except (TypeError, ValueError):
                notes.append(source)

        if getattr(scene, 'smc_save_path', ''):
            scene.cats_atlas_output = 'DISK'

        copied += self._copy_padding(scene, notes)
        copied += self._copy_materials()
        rows = self._copy_selection(scene)

        self.report(
            {'INFO'},
            t(
                'CatsAtlas.migrate.success',
                number=str(copied),
                rows=str(rows),
            ),
        )
        if notes:
            self.report({'WARNING'}, t('CatsAtlas.migrate.notCarried'))
        return {'FINISHED'}

    @staticmethod
    def _copy_padding(scene, notes) -> int:
        gaps = getattr(scene, 'smc_gaps', None)
        if gaps is None:
            return 0
        try:
            scene.cats_atlas_padding = max(0, min(32, int(gaps)))
        except (TypeError, ValueError):
            return 0
        notes.append('smc_gaps')
        return 1

    @staticmethod
    def _copy_materials() -> int:
        copied = 0
        for material in bpy.data.materials:
            settings = props.material_settings(material)
            if settings is None:
                continue
            if hasattr(material, 'smc_diffuse'):
                settings.multiply_diffuse = material.smc_diffuse
                copied += 1
            if hasattr(material, 'smc_size'):
                settings.size_override = material.smc_size
                settings.size_width = material.smc_size_width
                settings.size_height = material.smc_size_height
                copied += 1
        return copied

    @staticmethod
    def _copy_selection(scene) -> int:
        source = getattr(scene, 'smc_ob_data', None)
        if not source:
            return 0

        props.build_list(scene)

        remembered = {}
        for item in source:
            if item.type != props.ITEM_MATERIAL:
                continue
            if not item.ob or not item.mat:
                continue
            remembered[(item.ob.name, item.mat.name)] = (bool(item.used), int(item.layer))

        applied = 0
        for row in scene.cats_atlas_items:
            if row.item_type != props.ITEM_MATERIAL or not row.ob or not row.mat:
                continue
            found = remembered.get((row.ob.name, row.mat.name))
            if found is None:
                continue
            row.include, row.layer = found
            applied += 1
        return applied
