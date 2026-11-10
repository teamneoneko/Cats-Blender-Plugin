# MIT License

import bpy

from .. import globs
from .. import updater
from .main import ToolPanel, draw_error_box, draw_warning_box, draw_section, draw_wiki_button
from ..tools import common as Common
from ..tools import importer as Importer
from ..tools import iconloader as Iconloader
from ..tools import material as Material
from ..tools import armature as Armature
from ..tools import armature_manual as Armature_manual
from ..tools.register import register_wrap
from ..tools.translations import t

WIKI = 'QuickAccess.wikiURL'


@register_wrap
class QuickAccessPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_quickaccess_v3'
    bl_label = t('QuickAccess.label')
    bl_order = 0

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, pad=1.5)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        # Validate armature selection in case one was deleted
        Common.validate_armature_selection()

        # Update notifications section
        updater.draw_update_notification_panel(col)

        # Version warnings section, only check for dict not found in Blender 5.0 (Blender does a better job at checking versions due to the blender manifest)
        if not globs.dict_found:
            col.separator()
            self.draw_version_warnings(col, context)

        col.separator()

        # Import/Export section
        import_col = draw_section(col, t('QuickAccess.importSection'), 'IMPORT',
                                  WIKI, 'import-model')

        # Main import/export row
        row = import_col.row(align=True)
        row.scale_y = 1.3
        split = row.split(factor=0.85, align=True)
        sub_row = split.row(align=True)
        sub_row.operator(Importer.ImportAnyModel.bl_idname,
                        text=t('QuickAccess.ImportAnyModel.label'),
                        icon='ARMATURE_DATA')
        if len(Common.get_armature_objects()) > 0:
            sub_row.operator(Importer.ExporterModelsPopup.bl_idname,
                           icon='ARMATURE_DATA')
        split.operator(Importer.ModelsPopup.bl_idname, text="", icon='COLLAPSEMENU')

        # Armature selector
        if len(Common.get_armature_objects()) > 1:
            col.separator()
            row = col.row(align=True)
            row.scale_y = 1.0
            row.prop(context.scene, 'armature', icon='ARMATURE_DATA')

        # Quick actions section
        col.separator()
        quick_col = draw_section(col, t('QuickAccess.actionsSection'), 'SHADERFX',
                                 WIKI, 'quick-actions')

        # Material and mesh buttons
        row = quick_col.row(align=True)
        row.scale_y = 1.3
        row.operator(Material.CombineMaterialsButton.bl_idname,
                    text=t('QuickAccess.CombineMats.label'),
                    icon='MATERIAL')
        row.operator(Armature_manual.JoinMeshes.bl_idname,
                    text=t('QuickAccess.JoinMeshes.label'),
                    icon_value=Iconloader.preview_collections["custom_icons"]["mesh"].icon_id)

        # Fix MMD Model section, only for freshly imported MMD / VRM models
        col.separator()
        fix_col = draw_section(col, t('FixArmature.label'), globs.ICON_FIX_MODEL,
                               WIKI, 'fix-mmd-model')
        warn_col = fix_col.column(align=True)
        warn_col.scale_y = 0.7
        warn_col.label(text=t('FixArmature.warnMMDVRM1'), icon='ERROR')
        warn_col.label(text=t('FixArmature.warnMMDVRM2'), icon='BLANK1')
        warn_col.label(text=t('FixArmature.warnMMDVRM3'), icon='BLANK1')
        fix_col.separator(factor=0.5)
        row = fix_col.row(align=True)
        row.scale_y = 1.4
        split = row.split(factor=0.85, align=True)
        split.operator(FixArmatureWarning.bl_idname, icon=globs.ICON_FIX_MODEL)
        split.operator(ModelSettings.bl_idname, text="", icon='MODIFIER')

        # Pose mode section
        col.separator()
        pose_col = draw_section(col, t('QuickAccess.poseSection'), 'POSE_HLT',
                                WIKI, 'pose-mode')

        self.draw_pose_section(pose_col, context)

    def draw_version_warnings(self, col, context):
        # Blender 5.0+ only - just check for dictionary
        if not globs.dict_found:
            draw_error_box(col, [
                t("QuickAccess.warn.noDict1"),
                t("QuickAccess.warn.noDict2"),
                t("QuickAccess.warn.noDict3")
            ])

    def draw_pose_section(self, col, context):
        armature_obj = Common.get_armature()
        
        if not armature_obj or armature_obj.mode != 'POSE':
            row = col.row(align=True)
            row.scale_y = 1.3
            split = row.split(factor=0.85, align=True)
            split.operator(Armature_manual.StartPoseMode.bl_idname, icon='POSE_HLT')
            split.operator(Armature_manual.StartPoseModeNoReset.bl_idname, text="", icon='POSE_HLT')
        else:
            row = col.row(align=True)
            row.scale_y = 1.3
            split = row.split(factor=0.85, align=True)
            split.operator(Armature_manual.StopPoseMode.bl_idname, icon=globs.ICON_POSE_MODE)
            split.operator(Armature_manual.StopPoseModeNoReset.bl_idname, text="", icon=globs.ICON_POSE_MODE)

            if armature_obj and armature_obj.mode == 'POSE':
                col.separator()
                pose_actions = col.column(align=True)
                pose_actions.scale_y = 1.0
                pose_actions.operator(Armature_manual.PoseToShape.bl_idname, icon='SHAPEKEY_DATA')
                pose_actions.operator(Armature_manual.PoseToRest.bl_idname, icon='POSE_HLT')


@register_wrap
class ModelSettings(bpy.types.Operator):
    bl_idname = "cats_armature.settings"
    bl_label = t('ModelSettings.label')
    bl_description = t('ModelSettings.desc')

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        dpi_value = Common.get_user_preferences().system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * 3.25))

    def check(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        settings_col = col.column(align=True)
        settings_col.scale_y = 1.0
        settings_col.active = context.scene.remove_zero_weight
        settings_col.prop(context.scene, 'keep_end_bones')
        settings_col.prop(context.scene, 'keep_upper_chest')
        settings_col.prop(context.scene, 'keep_twist_bones')
        settings_col.prop(context.scene, 'fix_twist_bones')
        settings_col.prop(context.scene, 'join_meshes')
        settings_col.prop(context.scene, 'connect_bones')
        settings_col.prop(context.scene, 'remove_zero_weight')
        settings_col.prop(context.scene, 'remove_rigidbodies_joints')
        col.separator(factor=0.5)
        col.prop(context.scene, 'mmd_english_names_shapekeys')

        col.separator(factor=1.5)

        # Protected bones
        protected_col = col.column(align=True)
        protected_col.label(text=t('Scene.protected_bones.label'), icon='LOCKED')
        protected_col.prop(context.scene, 'protected_bones', text='')
        hint_col = col.column(align=True)
        hint_col.scale_y = 0.7
        hint_col.label(text=t('Scene.protected_bones.hint'), icon='INFO')

        # Warning text
        warning_col = col.column(align=True)
        warning_col.scale_y = 0.7
        warning_col.label(text=t('ModelSettings.warn.fbtFix1'), icon='INFO')
        warning_col.label(text=t('ModelSettings.warn.fbtFix2'), icon_value=Iconloader.preview_collections["custom_icons"]["empty"].icon_id)
        warning_col.label(text=t('ModelSettings.warn.fbtFix3'), icon_value=Iconloader.preview_collections["custom_icons"]["empty"].icon_id)


@register_wrap
class FixArmatureWarning(bpy.types.Operator):
    bl_idname = "cats_armature.fix_armature_warning"
    bl_label = t('FixArmature.label')
    bl_description = t('FixArmature.desc')
    bl_options = {'REGISTER', 'INTERNAL', 'UNDO'}

    def execute(self, context):
        return Armature.FixArmature.execute(self, context)

    def invoke(self, context, event):
        dpi_value = Common.get_user_preferences().system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * 6),
                                                          title=t('FixArmature.warning.dialogTitle'),
                                                          confirm_text=t('FixArmature.warning.confirm'))

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        title_row = col.row(align=True)
        title_row.alert = True
        title_row.scale_y = 1.2
        title_row.label(text=t('FixArmature.warning.title'), icon='ERROR')

        col.separator(factor=0.5)

        draw_error_box(col, [
            t('FixArmature.warning.dontUse1'),
            t('FixArmature.warning.dontUse2'),
            t('FixArmature.warning.dontUse3'),
        ])
        draw_warning_box(col, [
            t('FixArmature.warning.onlyUse1'),
            t('FixArmature.warning.onlyUse2'),
        ], icon='CHECKMARK')
        draw_warning_box(col, [
            t('FixArmature.warning.importer1'),
            t('FixArmature.warning.importer2'),
        ], icon='INFO')

        col.separator(factor=0.5)

        save_row = col.row(align=True)
        save_row.scale_y = 0.9
        save_row.label(text=t('FixArmature.warning.saveFirst'), icon='FILE_TICK')
