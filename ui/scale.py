# MIT License

import bpy

from .main import ToolPanel, draw_error_box, draw_wiki_button
from ..tools.scaler import draw_ui as draw_scaler_ui

from ..tools.translations import t
from ..tools.register import register_wrap

WIKI = 'ScalingPanel.wikiURL'


@register_wrap
class ScalingPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_scale_v2'
    bl_label = t('ScalingPanel.label')
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 80

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, pad=1.5)

    def draw(self, context):
        layout = self.layout
        try:
            draw_scaler_ui(context, layout)
        except Exception as e:
            draw_error_box(layout.column(align=True), ["Error loading scaling panel", str(e)])
