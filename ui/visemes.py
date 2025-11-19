# MIT License

import bpy
from .main import ToolPanel, SearchMenuOperatorBase, draw_error_box
from ..tools import common as Common
from ..tools import viseme as Viseme
from ..tools.register import register_wrap
from ..tools.translations import t

@register_wrap
class SearchMenuOperatorMouthA(bpy.types.Operator):
    bl_description = t('Scene.mouth_a.desc')
    bl_idname = "scene.search_menu_mouth_a"
    bl_label = ""
    bl_property = "my_enum"
    
    my_enum: bpy.props.EnumProperty(
        name="shapekeys",
        description=t('Scene.mouth_a.desc'),
        items=Common.get_shapekeys_mouth_ah,
    )

    def execute(self, context):
        context.scene.mouth_a = self.my_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

@register_wrap
class SearchMenuOperatorMouthO(bpy.types.Operator):
    bl_description = t('Scene.mouth_o.desc')
    bl_idname = "scene.search_menu_mouth_o"
    bl_label = ""
    bl_property = "my_enum"
    
    my_enum: bpy.props.EnumProperty(
        name="shapekeys",
        description=t('Scene.mouth_o.desc'),
        items=Common.get_shapekeys_mouth_oh,
    )

    def execute(self, context):
        context.scene.mouth_o = self.my_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

@register_wrap
class SearchMenuOperatorMouthCH(bpy.types.Operator):
    bl_description = t('Scene.mouth_ch.desc')
    bl_idname = "scene.search_menu_mouth_ch"
    bl_label = ""
    bl_property = "my_enum"
    
    my_enum: bpy.props.EnumProperty(
        name="shapekeys",
        description=t('Scene.mouth_ch.desc'),
        items=Common.get_shapekeys_mouth_ch,
    )

    def execute(self, context):
        context.scene.mouth_ch = self.my_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

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

        # Mouth A
        row = box_col.row(align=True)
        row.scale_y = 1.0
        row.label(text=t('Scene.mouth_a.label')+":")
        mouth_a_text = 'None' if Common.is_enum_empty(context.scene.mouth_a) else context.scene.mouth_a
        row.operator(SearchMenuOperatorMouthA.bl_idname, text=mouth_a_text, icon='SHAPEKEY_DATA')

        # Mouth O
        row = box_col.row(align=True)
        row.scale_y = 1.0
        row.label(text=t('Scene.mouth_o.label')+":")
        mouth_o_text = 'None' if Common.is_enum_empty(context.scene.mouth_o) else context.scene.mouth_o
        row.operator(SearchMenuOperatorMouthO.bl_idname, text=mouth_o_text, icon='SHAPEKEY_DATA')

        # Mouth CH
        row = box_col.row(align=True)
        row.scale_y = 1.0
        row.label(text=t('Scene.mouth_ch.label')+":")
        mouth_ch_text = 'None' if Common.is_enum_empty(context.scene.mouth_ch) else context.scene.mouth_ch
        row.operator(SearchMenuOperatorMouthCH.bl_idname, text=mouth_ch_text, icon='SHAPEKEY_DATA')

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
