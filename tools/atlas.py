# MIT License

import bpy
import webbrowser
import addon_utils

from . import common as Common
from .register import register_wrap
from .. import globs
from .translations import t


# addon_name = "Shotariya-don"
# min_version = [1, 1, 6]


@register_wrap
class EnableSMC(bpy.types.Operator):
    bl_idname = 'cats_atlas.enable_smc'
    bl_label = t('EnableSMC.label')
    bl_description = t('EnableSMC.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        # disable all wrong versions
        for mod in addon_utils.modules():
            if mod.bl_info['name'] == "Shotariya-don":
                if addon_utils.check(mod.__name__)[0]:
                    try:
                        bpy.ops.preferences.addon_disable(module=mod.__name__)
                    except:
                        pass
                    continue
            if mod.bl_info['name'] == "Shotariya's Material Combiner":
                if mod.bl_info['version'] < (2, 1, 2, 9) and addon_utils.check(mod.__name__)[0]:
                    try:
                        bpy.ops.preferences.addon_disable(module=mod.__name__)
                    except:
                        pass
                    continue

        # then enable correct version
        for mod in addon_utils.modules():
            if mod.bl_info['name'] == "Shotariya's Material Combiner":
                if mod.bl_info['version'] < (2, 1, 2, 9):
                    continue
                if not addon_utils.check(mod.__name__)[0]:
                    bpy.ops.preferences.addon_enable(module=mod.__name__)
                break
        self.report({'INFO'}, t('EnableSMC.success'))
        return {'FINISHED'}

@register_wrap
class AtlasHelpButton(bpy.types.Operator):
    bl_idname = 'cats_atlas.help'
    bl_label = t('AtlasHelpButton.label')
    bl_description = t('AtlasHelpButton.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        webbrowser.open(t('AtlasHelpButton.URL'))
        self.report({'INFO'}, t('AtlasHelpButton.success'))
        return {'FINISHED'}

@register_wrap
class InstallShotariya(bpy.types.Operator):
    bl_idname = "cats_atlas.install_shotariya_popup"
    bl_label = t('InstallShotariya.label')
    bl_options = {'INTERNAL'}

    action = bpy.props.EnumProperty(
        items=(('INSTALL', '', ''),
               ('ENABLE', '', ''),
               ('VERSION', '', '')))

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        dpi_value = Common.get_user_preferences().system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * 5.3))

    def check(self, context):
        # Important for changing options
        return True

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        if self.action == 'INSTALL':
            row = col.row(align=True)
            row.label(text=t('InstallShotariya.error.install1'))
            row.scale_y = 0.75
            row = col.row(align=True)
            row.scale_y = 0.75
            row.label(text=t('InstallShotariya.error.install2'))
            col.separator()
            row = col.row(align=True)
            row.label(text=t('InstallShotariya.error.install3'))
            row.scale_y = 0.75
            col.separator()
            row = col.row(align=True)
            row.operator(ShotariyaButton.bl_idname, icon=globs.ICON_URL)
            col.separator()

        elif self.action == 'ENABLE':
            row = col.row(align=True)
            row.label(text=t('InstallShotariya.error.enable1'))
            row.scale_y = 0.75
            row = col.row(align=True)
            row.scale_y = 0.75
            row.label(text=t('InstallShotariya.error.enable2'))
            col.separator()
            row = col.row(align=True)
            row.label(text=t('InstallShotariya.error.enable3'))
            row.scale_y = 0.75
            col.separator()

        elif self.action == 'VERSION':
            row = col.row(align=True)
            row.label(text=t('InstallShotariya.error.version1'))
            row.scale_y = 0.75
            row = col.row(align=True)
            row.scale_y = 0.75
            row.label(text=t('InstallShotariya.error.version2'))
            col.separator()
            row = col.row(align=True)
            row.label(text=t('InstallShotariya.error.version3'))
            row.scale_y = 0.75
            col.separator()
            row = col.row(align=True)
            row.operator(ShotariyaButton.bl_idname, icon=globs.ICON_URL)
            col.separator()


@register_wrap
class ShotariyaButton(bpy.types.Operator):
    bl_idname = 'cats_atlas.download_shotariya'
    bl_label = t('ShotariyaButton.label')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        webbrowser.open('https://github.com/teamneoneko/material-combiner-addon/releases/latest')

        self.report({'INFO'}, 'ShotariyaButton.success')
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=500)
    
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="This will open Material Combiner releases:", icon='INFO')
        col.separator()
        col.label(text="https://github.com/teamneoneko/material-combiner-addon/")
        col.label(text="releases/latest")
        col.separator() 
        col.label(text="Click OK to open, or Cancel to visit manually.")
