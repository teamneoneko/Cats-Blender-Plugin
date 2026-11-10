# MIT License

import bpy
import webbrowser

from ..tools.register import register_wrap
from ..tools.translations import t


class ToolPanel(object):
    bl_label = t('ToolPanel.label')
    bl_idname = '3D_VIEW_TS_vrc'
    bl_category = t('ToolPanel.category')
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'


class SearchMenuOperatorBase(object):
    """Base class for search menu operators that set scene properties."""
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    bl_property = "my_enum"
    scene_property = None  # Override in subclass
    
    def execute(self, context):
        if self.scene_property:
            setattr(context.scene, self.scene_property, self.my_enum)
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}


def layout_split(layout, factor=0.0, align=False):
    return layout.split(factor=factor, align=align)


def add_button_with_small_button(layout, button_1_idname, button_1_icon, button_2_idname, button_2_icon, scale=1):
    row = layout.row(align=True)
    row.scale_y = scale
    subcol = layout_split(row, factor=0, align=True)
    subcol.operator(button_1_idname, icon=button_1_icon)
    subcol = layout_split(row, factor=0, align=True)
    subcol.operator(button_2_idname, text="", icon=button_2_icon)


def draw_section(col, label=None, icon='NONE', wiki_page=None, wiki_section='', hint=None):
    """Boxed section with an optional small header row, returns its column."""
    box_col = col.box().column(align=True)
    if label:
        header_row = box_col.row(align=True)
        header_row.scale_y = 0.75
        if wiki_page:
            split = header_row.split(factor=0.9, align=True)
            split.label(text=label, icon=icon)
            draw_wiki_button(split, wiki_page, wiki_section)
        else:
            header_row.label(text=label, icon=icon)

        if hint:
            hint_col = box_col.column(align=True)
            hint_col.scale_y = 0.7
            hint_col.label(text=hint, icon='INFO')

        # Keep the title off the first button
        box_col.separator(factor=0.3)
    return box_col


@register_wrap
class CatsWikiButton(bpy.types.Operator):
    bl_idname = 'cats_wiki.open'
    bl_label = t('CatsWikiButton.label')
    bl_description = t('CatsWikiButton.desc')
    bl_options = {'REGISTER', 'INTERNAL'}

    url: bpy.props.StringProperty(default='')

    def execute(self, context):
        webbrowser.open(self.url)
        self.report({'INFO'}, t('CatsWikiButton.success'))
        return {'FINISHED'}


def draw_wiki_button(layout, url_key, section='', pad=0.0):
    """Small "?" linking to the wiki page for this panel or section."""
    url = t(url_key)
    if section:
        url += '#' + section

    row = layout.row(align=True)
    row.emboss = 'NONE'
    row.operator(CatsWikiButton.bl_idname, text="?", icon='NONE').url = url
    if pad:
        row.separator(factor=pad)


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


# Export commonly used classes and functions for easy import
__all__ = [
    'ToolPanel',
    'SearchMenuOperatorBase',
    'layout_split',
    'add_button_with_small_button',
    'draw_section',
    'draw_wiki_button',
    'draw_warning_box',
    'draw_error_box',
    'draw_info_box',
]
