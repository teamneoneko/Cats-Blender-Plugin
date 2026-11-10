# MIT License
import bpy
import mathutils
import math
import numpy as np
from typing import Iterable

from .. import common as Common
from .common import get_body_meshes, temp_ensure_enabled, ArmatureOperator
from .bones import get_bone, check_bone
from .posemode import start_pose_mode_with_reset, apply_pose_to_rest
from ..register import register_wrap


def get_bone_worldspace_z(name, arm):
    """Worldspace z position of the head of a (logical) bone."""
    return (arm.matrix_world @ get_bone(name, arm).head).z


def bound_box_to_co_array(obj: bpy.types.Object):
    # Note that bounding boxes of objects correspond to the object with shape keys and modifiers applied.
    # Bounding boxes are 8 (x, y, z) rows.
    return np.array(obj.bound_box, dtype=np.single)


def _get_global_z_from_co_ndarray(v_co: np.ndarray, wm: mathutils.Matrix, func):
    if v_co.dtype != np.single:
        raise ValueError("co array should be single precision float")
    if len(wm.row) != 4 or len(wm.col) != 4:
        raise ValueError("matrix must be 4x4")
    v_co = v_co.view()
    wm3x3 = np.array(wm.to_3x3(), dtype=np.single)

    v_co.shape = (-1, 3)
    v_co4_global_t = wm3x3 @ v_co.T
    global_z_only = v_co4_global_t[2]

    return func(global_z_only) + wm.translation.z


def get_global_min_z_from_co_ndarray(v_co: np.ndarray, wm: mathutils.Matrix):
    return _get_global_z_from_co_ndarray(v_co, wm, np.min)


def get_global_max_z_from_co_ndarray(v_co: np.ndarray, wm: mathutils.Matrix):
    return _get_global_z_from_co_ndarray(v_co, wm, np.max)


def get_lowest_point():
    """Get the lowest z coordinate of all vertices of all meshes of the avatar, in worldspace.
    Prefers vertices weighted to the feet (or children of the feet bones) when present."""
    arm = Common.get_armature()
    bones = set()
    for bone in (get_bone("left_ankle", arm), get_bone("right_ankle", arm)):
        bones.add(bone.name)
        bones.update(b.name for b in bone.children_recursive)

    meshes = []
    for o in get_body_meshes():
        likely_lowest_possible_vertex_z = get_global_min_z_from_co_ndarray(
            bound_box_to_co_array(o), o.matrix_world
        )
        meshes.append((likely_lowest_possible_vertex_z, o))
    # Sort meshes by lowest bounding box first so we can stop early
    meshes.sort(key=lambda t: t[0])

    lowest_vertex_z = math.inf
    lowest_foot_z = math.inf

    for likely_lowest_possible_vertex_z, o in meshes:
        mesh = o.data
        if not mesh.vertices:
            continue

        found_feet_previously = lowest_foot_z < math.inf
        if found_feet_previously and likely_lowest_possible_vertex_z > lowest_foot_z:
            break

        foot_group_indices = {
            idx for idx, vg in enumerate(o.vertex_groups) if vg.name in bones
        }
        if not foot_group_indices:
            if found_feet_previously:
                continue
            elif likely_lowest_possible_vertex_z > lowest_vertex_z:
                continue

        if mesh.shape_keys:
            # Keep the mesh vertices in sync with the reference shape key (what the user sees)
            num_verts = len(mesh.vertices)
            v_co = np.empty(num_verts * 3, dtype=np.single)
            mesh.shape_keys.reference_key.data.foreach_get("co", v_co)
            mesh.vertices.foreach_set("co", v_co)
        else:
            v_co = None

        wm = o.matrix_world
        foot_v_indices = []
        if foot_group_indices:
            for vert in mesh.vertices:
                for group in vert.groups:
                    if group.group in foot_group_indices and group.weight:
                        foot_v_indices.append(vert.index)
                        break
        found_feet = bool(foot_v_indices)
        if found_feet or not found_feet_previously:
            if v_co is None:
                v_co = np.empty(len(mesh.vertices) * 3, dtype=np.single)
                mesh.vertices.foreach_get("co", v_co)
            v_co.shape = (-1, 3)

            if found_feet:
                v_co_feet_only = v_co[foot_v_indices]
                lowest_foot_z = min(
                    lowest_foot_z, get_global_min_z_from_co_ndarray(v_co_feet_only, wm)
                )
            else:
                lowest_vertex_z = min(
                    lowest_vertex_z, get_global_min_z_from_co_ndarray(v_co, wm)
                )
    if lowest_foot_z == math.inf:
        if lowest_vertex_z == math.inf:
            raise RuntimeError("No mesh data found")
        else:
            return lowest_vertex_z
    return lowest_foot_z


def get_highest_point():
    # Almost the same as get_lowest_point, but only using numpy since we don't need vertex weights
    meshes = []
    for o in get_body_meshes():
        likely_highest_possible_vertex_z = get_global_max_z_from_co_ndarray(
            bound_box_to_co_array(o), o.matrix_world
        )
        meshes.append((likely_highest_possible_vertex_z, o))
    meshes.sort(key=lambda t: t[0], reverse=True)

    minimum_value = -math.inf
    highest_vertex_z = minimum_value
    for likely_highest_possible_vertex_z, o in meshes:
        wm = o.matrix_world
        mesh = o.data

        vertices = (
            mesh.shape_keys.reference_key.data if mesh.shape_keys else mesh.vertices
        )
        num_verts = len(vertices)
        if num_verts == 0:
            continue

        if likely_highest_possible_vertex_z < highest_vertex_z:
            break

        v_co = np.empty(num_verts * 3, dtype=np.single)
        vertices.foreach_get("co", v_co)
        max_global_z = get_global_max_z_from_co_ndarray(v_co, wm)
        highest_vertex_z = max(highest_vertex_z, max_global_z)
    if highest_vertex_z == minimum_value:
        raise RuntimeError("No mesh data found")
    else:
        return highest_vertex_z


def get_view_z(obj, custom_scale_ratio=0.4537):
    # VRC uses the distance between the head bone and right hand in t-pose as the basis
    # for world scale. This returns the in-VRChat virtual eye height relative to the floor.
    # NOTE: 0.4537 is VRChat's documented default "custom arm ratio" it's user-facing so
    # it can be re-tuned if VRChat changes the measurement.
    view_z = (head_to_hand(obj) / custom_scale_ratio) + 0.005
    return view_z


def get_current_scaling(obj):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="POSE", toggle=False)

    ratio = head_to_hand(obj) / (get_eye_height(obj) - 0.005 - get_lowest_point())

    bpy.ops.object.mode_set(mode="POSE", toggle=True)
    return ratio


def get_upper_body_portion(arm):
    eye_z = (
        get_bone_worldspace_z("left_eye", arm) + get_bone_worldspace_z("right_eye", arm)
    ) / 2
    leg_average_z = (
        get_bone_worldspace_z("left_leg", arm) + get_bone_worldspace_z("right_leg", arm)
    ) / 2
    lowest_point = get_lowest_point()

    return 1 - (leg_average_z - lowest_point) / (eye_z - lowest_point)


def get_arm_length(obj, worldspace=True):
    """Get the length of the (right) arm as if its bones are fully straightened"""
    upper_arm = get_bone("right_arm", obj).head
    elbow = get_bone("right_elbow", obj).head
    wrist = get_bone("right_wrist", obj).head
    if worldspace:
        wm = obj.matrix_world.to_3x3()
        upper_arm_length = (wm @ (upper_arm - elbow)).length
        lower_arm_length = (wm @ (elbow - wrist)).length
    else:
        upper_arm_length = (upper_arm - elbow).length
        lower_arm_length = (elbow - wrist).length

    return upper_arm_length + lower_arm_length


def head_to_hand(obj, worldspace=True):
    headpos = get_bone("head", obj).head
    upper_arm = get_bone("right_arm", obj).head

    upper_arm_to_head = headpos - upper_arm
    if worldspace:
        upper_arm_to_head = obj.matrix_world.to_3x3() @ upper_arm_to_head

    arm_length = get_arm_length(obj, worldspace)

    # The right arm is on the -x side in Blender, so arm_length is negative here
    t_hand_pos = mathutils.Vector((-arm_length, 0, 0))

    return (upper_arm_to_head - t_hand_pos).length


def calculate_arm_rescaling(obj, head_arm_change):
    need_mode_swap = obj.mode == "EDIT"
    if need_mode_swap:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="POSE", toggle=False)

    rarmpos = get_bone("right_arm", obj).head
    headpos = get_bone("head", obj).head

    if need_mode_swap:
        bpy.ops.object.mode_set(mode="POSE", toggle=True)

    total_length = head_to_hand(obj, worldspace=False)
    print("Head to hand length is {}".format(total_length))
    arm_length = get_arm_length(obj, worldspace=False)
    print(f"Arm length is {arm_length}")
    neck_length = abs((headpos[2] - rarmpos[2]))

    # Derived using sympy: solveset(Eq(a * x, sqrt((c * b + s)**2 + y**2)), b)
    # where x=total length, c=arm length, y=neck length, a=head_arm_change, s=shoulder_length
    shoulder_length = (
        math.sqrt((total_length - neck_length) * (total_length + neck_length))
        - arm_length
    )

    arm_change = (
        math.sqrt(
            (head_arm_change * total_length - neck_length)
            * (head_arm_change * total_length + neck_length)
        )
        / arm_length
    ) - (shoulder_length / arm_length)

    return arm_change


def get_eye_height(obj, worldspace=True):
    try:
        left_eye = get_bone("left_eye", obj)
        right_eye = get_bone("right_eye", obj)
    except KeyError as ke:
        raise RuntimeError(f"Cannot identify two eye bones: {ke}")

    eye_average = (left_eye.head + right_eye.head) / 2

    if worldspace:
        # The w component of eye_average works out to 1, so the full 4x4 matrix is fine here
        return (obj.matrix_world @ eye_average).z
    else:
        return eye_average.z


def get_leg_length(arm):
    """Worldspace vertical leg length, from the start of the upper leg bone to the lowest foot vertex."""
    return get_bone_worldspace_z("left_leg", arm) - get_lowest_point()


def get_leg_proportions(arm):
    """Relative worldspace-z lengths of each leg portion from the top of the leg to the lowest foot vertex.
    Returns ([0.0, to_knee, to_ankle, 1.0], total_length)."""
    leg_average_z = (
        get_bone_worldspace_z("left_leg", arm) + get_bone_worldspace_z("right_leg", arm)
    ) / 2
    knee_average_z = (
        get_bone_worldspace_z("left_knee", arm)
        + get_bone_worldspace_z("right_knee", arm)
    ) / 2
    ankle_average_z = (
        get_bone_worldspace_z("left_ankle", arm)
        + get_bone_worldspace_z("right_ankle", arm)
    ) / 2
    lowest_point = get_lowest_point()

    total = leg_average_z - lowest_point
    nl = (
        [0.0]
        + [1 - (i - lowest_point) / total for i in (knee_average_z, ankle_average_z)]
        + [1.0]
    )
    return nl, total


def scale_legs(arm, leg_scale_ratio, leg_thickness, scale_foot, thigh_percentage):
    leg_points, total_length = get_leg_proportions(arm)

    starting_portions = list([leg_points[i + 1] - leg_points[i] for i in range(3)])
    print("starting_portions: {}".format(starting_portions))

    # Foot scale is the percentage of the final it'll take up.
    foot_portion = (1 - leg_points[2]) * leg_thickness / leg_scale_ratio
    if scale_foot:
        foot_portion = (1 - leg_points[2]) * leg_thickness
    print("Foot portion: {}".format(foot_portion))
    print(
        "Leg thickness: {}, leg_scale_ratio: {}, leg_points: {}".format(
            leg_thickness, leg_scale_ratio, leg_points
        )
    )

    leg_portion = 1 - foot_portion

    thigh_portion = leg_portion * thigh_percentage
    calf_portion = leg_portion - thigh_portion

    print(
        "calculated desired leg portions: {}".format(
            [thigh_portion, calf_portion, foot_portion]
        )
    )

    final_thigh_scale = (thigh_portion / starting_portions[0]) * leg_scale_ratio
    final_calf_scale = (calf_portion / starting_portions[1]) * leg_scale_ratio
    final_foot_scale = (foot_portion / starting_portions[2]) * leg_scale_ratio

    # Disable scaling from parent for these bones
    scale_bones = ["left_knee", "right_knee", "left_ankle", "right_ankle"]
    for b in scale_bones:
        bone = get_bone(b, arm)
        arm.data.bones[bone.name].inherit_scale = "NONE"

    print(final_foot_scale)
    print(
        "Calculated final scales: thigh {} calf {} foot {}".format(
            final_thigh_scale, final_calf_scale, final_foot_scale
        )
    )

    for leg in [get_bone("left_leg", arm), get_bone("right_leg", arm)]:
        leg.scale = (leg_thickness, final_thigh_scale, leg_thickness)
    for knee in [get_bone("left_knee", arm), get_bone("right_knee", arm)]:
        knee.scale = (leg_thickness, final_calf_scale, leg_thickness)
    for foot in [get_bone("left_ankle", arm), get_bone("right_ankle", arm)]:
        foot.scale = (final_foot_scale, final_foot_scale, final_foot_scale)

    result_final_points, result_total_legs = get_leg_proportions(arm)
    print("Implemented leg portions: {}".format(result_final_points))


def scale_torso(arm, torso_scale_ratio):
    # The final distance measured is from the leg bones to the eyes, but the distance
    # lengthened is only from the leg bone roots to the chest or upper chest.
    if check_bone("upperchest", arm):
        scaled_top = get_bone_worldspace_z("upperchest", arm)
    else:
        scaled_top = get_bone_worldspace_z("chest", arm)

    scaled_bottom = (
        get_bone_worldspace_z("left_leg", arm) + get_bone_worldspace_z("right_leg", arm)
    ) / 2

    total_height = get_eye_height(arm) - scaled_bottom
    scaled_height = scaled_top - scaled_bottom

    print("Total height: {}, scaled height: {}".format(total_height, scaled_height))
    scale_ratio = 1 + ((total_height / scaled_height) * (torso_scale_ratio - 1))

    # Mark boundary bones as not inheriting scale
    boundry_bones = list(
        b.name
        for b in get_bone("hips", arm).children
        if b.name != get_bone("spine", arm).name
    )
    if check_bone("upperchest", arm):
        boundry_bones += [get_bone("upperchest", arm).name]
    else:
        boundry_bones += [get_bone("chest", arm).name]

    for b in boundry_bones:
        bone = arm.pose.bones[b]
        print("Disabling inherit scale on bone {}".format(b))
        arm.data.bones[bone.name].inherit_scale = "NONE"

    print("Scaling hip by {}".format(scale_ratio))
    get_bone("hips", arm).scale = (1, scale_ratio, 1)

    new_total_height = get_eye_height(arm) - scaled_bottom
    print(
        "Torso Scaling Expected height: {}, actual height: {}".format(
            total_height * torso_scale_ratio, new_total_height
        )
    )


def scale_to_floor(
    arm_to_legs,
    arm_thickness,
    leg_thickness,
    extra_leg_length,
    scale_hand,
    thigh_percentage,
    custom_scale_ratio,
    scale_relative,
    keep_head_size,
    upper_body_portion,
):
    arm = Common.get_armature()

    start_pose_mode_with_reset(arm)

    lowest_point = get_lowest_point()

    view_z = get_view_z(arm, custom_scale_ratio) + extra_leg_length
    eye_z = get_eye_height(arm) - lowest_point

    rescale_ratio = eye_z / view_z
    leg_height_portion = get_leg_length(arm) / eye_z

    if scale_relative:
        rescale_leg_ratio = rescale_ratio**arm_to_legs
        rescale_arm_ratio = rescale_ratio ** (1 - arm_to_legs)
        leg_scale_ratio = 1 - (1 - (1 / rescale_leg_ratio)) / leg_height_portion
    elif keep_head_size:
        # Keep head size: length taken from the legs is added to the torso (inverse scalings)
        current_ubp = get_upper_body_portion(arm)

        print(
            "current ubp: {}, desired ubp: {}".format(current_ubp, upper_body_portion)
        )
        torso_scale_ratio = upper_body_portion / current_ubp
        leg_scale_ratio = (1 - upper_body_portion) / (1 - current_ubp)

        # For debugging, get new scales
        eye_z = get_eye_height(arm)
        lowest_point = get_lowest_point()
        leg_average_z = (
            get_bone_worldspace_z("left_leg", arm)
            + get_bone_worldspace_z("right_leg", arm)
        ) / 2

        ntl = (eye_z - leg_average_z) * torso_scale_ratio
        ns = ntl / (ntl + ((leg_average_z - lowest_point) * leg_scale_ratio))

        print("Expected New scale: {}".format(ns))
        print("Torso scale ratio: {}".format(torso_scale_ratio))
        print("Leg scale ratio: {}".format(leg_scale_ratio))
        rescale_arm_ratio = rescale_ratio

    else:
        ubp = get_upper_body_portion(arm)
        ub_scale_ratio = ubp / upper_body_portion
        leg_scale_ratio = ub_scale_ratio + (
            (ub_scale_ratio * ubp - ubp) / (leg_height_portion)
        )
        rescale_leg_ratio = 1 / (leg_height_portion * (leg_scale_ratio - 1) + 1)
        rescale_arm_ratio = rescale_ratio / rescale_leg_ratio

    arm_scale_ratio = calculate_arm_rescaling(arm, rescale_arm_ratio)

    print("Total required scale factor is %f" % rescale_ratio)
    print(
        "Scaling legs by a factor of %f to %f"
        % (leg_scale_ratio, leg_scale_ratio * get_leg_length(arm))
    )
    print("Scaling arms by a factor of %f" % arm_scale_ratio)

    leg_thickness = leg_thickness + leg_scale_ratio * (1 - leg_thickness)
    arm_thickness = arm_thickness + arm_scale_ratio * arm_thickness

    scale_foot = False
    scale_legs(arm, leg_scale_ratio, leg_thickness, scale_foot, thigh_percentage)

    if keep_head_size:
        scale_torso(arm, torso_scale_ratio)

    # This kept getting me - make sure arms are set to inherit scale
    for b in ["left_elbow", "right_elbow", "left_wrist", "right_wrist"]:
        get_bone(b, arm).bone.inherit_scale = "FULL"

    for armbone in [get_bone("left_arm", arm), get_bone("right_arm", arm)]:
        armbone.scale = (arm_thickness, arm_scale_ratio, arm_thickness)

    if not scale_hand:
        for hand in [get_bone("left_wrist", arm), get_bone("right_wrist", arm)]:
            hand.scale = (1 / arm_thickness, 1 / arm_scale_ratio, 1 / arm_thickness)

            result_final_points, result_total_legs = get_leg_proportions(arm)
        print("Implemented leg portions: {}".format(result_final_points))

    # Apply the pose as rest pose, updating the meshes and their shape keys if they have them
    apply_pose_to_rest()


def move_to_floor():
    """Move the avatar down so that its lowest_point is at z=0 and set the origin of the armature
    and meshes to (armature_x, armature_y, z=0)."""
    arm = Common.get_armature()
    arm_location_world = arm.matrix_world.translation
    arm_location_world.z -= get_lowest_point()

    new_origin = arm_location_world.copy()
    new_origin.z = 0
    bpy.context.scene.cursor.location = new_origin

    all_objects = get_body_meshes()
    all_objects.append(arm)

    for obj in all_objects:
        if obj.data.users > 1:
            obj.data = obj.data.copy()

    override = dict(active_object=None, selected_editable_objects=all_objects)
    Common.op_override(bpy.ops.object.origin_set, override, type="ORIGIN_CURSOR")


def recursive_object_mode(objects: Iterable[bpy.types.Object]):
    """Set objects into OBJECT mode"""
    objects = [o for o in objects if o.mode != "OBJECT"]
    if objects:
        op_mode_set = bpy.ops.object.mode_set
        with temp_ensure_enabled(*objects):
            for o in objects:
                override = dict(active_object=o)
                Common.op_override(op_mode_set, override, mode="OBJECT", toggle=False)


def recursive_scale(objects: Iterable[bpy.types.Object]):
    """Apply scale transforms to objects, assumes the objects are already in OBJECT mode"""
    scene_objects = bpy.context.scene.objects
    objects = [o for o in objects if o.name in scene_objects]
    if objects:
        override = dict(active_object=objects[0], selected_editable_objects=objects)
        Common.op_override(
            bpy.ops.object.transform_apply,
            override,
            scale=True,
            location=False,
            rotation=False,
            properties=False,
        )


def scale_to_height(new_height, scale_eyes):
    obj = Common.get_armature()
    if scale_eyes:
        old_height = get_eye_height(obj) - get_lowest_point()
    else:
        old_height = get_highest_point() - get_lowest_point()

    print("Old height is %f" % old_height)

    scale_ratio = new_height / old_height
    print("Scaling by %f to achieve target height" % scale_ratio)
    bpy.context.scene.cursor.location = obj.matrix_world.translation
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    obj.scale = obj.scale * scale_ratio

    obj_and_all_children = obj.children_recursive + [obj]

    recursive_object_mode(obj_and_all_children)
    recursive_scale(obj_and_all_children)


def center_model(worldspace=True):
    arm = Common.get_armature()
    if worldspace:
        arm.matrix_world.translation = (0, 0, 0)
    else:
        arm.matrix_local.translation = (0, 0, 0)


def rescale_main(
    new_height,
    arm_to_legs,
    arm_thickness,
    leg_thickness,
    extra_leg_length,
    scale_hand,
    thigh_percentage,
    custom_scale_ratio,
    scale_eyes,
    scale_relative,
    keep_head_size,
    upper_body_percent,
):
    context = bpy.context
    s = context.scene

    if not s.imscale_debug_no_adjust:
        scale_to_floor(
            arm_to_legs,
            arm_thickness,
            leg_thickness,
            extra_leg_length,
            scale_hand,
            thigh_percentage,
            custom_scale_ratio,
            scale_relative,
            keep_head_size,
            upper_body_percent,
        )
    if not s.imscale_debug_no_floor:
        move_to_floor()

    result_final_points, result_total_legs = get_leg_proportions(Common.get_armature())
    print("Final Implemented leg portions: {}".format(result_final_points))

    if not s.imscale_debug_no_scale:
        scale_to_height(new_height, scale_eyes)

    if s.imscale_center_model:
        center_model()

    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")


def shrink_hips():
    arm = Common.get_armature()

    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT", toggle=False)

    edit_bones = arm.data.edit_bones
    left_leg_name = get_bone("left_leg", arm).name
    right_leg_name = get_bone("right_leg", arm).name
    hips_name = get_bone("hips", arm).name
    spine_name = get_bone("spine", arm).name

    leg_start = (
        edit_bones[left_leg_name].head[2] + edit_bones[right_leg_name].head[2]
    ) / 2
    spine_start = edit_bones[spine_name].head[2]
    edit_bones[hips_name].head[2] = leg_start + (spine_start - leg_start) * 0.9
    edit_bones[hips_name].head[1] = edit_bones[spine_name].head[1]
    edit_bones[hips_name].head[0] = edit_bones[spine_name].head[0]

    bpy.ops.object.mode_set(mode="EDIT", toggle=True)
    bpy.ops.object.select_all(action="DESELECT")


@register_wrap
class ArmatureRescale(ArmatureOperator):
    """Scale most aspects of an armature for use in VRChat"""

    bl_idname = "armature.rescale"
    bl_label = "Rescale Armature"
    bl_options = {"UNDO"}

    def execute_main(self, context, arm, meshes):
        # Read the scene properties here rather than caching them as instance
        # attributes.
        s = context.scene
        rescale_main(
            s.imscale_target_height,
            s.imscale_arm_to_legs / 100.0,
            s.imscale_arm_thickness / 100.0,
            s.imscale_leg_thickness / 100.0,
            s.imscale_extra_leg_length,
            s.imscale_scale_hand,
            s.imscale_thigh_percentage / 100.0,
            s.imscale_custom_scale_ratio,
            s.imscale_scale_eyes,
            s.imscale_scale_upper_body,
            s.imscale_keep_head_size,
            s.imscale_upper_body_percentage / 100,
        )
        return {"FINISHED"}


@register_wrap
class ArmatureShrinkHip(ArmatureOperator):
    """Shrink the hip bone in a humanoid avatar to be much closer to the spine location"""

    bl_idname = "armature.shrink_hips"
    bl_label = "Shrink Hips"
    bl_options = {"REGISTER", "UNDO"}

    def execute_main(self, context, arm, meshes):
        shrink_hips()
        return {"FINISHED"}


@register_wrap
class UIGetCurrentHeight(ArmatureOperator):
    """Set target height based on the current height"""

    bl_idname = "armature.get_avatar_height"
    bl_label = "Get Current Avatar Height"
    bl_options = {"REGISTER", "UNDO"}

    def execute_main(self, context, arm, meshes):
        lowest_point = get_lowest_point()
        if context.scene.imscale_scale_eyes:
            height = get_eye_height(arm) - lowest_point
        else:
            height = get_highest_point() - lowest_point
        context.scene.imscale_target_height = height
        return {"FINISHED"}


@register_wrap
class UIGetScaleRatio(ArmatureOperator):
    """Get the custom scaling ratio based on the current avatar's proportions"""

    bl_idname = "armature.get_scale_ratio"
    bl_label = "Get Current Avatar Scale Ratio"
    bl_options = {"REGISTER", "UNDO"}

    def execute_main(self, context, arm, meshes):
        scale = get_current_scaling(arm)
        context.scene.imscale_custom_scale_ratio = scale
        return {"FINISHED"}


@register_wrap
class UIGetCurrentUpperLegPercent(ArmatureOperator):
    """Set the Upper Leg Percent based on the current leg proportions"""

    bl_idname = "armature.get_avatar_upper_leg_percent"
    bl_label = "Get Current Avatar Upper Leg Percent"
    bl_options = {"REGISTER", "UNDO"}

    def execute_main(self, context, arm, meshes):
        proportions, _total_length = get_leg_proportions(arm)
        current_thigh_percentage = proportions[1] / proportions[2]
        context.scene.imscale_thigh_percentage = current_thigh_percentage * 100.0
        return {"FINISHED"}


@register_wrap
class UIGetUpperBodyPercent(ArmatureOperator):
    """Get the percent of the avatar's height used by the upper body - from eyes to legs"""

    bl_idname = "armature.get_upper_body_percentage"
    bl_label = "Get Current Avatar Upper Body Percentage"
    bl_options = {"REGISTER", "UNDO"}

    def execute_main(self, context, arm, meshes):
        scale = get_upper_body_portion(arm) * 100
        context.scene.imscale_upper_body_percentage = scale
        return {"FINISHED"}
