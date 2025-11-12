# MIT License

from ..tools.translations import t

class ToolPanel(object):
    bl_label = t('ToolPanel.label')
    bl_idname = '3D_VIEW_TS_vrc'
    bl_category = t('ToolPanel.category')
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'


def layout_split(layout, factor=0.0, align=False):
    return layout.split(factor=factor, align=align)


def add_button_with_small_button(layout, button_1_idname, button_1_icon, button_2_idname, button_2_icon, scale=1):
    row = layout.row(align=True)
    row.scale_y = scale
    subcol = layout_split(row, factor=0, align=True)
    subcol.operator(button_1_idname, icon=button_1_icon)
    subcol = layout_split(row, factor=0, align=True)
    subcol.operator(button_2_idname, text="", icon=button_2_icon)


def draw_warning_box(layout, messages, icon='INFO'):
    """Draw a warning/info box with consistent styling for Blender 5.0"""
    if isinstance(messages, str):
        messages = [messages]
    
    box = layout.box()
    col = box.column(align=True)
    col.scale_y = 0.75
    
    for i, msg in enumerate(messages):
        row = col.row(align=True)
        if i == 0:
            # First line gets alert styling and icon for errors/warnings
            if icon in ('ERROR', 'WARNING'):
                row.alert = True
            row.label(text=msg, icon=icon if i == 0 else 'BLANK1')
        else:
            row.label(text=msg, icon='BLANK1')
    
    return box


def draw_error_box(layout, messages):
    """Draw an error box with alert styling"""
    return draw_warning_box(layout, messages, icon='ERROR')


def draw_info_box(layout, messages):
    """Draw an info box"""
    return draw_warning_box(layout, messages, icon='INFO')