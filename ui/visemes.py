# MIT License

import bpy
from .main import ToolPanel, draw_error_box, draw_section, draw_wiki_button
from ..tools import common as Common
from ..tools import viseme as Viseme
from ..tools.register import register_wrap
from ..tools.translations import t

WIKI = 'VisemePanel.wikiURL'


@register_wrap
class VisemePanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_viseme_v3'
    bl_label = t('VisemePanel.label')
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 60

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, pad=1.5)

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        # Mesh selection section
        mesh_count = len(Common.get_meshes_objects(check=False))
        if mesh_count == 0:
            draw_error_box(col, t('VisemePanel.error.noMesh'))
            return
        elif mesh_count > 1:
            sec = draw_section(col, t('VisemePanel.meshSection'), 'MESH_DATA')
            row = sec.row(align=True)
            row.scale_y = 1.0
            row.prop(context.scene, 'mesh_name_viseme', text="", icon='MESH_DATA')
            col.separator()

        # Preview section
        preview_col = draw_section(col, t('VisemePanel.previewSection'), 'PLAY',
                                   WIKI, 'preview-controls')
        row = preview_col.row(align=True)
        row.scale_y = 1.3
        if context.scene.viseme_preview_mode:
            row.operator(Viseme.VisemePreviewOperator.bl_idname, text=t('VisemePanel.stopPreview'), icon='PAUSE')
            row = preview_col.row(align=True)
            row.prop(context.scene, "viseme_preview_selection", text="")
        else:
            row.operator(Viseme.VisemePreviewOperator.bl_idname, text=t('VisemePanel.startPreview'), icon='PLAY')

        col.separator()

        # Shape key assignment section
        box_col = draw_section(col, t('VisemePanel.shapeKeysSection'), 'SHAPEKEY_DATA',
                               WIKI, 'shape-key-assignment')

        # Get the mesh for shape key selection
        mesh_name = context.scene.mesh_name_viseme
        if not mesh_name or mesh_name == 'Cats_empty_enum_identifier':
            box_col.label(text=t('VisemePanel.error.noMesh'), icon='ERROR')
        else:
            try:
                mesh = Common.get_objects()[mesh_name]
                if not mesh or not mesh.data.shape_keys:
                    box_col.label(text=t('VisemePanel.error.noShapekeys'), icon='ERROR')
                else:
                    # Mouth A
                    row = box_col.row(align=True)
                    row.scale_y = 1.0
                    split = row.split(factor=0.35, align=True)
                    split.label(text=t('Scene.mouth_a.label')+":")
                    split.prop_search(context.scene, "mouth_a", mesh.data.shape_keys, "key_blocks", text="")

                    # Mouth O
                    row = box_col.row(align=True)
                    row.scale_y = 1.0
                    split = row.split(factor=0.35, align=True)
                    split.label(text=t('Scene.mouth_o.label')+":")
                    split.prop_search(context.scene, "mouth_o", mesh.data.shape_keys, "key_blocks", text="")

                    # Mouth CH
                    row = box_col.row(align=True)
                    row.scale_y = 1.0
                    split = row.split(factor=0.35, align=True)
                    split.label(text=t('Scene.mouth_ch.label')+":")
                    split.prop_search(context.scene, "mouth_ch", mesh.data.shape_keys, "key_blocks", text="")
            except KeyError:
                box_col.label(text=t('VisemePanel.error.noMesh'), icon='ERROR')

        box_col.separator(factor=0.5)

        # Shape intensity
        row = box_col.row(align=True)
        row.scale_y = 1.0
        row.prop(context.scene, 'shape_intensity')

        col.separator()

        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator(Viseme.AutoVisemeButton.bl_idname, icon='TRIA_RIGHT')
