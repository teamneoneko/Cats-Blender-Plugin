# MIT License

import bpy
import webbrowser
import numpy as np
from typing import List, Optional, Dict, Set
from mathutils import Vector

from . import common as Common
from . import armature_bones as Bones
from .register import register_wrap
from .translations import t


@register_wrap
class MergeArmature(bpy.types.Operator):
    bl_idname = 'cats_custom.merge_armatures'
    bl_label = t('MergeArmature.label')
    bl_description = t('MergeArmature.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return len(Common.get_armature_objects()) > 1

    def execute(self, context):
        wm = context.window_manager
        wm.progress_begin(0, 100)
        
        saved_data = Common.SavedData()

        # Set default stage
        Common.set_default_stage()
        Common.remove_rigidbodies_global()
        Common.unselect_all()
        wm.progress_update(10)

        # Get both armatures
        base_armature_name = bpy.context.scene.merge_armature_into
        merge_armature_name = bpy.context.scene.merge_armature
        base_armature = Common.get_objects().get(base_armature_name)
        merge_armature = Common.get_objects().get(merge_armature_name)
        armature = Common.set_default_stage()
        wm.progress_update(20)

        if not base_armature or not merge_armature:
            saved_data.load()
            wm.progress_end()
            Common.show_error(5.2, [t('MergeArmature.error.notFound', name=merge_armature_name)])
            return {'CANCELLED'}

        # Remove Rigid Bodies and Joints
        delete_rigidbodies_and_joints(base_armature)
        delete_rigidbodies_and_joints(merge_armature)
        wm.progress_update(40)

        # Set default stage and cleanup
        Common.set_default_stage()
        Common.unselect_all()
        Common.remove_empty()
        Common.remove_unused_objects()
        wm.progress_update(60)

        # Check parents and transformations
        if not validate_parents_and_transforms(merge_armature, base_armature, context):
            saved_data.load()
            wm.progress_end()
            return {'CANCELLED'}
        wm.progress_update(80)

        # Merge armatures
        merge_armatures(
            base_armature_name,
            merge_armature_name,
            mesh_only=False,
            merge_same_bones=context.scene.merge_same_bones
        )
        wm.progress_update(90)

        saved_data.load()
        wm.progress_update(100)
        wm.progress_end()

        self.report({'INFO'}, t('MergeArmature.success'))
        return {'FINISHED'}

@register_wrap
class AttachMesh(bpy.types.Operator):
    bl_idname = 'cats_custom.attach_mesh'
    bl_label = t('AttachMesh.label')
    bl_description = t('AttachMesh.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return len(Common.get_armature_objects()) > 0 and len(Common.get_meshes_objects(mode=1, check=False)) > 0

    def execute(self, context):
        wm = context.window_manager
        wm.progress_begin(0, 100)
        saved_data = Common.SavedData()

        # Set default stage
        Common.set_default_stage()
        Common.remove_rigidbodies_global()
        Common.unselect_all()
        wm.progress_update(5)

        # Get armature and mesh
        mesh_name = context.scene.attach_mesh
        base_armature_name = context.scene.merge_armature_into
        attach_bone_name = context.scene.attach_to_bone
        mesh = Common.get_objects().get(mesh_name)
        armature = Common.get_objects().get(base_armature_name)
        wm.progress_update(10)

        # Validate mesh transforms
        is_valid, error_msg = validate_mesh_transforms(mesh)
        if not is_valid:
            self.report({'ERROR'}, error_msg)
            saved_data.load()
            wm.progress_end()
            return {'CANCELLED'}
        wm.progress_update(15)

        # Validate mesh name
        is_valid, error_msg = validate_mesh_name(armature, mesh_name)
        if not is_valid:
            self.report({'ERROR'}, error_msg)
            saved_data.load()
            wm.progress_end()
            return {'CANCELLED'}
        wm.progress_update(20)

        # Parent mesh to armature
        mesh.parent = armature
        mesh.parent_type = 'OBJECT'
        wm.progress_update(30)

        # Apply transforms
        Common.apply_transforms(armature_name=base_armature_name)
        wm.progress_update(35)

        # Setup mesh editing
        Common.unselect_all()
        Common.set_active(mesh)
        Common.switch('EDIT')
        wm.progress_update(40)

        # Handle vertex groups
        if mesh.vertex_groups:
            bpy.ops.object.vertex_group_remove(all=True)
        wm.progress_update(45)

        # Create new vertex group
        bpy.ops.mesh.select_all(action='SELECT')
        vg = mesh.vertex_groups.new(name=mesh_name)
        bpy.ops.object.vertex_group_assign()
        wm.progress_update(50)

        Common.switch('OBJECT')

        # Verify vertex group
        verts_in_group = [v for v in mesh.data.vertices 
                         for g in v.groups if g.group == vg.index]
        if not verts_in_group:
            self.report({'ERROR'}, f"Vertex group '{mesh_name}' is empty")
            saved_data.load()
            wm.progress_end()
            return {'CANCELLED'}
        wm.progress_update(60)

        # Setup armature editing
        Common.unselect_all()
        Common.set_active(armature)
        Common.switch('EDIT')
        wm.progress_update(70)

        # Create and setup bone
        attach_to_bone = armature.data.edit_bones.get(attach_bone_name)
        if not attach_to_bone:
            self.report({'ERROR'}, f"Attach bone '{attach_bone_name}' not found")
            saved_data.load()
            wm.progress_end()
            return {'CANCELLED'}

        mesh_bone = armature.data.edit_bones.new(mesh_name)
        mesh_bone.parent = attach_to_bone
        wm.progress_update(75)

        # Calculate optimal bone placement
        center_vector = Common.find_center_vector_of_vertex_group(mesh, mesh_name)
        if center_vector is None:
            self.report({'ERROR'}, f"Unable to find center of vertex group")
            saved_data.load()
            wm.progress_end()
            return {'CANCELLED'}

        dimensions, roll_angle = calculate_bone_orientation(mesh, verts_in_group)
        mesh_bone.head = center_vector
        mesh_bone.tail = center_vector + Vector((0, 0, max(0.1, dimensions.z)))
        mesh_bone.roll = roll_angle
        wm.progress_update(80)

        # Setup armature modifier
        Common.switch('OBJECT')
        add_armature_modifier(mesh, armature)
        wm.progress_update(90)

        # Restore the attach bone field
        context.scene.attach_to_bone = attach_bone_name

        saved_data.load()
        wm.progress_update(100)
        wm.progress_end()

        self.report({'INFO'}, t('AttachMesh.success'))
        return {'FINISHED'}

@register_wrap
class CustomModelTutorialButton(bpy.types.Operator):
    bl_idname = 'cats_custom.tutorial'
    bl_label = t('CustomModelTutorialButton.label')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        webbrowser.open(t('CustomModelTutorialButton.URL'))

        self.report({'INFO'}, t('CustomModelTutorialButton.success'))
        return {'FINISHED'}

def validate_mesh_transforms(mesh):
    """Validate mesh transforms are suitable for attaching."""
    if not mesh:
        return False, "Mesh not found"
    
    # Check for non-uniform scale
    scale = mesh.scale
    if abs(scale[0] - scale[1]) > 0.001 or abs(scale[1] - scale[2]) > 0.001:
        return False, "Mesh has non-uniform scale. Please apply scale (Ctrl+A)"
    
    return True, ""

def validate_mesh_name(armature, mesh_name):
    """Validate mesh name doesn't conflict with existing bones."""
    if mesh_name in armature.data.bones:
        return False, f"Bone named '{mesh_name}' already exists in armature"
    return True, ""

def calculate_bone_orientation(mesh, vertices):
    """Calculate optimal bone orientation based on mesh geometry."""
    from mathutils import Vector
    
    # Calculate mesh dimensions
    if not vertices:
        return Vector((0, 0, 0.1)), 0.0
        
    coords = [mesh.data.vertices[v.index].co for v in vertices]
    min_co = Vector(map(min, zip(*coords)))
    max_co = Vector(map(max, zip(*coords)))
    dimensions = max_co - min_co
    
    # Calculate roll angle (simplified - could be enhanced)
    roll_angle = 0.0
    
    return dimensions, roll_angle

def delete_rigidbodies_and_joints(armature: bpy.types.Object):
    """Delete rigid bodies and joints associated with the armature."""
    to_delete = []
    for child in Common.get_top_parent(armature).children:
        if 'rigidbodies' in child.name.lower() or 'joints' in child.name.lower():
            to_delete.append(child)
        for grandchild in child.children:
            if 'rigidbodies' in grandchild.name.lower() or 'joints' in grandchild.name.lower():
                to_delete.append(grandchild)
    for obj in to_delete:
        Common.delete_hierarchy(obj)


def validate_parents_and_transforms(merge_armature: bpy.types.Object, base_armature: bpy.types.Object, context) -> bool:
    """Validate parents and transformations of armatures before merging."""
    merge_parent = merge_armature.parent
    base_parent = base_armature.parent
    if merge_parent or base_parent:
        if context.scene.merge_same_bones:
            for armature, parent in [(merge_armature, merge_parent), (base_armature, base_parent)]:
                if parent:
                    if not is_transform_clean(parent):
                        Common.show_error(6.5, t('MergeArmature.error.checkTransforms'))
                        return False
                    Common.delete(parent)
        else:
            Common.show_error(6.2, t('MergeArmature.error.pleaseFix'))
            return False
    return True


def is_transform_clean(obj: bpy.types.Object) -> bool:
    """Check if an object's transforms are at default values."""
    for i in range(3):
        if obj.scale[i] != 1 or obj.location[i] != 0 or obj.rotation_euler[i] != 0:
            return False
    return True


def attach_mesh_to_armature(mesh: bpy.types.Object, armature: bpy.types.Object, attach_bone_name: str):
    """Attach a mesh to a bone in the armature."""
    # Reparent mesh to target armature
    mesh.parent = armature
    mesh.parent_type = 'OBJECT'

    # Apply transforms
    Common.apply_transforms(armature_name=armature.name)
    Common.apply_transforms_to_mesh(mesh)

    # Prepare mesh vertex groups
    Common.unselect_all()
    Common.set_active(mesh)
    Common.switch('EDIT')
    prepare_mesh_vertex_groups(mesh)

    # Switch armature to edit mode
    Common.unselect_all()
    Common.set_active(armature)
    Common.switch('EDIT')

    # Create bone in target armature
    attach_to_bone = armature.data.edit_bones.get(attach_bone_name)
    if not attach_to_bone:
        raise Exception(f"Attach bone '{attach_bone_name}' not found in armature.")
    mesh_bone = armature.data.edit_bones.new(mesh.name)
    mesh_bone.parent = attach_to_bone

    # Compute the center vector
    center_vector = Common.find_center_vector_of_vertex_group(mesh, mesh.name)
    if center_vector is None:
        raise Exception(f"Unable to find center of vertex group '{mesh.name}'.")

    # Set bone head and tail positions
    mesh_bone.head = center_vector
    mesh_bone.tail = center_vector.copy()
    mesh_bone.tail[2] += 0.1

    # Switch armature back to object mode
    Common.switch('OBJECT')

    # Remove previous armature modifiers and add new one
    add_armature_modifier(mesh, armature)


def prepare_mesh_vertex_groups(mesh: bpy.types.Object):
    """Prepare mesh by assigning all vertices to a new vertex group."""
    # Delete all previous vertex groups
    if mesh.vertex_groups:
        bpy.ops.object.vertex_group_remove(all=True)

    # Select and assign all vertices to new vertex group
    bpy.ops.mesh.select_all(action='SELECT')
    vg = mesh.vertex_groups.new(name=mesh.name)
    bpy.ops.object.vertex_group_assign()

    Common.switch('OBJECT')

    # Verify that the vertex group has vertices assigned
    verts_in_group = [v for v in mesh.data.vertices if vg.index in [g.group for g in v.groups]]
    if not verts_in_group:
        raise Exception(f"Vertex group '{mesh.name}' is empty or does not exist.")

def merge_armatures(
    base_armature_name: str,
    merge_armature_name: str,
    mesh_only: bool,
    mesh_name: Optional[str] = None,
    merge_same_bones: bool = False
):
    tolerance = 0.00008726647  # around 0.005 degrees
    base_armature = Common.get_objects().get(base_armature_name)
    merge_armature = Common.get_objects().get(merge_armature_name)

    if not base_armature or not merge_armature:
        Common.show_error(5.2, [t('MergeArmature.error.notFound', name=merge_armature_name)])
        return

    # Check transforms early
    if not validate_merge_armature_transforms(base_armature, merge_armature, None, tolerance):
        if not bpy.context.scene.apply_transforms:
            Common.show_error(7.5, t('merge_armatures.error.mustapplytransforms'))
            return

    # Fix zero-length bones
    Common.fix_zero_length_bones(base_armature)
    Common.fix_zero_length_bones(merge_armature)

    # Get meshes and join if necessary
    if bpy.context.scene.merge_armatures_join_meshes:
        meshes_base = [Common.join_meshes(armature_name=base_armature_name, apply_transformations=False)]
        meshes_merge = [Common.join_meshes(armature_name=merge_armature_name, apply_transformations=False)]
    else:
        meshes_base = Common.get_meshes_objects(armature_name=base_armature_name)
        meshes_merge = Common.get_meshes_objects(armature_name=merge_armature_name)

    # Filter out None entries
    meshes_base = [mesh for mesh in meshes_base if mesh]
    meshes_merge = [mesh for mesh in meshes_merge if mesh]

    # Apply transforms to base armature only if user requests it
    if bpy.context.scene.apply_transforms:
        Common.apply_transforms(armature_name=base_armature_name)

    # Handle transforms for merge armature based on checkbox
    if len(meshes_merge) == 1:
        mesh_merge = meshes_merge[0]
        if not validate_merge_armature_transforms(base_armature, merge_armature, mesh_merge, tolerance):
            if not bpy.context.scene.apply_transforms:
                Common.show_error(7.5, t('merge_armatures.error.mustapplytransforms'))
                return
            Common.apply_transforms(armature_name=merge_armature_name)
        else:
            adjust_merge_armature_transforms(merge_armature, mesh_merge)
            Common.apply_transforms(armature_name=merge_armature_name)
    elif bpy.context.scene.apply_transforms:
        Common.apply_transforms(armature_name=merge_armature_name)

    # Track original parent relationships for both armatures
    original_parents = {}
    for bone in merge_armature.data.bones:
        original_parents[bone.name] = bone.parent.name if bone.parent else None

    if not merge_same_bones:
        attach_bone = bpy.context.scene.attach_to_bone 
        if attach_bone:
            for bone in merge_armature.data.bones:
                # Only set new parent for root bones (bones without parents)
                if not bone.parent:
                    original_parents[bone.name] = attach_bone
                else:
                    # Keep the original parent relationship for non-root bones
                    original_parents[bone.name] = bone.parent.name

    # Get names of bones in the base armature
    base_bone_names = set(bone.name for bone in base_armature.data.bones)

    # Switch to edit mode on merge armature to prepare for merging
    Common.unselect_all()
    Common.set_active(merge_armature)
    Common.switch('EDIT')

    # Rename bones in merge armature to avoid name conflicts
    bones_to_rename = list(merge_armature.data.edit_bones)
    for bone in bones_to_rename:
        if bone.name in base_bone_names:
            bone.name += '.merge'

    Common.set_default_stage()
    Common.remove_rigidbodies_global()
    Common.unselect_all()

    # Select and join armatures
    Common.set_active(base_armature)
    Common.select(merge_armature)
    if bpy.ops.object.join.poll():
        bpy.ops.object.join()

    # Update references after joining
    armature = base_armature

    # Re-establish parent relationships
    Common.unselect_all()
    Common.set_active(armature)
    Common.switch('EDIT')
    for bone in armature.data.edit_bones:
        base_name = bone.name.replace('.merge', '')
        if base_name in original_parents:
            parent_name = original_parents[base_name]
            if parent_name:
                parent_bone = armature.data.edit_bones.get(parent_name)
                if parent_bone:
                    bone.parent = parent_bone

    Common.switch('OBJECT')

    # Clean up shape keys if needed
    if bpy.context.scene.merge_armatures_cleanup_shape_keys:
        for mesh_base in meshes_base:
            Common.clean_shapekeys(mesh_base)
        for mesh_merge in meshes_merge:
            Common.clean_shapekeys(mesh_merge)

    # Join meshes if necessary
    if bpy.context.scene.merge_armatures_join_meshes:
        meshes_merged = [Common.join_meshes(armature_name=base_armature_name, apply_transformations=False)]
    else:
        meshes_merged = meshes_base + meshes_merge
        for mesh in meshes_merged:
            mesh.parent = base_armature
            Common.repair_mesh(mesh, base_armature_name)
    meshes_merged = [mesh for mesh in meshes_merged if mesh]

    # Process vertex groups to merge or rename '.merge' groups
    if not mesh_only:
        process_vertex_groups(meshes_merged)
        
        # Remove zero weight bones after vertex groups are processed
        if bpy.context.scene.merge_armatures_remove_zero_weight_bones:
            for mesh in meshes_merged:
                Common.remove_unused_vertex_groups(ignore_main_bones=True)
            if Common.get_meshes_objects(armature_name=base_armature_name):
                Common.delete_zero_weight(armature_name=base_armature_name)
                
            # Clean up the scene
            Common.set_default_stage()
            Common.remove_rigidbodies_global()

    # Remove any remaining '.merge' bones
    Common.unselect_all()
    Common.set_active(armature)
    Common.switch('EDIT')
    edit_bones = armature.data.edit_bones
    bones_to_remove = [bone for bone in edit_bones if bone.name.endswith('.merge')]
    for bone in bones_to_remove:
        edit_bones.remove(bone)
    Common.switch('OBJECT')

    # Final cleanup
    Common.set_default_stage()
    Common.remove_rigidbodies_global()
    if not mesh_only:
        if bpy.context.scene.merge_armatures_remove_zero_weight_bones:
            Common.remove_unused_vertex_groups()
            if Common.get_meshes_objects(armature_name=base_armature_name):
                Common.delete_zero_weight(armature_name=base_armature_name)
            Common.set_default_stage()
            Common.remove_rigidbodies_global()

    # Clear unused data blocks
    Common.clear_unused_data()

    # Fix armature names
    Common.fix_armature_names(armature_name=base_armature_name)

def validate_merge_armature_transforms(
    base_armature: bpy.types.Object,
    merge_armature: bpy.types.Object, 
    mesh_merge: Optional[bpy.types.Object],
    tolerance: float
) -> bool:
    """Validate transforms of both armatures and mesh."""
    # Check if both armatures have the same scale values
    for i in [0, 1, 2]:
        if abs(base_armature.scale[i] - merge_armature.scale[i]) > tolerance:
            return False
            
        # Check rotations
        if abs(merge_armature.rotation_euler[i]) > tolerance or \
           (mesh_merge and abs(mesh_merge.rotation_euler[i]) > tolerance):
            return False
            
    return True

def adjust_merge_armature_transforms(
    merge_armature: bpy.types.Object,
    mesh_merge: bpy.types.Object
):
    """Adjust transforms of the merge armature."""
    old_loc = list(merge_armature.location)
    old_scale = list(merge_armature.scale)

    for i in [0, 1, 2]:
        merge_armature.location[i] = (mesh_merge.location[i] * old_scale[i]) + old_loc[i]
        merge_armature.rotation_euler[i] = mesh_merge.rotation_euler[i]
        merge_armature.scale[i] = mesh_merge.scale[i] * old_scale[i]

    for i in [0, 1, 2]:
        mesh_merge.location[i] = 0
        mesh_merge.rotation_euler[i] = 0
        mesh_merge.scale[i] = 1

def detect_bones_to_merge(
    base_edit_bones: bpy.types.ArmatureEditBones,
    merge_edit_bones: bpy.types.ArmatureEditBones,
    tolerance: float,
    merge_same_bones: bool
) -> List[str]:
    """Detect corresponding bones between base and merge armatures using smart detection and position tolerance."""
    bones_to_merge = []

    # Cache base bone positions
    base_bones_positions = {
        bone.name: np.array(bone.head) for bone in base_edit_bones
    }

    # Smart bone detection
    for merge_bone in merge_edit_bones:
        merge_bone_position = np.array(merge_bone.head)
        found_match = False

        if merge_same_bones and merge_bone.name in base_bones_positions:
            # If merging same bones by name
            bones_to_merge.append(merge_bone.name)
            found_match = True
        else:
            # Find bones with close positions
            for base_bone_name, base_bone_position in base_bones_positions.items():
                if np.linalg.norm(merge_bone_position - base_bone_position) <= tolerance:
                    bones_to_merge.append(base_bone_name)
                    found_match = True
                    break

        if not found_match:
            # Handle unmatched bones if needed
            pass

    return bones_to_merge

def process_vertex_groups(meshes: List[bpy.types.Object]):
    """Process all vertex groups in the given meshes, merging or renaming groups with '.merge' suffix."""
    for mesh in meshes:
        vg_names = {vg.name for vg in mesh.vertex_groups}

        # Find all vertex groups ending with '.merge'
        merge_vg_names = [vg_name for vg_name in vg_names if vg_name.endswith('.merge')]

        for vg_merge_name in merge_vg_names:
            # Remove the '.merge' suffix to get the base vertex group name
            base_name = vg_merge_name[:-6]  # Remove the last 6 characters ('.merge')
            vg_merge = mesh.vertex_groups.get(vg_merge_name)
            vg_base = mesh.vertex_groups.get(base_name)

            if vg_merge is None:
                continue  # Skip if the vertex group is not found

            if vg_base:
                # Both vertex groups exist, so merge them using the mix_weights function
                Common.mix_weights(mesh, vg_merge_name, base_name, mix_set='ALL')
                # Remove the '.merge' vertex group after merging (handled in mix_weights)
            else:
                # Only the '.merge' vertex group exists, rename it to the base name
                vg_merge.name = base_name

def mix_vertex_groups(mesh: bpy.types.Object, vg_from_name: str, vg_to_name: str):
    """Mix vertex group weights from 'vg_from' into 'vg_to' and remove 'vg_from'."""
    vg_from = mesh.vertex_groups.get(vg_from_name)
    vg_to = mesh.vertex_groups.get(vg_to_name)
        
    if not vg_from or not vg_to:
        return

    num_vertices = len(mesh.data.vertices)
    weights_from = np.zeros(num_vertices)
    weights_to = np.zeros(num_vertices)

    # Build index mappings
    idx_from = vg_from.index
    idx_to = vg_to.index

    # Collect weights efficiently
    for v in mesh.data.vertices:
        for g in v.groups:
            if g.group == idx_from:
                weights_from[v.index] = g.weight
            elif g.group == idx_to:
                weights_to[v.index] = g.weight

    # Combine weights
    weights_combined = weights_from + weights_to
    weights_combined = np.clip(weights_combined, 0.0, 1.0)  # Optional: Clamp weights to [0, 1]

    # Apply combined weights to the target vertex group
    vg_to.add(range(num_vertices), weights_combined.tolist(), 'REPLACE')

    # Remove the source vertex group
    mesh.vertex_groups.remove(vg_from)

def add_armature_modifier(mesh: bpy.types.Object, armature: bpy.types.Object):
    """Add an armature modifier to the mesh."""
    # Remove previous armature modifiers
    for mod in mesh.modifiers:
        if mod.type == 'ARMATURE':
            mesh.modifiers.remove(mod)

    # Create new armature modifier
    modifier = mesh.modifiers.new('Armature', 'ARMATURE')
    modifier.object = armature