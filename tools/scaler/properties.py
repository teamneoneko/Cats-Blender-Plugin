# MIT License
from bpy.types import Scene
from bpy.props import BoolProperty, EnumProperty, FloatProperty

from .. import common as Common
from ..common import wrap_dynamic_enum_items
from .bones import BONE_LIST, get_bone_enum_items


def register_scene_properties():
    Scene.imscale_target_height = FloatProperty(
        name="Target Height",
        description="Desired height of the highest vertex in the model. If Scale to Eyes is set, desired eye height",
        default=1.61, step=0.01, precision=3, soft_min=0, soft_max=3, subtype="DISTANCE",
    )
    Scene.imscale_arm_to_legs = FloatProperty(
        name="Leg/Arm Scaling",
        description="What percentage of the needed rescaling should be done to the legs. Remaining scaling is done on the arms",
        default=55, step=1, precision=3, soft_min=0, soft_max=100, subtype="PERCENTAGE",
    )
    Scene.imscale_upper_body_percentage = FloatProperty(
        name="Upper Body Percentage",
        description="Percentage of the distance from the eyes to the heel that should be taken up by the torso and neck",
        default=44, step=1, precision=3, soft_min=30, soft_max=75, subtype="PERCENTAGE",
    )
    Scene.imscale_arm_thickness = FloatProperty(
        name="Arm Thickness",
        description="How much arm thickness should be kept or added when scaling",
        default=50, step=1, precision=3, soft_min=0, soft_max=100, subtype="PERCENTAGE",
    )
    Scene.imscale_leg_thickness = FloatProperty(
        name="Leg Thickness",
        description="How much leg thickness should be kept or added when scaling",
        default=50, step=1, precision=3, soft_min=0, soft_max=100, subtype="PERCENTAGE",
    )
    Scene.imscale_extra_leg_length = FloatProperty(
        name="Extra Leg Length",
        description="How far beneath the real floor the model's legs should go (how far below the real floor the VRChat floor should be). Calculated before scaling",
        default=0, step=0.01, precision=3, soft_min=-1, soft_max=1, subtype="DISTANCE",
    )
    Scene.imscale_thigh_percentage = FloatProperty(
        name="Upper Leg Percent",
        description="Percentage of the distance from the hips to the heel that should be taken up by the upper leg",
        default=53, step=1, precision=3, soft_min=10, soft_max=90, subtype="PERCENTAGE",
    )
    Scene.imscale_custom_scale_ratio = FloatProperty(
        name="Custom Arm Ratio",
        description="The target proportions to scale to. Same as the --custom-arm-ratio argument in VRChat. A higher value means longer arms. 0.4537 is VRChat's default; 0.415 was used previously in beta. Personal values will likely be between the two",
        default=0.4537, step=0.005, precision=4, soft_min=0.35, soft_max=0.5, subtype="FACTOR",
    )
    Scene.imscale_scale_hand = BoolProperty(
        name="Scale hand",
        description="Toggle for scaling the hand with the arm",
        default=False,
    )
    Scene.imscale_scale_foot = BoolProperty(
        name="Scale foot",
        description="Toggle for scaling the foot with the leg",
        default=False,
    )
    Scene.imscale_center_model = BoolProperty(
        name="Center Model",
        description="Toggle for centering the model on x,y = 0,0",
        default=False,
    )
    Scene.imscale_debug_no_scale = BoolProperty(
        name="Skip Height Scaling",
        description="Toggle for the final scaling phase",
        default=False,
    )
    Scene.imscale_debug_no_floor = BoolProperty(
        name="Skip move to floor",
        description="Toggle for the move-to-floor phase",
        default=False,
    )
    Scene.imscale_debug_no_adjust = BoolProperty(
        name="Skip Main Rescale",
        description="Toggle for the first adjustment phase",
        default=False,
    )
    Scene.imscale_scale_eyes = BoolProperty(
        name="Scale to Eyes",
        description="Target height targets the eyes instead of the highest vertex",
        default=False,
    )

    # Finger spreading
    Scene.imscale_spare_thumb = BoolProperty(
        name="Ignore thumb",
        description="Toggle whether the thumb should be adjusted in addition to the other fingers",
        default=True,
    )
    Scene.imscale_spread_factor = FloatProperty(
        name="Spread Factor",
        description="How much fingers should be rotated. 1 is default and points the finger bone directly away from the head of the wrist bone",
        default=1, step=0.1, precision=2, soft_min=0, soft_max=2, subtype="FACTOR",
    )

    # Armature aligning / scale matching
    Scene.imscale_scale_armature_ref = EnumProperty(
        name="Scaling Reference Armature",
        description="Target armature for scaling",
        items=wrap_dynamic_enum_items(
            Common.get_armature_list, "imscale_scale_armature_ref", sort=False, in_place=False
        ),
    )
    Scene.imscale_scale_armature_arm = EnumProperty(
        name="Scaling Active Armature",
        description="Active armature to scale",
        items=wrap_dynamic_enum_items(
            Common.get_armature_list, "imscale_scale_armature_arm", sort=False, in_place=False
        ),
    )

    # UI toggles
    Scene.imscale_scale_upper_body = BoolProperty(
        name="Scale by Upper Body",
        default=False,
        description="Works better for upper-lock-all mode in VRChat",
    )
    Scene.imscale_keep_head_size = BoolProperty(
        name="Keep head size",
        default=False,
        description="Attempts to keep head size by scaling the torso",
    )
    Scene.imscale_show_customize = BoolProperty(name="Show customize panel", default=False)
    Scene.imscale_show_sf_custom = BoolProperty(name="Show customize panel", default=False)
    Scene.imscale_show_debug = BoolProperty(name="Show debug panel", default=False)
    Scene.imscale_show_bone_map = BoolProperty(name="Show bone mapping", default=False)

    # Per-bone override pickers. Each wraps the shared bone items callback so a stale
    # Blender 5.x value can't leave the property pointing at the wrong bone.
    for bone_name in BONE_LIST:
        prop_name = "override_" + bone_name
        setattr(
            Scene,
            prop_name,
            EnumProperty(
                name=bone_name.replace("_", " "),
                description="Override for {} when the bone is not automatically found".format(
                    bone_name.replace("_", " ")
                ),
                items=wrap_dynamic_enum_items(
                    get_bone_enum_items, prop_name, sort=False, in_place=False
                ),
            ),
        )
