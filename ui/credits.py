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

        # Version info section with custom icon
        version_box = box.box()
        row = version_box.row(align=True)
        row.scale_y = 1.2
        row.label(text=t('CreditsPanel.desc1') + globs.version_str + ')', 
                 icon_value=Iconloader.preview_collections["custom_icons"]["cats1"].icon_id)

        # Current maintainers info
        info_box = box.box()
        info_col = info_box.column(align=True)
        info_col.scale_y = 0.9
        info_col.label(text=t('CreditsPanel.maintainers1'))
        info_col.label(text=t('CreditsPanel.maintainers2'))

        # Contributors section
        contrib_box = box.box()
        contrib_col = contrib_box.column(align=True)
        contrib_col.scale_y = 0.9
        contrib_col.label(text=t('CreditsPanel.desc4'))
        contrib_col.label(text=t('CreditsPanel.descContributors'))
        contrib_col.label(text=t('CreditsPanel.descContributors2'))

        # Original creators
        desc_box = box.box()
        desc_col = desc_box.column(align=True)
        desc_col.scale_y = 0.9
        desc_col.label(text=t('CreditsPanel.originalCreators'))

        box.separator(factor=0.5)

        # Action buttons
        actions_col = box.column(align=True)
        
        help_row = actions_col.row(align=True)
        help_row.scale_y = 1.4
        help_row.operator(Credits.HelpButton.bl_idname, 
                    icon_value=Iconloader.preview_collections["custom_icons"]["help1"].icon_id)
        
        support_row = actions_col.row(align=True)
        support_row.scale_y = 1.4
        support_row.operator(Credits.SupportButton.bl_idname, icon='HEART')
        
        patch_row = actions_col.row(align=True)
        patch_row.scale_y = 1.2
        patch_row.operator(Credits.PatchnotesButton.bl_idname, icon='WORDWRAP_ON')

