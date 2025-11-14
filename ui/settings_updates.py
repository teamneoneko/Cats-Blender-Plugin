# MIT License

import bpy

from .. import globs
from .. import updater
from .main import ToolPanel, layout_split
from ..tools import settings as Settings
from ..tools.register import register_wrap
from ..tools.translations import t, DownloadTranslations

@register_wrap
class UpdaterPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_updater_v3'
    bl_label = t('UpdaterPanel.label')
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        box = layout.box()

        # Settings section
        settings_box = box.box()
        settings_col = settings_box.column(align=True)
        
        header_row = settings_col.row(align=True)
        header_row.scale_y = 0.75
        header_row.label(text=t('UpdaterPanel.name'), icon=globs.ICON_SETTINGS)
        
        settings_col.separator()

        # General settings
        row = settings_col.row(align=True)
        row.prop(context.scene, 'embed_textures')
        
        row = settings_col.row(align=True)
        row.prop(context.scene, 'remove_rigidbodies_joints_global')
        
        row = settings_col.row(align=True)
        row.prop(context.scene, "export_translate_csv")
        
        row = settings_col.row(align=True)
        path = context.scene.custom_translate_csv_export_dir if context.scene.custom_translate_csv_export_dir else default_cats_dir
        row.prop(context.scene, "custom_translate_csv_export_dir")

        settings_col.separator()

        # Language settings
        lang_row = settings_col.row(align=True)
        lang_split = layout_split(lang_row, factor=0.56)
        lang_split.label(text=t('Scene.ui_lang.label') + ':')
        lang_split.prop(context.scene, 'ui_lang', text='')

        # Dev branch options
        if globs.dev_branch:
            settings_col.separator()
            row = settings_col.row(align=True)
            row.operator(DownloadTranslations.bl_idname)

        settings_col.separator()

        # Debug options
        debug_box = box.box()
        debug_col = debug_box.column(align=True)
        
        row = debug_col.row(align=True)
        row.scale_y = 0.75
        row.operator(Settings.ResetGoogleDictButton.bl_idname, icon='X')
        
        if globs.dev_branch:
            row = debug_col.row(align=True)
            row.scale_y = 0.75
            row.operator(Settings.DebugTranslations.bl_idname, icon='X')

        # Settings changed warning
        if Settings.settings_changed():
            warning_box = box.box()
            warning_col = warning_box.column(align=True)
            
            row = warning_col.row(align=True)
            row.scale_y = 0.75
            row.label(text=t('UpdaterPanel.requireRestart1'), icon='ERROR')
            
            row = warning_col.row(align=True)
            row.scale_y = 0.75
            row.label(text=t('UpdaterPanel.requireRestart2'), icon='BLANK1')
            
            row = warning_col.row(align=True)
            row.operator(Settings.RevertChangesButton.bl_idname, icon='RECOVER_LAST')

        # Updater section
        updater_box = box.box()
        updater.draw_updater_panel(context, updater_box)

