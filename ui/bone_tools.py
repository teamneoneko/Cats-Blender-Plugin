# MIT License

import bpy

from .main import ToolPanel, draw_section, draw_wiki_button
from ..tools import armature_manual as Armature_manual
from ..tools.register import register_wrap
from ..tools.translations import t

WIKI = 'BoneToolsPanel.wikiURL'


@register_wrap
class BoneToolsPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_BoneToolsPanel_v3'
    bl_label = t('BoneToolsPanel.label')
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 40

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, pad=1.5)

    def draw(self, context):
        col = self.layout.column(align=True)

        box_col = draw_section(col, t('BoneToolsPanel.digitigradeSection'), 'OUTLINER_DATA_ARMATURE',
                               WIKI, 'create-digitigrade-legs',
                               hint=t('BoneToolsPanel.digitigradeSection.hint'))
        row = box_col.row(align=True)
        row.operator(Armature_manual.CreateDigitigradeLegs.bl_idname, icon='OUTLINER_DATA_ARMATURE')

        col.separator()

        box_col = draw_section(col, t('BoneToolsPanel.twistSection'), 'CONSTRAINT_BONE',
                               WIKI, 'generate-twist-bones',
                               hint=t('BoneToolsPanel.twistSection.hint'))
        row = box_col.row(align=True)
        row.operator(Armature_manual.GenerateTwistBones.bl_idname, icon='OUTLINER_DATA_ARMATURE')
        box_col.prop(context.scene, 'generate_twistbones_upper')
