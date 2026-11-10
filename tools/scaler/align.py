# MIT License
import bpy
import mathutils
import statistics

from .. import common as Common
from .common import get_body_meshes, ArmatureOperator, temp_ensure_enabled
from .posemode import start_pose_mode_with_reset, apply_pose_to_rest
from .bones import get_bone, bone_lookup, check_bone
from ..register import register_wrap


def scale_torso(context, ref_arm, scale_arm):
    # Match scale to ref's neck and upper legs
    scale_leg_center = (
        get_bone("left_leg", scale_arm).head + get_bone("right_leg", scale_arm).head
    ) / 2
    ref_leg_center = (
        get_bone("left_leg", ref_arm).head + get_bone("right_leg", ref_arm).head
    ) / 2

    translation = ref_leg_center - scale_leg_center
    hips = get_bone("hips", scale_arm)
    translation.rotate(hips.bone.matrix_local.to_quaternion().inverted())
    hips.location = translation

    # Translations aren't reflected in coordinates unless the pose is applied
    apply_pose_to_rest(arm=scale_arm)
    start_pose_mode_with_reset(scale_arm)

    scale_leg_center = (
        get_bone("left_leg", scale_arm).head + get_bone("right_leg", scale_arm).head
    ) / 2
    ref_leg_center = (
        get_bone("left_leg", ref_arm).head + get_bone("right_leg", ref_arm).head
    ) / 2

    scale_shoulder_center = (
        get_bone("left_shoulder", scale_arm).head
        + get_bone("right_shoulder", scale_arm).head
    ) / 2
    ref_shoulder_center = (
        get_bone("left_shoulder", ref_arm).head
        + get_bone("right_shoulder", ref_arm).head
    ) / 2

    scale_torso_len = (scale_shoulder_center - ref_leg_center).length
    ref_torso_len = (ref_shoulder_center - ref_leg_center).length

    base_scaling = ref_torso_len / scale_torso_len

    get_bone("hips", scale_arm).scale = mathutils.Vector(
        (base_scaling, base_scaling, base_scaling)
    )

    apply_pose_to_rest(arm=scale_arm)
    start_pose_mode_with_reset(scale_arm)

    scale_leg_center = (
        get_bone("left_leg", scale_arm).head + get_bone("right_leg", scale_arm).head
    ) / 2
    ref_leg_center = (
        get_bone("left_leg", ref_arm).head + get_bone("right_leg", ref_arm).head
    ) / 2

    translation = ref_leg_center - scale_leg_center
    hips = get_bone("hips", scale_arm)
    translation.rotate(hips.bone.matrix_local.to_quaternion().inverted())
    hips.location = translation

    # Correction for lining up the knees and shoulders. If the base is the same it's a no-op.
    hip_scale = (
        get_bone("left_leg", ref_arm).head - get_bone("right_leg", ref_arm).head
    ).length / (
        get_bone("left_leg", scale_arm).head - get_bone("right_leg", scale_arm).head
    ).length
    get_bone("hips", scale_arm).scale = (hip_scale, 1.0, 1.0)
    bpy.context.view_layer.update()

    chest_scale = (
        get_bone("left_shoulder", ref_arm).head
        - get_bone("right_shoulder", ref_arm).head
    ).length / (
        get_bone("left_shoulder", scale_arm).head
        - get_bone("right_shoulder", scale_arm).head
    ).length

    get_bone("left_shoulder", scale_arm).parent.scale = (chest_scale, 1.0, 1.0)
    # Try not to scale the head
    if check_bone("neck", scale_arm):
        get_bone("neck", scale_arm).scale = (1 / (hip_scale * chest_scale), 1.0, 1.0)

    apply_pose_to_rest(arm=scale_arm)
    start_pose_mode_with_reset(scale_arm)

    # Rotate the whole model to move the shoulders back a little, counter rotating the
    # neck so the head stays as vertical as it was before.
    scale_shoulder_center = (
        get_bone("left_shoulder", scale_arm).head
        + get_bone("right_shoulder", scale_arm).head
    ) / 2
    ref_shoulder_center = (
        get_bone("left_shoulder", ref_arm).head
        + get_bone("right_shoulder", ref_arm).head
    ) / 2

    spine = get_bone("hips", scale_arm)
    v1 = (ref_shoulder_center - spine.head).normalized()
    v2 = (scale_shoulder_center - spine.head).normalized()

    sq = spine.matrix.to_quaternion()
    sq.rotate(spine.matrix.inverted())
    sq.rotate(v2.rotation_difference(v1))
    spine.rotation_quaternion = sq

    if check_bone("neck", scale_arm):
        neck = get_bone("neck", scale_arm)
        nq = neck.matrix.to_quaternion()
        nq.rotate(neck.matrix.inverted())
        nq.rotate(v1.rotation_difference(v2))
        neck.rotation_quaternion = nq

    apply_pose_to_rest(arm=scale_arm)
    start_pose_mode_with_reset(scale_arm)

    return base_scaling


def get_scaling_rotations(ref_bone, scale_bone):
    child_target_scales = []
    child_target_rotations = []
    for s_child in scale_bone.children:
        for r_child in ref_bone.children:
            if s_child.name == r_child.name or (
                bone_lookup(s_child.name) == bone_lookup(r_child.name)
                and bone_lookup(r_child.name) is not None
            ):
                scale = (r_child.head - ref_bone.head).length / (
                    s_child.head - scale_bone.head
                ).length
                child_target_scales.append(scale)

                # Rotation difference between s_child.head -> scale_bone.head -> r_child.head
                v1 = (s_child.head - scale_bone.head).normalized()
                v2 = (r_child.head - scale_bone.head).normalized()
                child_target_rotations.append(v1.rotation_difference(v2))

                # For the wrist bone, always scale to the middle finger if available
                if "wrist" in (bone_lookup(scale_bone.name) or "") and "middle" in (
                    bone_lookup(s_child.name) or ""
                ):
                    starting_rotation = v1.rotation_difference(v2)
                    return [scale], [starting_rotation]

    return child_target_scales, child_target_rotations


def align_bones(ref_bone, scale_bone, arm_thickness, leg_thickness, parent_scale):
    ref_oloc = ref_bone.matrix.decompose()[0]
    scale_oloc = (
        scale_bone.matrix @ mathutils.Matrix.Translation(scale_bone.location)
    ).decompose()[0]
    if (ref_oloc - scale_oloc).length > 0.01:
        print(
            "Bone {} is off by {}, skipping".format(
                scale_bone.name, ref_oloc - scale_oloc
            )
        )
        return

    child_target_scales, child_target_rotations = get_scaling_rotations(
        ref_bone, scale_bone
    )

    # Default to not changing scaling if there are no children
    scale_vector = scale_bone.scale

    if len(child_target_scales) > 0:
        sf = statistics.median(child_target_scales)
        scale_vector = (sf, sf, sf)

    def lerp(a, b, f):
        return (1 - f) * a + f * b

    if bone_lookup(scale_bone.name) in ["left_leg", "right_leg"]:
        scale_vector = (
            lerp(scale_bone.scale[0], scale_vector[0], leg_thickness),
            scale_vector[1],
            lerp(scale_bone.scale[2], scale_vector[2], leg_thickness),
        )

    if bone_lookup(scale_bone.name) in ["left_arm", "right_arm"]:
        scale_vector = (
            lerp(scale_bone.scale[0], scale_vector[0], arm_thickness),
            scale_vector[1],
            lerp(scale_bone.scale[2], scale_vector[2], arm_thickness),
        )

    if bone_lookup(scale_bone.name) in ["left_wrist", "right_wrist"]:
        scale_vector = tuple(1.0 / ps for ps in parent_scale)

    print("Scaling bone {} by factor {}".format(scale_bone.name, scale_vector))
    scale_bone.scale = scale_vector
    bpy.context.view_layer.update()

    if len(child_target_rotations) > 0:
        bq = scale_bone.matrix.to_quaternion()
        bq.rotate(child_target_rotations[-1])
        bq.rotate(scale_bone.matrix.inverted())
        scale_bone.rotation_quaternion = bq

    bpy.context.view_layer.update()

    # Recurse to children with matching names
    for s_child in scale_bone.children:
        for r_child in ref_bone.children:
            if s_child.name == r_child.name or (
                bone_lookup(s_child.name) is not None
                and bone_lookup(s_child.name) == bone_lookup(r_child.name)
            ):
                if not bone_lookup(s_child.name):
                    print(
                        "bone {} not a main human armature bone, skipping".format(
                            s_child.name
                        )
                    )
                    continue
                align_bones(
                    r_child,
                    s_child,
                    arm_thickness,
                    leg_thickness,
                    tuple(
                        scale_vector[i] * parent_scale[i]
                        for i in range(len(scale_vector))
                    ),
                )


def align_armatures(context, arm_ref_name, arm_scaling_name, arm_thickness, leg_thickness):
    ref_arm = context.scene.objects.get(arm_ref_name)
    scale_arm = context.scene.objects.get(arm_scaling_name)

    if ref_arm is None or scale_arm is None or ref_arm == scale_arm:
        return

    start_pose_mode_with_reset(scale_arm)

    scale_torso(context, ref_arm, scale_arm)
    apply_pose_to_rest(arm=scale_arm)
    start_pose_mode_with_reset(scale_arm)

    # Recursive call to scale each of the limbs
    for limb_start in ["right_leg", "left_leg", "right_shoulder", "left_shoulder"]:
        align_bones(
            get_bone(limb_start, ref_arm),
            get_bone(limb_start, scale_arm),
            arm_thickness,
            leg_thickness,
            (1.0, 1.0, 1.0),
        )

    apply_pose_to_rest(arm=scale_arm)


@register_wrap
class ArmatureAlign(ArmatureOperator):
    """Take one armature and align its proportions to another"""

    bl_idname = "armature.imscale_align"
    bl_label = "Align Armatures"
    bl_options = {"UNDO"}

    def execute_main(self, context, arm, meshes):
        # Read the scene properties here, not in invoke().
        s = context.scene
        scale_armature_ref = Common.get_enum_property_value(
            s, "imscale_scale_armature_ref", Common.get_armature_list
        )
        scale_armature_arm = Common.get_enum_property_value(
            s, "imscale_scale_armature_arm", Common.get_armature_list
        )
        ra = context.scene.objects.get(scale_armature_ref)
        sa = context.scene.objects.get(scale_armature_arm)
        if ra is None or sa is None:
            self.report({'ERROR'}, "Pick two different armatures to match")
            return {'CANCELLED'}
        meshes = get_body_meshes(sa)
        with temp_ensure_enabled(sa, ra, *meshes):
            align_armatures(
                context,
                scale_armature_ref,
                scale_armature_arm,
                s.imscale_arm_thickness / 100.0,
                s.imscale_leg_thickness / 100.0,
            )
        return {"FINISHED"}


class _SearchMenuArmatureBase:
    """Shared invoke/execute for the scale-matching armature pickers (search popup)."""
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    bl_property = "my_enum"
    scene_property = None  # set in subclass

    def execute(self, context):
        setattr(context.scene, self.scene_property, self.my_enum)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}


@register_wrap
class SearchMenuOperator_scale_armature_ref(_SearchMenuArmatureBase, bpy.types.Operator):
    bl_description = "Select the armature to use as a reference for scaling"
    bl_idname = "scene.search_menu_scale_armature_ref"
    bl_label = "Scale Armature Reference"
    scene_property = "imscale_scale_armature_ref"

    my_enum: bpy.props.EnumProperty(
        name="Scaling Reference Armature",
        description="Target armature for scaling",
        items=Common.get_armature_list,
    )


@register_wrap
class SearchMenuOperator_scale_armature_arm(_SearchMenuArmatureBase, bpy.types.Operator):
    bl_description = "Select the armature to scale"
    bl_idname = "scene.search_menu_scale_armature_arm"
    bl_label = "Scale Armature"
    scene_property = "imscale_scale_armature_arm"

    my_enum: bpy.props.EnumProperty(
        name="Scaling Active Armature",
        description="Active Armature to scale",
        items=Common.get_armature_list,
    )
