# MIT License

import bpy
import copy
import math
import platform
from mathutils import Matrix
from collections import defaultdict

from . import common as Common
from . import material as Material
from . import translate as Translate
from . import armature_bones as Bones
from .common import version_3_6_or_older
from .register import register_wrap
from .translations import t

# Only load mmd_tools_local if it's not on linux and 2.90 or higher since it causes Blender to crash
mmd_tools_local_installed = False
if platform.system() != "Linux":
    try:
        from mmd_tools_local.operators import morph as Morph
        mmd_tools_local_installed = True
    except ImportError:
        pass


class ValidationError(Exception):
    """Custom exception for validation errors"""
    def __init__(self, message, error_code=None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class ArmatureValidator:
    """Comprehensive input validation for armature fixing"""
    
    @staticmethod
    def validate_armature_requirements(context, armature):
        """Validate all requirements before processing begins"""
        errors = []
        warnings = []
        
        # Basic armature validation
        if not armature:
            errors.append("No armature found in the scene")
            return errors, warnings
            
        if not armature.data:
            errors.append("Armature has no data")
            return errors, warnings
        
        if any(armature.lock_location) or any(armature.lock_rotation) or any(armature.lock_scale):
            warnings.append("Armature has locked transforms - these will be unlocked")
        
        # Check bone count
        bone_count = len(armature.data.bones)
        if bone_count == 0:
            errors.append("Armature has no bones")
        elif bone_count > 1000:
            warnings.append(f"Armature has {bone_count} bones - processing may be slow")
        
        # Check for Rigify/Metarig (from original logic)
        if ArmatureValidator._is_rigify_armature(armature):
            errors.append("Rigify and Metarig armatures are not supported. Please use Rigify to Unity plugin instead.")
        
        # Validate meshes
        mesh_errors, mesh_warnings = ArmatureValidator._validate_meshes(context, armature)
        errors.extend(mesh_errors)
        warnings.extend(mesh_warnings)
        
        # Check for required bones for basic functionality
        required_bone_groups = [
            ['Hips', 'Spine'],
            ['Head', 'Neck'],
        ]
        
        for bone_group in required_bone_groups:
            if not any(bone.name in bone_group for bone in armature.data.bones):
                warnings.append(f"No bones found from group: {', '.join(bone_group)}")
        
        return errors, warnings
    
    @staticmethod
    def _is_rigify_armature(armature):
        """Check if armature is Rigify/Metarig"""
        if armature.name.lower() == 'metarig':
            return True
            
        rigify_bones = {'brow.B.L', 'lip.B.R', 'lip.T.R', 'lip.B.L', 'lip.T.L'}
        
        for bone in armature.data.bones:
            if bone.name.startswith(('DEF-', 'MCH-', 'ORG-')) or bone.name in rigify_bones:
                return True
                
        return False
    
    @staticmethod
    def _validate_meshes(context, armature):
        """Validate mesh requirements"""
        errors = []
        warnings = []
        
        meshes = Common.get_meshes_objects()
        
        if not meshes:
            # Check for VRM models with .baked meshes
            is_vrm = False
            for mesh in Common.get_meshes_objects(mode=2):
                if mesh.name.endswith(('.baked', '.baked0')):
                    is_vrm = True
                    break
            
            if not is_vrm:
                errors.append("No meshes found in the scene")
        
        # Single user data check removed - handled by original code to preserve popup behavior
        
        # Check for valid vertex groups
        for mesh in meshes:
            if not mesh.vertex_groups:
                warnings.append(f"Mesh '{mesh.name}' has no vertex groups")
            
            # Check for NaN values in UV coordinates
            uv_issues = 0
            for uv_layer in mesh.data.uv_layers:
                for vert_idx in range(len(uv_layer.data)):
                    if math.isnan(uv_layer.data[vert_idx].uv.x) or math.isnan(uv_layer.data[vert_idx].uv.y):
                        uv_issues += 1
            
            if uv_issues > 0:
                warnings.append(f"Mesh '{mesh.name}' has {uv_issues} faulty UV coordinates that will be fixed")
        
        return errors, warnings


class BoneCache:
    """Lightweight cache system for bone lookups"""
    
    def __init__(self, armature):
        self.armature = armature
        self.bone_name_map = {}  # lowercase name -> actual bone
        self._build_name_cache()
    
    def _build_name_cache(self):
        """Build lightweight name mapping cache only"""
        # Only cache bone names for case-insensitive lookups
        for bone in self.armature.data.bones:
            self.bone_name_map[bone.name.lower()] = bone.name
    
    def find_bone_by_name(self, name):
        """Find bone by name with caching"""
        return self.bone_name_map.get(name.lower())
    
    def clear_cache(self):
        """Clear all cached data to prevent memory leaks"""
        self.bone_name_map.clear()
        self.armature = None


def convert_bone_morphs_native(context, armature, mmd_root):
    """Native bone morph to shape key conversion for Linux compatibility"""
    if not hasattr(mmd_root, 'bone_morphs') or len(mmd_root.bone_morphs) == 0:
        return
    
    from mathutils import Vector, Quaternion
    
    mesh_objects = Common.get_meshes_objects()
    if not mesh_objects:
        return
    
    mesh = mesh_objects[0]
    Common.set_active(mesh)
    
    # Ensure we have shape keys
    if not mesh.data.shape_keys:
        mesh.shape_key_add(name="Basis")
    
    # Collect morph names for translation (same as bones do) - USE JAPANESE NAMES
    to_translate = []
    for morph in mmd_root.bone_morphs:
        to_translate.append(morph.name)  # Always use Japanese name for translation
    
    # Update translation dictionary (same as bones do)
    Translate.update_dictionary(to_translate, translating_shapes=True)
    
    wm = context.window_manager
    current_step = 0
    wm.progress_begin(current_step, len(mmd_root.bone_morphs))
    
    # Store original bone transforms
    original_transforms = {}
    for bone in armature.pose.bones:
        original_transforms[bone.name] = {
            'location': bone.location.copy(),
            'rotation_quaternion': bone.rotation_quaternion.copy(),
            'rotation_euler': bone.rotation_euler.copy(),
        }
    
    # Process each bone morph
    for morph in mmd_root.bone_morphs:
        current_step += 1
        wm.progress_update(current_step)
        
        if not morph.data:
            continue
            
        # Apply bone transformations
        for morph_data in morph.data:
            if morph_data.bone in armature.pose.bones:
                bone = armature.pose.bones[morph_data.bone]
                
                bone.location = original_transforms[bone.name]['location'] + Vector(morph_data.location)
                offset_quat = Quaternion(morph_data.rotation)
                bone.rotation_quaternion = original_transforms[bone.name]['rotation_quaternion'] @ offset_quat
        
        # Update scene to apply transformations
        context.view_layer.update()
        
        # Create shape key with translated name - ALWAYS translate Japanese name
        original_name = morph.name  # Use Japanese name
        shape_key_name, translated = Translate.translate(original_name, add_space=True, translating_shapes=True)
        shape_key = mesh.shape_key_add(name=shape_key_name)
        
        # Reset bone transforms for next morph
        for bone_name, transforms in original_transforms.items():
            if bone_name in armature.pose.bones:
                bone = armature.pose.bones[bone_name]
                bone.location = transforms['location']
                bone.rotation_quaternion = transforms['rotation_quaternion']
                bone.rotation_euler = transforms['rotation_euler']
    
    wm.progress_end()
    context.view_layer.update()


@register_wrap
class FixArmature(bpy.types.Operator):
    bl_idname = 'cats_armature.fix'
    bl_label = t('FixArmature.label')
    bl_description = t('FixArmature.desc')

    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        if not Common.get_armature():
            return False

        if len(Common.get_armature_objects()) == 0:
            return False

        return True

    def execute(self, context):
        saved_data = Common.SavedData()
        armature = Common.get_armature()
        
        # ========== COMPREHENSIVE INPUT VALIDATION ==========
        try:
            errors, warnings = ArmatureValidator.validate_armature_requirements(context, armature)
            
            # Display warnings to user
            for warning in warnings:
                self.report({'WARNING'}, warning)
            
            # Stop execution if there are critical errors
            if errors:
                for error in errors:
                    self.report({'ERROR'}, error)
                return {'CANCELLED'}
                
        except Exception as e:
            self.report({'ERROR'}, f"Validation failed: {str(e)}")
            return {'CANCELLED'}
        
        # Initialize lightweight bone cache for performance optimization
        bone_cache = BoneCache(armature)
        
        # Store and remove bone collections to prevent crashes
        bone_collections_backup = []
        # Check if this is an MMD model
        mmd_root = None
        try:
            mmd_root = armature.parent.mmd_root
        except AttributeError:
            pass
                
        if mmd_root:
            # This is an MMD model, back up and remove bone collections
            # First, collect all bone collection data in EDIT mode
            Common.set_active(armature)
            Common.switch('EDIT')
            
            for collection in armature.data.collections:
                # Store collection data
                collection_data = {
                    'name': collection.name,
                    'is_visible': collection.is_visible,
                    'bones': []
                }
                
                # Store bones while in edit mode
                for bone in collection.bones:
                    collection_data['bones'].append(bone.name)
                
                bone_collections_backup.append(collection_data)
            
            # Switch to OBJECT mode before removing collections to avoid crashes
            Common.switch('OBJECT')
            
            # Now safely remove collections in OBJECT mode
            for collection in list(armature.data.collections):
                armature.data.collections.remove(collection)
        
        # Check for Rigify/Metarig
        is_rigify = False
        rigify_bones = {'brow.B.L', 'lip.B.R', 'lip.T.R', 'lip.B.L', 'lip.T.L'}
        
        if armature.name.lower() == 'metarig':
            is_rigify = True
        
        if not is_rigify:
            for bone in armature.data.bones:
                if bone.name.startswith(('DEF-', 'MCH-', 'ORG-')) or bone.name in rigify_bones:
                    is_rigify = True
                    break
                
        if is_rigify:
            Common.show_error(3, ["Rigify and Metarig armatures are not", 
                                "supported. Please use Rigify to Unity", 
                                "plugin instead.",
                                "If you think this is a error, then make sure your",
                                "bones and amrature do not have metarig", 
                                "names or Rigify names."])
            return {'CANCELLED'}

        # Check if all meshes are single user
        meshes_to_check = Common.get_meshes_objects()
        for mesh in meshes_to_check:
            if mesh.data.users > 1:
                Common.show_error(4, [t('JoinMeshes.error.not_single_user'),
                                    t('JoinMeshes.error.make_single_user'),
                                    t('JoinMeshes.error.make_single_user1'),
                                    t('JoinMeshes.error.make_single_user2')])
                return {'CANCELLED'}

        is_vrm = False
        if len(Common.get_meshes_objects()) == 0:
            for mesh in Common.get_meshes_objects(mode=2):
                if mesh.name.endswith(('.baked', '.baked0')):
                    is_vrm = True  # TODO
            if not is_vrm:
                Common.show_error(3.8, t('FixArmature.error.noMesh'))
                return {'CANCELLED'}

        print('\nFixing Model:\n')

        wm = bpy.context.window_manager
        armature = Common.set_default_stage()

        # Add rename bones to reweight bones
        temp_rename_bones = copy.deepcopy(Bones.bone_rename)
        temp_reweight_bones = copy.deepcopy(Bones.bone_reweight)
        temp_list_reweight_bones = copy.deepcopy(Bones.bone_list_weight)
        temp_list_reparent_bones = copy.deepcopy(Bones.bone_list_parenting)

        for key, value in Bones.bone_rename_fingers.items():
            temp_rename_bones[key] = value

        for key, value in temp_rename_bones.items():
            if key == 'Spine':
                continue
            bone_list = temp_reweight_bones.get(key) 
            if not bone_list:
                temp_reweight_bones[key] = value
            else:
                for name in value:
                    if name not in bone_list:
                        temp_reweight_bones.get(key).append(name)

        # Count objects for loading bar
        steps = 0
        for key, value in temp_rename_bones.items():
            if "\\L" in key:
                steps += 2 * len(value)
            else:
                steps += len(value)
        for key, value in temp_reweight_bones.items():
            if "\\L" in key:
                steps += 2 * len(value)
            else:
                steps += len(value)
        steps += len(temp_list_reweight_bones)  # + len(Bones.bone_list_parenting)

        # Get Double Entries
        print('DOUBLE ENTRIES:')
        print('RENAME:')
        name_list = []  
        for key, value in temp_rename_bones.items():
            for name in value:
                if name.lower() not in name_list:
                    name_list.append(name.lower())
                else:
                    print(key + " | " + name)
        print('REWEIGHT:')
        name_list = [] 
        for key, value in temp_reweight_bones.items():
            for name in value:
                if name.lower() not in name_list:
                    name_list.append(name.lower())
                else:
                    print(key + " | " + name)
        print('DOUBLES END')

        # Check if model is mmd model
        mmd_root = None
        try:
            mmd_root = armature.parent.mmd_root
        except AttributeError:
            pass

        # Perform mmd specific operations
        if mmd_root:
            # Set correct mmd shading (only if mmd_tools_local available)
            if mmd_tools_local_installed:
                mmd_root.use_toon_texture = False
                mmd_root.use_sphere_texture = False

            # Convert mmd bone morphs into shape keys
            if hasattr(mmd_root, 'bone_morphs') and len(mmd_root.bone_morphs) > 0:
                
                if mmd_tools_local_installed:
                    # Collect morph names for translation (same as bones do) - USE JAPANESE NAMES
                    to_translate = []
                    for morph in mmd_root.bone_morphs:
                        to_translate.append(morph.name)  # Always use Japanese name for translation
                    
                    # Update translation dictionary (same as bones do)
                    Translate.update_dictionary(to_translate, translating_shapes=True)
                    
                    # Use mmd_tools_local for non-Linux platforms
                    current_step = 0
                    wm.progress_begin(current_step, len(mmd_root.bone_morphs))

                    armature.data.pose_position = 'POSE'
                    for index, morph in enumerate(mmd_root.bone_morphs):
                        current_step += 1
                        wm.progress_update(current_step)

                        armature.parent.mmd_root.active_morph = index
                        Morph.ViewBoneMorph.execute(None, context)

                        mesh = Common.get_meshes_objects()[0]
                        Common.set_active(mesh)

                        # Use same translation system as bones - ALWAYS translate Japanese name
                        original_name = morph.name  # Use Japanese name
                        modifier_name, _ = Translate.translate(original_name, add_space=True, translating_shapes=True)
                        mod = mesh.modifiers.new(modifier_name, 'ARMATURE')
                        mod.object = armature
                        Common.apply_modifier(mod, as_shapekey=True)
                    wm.progress_end()
                else:
                    # Use native conversion for Linux
                    armature.data.pose_position = 'POSE'
                    convert_bone_morphs_native(context, armature, mmd_root)

        # Perform source engine specific operations
        # Check if model is source engine model
        source_engine = False
        for bone in armature.pose.bones:
            if bone.name.startswith('ValveBiped'):
                source_engine = True
                break

        #Perform "Blenda" specific operation. This is needed because Spine1 on this model represents the hips and that conflicts with other mappings.
        for bone in armature.pose.bones:
            if bone.name.startswith("cShrugger"):
                for bone in armature.pose.bones:
                    if bone.name == "Spine1":
                        bone.name = "Hips"
                        break
                break

        # Remove unused animation data
        if armature.animation_data and armature.animation_data.action and armature.animation_data.action.name == 'ragdoll':
            armature.animation_data_clear()
            source_engine = True

        # Delete unused VTA mesh
        for mesh in Common.get_meshes_objects(mode=1):
            if mesh.name == 'VTA vertices':
                Common.delete_hierarchy(mesh)
                source_engine = True
                break

        if source_engine:
            # Delete unused physics meshes (like rigidbodies)
            for mesh in Common.get_meshes_objects():
                if len(Common.get_meshes_objects()) == 1:
                    break
                if mesh.name.endswith(('_physics', '_lod1', '_lod2', '_lod3', '_lod4', '_lod5', '_lod6')):
                    Common.delete_hierarchy(mesh)

        # Reset to default
        armature = Common.set_default_stage()

        # Find 3D view
        view_area = None
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                view_area = area.spaces[0]
                break

        if view_area:
            view_area.clip_start = 0.01
            view_area.clip_end = 300
            armature.data.display_type = 'OCTAHEDRAL'
            if hasattr(armature, 'draw_type'):
                armature.draw_type = 'WIRE'
            armature.show_in_front = True
            armature.data.show_bone_custom_shapes = False
            # context.space_data.overlay.show_transparent_bones = True
            if view_area:
                view_area.shading.show_backface_culling = True

            # Set the Color Management View Transform to "Standard" instead of the Blender default "Filmic"
            try:
                context.scene.view_settings.view_transform = 'Standard'
            except TypeError:
                print('Color Management View Transform "Standard" not found!')

        # Remove Rigidbodies and joints
        if context.scene.remove_rigidbodies_joints:
            to_delete = []
            for child in Common.get_top_parent(armature).children:
                if 'rigidbodies' in child.name or 'joints' in child.name and child.name not in to_delete:
                    to_delete.append(child.name)
                    continue
                for child2 in child.children:
                    if 'rigidbodies' in child2.name or 'joints' in child2.name and child2.name not in to_delete:
                        to_delete.append(child2.name)
                        continue
            for obj_name in to_delete:
                Common.set_active(armature)
                Common.switch('EDIT')
                Common.switch('OBJECT')
                Common.delete_hierarchy(bpy.data.objects[obj_name])

        if len(armature.children) > 1:
            for child in armature.children:
                for child2 in child.children:
                    if child2.type != 'MESH':
                        Common.delete(child2)

                if child.type != 'MESH':
                    Common.delete(child)

        # Unlock all transforms
        for i in range(0, 3):
            armature.lock_location[i] = False
            armature.lock_rotation[i] = False
            armature.lock_scale[i] = False

        # Unlock all bone transforms
        for bone in armature.pose.bones:
            bone.lock_location[0] = False
            bone.lock_location[1] = False
            bone.lock_location[2] = False
            bone.lock_rotation[0] = False
            bone.lock_rotation[1] = False
            bone.lock_rotation[2] = False
            bone.lock_scale[0] = False
            bone.lock_scale[1] = False
            bone.lock_scale[2] = False

        # Remove empty mmd object and unused objects
        Common.set_active(armature)
        Common.switch('EDIT')
        Common.switch('OBJECT')
        Common.remove_empty()
        Common.remove_unused_objects()

        # Fix VRM meshes being outside of the armature
        if is_vrm:
            for mesh in Common.get_meshes_objects(mode=2):
                if mesh.name.endswith(('.baked', '.baked0')):
                    mesh.parent = armature
        collections_armature_is_in = armature.users_collection
        if collections_armature_is_in:
            armature_collection = collections_armature_is_in[0]
            for col in collections_armature_is_in[1:]:
                col.objects.unlink(armature)
        else:
            armature_collection = context.scene.collection
            armature_collection.objects.link(armature)

        for mesh in Common.get_meshes_objects():
            mesh_already_in_armature_collection = False
            for col in mesh.users_collection:
                if col == armature_collection:
                    mesh_already_in_armature_collection = True
                else:
                    col.objects.unlink(mesh)
            if not mesh_already_in_armature_collection:
                armature_collection.objects.link(mesh)

        # Check if weird FBX model
        print('CHECK TRANSFORMS:', armature.scale[0], armature.scale[1], armature.scale[2])
        if round(armature.scale[0], 2) == 0.01 \
                and round(armature.scale[1], 2) == 0.01 \
                and round(armature.scale[2], 2) == 0.01:

            # Delete keyframes
            Common.set_active(armature)
            armature.animation_data_clear()
            for mesh in Common.get_meshes_objects():
                mesh.animation_data_clear()

        # Fixes bones disappearing, prevents bones from having their tail and head at the exact same position
        Common.fix_zero_length_bones(armature)

        # Apply transforms of this model
        Common.apply_transforms()

        # Puts all meshes into a list and joins them if selected
        if context.scene.join_meshes:
            meshes = [Common.join_meshes()]
        else:
            meshes = Common.get_meshes_objects()

        for mesh in meshes:
            Common.unselect_all()
            Common.set_active(mesh)

            # Unlock all mesh transforms
            for i in range(0, 3):
                mesh.lock_location[i] = False
                mesh.lock_rotation[i] = False
                mesh.lock_scale[i] = False

            # Set layer of mesh to 0
            if hasattr(mesh, 'layers'):
                mesh.layers[0] = True

            # Fix Source Shapekeys
            if source_engine and Common.has_shapekeys(mesh):
                mesh.data.shape_keys.key_blocks[0].name = "Basis"

            # Fix VRM shapekeys
            if is_vrm and Common.has_shapekeys(mesh):
                shapekeys = mesh.data.shape_keys.key_blocks
                for shapekey in shapekeys:
                    shapekey.name = shapekey.name.replace('_', ' ').replace('Face.M F00 000 Fcl ', '').replace('Face.M F00 000 00 Fcl ', '')

                # Sort shapekeys in categories
                shapekey_order = []
                for categorie in ['MTH', 'EYE', 'BRW', 'ALL', 'HA']:
                    for shapekey in shapekeys:
                        if shapekey.name.startswith(categorie):
                            shapekey_order.append(shapekey.name)

                Common.sort_shape_keys(mesh.name, shapekey_order)        

            # Remove empty shape keys and then save the shape key order
            Common.clean_shapekeys(mesh)
            Common.save_shapekey_order(mesh.name)

            # Reorders vrc shape keys to the correct order
            Common.sort_shape_keys(mesh.name)

            # Fix all shape key names of half jp chars
            if Common.has_shapekeys(mesh):
                for shapekey in mesh.data.shape_keys.key_blocks:
                    shapekey.name = Translate.fix_jp_chars(shapekey.name)

            # Fix faulty UV coordinates
            fixed_uv_coords = 0
            for uv in mesh.data.uv_layers:
                for vert in range(len(uv.data) - 1):
                    if math.isnan(uv.data[vert].uv.x):
                        uv.data[vert].uv.x = 0
                        fixed_uv_coords += 1
                    if math.isnan(uv.data[vert].uv.y):
                        uv.data[vert].uv.y = 0
                        fixed_uv_coords += 1

        # Translate bones and unhide them all
        to_translate = []
        for bone in armature.data.bones:
            to_translate.append(bone.name)
        # Unhide all pose bones for visibility in object/pose mode
        for pb in armature.pose.bones:
            pb.hide = False
        Translate.update_dictionary(to_translate)
        for bone in armature.data.bones:
            bone.name, translated = Translate.translate(bone.name)

        # Armature should be selected
        Common.set_default_stage()
        Common.unselect_all()
        Common.set_active(armature)

        # Reset pose position
        Common.switch('POSE')
        bpy.ops.pose.rot_clear()
        bpy.ops.pose.scale_clear()
        bpy.ops.pose.transforms_clear()

        # Enter edit mode
        Common.switch('EDIT')

        # Show all hidden bones (the comment was misleading - this should be for bones, not mesh verts)
        # In armature edit mode, ensure all bones are visible
        for bone in armature.data.edit_bones:
            bone.hide = False

        # Switch to OBJECT mode before removing bone collections to avoid crashes
        Common.switch('OBJECT')

        # Remove Bone Groups
        # Replaced in 4.0 with Bone Collections (Armature.collections), which also subsumed Armature.layers. Bone colors
        # are now defined per-bone, Bone.color.palette and PoseBone.color.palette
        if Common.version_3_6_or_older():
            for group in armature.pose.bone_groups:
                armature.pose.bone_groups.remove(group)
        else:
            for collection in list(armature.data.collections):
                armature.data.collections.remove(collection)

        # Re-enter EDIT mode for subsequent operations
        Common.switch('EDIT')

        # Bone constraints should be deleted
        # if context.scene.remove_constraints:
        Common.delete_bone_constraints()

        # Model should be in rest position
        # armature.data.pose_position = 'REST'

        # Count steps for loading bar again and reset the layers
        steps += len(armature.data.edit_bones)
        
        # Handle bone visibility based on Blender version
        if Common.version_3_6_or_older():
            # For Blender 3.6 or older, use bone layers
            for bone in armature.data.edit_bones:
                bone.layers[0] = True
        else:
            # For Blender 4.0+, use bone collections
            bone_collections = armature.data.collections
            if bone_collections:
                # The default collection on new Armatures is called "Bones" and usually has all bones assigned to it.
                default_collection_name = "Bones"
                bone_collection = bone_collections.get(default_collection_name)
                if bone_collection is None:
                    # The default "Bones" collection does not exist, create it.
                    bone_collection = bone_collections.new(default_collection_name)
                # Ensure the collection is visible.
                bone_collection.is_visible = True
                
                # Assign all bones to the default collection
                for bone in armature.data.edit_bones:
                    bone_collection.assign(bone)
        
        for bone in armature.data.edit_bones:
            if bone.name in Bones.bone_list or bone.name.startswith(tuple(Bones.bone_list_with)):
                if bone.parent is not None:
                    steps += 1
                else:
                    steps -= 1

        # Start loading bar
        current_step = 0
        wm.progress_begin(current_step, steps)

        # List of chars to replace if they are at the start of a bone name
        starts_with = [
            ('_', ''),
            ('ValveBiped_', ''),
            ('Valvebiped_', ''),
            ('Bip1_', 'Bip_'),
            ('Bip01_', 'Bip_'),
            ('Bip001_', 'Bip_'),
            ('Bip01', ''),
            ('Bip02_', 'Bip_'),
            ('Character1_', ''),
            ('HLP_', ''),
            ('JD_', ''),
            ('JU_', ''),
            ('Armature|', ''),
            ('Bone_', ''),
            ('C_', ''),
            ('Cf_S_', ''),
            ('Cf_J_', ''),
            ('G_', ''),
            ('Joint_', ''),
            ('Def_C_', ''),
            ('Def_', ''),
            ('DEF_', ''),
            ('Chr_', ''),
            ('Chr_', ''),
            ('B_', ''),
        ]
        # List of chars to replace if they are at the end of a bone name
        ends_with = [
            ('_Bone', ''),
            ('_Bn', ''),
            ('_Le', '_L'),
            ('_Ri', '_R'),
            ('_', ''),
        ]
        # List of chars to replace
        replaces = [
            (' ', '_'),
            ('-', '_'),
            ('.', '_'),
            (':', '_'),
            ('____', '_'),
            ('___', '_'),
            ('__', '_'),
            ('_Le_', '_L_'),
            ('_Ri_', '_R_'),
            ('LEFT', 'Left'),
            ('RIGHT', 'Right'),
        ]

        # Standardize names
        for bone in armature.data.edit_bones:
            current_step += 1
            wm.progress_update(current_step)

            name = bone.name

            # Always uppercase at the start and after an underscore
            upper_name = ''
            for i, s in enumerate(name.split('_')):
                if i != 0:
                    upper_name += '_'
                upper_name += s[:1].upper() + s[1:]
            name = upper_name

            # Replace all the things!
            for replacement in replaces:
                name = name.replace(replacement[0], replacement[1])

            # Replace if name starts with specified chars
            for replacement in starts_with:
                if name.startswith(replacement[0]):
                    name = replacement[1] + name[len(replacement[0]):]

            # Replace if name ends with specified chars
            for replacement in ends_with:
                if name.endswith(replacement[0]):
                    name = name[:-len(replacement[0])] + replacement[1]

            # Remove digits from the start
            name_split = name.split('_')
            if len(name_split) > 1 and name_split[0].isdigit():
                name = name_split[1]

            # Specific condition
            name_split = name.split('"')
            if len(name_split) > 3:
                name = name_split[1]

            # Another specific condition
            if ':' in name:
                for i, split in enumerate(name.split(':')):
                    if i == 0:
                        name = ''
                    else:
                        name += split

            # Remove S0 from the end
            if name[-2:] == 'S0':
                name = name[:-2]

            if name[-4:] == '_Jnt':
                name = name[:-4]

            bone.name = name

        # Add conflicting bone names to new list
        conflicting_bones = []
        for names in Bones.bone_list_conflicting_names:
            if '\Left' not in names[1] and '\L' not in names[1]:
                conflicting_bones.append(names)
                continue

            names0 = []
            name1 = ''
            name2 = ''
            for name0 in names[0]:
                names0.append(name0.replace('\Left', 'Left').replace('\left', 'left').replace('\L', 'L').replace('\l', 'l'))
            if '\Left' in names[1] or '\L' in names[1]:
                name1 = names[1].replace('\Left', 'Left').replace('\left', 'left').replace('\L', 'L').replace('\l', 'l')
            if '\Left' in names[2] or '\L' in names[2]:
                name2 = names[2].replace('\Left', 'Left').replace('\left', 'left').replace('\L', 'L').replace('\l', 'l')
            conflicting_bones.append((names0, name1, name2))

            for name0 in names[0]:
                names0.append(name0.replace('\Left', 'Right').replace('\left', 'right').replace('\L', 'R').replace('\l', 'r'))
            if '\Left' in names[1] or '\L' in names[1]:
                name1 = names[1].replace('\Left', 'Right').replace('\left', 'right').replace('\L', 'R').replace('\l', 'r')
            if '\Left' in names[2] or '\L' in names[2]:
                name2 = names[2].replace('\Left', 'Right').replace('\left', 'right').replace('\L', 'R').replace('\l', 'r')
            conflicting_bones.append((names0, name1, name2))

        # Resolve conflicting bone names
        for names in conflicting_bones:

            # Search for bone in armature
            bone = None
            for bone_tmp in armature.data.edit_bones:
                if bone_tmp.name.lower() == names[1].lower():
                    bone = bone_tmp
                    break

            # Cancel if bone was not found
            if not bone:
                continue

            # Search for all the required bones
            found_all = True
            for name in names[0]:
                found = False
                for bone_tmp in armature.data.edit_bones:
                    if bone_tmp.name.lower() == name.lower():
                        found = True
                        break
                if not found:
                    found_all = False
                    break

            # Rename only if all required bones are found
            if found_all:
                bone.name = names[2]

        # Standardize bone names again (new duplicate bones have ".001" in it)
        for bone in armature.data.edit_bones:
            bone.name = bone.name.replace('.', '_')

        # Rename all the bones
        spines = []
        spine_parts = []
        for bone_new, bones_old in temp_rename_bones.items():
            if "\\L" in bone_new:
                bones = [[bone_new.replace("\\Left", "Left").replace("\\L", "L"), ""],
                        [bone_new.replace("\\Left", "Right").replace("\\L", "R"), ""]]
            else:
                bones = [[bone_new, ""]]
            for bone_old in bones_old:
                if "\\L" in bone_new:
                    bones[0][1] = bone_old.replace("\\Left", "Left").replace("\\L", "L")
                    bones[1][1] = bone_old.replace("\\Left", "Right").replace("\\L", "R")
                else:
                    bones[0][1] = bone_old

                for bone in bones:  # bone[0] = new name, bone[1] = old name
                    current_step += 1
                    wm.progress_update(current_step)

                    # Seach for bone in armature
                    bone_final = None
                    for bone_tmp in armature.data.edit_bones:
                        if bone_tmp.name.lower() == bone[1].lower():
                            bone_final = bone_tmp
                            break

                    # Cancel if bone was not found
                    if not bone_final:
                        continue

                    # If spine bone, then don't rename for now, and ignore spines with no children
                    if bone_new == 'Spine':
                        if len(bone_final.children) > 0:
                            spines.append(bone_final.name)
                        else:
                            spine_parts.append(bone_final.name)
                        continue

                    # Rename the bone
                    if bone[0] not in armature.data.edit_bones:
                        # print(bone_final.name, '>', bone[0])
                        bone_final.name = bone[0]

        # Check if it is a mixamo model
        mixamo = False
        for bone in armature.data.edit_bones:
            if not mixamo and 'Mixamo' in bone.name:
                mixamo = True
                break

        # Rename bones which don't have a side and try to detect it automatically
        for key, value in Bones.bone_list_rename_unknown_side.items():
            for bone in armature.data.edit_bones:
                parent = bone.parent
                if parent is None:
                    continue
                if parent.name == key or parent.name == key.lower():
                    if 'right' in bone.name.lower():
                        parent.name = 'Right ' + value
                        break
                    elif 'left' in bone.name.lower():
                        parent.name = 'Left ' + value
                        break

                parent = parent.parent
                if parent is None:
                    continue
                if parent.name == key or parent.name == key.lower():
                    if 'right' in bone.name.lower():
                        parent.name = 'Right ' + value
                        break
                    elif 'left' in bone.name.lower():
                        parent.name = 'Left ' + value
                        break

        # Remove un-needed bones, disconnect them and set roll to 0
        for bone in armature.data.edit_bones:
            if bone.name in Bones.bone_list or bone.name.startswith(tuple(Bones.bone_list_with)):
                if bone.parent:
                    temp_list_reweight_bones[bone.name] = bone.parent.name
                else:
                    armature.data.edit_bones.remove(bone)
            else:
                bone.use_connect = False
                bone.roll = 0

        # Make Hips top parent and reparent other top bones to hips
        if 'Hips' in armature.data.edit_bones:
            hips = armature.data.edit_bones.get('Hips')
            hips.parent = None
            for bone in armature.data.edit_bones:
                if bone.parent is None:
                    bone.parent = hips

        # == FIXING OF SPECIAL BONE CASES ==

        # Fix all spines!
        spine_count = len(spines)

        # Fix spines from armatures with no upper body (like skirts)
        if len(spine_parts) == 1 and not armature.data.edit_bones.get('Neck'):
            if spine_count == 0:
                armature.data.edit_bones.get(spine_parts[0]).name = 'Spine'
            else:
                spines.append(spine_parts[0])

        if spine_count == 0:
            pass

        elif spine_count == 1:  # Create missing Chest
            print('BONE CREATION')
            spine = armature.data.edit_bones.get(spines[0])
            chest = armature.data.edit_bones.new('Chest')
            neck = armature.data.edit_bones.get('Neck')

            # Check for neck
            if neck:
                chest_top = neck.head
            else:
                chest_top = spine.tail

            # Correct the names
            spine.name = 'Spine'
            chest.name = 'Chest'

            # Set new Chest bone to new position
            chest.tail = chest_top
            chest.head = spine.head
            chest.head.z = spine.head.z + (chest_top.z - spine.head.z) / 2
            chest.head.y = spine.head.y + (chest_top.y - spine.head.y) / 2

            # Adjust spine bone position
            spine.tail = chest.head

            # Reparent bones to include new chest
            chest.parent = spine

            for bone in armature.data.edit_bones:
                if bone.parent == spine:
                    bone.parent = chest

        elif spine_count == 2:  # Everything correct, just rename them
            print('NORMAL')
            armature.data.edit_bones.get(spines[0]).name = 'Spine'
            armature.data.edit_bones.get(spines[1]).name = 'Chest'

        elif spine_count == 3:  # Everything correct, just rename them
            print('NORMAL')
            armature.data.edit_bones.get(spines[0]).name = 'Spine'
            armature.data.edit_bones.get(spines[1]).name = 'Chest'
            armature.data.edit_bones.get(spines[2]).name = 'Upper Chest'

        elif spine_count == 4 and source_engine:  # SOURCE ENGINE SPECIFIC
            print('SOURCE ENGINE')
            spine = armature.data.edit_bones.get(spines[0])
            chest = armature.data.edit_bones.get(spines[2])

            chest.name = 'Chest'
            spine.name = 'Spine'

            spine.tail = chest.head

            temp_list_reweight_bones[spines[1]] = 'Spine'
            temp_list_reweight_bones[spines[3]] = 'Chest'

        elif spine_count > 2:  # Merge spines
            print('MASS MERGING')
            print(spines)
            spine = armature.data.edit_bones.get(spines[0])
            chest = armature.data.edit_bones.get(spines[spine_count - 1])

            # Correct names
            spine.name = 'Spine'
            chest.name = 'Chest'

            # Adjust spine bone position
            spine.tail = chest.head

            # Add all redundant spines to the merge list
            for spine in spines[1:spine_count-1]:
                print(spine)
                temp_list_reweight_bones[spine] = 'Spine'

        # Fix missing neck
        if 'Neck' not in armature.data.edit_bones:
            if 'Chest' in armature.data.edit_bones:
                if 'Head' in armature.data.edit_bones:
                    neck = armature.data.edit_bones.new('Neck')
                    chest = armature.data.edit_bones.get('Chest')
                    head = armature.data.edit_bones.get('Head')
                    neck.head = chest.tail
                    neck.tail = head.head

                    if neck.head.z == neck.tail.z:
                        neck.tail.z += 0.1

        # Straighten up the head bone
        if 'Head' in armature.data.edit_bones:
            head = armature.data.edit_bones.get('Head')
            head.tail.xy = head.head.xy
            if head.tail.z < head.head.z:
                head.tail.z = head.head.z + 0.1

        # Correct arm bone positions for better looks
        Common.correct_bone_positions()

        # Hips bone should be fixed as per specification from the SDK code
        if not mixamo:
            if 'Hips' in armature.data.edit_bones:
                if 'Spine' in armature.data.edit_bones:
                    if 'Left leg' in armature.data.edit_bones:
                        if 'Right leg' in armature.data.edit_bones:
                            hips = armature.data.edit_bones.get('Hips')
                            spine = armature.data.edit_bones.get('Spine')
                            left_leg = armature.data.edit_bones.get('Left leg')
                            right_leg = armature.data.edit_bones.get('Right leg')

                            # Fixing the hips

                            # Put Hips in the center of the leg bones
                            hips.head.x = (right_leg.head.x + left_leg.head.x) / 2

                            # Put Hips at 33% between spine and legs
                            hips.head.z = left_leg.head.z + (spine.head.z - left_leg.head.z) * 0.33

                            # If Hips are below or at the leg bones, put them above
                            if hips.head.z <= right_leg.head.z:
                                hips.head.z = right_leg.head.z + 0.1

                            # Make Hips point straight up
                            hips.tail.xy = hips.head.xy
                            hips.tail.z = spine.head.z

                            if hips.tail.z < hips.head.z:
                                hips.tail.z += 0.1

                            # Make legs bend very slightly forward
                            right_knee = armature.data.edit_bones.get('Right knee')
                            left_knee = armature.data.edit_bones.get('Left knee')
                            leg_vectors = []
                            if left_knee:
                                leg_vectors.append((left_leg.head, left_knee.head))
                            if right_knee:
                                leg_vectors.append((right_leg.head, right_knee.head))
                            for leg_head, knee_head in leg_vectors:
                                if all(round(leg, 4) == round(knee, 4) for leg, knee in zip(leg_head.xy, knee_head.xy)):
                                    print('FIXING LEG')
                                    knee_head.y -= 0.001

        # Function: Reweight all eye children into the eyes
        def add_eye_children(eye_bone, parent_name):
            for eye in eye_bone.children:
                temp_list_reweight_bones[eye.name] = parent_name
                add_eye_children(eye, parent_name)

        # Reweight all eye children into the eyes
        for eye_name in ['Eye_L', 'Eye_R']:
            if eye_name in armature.data.edit_bones:
                eye = armature.data.edit_bones.get(eye_name)
                add_eye_children(eye, eye.name)

        # Rotate if on head and not fbx (Unreal engine model)
        if 'Hips' in armature.data.edit_bones:

            hips = armature.pose.bones.get('Hips')

            obj = hips.id_data
            matrix_final = obj.matrix_world @ hips.matrix
            # print(matrix_final)
            # print(matrix_final[2][3])
            # print(fbx)

            if matrix_final[2][3] < 0:
                # print(hips.head[0], hips.head[1], hips.head[2])
                # Rotation of -180 around the X-axis
                rot_x_neg180 = Matrix.Rotation(-math.pi, 4, 'X')
                armature.matrix_world = rot_x_neg180 @ armature.matrix_world

                for mesh in meshes:
                    mesh.rotation_euler = (math.radians(180), 0, 0)

        # Fixes bones disappearing, prevents bones from having their tail and head at the exact same position
        Common.fix_zero_length_bones(armature)

        # Merged bones that should be deleted
        bones_to_delete = []
        
        meshes = Common.get_meshes_objects()

        # Mixing the weights
        for mesh in meshes:
            Common.unselect_all()
            Common.switch('OBJECT')
            Common.set_active(mesh)

            # for bone_name in temp_rename_bones.keys():
            #     bone = armature.data.bones.get(bone_name)
            #     if bone:
            #         print(bone_name)
            #         bone.hide = False

            # Temporarily remove armature modifier to avoid errors in console
            for mod in mesh.modifiers:
                if mod.type == 'ARMATURE':
                    bpy.ops.object.modifier_remove(modifier=mod.name)

            # Fix MMD twist bones
            print('FIX TWIST BONES')
            print(bones_to_delete)
            Common.fix_twist_bones(mesh, bones_to_delete)
            print(bones_to_delete)

            # Add bones to parent reweight list
            for name in Bones.bone_reweigth_to_parent:
                if "\\L" in name:
                    bones = [name.replace("\\Left", "Left").replace("\\L", "L"),
                             name.replace("\\Left", "Right").replace("\\L", "R")]
                else:
                    bones = [name]

                for bone_name in bones:
                    bone_child = None
                    bone_parent = None
                    for bone in armature.data.bones:
                        if bone_name.lower() == bone.name.lower():
                            bone_child = bone
                            bone_parent = bone.parent

                    if not bone_child or not bone_parent:
                        continue

                    if context.scene.keep_twist_bones and 'twist' in bone_child.name.lower():
                        continue
                    if context.scene.fix_twist_bones and bone_child.name.lower() in ['handtwist_l', 'handtwist_r', 'armtwist_l', 'armtwist_r']:
                        print('TWIST FOUND!')
                        continue

                    # search for next parent that is not in the "reweight to parent" list
                    parent_in_list = True
                    while parent_in_list:
                        parent_in_list = False
                        for name_tmp in Bones.bone_reweigth_to_parent:
                            if bone_parent.name == name_tmp.replace("\\Left", "Left").replace("\\L", "L") \
                                    or bone_parent.name == name_tmp.replace("\\Left", "Right").replace("\\L", "R"):
                                bone_parent = bone_parent.parent
                                parent_in_list = True
                                break

                    if not bone_parent:
                        continue

                    if bone_child.name not in mesh.vertex_groups:
                        # Add bone to delete list
                        if bone_child.name not in bones_to_delete:
                            bones_to_delete.append(bone_child.name)
                        continue

                    if bone_parent.name not in mesh.vertex_groups:
                        mesh.vertex_groups.new(name=bone_parent.name)

                    bone_tmp = armature.data.bones.get(bone_child.name)
                    if bone_tmp:
                        for child in bone_tmp.children:
                            if not temp_list_reparent_bones.get(child.name):
                                temp_list_reparent_bones[child.name] = bone_parent.name

                    # Add bone to delete list
                    if bone_child.name not in bones_to_delete:
                        bones_to_delete.append(bone_child.name)

                    # Mix the weights
                    Common.mix_weights(mesh, bone_child.name, bone_parent.name)

            # Merge weights
            for bone_new, bones_old in temp_reweight_bones.items():
                if "\\L" in bone_new:
                    bones = [[bone_new.replace("\\Left", "Left").replace("\\L", "L"), ""],
                             [bone_new.replace("\\Left", "Right").replace("\\L", "R"), ""]]
                else:
                    bones = [[bone_new, ""]]
                for bone_old in bones_old:
                    if "\\L" in bone_new:
                        bones[0][1] = bone_old.replace("\\Left", "Left").replace("\\L", "L")
                        bones[1][1] = bone_old.replace("\\Left", "Right").replace("\\L", "R")
                    else:
                        bones[0][1] = bone_old

                    for bone in bones:  # bone[0] = new name, bone[1] = old name
                        current_step += 1
                        wm.progress_update(current_step)

                        # Seach for vertex group
                        vg = None
                        for vg_tmp in mesh.vertex_groups:
                            if vg_tmp.name.lower() == bone[1].lower():
                                vg = vg_tmp
                                break

                        # Cancel if vertex group was not found
                        if not vg:
                            # Add bone to delete list
                            if bone[1] not in bones_to_delete:
                                bones_to_delete.append(bone[1])
                            continue

                        if bone[0] == vg.name:
                            print('BUG: ' + bone[0] + ' tried to mix weights with itself!')
                            continue

                        if context.scene.keep_twist_bones and 'twist' in bone[1].lower():
                            continue
                        if context.scene.fix_twist_bones and bone[1].lower() in ['handtwist_l', 'handtwist_r', 'armtwist_l', 'armtwist_r']:
                            print('TWIST FOUND!')
                            continue

                        # print(bone[1] + " to1 " + bone[0])

                        # If important vertex group is not there create it
                        if mesh.vertex_groups.get(bone[0]) is None:
                            if bone[0] in Bones.dont_delete_these_bones and bone[0] in armature.data.bones:
                                bpy.ops.object.vertex_group_add()
                                mesh.vertex_groups.active.name = bone[0]
                                if mesh.vertex_groups.get(bone[0]) is None:
                                    continue
                            else:
                                continue

                        bone_tmp = armature.data.bones.get(vg.name)
                        if bone_tmp:
                            for child in bone_tmp.children:
                                if not temp_list_reparent_bones.get(child.name):
                                    temp_list_reparent_bones[child.name] = bone[0]

                        # Add bone to delete list
                        if vg.name not in bones_to_delete:
                            bones_to_delete.append(vg.name)

                        # Mix and delete group
                        Common.mix_weights(mesh, vg.name, bone[0])

            # Old mixing weights. Still important
            for key, value in temp_list_reweight_bones.items():
                current_step += 1
                wm.progress_update(current_step)

                # Search for vertex groups
                vg_from = None
                vg_to = None
                for vg_tmp in mesh.vertex_groups:
                    if vg_tmp.name.lower() == key.lower():
                        vg_from = vg_tmp
                        if vg_to:
                            break
                    elif vg_tmp.name.lower() == value.lower():
                        vg_to = vg_tmp
                        if vg_from:
                            break

                # Cancel if vertex groups was not found
                if not vg_from:
                    # Add bone to delete list
                    if key not in bones_to_delete:
                        bones_to_delete.append(key)
                    continue

                # Cancel if vertex groups was not found
                if not vg_to:
                    continue

                if context.scene.keep_twist_bones and 'twist' in vg_from.name.lower():
                    continue
                if context.scene.fix_twist_bones and vg_from.name.lower() in ['handtwist_l', 'handtwist_r', 'armtwist_l', 'armtwist_r']:
                    print('TWIST FOUND!')
                    continue

                bone_tmp = armature.data.bones.get(vg_from.name)
                if bone_tmp:
                    for child in bone_tmp.children:
                        if not temp_list_reparent_bones.get(child.name):
                            temp_list_reparent_bones[child.name] = vg_to.name

                if vg_from.name == vg_to.name:
                    print('BUG: ' + vg_to.name + ' tried to mix weights with itself!')
                    continue

                # Add bone to delete list
                if vg_from.name not in bones_to_delete:
                    bones_to_delete.append(vg_from.name)

                # Mix the weights
                Common.mix_weights(mesh, vg_from.name, vg_to.name)

            # Put back armature modifier
            mod = mesh.modifiers.new("Armature", 'ARMATURE')
            mod.object = armature

            # Delete Upper Chest, if selected
            if not context.scene.keep_upper_chest:
                if 'Upper Chest' in mesh.vertex_groups and 'Chest' in mesh.vertex_groups:
                    Common.mix_weights(mesh, 'Upper Chest', 'Chest')

                    # Add bone to delete list
                    if 'Upper Chest' not in bones_to_delete:
                        bones_to_delete.append('Upper Chest')

        Common.unselect_all()
        Common.set_active(armature)
        Common.switch('EDIT')

        # Delete all the leftover bones from the merging process
        for bone_name in bones_to_delete:
            if bone_name in armature.data.edit_bones:
                armature.data.edit_bones.remove(armature.data.edit_bones.get(bone_name))

        # Reparent all bones to be correct for unity mapping and vrc itself
        for key, value in temp_list_reparent_bones.items():
            if value == 'Upper Chest' and 'Upper Chest' not in armature.data.edit_bones:
                value = 'Chest'

            if key in armature.data.edit_bones and value in armature.data.edit_bones:
                armature.data.edit_bones.get(key).parent = armature.data.edit_bones.get(value)

        # Fix MMD twist bone names
        Common.fix_twist_bone_names(armature)

        if context.scene.remove_zero_weight:
            # Removes unused vertex groups
            Common.remove_unused_vertex_groups()

            # Zero weight bones should be deleted
            Common.delete_zero_weight()

        # Connect all bones with their children if they have exactly one
        if context.scene.connect_bones:
            Common.fix_bone_orientations(armature)

        # # This is code for testing
        # print('LOOKING FOR BONES!')
        # if 'Head' in Common.get_armature().pose.bones:
        #     print('THEY ARE THERE!')
        # else:
        #     print('NOT FOUND!!!!!!')
        # return {'FINISHED'}

        # At this point, everything should be fixed and now we validate and give errors if needed

        # The bone hierarchy needs to be validated
        hierarchy_check_hips = check_hierarchy(False, [
            ['Hips', 'Spine', 'Chest', 'Neck', 'Head'],
            ['Hips', 'Left leg', 'Left knee', 'Left ankle'],
            ['Hips', 'Right leg', 'Right knee', 'Right ankle'],
            ['Chest', 'Left shoulder', 'Left arm', 'Left elbow', 'Left wrist'],
            ['Chest', 'Right shoulder', 'Right arm', 'Right elbow', 'Right wrist']
        ])

        # Armature should be named correctly (has to be at the end because of multiple armatures)
        Common.fix_armature_names()
        
        fixed_uv_coords = False
        armature.show_in_front = False
        wm.progress_end()

        if not hierarchy_check_hips['result']:
            self.report({'ERROR'}, hierarchy_check_hips['message'])
            saved_data.load()
            return {'FINISHED'}

        if fixed_uv_coords:
            saved_data.load()
            Common.show_error(6.2, [t('FixArmature.error.faultyUV1', uvcoord=str(fixed_uv_coords)),
                                          t('FixArmature.error.faultyUV2'),
                                          t('FixArmature.error.faultyUV3')])
            return {'FINISHED'}

        # Clean up cache to prevent memory leaks
        if bone_cache:
            bone_cache.clear_cache()
            del bone_cache

        saved_data.load()

        self.report({'INFO'}, t('FixArmature.fixedSuccess'))
        return {'FINISHED'}


def check_hierarchy(check_parenting, correct_hierarchy_array):
    armature = Common.set_default_stage()

    missing_bones = []
    missing2 = [t('FixArmature.bonesNotFound'), '']

    for correct_hierarchy in correct_hierarchy_array:  # For each hierarchy array
        line = ' - '

        for index, bone in enumerate(correct_hierarchy):  # For each hierarchy bone item
            if bone not in missing_bones and bone not in armature.data.bones:
                missing_bones.append(bone)
                if len(line) > 3:
                    line += ', '
                line += bone

        if len(line) > 3:
            missing2.append(line)

    if len(missing2) > 2 and not check_parenting:
        missing2.append('')
        missing2.append(t('FixArmature.cantFix1'))
        missing2.append(t('FixArmature.cantFix2'))
        missing2.append(t('FixArmature.cantFix3'))

        Common.show_error(6.4, missing2)
        return {'result': True, 'message': ''}

    if check_parenting:
        for correct_hierarchy in correct_hierarchy_array:  # For each hierachy array
            previous = None
            for index, bone in enumerate(correct_hierarchy):  # For each hierarchy bone item
                if index > 0:
                    previous = correct_hierarchy[index - 1]

                if bone in armature.data.bones:
                    bone = armature.data.bones[bone]

                    # If a previous item was found
                    if previous is not None:
                        # And there is no parent, then we have a problem mkay
                        if bone.parent is None:
                            return {'result': False, 'message': bone.name + t('FixArmature.notParent')}
                        # Previous needs to be the parent of the current item
                        if previous != bone.parent.name:
                            return {'result': False, 'message': bone.name + t('FixArmature.notParentTo1') + previous + t('FixArmature.notParentTo2')}

    return {'result': True}
