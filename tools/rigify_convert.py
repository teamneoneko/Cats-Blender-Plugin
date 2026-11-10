# MIT License
#
# Convert a Rigify / Metarig armature into a Cats-compatible armature.
#
# Adapted from Avatar Toolkit's "Rigify to Unity" converter, reworked to use
# Cats' common helpers and to rename bones to Cats' internal naming scheme (so
# the rest of the Cats toolset recognises the result) instead of Unity names.

import bpy
import traceback
from typing import Dict, List, Optional

from . import common as Common
from . import armature_bones as Bones
from .register import register_wrap
from .translations import t


def is_rigify_armature(armature: Optional[bpy.types.Object]) -> bool:
    """Return True if the armature looks like a Rigify or Metarig rig.

    Thin wrapper around the shared detector in common so Fix Model and this
    converter always agree; kept for the UI/tests that reference it here.
    """
    return Common.is_rigify_armature(armature)


@register_wrap
class ConvertRigifyToCats(bpy.types.Operator):
    """Convert a Rigify / Metarig armature into a Cats-compatible armature"""
    bl_idname = 'cats_armature.convert_rigify'
    bl_label = t('ConvertRigify.label')
    bl_description = t('ConvertRigify.desc')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context) -> bool:
        return is_rigify_armature(Common.get_armature())

    def execute(self, context):
        saved_data = Common.SavedData()
        try:
            Common.set_default_stage()
            armature = Common.get_armature()
            if not armature:
                saved_data.load()
                Common.show_error(3.5, [t('ConvertRigify.error.noArmature')])
                return {'CANCELLED'}

            Common.unselect_all()
            Common.set_active(armature)
            armature.name = 'Armature'
            armature.data.name = 'Armature'

            if 'DEF-spine' in armature.data.bones:
                # Generated rig
                self.move_def_bones(armature)
                # Merge twist bones *before* renaming, while DEF- names still
                # exist (the original tool ran this after the rename, where the
                # DEF- parents no longer matched and the merge silently no-op'd)
                if context.scene.rigify_merge_twist_bones:
                    self.handle_twist_bones(armature)
                self.rename_bones(armature, Bones.rigify_cats_names)
            else:
                # Ungenerated metarig
                self.cleanup_extra_bones(armature)
                self.rename_bones(armature, Bones.rigify_basic_cats_names)

            self.cleanup_bone_collections(armature)

            Common.set_default_stage()
            saved_data.load()
            self.report({'INFO'}, t('ConvertRigify.success'))
            return {'FINISHED'}

        except Exception:
            print(traceback.format_exc())
            saved_data.load()
            self.report({'ERROR'}, t('ConvertRigify.error.failed'))
            return {'CANCELLED'}

    def _mix_into(self, meshes: List[bpy.types.Object], vg_from: str, vg_to: str) -> None:
        """Transfer weights from vg_from into vg_to on every mesh, then drop vg_from."""
        for mesh in meshes:
            if vg_from not in mesh.vertex_groups:
                continue
            if vg_to not in mesh.vertex_groups:
                mesh.vertex_groups.new(name=vg_to)
            Common.unselect_all()
            Common.switch('OBJECT')
            Common.set_active(mesh)
            Common.mix_weights(mesh, vg_from, vg_to)

    def _drop_group(self, meshes: List[bpy.types.Object], vg_name: str) -> None:
        """Remove a vertex group (and its weights) from every mesh."""
        for mesh in meshes:
            vg = mesh.vertex_groups.get(vg_name)
            if vg:
                mesh.vertex_groups.remove(vg)

    def move_def_bones(self, armature: bpy.types.Object) -> None:
        """Reparent DEF bones and collapse the split limb chain bones."""
        meshes = Common.get_meshes_objects(armature_name=armature.name)

        Common.set_active(armature)
        Common.switch('OBJECT')

        remap = self.get_org_remap(armature)
        remap.update(self.get_special_remap())

        remove_bones_in_chain = [
            'DEF-upper_arm.L.001', 'DEF-forearm.L.001',
            'DEF-upper_arm.R.001', 'DEF-forearm.R.001',
            'DEF-thigh.L.001', 'DEF-shin.L.001',
            'DEF-thigh.R.001', 'DEF-shin.R.001',
        ]

        transform_copies = self.get_transform_copies(armature)

        # Bake ORG motion into the DEF bones via copy transforms constraints
        Common.switch('POSE')
        for bone_name in transform_copies:
            bone = armature.pose.bones[bone_name]
            org_name = 'ORG-' + self.get_proto_name(bone_name)
            if org_name in armature.pose.bones:
                constraint = bone.constraints.new('COPY_TRANSFORMS')
                constraint.target = armature
                constraint.subtarget = org_name
                if len(bone.constraints) > 1:
                    bone.constraints.move(len(bone.constraints) - 1, 0)

        # Remap DEF bone parents to skip the intermediate ORG hierarchy
        Common.switch('EDIT')
        edit_bones = armature.data.edit_bones
        for src, dst in remap.items():
            if src in edit_bones and dst in edit_bones:
                edit_bones[src].parent = edit_bones[dst]

        # Cache parent names for the chain bones before we touch anything
        Common.switch('OBJECT')
        chain_parents: Dict[str, Optional[str]] = {}
        for bone_name in remove_bones_in_chain:
            bone = armature.data.bones.get(bone_name)
            if bone:
                chain_parents[bone_name] = bone.parent.name if bone.parent else None

        # Transfer weights from the split chain bones to their parents
        for bone_name in remove_bones_in_chain:
            parent_name = chain_parents.get(bone_name)
            if parent_name:
                self._mix_into(meshes, bone_name, parent_name)
            else:
                self._drop_group(meshes, bone_name)

        # Collapse the split chain bones into their parent
        Common.set_active(armature)
        Common.switch('EDIT')
        edit_bones = armature.data.edit_bones
        for bone_name in remove_bones_in_chain:
            if bone_name not in edit_bones:
                continue
            remove_bone = edit_bones[bone_name]
            parent_bone = remove_bone.parent
            if parent_bone:
                parent_bone.tail = remove_bone.tail
                for child in list(remove_bone.children):
                    child.parent = parent_bone
            edit_bones.remove(remove_bone)
        Common.switch('OBJECT')

    def handle_twist_bones(self, armature: bpy.types.Object) -> None:
        """Merge Rigify twist deform bones into their parent bones."""
        meshes = Common.get_meshes_objects(armature_name=armature.name)
        twist_bones = [
            ('DEF-upper_arm_twist.L', 'DEF-upper_arm.L'),
            ('DEF-upper_arm_twist.R', 'DEF-upper_arm.R'),
            ('DEF-forearm_twist.L', 'DEF-forearm.L'),
            ('DEF-forearm_twist.R', 'DEF-forearm.R'),
            ('DEF-thigh_twist.L', 'DEF-thigh.L'),
            ('DEF-thigh_twist.R', 'DEF-thigh.R'),
        ]

        Common.set_active(armature)
        Common.switch('OBJECT')
        for twist_bone, parent_bone in twist_bones:
            if twist_bone in armature.data.bones and parent_bone in armature.data.bones:
                self._mix_into(meshes, twist_bone, parent_bone)

        Common.set_active(armature)
        Common.switch('EDIT')
        edit_bones = armature.data.edit_bones
        for twist_bone, parent_bone in twist_bones:
            if twist_bone in edit_bones and parent_bone in edit_bones:
                twist = edit_bones[twist_bone]
                parent = edit_bones[parent_bone]
                parent.tail = twist.tail
                for child in list(twist.children):
                    child.parent = parent
                edit_bones.remove(twist)
        Common.switch('OBJECT')

    def cleanup_extra_bones(self, armature: bpy.types.Object) -> None:
        """Remove unnecessary metarig bones and merge the neck chain."""
        meshes = Common.get_meshes_objects(armature_name=armature.name)

        Common.set_active(armature)
        Common.switch('EDIT')
        edit_bones = armature.data.edit_bones

        bones_to_remove = []
        for bone in edit_bones:
            name_l = bone.name.lower()
            if any(name_l.startswith(pattern) or name_l == pattern
                   for pattern in Bones.rigify_unnecessary_bones):
                bones_to_remove.append(bone.name)

        merge_neck = 'spine.004' in edit_bones and 'spine.005' in edit_bones

        # Drop weights for the junk bones / merge the second neck segment
        Common.switch('OBJECT')
        for bone_name in bones_to_remove:
            self._drop_group(meshes, bone_name)
        if merge_neck:
            self._mix_into(meshes, 'spine.005', 'spine.004')

        Common.set_active(armature)
        Common.switch('EDIT')
        edit_bones = armature.data.edit_bones

        for bone_name in bones_to_remove:
            if bone_name in edit_bones:
                edit_bones.remove(edit_bones[bone_name])

        if merge_neck and 'spine.004' in edit_bones and 'spine.005' in edit_bones:
            neck_start = edit_bones['spine.004']
            neck_end = edit_bones['spine.005']
            neck_start.tail = neck_end.tail
            edit_bones.remove(neck_end)
            neck_start.name = 'Neck'

        if 'spine.006' in edit_bones:
            edit_bones['spine.006'].name = 'Head'

        Common.switch('OBJECT')

    def rename_bones(self, armature: bpy.types.Object, name_map: Dict[str, str]) -> None:
        """Rename bones to Cats' internal naming scheme."""
        Common.set_active(armature)
        Common.switch('OBJECT')
        for old_name, new_name in name_map.items():
            bone = armature.pose.bones.get(old_name)
            if bone:
                bone.name = new_name

    def cleanup_bone_collections(self, armature: bpy.types.Object) -> None:
        """Remove all bone collections, which Cats/Unity don't need."""
        Common.set_active(armature)
        Common.switch('OBJECT')
        data = armature.data
        if hasattr(data, 'collections') and data.collections:
            for collection in list(data.collections):
                data.collections.remove(collection)

    def get_org_remap(self, armature: bpy.types.Object) -> Dict[str, str]:
        """Map each DEF bone to the nearest DEF ancestor (skipping ORG bones)."""
        remap: Dict[str, str] = {}
        for bone in armature.data.bones:
            if not self.is_def_bone(bone.name):
                continue
            name = self.get_proto_name(bone.name)
            parent = bone.parent
            while parent:
                parent_name = self.get_proto_name(parent.name)
                if parent_name != name and ('DEF-' + parent_name) in armature.data.bones:
                    remap[bone.name] = 'DEF-' + parent_name
                    break
                parent = parent.parent
        return remap

    def get_special_remap(self) -> Dict[str, str]:
        """Special-case parenting the automatic remap can't infer."""
        return {
            'DEF-thigh.L': 'DEF-pelvis.L',
            'DEF-thigh.R': 'DEF-pelvis.R',
            'DEF-upper_arm.L': 'DEF-shoulder.L',
            'DEF-upper_arm.R': 'DEF-shoulder.R',
        }

    def get_transform_copies(self, armature: bpy.types.Object) -> List[str]:
        """DEF bones that still need a copy-transforms constraint added."""
        result: List[str] = []
        for bone in armature.pose.bones:
            if self.is_def_bone(bone.name) and not self.has_transform_copies(bone):
                result.append(bone.name)
        return result

    def has_transform_copies(self, bone: bpy.types.PoseBone) -> bool:
        return any(c.type == 'COPY_TRANSFORMS' for c in bone.constraints)

    def is_def_bone(self, bone_name: str) -> bool:
        return bone_name.startswith('DEF-')

    def is_org_bone(self, bone_name: str) -> bool:
        return bone_name.startswith('ORG-')

    def get_proto_name(self, bone_name: str) -> str:
        """Strip the DEF-/ORG- prefix to get the underlying bone name."""
        if self.is_def_bone(bone_name) or self.is_org_bone(bone_name):
            return bone_name[4:]
        return bone_name
