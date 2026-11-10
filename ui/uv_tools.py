# MIT License

import bpy

from .main import ToolPanel, draw_section, draw_wiki_button
from ..tools import uv_tools as UVTools
from ..tools.register import register_wrap
from ..tools.translations import t

WIKI = 'UVToolsPanel.wikiURL'


def draw_seam_path(layout):
    """Draw the Find Shortest Seam Path button + hint. Shared by both panels since
    the tool works on the 3D mesh and doesn't need the UV editor context."""
    col = draw_section(layout, t('UVToolsPanel.seamPath.section'), 'EDGESEL',
                       WIKI, 'find-shortest-seam-path')

    row = col.row(align=True)
    row.scale_y = 1.3
    row.operator(UVTools.FindShortestSeamPath.bl_idname,
                 text=t('UVToolsPanel.seamPath.label'), icon='EDGESEL')

    hint = col.column(align=True)
    hint.scale_y = 0.8
    hint.label(text=t('UVToolsPanel.seamPath.hint'), icon='INFO')


@register_wrap
class UVToolsPanel(ToolPanel, bpy.types.Panel):
    # Lives in the UV/Image editor (not the 3D view) because the align tool reads
    # the UV editor's selection state and 2D cursor.
    bl_idname = 'IMAGE_EDITOR_PT_CatsUVToolsPanel'
    bl_label = t('UVToolsPanel.label')
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_order = 0

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, pad=1.5)

    def draw(self, context):
        col = self.layout.column(align=True)

        align_col = draw_section(col, t('UVToolsPanel.alignEdges.section'), 'ARROW_LEFTRIGHT',
                                 WIKI, 'align-uv-edges-to-target')
        row = align_col.row(align=True)
        row.scale_y = 1.3
        row.operator(UVTools.AlignUVEdgesToTarget.bl_idname,
                     text=t('UVToolsPanel.alignEdges.label'), icon='ARROW_LEFTRIGHT')

        hint = align_col.column(align=True)
        hint.scale_y = 0.8
        hint.label(text=t('UVToolsPanel.alignEdges.hint'), icon='INFO')

        col.separator()

        draw_seam_path(col)


@register_wrap
class UVToolsPanelView3D(ToolPanel, bpy.types.Panel):
    # Mirror of the seam-path tool in the 3D View N-panel.
    bl_idname = 'VIEW3D_PT_CatsUVToolsPanel'
    bl_label = t('UVToolsPanel.label')
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 90

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, pad=1.5)

    def draw(self, context):
        col = self.layout.column(align=True)
        draw_seam_path(col)
