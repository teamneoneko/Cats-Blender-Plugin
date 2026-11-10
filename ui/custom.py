# MIT License

import bpy

from .main import ToolPanel, draw_info_box, draw_section, draw_wiki_button
from .. import globs
from ..tools import common as Common
from ..tools import iconloader as Iconloader
from ..tools import armature_bones as Armature_bones
from ..tools import armature_custom as Armature_custom
from ..tools.register import register_wrap
from ..tools.translations import t

WIKI = 'CustomPanel.wikiURL'


@register_wrap
class SearchMenuOperator_merge_armature_into(bpy.types.Operator):
    bl_description = t('Scene.merge_armature_into.desc')
    bl_idname = "scene.search_menu_merge_armature_into"
    bl_label = ""
    bl_property = "my_enum"

    my_enum: bpy.props.EnumProperty(
        name=t('Scene.merge_armature_into.label'),
        description=t('Scene.merge_armature_into.desc'),
        items=Common.wrap_dynamic_enum_items(Common.get_armature_list, 'my_enum', sort=False, in_place=False, is_holder=False),
    )

    def execute(self, context):
        context.scene.merge_armature_into = self.my_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

@register_wrap
class SearchMenuOperator_merge_armature(bpy.types.Operator):
    bl_description = t('Scene.merge_armature.desc')
    bl_idname = "scene.search_menu_merge_armature"
    bl_label = t('Scene.root_bone.label')
    bl_property = "my_enum"

    my_enum: bpy.props.EnumProperty(
        name=t('Scene.merge_armature.label'),
        description=t('Scene.merge_armature.desc'),
        items=Common.wrap_dynamic_enum_items(Common.get_armature_merge_list, 'my_enum', sort=False, in_place=False, is_holder=False),
    )

    def execute(self, context):
        context.scene.merge_armature = self.my_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

@register_wrap
class SearchMenuOperator_attach_to_bone(bpy.types.Operator):
    bl_description = t('Scene.attach_to_bone.desc')
    bl_idname = "scene.search_menu_attach_to_bone"
    bl_label = ""
    bl_property = "my_enum"

    my_enum: bpy.props.EnumProperty(
        name=t('Scene.attach_to_bone.label'),
        description=t('Scene.attach_to_bone.desc'),
        items=Common.wrap_dynamic_enum_items(Common.get_bones_merge, 'my_enum', sort=False, in_place=False, is_holder=False),
    )

    def execute(self, context):
        context.scene.attach_to_bone = self.my_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

@register_wrap
class SearchMenuOperator_attach_mesh(bpy.types.Operator):
    bl_description = t('Scene.attach_mesh.desc')
    bl_idname = "scene.search_menu_attach_mesh"
    bl_label = ""
    bl_property = "my_enum"

    my_enum: bpy.props.EnumProperty(
        name=t('Scene.attach_mesh.label'),
        description=t('Scene.attach_mesh.desc'),
        items=Common.wrap_dynamic_enum_items(Common.get_top_meshes, 'my_enum', sort=False, in_place=False, is_holder=False),
    )

    def execute(self, context):
        context.scene.attach_mesh = self.my_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

@register_wrap
class CustomPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_custom_v3'
    bl_label = t('CustomPanel.label')
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 10

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, pad=1.5)

    def draw(self, context):
        # Parent panel is just a container for sub-panels
        pass


@register_wrap
class MergeArmatureSubPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_custom_armature_v3'
    bl_label = t('CustomPanel.armature.label')
    bl_parent_id = 'VIEW3D_PT_custom_v3'
    bl_options = set()
    bl_order = 0

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, 'armature-mode')

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        self.draw_armature_section(col, context)

    def draw_armature_section(self, col, context):
        if len(Common.get_armature_objects()) <= 1:
            draw_info_box(col, t('CustomPanel.warn.twoArmatures'))
            return

        # Settings
        settings_col = draw_section(col, t('CustomPanel.settingsSection'), 'PREFERENCES').column(align=True)
        settings_col.scale_y = 0.75

        settings_col.prop(context.scene, 'merge_same_bones')
        settings_col.prop(context.scene, 'apply_transforms')
        settings_col.prop(context.scene, 'merge_armatures_join_meshes')
        settings_col.prop(context.scene, 'merge_armatures_remove_zero_weight_bones')
        settings_col.prop(context.scene, 'merge_armatures_cleanup_shape_keys')

        col.separator()

        # Merge selection
        box_col = draw_section(col, t('CustomPanel.selectionSection'), 'RESTRICT_SELECT_OFF').column(align=True)
        box_col.scale_y = 1.0

        # Get safe enum values for display (handles integer indices in Blender 5.0)
        merge_into_name = Common.get_enum_property_value(context.scene, 'merge_armature_into', Common.get_armature_list)
        merge_armature_name = Common.get_enum_property_value(context.scene, 'merge_armature', Common.get_armature_merge_list)

        row = box_col.row(align=True)
        row.label(text=t('CustomPanel.mergeInto'))
        row.operator(SearchMenuOperator_merge_armature_into.bl_idname,
                    text=Common.enum_display_text(merge_into_name, t('CustomPanel.selectArmature')), 
                    icon=globs.ICON_MOD_ARMATURE)

        row = box_col.row(align=True)
        row.label(text=t('CustomPanel.toMerge'))
        row.operator(SearchMenuOperator_merge_armature.bl_idname,
                    text=Common.enum_display_text(merge_armature_name, t('CustomPanel.selectArmature')), 
                    icon_value=Iconloader.preview_collections["custom_icons"]["UP_ARROW"].icon_id)

        # Bone attachment if needed
        if not context.scene.merge_same_bones:
            found = False
            base_armature = Common.get_armature(armature_name=merge_into_name)
            merge_armature = Common.get_armature(armature_name=merge_armature_name)
            
            if merge_armature and base_armature:
                for bone in Armature_bones.dont_delete_these_main_bones:
                    if 'Eye' not in bone and bone in merge_armature.pose.bones and bone in base_armature.pose.bones:
                        found = True
                        break

            if not found:
                attach_bone_name = Common.get_enum_property_value(context.scene, 'attach_to_bone', Common.get_bones_merge)
                row = box_col.row(align=True)
                row.label(text=t('CustomPanel.attachToBone'))
                row.operator(SearchMenuOperator_attach_to_bone.bl_idname, 
                           text=Common.enum_display_text(attach_bone_name, t('CustomPanel.selectBone')), 
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
    bl_order = 1

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, 'mesh-mode')

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

        # Settings
        settings_col = draw_section(col, t('CustomPanel.settingsSection'), 'PREFERENCES').column(align=True)
        settings_col.scale_y = 0.75
        settings_col.prop(context.scene, 'merge_armatures_join_meshes')

        col.separator()

        # Merge selection
        box_col = draw_section(col, t('CustomPanel.selectionSection'), 'RESTRICT_SELECT_OFF').column(align=True)
        box_col.scale_y = 1.0

        # Get safe enum values for display (handles integer indices in Blender 5.0)
        merge_into_name = Common.get_enum_property_value(context.scene, 'merge_armature_into', Common.get_armature_list)
        attach_mesh_name = Common.get_enum_property_value(context.scene, 'attach_mesh', Common.get_top_meshes)
        attach_bone_name = Common.get_enum_property_value(context.scene, 'attach_to_bone', Common.get_bones_merge)

        row = box_col.row(align=True)
        row.label(text=t('CustomPanel.mergeInto'))
        row.operator(SearchMenuOperator_merge_armature_into.bl_idname,
                    text=Common.enum_display_text(merge_into_name, t('CustomPanel.selectArmature')), 
                    icon=globs.ICON_MOD_ARMATURE)

        row = box_col.row(align=True)
        row.label(text=t('CustomPanel.attachMesh2'))
        row.operator(SearchMenuOperator_attach_mesh.bl_idname,
                    text=Common.enum_display_text(attach_mesh_name, t('CustomPanel.selectMesh')),
                    icon_value=Iconloader.preview_collections["custom_icons"]["UP_ARROW"].icon_id)

        row = box_col.row(align=True)
        row.label(text=t('CustomPanel.attachToBone'))
        row.operator(SearchMenuOperator_attach_to_bone.bl_idname,
                    text=Common.enum_display_text(attach_bone_name, t('CustomPanel.selectBone')),
                    icon='BONE_DATA')

        col.separator()

        # Attach button
        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator(Armature_custom.AttachMesh.bl_idname, icon='MESH_DATA')
