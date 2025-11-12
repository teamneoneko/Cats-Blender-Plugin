# MIT License

import bpy

from .. import globs
from .main import ToolPanel
from ..tools import iconloader as Iconloader
from ..tools import credits as Credits
from ..tools.register import register_wrap
from ..tools.translations import t

@register_wrap
class CreditsPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_credits_v3'
    bl_label = t('CreditsPanel.label')

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column(align=True)

        # Version info section with custom icon
        row = col.row(align=True)
        row.scale_y = 1.0
        row.label(text=t('CreditsPanel.desc1') + globs.version_str + ')', 
                 icon_value=Iconloader.preview_collections["custom_icons"]["cats1"].icon_id)

        col.separator()

        # Current maintainers info
        info_col = col.column(align=True)
        info_col.scale_y = 0.85
        info_col.label(text=t('CreditsPanel.maintainers1'))
        info_col.label(text=t('CreditsPanel.maintainers2'))

        col.separator()

        # Contributors section
        contrib_col = col.column(align=True)
        contrib_col.scale_y = 0.85
        contrib_col.label(text=t('CreditsPanel.desc4'))
        contrib_col.label(text=t('CreditsPanel.descContributors'))
        contrib_col.label(text=t('CreditsPanel.descContributors2'))

        col.separator()

        # Original creators
        desc_col = col.column(align=True)
        desc_col.scale_y = 0.85
        desc_col.label(text=t('CreditsPanel.originalCreators'))

        col.separator()

        # Action buttons
        actions_col = col.column(align=True)
        
        help_row = actions_col.row(align=True)
        help_row.scale_y = 1.3
        help_row.operator(Credits.HelpButton.bl_idname, 
                    icon_value=Iconloader.preview_collections["custom_icons"]["help1"].icon_id)
        
        support_row = actions_col.row(align=True)
        support_row.scale_y = 1.3
        support_row.operator(Credits.SupportButton.bl_idname, icon='HEART')
        
        patch_row = actions_col.row(align=True)
        patch_row.scale_y = 1.0
        patch_row.operator(Credits.PatchnotesButton.bl_idname, icon='WORDWRAP_ON')

