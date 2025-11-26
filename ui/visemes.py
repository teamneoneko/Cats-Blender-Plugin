# MIT License

import bpy
from .main import ToolPanel, SearchMenuOperatorBase, draw_error_box
from ..tools import common as Common
from ..tools import viseme as Viseme
from ..tools.register import register_wrap
from ..tools.translations import t

@register_wrap
class VisemePanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_viseme_v3'
    bl_label = t('VisemePanel.label')
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        # Mesh selection section
        mesh_count = len(Common.get_meshes_objects(check=False))
        if mesh_count == 0:
            draw_error_box(col, t('VisemePanel.error.noMesh'))
            return
        elif mesh_count > 1:
            row = col.row(align=True)
            row.scale_y = 1.0
            row.prop(context.scene, 'mesh_name_viseme', icon='MESH_DATA')
            col.separator()

        # Viseme settings section
        box = col.box()
        box_col = box.column(align=True)

        # Preview section
        row = box_col.row(align=True)
        row.scale_y = 1.3
        if context.scene.viseme_preview_mode:
            row.operator(Viseme.VisemePreviewOperator.bl_idname, text="Stop Preview", icon='PAUSE')
            row = box_col.row(align=True)
            row.prop(context.scene, "viseme_preview_selection", text="")
        else:
            row.operator(Viseme.VisemePreviewOperator.bl_idname, text="Preview Visemes", icon='PLAY')
        
        box_col.separator()

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
                    row.label(text=t('Scene.mouth_a.label')+":")
                    row.prop_search(context.scene, "mouth_a", mesh.data.shape_keys, "key_blocks", text="")

                    # Mouth O
                    row = box_col.row(align=True)
                    row.scale_y = 1.0
                    row.label(text=t('Scene.mouth_o.label')+":")
                    row.prop_search(context.scene, "mouth_o", mesh.data.shape_keys, "key_blocks", text="")

                    # Mouth CH
                    row = box_col.row(align=True)
                    row.scale_y = 1.0
                    row.label(text=t('Scene.mouth_ch.label')+":")
                    row.prop_search(context.scene, "mouth_ch", mesh.data.shape_keys, "key_blocks", text="")
            except KeyError:
                box_col.label(text=t('VisemePanel.error.noMesh'), icon='ERROR')

        box_col.separator()

        # Shape intensity
        row = box_col.row(align=True)
        row.scale_y = 1.0
        row.prop(context.scene, 'shape_intensity')

        box_col.separator()

        # Auto viseme button
        row = box_col.row(align=True)
        row.scale_y = 1.3
        row.operator(Viseme.AutoVisemeButton.bl_idname, icon='TRIA_RIGHT')
