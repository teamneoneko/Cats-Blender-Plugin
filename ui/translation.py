# MIT License

import bpy

from .. import globs
from .main import ToolPanel, draw_section, draw_wiki_button
from ..tools import translate as Translate
from ..tools.register import register_wrap
from ..tools.translations import t

WIKI = 'TranslationPanel.wikiURL'


@register_wrap
class TranslationPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_TranslationPanel_v3'
    bl_label = t('TranslationPanel.label')
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 100

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, pad=1.5)

    def draw(self, context):
        col = self.layout.column(align=True)

        self.draw_service_section(col, context)
        col.separator()
        self.draw_options_section(col, context)
        col.separator()
        self.draw_translate_section(col, context)

    def draw_service_section(self, col, context):
        box_col = draw_section(col, t('TranslationPanel.serviceSection'), 'WORLD',
                               WIKI, 'choosing-a-service')

        # Online provider that fills gaps the internal dictionary can't resolve.
        # Drawn without its property name, the section header already says what it is.
        box_col.prop(context.scene, 'translation_service', text="")

        service = context.scene.translation_service
        if service == 'deepl':
            self.draw_field(box_col, context, 'deepl_api_key', 'Scene.deepl_api_key.label')
        elif service == 'libretranslate':
            self.draw_field(box_col, context, 'libretranslate_url', 'Scene.libretranslate_url.label')
            self.draw_field(box_col, context, 'libretranslate_api_key', 'Scene.libretranslate_api_key.label')
        elif service == 'mymemory':
            self.draw_field(box_col, context, 'mymemory_email', 'Scene.mymemory_email.label')

    @staticmethod
    def draw_field(col, context, prop_name, label_key):
        """Label above a full-width field, service names are too long to sit beside one."""
        col.separator(factor=0.5)
        label_row = col.row(align=True)
        label_row.scale_y = 0.75
        label_row.label(text=t(label_key))
        col.prop(context.scene, prop_name, text="")

    def draw_options_section(self, col, context):
        box_col = draw_section(col, t('TranslationPanel.optionsSection'), 'PREFERENCES',
                               WIKI, 'options')

        box_col.prop(context.scene, 'use_google_only')
        box_col.prop(context.scene, 'skip_locked_shape_keys')

        self.draw_field(box_col, context, 'mmd_english_names_shapekeys', 'Scene.mmd_english_names_shapekeys.label')
        box_col.prop(context.scene, 'mmd_english_names_materials')

    def draw_translate_section(self, col, context):
        box_col = draw_section(col, t('TranslationPanel.translateSection'), 'FONT_DATA',
                               WIKI, 'translate-buttons')

        row = box_col.row(align=True)
        row.scale_y = 1.3
        row.operator(Translate.TranslateAllButton.bl_idname,
                     text=t('OtherOptionsPanel.TranslateAllButton.label'), icon=globs.ICON_ALL)

        # Two per row, a single column of four clips the longer labels
        grid = box_col.column(align=True)
        grid.scale_y = 1.1

        row = grid.row(align=True)
        row.operator(Translate.TranslateShapekeyButton.bl_idname,
                     text=t('OtherOptionsPanel.TranslateShapekeyButton.label'), icon='SHAPEKEY_DATA')
        row.operator(Translate.TranslateBonesButton.bl_idname,
                     text=t('OtherOptionsPanel.TranslateBonesButton.label'), icon='BONE_DATA')

        row = grid.row(align=True)
        row.operator(Translate.TranslateObjectsButton.bl_idname,
                     text=t('OtherOptionsPanel.TranslateObjectsButton.label'), icon='MESH_DATA')
        row.operator(Translate.TranslateMaterialsButton.bl_idname,
                     text=t('OtherOptionsPanel.TranslateMaterialsButton.label'), icon='MATERIAL')
