# MIT License

import bpy

from .. import globs
from .. import updater
from .main import ToolPanel
from ..tools import common as Common
from ..tools import armature as Armature
from ..tools import importer as Importer
from ..tools import iconloader as Iconloader
from ..tools import material as Material
from ..tools import eyetracking as Eyetracking
from ..tools import armature_manual as Armature_manual
from ..tools.register import register_wrap
from ..tools.translations import t


@register_wrap
class QuickAccessPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_quickaccess_v3'
    bl_label = t('QuickAccess.label')

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        # Update notifications section
        updater.check_for_update_background(check_on_startup=True)
        updater.draw_update_notification_panel(col)

        # Version warnings section - only check for dict not found in Blender 5.0 (Blender does a better job at checking versions due to the blender manifest)
        if not globs.dict_found:
            col.separator()
            self.draw_version_warnings(col, context)

        col.separator()

        # Import/Export row
        row = col.row(align=True)
        row.scale_y = 1.2
        split = row.split(factor=0.85, align=True)
        sub_row = split.row(align=True)
        sub_row.operator(Importer.ImportAnyModel.bl_idname, 
                        text=t('QuickAccess.ImportAnyModel.label'), 
                        icon='ARMATURE_DATA')
        if len(Common.get_armature_objects()) > 0:
            sub_row.operator(Importer.ExporterModelsPopup.bl_idname, 
                           icon='ARMATURE_DATA')
        split.operator(Importer.ModelsPopup.bl_idname, text="", icon='COLLAPSEMENU')

        # FBX Test Import row
        row = col.row(align=True)
        row.scale_y = 1.0
        row.operator(Importer.ImportFBXTest.bl_idname, 
                    text="Import FBX (Test)", 
                    icon='EXPERIMENTAL')

        # Armature selector
        if len(Common.get_armature_objects()) > 1:
            col.separator()
            row = col.row(align=True)
            row.scale_y = 1.0
            row.prop(context.scene, 'armature', icon='ARMATURE_DATA')

        # Quick actions section
        col.separator()
        box = col.box()
        quick_col = box.column(align=True)
        
        # Info text
        info_col = quick_col.column(align=True)
        info_col.scale_y = 0.75
        info_col.label(text=t("FixLegacy.info1"), icon='INFO')
        info_col.label(text=t("FixLegacy.info2"), icon='BLANK1')

        quick_col.separator()

        # Material and mesh buttons
        row = quick_col.row(align=True)
        row.scale_y = 1.2
        row.operator(Material.CombineMaterialsButton.bl_idname, 
                    text=t('QuickAccess.CombineMats.label'), 
                    icon='MATERIAL')
        row.operator(Armature_manual.JoinMeshes.bl_idname,
                    text=t('QuickAccess.JoinMeshes.label'),
                    icon_value=Iconloader.preview_collections["custom_icons"]["mesh"].icon_id)

        # Pose mode section
        col.separator()
        self.draw_pose_section(col, context)

    def draw_version_warnings(self, col, context):
        # Blender 5.0+ only - just check for dictionary
        if not globs.dict_found:
            self.draw_warning(col, "QuickAccess.warn.noDict", 3)

    def draw_warning(self, col, text_key, lines):
        warning_col = col.column(align=True)
        warning_col.scale_y = 0.75
        
        row = warning_col.row(align=True)
        row.alert = True
        row.label(text=t(f'{text_key}1'), icon='ERROR')
        
        for i in range(2, lines + 1):
            row = warning_col.row(align=True)
            row.label(text=t(f'{text_key}{i}'), icon='BLANK1')

    def draw_pose_section(self, col, context):
        box = col.box()
        box_col = box.column(align=True)
        armature_obj = Common.get_armature()
        
        if not armature_obj or armature_obj.mode != 'POSE':
            row = box_col.row(align=True)
            row.scale_y = 1.2
            split = row.split(factor=0.85, align=True)
            split.operator(Armature_manual.StartPoseMode.bl_idname, icon='POSE_HLT')
            split.operator(Armature_manual.StartPoseModeNoReset.bl_idname, text="", icon='POSE_HLT')
        else:
            row = box_col.row(align=True)
            row.scale_y = 1.2
            split = row.split(factor=0.85, align=True)
            split.operator(Armature_manual.StopPoseMode.bl_idname, icon=globs.ICON_POSE_MODE)
            split.operator(Armature_manual.StopPoseModeNoReset.bl_idname, text="", icon=globs.ICON_POSE_MODE)

            if armature_obj and armature_obj.mode == 'POSE':
                pose_actions = box_col.column(align=True)
                pose_actions.scale_y = 1.0
                pose_actions.operator(Armature_manual.PoseToShape.bl_idname, icon='SHAPEKEY_DATA')
                pose_actions.operator(Armature_manual.PoseToRest.bl_idname, icon='POSE_HLT')
