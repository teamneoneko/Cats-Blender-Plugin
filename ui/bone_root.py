# MIT License

import bpy

from .main import ToolPanel, draw_section, draw_wiki_button
from ..tools import rootbone as Rootbone
from ..tools.register import register_wrap
from ..tools.translations import t
from ..tools.common import enum_display_text, wrap_dynamic_enum_items

WIKI = 'BoneRootPanel.wikiURL'


@register_wrap
class SearchMenuOperator_root_bone(bpy.types.Operator):
    bl_description = t('Scene.root_bone.desc')
    bl_idname = "scene.search_menu_root_bone"
    bl_label = ""
    bl_property = "my_enum"

    my_enum: bpy.props.EnumProperty(
        name=t('Scene.root_bone.label'),
        description=t('Scene.root_bone.desc'),
        # get_parent_root_bones caches results so the wrapper cannot run in-place
        items=wrap_dynamic_enum_items(
            Rootbone.get_parent_root_bones, 'my_enum', sort=False, in_place=False, is_holder=False
        ),
    )

    def execute(self, context):
        context.scene.root_bone = self.my_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}


@register_wrap
class BoneRootPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_boneroot_v3'
    bl_label = t('BoneRootPanel.label')
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 50

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, pad=1.5)

    def draw(self, context):
        col = self.layout.column(align=True)

        box_col = draw_section(col, t('BoneRootPanel.rootSection'), 'BONE_DATA',
                               WIKI, 'root-bone-selection',
                               hint=t('BoneRootPanel.rootSection.hint'))

        # Root bone selection
        row = box_col.row(align=True)
        row.scale_y = 1.3
        row.operator(SearchMenuOperator_root_bone.bl_idname,
                     text=enum_display_text(context.scene.root_bone, t('BoneRootPanel.noRootBones')),
                     icon='BONE_DATA')

        box_col.separator(factor=0.5)

        # Action buttons
        row = box_col.row(align=True)
        row.scale_y = 1.3
        row.operator(Rootbone.RefreshRootButton.bl_idname, icon='FILE_REFRESH')
        row.operator(Rootbone.RootButton.bl_idname, icon='TRIA_RIGHT')

