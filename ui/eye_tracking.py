# MIT License

import bpy

from .. import globs
from .main import ToolPanel, draw_info_box, draw_error_box
from ..tools import common as Common
from ..tools import eyetracking as Eyetracking
from ..tools.register import register_wrap
from ..tools.translations import t

@register_wrap
class SearchMenuOperatorBoneHead(bpy.types.Operator):
    bl_idname = "scene.search_menu_head"
    bl_label = ""
    bl_description = t('Scene.head.desc')
    bl_property = "my_enum"

    def items_callback(self, context):
        items = Common.get_bones_head(self, context)
        return items

    my_enum: bpy.props.EnumProperty(name="shapekeys", items=items_callback)


    def execute(self, context):
        context.scene.head = self.my_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

@register_wrap
class SearchMenuOperatorBoneEyeLeft(bpy.types.Operator):
    bl_description = t('Scene.eye_left.desc')
    bl_idname = "scene.search_menu_eye_left"
    bl_label = ""
    bl_property = "my_enum"

    my_enum: bpy.props.EnumProperty(name="shapekeys", items=Common.get_bones_eye_l)

    def execute(self, context):
        context.scene.eye_left = self.my_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

@register_wrap
class SearchMenuOperatorBoneEyeRight(bpy.types.Operator):
    bl_description = t('Scene.eye_right.desc')
    bl_idname = "scene.search_menu_eye_right"
    bl_label = ""
    bl_property = "my_enum"

    my_enum: bpy.props.EnumProperty(name="shapekeys", items=Common.get_bones_eye_r)

    def execute(self, context):
        context.scene.eye_right = self.my_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

@register_wrap
class SearchMenuOperatorShapekeyWinkLeft(bpy.types.Operator):
    bl_description = t('Scene.wink_left.desc')
    bl_idname = "scene.search_menu_wink_left"
    bl_label = ""
    bl_property = "my_enum"

    my_enum: bpy.props.EnumProperty(name="shapekeys", items=Common.get_shapekeys_eye_blink_l)

    def execute(self, context):
        context.scene.wink_left = self.my_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

@register_wrap
class SearchMenuOperatorShapekeyWinkRight(bpy.types.Operator):
    bl_description = t('Scene.wink_right.desc')
    bl_idname = "scene.search_menu_wink_right"
    bl_label = ""
    bl_property = "my_enum"

    my_enum: bpy.props.EnumProperty(name="shapekeys", items=Common.get_shapekeys_eye_blink_r)

    def execute(self, context):
        context.scene.wink_right = self.my_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

@register_wrap
class SearchMenuOperatorShapekeyLowerLidLeft(bpy.types.Operator):
    bl_description = t('Scene.lowerlid_left.desc')
    bl_idname = "scene.search_menu_lowerlid_left"
    bl_label = ""
    bl_property = "my_enum"

    my_enum: bpy.props.EnumProperty(name="shapekeys", items=Common.get_shapekeys_eye_low_l)

    def execute(self, context):
        context.scene.lowerlid_left = self.my_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

@register_wrap
class SearchMenuOperatorShapekeyLowerLidRight(bpy.types.Operator):
    bl_description = t('Scene.lowerlid_right.desc')
    bl_idname = "scene.search_menu_lowerlid_right"
    bl_label = ""
    bl_property = "my_enum"

    my_enum: bpy.props.EnumProperty(name="shapekeys", items=Common.get_shapekeys_eye_low_r)

    def execute(self, context):
        context.scene.lowerlid_right = self.my_enum
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

@register_wrap
class EyeTrackingPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_eye_tracking_v3'
    bl_label = t('EyeTrackingPanel.label')
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        # Parent panel is now just a container for sub-panels
        pass


@register_wrap
class SDK3EyeTrackingSubPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_eye_tracking_sdk3_v3'
    bl_label = t('EyeTrackingPanel.sdk3.label')
    bl_parent_id = 'VIEW3D_PT_eye_tracking_v3'
    bl_options = set()

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        self.draw_sdk3_section(col, context)

    def draw_sdk3_section(self, col, context):
        # Info section
        draw_info_box(col, [
            t("Av3EyeTrackingPanel.info1"),
            t("Av3EyeTrackingPanel.info2"),
            t("Av3EyeTrackingPanel.info3")
        ])

        col.separator()

        # Eye bones section
        box = col.box()
        box_col = box.column(align=True)
        
        # Get armature and verify it exists
        armature = Common.get_armature()
        if not armature:
            draw_error_box(col, t('EyeTrackingPanel.error.noArm'))
            return

        row = box_col.row(align=True)
        row.scale_y = 1.0
        row.label(text=t('Scene.eye_left.label') + ":")
        row.prop_search(context.scene, "eye_left", armature.data, "bones", text="")

        row = box_col.row(align=True)
        row.scale_y = 1.0
        row.label(text=t('Scene.eye_right.label') + ":")
        row.prop_search(context.scene, "eye_right", armature.data, "bones", text="")

        col.separator()

        # Actions section
        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator(Eyetracking.RotateEyeBonesForAv3Button.bl_idname, icon='CON_ROTLIMIT')


@register_wrap
class LegacyEyeTrackingSubPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_eye_tracking_legacy_v3'
    bl_label = t('EyeTrackingPanel.legacy.label')
    bl_parent_id = 'VIEW3D_PT_eye_tracking_v3'
    bl_options = set()

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        self.draw_legacy_section(col, context)

    def draw_legacy_section(self, col, context):
        # Info section
        draw_info_box(col, [
            t("LegacyEyeTrackingPanel.info1"),
            t("LegacyEyeTrackingPanel.info2"),
            t("LegacyEyeTrackingPanel.info3"),
            t("LegacyEyeTrackingPanel.info4"),
            t("LegacyEyeTrackingPanel.info5")
        ])

        col.separator()

        # Troubleshooting Guide
        box = col.box()
        help_col = box.column(align=True)
        help_col.scale_y = 0.85
        help_col.label(text=t('EyeTrackingPanel.troubleshooting.title'), icon='QUESTION')
        help_col.label(text=t('EyeTrackingPanel.troubleshooting.vertexGroups'), icon='GROUP_VERTEX')
        help_col.label(text=t('EyeTrackingPanel.troubleshooting.shapeKeys'), icon='SHAPEKEY_DATA')
        help_col.label(text=t('EyeTrackingPanel.troubleshooting.boneWeights'), icon='BONE_DATA')
        help_col.label(text=t('EyeTrackingPanel.troubleshooting.restPosition'), icon='ARMATURE_DATA')

        col.separator()

        # Main content section
        if context.scene.eye_mode == 'CREATION':
            self.draw_creation_mode(context, col)
        else:
            self.draw_testing_mode(context, col)

        # Progress Indicator (when operations are running)
        if hasattr(context.scene, "progress_update"):
            col.separator()
            box = col.box()
            box.label(text="Operation Progress:", icon='TIME')
            box.prop(context.scene, "progress_update", text="")

    def draw_creation_mode(self, context, box):
        col = box.column(align=True)
        mesh_count = len(Common.get_meshes_objects(check=False))

        if mesh_count == 0:
            self.draw_no_meshes_warning(col)
        elif mesh_count > 1:
            self.draw_mesh_selector(context, col)

        self.draw_bone_selection(context, col)
        self.draw_shapekey_selection(context, col)
        self.draw_options(context, col)
        self.draw_creation_button(box)

    def draw_testing_mode(self, context, box):
        col = box.column(align=True)
        armature = Common.get_armature()
        
        if not armature:
            box.label(text=t('EyeTrackingPanel.error.noArm'), icon='ERROR')
            return

        if bpy.context.active_object is None or bpy.context.active_object.mode != 'POSE':
            self.draw_testing_start(col)
        else:
            self.draw_testing_controls(context, col, armature)

    def draw_no_meshes_warning(self, col):
        col.separator()
        sub = col.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.1
        row.label(text=t('EyeTrackingPanel.error.noMesh'), icon='ERROR')

    def draw_mesh_selector(self, context, col):
        col.separator()
        row = col.row(align=True)
        row.scale_y = 1.1
        row.prop(context.scene, 'mesh_name_eye', icon='MESH_DATA')

    def draw_bone_selection(self, context, col):
        armature = Common.get_armature()
        
        if not armature:
            col.separator()
            col.label(text=t('EyeTrackingPanel.error.noArm'), icon='ERROR')
            return
        
        col.separator()
        row = col.row(align=True)
        row.scale_y = 1.1
        row.label(text=t('Scene.head.label')+":")
        row.prop_search(context.scene, "head", armature.data, "bones", text="")

        row = col.row(align=True)
        row.scale_y = 1.1
        row.active = not context.scene.disable_eye_movement
        row.label(text=t('Scene.eye_left.label')+":")
        row.prop_search(context.scene, "eye_left", armature.data, "bones", text="")

        row = col.row(align=True)
        row.scale_y = 1.1
        row.active = not context.scene.disable_eye_movement
        row.label(text=t('Scene.eye_right.label')+":")
        row.prop_search(context.scene, "eye_right", armature.data, "bones", text="")

    def draw_shapekey_selection(self, context, col):
        col.separator()
        active = not context.scene.disable_eye_blinking
        
        # Check if a valid mesh is selected (not the empty placeholder)
        mesh_name = context.scene.mesh_name_eye
        if not mesh_name or mesh_name == 'Cats_empty_enum_identifier':
            col.label(text=t('EyeTrackingPanel.error.noMesh'), icon='ERROR')
            return
        
        try:
            mesh = Common.get_objects()[mesh_name]
        except KeyError:
            col.label(text=t('EyeTrackingPanel.error.noMesh'), icon='ERROR')
            return
        
        if not mesh or not mesh.data.shape_keys:
            col.label(text=t('EyeTrackingPanel.error.noShapekeys'), icon='ERROR')
            return

        # Wink Left
        row = col.row(align=True)
        row.scale_y = 1.1
        row.active = active
        row.label(text=t('Scene.wink_left.label')+":")
        row.prop_search(context.scene, "wink_left", mesh.data.shape_keys, "key_blocks", text="")

        # Wink Right  
        row = col.row(align=True)
        row.scale_y = 1.1
        row.active = active
        row.label(text=t('Scene.wink_right.label')+":")
        row.prop_search(context.scene, "wink_right", mesh.data.shape_keys, "key_blocks", text="")

        # Lower Lid Left
        row = col.row(align=True)
        row.scale_y = 1.1
        row.active = active
        row.label(text=t('Scene.lowerlid_left.label')+":")
        row.prop_search(context.scene, "lowerlid_left", mesh.data.shape_keys, "key_blocks", text="")

        # Lower Lid Right
        row = col.row(align=True)
        row.scale_y = 1.1
        row.active = active
        row.label(text=t('Scene.lowerlid_right.label')+":")
        row.prop_search(context.scene, "lowerlid_right", mesh.data.shape_keys, "key_blocks", text="")

    def draw_options(self, context, col):
        col.separator()
        row = col.row(align=True)
        row.prop(context.scene, 'disable_eye_blinking')

        row = col.row(align=True)
        row.prop(context.scene, 'disable_eye_movement')

        if not context.scene.disable_eye_movement:
            col.separator()
            row = col.row(align=True)
            row.prop(context.scene, 'eye_distance')

    def draw_creation_button(self, box):
        col = box.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator(Eyetracking.CreateEyesButton.bl_idname, icon='TRIA_RIGHT')

    def draw_testing_start(self, col):
        col.separator()
        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator(Eyetracking.StartTestingButton.bl_idname, icon='TRIA_RIGHT')

        row = col.row(align=True)
        row.scale_y = 1.0
        row.operator(Eyetracking.ResetEyeTrackingButton.bl_idname, icon='FILE_REFRESH')

    def draw_testing_controls(self, context, col, armature):
        col.separator()
        
        # Eye rotation controls
        row = col.row(align=True)
        row.prop(context.scene, 'eye_rotation_x', icon='FILE_PARENT')
        row = col.row(align=True)
        row.prop(context.scene, 'eye_rotation_y', icon='ARROW_LEFTRIGHT')
        row = col.row(align=True)
        row.operator(Eyetracking.ResetRotationButton.bl_idname, icon=globs.ICON_EYE_ROTATION)

        # Eye distance controls
        col.separator()
        row = col.row(align=True)
        row.prop(context.scene, 'eye_distance')
        row = col.row(align=True)
        row.operator(Eyetracking.AdjustEyesButton.bl_idname, icon='CURVE_NCIRCLE')

        # Blinking controls
        col.separator()
        row = col.row(align=True)
        row.prop(context.scene, 'eye_blink_shape')
        row.operator(Eyetracking.TestBlinking.bl_idname, icon='RESTRICT_VIEW_OFF')
        row = col.row(align=True)
        row.prop(context.scene, 'eye_lowerlid_shape')
        row.operator(Eyetracking.TestLowerlid.bl_idname, icon='RESTRICT_VIEW_OFF')
        row = col.row(align=True)
        row.operator(Eyetracking.ResetBlinkTest.bl_idname, icon='FILE_REFRESH')

        # Warnings
        self.draw_testing_warnings(context, col, armature)

        col.separator()
        
        # Testing controls
        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator(Eyetracking.StopTestingButton.bl_idname, icon='PAUSE')
        
        row = col.row(align=True)
        row.scale_y = 1.0
        row.operator(Eyetracking.ResetEyeTrackingButton.bl_idname, icon='FILE_REFRESH')

        # Eye Movement Preview at bottom
        preview_box = col.box()
        preview_box.label(text="Eye Movement Preview:", icon='PREVIEW_RANGE')
        
        row = preview_box.row(align=True)
        row.prop(context.scene, "eye_rotation_x", text="Vertical Range")
        row.prop(context.scene, "eye_rotation_y", text="Horizontal Range")
        
        # Visual indicator for current eye rotation
        indicator_row = preview_box.row()
        indicator_row.scale_y = 2.0
        indicator_row.alignment = 'CENTER'
        
        current_x = context.scene.eye_rotation_x
        current_y = context.scene.eye_rotation_y
        direction = "●"  # Center point
        
        if abs(current_x) > 15 or abs(current_y) > 15:
            direction = "◎"  # Warning indicator for extreme angles
        
        indicator_row.label(text=direction)

    def draw_testing_warnings(self, context, col, armature):
        col.separator()
        
        if armature.name != 'Armature':
            draw_error_box(col, [
                t('EyeTrackingPanel.error.wrongNameArm1'),
                t('EyeTrackingPanel.error.wrongNameArm2'),
                t('EyeTrackingPanel.error.wrongNameArm3') + armature.name + "')"
            ])
            col.separator()

        if context.scene.mesh_name_eye != 'Body':
            draw_error_box(col, [
                t('EyeTrackingPanel.error.wrongNameBody1'),
                t('EyeTrackingPanel.error.wrongNameBody2'),
                t('EyeTrackingPanel.error.wrongNameBody3') + context.scene.mesh_name_eye + "')"
            ])
            col.separator()

        draw_info_box(col, [
            t('EyeTrackingPanel.warn.assignEyes1'),
            t('EyeTrackingPanel.warn.assignEyes2')
        ])
