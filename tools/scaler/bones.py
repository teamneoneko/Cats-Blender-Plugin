# MIT License
import bpy
from sys import intern

from .. import common as Common
from ..register import register_wrap

# Keys here must match the identifiers used by the scaling math and the override
# properties (see BONE_LIST below and properties.register_scene_properties).
bone_names = {
    "right_shoulder": ["rightshoulder", "shoulderr", "rshoulder"],
    "right_arm": ["rightarm", "armr", "rarm", "upperarmr", "rightupperarm"],
    "right_elbow": [
        "rightelbow",
        "elbowr",
        "relbow",
        "lowerarmr",
        "rightlowerarm",
        "lowerarmr",
        "forearmr",
    ],
    "right_wrist": ["rightwrist", "wristr", "rwrist", "handr", "righthand"],
    "right_leg": [
        "rightleg",
        "legr",
        "rleg",
        "upperlegr",
        "thighr",
        "rightupperleg",
        "rupperleg",
    ],
    "right_knee": [
        "rightknee",
        "kneer",
        "rknee",
        "lowerlegr",
        "calfr",
        "rightlowerleg",
        "shinr",
    ],
    "right_ankle": [
        "rightankle",
        "ankler",
        "rankle",
        "rightfoot",
        "footr",
        "rightfoot",
    ],
    "right_eye": ["eyer", "righteye", "eyeright", "righteye001"],
    "left_shoulder": ["leftshoulder", "shoulderl", "lshoulder"],
    "left_arm": ["leftarm", "arml", "larm", "upperarml", "leftupperarm"],
    "left_elbow": [
        "leftelbow",
        "elbowl",
        "lelbow",
        "lowerarml",
        "leftlowerarm",
        "lowerarml",
        "forearml",
    ],
    "left_wrist": ["leftwrist", "wristl", "lwrist", "handl", "lefthand"],
    "left_leg": [
        "leftleg",
        "legl",
        "lleg",
        "upperlegl",
        "thighl",
        "leftupperleg",
        "lupperleg",
    ],
    "left_knee": [
        "leftknee",
        "kneel",
        "lknee",
        "lowerlegl",
        "calfl",
        "shinl",
        "leftlowerleg",
    ],
    "left_ankle": ["leftankle", "anklel", "lankle", "leftfoot", "footl", "leftfoot"],
    "left_eye": ["eyel", "lefteye", "eyeleft", "lefteye001"],
    "head": ["head"],
    "neck": ["neck"],
    "hips": ["hips", "hip", "pelvis", "root"],
    "spine": ["spine"],
    "chest": ["chest"],
    "upperchest": ["upperchest", "upper_chest"],
    "left_toes": ["toesl", "toel"],
    "right_toes": ["toesr", "toer"],
    "left_little_proximal": ["littleproximall", "leftpinkyproximal"],
    "left_ring_proximal": ["ringproximall", "leftringproximal"],
    "left_middle_proximal": ["middleproximall", "leftmiddleproximal"],
    "left_index_proximal": ["indexproximall", "leftindexproximal"],
    "left_thumb_proximal": ["thumbproximall", "leftthumbproximal"],
    "left_little_intermediate": ["littleintermediatel", "leftpinkyintermediate"],
    "left_ring_intermediate": ["ringintermediatel", "leftringintermediate"],
    "left_middle_intermediate": ["middleintermediatel", "leftmiddleintermediate"],
    "left_index_intermediate": ["indexintermediatel", "leftindexintermediate"],
    "left_thumb_intermediate": ["thumbintermediatel", "leftthumbintermediate"],
    "left_little_distal": ["littledistall", "leftpinkydistal"],
    "left_ring_distal": ["ringdistall", "leftringdistal"],
    "left_middle_distal": ["middledistall", "leftmiddledistal"],
    "left_index_distal": ["indexdistall", "leftindexdistal"],
    "left_thumb_distal": ["thumbdistall", "leftthumbdistal"],
    "right_little_proximal": ["littleproximalr", "rightpinkyproximal"],
    "right_ring_proximal": ["ringproximalr", "rightringproximal"],
    "right_middle_proximal": ["middleproximalr", "rightmiddleproximal"],
    "right_index_proximal": ["indexproximalr", "rightindexproximal"],
    "right_thumb_proximal": ["thumbproximalr", "rightthumbproximal"],
    "right_little_intermediate": ["littleintermediater", "rightpinkyintermediate"],
    "right_ring_intermediate": ["ringintermediater", "rightringintermediate"],
    "right_middle_intermediate": ["middleintermediater", "rightmiddleintermediate"],
    "right_index_intermediate": ["indexintermediater", "rightindexintermediate"],
    "right_thumb_intermediate": ["thumbintermediater", "rightthumbintermediate"],
    "right_little_distal": ["littledistalr", "rightpinkydistal"],
    "right_ring_distal": ["ringdistalr", "rightringdistal"],
    "right_middle_distal": ["middledistalr", "rightmiddledistal"],
    "right_index_distal": ["indexdistalr", "rightindexdistal"],
    "right_thumb_distal": ["thumbdistalr", "rightthumbdistal"],
}

# Order the override UI/props are generated in. Must stay in sync with bone_names.
BONE_LIST = [
    "right_shoulder", "right_arm", "right_elbow", "right_wrist",
    "right_leg", "right_knee", "right_ankle", "right_eye",
    "left_shoulder", "left_arm", "left_elbow", "left_wrist",
    "left_leg", "left_knee", "left_ankle", "left_eye",
    "neck", "head", "hips", "spine", "chest", "upperchest",
    "left_toes", "right_toes",
    "left_little_proximal", "left_ring_proximal", "left_middle_proximal",
    "left_index_proximal", "left_thumb_proximal",
    "left_little_intermediate", "left_ring_intermediate", "left_middle_intermediate",
    "left_index_intermediate", "left_thumb_intermediate",
    "left_little_distal", "left_ring_distal", "left_middle_distal",
    "left_index_distal", "left_thumb_distal",
    "right_little_proximal", "right_ring_proximal", "right_middle_proximal",
    "right_index_proximal", "right_thumb_proximal",
    "right_little_intermediate", "right_ring_intermediate", "right_middle_intermediate",
    "right_index_intermediate", "right_thumb_intermediate",
    "right_little_distal", "right_ring_distal", "right_middle_distal",
    "right_index_distal", "right_thumb_distal",
]

NO_OVERRIDE = "_None"

def get_bone_enum_items(self, context):
    """Items callback shared by every override EnumProperty and the bone-selection
    search operator: '_None' plus every bone on the current Cats armature."""
    choices = [(NO_OVERRIDE, "None", "")]
    arm = Common.get_armature()
    if arm is not None:
        # intern each string so Python keeps its own reference (avoids a Blender UI bug)
        choices += [(intern(b.name), b.name, b.name) for b in arm.data.bones]
    return choices


def _get_override(name):
    """Return the overridden bone name for a logical bone, or NO_OVERRIDE if unset.
    Uses Cats' safe getter so a stale integer value from Blender 5.0 is resolved back
    to its identifier instead of being misread."""
    value = Common.get_enum_property_value(
        bpy.context.scene, "override_" + name, get_bone_enum_items
    )
    return value or NO_OVERRIDE


def _normalize(name):
    return name.lower().replace("_", "").replace("-", "").replace(" ", "").replace(".", "")


def bone_lookup(name):
    """Given an actual bone name, return the logical bone key it corresponds to
    (e.g. 'LeftUpperArm' -> 'left_arm'), or None."""
    # User overrides win if any logical bone has been overridden to this bone, use that.
    for bone in bone_names:
        if _get_override(bone) == name:
            return bone

    lower_name = _normalize(name)
    for token in bone_names:
        if lower_name in bone_names[token]:
            return token
    return None


def check_bone(name, arm):
    """True if a logical bone is present on the armature (via override or auto-detect).
    Used for optional bones (e.g. upperchest, neck)."""
    override = _get_override(name)
    if override != NO_OVERRIDE and override in arm.pose.bones:
        return True
    name_list = bone_names[name]
    lookup = {_normalize(bone.name): bone for bone in arm.pose.bones}
    for n in name_list:
        if n in lookup:
            return True
    return False


def get_bone(name, arm):
    """Resolve a logical bone key to a PoseBone on the armature. Honors the user
    override first, then the name dictionary, then falls back to a bone literally
    named `name` (which raises KeyError if absent)."""
    override = _get_override(name)
    if override != NO_OVERRIDE and override in arm.pose.bones:
        return arm.pose.bones[override]
    name_list = bone_names[name]
    lookup = {_normalize(bone.name): bone for bone in arm.pose.bones}
    for n in name_list:
        if n in lookup:
            return lookup[n]
    return arm.pose.bones[name]


@register_wrap
class SearchMenuOperator_bone_selection(bpy.types.Operator):
    bl_description = "Select the bone to use for this override"
    bl_idname = "scene.search_menu_bone_selection"
    bl_label = "Select Bone"
    bl_property = "my_enum"

    bone_name: bpy.props.StringProperty()
    my_enum: bpy.props.EnumProperty(
        name="Override Bone",
        description="Bone to use for this override",
        items=get_bone_enum_items,
    )

    def execute(self, context):
        setattr(context.scene, "override_" + self.bone_name, self.my_enum)
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}
