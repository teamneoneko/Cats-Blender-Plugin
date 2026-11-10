# MIT License
import bpy

from .. import common as Common
from .common import ArmatureOperator
from .posemode import start_pose_mode_with_reset, apply_pose_to_rest
from .bones import get_bone
from ..register import register_wrap


def point_bone(bone, point, spread_factor):
    v1 = (bone.tail - bone.head).normalized()
    v2 = (bone.head - point).normalized()
    rotation_quat_pose = v1.rotation_difference(v2)

    newbm = bone.matrix.to_quaternion()
    newbm.rotate(rotation_quat_pose)
    newbm.rotate(rotation_quat_pose)
    newbm.rotate(bone.matrix.inverted())

    oldbm = bone.matrix.to_quaternion()
    oldbm.rotate(bone.matrix.inverted())

    finalbm = oldbm.slerp(newbm, spread_factor / 2)

    bone.rotation_quaternion = finalbm


def spread_fingers(spare_thumb, spread_factor):
    obj = Common.get_armature()
    start_pose_mode_with_reset(obj)
    for hand in [get_bone("right_wrist", obj), get_bone("left_wrist", obj)]:
        for finger in hand.children:
            if "thumb" in finger.name.lower() and spare_thumb:
                continue
            point_bone(finger, hand.head, spread_factor)
    apply_pose_to_rest()
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")


@register_wrap
class ArmatureSpreadFingers(ArmatureOperator):
    """Spread the fingers on a humanoid avatar"""

    bl_idname = "armature.spreadfingers"
    bl_label = "Spread Fingers"
    bl_options = {"UNDO"}

    def execute_main(self, context, arm, meshes):
        # Read the scene properties here, not in invoke().
        s = context.scene
        spread_fingers(s.imscale_spare_thumb, s.imscale_spread_factor)
        return {"FINISHED"}
