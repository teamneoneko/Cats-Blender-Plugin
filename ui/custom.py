# MIT License

import bpy

from .main import ToolPanel, SearchMenuOperatorBase, draw_info_box
from .. import globs
from ..tools import common as Common
from ..tools import iconloader as Iconloader
from ..tools import armature_bones as Armature_bones
from ..tools import armature_custom as Armature_custom
from ..tools.register import register_wrap
from ..tools.translations import t


@register_wrap
class SearchMenuOperator_merge_armature_into(SearchMenuOperatorBase, bpy.types.Operator):
    bl_description = t('Scene.merge_armature_into.desc')
    bl_idname = "scene.search_menu_merge_armature_into"
    bl_label = ""
    scene_property = "merge_armature_into"

    my_enum: bpy.props.EnumProperty(
        name=t('Scene.merge_armature_into.label'),
        description=t('Scene.merge_armature_into.desc'),
        items=Common.wrap_dynamic_enum_items(Common.get_armature_list, bl_idname, is_holder=False),
    )

@register_wrap
class SearchMenuOperator_merge_armature(SearchMenuOperatorBase, bpy.types.Operator):
    bl_description = t('Scene.merge_armature.desc')
    bl_idname = "scene.search_menu_merge_armature"
    bl_label = t('Scene.root_bone.label')
    scene_property = "merge_armature"

    my_enum: bpy.props.EnumProperty(
        name=t('Scene.merge_armature.label'),
        description=t('Scene.merge_armature.desc'),
        items=Common.wrap_dynamic_enum_items(Common.get_armature_merge_list, bl_idname, is_holder=False),
    )

@register_wrap
class SearchMenuOperator_attach_to_bone(SearchMenuOperatorBase, bpy.types.Operator):
    bl_description = t('Scene.attach_to_bone.desc')
    bl_idname = "scene.search_menu_attach_to_bone"
    bl_label = ""
    scene_property = "attach_to_bone"

    my_enum: bpy.props.EnumProperty(
        name=t('Scene.attach_to_bone.label'),
        description=t('Scene.attach_to_bone.desc'),
        items=Common.wrap_dynamic_enum_items(Common.get_bones_merge, bl_idname, sort=False, is_holder=False),
    )

@register_wrap
class SearchMenuOperator_attach_mesh(SearchMenuOperatorBase, bpy.types.Operator):
    bl_description = t('Scene.attach_mesh.desc')
    bl_idname = "scene.search_menu_attach_mesh"
    bl_label = ""
    scene_property = "attach_mesh"

    my_enum: bpy.props.EnumProperty(
        name=t('Scene.attach_mesh.label'),
        description=t('Scene.attach_mesh.desc'),
        items=Common.wrap_dynamic_enum_items(Common.get_top_meshes, bl_idname, is_holder=False),
    )

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

@register_wrap
class CustomPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_custom_v3'
    bl_label = t('CustomPanel.label')
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        # Tutorial button
        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator(Armature_custom.CustomModelTutorialButton.bl_idname, icon='FORWARD')


@register_wrap
class MergeArmatureSubPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_custom_armature_v3'
    bl_label = t('CustomPanel.armature.label')
    bl_parent_id = 'VIEW3D_PT_custom_v3'
    bl_options = set()

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        self.draw_armature_section(col, context)

    def draw_armature_section(self, col, context):
        if len(Common.get_armature_objects()) <= 1:
            draw_info_box(col, t('CustomPanel.warn.twoArmatures'))
            return

        col.separator()

        # Settings
        box = col.box()
        box_col = box.column(align=True)
        box_col.scale_y = 0.85
        
        box_col.prop(context.scene, 'merge_same_bones')
        box_col.prop(context.scene, 'apply_transforms')
        box_col.prop(context.scene, 'merge_armatures_join_meshes')
        box_col.prop(context.scene, 'merge_armatures_remove_zero_weight_bones')
        box_col.prop(context.scene, 'merge_armatures_cleanup_shape_keys')

        col.separator()

        # Merge selection
        box = col.box()
        box_col = box.column(align=True)
        box_col.scale_y = 1.0

        row = box_col.row(align=True)
        row.label(text=t('CustomPanel.mergeInto'))
        row.operator(SearchMenuOperator_merge_armature_into.bl_idname,
                    text=context.scene.merge_armature_into, 
                    icon=globs.ICON_MOD_ARMATURE)

        row = box_col.row(align=True)
        row.label(text=t('CustomPanel.toMerge'))
        row.operator(SearchMenuOperator_merge_armature.bl_idname,
                    text=context.scene.merge_armature, 
                    icon_value=Iconloader.preview_collections["custom_icons"]["UP_ARROW"].icon_id)

        # Bone attachment if needed
        if not context.scene.merge_same_bones:
            found = False
            base_armature = Common.get_armature(armature_name=context.scene.merge_armature_into)
            merge_armature = Common.get_armature(armature_name=context.scene.merge_armature)
            
            if merge_armature:
                for bone in Armature_bones.dont_delete_these_main_bones:
                    if 'Eye' not in bone and bone in merge_armature.pose.bones and bone in base_armature.pose.bones:
                        found = True
                        break

            if not found:
                row = box_col.row(align=True)
                row.label(text=t('CustomPanel.attachToBone'))
                row.operator(SearchMenuOperator_attach_to_bone.bl_idname, 
                           text=context.scene.attach_to_bone, 
                           icon='BONE_DATA')
            else:
                row = box_col.row(align=True)
                row.label(text=t('CustomPanel.armaturesCanMerge'))

        col.separator()

        # Merge button
        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator(Armature_custom.MergeArmature.bl_idname, icon='ARMATURE_DATA')


@register_wrap
class AttachMeshSubPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_custom_mesh_v3'
    bl_label = t('CustomPanel.mesh.label')
    bl_parent_id = 'VIEW3D_PT_custom_v3'
    bl_options = set()

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        self.draw_mesh_section(col, context)

    def draw_mesh_section(self, col, context):
        if len(Common.get_armature_objects()) == 0 or len(Common.get_meshes_objects(mode=1, check=False)) == 0:
            draw_info_box(col, [
                t('CustomPanel.warn.noArmOrMesh1'),
                t('CustomPanel.warn.noArmOrMesh2')
            ])
            return

        col.separator()

        # Settings
        box = col.box()
        box_col = box.column(align=True)
        box_col.scale_y = 0.85
        box_col.prop(context.scene, 'merge_armatures_join_meshes')

        col.separator()

        # Merge selection
        box = col.box()
        box_col = box.column(align=True)
        box_col.scale_y = 1.0

        row = box_col.row(align=True)
        row.label(text=t('CustomPanel.mergeInto'))
        row.operator(SearchMenuOperator_merge_armature_into.bl_idname,
                    text=context.scene.merge_armature_into, 
                    icon=globs.ICON_MOD_ARMATURE)

        row = box_col.row(align=True)
        row.label(text=t('CustomPanel.attachMesh2'))
        row.operator(SearchMenuOperator_attach_mesh.bl_idname,
                    text=context.scene.attach_mesh,
                    icon_value=Iconloader.preview_collections["custom_icons"]["UP_ARROW"].icon_id)

        row = box_col.row(align=True)
        row.label(text=t('CustomPanel.attachToBone'))
        row.operator(SearchMenuOperator_attach_to_bone.bl_idname,
                    text=context.scene.attach_to_bone,
                    icon='BONE_DATA')

        col.separator()

        # Attach button
        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator(Armature_custom.AttachMesh.bl_idname, icon='MESH_DATA')
