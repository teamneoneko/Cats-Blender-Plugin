# MIT License

import bpy
import webbrowser

from .. import globs
from .. import updater
from .main import ToolPanel, draw_info_box
from ..tools import common as Common
from ..tools import armature as Armature
from ..tools import importer as Importer
from ..tools import iconloader as Iconloader
from ..tools import eyetracking as Eyetracking
from ..tools import armature_manual as Armature_manual
from ..tools import material as Material
from ..tools.register import register_wrap
from ..tools.translations import t

@register_wrap
class MMDOptions(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_mmdoptions_stuff'
    bl_label = t('MMDOptions.label')
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        box = layout.box()
        col = box.column(align=True)

        # Info section
        draw_info_box(col, [
            t("MMDOptions.info1"),
            t("MMDOptions.info2"),
            t("MMDOptions.info3"),
            t("MMDOptions.info4"),
            t("MMDOptions.info5"),
            t("MMDOptions.info6")
        ])
        
        col.separator()

        # Fix Model section
        row = col.row(align=True)
        row.scale_y = 1.3
        split = row.split(factor=0.85, align=True)
        split.operator(FixArmatureWarning.bl_idname, icon=globs.ICON_FIX_MODEL)
        split.operator(ModelSettings.bl_idname, text="", icon='MODIFIER')

        col.separator()

        # Rigidbodies section
        draw_info_box(col, [
            t("MMDOptions.RemoveRigidBodiesManaulInfo1"),
            t("MMDOptions.RemoveRigidBodiesManaulInfo2")
        ])
        
        col.separator()

        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator(Armature_manual.RemoveRigidbodiesJointsOperator.bl_idname, icon='RIGID_BODY')

        col.separator()

        # Help section
        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator(MMDOptionswiki.bl_idname, icon_value=Iconloader.preview_collections["custom_icons"]["help1"].icon_id)

@register_wrap
class MMDOptionswiki(bpy.types.Operator):
    bl_idname = 'mmdoptionwiki_read.help'
    bl_label = t('MMDOptionswiki.label')
    bl_description = t('MMDOptionswiki.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        webbrowser.open(t('MMDOptionswiki.URL'))
        self.report({'INFO'}, t('MMDOptionswiki.success'))
        return {'FINISHED'}

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

        col.separator(factor=1.5)

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
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * 5.2))

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        
        warning_col = col.column(align=True)
        warning_col.scale_y = 1.0
        warning_col.label(text=t('FixArmature.warning.line1'))
        warning_col.label(text=t('FixArmature.warning.line2'))
        warning_col.label(text=t('FixArmature.warning.line3'))
        warning_col.label(text=t('FixArmature.warning.line4'))
        warning_col.label(text=t('FixArmature.warning.line5'))
