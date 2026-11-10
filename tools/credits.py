# MIT License

import bpy
import webbrowser
from .register import register_wrap
from .translations import t

@register_wrap
class ForumButton(bpy.types.Operator):
    bl_idname = 'cats_credits.forum'
    bl_label = t('ForumButton.label')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        webbrowser.open(t('ForumButton.URL'))

        self.report({'INFO'}, t('ForumButton.success'))
        return {'FINISHED'}


@register_wrap
class HelpButton(bpy.types.Operator):
    bl_idname = 'cats_credits.help'
    bl_label = t('HelpButton.label')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        webbrowser.open(t('HelpButton.URL'))

        self.report({'INFO'}, t('HelpButton.success'))
        return {'FINISHED'}


@register_wrap
class PatchnotesButton(bpy.types.Operator):
    bl_idname = 'cats_credits.patchnotes'
    bl_label = t('PatchnotesButton.label')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        webbrowser.open(t('PatchnotesButton.URL'))

        self.report({'INFO'}, t('PatchnotesButton.success'))
        return {'FINISHED'}
