# MIT License

import bpy
import copy
import math
import platform
import numpy as np
from mathutils import Matrix

from . import common as Common
from . import translate as Translate
from . import armature_bones as Bones
from .register import register_wrap
from .translations import t

# Only load mmd_tools_local if it's not on linux and 2.90 or higher since it causes Blender to crash
mmd_tools_local_installed = False
if platform.system() != "Linux":
    try:
        from ..mmd_tools_local.operators import morph as Morph
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
        
        # Check for Rigify/Metarig (shared detector, so this agrees with the converter's poll).
        # This is the only Rigify gate in Fix Model.
        if Common.is_rigify_armature(armature):
            errors.append("Rigify and Metarig armatures are not supported by Fix Model. Use the 'Convert Rigify to Cats' button in Model Options instead.")
        
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
                
        # Check for valid vertex groups
        for mesh in meshes:
            if not mesh.vertex_groups:
                warnings.append(f"Mesh '{mesh.name}' has no vertex groups")
            
            # Check for NaN values in UV coordinates.
            uv_issues = 0
            for uv_layer in mesh.data.uv_layers:
                uv_count = len(uv_layer.data)
                if not uv_count:
                    continue
                coords = np.empty(uv_count * 2, dtype=np.float32)
                uv_layer.data.foreach_get("uv", coords)
                # Count UVs where either component is NaN (matches the old per-UV count).
                nan_per_uv = np.isnan(coords).reshape(-1, 2).any(axis=1)
                uv_issues += int(np.count_nonzero(nan_per_uv))

            if uv_issues > 0:
                warnings.append(f"Mesh '{mesh.name}' has {uv_issues} faulty UV coordinates that will be fixed")
        
        return errors, warnings


class EditBoneIndex:
    """Case-insensitive name -> EditBone index used by the rename passes."""

    def __init__(self, armature):
        self.edit_bones = armature.data.edit_bones
        self.rebuild()

    def rebuild(self):
        """(Re)build from scratch, e.g. after a pass that renamed bones in bulk."""
        self._by_lower = {}
        # setdefault keeps the first match, which is what the linear scans returned
        for bone in self.edit_bones:
            self._by_lower.setdefault(bone.name.lower(), bone)

    def get(self, name):
        """The first edit bone whose name matches case-insensitively, or None."""
        return self._by_lower.get(name.lower())

    def rename(self, bone, new_name):
        """Rename a bone, keeping the index consistent."""
        old_lower = bone.name.lower()
        bone.name = new_name
        if self._by_lower.get(old_lower) is bone:
            del self._by_lower[old_lower]
        # Blender adjusts the name on collision, so index whatever it ended up as
        self._by_lower.setdefault(bone.name.lower(), bone)


class VertexGroupIndex:
    def __init__(self, mesh):
        self.vertex_groups = mesh.vertex_groups
        self._by_lower = None

    def invalidate(self):
        """Call after adding or removing a vertex group on this mesh."""
        self._by_lower = None

    def get(self, name):
        """The first vertex group whose name matches case-insensitively, or None."""
        if self._by_lower is None:
            self._by_lower = {}
            # setdefault keeps the first match, which is what the linear scans returned
            for group in self.vertex_groups:
                self._by_lower.setdefault(group.name.lower(), group)
        return self._by_lower.get(name.lower())


def _begin_morph_bake(mesh, armature):
    """Make a mesh evaluate to its base shape plus armature deformation only."""
    # Ensure we have shape keys
    if not mesh.data.shape_keys:
        mesh.shape_key_add(name="Basis")

    state = {
        'mesh': mesh,
        'active_shape_key_index': mesh.active_shape_key_index,
        'show_only_shape_key': mesh.show_only_shape_key,
        'muted_modifiers': [],
        # cos are xyz positions and get flattened by foreach_get/foreach_set, so the
        # array length is 3 times the vertex count. Re-used for every morph.
        'coords': np.empty(len(mesh.data.vertices) * 3, dtype=np.single),
    }

    mesh.show_only_shape_key = True

    # Disable every existing modifier and drive the deformation from one temporary
    # armature modifier.
    for mod in mesh.modifiers:
        if mod.show_viewport:
            mod.show_viewport = False
            state['muted_modifiers'].append(mod)
    armature_mod = mesh.modifiers.new('CatsBoneMorph', 'ARMATURE')
    armature_mod.object = armature
    state['armature_mod'] = armature_mod

    return state


def _end_morph_bake(state):
    """Restore everything _begin_morph_bake() changed on a mesh."""
    mesh = state['mesh']
    mesh.modifiers.remove(state['armature_mod'])
    for mod in state['muted_modifiers']:
        mod.show_viewport = True
    mesh.show_only_shape_key = state['show_only_shape_key']
    mesh.active_shape_key_index = state['active_shape_key_index']


def _plan_bone_morph_names(context, armature, mmd_root):
    """Decide which bone morphs take the MMD author's English name as their shape key."""
    names = [morph.name for morph in mmd_root.bone_morphs]
    author_names = Translate.collect_mmd_english_names(armature)
    return Translate.plan_author_names(names, author_names, context.scene.mmd_english_names_shapekeys,
                                       translating_shapes=True)


def convert_bone_morphs_native(context, armature, mmd_root):
    """Native bone morph to shape key conversion for Linux compatibility

    mmd_tools_local cannot be imported on Linux, so the apply-modifier-as-shapekey
    route the other platforms take is unavailable. Instead we pose the armature for
    each morph and copy the depsgraph-evaluated (skinned) vertex positions into a new
    shape key. shape_key_add() on its own only ever samples the undeformed base mesh,
    which produced empty keys that clean_shapekeys() then threw away.
    """
    if not hasattr(mmd_root, 'bone_morphs') or len(mmd_root.bone_morphs) == 0:
        return

    from mathutils import Vector, Quaternion

    mesh_objects = Common.get_meshes_objects()
    if not mesh_objects:
        return

    picked_author_names, to_translate = _plan_bone_morph_names(context, armature, mmd_root)

    # Update translation dictionary (same as bones do)
    Translate.update_dictionary(to_translate, translating_shapes=True)

    wm = context.window_manager
    current_step = 0
    wm.progress_begin(current_step, len(mmd_root.bone_morphs))

    bake_targets = [_begin_morph_bake(mesh, armature) for mesh in mesh_objects]

    # Morph offsets apply on top of the current pose. Keep that pose as matrices:
    # assigning matrix_basis is decomposed into whatever rotation_mode each bone uses,
    # whereas writing rotation_quaternion is silently ignored on euler-mode bones.
    original_basis = {pose_bone.name: pose_bone.matrix_basis.copy() for pose_bone in armature.pose.bones}

    try:
        # Process each bone morph
        for morph in mmd_root.bone_morphs:
            current_step += 1
            wm.progress_update(current_step)

            if not morph.data:
                continue

            # Apply bone transformations
            posed_bones = []
            for morph_data in morph.data:
                pose_bone = armature.pose.bones.get(morph_data.bone)
                if not pose_bone:
                    continue
                offset = Matrix.Translation(Vector(morph_data.location)) \
                    @ Quaternion(morph_data.rotation).to_matrix().to_4x4()
                pose_bone.matrix_basis = original_basis[pose_bone.name] @ offset
                posed_bones.append(pose_bone)

            if not posed_bones:
                continue

            # shape_key_add() below makes its new key active, so re-pin Basis first
            for state in bake_targets:
                state['mesh'].active_shape_key_index = 0

            context.view_layer.update()
            depsgraph = context.evaluated_depsgraph_get()
            for state in bake_targets:
                state['mesh'].evaluated_get(depsgraph).data.vertices.foreach_get('co', state['coords'])

            # Reset bone transforms for next morph
            for pose_bone in posed_bones:
                pose_bone.matrix_basis = original_basis[pose_bone.name]

            shape_key_name, _ = Translate.resolve_name(morph.name, picked_author_names.get(morph.name),
                                                       add_space=True, translating_shapes=True)
            for state in bake_targets:
                state['mesh'].shape_key_add(name=shape_key_name, from_mix=False) \
                    .data.foreach_set('co', state['coords'])
    finally:
        # Restore temporarily changed attributes and remove the added armature modifiers
        for pose_bone in armature.pose.bones:
            pose_bone.matrix_basis = original_basis[pose_bone.name]
        for state in bake_targets:
            _end_morph_bake(state)
        wm.progress_end()
        context.view_layer.update()


# Bone renames/removals from the most recent Fix Model run, shown on demand so the
# user knows which downstream references (Unity components, animation clips,
# constraints) need rebinding after a re-export.
_last_bone_change_report = {'renamed': [], 'removed': []}


def store_bone_change_report(report):
    global _last_bone_change_report
    _last_bone_change_report = report


def get_bone_change_report():
    return _last_bone_change_report


@register_wrap
class ShowBoneChangeReport(bpy.types.Operator):
    bl_idname = 'cats_armature.show_bone_change_report'
    bl_label = t('ShowBoneChangeReport.label')
    bl_description = t('ShowBoneChangeReport.desc')
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        report = get_bone_change_report()
        return bool(report['renamed'] or report['removed'])

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        dpi_value = Common.get_user_preferences().system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * 4.5))

    def draw(self, context):
        report = get_bone_change_report()
        layout = self.layout
        col = layout.column(align=True)

        if report['renamed']:
            col.label(text=t('ShowBoneChangeReport.renamed', number=str(len(report['renamed']))), icon='SORTALPHA')
            renamed_col = col.column(align=True)
            renamed_col.scale_y = 0.7
            for old_name, new_name in report['renamed']:
                renamed_col.label(text=f'{old_name}  →  {new_name}')
            col.separator()

        if report['removed']:
            col.label(text=t('ShowBoneChangeReport.removed', number=str(len(report['removed']))), icon='X')
            removed_col = col.column(align=True)
            removed_col.scale_y = 0.7
            for bone_name in report['removed']:
                removed_col.label(text=bone_name)
            col.separator()

        hint_col = col.column(align=True)
        hint_col.scale_y = 0.7
        hint_col.label(text=t('ShowBoneChangeReport.hint'), icon='INFO')


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
        
        # Tag every bone with its current name so we can report exactly what got
        # renamed or removed. Downstream tools bind to bones by name, so users need
        # to know which references they have to rebind after a fix.
        bone_name_snapshot = Common.snapshot_bone_identities(armature)

        # Check if this is an MMD model
        mmd_root = None
        try:
            mmd_root = armature.parent.mmd_root
        except AttributeError:
            pass

        if mmd_root:
            Common.set_active(armature)
            Common.switch('OBJECT')

            for collection in list(armature.data.collections):
                armature.data.collections.remove(collection)
        
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
            # VRM import/bake pipelines commonly leave the mesh unparented from the armature, but name
            # it with a '.baked'/'.baked0' suffix. Kept in sync with the equivalent check in
            # _validate_meshes() above, since both need to agree on what counts as a VRM model.
            for mesh in Common.get_meshes_objects(mode=2):
                if mesh.name.endswith(('.baked', '.baked0')):
                    is_vrm = True
                    break
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
        steps = 0
        steps_per_mesh = 0
        for key, value in temp_rename_bones.items():
            if "\\L" in key:
                steps += 2 * len(value)
            else:
                steps += len(value)
        for key, value in temp_reweight_bones.items():
            if "\\L" in key:
                steps_per_mesh += 2 * len(value)
            else:
                steps_per_mesh += len(value)
        steps_per_mesh += len(temp_list_reweight_bones)  # + len(Bones.bone_list_parenting)

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
                    # Same naming as Translate Shape Keys dictionary, then the MMD
                    # author's English name (per the Author Names setting), then the
                    # online provider.
                    picked_author_names, to_translate = _plan_bone_morph_names(context, armature, mmd_root)

                    # Update translation dictionary (same as bones do)
                    Translate.update_dictionary(to_translate, translating_shapes=True)
                    
                    # Use mmd_tools_local for non-Linux platforms
                    current_step = 0
                    wm.progress_begin(current_step, len(mmd_root.bone_morphs))

                    morph_meshes = Common.get_meshes_objects()

                    armature.data.pose_position = 'POSE'
                    for index, morph in enumerate(mmd_root.bone_morphs):
                        current_step += 1
                        wm.progress_update(current_step)

                        armature.parent.mmd_root.active_morph = index
                        Morph.ViewBoneMorph.execute(None, context)

                        # The modifier name becomes the shape key name, keyed off the Japanese name
                        modifier_name, _ = Translate.resolve_name(morph.name, picked_author_names.get(morph.name),
                                                                  add_space=True, translating_shapes=True)

                        for mesh in morph_meshes:
                            Common.set_active(mesh)
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
                if Common.is_rigidbody_or_joint(child):
                    if child.name not in to_delete:
                        to_delete.append(child.name)
                    # delete_hierarchy() takes the whole subtree, so don't scan inside
                    continue
                for child2 in child.children:
                    if Common.is_rigidbody_or_joint(child2) and child2.name not in to_delete:
                        to_delete.append(child2.name)
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
        
        Translate.store_mmd_english_names(armature)
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

        fixed_uv_coords = 0

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

            # Fix faulty UV coordinates. Read the whole layer into NumPy, zero any
            # NaN components, and write it back in one call far faster than
            # per UV Python on dense meshes, and unlike the old loop this also
            # checks the final UV.
            for uv in mesh.data.uv_layers:
                uv_count = len(uv.data)
                if not uv_count:
                    continue
                coords = np.empty(uv_count * 2, dtype=np.float32)
                uv.data.foreach_get("uv", coords)
                nan_mask = np.isnan(coords)
                nan_total = int(np.count_nonzero(nan_mask))
                if nan_total:
                    coords[nan_mask] = 0.0
                    uv.data.foreach_set("uv", coords)
                    fixed_uv_coords += nan_total

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

        # Remove Bone Collections (Armature.collections), which in 4.0 replaced Bone Groups and subsumed
        # Armature.layers. Bone colors are now defined per-bone, Bone.color.palette and PoseBone.color.palette
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

        for bone in armature.data.edit_bones:
            if bone.name in Bones.bone_list or bone.name.startswith(tuple(Bones.bone_list_with)):
                if bone.parent is not None:
                    steps_per_mesh += 1
                else:
                    steps_per_mesh -= 1

        # Start loading bar
        current_step = 0
        wm.progress_begin(current_step, steps + steps_per_mesh * max(1, len(meshes)))

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

        # Bones the user marked as protected are never renamed
        protected_patterns = Common.get_protected_bone_patterns()

        # Standardize names
        for bone in armature.data.edit_bones:
            current_step += 1
            wm.progress_update(current_step)

            if Common.is_protected_bone(bone.name, protected_patterns):
                continue

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
            if '\\Left' not in names[1] and '\\L' not in names[1]:
                conflicting_bones.append(names)
                continue

            names0 = []
            name1 = ''
            name2 = ''
            for name0 in names[0]:
                names0.append(name0.replace('\\Left', 'Left').replace('\\left', 'left').replace('\\L', 'L').replace('\\l', 'l'))
            if '\\Left' in names[1] or '\\L' in names[1]:
                name1 = names[1].replace('\\Left', 'Left').replace('\\left', 'left').replace('\\L', 'L').replace('\\l', 'l')
            if '\\Left' in names[2] or '\\L' in names[2]:
                name2 = names[2].replace('\\Left', 'Left').replace('\\left', 'left').replace('\\L', 'L').replace('\\l', 'l')
            conflicting_bones.append((names0, name1, name2))

            for name0 in names[0]:
                names0.append(name0.replace('\\Left', 'Right').replace('\\left', 'right').replace('\\L', 'R').replace('\\l', 'r'))
            if '\\Left' in names[1] or '\\L' in names[1]:
                name1 = names[1].replace('\\Left', 'Right').replace('\\left', 'right').replace('\\L', 'R').replace('\\l', 'r')
            if '\\Left' in names[2] or '\\L' in names[2]:
                name2 = names[2].replace('\\Left', 'Right').replace('\\left', 'right').replace('\\L', 'R').replace('\\l', 'r')
            conflicting_bones.append((names0, name1, name2))

        # Name -> bone index for the rename passes below, so they do not rescan every
        # edit bone for every candidate name
        bone_index = EditBoneIndex(armature)

        # Resolve conflicting bone names
        for names in conflicting_bones:

            # Search for bone in armature
            bone = bone_index.get(names[1])

            # Cancel if bone was not found
            if not bone:
                continue

            # Search for all the required bones
            found_all = True
            for name in names[0]:
                if not bone_index.get(name):
                    found_all = False
                    break

            # Rename only if all required bones are found
            if found_all:
                bone_index.rename(bone, names[2])

        # Standardize bone names again (new duplicate bones have ".001" in it)
        for bone in armature.data.edit_bones:
            if Common.is_protected_bone(bone.name, protected_patterns):
                continue
            bone.name = bone.name.replace('.', '_')

        # That pass renamed bones in bulk behind the index's back
        bone_index.rebuild()

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
                    bone_final = bone_index.get(bone[1])

                    # Cancel if bone was not found
                    if not bone_final:
                        continue

                    # Never rename bones the user marked as protected
                    if Common.is_protected_bone(bone_final.name, protected_patterns):
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
                        bone_index.rename(bone_final, bone[0])

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

            # Temporarily remove armature modifier to avoid errors in console.
            # Snapshot with list() so removal doesn't disturb iteration, and use the data API so we
            # target this mesh's modifiers directly instead of relying on the active-object context.
            for mod in list(mesh.modifiers):
                if mod.type == 'ARMATURE':
                    mesh.modifiers.remove(mod)

            # Fix MMD twist bones
            print('FIX TWIST BONES')
            print(bones_to_delete)
            Common.fix_twist_bones(mesh, bones_to_delete)
            print(bones_to_delete)

            # Name -> vertex group index for the merge passes below. Built after
            # fix_twist_bones, which adds and removes groups of its own.
            vg_index = VertexGroupIndex(mesh)

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
                        vg_index.invalidate()

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
                    vg_index.invalidate()

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
                        vg = vg_index.get(bone[1])

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
                                vg_index.invalidate()
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
                        vg_index.invalidate()

            # Old mixing weights. Still important
            for key, value in temp_list_reweight_bones.items():
                current_step += 1
                wm.progress_update(current_step)

                # Search for vertex groups
                vg_from = vg_index.get(key)
                vg_to = None if key.lower() == value.lower() else vg_index.get(value)

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
                vg_index.invalidate()

            # Put back armature modifier
            mod = mesh.modifiers.new("Armature", 'ARMATURE')
            mod.object = armature

            # Delete Upper Chest, if selected
            if not context.scene.keep_upper_chest:
                if 'Upper Chest' in mesh.vertex_groups and 'Chest' in mesh.vertex_groups:
                    Common.mix_weights(mesh, 'Upper Chest', 'Chest')
                    vg_index.invalidate()

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

        armature.show_in_front = False
        wm.progress_end()

        # Build the bone change report and drop the tracking data.
        change_report = Common.build_bone_change_report(armature, bone_name_snapshot)
        Common.clear_bone_identity_snapshot(armature)
        store_bone_change_report(change_report)

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

        saved_data.load()

        renamed_count = len(change_report['renamed'])
        removed_count = len(change_report['removed'])
        if renamed_count or removed_count:
            self.report({'INFO'}, t('FixArmature.fixedSuccessWithChanges',
                                    renamed=str(renamed_count),
                                    removed=str(removed_count)))
        else:
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
