# MIT License

import bpy

from .. import globs
from .main import ToolPanel, draw_error_box, draw_warning_box
from .main import add_button_with_small_button, draw_section, draw_wiki_button
from ..tools import common as Common
from ..tools import atlas as Atlas
from ..tools import material as Material
from ..tools import bonemerge as Bonemerge
from ..tools import rootbone as Rootbone
from ..tools import armature as Armature
from ..tools import armature_manual as Armature_manual
from ..tools import shapekey as Shapekey

from ..tools.atlas import props as AtlasProps
from ..tools.atlas import migrate as AtlasMigrate
from ..tools.register import register_wrap
from ..tools.translations import t


WIKI = 'OptimizePanel.wikiURL'


@register_wrap
class CATS_UL_atlas_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index=0, filter_flag=0):
        row = layout.row(align=True)

        if item.item_type == AtlasProps.ITEM_OBJECT:
            if item.ob:
                row.label(text=item.ob.name, icon='OUTLINER_OB_MESH')
            return

        if not item.mat:
            row.label(text='', icon='ERROR')
            return

        row.separator(factor=1.5)
        row.prop(item, 'include', text='')

        if item.mat.preview:
            row.label(text='', icon_value=item.mat.preview.icon_id)
        else:
            row.label(text='', icon='MATERIAL')

        name_row = row.row(align=True)
        name_row.enabled = item.include
        name_row.label(text=item.mat.name)

        settings = AtlasProps.material_settings(item.mat)
        if item.low_confidence and not (settings and settings.bake):
            hint = row.row(align=True)
            hint.alert = True
            hint.label(text='', icon='ERROR')

        if settings is not None:
            bake_col = row.row(align=True)
            bake_col.enabled = item.include
            bake_col.prop(
                settings, 'bake', text='',
                icon='RENDER_STILL' if settings.bake else 'RENDERLAYERS',
            )

        layer_col = row.column(align=True)
        layer_col.scale_x = 0.4
        layer_col.enabled = item.include
        layer_col.prop(item, 'layer', text='')


@register_wrap
class OptimizePanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_optimize_v3'
    bl_label = t('OptimizePanel.label')
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 20

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, pad=1.5)

    def draw(self, context):
        pass


@register_wrap
class MaterialSubPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_optimize_material_v3'
    bl_label = t('OptimizePanel.material.label')
    bl_parent_id = 'VIEW3D_PT_optimize_v3'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 0

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, 'materials')

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        try:
            ops_col = col.column(align=True)
            ops_col.scale_y = 1.3
            ops_col.operator(Material.CombineMaterialsButton.bl_idname, icon='MATERIAL')
            ops_col.operator(Material.ConvertAllToPngButton.bl_idname, icon='IMAGE_RGB_ALPHA')

        except Exception as e:
            draw_error_box(col, ["Error loading material operations", str(e)])


@register_wrap
class MeshSubPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_optimize_mesh_v3'
    bl_label = t('OptimizePanel.mesh.label')
    bl_parent_id = 'VIEW3D_PT_optimize_v3'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 1

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, 'mesh-cleanup')

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        try:
            # Join
            box_col = draw_section(col, t('OtherOptionsPanel.joinMeshes'), 'AUTOMERGE_ON')
            row = box_col.row(align=True)
            row.scale_y = 1.3
            row.operator(Armature_manual.JoinMeshes.bl_idname, text=t('OtherOptionsPanel.JoinMeshes.label'))
            row.operator(Armature_manual.JoinMeshesSelected.bl_idname, text=t('OtherOptionsPanel.JoinMeshesSelected.label'))

            col.separator()

            # Separate
            box_col = draw_section(col, t('OtherOptionsPanel.separateBy'), 'MESH_DATA')
            row = box_col.row(align=True)
            row.scale_y = 1.3
            row.operator(Armature_manual.SeparateByMaterials.bl_idname, text=t('OtherOptionsPanel.SeparateByMaterials.label'))
            row.operator(Armature_manual.SeparateByLooseParts.bl_idname, text=t('OtherOptionsPanel.SeparateByLooseParts.label'))
            row.operator(Armature_manual.SeparateByShapekeys.bl_idname, text=t('OtherOptionsPanel.SeparateByShapekeys.label'))

            col.separator()

            # Remove doubles
            box_col = draw_section(col, t('OptimizePanel.removeDoubles'), 'X')
            box_col.prop(context.scene, 'remove_doubles_threshold')
            row = box_col.row(align=True)
            row.scale_y = 1.3
            row.operator(Armature_manual.RemoveDoubles.bl_idname, icon='X')

            col.separator()

            # Normals
            box_col = draw_section(col, t('OtherOptionsPanel.normals'), 'SNAP_NORMAL')
            row = box_col.row(align=True)
            row.scale_y = 1.3
            row.operator(Armature_manual.RecalculateNormals.bl_idname, text=t('OtherOptionsPanel.RecalculateNormals.label'))
            row.operator(Armature_manual.FlipNormals.bl_idname, text=t('OtherOptionsPanel.FlipNormals.label'))

            col.separator()

            # Transforms
            box_col = draw_section(col, t('OptimizePanel.transforms'), 'ORIENTATION_GLOBAL')
            add_button_with_small_button(box_col, Armature_manual.ApplyTransformations.bl_idname, 'OUTLINER_DATA_ARMATURE',
                                         Armature_manual.ApplyAllTransformations.bl_idname, globs.ICON_ALL, scale=1.3)

        except Exception as e:
            draw_error_box(col, ["Error loading mesh operations", str(e)])


@register_wrap
class ShapekeySubPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_optimize_shapekeys_v3'
    bl_label = t('OptimizePanel.shapekeys.label')
    bl_parent_id = 'VIEW3D_PT_optimize_v3'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 2

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, 'shape-keys')

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        try:
            ops_col = col.column(align=True)
            ops_col.scale_y = 1.3
            ops_col.operator(Shapekey.ShapeKeyPruner.bl_idname, icon='SHAPEKEY_DATA')
            ops_col.operator(Armature_manual.RepairShapekeys.bl_idname, icon='MESH_DATA')
            ops_col.operator(Armature_manual.OptimizeStaticShapekeys.bl_idname, icon='MESH_DATA')

        except Exception as e:
            draw_error_box(col, ["Error loading shape key operations", str(e)])


@register_wrap
class BoneMergingSubPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_optimize_bonemerging_v3'
    bl_label = t('OptimizePanel.bonemerging.label')
    bl_parent_id = 'VIEW3D_PT_optimize_v3'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 3

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, 'bones-weights')

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        self.draw_bone_merging_section(col, context)

    def draw_bone_merging_section(self, col, context):
        try:
            # Merge bones box
            box_col = draw_section(col, t('OptimizePanel.mergeBones'), 'AUTOMERGE_ON',
                                   hint=t('OptimizePanel.mergeBones.hint'))

            if len(Common.get_meshes_objects(check=False)) > 1:
                row = box_col.row(align=True)
                row.scale_y = 1.0
                row.prop(context.scene, 'merge_mesh')
            
            box_col.prop(context.scene, 'merge_bone')
            box_col.prop(context.scene, 'merge_ratio')
            
            # Actions row
            actions_row = box_col.row(align=True)
            actions_row.scale_y = 1.3
            actions_row.operator(Rootbone.RefreshRootButton.bl_idname, icon='FILE_REFRESH')
            actions_row.operator(Bonemerge.BoneMergeButton.bl_idname, icon='AUTOMERGE_ON')
            
            col.separator()

            # Weights box
            box_col = draw_section(col, t('OtherOptionsPanel.mergeWeights'), 'BONE_DATA')

            ops_row = box_col.row(align=True)
            ops_row.scale_y = 1.3
            ops_row.operator(Armature_manual.MergeWeights.bl_idname, text=t('OtherOptionsPanel.MergeWeights.label'))
            ops_row.operator(Armature_manual.MergeWeightsToActive.bl_idname, text=t('OtherOptionsPanel.MergeWeightsToActive.label'))
            
            # Options
            options_col = box_col.column(align=True)
            options_col.scale_y = 0.85
            options_col.separator()
            options_col.prop(context.scene, 'keep_merged_bones')
            options_col.prop(context.scene, 'merge_visible_meshes_only')
            
            col.separator()

            # Delete operations box
            box_col = draw_section(col, t('OtherOptionsPanel.delete'), 'X')

            # Two per row, three of these labels never fit side by side
            ops_col = box_col.column(align=True)
            ops_col.scale_y = 1.3
            row = ops_col.row(align=True)
            row.operator(Armature_manual.RemoveZeroWeightBones.bl_idname, text=t('OtherOptionsPanel.RemoveZeroWeightBones.label'))
            row.operator(Armature_manual.RemoveConstraints.bl_idname, text=t('OtherOptionsPanel.RemoveConstraints'))
            row = ops_col.row(align=True)
            row.operator(Armature_manual.RemoveZeroWeightGroups.bl_idname, text=t('OtherOptionsPanel.RemoveZeroWeightGroups'))
            
            options_col = box_col.column(align=True)
            options_col.scale_y = 0.85
            options_col.separator()
            options_col.prop(context.scene, "delete_zero_weight_keep_twists")
            options_col.prop(context.scene, "delete_zero_weight_keep_empty_parents")
            options_col.prop(context.scene, "delete_zero_weight_skip_hidden_bones")
            options_col.separator()
            prot_lbl = options_col.row(align=True)
            prot_lbl.scale_y = 0.75
            prot_lbl.label(text=t('Scene.protected_bones.label'), icon='LOCKED')
            options_col.prop(context.scene, "protected_bones", text="")

            report_col = box_col.column(align=True)
            report_col.scale_y = 1.1
            report_col.separator()
            report_col.operator(Armature.ShowBoneChangeReport.bl_idname, icon='INFO')

            col.separator()

            # Extra operations box
            box_col = draw_section(col, t('OptimizePanel.boneExtras'), 'BONE_DATA')
            ops_col = box_col.column(align=True)
            ops_col.scale_y = 1.3
            ops_col.operator(Armature_manual.DuplicateBonesButton.bl_idname, icon='GROUP_BONE')
            ops_col.operator(Armature_manual.ConnectBonesButton.bl_idname, icon='CONSTRAINT_BONE')
            
        except Exception as e:
            draw_error_box(col, ["Error loading bone merging operations", str(e)])


@register_wrap
class AtlasNewSubPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_optimize_atlas_new_v3'
    bl_label = t('OptimizePanel.atlasNew.label')
    bl_parent_id = 'VIEW3D_PT_optimize_v3'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 5

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, 'atlas-generation')

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        try:
            self.draw_builtin_section(col, context)
        except Exception as e:
            draw_error_box(col, ["Error loading atlas generator", str(e)])

    def draw_builtin_section(self, col, context):
        scene = context.scene

        # Scene properties are registered after the panel classes, so a redraw can
        # land in between during a reload.
        if not hasattr(scene, 'cats_atlas_items'):
            draw_error_box(col, t('OptimizePanel.builtinUnavailable'))
            return

        box_col = draw_section(col, t('OptimizePanel.builtinMaterials'), 'MATERIAL')

        if scene.cats_atlas_items:
            box_col.template_list(
                'CATS_UL_atlas_list', 'cats_atlas_list',
                scene, 'cats_atlas_items',
                scene, 'cats_atlas_active',
                rows=10,
            )

        refresh_col = box_col.column(align=True)
        refresh_col.scale_y = 1.3
        refresh_col.operator(
            Atlas.CatsAtlasRefreshList.bl_idname,
            text=t('CatsAtlas.refresh.update') if scene.cats_atlas_items
            else t('CatsAtlas.refresh.generate'),
            icon='FILE_REFRESH',
        )

        active_mat = AtlasProps.active_material(scene)
        settings = AtlasProps.material_settings(active_mat)
        if settings is not None:
            box_col.separator()
            mat_col = box_col.column(align=True)
            mat_col.label(text=active_mat.name, icon='MATERIAL')
            mat_col.prop(settings, 'multiply_diffuse')
            mat_col.prop(settings, 'size_override')
            size_row = mat_col.row(align=True)
            size_row.enabled = settings.size_override
            size_row.prop(settings, 'size_width')
            size_row.prop(settings, 'size_height')

        col.separator()

        box_col = draw_section(col, t('OptimizePanel.builtinSettings'), globs.ICON_SETTINGS)
        box_col.prop(scene, 'cats_atlas_size_mode')
        size_row = box_col.row(align=True)
        size_row.prop(scene, 'cats_atlas_max_width')
        size_row.prop(scene, 'cats_atlas_max_height')
        box_col.prop(scene, 'cats_atlas_padding')
        box_col.prop(scene, 'cats_atlas_color_size')
        box_col.prop(scene, 'cats_atlas_max_tiles')

        options_col = box_col.column(align=True)
        options_col.scale_y = 0.85
        options_col.separator()
        options_col.prop(scene, 'cats_atlas_crop_uv')
        options_col.prop(scene, 'cats_atlas_pixel_art')
        options_col.prop(scene, 'cats_atlas_remap_all_uv_layers')
        options_col.prop(scene, 'cats_atlas_remove_originals')

        col.separator()

        box_col = draw_section(col, t('OptimizePanel.builtinMaps'), 'IMAGE_RGB_ALPHA',
                               hint=t('OptimizePanel.builtinMaps.hint'))
        maps_col = box_col.column(align=True)
        maps_col.prop(scene, 'cats_atlas_map_normal')
        maps_col.prop(scene, 'cats_atlas_map_emission')
        maps_col.prop(scene, 'cats_atlas_map_roughness')
        maps_col.prop(scene, 'cats_atlas_map_metallic')
        maps_col.prop(scene, 'cats_atlas_map_ao')
        maps_col.prop(scene, 'cats_atlas_map_height')

        box_col.separator()
        pack_row = box_col.row(align=True)
        pack_row.enabled = scene.cats_atlas_map_metallic and scene.cats_atlas_map_roughness
        pack_row.prop(scene, 'cats_atlas_pack_metallic_smoothness')
        box_col.prop(scene, 'cats_atlas_secondary_scale')

        col.separator()

        baking = any(
            row.item_type == AtlasProps.ITEM_MATERIAL
            and row.include
            and getattr(AtlasProps.material_settings(row.mat), 'bake', False)
            for row in scene.cats_atlas_items
        )
        box_col = draw_section(col, t('OptimizePanel.builtinBake'), 'RENDER_STILL',
                               hint=t('OptimizePanel.builtinBake.hint'))
        bake_col = box_col.column(align=True)
        bake_col.enabled = baking
        bake_col.prop(scene, 'cats_atlas_bake_size')
        bake_col.prop(scene, 'cats_atlas_bake_samples')

        if baking:
            draw_warning_box(box_col, [
                t('OptimizePanel.bakeOverlapWarn1'),
                t('OptimizePanel.bakeOverlapWarn2'),
                t('OptimizePanel.bakeOverlapWarn3'),
            ], icon='INFO')

        col.separator()

        box_col = draw_section(col, t('OptimizePanel.builtinOutput'), globs.ICON_EXPORT)
        box_col.prop(scene, 'cats_atlas_output')
        if scene.cats_atlas_output == 'DISK':
            box_col.prop(scene, 'cats_atlas_save_path', text='')

        if AtlasMigrate.is_available():
            box_col.separator()
            migrate_row = box_col.row(align=True)
            migrate_row.scale_y = 1.1
            migrate_row.operator(Atlas.CatsAtlasImportSMC.bl_idname, icon='IMPORT')

        col.separator()

        actions = col.column(align=True)
        actions.scale_y = 1.3
        actions.operator(
            Atlas.CatsAtlasBuild.bl_idname,
            text=t('CatsAtlas.dryRun.label'),
            icon='VIEWZOOM',
        ).dry_run = True
        actions.operator(
            Atlas.CatsAtlasBuild.bl_idname,
            text=t('CatsAtlas.build.run'),
            icon='TEXTURE',
        ).dry_run = False
