# MIT License
import bpy
import numpy as np

from .. import common as Common
from ..armature_manual import bake_pose_to_rest
from .common import get_body_meshes

_ZERO_ROTATION_QUATERNION = np.array([1, 0, 0, 0], dtype=np.single)


def reset_current_pose(pose_bones):
    num_bones = len(pose_bones)
    pose_bones.foreach_set("location", np.zeros(num_bones * 3, dtype=np.single))
    pose_bones.foreach_set("scale", np.ones(num_bones * 3, dtype=np.single))
    pose_bones.foreach_set(
        "rotation_quaternion", np.tile(_ZERO_ROTATION_QUATERNION, num_bones)
    )


def start_pose_mode_with_reset(arm):
    vl_objects = bpy.context.view_layer.objects
    if vl_objects.active != arm:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        vl_objects.active = arm

    if arm.mode != "POSE":
        bpy.ops.object.mode_set(mode="POSE")

    reset_current_pose(arm.pose.bones)
    arm.data.pose_position = "POSE"


def apply_pose_to_rest(arm=None):
    if not arm:
        arm = Common.get_armature()
    bake_pose_to_rest(arm, get_body_meshes(arm), bpy.context.scene)
