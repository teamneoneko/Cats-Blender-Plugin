# MIT License

import os
import bpy
import copy
import math
import bmesh
import mathutils
from typing import Optional, Dict, Tuple, Set

from collections import OrderedDict
from random import random
from itertools import chain

from . import common as Common
from . import armature as Armature
from .register import register_wrap
from .translations import t

VALID_EYE_NAMES = {
    'left': ['LeftEye', 'Eye_L', 'eye_L', 'eye.L', 'EyeLeft', 'left_eye', 'l_eye'],
    'right': ['RightEye', 'Eye_R', 'eye_R', 'eye.R', 'EyeRight', 'right_eye', 'r_eye']
}

class EyeTrackingBackup:
    def __init__(self):
        self.backup_path = os.path.join(bpy.app.tempdir, "eye_tracking_backup.json")
        self.bone_positions: Dict[str, Dict[str, Tuple[float, float, float]]] = {}
        
    def store_bone_positions(self, armature) -> bool:
        try:
            self.bone_positions = {
                'LeftEye': {
                    'head': tuple(armature.data.bones['LeftEye'].head_local),
                    'tail': tuple(armature.data.bones['LeftEye'].tail_local)
                },
                'RightEye': {
                    'head': tuple(armature.data.bones['RightEye'].head_local),
                    'tail': tuple(armature.data.bones['RightEye'].tail_local)
                }
            }
            
            with open(self.backup_path, 'w') as f:
                json.dump(self.bone_positions, f)
            return True
        except Exception as e:
            print(f"Backup failed: {str(e)}")
            return False
            
    def restore_bone_positions(self, armature) -> bool:
        try:
            if not os.path.exists(self.backup_path):
                return False
                
            with open(self.backup_path, 'r') as f:
                backup_data = json.load(f)
                
            Common.switch('EDIT')
            
            for bone_name, positions in backup_data.items():
                if bone_name in armature.data.edit_bones:
                    bone = armature.data.edit_bones[bone_name]
                    bone.head = positions['head']
                    bone.tail = positions['tail']
                    
            return True
        except Exception as e:
            print(f"Restore failed: {str(e)}")
            return False

class EyeTrackingValidator:
    @staticmethod
    def find_eye_vertex_groups(mesh_name: str) -> Tuple[str, str]:
        """Find eye vertex groups using multiple naming conventions"""
        mesh = Common.get_objects().get(mesh_name)
        if not mesh:
            return None, None
            
        left_group = None
        right_group = None
        
        for group in mesh.vertex_groups:
            if any(name.lower() in group.name.lower() for name in VALID_EYE_NAMES['left']):
                left_group = group.name
            if any(name.lower() in group.name.lower() for name in VALID_EYE_NAMES['right']):
                right_group = group.name
                
        return left_group, right_group

    @staticmethod
    def validate_setup(context, mesh_name: str) -> Tuple[bool, str]:
        """Validate the complete eye tracking setup"""
        # Validate armature
        armature = Common.get_armature()
        if not armature:
            return False, t('EyeTrackingValidator.error.noArmature')
            
        # Validate mesh
        mesh = Common.get_objects().get(mesh_name)
        if not mesh:
            return False, t('EyeTrackingValidator.error.noMesh', mesh=mesh_name)
            
        # Validate shape keys
        if not Common.has_shapekeys(mesh):
            return False, t('EyeTrackingValidator.error.noShapekeys')
            
        # Validate vertex groups
        left_group, right_group = EyeTrackingValidator.find_eye_vertex_groups(mesh_name)
        missing_groups = []
        
        if not left_group:
            missing_groups.append(t('EyeTrackingValidator.error.leftEye'))
        if not right_group:
            missing_groups.append(t('EyeTrackingValidator.error.rightEye'))
            
        if missing_groups:
            return False, t('EyeTrackingValidator.error.missingGroups', groups=', '.join(missing_groups))
            
        # Validate bone structure
        required_bones = [context.scene.head, context.scene.eye_left, context.scene.eye_right]
        missing_bones = [bone for bone in required_bones if bone not in armature.data.bones]
        
        if missing_bones:
            return False, t('EyeTrackingValidator.error.missingBones', bones=', '.join(missing_bones))
            
        return True, t('EyeTrackingValidator.success')

    @staticmethod
    def validate_weights(mesh_name: str, vertex_group: str) -> bool:
        """Validate that vertex groups have proper weight assignments"""
        mesh = Common.get_objects().get(mesh_name)
        if not mesh:
            return False
            
        group = mesh.vertex_groups.get(vertex_group)
        if not group:
            return False
            
        for vertex in mesh.data.vertices:
            for group_element in vertex.groups:
                if group_element.group == group.index and group_element.weight > 0:
                    return True
                    
        return False

    @staticmethod
    def get_eye_bone_names(armature) -> Dict[str, str]:
        """Get standardized eye bone names based on armature"""
        eye_bones = {'left': None, 'right': None}
        
        for bone in armature.data.bones:
            if any(name.lower() in bone.name.lower() for name in VALID_EYE_NAMES['left']):
                eye_bones['left'] = bone.name
            if any(name.lower() in bone.name.lower() for name in VALID_EYE_NAMES['right']):
                eye_bones['right'] = bone.name
                
        return eye_bones


class VertexGroupCache:
    _cache = {}
    
    @classmethod
    def get_vertex_indices(cls, mesh_name: str, group_name: str) -> Optional[set]:
        cache_key = f"{mesh_name}_{group_name}"
        
        if cache_key in cls._cache:
            return cls._cache[cache_key]
            
        mesh = Common.get_objects().get(mesh_name)
        if not mesh:
            return None
            
        group = mesh.vertex_groups.get(group_name)
        if not group:
            return None
            
        indices = {v.index for v in mesh.data.vertices
                  if any(g.group == group.index for g in v.groups)}
                  
        cls._cache[cache_key] = indices
        return indices
    
    @classmethod
    def clear_cache(cls):
        cls._cache.clear()


@register_wrap
class RotateEyeBonesForAv3Button(bpy.types.Operator):
    """Reorient eye bones to point straight up and have zero roll. This isn't necessary for VRChat because eye-tracking
    rotations can be set separately per eye in Unity, however it does simplify setting up the eye-tracking rotations,
    because both eyes can use the same rotations, and it makes it so that (0,0,0) rotation results in the eyes looking
    forward."""
    bl_idname = "cats_eyes.av3_orient_eye_bones"
    bl_label = t("Av3EyeTrackingRotateEyeBones.label")
    bl_description = t("Av3EyeTrackingRotateEyeBones.desc")
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        # The eye_left and eye_right properties already check that there is an armature, so we don't need to check that
        # here.
        scene = context.scene
        if not (Common.is_enum_non_empty(scene.eye_left) or Common.is_enum_non_empty(scene.eye_right)):
            cls.poll_message_set(t("Av3EyeTrackingRotateEyeBones.poll.noBones"))
            return False

        # If another Object is currently in EDIT mode and the armature is not also in the same EDIT mode, we cannot swap
        # the armature into EDIT mode and then swap back to the original Object in its original EDIT mode because
        # Undo/Redo will not work for the changes made by this Operator.
        armature = Common.get_armature()
        if context.object.mode == 'EDIT' and armature not in context.objects_in_mode:
            cls.poll_message_set(t("Av3EyeTrackingRotateEyeBones.poll.notInCurrentEditMode", armature=armature.name))
            return False

        return True

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene

        armature_obj = Common.get_armature()
        armature = armature_obj.data

        already_editing = armature_obj.mode == 'EDIT'

        # If we're in EDIT mode already, we need to access the matrices of the edit bones because the bones may not be
        # up-to-date.
        if already_editing:
            bones = armature.edit_bones
            matrix_attribute = "matrix"
        else:
            bones = armature.bones
            matrix_attribute = "matrix_local"

        # Both bones could be set the same, so use a set to ensure we only have unique names
        eye_bone_names = {scene.eye_left, scene.eye_right}

        # The position of the head and tail are easy to compare from OBJECT mode through head_local and tail_local, but
        # bone roll is not easily accessible.
        # We can determine bone roll (and the overall orientation of the bone) through matrix_local.
        # The expected matrix_local for a bone pointing straight up and with zero roll is a 90 degrees rotation about
        # the X-axis and no other rotation.
        straight_up_and_zero_roll = mathutils.Matrix.Rotation(math.pi/2, 3, 'X')

        # Check each bone
        for eye_bone_name in list(eye_bone_names):
            bone = bones[eye_bone_name]

            # Due to floating-point precision, it's unlikely that the bone's matrix_local will exactly match, so
            # we'll check if it's close enough.
            matrix_close_enough = True

            # Create iterators to iterate through each value of the matrices in order
            matrix_iter = chain.from_iterable(getattr(bone, matrix_attribute).to_3x3())
            expected_matrix_iter = chain.from_iterable(straight_up_and_zero_roll)
            for bone_val, expected_val in zip(matrix_iter, expected_matrix_iter):
                # Note that while the values may be accessed as standard python float which is up to double-precision,
                # mathutils.Matrix/Vector only store single-precision float, so the tolerances need to be more lenient
                # than they might usually be.
                if not math.isclose(bone_val, expected_val, rel_tol=1e-6, abs_tol=1e-6):
                    matrix_close_enough = False
                    break
            if matrix_close_enough:
                eye_bone_names.remove(eye_bone_name)

        if not eye_bone_names:
            # Both bones are already oriented correctly
            self.report({'INFO'}, t("Av3EyeTrackingRotateEyeBones.info.noChanges"))
            return {'CANCELLED'}

        if not already_editing:
            # Store active/selected/hidden object states, so they can be restored afterwards.
            saved_data = Common.SavedData()

            # set_default_stage will set the armature as active
            armature_obj2 = Common.set_default_stage()
            assert armature_obj == armature_obj2

            # Bones can only be moved while in EDIT mode.
            Common.switch('EDIT')

        edit_bones = armature.edit_bones

        # Get each eye's EditBone
        eye_bones = {edit_bones[eye_bone_name] for eye_bone_name in eye_bone_names}

        # Setting a bone's matrix doesn't currently update mirrored bones like when setting a bone's head/tail, but
        # we'll temporarily disable mirroring in-case this changes in the future.
        orig_mirroring = armature.use_mirror_x
        armature.use_mirror_x = False

        # We're going to result in moving the tails of the eye bones, but we don't want this to affect any other bones,
        # so disconnect any bones that are connected to the eye bones.
        for bone in edit_bones:
            if bone.use_connect and bone.parent in eye_bones:
                bone.use_connect = False

        for eye_bone in eye_bones:
            # Re-orient the bone to point straight up with zero roll, maintaining the original length and the position
            # of the bone's head.
            new_matrix = straight_up_and_zero_roll.to_4x4()
            new_matrix.translation = eye_bone.matrix.translation
            eye_bone.matrix = new_matrix

        # Restore the mirror setting.
        armature.use_mirror_x = orig_mirroring

        if not already_editing:
            Common.switch('OBJECT')
            # Restore active/selected/hidden object states
            saved_data.load()

        self.report({'INFO'}, t("Av3EyeTrackingRotateEyeBones.success"))
        return {'FINISHED'}

@register_wrap
class CreateEyesButton(bpy.types.Operator):
    bl_idname = 'cats_eyes.create_eye_tracking'
    bl_label = t('CreateEyesButton.label')
    bl_description = t('CreateEyesButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    mesh = None

    @classmethod
    def poll(cls, context):
        if not Common.get_meshes_objects(check=False):
            return False

        if Common.is_enum_empty(context.scene.head) \
                or Common.is_enum_empty(context.scene.eye_left) \
                or Common.is_enum_empty(context.scene.eye_right):
            return False

        if context.scene.disable_eye_blinking and context.scene.disable_eye_movement:
            return False

        return True

    def execute(self, context):
        wm = bpy.context.window_manager
        wm.progress_begin(0, 100)

        # Validate setup
        validator = EyeTrackingValidator()
        is_valid, message = validator.validate_setup(context, context.scene.mesh_name_eye)
        if not is_valid:
            self.report({'ERROR'}, message)
            wm.progress_end()
            return {'CANCELLED'}

        # Create backup
        backup = EyeTrackingBackup()
        if not backup.store_bone_positions(Common.get_armature()):
            self.report({'WARNING'}, "Failed to create backup")

        try:
            saved_data = Common.SavedData()
            wm.progress_update(10)
            context.scene.progress_update = 10

            # Set the stage
            armature = Common.set_default_stage()
            Common.switch('EDIT')
            wm.progress_update(20)
            context.scene.progress_update = 20

            mesh_name = context.scene.mesh_name_eye
            self.mesh = Common.get_objects().get(mesh_name)

            # Set up old bones
            head = armature.data.edit_bones.get(context.scene.head)
            old_eye_left = armature.data.edit_bones.get(context.scene.eye_left)
            old_eye_right = armature.data.edit_bones.get(context.scene.eye_right)

            # Validation checks with proper error messages
            if not context.scene.disable_eye_blinking:
                if any(Common.is_enum_empty(getattr(context.scene, attr)) for attr in 
                      ['wink_left', 'wink_right', 'lowerlid_left', 'lowerlid_right']):
                    saved_data.load()
                    self.report({'ERROR'}, t('CreateEyesButton.error.noShapeSelected'))
                    return {'CANCELLED'}

            # Use cached vertex groups for performance
            VertexGroupCache.clear_cache()
            left_eye_verts = VertexGroupCache.get_vertex_indices(mesh_name, 'LeftEye')
            right_eye_verts = VertexGroupCache.get_vertex_indices(mesh_name, 'RightEye')
            wm.progress_update(30)
            context.scene.progress_update = 30

            # Create the new eye bones
            new_left_eye = bpy.context.object.data.edit_bones.new('LeftEye')
            new_right_eye = bpy.context.object.data.edit_bones.new('RightEye')
            wm.progress_update(40)
            context.scene.progress_update = 40

            # Parent them correctly
            new_left_eye.parent = head
            new_right_eye.parent = head
            wm.progress_update(50)
            context.scene.progress_update = 50

            # Calculate their new positions
            fix_eye_position(context, old_eye_left, new_left_eye, head, False)
            fix_eye_position(context, old_eye_right, new_right_eye, head, True)
            wm.progress_update(60)
            context.scene.progress_update = 60

            # Store names before mode switch
            new_right_eye_name = new_right_eye.name
            old_eye_left_name = old_eye_left.name
            old_eye_right_name = old_eye_right.name
            head_name = head.name

            # Switch to mesh
            Common.set_active(self.mesh)
            Common.switch('OBJECT')
            wm.progress_update(70)
            context.scene.progress_update = 70

            # Fix shape key bug
            bpy.context.object.show_only_shape_key = False

            # Handle vertex groups
            if not context.scene.disable_eye_movement:
                self.copy_vertex_group(old_eye_left_name, 'LeftEye')
                self.copy_vertex_group(old_eye_right_name, 'RightEye')
            else:
                for bone in ['LeftEye', 'RightEye']:
                    group = self.mesh.vertex_groups.get(bone)
                    if group is not None:
                        self.mesh.vertex_groups.remove(group)
            wm.progress_update(80)
            context.scene.progress_update = 80

            # Handle shape keys
            shapes = [context.scene.wink_left, context.scene.wink_right, 
                     context.scene.lowerlid_left, context.scene.lowerlid_right]
            new_shapes = ['vrc.blink_left', 'vrc.blink_right', 
                         'vrc.lowerlid_left', 'vrc.lowerlid_right']

            # Remove existing shapekeys efficiently
            for new_shape in new_shapes:
                for index, shapekey in enumerate(self.mesh.data.shape_keys.key_blocks):
                    if shapekey.name == new_shape and new_shape not in shapes:
                        bpy.context.active_object.active_shape_key_index = index
                        bpy.ops.object.shape_key_remove()
                        break
            wm.progress_update(85)
            context.scene.progress_update = 85

            # Copy shape keys with progress updates
            shapes[0] = self.copy_shape_key(context, shapes[0], new_shapes, 1)
            wm.progress_update(88)
            context.scene.progress_update = 88
            shapes[1] = self.copy_shape_key(context, shapes[1], new_shapes, 2)
            wm.progress_update(91)
            context.scene.progress_update = 91
            shapes[2] = self.copy_shape_key(context, shapes[2], new_shapes, 3)
            wm.progress_update(94)
            context.scene.progress_update = 94
            shapes[3] = self.copy_shape_key(context, shapes[3], new_shapes, 4)
            wm.progress_update(97)
            context.scene.progress_update = 97

            Common.sort_shape_keys(mesh_name)

            # Reset the scenes
            context.scene.head = head_name
            context.scene.eye_left = old_eye_left_name
            context.scene.eye_right = old_eye_right_name
            context.scene.wink_left = shapes[0]
            context.scene.wink_right = shapes[1]
            context.scene.lowerlid_left = shapes[2]
            context.scene.lowerlid_right = shapes[3]

            # Cleanup
            Common.set_default_stage()
            Common.remove_rigidbodies_global()
            Common.remove_empty()
            Common.fix_armature_names()
            wm.progress_update(100)
            context.scene.progress_update = 100

            # Verify hierarchy
            is_correct = Armature.check_hierarchy(True, [['Hips', 'Spine', 'Chest', 'Neck', 'Head']])

            if context.scene.disable_eye_movement:
                repair_shapekeys_mouth(mesh_name)
            else:
                repair_shapekeys(mesh_name, new_right_eye_name)

            saved_data.load()
            wm.progress_end()

            if not is_correct['result']:
                self.report({'ERROR'}, is_correct['message'])
                self.report({'ERROR'}, t('CreateEyesButton.error.hierarchy'))
            else:
                context.scene.eye_mode = 'TESTING'
                self.report({'INFO'}, t('CreateEyesButton.success'))

            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Setup failed: {str(e)}")
            if backup.restore_bone_positions(Common.get_armature()):
                self.report({'WARNING'}, "Restored from backup")
            wm.progress_end()
            return {'CANCELLED'}

    def copy_vertex_group(self, vertex_group, rename_to):
        # iterate through the vertex group
        vertex_group_index = 0
        for group in self.mesh.vertex_groups:
            # Find the vertex group
            if group.name == vertex_group:
                # Copy the group and rename
                self.mesh.vertex_groups.active_index = vertex_group_index
                bpy.ops.object.vertex_group_copy()
                self.mesh.vertex_groups[vertex_group + '_copy'].name = rename_to
                break

            vertex_group_index += 1

    def copy_shape_key(self, context, from_shape, new_names, new_index):
        blinking = not context.scene.disable_eye_blinking
        new_name = new_names[new_index - 1]

        # Rename shapekey if it already exists and set all values to 0
        for shapekey in self.mesh.data.shape_keys.key_blocks:
            shapekey.value = 0
            if shapekey.name == new_name:
                shapekey.name = shapekey.name + '_old'
                if from_shape == new_name:
                    from_shape = shapekey.name

        # Create new shape key
        for index, shapekey in enumerate(self.mesh.data.shape_keys.key_blocks):
            if from_shape == shapekey.name:
                self.mesh.active_shape_key_index = index
                shapekey.value = 1
                self.mesh.shape_key_add(name=new_name, from_mix=blinking)
                break

        # Reset shape keys
        for shapekey in self.mesh.data.shape_keys.key_blocks:
            shapekey.value = 0
        self.mesh.active_shape_key_index = 0
        return from_shape

    def vertex_group_exists(self, bone_name):
        data = self.mesh.data
        verts = data.vertices

        for vert in verts:
            i = vert.index
            try:
                self.mesh.vertex_groups[bone_name].weight(i)
                return True
            except:
                pass

        return False


def fix_eye_position(context, old_eye, new_eye, head, right_side):
    # Verify that the new eye bone is in the correct position
    # by comparing the old eye vertex group average vector location
    mesh = Common.get_objects()[context.scene.mesh_name_eye]
    scale = -context.scene.eye_distance + 1

    if not context.scene.disable_eye_movement:
        if head:
            coords_eye = Common.find_center_vector_of_vertex_group(mesh, old_eye.name)
        else:
            coords_eye = Common.find_center_vector_of_vertex_group(mesh, new_eye.name)

        if coords_eye is False:
            return

        if head:
            p1 = mesh.matrix_world @ head.head
            p2 = mesh.matrix_world @ coords_eye
            length = (p1 - p2).length
            print(length)  # TODO calculate scale if bone is too close to center of the eye

    # dist = math.sqrt((coords_eye[0] - head.head[x_cord]) ** 2 + (coords_eye[1] - head.head[y_cord]) ** 2 + (coords_eye[2] - head.head[z_cord]) ** 2)
    # dist2 = np.linalg.norm(coords_eye - head.head)
    # dist3 = math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2 + (p1[2] - p2[2]) ** 2)
    # dist4 = np.linalg.norm(p1 - p2)
    # print(dist)
    # print(dist2)
    # print(2 ** 2)
    # print(dist4)

    # Check if bone matrix == world matrix, important for xps models
    x_cord, y_cord, z_cord, fbx = Common.get_bone_orientations(Common.get_armature())

    if context.scene.disable_eye_movement:
        if head is not None:
            if right_side:
                new_eye.head[x_cord] = head.head[x_cord] + 0.05
            else:
                new_eye.head[x_cord] = head.head[x_cord] - 0.05
            new_eye.head[y_cord] = head.head[y_cord]
            new_eye.head[z_cord] = head.head[z_cord]
    else:
        new_eye.head[x_cord] = old_eye.head[x_cord] + scale * (coords_eye[0] - old_eye.head[x_cord])
        new_eye.head[y_cord] = old_eye.head[y_cord] + scale * (coords_eye[1] - old_eye.head[y_cord])
        new_eye.head[z_cord] = old_eye.head[z_cord] + scale * (coords_eye[2] - old_eye.head[z_cord])

    new_eye.tail[x_cord] = new_eye.head[x_cord]
    new_eye.tail[y_cord] = new_eye.head[y_cord]
    new_eye.tail[z_cord] = new_eye.head[z_cord] + 0.1


# Repair vrc shape keys
def repair_shapekeys(mesh_name, vertex_group):
    # This is done to fix a very weird bug where the mouth stays open sometimes
    Common.set_default_stage()
    Common.remove_rigidbodies_global()
    mesh = Common.get_objects()[mesh_name]
    Common.unselect_all()
    Common.set_active(mesh)
    Common.switch('EDIT')
    Common.switch('OBJECT')

    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    bm.verts.ensure_lookup_table()

    # Get a vertex from the eye vertex group # TODO https://i.imgur.com/tWi8lk6.png after many times resetting the eyes
    print('DEBUG: Group: ' + vertex_group)
    group = mesh.vertex_groups.get(vertex_group)
    if group is None:
        print('DEBUG: Group: ' + vertex_group + ' not found!')
        repair_shapekeys_mouth(mesh_name)
        return
    print('DEBUG: Group: ' + vertex_group + ' found!')

    vcoords = None
    gi = group.index
    for v in mesh.data.vertices:
        for g in v.groups:
            if g.group == gi:
                vcoords = v.co.xyz

    if not vcoords:
        return

    print('DEBUG: Repairing shapes!')
    # Move that vertex by a tiny amount
    moved = False
    i = 0
    for key in bm.verts.layers.shape.keys():
        if not key.startswith('vrc.'):
            continue
        print('DEBUG: Repairing shape: ' + key)
        value = bm.verts.layers.shape.get(key)
        for index, vert in enumerate(bm.verts):
            if vert.co.xyz == vcoords:
                if index < i:
                    continue
                shapekey = vert
                shapekey_coords = mesh.matrix_world @ shapekey[value]
                shapekey_coords[0] -= 0.00007 * randBoolNumber()
                shapekey_coords[1] -= 0.00007 * randBoolNumber()
                shapekey_coords[2] -= 0.00007 * randBoolNumber()
                shapekey[value] = mesh.matrix_world.inverted() @ shapekey_coords
                print('DEBUG: Repaired shape: ' + key)
                i += 1
                moved = True
                break

    bm.to_mesh(mesh.data)

    if not moved:
        print('Error: Shapekey repairing failed for some reason! Using random shapekey method now.')
        repair_shapekeys_mouth(mesh_name)


def randBoolNumber():
    if random() < 0.5:
        return -1
    return 1


# Repair vrc shape keys with random vertex
def repair_shapekeys_mouth(mesh_name):  # TODO Add vertex repairing!
    # This is done to fix a very weird bug where the mouth stays open sometimes
    Common.set_default_stage()
    Common.remove_rigidbodies_global()
    mesh = Common.get_objects()[mesh_name]
    Common.unselect_all()
    Common.set_active(mesh)
    Common.switch('EDIT')
    Common.switch('OBJECT')

    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    bm.verts.ensure_lookup_table()

    # Move that vertex by a tiny amount
    moved = False
    for key in bm.verts.layers.shape.keys():
        if not key.startswith('vrc'):
            continue
        value = bm.verts.layers.shape.get(key)
        for vert in bm.verts:
            shapekey = vert
            shapekey_coords = mesh.matrix_world @ shapekey[value]
            shapekey_coords[0] -= 0.00007
            shapekey_coords[1] -= 0.00007
            shapekey_coords[2] -= 0.00007
            shapekey[value] = mesh.matrix_world.inverted() @ shapekey_coords
            print('TEST')
            moved = True
            break

    bm.to_mesh(mesh.data)

    if not moved:
        print('Error: Random shapekey repairing failed for some reason! Canceling!')


eye_left = None
eye_right = None
eye_left_data = None
eye_right_data = None
eye_left_rot = []
eye_right_rot = []


@register_wrap
class StartTestingButton(bpy.types.Operator):
    bl_idname = 'cats_eyes.start_testing'
    bl_label = t('StartTestingButton.label')
    bl_description = t('StartTestingButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        armature = Common.get_armature()
        if 'LeftEye' in armature.pose.bones:
            if 'RightEye' in armature.pose.bones:
                if Common.get_objects().get(context.scene.mesh_name_eye) is not None:
                    return True
        return False

    def execute(self, context):
        armature = Common.set_default_stage()
        Common.remove_rigidbodies_global()
        Common.switch('POSE')
        armature.data.pose_position = 'POSE'

        global eye_left, eye_right, eye_left_data, eye_right_data, eye_left_rot, eye_right_rot
        eye_left = armature.pose.bones.get('LeftEye')
        eye_right = armature.pose.bones.get('RightEye')
        eye_left_data = armature.data.bones.get('LeftEye')
        eye_right_data = armature.data.bones.get('RightEye')

        # Save initial eye rotations
        eye_left.rotation_mode = 'XYZ'
        eye_left_rot = copy.deepcopy(eye_left.rotation_euler)
        eye_right.rotation_mode = 'XYZ'
        eye_right_rot = copy.deepcopy(eye_right.rotation_euler)

        if eye_left is None or eye_right is None or eye_left_data is None or eye_right_data is None:
            return {'FINISHED'}

        for shape_key in Common.get_objects()[context.scene.mesh_name_eye].data.shape_keys.key_blocks:
            shape_key.value = 0

        armature_obj = Common.get_armature()
        for pb in armature_obj.pose.bones:
            pb.select = True
        bpy.ops.pose.rot_clear()
        bpy.ops.pose.scale_clear()
        bpy.ops.pose.transforms_clear()
        for pb in armature_obj.pose.bones:
            pb.select = False
            pb.hide = True

        # eye_left.select = True
        # eye_right.select = True
        eye_left_data.hide = False
        eye_right_data.hide = False

        context.scene.eye_rotation_x = 0
        context.scene.eye_rotation_y = 0

        return {'FINISHED'}


@register_wrap
class StopTestingButton(bpy.types.Operator):
    bl_idname = 'cats_eyes.stop_testing'
    bl_label = t('StopTestingButton.label')
    bl_description = t('StopTestingButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        global eye_left, eye_right, eye_left_data, eye_right_data, eye_left_rot, eye_right_rot
        if eye_left:
            context.scene.eye_rotation_x = 0
            context.scene.eye_rotation_y = 0

        if not context.object or context.object.mode != 'POSE':
            Common.set_default_stage()
            Common.remove_rigidbodies_global()
            Common.switch('POSE')

        armature_obj = Common.get_armature()
        for pb in armature_obj.pose.bones:
            pb.hide = False
            pb.select = True
        bpy.ops.pose.rot_clear()
        bpy.ops.pose.scale_clear()
        bpy.ops.pose.transforms_clear()
        for pb in armature_obj.pose.bones:
            pb.select = False

        armature = Common.set_default_stage()
        # armature.data.pose_position = 'REST'

        for shape_key in Common.get_objects()[context.scene.mesh_name_eye].data.shape_keys.key_blocks:
            shape_key.value = 0

        eye_left = None
        eye_right = None
        eye_left_data = None
        eye_right_data = None
        eye_left_rot = []
        eye_right_rot = []

        return {'FINISHED'}

# This gets called by the eye testing sliders
def set_rotation(self, context):
    global eye_left, eye_right, eye_left_rot, eye_right_rot

    # Initialize testing mode if not already set up
    if not eye_left or not eye_right:
        StartTestingButton.execute(StartTestingButton, context)
        return None

    # Apply rotations
    eye_left.rotation_mode = 'XYZ'
    eye_right.rotation_mode = 'XYZ'

    # Store and print values for debugging
    x_rotation = math.radians(context.scene.eye_rotation_x)
    y_rotation = math.radians(context.scene.eye_rotation_y)
    
    # Apply rotations with initial offset
    eye_left.rotation_euler[0] = eye_left_rot[0] + x_rotation
    eye_left.rotation_euler[1] = eye_left_rot[1] + y_rotation

    eye_right.rotation_euler[0] = eye_right_rot[0] + x_rotation
    eye_right.rotation_euler[1] = eye_right_rot[1] + y_rotation

    return None


def stop_testing(self, context):
        global eye_left, eye_right, eye_left_data, eye_right_data, eye_left_rot, eye_right_rot
        if not eye_left or not eye_right or not eye_left_data or not eye_right_data or not eye_left_rot or not eye_right_rot:
            return None

        armature = Common.set_default_stage()
        Common.switch('POSE')
        armature.data.pose_position = 'POSE'

        context.scene.eye_rotation_x = 0
        context.scene.eye_rotation_y = 0

        for pb in armature.data.bones:
            pb.hide = False
            pb.select = True
        bpy.ops.pose.rot_clear()
        bpy.ops.pose.scale_clear()
        bpy.ops.pose.transforms_clear()
        for pb in armature.data.bones:
            pb.select = False

        armature = Common.set_default_stage()
        # armature.data.pose_position = 'REST'

        for shape_key in Common.get_objects()[context.scene.mesh_name_eye].data.shape_keys.key_blocks:
            shape_key.value = 0

        eye_left = None
        eye_right = None
        eye_left_data = None
        eye_right_data = None
        eye_left_rot = []
        eye_right_rot = []
        return None


@register_wrap
class ResetRotationButton(bpy.types.Operator):
    bl_idname = 'cats_eyes.reset_rotation'
    bl_label = t('ResetRotationButton.label')
    bl_description = t('ResetRotationButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        armature = Common.get_armature()
        if 'LeftEye' in armature.pose.bones:
            if 'RightEye' in armature.pose.bones:
                return True
        return False

    def execute(self, context):
        armature = Common.get_armature()

        context.scene.eye_rotation_x = 0
        context.scene.eye_rotation_y = 0

        global eye_left, eye_right, eye_left_data, eye_right_data
        eye_left = armature.pose.bones.get('LeftEye')
        eye_right = armature.pose.bones.get('RightEye')
        eye_left_data = armature.data.bones.get('LeftEye')
        eye_right_data = armature.data.bones.get('RightEye')

        eye_left.rotation_mode = 'XYZ'
        eye_left.rotation_euler[0] = 0
        eye_left.rotation_euler[1] = 0
        eye_left.rotation_euler[2] = 0

        eye_right.rotation_mode = 'XYZ'
        eye_right.rotation_euler[0] = 0
        eye_right.rotation_euler[1] = 0
        eye_right.rotation_euler[2] = 0

        return {'FINISHED'}


@register_wrap
class AdjustEyesButton(bpy.types.Operator):
    bl_idname = 'cats_eyes.adjust_eyes'
    bl_label = t('AdjustEyesButton.label')
    bl_description = t('AdjustEyesButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        armature = Common.get_armature()
        if 'LeftEye' in armature.pose.bones:
            if 'RightEye' in armature.pose.bones:
                return True
        return False

    def execute(self, context):
        if context.scene.disable_eye_movement:
            return {'FINISHED'}

        mesh_name = context.scene.mesh_name_eye

        if not Common.vertex_group_exists(mesh_name, 'LeftEye'):
            self.report({'ERROR'}, t('AdjustEyesButton.error.noVertex', bone='LeftEye'))
            return {'CANCELLED'}

        # Find the existing vertex group of the right eye bone
        if not Common.vertex_group_exists(mesh_name, 'RightEye'):
            self.report({'ERROR'}, t('AdjustEyesButton.error.noVertex', bone='RightEye'))
            return {'CANCELLED'}

        armature = Common.set_default_stage()
        armature.data.pose_position = 'POSE'

        Common.switch('EDIT')

        new_eye_left = armature.data.edit_bones.get('LeftEye')
        new_eye_right = armature.data.edit_bones.get('RightEye')
        old_eye_left = armature.pose.bones.get(context.scene.eye_left)
        old_eye_right = armature.pose.bones.get(context.scene.eye_right)

        fix_eye_position(context, old_eye_left, new_eye_left, None, False)
        fix_eye_position(context, old_eye_right, new_eye_right, None, True)

        Common.switch('POSE')

        global eye_left, eye_right, eye_left_data, eye_right_data
        eye_left = armature.pose.bones.get('LeftEye')
        eye_right = armature.pose.bones.get('RightEye')
        eye_left_data = armature.data.bones.get('LeftEye')
        eye_right_data = armature.data.bones.get('RightEye')

        return {'FINISHED'}


@register_wrap
class StartIrisHeightButton(bpy.types.Operator):
    bl_idname = 'cats_eyes.adjust_iris_height_start'
    bl_label = t('StartIrisHeightButton.label')
    bl_description = t('StartIrisHeightButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        armature = Common.get_armature()
        if 'LeftEye' in armature.pose.bones:
            if 'RightEye' in armature.pose.bones:
                return True
        return False

    def execute(self, context):
        if context.scene.disable_eye_movement:
            return {'FINISHED'}

        armature = Common.set_default_stage()
        Common.hide(armature)

        mesh = Common.get_objects()[context.scene.mesh_name_eye]
        Common.set_active(mesh)
        Common.switch('EDIT')

        if len(mesh.vertex_groups) > 0:
            Common.set_active(mesh)
            Common.switch('EDIT')
            bpy.ops.mesh.select_mode(type='VERT')

            vgs = [mesh.vertex_groups.get('LeftEye'), mesh.vertex_groups.get('RightEye')]
            for vg in vgs:
                if vg:
                    bpy.ops.object.vertex_group_set_active(group=vg.name)
                    bpy.ops.object.vertex_group_select()

            import bmesh
            [i.index for i in bmesh.from_edit_mesh(bpy.context.active_object.data).verts if i.select]

            bm = bmesh.from_edit_mesh(mesh.data)
            for v in bm.verts:
                if v.select:
                    v.co.y += context.scene.iris_height * 0.01
                    print(v.co)

        return {'FINISHED'}


@register_wrap
class TestBlinking(bpy.types.Operator):
    bl_idname = 'cats_eyes.test_blinking'
    bl_label = t('TestBlinking.label')
    bl_description = t('TestBlinking.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        mesh = Common.get_objects()[context.scene.mesh_name_eye]
        if Common.has_shapekeys(mesh):
            if 'vrc.blink_left' in mesh.data.shape_keys.key_blocks:
                if 'vrc.blink_right' in mesh.data.shape_keys.key_blocks:
                    return True
        return False

    def execute(self, context):
        mesh = Common.get_objects()[context.scene.mesh_name_eye]
        shapes = ['vrc.blink_left', 'vrc.blink_right']

        for shape_key in mesh.data.shape_keys.key_blocks:
            if shape_key.name in shapes:
                mesh.data.shape_keys.key_blocks[shape_key.name].value = context.scene.eye_blink_shape
            else:
                mesh.data.shape_keys.key_blocks[shape_key.name].value = 0

        return {'FINISHED'}


@register_wrap
class TestLowerlid(bpy.types.Operator):
    bl_idname = 'cats_eyes.test_lowerlid'
    bl_label = t('TestLowerlid.label')
    bl_description = t('TestLowerlid.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        mesh = Common.get_objects()[context.scene.mesh_name_eye]
        if Common.has_shapekeys(mesh):
            if 'vrc.lowerlid_left' in mesh.data.shape_keys.key_blocks:
                if 'vrc.lowerlid_right' in mesh.data.shape_keys.key_blocks:
                    return True
        return False

    def execute(self, context):
        mesh = Common.get_objects()[context.scene.mesh_name_eye]
        shapes = OrderedDict()
        shapes['vrc.lowerlid_left'] = context.scene.eye_lowerlid_shape
        shapes['vrc.lowerlid_right'] = context.scene.eye_lowerlid_shape

        for shape_key in mesh.data.shape_keys.key_blocks:
            if shape_key.name in shapes:
                mesh.data.shape_keys.key_blocks[shape_key.name].value = context.scene.eye_lowerlid_shape
            else:
                mesh.data.shape_keys.key_blocks[shape_key.name].value = 0

        return {'FINISHED'}


@register_wrap
class ResetBlinkTest(bpy.types.Operator):
    bl_idname = 'cats_eyes.reset_blink_test'
    bl_label = t('ResetBlinkTest.label')
    bl_description = t('ResetBlinkTest.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        for shape_key in Common.get_objects()[context.scene.mesh_name_eye].data.shape_keys.key_blocks:
            shape_key.value = 0
        context.scene.eye_blink_shape = 1
        context.scene.eye_lowerlid_shape = 1

        return {'FINISHED'}

@register_wrap
class ResetEyeTrackingButton(bpy.types.Operator):
    bl_idname = 'cats_eyes.reset_eye_tracking'
    bl_label = t('ResetEyeTrackingButton.label')
    bl_description = t('ResetEyeTrackingButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        global eye_left, eye_right, eye_left_data, eye_right_data, eye_left_rot, eye_right_rot
        eye_left = eye_right = eye_left_data = eye_right_data = None
        eye_left_rot = eye_right_rot = []
        context.scene.eye_mode = 'CREATION'
        return {'FINISHED'}
