# MIT License

import re
import bpy
import time
import bmesh
import numpy as np

from bpy.types import (
    Key,
    ShapeKey,
    AnimData,
    Context,
    Object,
    Mesh,
    Node,
    NodeLink,
    ShaderNodeTexImage,
    ShaderNodeGroup,
)

from math import degrees
from mathutils import Vector
from datetime import datetime
from html.parser import HTMLParser
from functools import lru_cache
from html.entities import name2codepoint
from typing import Optional, Set, Dict, Any

from . import common as Common
from . import iconloader as Iconloader
from . import translate as Translate
from . import armature_bones as Bones
from . import settings as Settings
from .register import register_wrap
from .translations import t
from sys import intern

from mmd_tools_local import utils

def version_3_6_or_older():
    return bpy.app.version < (3, 7)


def get_objects():
    return bpy.context.view_layer.objects


class SavedData:
    __object_properties = {}
    __active_object = None

    def __init__(self):
        context = bpy.context
        # initialize as instance attributes rather than class attributes
        self.__object_properties = {}
        self.__active_object = None

        for obj in get_objects():
            mode = obj.mode
            selected = obj.select_get()
            hidden = is_hidden(obj)
            pose = None
            if obj.type == 'ARMATURE':
                pose = obj.data.pose_position
            self.__object_properties[obj.name] = [mode, selected, hidden, pose]

            active = context.view_layer.objects.active
            if active:
                self.__active_object = active.name

    def load(self, ignore=None, load_mode=True, load_select=True, load_hide=True, load_active=True, hide_only=False):
        if not ignore:
            ignore = []
        if hide_only:
            load_mode = False
            load_select = False
            load_active = False

        for obj_name, values in self.__object_properties.items():
            # print(obj_name, ignore)
            if obj_name in ignore:
                continue

            obj = get_objects().get(obj_name)
            if not obj:
                continue

            mode, selected, hidden, pose = values
            # print(obj_name, mode, selected, hidden)
            print(obj_name, pose)

            if load_mode and obj.mode != mode:
                set_active(obj, skip_sel=True)
                switch(mode, check_mode=False)
                if pose:
                    obj.data.pose_position = pose

            if load_select:
                select(obj, selected)
            if load_hide:
                hide(obj, hidden)

        # Set the active object
        if load_active and self.__active_object and get_objects().get(self.__active_object):
            context = bpy.context
            if self.__active_object not in ignore and self.__active_object != context.view_layer.objects.active:
                set_active(get_objects().get(self.__active_object), skip_sel=True)

def get_armature(armature_name=None):
    if not armature_name:
        armature_name = bpy.context.scene.armature
        
    # Get all objects in the scene
    objects = get_objects()
    if not objects:
        return None
        
    # First try to find exact name match
    for obj in objects:
        if obj and obj.type == 'ARMATURE':
            if obj.name == armature_name:
                return obj
                
    # If no exact match, return first armature if name is empty
    if Common.is_enum_empty(armature_name):
        for obj in objects:
            if obj and obj.type == 'ARMATURE':
                return obj

def get_armature_objects():
    armatures = []
    for obj in get_objects():
        if obj.type == 'ARMATURE':
            armatures.append(obj)
    return armatures


def get_top_parent(child):
    if child.parent:
        return get_top_parent(child.parent)
    return child


def unhide_all_unnecessary():
    # TODO: Documentation? What does "unnecessary" mean?
    try:
        switch('OBJECT')
        bpy.ops.object.hide_view_clear()
    except RuntimeError:
        pass

    for collection in bpy.data.collections:
        collection.hide_select = False
        collection.hide_viewport = False


def unhide_all():
    for obj in get_objects():
        hide(obj, False)
        set_unselectable(obj, False)

        unhide_all_unnecessary()


def unhide_children(parent):
    for child in parent.children:
        hide(child, False)
        set_unselectable(child, False)
        unhide_children(child)


def unhide_all_of(obj_to_unhide=None):
    if not obj_to_unhide:
        return

    top_parent = get_top_parent(obj_to_unhide)
    hide(top_parent, False)
    set_unselectable(top_parent, False)
    unhide_children(top_parent)


def unselect_all():
    for obj in get_objects():
        select(obj, False)


def set_active(obj, skip_sel=False):
    if not skip_sel:
        select(obj)
        bpy.context.view_layer.objects.active = obj


def select(obj, sel=True):
    if obj is not None:
        hide(obj, False)
        obj.select_set(sel)
        

def hide(obj, val=True):
    if hasattr(obj, 'hide_set'):
        obj.hide_set(val)
    elif hasattr(obj, 'hide'):
        obj.hide = val


def is_hidden(obj):
    if hasattr(obj, 'hide_get'):
        return obj.hide_get()
    elif hasattr(obj, 'hide'):
        return obj.hide
    return False  # Return a default value if the hide state cannot be determined


def set_unselectable(obj, val=True):
    obj.hide_select = val


def switch(new_mode, check_mode=True):
    context = bpy.context
    active = context.view_layer.objects.active
    if check_mode and active and active.mode == new_mode:
        return
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=new_mode, toggle=False)


def remove_rigidbodies_global():

    if bpy.context.scene.remove_rigidbodies_joints_global:
        print('Collections:')
        for collection in bpy.data.collections:
            print(' ' + collection.name, collection.name.lower())
            if 'rigidbody' in collection.name.lower():
                print('DELETE')
                for obj in collection.objects:
                    delete(obj)
                bpy.data.collections.remove(collection)

    armature = get_armature()
    if armature:
        set_active(armature)

    return armature

def set_default_stage():
    """
    Selects the armature, unhides everything and sets the modes of every object to object mode
    :return: the armature
    """

    unhide_all()
    unselect_all()

    for obj in get_objects():
        set_active(obj)
        switch('OBJECT')
        if obj.type == 'ARMATURE':
            # obj.data.pose_position = 'REST'
            pass

        select(obj, False)

    armature = get_armature()
    if armature:
        set_active(armature)

    return armature


def apply_modifier(mod, as_shapekey=False):
    if bpy.app.version < (2, 90):
        bpy.ops.object.modifier_apply(apply_as='SHAPE' if as_shapekey else 'DATA', modifier=mod.name)
        return

    if as_shapekey:
        bpy.ops.object.modifier_apply_as_shapekey(keep_modifier=False, modifier=mod.name)
    else:
        bpy.ops.object.modifier_apply(modifier=mod.name)


def remove_bone(find_bone):
    armature = get_armature()
    switch('EDIT')
    for bone in armature.data.edit_bones:
        if bone.name == find_bone:
            armature.data.edit_bones.remove(bone)


def remove_empty():
    armature = set_default_stage()
    if armature.parent and armature.parent.type == 'EMPTY':
        unselect_all()
        set_active(armature.parent)
        bpy.ops.object.delete(use_global=False)
        unselect_all()


def remove_unused_vertex_groups(ignore_main_bones=False):
    remove_count = 0
    unselect_all()
    for mesh in get_meshes_objects(mode=2):
        mesh.update_from_editmode()

        vgroup_used = {i: False for i, k in enumerate(mesh.vertex_groups)}

        for v in mesh.data.vertices:
            for g in v.groups:
                if g.weight > 0.0:
                    vgroup_used[g.group] = True

        for i, used in sorted(vgroup_used.items(), reverse=True):
            if not used:
                if ignore_main_bones and mesh.vertex_groups[i].name in Bones.dont_delete_these_main_bones:
                    continue
                mesh.vertex_groups.remove(mesh.vertex_groups[i])
                remove_count += 1
    return remove_count


def find_center_vector_of_vertex_group(mesh, vertex_group):
    data = mesh.data
    verts = data.vertices
    verts_in_group = []

    # Ensure the vertex group exists
    vg = mesh.vertex_groups.get(vertex_group)
    if vg is None:
        return None  # Vertex group doesn't exist
    for vert in verts:
        i = vert.index
        try:
            if vg.weight(i) > 0:
                verts_in_group.append(vert)
        except RuntimeError:
            # Vertex is not in the group
            pass

    if not verts_in_group:
        return None  # No vertices in the group
    # Calculate the average position
    total = Vector()
    for vert in verts_in_group:
        total += vert.co

    average = total / len(verts_in_group)
    return average


def vertex_group_exists(mesh_name, bone_name):
    mesh = get_objects()[mesh_name]
    data = mesh.data
    verts = data.vertices

    for vert in verts:
        i = vert.index
        try:
            mesh.vertex_groups[bone_name].weight(i)
            return True
        except:
            pass

    return False


def get_meshes(self, context):
    # Modes:
    # 0 = With Armature only
    # 1 = Without armature only
    # 2 = All meshes

    choices = []

    for mesh in get_meshes_objects(mode=0, check=False):
        choices.append((mesh.name, mesh.name, mesh.name))

    return _sort_enum_choices_by_identifier_lower(choices)


def get_top_meshes(self, context):
    choices = []

    for mesh in get_meshes_objects(mode=1, check=False):
        choices.append((mesh.name, mesh.name, mesh.name))

    return choices


def get_armature_list(self, context):
    choices = []

    for armature in get_armature_objects():
        # Set name displayed in list
        name = armature.data.name
        if name.startswith('Armature ('):
            name = armature.name + ' (' + name.replace('Armature (', '')[:-1] + ')'

        # 1. Will be returned by context.scene
        # 2. Will be shown in lists
        # 3. will be shown in the hover description (below description)
        choices.append((armature.name, name, armature.name))

    return choices


def get_armature_merge_list(self, context):
    choices = []
    current_armature = context.scene.merge_armature_into

    for armature in get_armature_objects():
        if armature.name != current_armature:
            # Set name displayed in list
            name = armature.data.name
            if name.startswith('Armature ('):
                name = armature.name + ' (' + name.replace('Armature (', '')[:-1] + ')'

            # 1. Will be returned by context.scene
            # 2. Will be shown in lists
            # 3. will be shown in the hover description (below description)
            choices.append((armature.name, name, armature.name))

    return choices


def get_bone_orientations(armature):
    x_cord = 0
    y_cord = 1
    z_cord = 2
    fbx = False
    return x_cord, y_cord, z_cord, fbx


def get_bones_head(self, context):
    return get_bones(names=['Head'])


def get_bones_eye_l(self, context):
    return get_bones(names=['Eye_L', 'EyeReturn_L'])


def get_bones_eye_r(self, context):
    return get_bones(names=['Eye_R', 'EyeReturn_R'])


def get_bones_merge(self, context):
    return get_bones(armature_name=bpy.context.scene.merge_armature_into)


# names - The first object will be the first one in the list. So the first one has to be the one that exists in the most models
def get_bones(names=None, armature_name=None, check_list=False):
    if not names:
        names = []
    if not armature_name:
        armature_name = bpy.context.scene.armature

    choices = []
    armature = get_armature(armature_name=armature_name)

    if not armature:
        return choices

    # print("")
    # print("START DEBUG UNICODE")
    # print("")
    for bone in armature.data.bones:
        # print(bone.name)
        try:
            # 1. Will be returned by context.scene
            # 2. Will be shown in lists
            # 3. will be shown in the hover description (below description)
            choices.append((bone.name, bone.name, bone.name))
        except UnicodeDecodeError:
            print("ERROR", bone.name)

    _sort_enum_choices_by_identifier_lower(choices)

    choices2 = []
    for name in names:
        if name in armature.data.bones and choices[0][0] != name:
            choices2.append((name, name, name))

    if not check_list:
        for choice in choices:
            choices2.append(choice)

    return choices2


def get_shapekeys_mouth_ah(self, context):
    return get_shapekeys(context, ['MTH A', 'Ah', 'A'], True, False, False)


def get_shapekeys_mouth_oh(self, context):
    return get_shapekeys(context, ['MTH U', 'Oh', 'O', 'Your'], True, False, False)


def get_shapekeys_mouth_ch(self, context):
    return get_shapekeys(context, ['MTH I', 'Glue', 'Ch', 'I', 'There'], True, False, False)


def get_shapekeys_eye_blink_l(self, context):
    return get_shapekeys(context, ['EYE Close L', 'Wink 2', 'Wink', 'Wink left', 'Wink Left', 'Blink (Left)', 'Blink', 'Basis'], False, False, False)


def get_shapekeys_eye_blink_r(self, context):
    return get_shapekeys(context, ['EYE Close R', 'Wink 2 right', 'Wink 2 Right', 'Wink right 2', 'Wink Right 2', 'Wink right', 'Wink Right', 'Blink (Right)', 'Basis'], False, False, False)


def get_shapekeys_eye_low_l(self, context):
    return get_shapekeys(context, ['Basis'], False, False, False)


def get_shapekeys_eye_low_r(self, context):
    return get_shapekeys(context, ['Basis'], False, False, False)


# names - The first object will be the first one in the list. So the first one has to be the one that exists in the most models
# no_basis - If this is true the Basis will not be available in the list
def get_shapekeys(context, names, is_mouth, no_basis, return_list):
    choices = []
    choices_simple = []
    meshes_list = get_meshes_objects(check=False)

    if meshes_list:
        if is_mouth:
            meshes = [get_objects().get(context.scene.mesh_name_viseme)]
        else:
            meshes = [get_objects().get(context.scene.mesh_name_eye)]
    else:
        return choices

    for mesh in meshes:
        if not mesh or not has_shapekeys(mesh):
            return choices

        for shapekey in mesh.data.shape_keys.key_blocks:
            name = shapekey.name
            if name in choices_simple:
                continue
            if no_basis and name == 'Basis':
                continue
            # 1. Will be returned by context.scene
            # 2. Will be shown in lists
            # 3. will be shown in the hover description (below description)
            choices.append((name, name, name))
            choices_simple.append(name)

    _sort_enum_choices_by_identifier_lower(choices)

    choices2 = []
    for name in names:
        if name in choices_simple and len(choices) > 1 and choices[0][0] != name:
            continue
        choices2.append((name, name, name))

    choices2.extend(choices)

    if return_list:
        shape_list = []
        for choice in choices2:
            shape_list.append(choice[0])
        return shape_list

    return choices2


def fix_armature_names(armature_name=None):
    if not armature_name:
        armature_name = bpy.context.scene.armature
    base_armature = get_armature(armature_name=bpy.context.scene.merge_armature_into)
    merge_armature = get_armature(armature_name=bpy.context.scene.merge_armature)

    # Armature should be named correctly (has to be at the end because of multiple armatures)
    armature = get_armature(armature_name=armature_name)
    armature.name = 'Armature'
    if not armature.data.name.startswith('Armature'):
        Translate.update_dictionary(armature.data.name)
        armature.data.name = 'Armature (' + Translate.translate(armature.data.name, add_space=True)[0] + ')'

    # Reset the armature lists
    try:
        bpy.context.scene.armature = armature.name
    except TypeError:
        pass

    try:
        if base_armature:
            bpy.context.scene.merge_armature_into = base_armature.name
    except TypeError:
        pass

    try:
        if merge_armature:
            bpy.context.scene.merge_armature = merge_armature.name
    except TypeError:
        pass


def get_meshes_objects(armature_name=None, mode=0, check=True, visible_only=False):
    context = bpy.context
    # Modes:
    # 0 = With armatures only
    # 1 = Top level only
    # 2 = All meshes
    # 3 = Selected only

    if not armature_name:
        armature = get_armature()
        if armature:
            armature_name = armature.name

    meshes = []
    
    for ob in get_objects():
            if ob is None:
                continue
            if ob.type != 'MESH':
                continue
                
            if mode == 0 or mode == 5: 
                if ob.parent:
                    if ob.parent.type == 'ARMATURE' and ob.parent.name == armature_name:
                        meshes.append(ob)
                    elif ob.parent.parent and ob.parent.parent.type == 'ARMATURE' and ob.parent.parent.name == armature_name:
                        meshes.append(ob) 

            elif mode == 1:
                if not ob.parent:
                    meshes.append(ob)

            elif mode == 2:
                meshes.append(ob)

            elif mode == 3:
                if ob.select_get():
                    meshes.append(ob)

    if visible_only:
        for mesh in meshes:
            if is_hidden(mesh):
                meshes.remove(mesh)

    # Check for broken meshes and delete them
    if check:
        current_active = context.view_layer.objects.active
        to_remove = []
        for mesh in meshes:
            selected = mesh.select_get()
            # print(mesh.name, mesh.users)
            set_active(mesh)

            if not context.view_layer.objects.active:
                to_remove.append(mesh)

            if not selected:
                select(mesh, False)

        for mesh in to_remove:
            print('DELETED CORRUPTED MESH:', mesh.name, mesh.users)
            meshes.remove(mesh)
            delete(mesh)

        if current_active:
            set_active(current_active)

    return meshes

def get_meshes_objects_for_export(armature_name=None, mode=0, check=True):
    context = bpy.context
    if not armature_name:
        armature = get_armature()
        if armature:
            armature_name = armature.name

    meshes = []
    
    for ob in get_objects():
        if ob is None or ob.type != 'MESH':
            continue
            
        # Only include visible meshes
        if is_hidden(ob):
            continue
            
        if mode == 0 or mode == 5: 
            if ob.parent:
                if ob.parent.type == 'ARMATURE' and ob.parent.name == armature_name:
                    meshes.append(ob)
                elif ob.parent.parent and ob.parent.parent.type == 'ARMATURE' and ob.parent.parent.name == armature_name:
                    meshes.append(ob)
        elif mode == 1:
            if not ob.parent:
                meshes.append(ob)
        elif mode == 2:
            meshes.append(ob)
        elif mode == 3:
            if ob.select_get():
                meshes.append(ob)

    return meshes

def join_meshes(armature_name=None, mode=0, apply_transformations=True, repair_shape_keys=True):
    # Modes:
    # 0 - Join all meshes
    # 1 - Join selected only
    context = bpy.context
    
    if not armature_name:
        armature_name = bpy.context.scene.armature

    # Get meshes to join
    meshes_to_join = get_meshes_objects(armature_name=armature_name, mode=3 if mode == 1 else 0)
    if not meshes_to_join:
        return None

    # Check if all meshes are single user
    for mesh in meshes_to_join:
        if mesh.data.users > 1:
            show_error(4, [t('JoinMeshes.error.not_single_user'),
                           t('JoinMeshes.error.make_single_user'),
                           t('JoinMeshes.error.make_single_user1'),
                           t('JoinMeshes.error.make_single_user2')])
            return None

    set_default_stage()
    unselect_all()

    if apply_transformations:
        apply_transforms(armature_name=armature_name)

    unselect_all()

    for mesh in meshes_to_join:
        set_active(mesh)
        
        for mod in mesh.modifiers:
            if mod.type == 'SUBSURF':
                mesh.modifiers.remove(mod)

        if mesh.data.uv_layers:
            mesh.data.uv_layers[0].name = 'UVMap'
            

    # Get the name of the active mesh in order to check if it was deleted later
    active_mesh_name = context.view_layer.objects.active.name

    # Join the meshes
    if bpy.ops.object.join.poll():
        bpy.ops.object.join()
    else:
        print('NO MESH COMBINED!')
        

    # Delete meshes that somehow weren't deleted. Both pre and post join mesh deletion methods are needed!
    for mesh in get_meshes_objects(armature_name=armature_name):
        if mesh.name == active_mesh_name:
            set_active(mesh)
        elif mesh.name in meshes_to_join:
            delete(mesh)
            print('DELETED', mesh.name, mesh.users)

    # Rename result to Body and correct modifiers
    mesh = context.view_layer.objects.active
    if mesh:
        # If its the only mesh in the armature left, rename it to Body
        if len(get_meshes_objects(armature_name=armature_name)) == 1:
            mesh.name = 'Body'
        mesh.parent_type = 'OBJECT'

        repair_mesh(mesh, armature_name)

        if repair_shape_keys:
            repair_shapekey_order(mesh.name)

    # Update the material list of the Material Combiner
    update_material_list()

    return mesh


def repair_mesh(mesh, armature_name):
    mesh.parent_type = 'OBJECT'

    # Remove duplicate armature modifiers
    mod_count = 0
    for mod in mesh.modifiers:
        mod.show_expanded = False
        if mod.type == 'ARMATURE':
            mod_count += 1
            if mod_count > 1:
                bpy.ops.object.modifier_remove(modifier=mod.name)
                continue
            mod.object = get_armature(armature_name=armature_name)
            mod.show_viewport = True

    # Add armature mod if there is none
    if mod_count == 0:
        mod = mesh.modifiers.new("Armature", 'ARMATURE')
        mod.object = get_armature(armature_name=armature_name)


def apply_transforms(armature_name=None):
    if not armature_name:
        armature_name = bpy.context.scene.armature
    armature = get_armature(armature_name=armature_name)

    # Apply transforms on armature
    unselect_all()
    set_active(armature)
    switch('OBJECT')
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Apply transforms of meshes
    for mesh in get_meshes_objects(armature_name=armature_name):
        unselect_all()
        set_active(mesh)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def apply_all_transforms():

    def apply_transforms_with_children(parent):
        unselect_all()
        set_active(parent)
        switch('OBJECT')
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        for child in parent.children:
            apply_transforms_with_children(child)

    for obj in get_objects():
        if not obj.parent:
            apply_transforms_with_children(obj)


def separate_by_materials(context, mesh):
    prepare_separation(mesh)

    utils.separateByMaterials(mesh)

    for ob in context.selected_objects:
        if ob.type == 'MESH':
            hide(ob, False)
            clean_shapekeys(ob)

    utils.clearUnusedMeshes()

    # Update the material list of the Material Combiner
    update_material_list()


def separate_by_loose_parts(context, mesh):
    prepare_separation(mesh)

    # Correctly put mesh together. This is done to prevent extremely small pieces.
    # This essentially does nothing but merges the extremely small parts together.
    remove_doubles(mesh, 0, save_shapes=True)

    utils.separateByMaterials(mesh)

    meshes = []
    for ob in context.selected_objects:
        if ob.type == 'MESH':
            hide(ob, False)
            meshes.append(ob)

    wm = bpy.context.window_manager
    current_step = 0
    wm.progress_begin(current_step, len(meshes))

    for mesh in meshes:
        unselect_all()
        set_active(mesh)
        bpy.ops.mesh.separate(type='LOOSE')

        meshes2 = []
        for ob in context.selected_objects:
            if ob.type == 'MESH':
                meshes2.append(ob)

        ## This crashes blender, but would be better
        # unselect_all()
        # for mesh2 in meshes2:
        #     if len(mesh2.data.vertices) <= 3:
        #         select(mesh2)
        #     elif bpy.ops.object.join.poll():
        #         bpy.ops.object.join()
        #         unselect_all()

        for mesh2 in meshes2:
            clean_shapekeys(mesh2)

        current_step += 1
        wm.progress_update(current_step)

    wm.progress_end()

    utils.clearUnusedMeshes()

    # Update the material list of the Material Combiner
    update_material_list()


def separate_by_shape_keys(context, mesh):
    prepare_separation(mesh)

    switch('EDIT')
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.select_all(action='DESELECT')

    switch('OBJECT')
    selected_count = 0
    max_count = 0
    if has_shapekeys(mesh):
        for kb in mesh.data.shape_keys.key_blocks:
            for i, (v0, v1) in enumerate(zip(kb.relative_key.data, kb.data)):
                max_count += 1
                if v0.co != v1.co:
                    mesh.data.vertices[i].select = True
                    selected_count += 1

    if not selected_count or selected_count == max_count:
        return False

    switch('EDIT')
    bpy.ops.mesh.select_all(action='INVERT')

    bpy.ops.mesh.separate(type='SELECTED')

    for ob in context.selected_objects:
        if ob.type == 'MESH':
            active_tmp = context.view_layer.objects.active
            if ob != active_tmp:
                print('not active', ob.name)
                ob.name = ob.name.replace('.001', '') + '.no_shapes'
                set_active(ob)
                bpy.ops.object.shape_key_remove(all=True)
                set_active(active_tmp)
                select(ob, False)
            else:
                print('active', ob.name)
                clean_shapekeys(ob)
                switch('OBJECT')

    utils.clearUnusedMeshes()

    # Update the material list of the Material Combiner
    update_material_list()
    return True


def prepare_separation(mesh):
    set_default_stage()
    unselect_all()

    # Remove Rigidbodies and joints
    if bpy.context.scene.remove_rigidbodies_joints:
        for obj in get_objects():
            if 'rigidbodies' in obj.name or 'joints' in obj.name:
                delete_hierarchy(obj)

    save_shapekey_order(mesh.name)
    set_active(mesh)

    for mod in mesh.modifiers:
        mod.show_expanded = False

    clean_material_names(mesh)


def clean_shapekeys(mesh):
    # Remove empty shapekeys
    if has_shapekeys(mesh):
        for kb in mesh.data.shape_keys.key_blocks:
            if can_remove_shapekey(kb):
                mesh.shape_key_remove(kb)
        if len(mesh.data.shape_keys.key_blocks) == 1:
            mesh.shape_key_remove(mesh.data.shape_keys.key_blocks[0])


def can_remove_shapekey(key_block):
    if 'mmd_' in key_block.name:
        return True
    if key_block.relative_key == key_block:
        return False  # Basis
    for v0, v1 in zip(key_block.relative_key.data, key_block.data):
        if v0.co != v1.co:
            return False
    return True


def save_shapekey_order(mesh_name):
    mesh = get_objects()[mesh_name]
    armature = get_armature()

    if not armature:
        return

    # Get current custom data
    custom_data = armature.get('CUSTOM')
    if not custom_data:
        # print('NEW DATA!')
        custom_data = {}

    # Create shapekey order
    shape_key_order = []
    if has_shapekeys(mesh):
        for index, shapekey in enumerate(mesh.data.shape_keys.key_blocks):
            shape_key_order.append(shapekey.name)

    # Check if there is already a shapekey order
    if custom_data.get('shape_key_order'):
        # print('SHAPEKEY ORDER ALREADY EXISTS!')
        # print(custom_data['shape_key_order'])
        old_len = len(custom_data.get('shape_key_order'))

        if type(shape_key_order) is str:
            old_len = len(shape_key_order.split(',,,'))

        if len(shape_key_order) <= old_len:
            # print('ABORT')
            return

    # Save order to custom data
    # print('SAVE NEW ORDER')
    custom_data['shape_key_order'] = shape_key_order

    # Save custom data in armature
    armature['CUSTOM'] = custom_data

    # print(armature.get('CUSTOM').get('shape_key_order'))


def repair_shapekey_order(mesh_name):
    # Get current custom data
    armature = get_armature()
    custom_data = armature.get('CUSTOM', {})

    # Extract shape keys from string, using an empty list as default
    shape_key_order = custom_data.get('shape_key_order', [])

    if not shape_key_order:
        custom_data['shape_key_order'] = []
        armature['CUSTOM'] = custom_data
    elif isinstance(shape_key_order, str):
        shape_key_order_temp = shape_key_order.split(',,,')
        custom_data['shape_key_order'] = shape_key_order_temp
        armature['CUSTOM'] = custom_data

    # Only call sort_shape_keys if shape_key_order is not empty
    if custom_data.get('shape_key_order'):
        sort_shape_keys(mesh_name, custom_data['shape_key_order'])



def update_shapekey_orders():
    for armature in get_armature_objects():
        shape_key_order_translated = []

        # Get current custom data
        custom_data = armature.get('CUSTOM')
        if not custom_data:
            continue
        order = custom_data.get('shape_key_order')
        if not order:
            continue

        if type(order) is str:
            shape_key_order_temp = order.split(',,,')
            order = []
            for shape_name in shape_key_order_temp:
                order.append(shape_name)

        # Get shape keys and translate them
        for shape_name in order:
            shape_key_order_translated.append(Translate.translate(shape_name, add_space=True, translating_shapes=True)[0])

        # print(armature.name, shape_key_order_translated)
        custom_data['shape_key_order'] = shape_key_order_translated
        armature['CUSTOM'] = custom_data


def sort_shape_keys(mesh_name, shape_key_order=None):
    mesh = get_objects().get(mesh_name)
    if not mesh or not has_shapekeys(mesh):
        return
    set_active(mesh)

    shape_key_order = shape_key_order or []

    order = [
        'Basis',
        'vrc.blink_left',
        'vrc.blink_right',
        'vrc.lowerlid_left',
        'vrc.lowerlid_right',
        'vrc.v_aa',
        'vrc.v_ch',
        'vrc.v_dd',
        'vrc.v_e',
        'vrc.v_ff',
        'vrc.v_ih',
        'vrc.v_kk',
        'vrc.v_nn',
        'vrc.v_oh',
        'vrc.v_ou',
        'vrc.v_pp',
        'vrc.v_rr',
        'vrc.v_sil',
        'vrc.v_ss',
        'vrc.v_th',
        'Basis Original'
    ]

    for shape in shape_key_order:
        if shape not in order:
            order.append(shape)

    wm = bpy.context.window_manager
    current_step = 0
    wm.progress_begin(current_step, len(order))

    i = 0
    for name in order:
        if name == 'Basis' and 'Basis' not in mesh.data.shape_keys.key_blocks:
            i += 1
            current_step += 1
            wm.progress_update(current_step)
            continue

        for index, shapekey in enumerate(mesh.data.shape_keys.key_blocks):
            if shapekey.name == name:

                mesh.active_shape_key_index = index
                new_index = i
                index_diff = (index - new_index)

                if new_index >= len(mesh.data.shape_keys.key_blocks):
                    bpy.ops.object.shape_key_move(type='BOTTOM')
                    break

                position_correct = False
                if 0 <= index_diff <= (new_index - 1):
                    while position_correct is False:
                        if mesh.active_shape_key_index != new_index:
                            bpy.ops.object.shape_key_move(type='UP')
                        else:
                            position_correct = True
                else:
                    if mesh.active_shape_key_index > new_index:
                        bpy.ops.object.shape_key_move(type='TOP')

                    position_correct = False
                    while position_correct is False:
                        if mesh.active_shape_key_index != new_index:
                            bpy.ops.object.shape_key_move(type='DOWN')
                        else:
                            position_correct = True

                i += 1
                break

        current_step += 1
        wm.progress_update(current_step)

    mesh.active_shape_key_index = 0

    wm.progress_end()


def delete_hierarchy(parent):
    unselect_all()
    to_delete = []

    def get_child_names(obj):
        for child in obj.children:
            to_delete.append(child)
            if child.children:
                get_child_names(child)

    get_child_names(parent)
    to_delete.append(parent)

    objs = bpy.data.objects
    for obj in to_delete:
        objs.remove(objs[obj.name], do_unlink=True)


def delete(obj):
    if obj.parent:
        for child in obj.children:
            child.parent = obj.parent

    objs = bpy.data.objects
    objs.remove(objs[obj.name], do_unlink=True)


def delete_bone_constraints(armature_name=None):
    if not armature_name:
        armature_name = bpy.context.scene.armature

    armature = get_armature(armature_name=armature_name)
    switch('POSE')

    for bone in armature.pose.bones:
        if len(bone.constraints) > 0:
            for constraint in bone.constraints:
                bone.constraints.remove(constraint)

    switch('EDIT')


def delete_zero_weight(armature_name=None, ignore=''):
    if not armature_name:
        armature_name = bpy.context.scene.armature

    armature = get_armature(armature_name=armature_name)
    switch('EDIT')

    bone_names_to_work_on = set([bone.name for bone in armature.data.edit_bones])

    bone_name_to_edit_bone = dict()
    for edit_bone in armature.data.edit_bones:
        bone_name_to_edit_bone[edit_bone.name] = edit_bone

    vertex_group_names_used = set()
    vertex_group_name_to_objects_having_same_named_vertex_group = dict()
    for objects in get_meshes_objects(armature_name=armature_name):
        vertex_group_id_to_vertex_group_name = dict()
        for vertex_group in objects.vertex_groups:
            vertex_group_id_to_vertex_group_name[vertex_group.index] = vertex_group.name
            if vertex_group.name not in vertex_group_name_to_objects_having_same_named_vertex_group:
                vertex_group_name_to_objects_having_same_named_vertex_group[vertex_group.name] = set()
            vertex_group_name_to_objects_having_same_named_vertex_group[vertex_group.name].add(objects)
        for vertex in objects.data.vertices:
            for group in vertex.groups:
                if group.weight > 0:
                    vertex_group_names_used.add(vertex_group_id_to_vertex_group_name.get(group.group))

    not_used_bone_names = bone_names_to_work_on - vertex_group_names_used

    count = 0
    keep_twists = bpy.context.scene.delete_zero_weight_keep_twists
    keep_empty_parents = bpy.context.scene.delete_zero_weight_keep_empty_parents
    skip_hidden_bones = bpy.context.scene.delete_zero_weight_skip_hidden_bones

    for bone_name in not_used_bone_names:
        bone = bone_name_to_edit_bone[bone_name]

        if skip_hidden_bones and bone.hide:
            continue

        if keep_twists and ("_twist" in bone_name.lower() or "Twist" in bone_name):
            continue


        if keep_empty_parents:
            found_non_empty_child = False
            if bone:
                for child in bone.children_recursive:
                    if child.name in vertex_group_names_used:
                        found_non_empty_child = True
                        break
            if found_non_empty_child:
                continue
        
        if not bpy.context.scene.keep_end_bones or not is_end_bone(bone_name, armature_name):
            if bone_name not in Bones.dont_delete_these_bones and 'Root_' not in bone_name and bone_name != ignore:
                armature.data.edit_bones.remove(bone)  # delete bone
                count += 1
                if bone_name in vertex_group_name_to_objects_having_same_named_vertex_group:
                    for objects in vertex_group_name_to_objects_having_same_named_vertex_group[bone_name]:  # delete vertex groups
                        vertex_group = objects.vertex_groups.get(bone_name)
                        if vertex_group is not None:
                            objects.vertex_groups.remove(vertex_group)

    return count


def remove_unused_objects():
    default_scene_objects = []
    
    for obj in get_objects():
        if obj.type in {'CAMERA', 'LAMP', 'LIGHT', 'MESH'} and is_default_object(obj):
            default_scene_objects.append(obj)

    if len(default_scene_objects) == 3:
        for obj in default_scene_objects:
            delete_hierarchy(obj)

def is_default_object(obj):
    # Check if the object is one of the default objects based on type
    if obj.type == 'CAMERA' and obj.data.name == 'Camera':
        return True
    elif obj.type == 'LAMP' and obj.data.name == 'Lamp':
        return True
    elif obj.type == 'LIGHT' and obj.data.name == 'Light':
        return True
    elif obj.type == 'MESH' and obj.data.name == 'Cube':
        return True
    return False


def is_end_bone(name, armature_name):
    armature = get_armature(armature_name=armature_name)
    end_bone = armature.data.edit_bones.get(name)
    if end_bone and end_bone.parent and len(end_bone.parent.children) == 1:
        return True
    return False


def correct_bone_positions(armature_name=None):
    if not armature_name:
        armature_name = bpy.context.scene.armature
    armature = get_armature(armature_name=armature_name)

    upper_chest = armature.data.edit_bones.get('Upper Chest')
    chest = armature.data.edit_bones.get('Chest')
    neck = armature.data.edit_bones.get('Neck')
    head = armature.data.edit_bones.get('Head')
    if chest and neck:
        if upper_chest and bpy.context.scene.keep_upper_chest:
            chest.tail = upper_chest.head
            upper_chest.tail = neck.head
        else:
            chest.tail = neck.head
    if neck and head:
        neck.tail = head.head

    if 'Left shoulder' in armature.data.edit_bones:
        if 'Left arm' in armature.data.edit_bones:
            if 'Left elbow' in armature.data.edit_bones:
                if 'Left wrist' in armature.data.edit_bones:
                    shoulder = armature.data.edit_bones.get('Left shoulder')
                    arm = armature.data.edit_bones.get('Left arm')
                    elbow = armature.data.edit_bones.get('Left elbow')
                    wrist = armature.data.edit_bones.get('Left wrist')
                    shoulder.tail = arm.head
                    arm.tail = elbow.head
                    elbow.tail = wrist.head

    if 'Right shoulder' in armature.data.edit_bones:
        if 'Right arm' in armature.data.edit_bones:
            if 'Right elbow' in armature.data.edit_bones:
                if 'Right wrist' in armature.data.edit_bones:
                    shoulder = armature.data.edit_bones.get('Right shoulder')
                    arm = armature.data.edit_bones.get('Right arm')
                    elbow = armature.data.edit_bones.get('Right elbow')
                    wrist = armature.data.edit_bones.get('Right wrist')
                    shoulder.tail = arm.head
                    arm.tail = elbow.head
                    elbow.tail = wrist.head

    if 'Left leg' in armature.data.edit_bones:
        if 'Left knee' in armature.data.edit_bones:
            if 'Left ankle' in armature.data.edit_bones:
                leg = armature.data.edit_bones.get('Left leg')
                knee = armature.data.edit_bones.get('Left knee')
                ankle = armature.data.edit_bones.get('Left ankle')

                if 'Left leg 2' in armature.data.edit_bones:
                    leg = armature.data.edit_bones.get('Left leg 2')

                leg.tail = knee.head
                knee.tail = ankle.head

    if 'Right leg' in armature.data.edit_bones:
        if 'Right knee' in armature.data.edit_bones:
            if 'Right ankle' in armature.data.edit_bones:
                leg = armature.data.edit_bones.get('Right leg')
                knee = armature.data.edit_bones.get('Right knee')
                ankle = armature.data.edit_bones.get('Right ankle')

                if 'Right leg 2' in armature.data.edit_bones:
                    leg = armature.data.edit_bones.get('Right leg 2')

                leg.tail = knee.head
                knee.tail = ankle.head


dpi_scale = 3
error = []
override = False


def show_error(scale, error_list, override_header=False):
    global override, dpi_scale, error
    override = override_header
    dpi_scale = scale

    if type(error_list) is str:
        error_list = error_list.split('\n')

    error = error_list

    header = t('ShowError.label')
    if override:
        header = error_list[0]

    ShowError.bl_label = header
    try:
        bpy.utils.register_class(ShowError)
    except ValueError:
        bpy.utils.unregister_class(ShowError)
        bpy.utils.register_class(ShowError)

    bpy.ops.cats_common.show_error('INVOKE_DEFAULT')

    print('')
    print('Report: Error')
    for line in error:
        print('    ' + line)


@register_wrap
class ShowError(bpy.types.Operator):
    bl_idname = 'cats_common.show_error'
    bl_label = t('ShowError.label')

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        dpi_value = Common.get_user_preferences().system.dpi
        return context.window_manager.invoke_props_dialog(self, width=int(dpi_value * dpi_scale))

    def draw(self, context):
        if not error or len(error) == 0:
            return

        if override and len(error) == 1:
            return

        layout = self.layout
        col = layout.column(align=True)

        first_line = False
        for i, line in enumerate(error):
            if i == 0 and override:
                continue
            if line == '':
                col.separator()
            else:
                row = col.row(align=True)
                row.scale_y = 0.85
                if not first_line:
                    row.label(text=line, icon='ERROR')
                    first_line = True
                else:
                    row.label(text=line, icon_value=Iconloader.preview_collections["custom_icons"]["empty"].icon_id)


def has_shapekeys(mesh_obj: Object) -> bool:
    return mesh_obj.data.shape_keys is not None


@lru_cache(maxsize=None)
def _get_shape_key_co(shape_key: ShapeKey) -> np.ndarray:
    return np.array([v.co for v in shape_key.data])


def remove_doubles(mesh_obj: Object, threshold: float, save_shapes: bool = True) -> int:
    if not isinstance(mesh_obj, Object):
        raise TypeError("mesh_obj must be an instance of Object")

    mesh = mesh_obj.data

    if not has_shapekeys(mesh_obj) or len(mesh.shape_keys.key_blocks) == 1:
        return 0

    pre_polygons = len(mesh.polygons)

    if save_shapes:
        vertex_selection = np.full(len(mesh.vertices), True, dtype=bool)
        cached_co_getter = lru_cache(maxsize=None)(_get_shape_key_co)
        for kb in mesh.shape_keys.key_blocks[1:]:
            relative_key = kb.relative_key
            if kb == relative_key:
                continue
            same = cached_co_getter(kb) == cached_co_getter(relative_key)
            vertex_not_moved_by_shape_key = np.all(same.reshape(-1, 3), axis=1)
            vertex_selection &= vertex_not_moved_by_shape_key
        del cached_co_getter

        if not vertex_selection.any():
            return 0

        if vertex_selection.all():
            save_shapes = False
        else:
            bpy.context.view_layer.objects.active = mesh_obj
            bpy.ops.object.mode_set(mode='EDIT')
            verts = list(bmesh.from_edit_mesh(mesh).verts)
            for v in verts:
                v.select = vertex_selection[v.index]
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.context.view_layer.update()
    else:
        bmesh.ops.select_all(bm, action='DESELECT')

    bm = bmesh.new()
    bm.from_mesh(mesh)
    if save_shapes:
        verts = [v for v in bm.verts if v.select]
    else:
        verts = bm.verts

    total_verts = len(verts)
    progress_steps = 100
    progress_step_size = total_verts // progress_steps
    progress = 0

    bmesh.ops.remove_doubles(bm, verts=verts, dist=threshold)

    while progress < total_verts:
        bm.select_flush(True)
        bpy.context.view_layer.update()
        bpy.context.window_manager.progress_update(progress / total_verts)
        progress += progress_step_size

    bm.to_mesh(mesh)

    return pre_polygons - len(mesh.polygons)


def get_tricount(obj):
    # Triangulates with Bmesh to avoid messing with the original geometry
    bmesh_mesh = bmesh.new()
    bmesh_mesh.from_mesh(obj.data)

    bmesh.ops.triangulate(bmesh_mesh, faces=bmesh_mesh.faces[:])
    return len(bmesh_mesh.faces)


def clean_material_names(mesh):
    for j, mat in enumerate(mesh.material_slots):
        if mat.name.endswith(('.0+', ' 0+')):
            mesh.active_material_index = j
            mesh.active_material.name = mat.name[:-len(mat.name.rstrip('0')) - 1]


def mix_weights(mesh, vg_from, vg_to, mix_strength=1.0, mix_mode='ADD', mix_set='ALL', delete_old_vg=True):
    """Mix the weights of two vertex groups on the mesh, optionally removing the vertex group named vg_from.
    This function uses the Vertex Weight Mix modifier to efficiently mix vertex group weights.
    """
    # Ensure the correct shape key is active
    mesh.active_shape_key_index = 0
    # Create the Vertex Weight Mix modifier
    mod = mesh.modifiers.new(name="VertexWeightMix_" + vg_from + "_into_" + vg_to, type='VERTEX_WEIGHT_MIX')
    mod.vertex_group_a = vg_to
    mod.vertex_group_b = vg_from
    mod.mix_mode = mix_mode
    mod.mix_set = mix_set  # Use 'ALL' to include all vertices
    mod.mask_constant = mix_strength  # Strength of the mix
    # Apply the modifier to the mesh
    # Depending on your Blender version, you may need to adjust how the modifier is applied.
    if bpy.ops.object.modifier_apply.poll():
        mesh.modifiers.active = mod
        bpy.ops.object.modifier_apply(modifier=mod.name)
    # Optionally remove the source vertex group
    if delete_old_vg:
        vg_from_group = mesh.vertex_groups.get(vg_from)
        if vg_from_group:
            mesh.vertex_groups.remove(vg_from_group)

    # Reset the active shape key index
    mesh.active_shape_key_index = 0


def get_user_preferences():
    return bpy.context.user_preferences if hasattr(bpy.context, 'user_preferences') else bpy.context.preferences


def has_shapekeys(mesh):
    if not hasattr(mesh.data, 'shape_keys'):
        return False
    return hasattr(mesh.data.shape_keys, 'key_blocks')


def ui_refresh():
    # A way to refresh the ui
    refreshed = False
    while not refreshed:
        if hasattr(bpy.data, 'window_managers'):
            for windowManager in bpy.data.window_managers:
                for window in windowManager.windows:
                    for area in window.screen.areas:
                        area.tag_redraw()
            refreshed = True
            # print('Refreshed UI')
        else:
            time.sleep(0.5)


def fix_zero_length_bones(armature: bpy.types.Object):
    if armature.mode != 'EDIT':
        return

    edit_bones = armature.data.edit_bones[:]

    for bone in edit_bones:
        length = (bone.head - bone.tail).length
        if length > 0.0001:
            continue

        head_rounded = [round(x, 4) for x in bone.head] 
        tail_rounded = [round(x, 4) for x in bone.tail]

        if head_rounded == tail_rounded:
            bone.tail += Vector((0, 0, 0.1))

def fix_bone_orientations(armature):
    # Connect all bones with their children if they have exactly one
    for bone in armature.data.edit_bones:
        if len(bone.children) == 1 and bone.name not in ['LeftEye', 'RightEye', 'Head', 'Hips']:
            p1 = bone.head
            p2 = bone.children[0].head
            dist = ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2 + (p2[2] - p1[2]) ** 2) ** (1/2)

            # Only connect them if the other bone is a certain distance away, otherwise blender will delete them
            if dist > 0.005:
                bone.tail = bone.children[0].head
                if bone.parent:
                    if len(bone.parent.children) == 1:  # if the bone's parent bone only has one child, connect the bones (Don't connect them all because that would mess up hand/finger bones)
                        bone.use_connect = True


def update_material_list(self=None, context=None):
    try:
        if hasattr(bpy.context.scene, 'smc_ob_data') and bpy.context.scene.smc_ob_data:
            bpy.ops.smc.refresh_ob_data()
    except AttributeError:
        print('Material Combiner not found')


def bake_mmd_colors(node_base_tex: ShaderNodeTexImage, node_mmd_shader: ShaderNodeGroup):
    """Bake the mmd ambient color and diffuse color into the base tex or return the combined color if there is no base
    tex. This process follows the same steps that the mmd_shader group node follows."""
    # Input names used by mmd_shader group node from the mmd_tools addon
    ambient_color_input_name = "Ambient Color"
    diffuse_color_input_name = "Diffuse Color"

    ambient_color_input = node_mmd_shader.inputs.get(ambient_color_input_name)

    if not ambient_color_input or ambient_color_input.type != 'RGBA':
        print(f"Could not find color input '{ambient_color_input_name}' in {node_mmd_shader}."
              f" Is it a correct mmd_shader group node?")
        # The mmd_shader node does not appear to be correct, abort
        return node_base_tex, None

    diffuse_color_input = node_mmd_shader.inputs.get(diffuse_color_input_name)

    if not diffuse_color_input or diffuse_color_input.type != 'RGBA':
        print(f"Could not find color input '{diffuse_color_input_name}' in {node_mmd_shader}."
              f" Is it a correct mmd_shader group node?")
        # The mmd_shader node does not appear to be correct, abort
        return node_base_tex, None

    # We assume that the Ambient Color and Diffuse Color inputs have not been modified following the initial import of
    # the mmd model into Blender, meaning that they are not linked to other nodes.
    # Colors in shader nodes only use RGB, so ignore the alpha channels
    ambient_color = np.array(ambient_color_input.default_value[:3])
    diffuse_color = np.array(diffuse_color_input.default_value[:3])

    # Add 0.6 times the Diffuse Color to the Ambient Color and clamp the result to the range [0,1]
    # This is the first step done inside the mmd_shader group node
    mmd_color = np.clip(ambient_color + diffuse_color * 0.6, 0, 1)

    # TODO: Create a 4x4 image of the colour instead to avoid issues where Blender colours are linear, but Unity colours
    #  could be linear or could be sRGB depending on the settings used and the shaders used.
    # If there's no image, we'll use a color instead
    if not node_base_tex or not node_base_tex.image:
        # Add alpha of 1 to the color to make it into RGBA because colors in shader nodes are RGBA, despite only RGB
        # being used.
        principled_base_color = np.append(mmd_color, 1)
        return None, principled_base_color
    else:
        # Multiply the base_tex by the combined diffuse and ambient color.
        base_tex_image = node_base_tex.image

        if not base_tex_image.pixels:
            # Image is not loaded
            return node_base_tex, None

        # There are other non-linear colorspaces, but they are more complicated and there are no clear conversions
        # because it looks like Blender uses OCIO for them. Typically, only linear colorspaces and sRGB are used, so we
        # are ignoring the other colorspaces for now.
        if base_tex_image.colorspace_settings.name == 'sRGB':
            # In shader nodes, the linear base_color would be multiplied by the sRGB image pixels, but we can only read
            # and write image pixels in scene linear colorspace.
            #
            # We have to convert base_color (linear) to appear in sRGB as it currently appears in linear. We can do this
            # by converting it to linear as if it was already sRGB.
            # The conversion from linear to sRGB is then cancelled out by being viewed in sRGB colorspace.
            #
            # Alternatively, you can look at it mathematically, since to convert linear pixels to how they would appear
            # if viewed in sRGB colorspace, the conversion is pretty close to RGB**2.4:
            # Given: sRGB(pixels) * color == sRGB(baked_pixels)
            # We can treat it as:
            #   pixels**2.4 * color == baked_pixels**2.4
            # to get:
            #   pixels * color**1/2.4 == baked_pixels
            # giving us both the input and output image pixels in linear colorspace
            # The following is color_scene_linear_to_srgb from node_color.h in the Blender source code, rewritten for
            # Python and numpy
            is_small_mask = mmd_color < 0.0031308
            small_rgb = mmd_color[is_small_mask]
            # 0 if less than 0, otherwise multiply by 12.92
            mmd_color[is_small_mask] = np.where(small_rgb < 0.0, 0, small_rgb * 12.92)

            # Invert is_small_mask in-place, new variable name for clarity
            is_large_mask = np.invert(is_small_mask, out=is_small_mask)
            large_rgb = mmd_color[is_large_mask]
            mmd_color[is_large_mask] = (large_rgb ** (1.0 / 2.4)) * 1.055 - 0.055

        # Read the image pixels into a numpy array
        pixels = np.empty(np.prod(base_tex_image.size) * 4, dtype=np.single)
        base_tex_image.pixels.foreach_get(pixels)

        # View as grouped into individual pixels, so we can easily multiply all pixels by the same amount
        pixels.shape = (-1, 4)

        # Multiply the RGB of all the pixels in-place, automatically broadcasting the basecolor array.
        # We are currently ignoring base tex fac, treating it as if it's always 1
        pixels[:, :3] *= np.asarray(mmd_color)

        # Create new image so as not to touch the old one.
        baked_image = bpy.data.images.new(base_tex_image.name + "MMDCatsBaked",
                                          width=base_tex_image.size[0],
                                          height=base_tex_image.size[1],
                                          alpha=True)
        baked_image.filepath = bpy.path.abspath("//" + base_tex_image.name + ".png")
        baked_image.file_format = 'PNG'
        # Set the colorspace to match the original image
        baked_image.colorspace_settings.name = base_tex_image.colorspace_settings.name
        # Replace the existing image in the node with the new, baked image

        expected_len = baked_image.size[0] * baked_image.size[1] * 4

        pixels = np.empty(np.prod(base_tex_image.size) * 4, dtype=np.single)
        base_tex_image.pixels.foreach_get(pixels)

        # Resize pixels to expected length
        pixels.resize(expected_len) 

        print(f"Pixels length: {len(pixels)}, Expected: {expected_len}")
        node_base_tex.image = baked_image

        # Write the image pixels to the image
        baked_image.pixels.foreach_set(pixels)
        # Save the image to file if possible
        if bpy.data.is_saved:
            node_base_tex.image.save()
        return node_base_tex, None


def add_principled_shader(mesh: Object, bake_mmd=True):
    # Blender's FBX exporter only exports material properties when a Principled BSDF shader is used.
    # This adds a Principled BSDF shader and material output node in order for Unity to automatically detect exported
    # material properties.
    # Note that Unity's support for material properties from Blender exported FBX files is limited without additional
    # Unity scripts, for Blender exported FBX, Unity uses CreateFromStandardMaterial in:
    # https://github.com/Unity-Technologies/UnityCsReference/blob/master/Modules/AssetPipelineEditor/AssetPostprocessors/FBXMaterialDescriptionPreprocessor.cs

    # Positions to place Cats specific nodes, this typically puts the nodes down and to the right of existing nodes
    principled_shader_pos = (501, -500)
    output_shader_pos = (801, -500)
    # Labels used to identify Cats specific nodes
    principled_shader_label = "Cats Export Shader"
    output_shader_label = "Cats Export"
    # Node names and labels used by Materials created when importing an MMD model
    mmd_base_tex_name = "mmd_base_tex"
    mmd_base_tex_label = "MainTexture"
    mmd_shader_name = "mmd_shader"
    # Node types. These are Blender defined constants
    principled_bsdf_idname = "ShaderNodeBsdfPrincipled"
    material_output_idname = "ShaderNodeOutputMaterial"
    image_texture_idname = "ShaderNodeTexImage"
    group_idname = "ShaderNodeGroup"

    for mat_slot in mesh.material_slots:
        mat = mat_slot.material
        if mat and mat.node_tree:
            node_tree = mat.node_tree
            nodes = node_tree.nodes
            node_base_tex = nodes.get(mmd_base_tex_name)
            if node_base_tex and node_base_tex.bl_idname != image_texture_idname:
                # If for some reason it's not an Image Texture node, we'll try and get the node by its label instead
                node_base_tex = None
            found_image_texture_nodes = []
            cats_principled_bsdf = None
            cats_material_output = None

            # Check if the new nodes should be added and to which image node they should be linked to
            # Remove any extra Material Output nodes that aren't the Cats one
            # If there is more than one Material Output node or Principled BSDF node with the Cats label, remove
            # all but the first found.
            for node in nodes:
                if node.bl_idname == principled_bsdf_idname and node.label == principled_shader_label:
                    if cats_principled_bsdf:
                        # Remove any extra principled bsdf nodes with the label
                        nodes.remove(node)
                    else:
                        cats_principled_bsdf = node
                elif node.bl_idname == material_output_idname:
                    if node.label == output_shader_label:
                        if cats_material_output:
                            # Remove any extra material output nodes with the label
                            nodes.remove(node)
                        else:
                            cats_material_output = node
                    else:
                        # Remove any extra Material Output nodes so that blender doesn't get confused on which to use
                        nodes.remove(node)
                elif not node_base_tex and node.bl_idname == image_texture_idname:
                    # If we couldn't find the mmd_base_tex node by name initially, we'll try to find it by its expected
                    # label instead.
                    # Otherwise, we'll only pick an image texture node if there's only one.
                    if node.label == mmd_base_tex_label:
                        node_base_tex = node
                    else:
                        found_image_texture_nodes.append(node)

            # If the Cats nodes weren't found, they need to be added
            if not cats_principled_bsdf or not cats_material_output:
                node_mmd_shader = nodes.get(mmd_shader_name)

                # If there's no mmd texture, but there was only one image texture node, we'll use that one image texture
                # node.
                if not node_base_tex:
                    if len(found_image_texture_nodes) == 1:
                        node_base_tex = found_image_texture_nodes[0]

                # If there is an mmd_shader group node, copy how it combines the Ambient Color, Diffuse Color and
                # Base Tex, and bake the result into a single texture (or color if there is no Base Tex) that can be
                # used as the Base Color in the Principled BSDF shader node.
                if node_mmd_shader and node_mmd_shader.bl_idname == group_idname and bake_mmd:
                    node_base_tex, principled_base_color = bake_mmd_colors(node_base_tex, node_mmd_shader)
                else:
                    principled_base_color = None

                # Create Principled BSDF node if it doesn't exist
                if not cats_principled_bsdf:
                    cats_principled_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
                cats_principled_bsdf.label = principled_shader_label
                cats_principled_bsdf.location = principled_shader_pos
                cats_principled_bsdf.inputs["Specular IOR Level"].default_value = 0
                cats_principled_bsdf.inputs["Roughness"].default_value = 0
                cats_principled_bsdf.inputs["Sheen Tint"].default_value = (1.0, 1.0, 1.0, 1.0)
                cats_principled_bsdf.inputs["Coat Roughness"].default_value = 0
                cats_principled_bsdf.inputs["IOR"].default_value = 0

                # Create Material Output node if it doesn't exist
                if not cats_material_output:
                    cats_material_output = nodes.new(type="ShaderNodeOutputMaterial")
                cats_material_output.label = output_shader_label
                cats_material_output.location = output_shader_pos

                # Link base tex image texture node's color output to the principled BSDF node's Base Color input or set
                # the Base Color input's default_value if there is no node to link
                if node_base_tex and node_base_tex.image:
                    node_tree.links.new(node_base_tex.outputs["Color"], cats_principled_bsdf.inputs["Base Color"])
                elif principled_base_color is not None:
                    cats_principled_bsdf.inputs["Base Color"].default_value = principled_base_color
                # Link principled BSDF node's output to the material output
                node_tree.links.new(cats_principled_bsdf.outputs["BSDF"], cats_material_output.inputs["Surface"])
                
def fix_twist_bones(mesh, bones_to_delete):
    # This will fix MMD twist bones

    for bone_type in ['Hand', 'Arm']:
        for suffix in ['L', 'R']:
            prefix = 'Left' if suffix == 'L' else 'Right'
            bone_parent_name = prefix + ' ' + ('elbow' if bone_type == 'Hand' else 'arm')

            vg_twist = mesh.vertex_groups.get(bone_type + 'Twist_' + suffix)
            vg_parent = mesh.vertex_groups.get(bone_parent_name)

            if not vg_twist:
                print('1. no ' + bone_type + 'Twist_' + suffix)
                continue
            if not vg_parent:
                print('2. no ' + bone_parent_name)
                vg_parent = mesh.vertex_groups.new(name=bone_parent_name)

            vg_twist1_name = bone_type + 'Twist1_' + suffix
            vg_twist2_name = bone_type + 'Twist2_' + suffix
            vg_twist3_name = bone_type + 'Twist3_' + suffix
            vg_twist1 = bool(mesh.vertex_groups.get(vg_twist1_name))
            vg_twist2 = bool(mesh.vertex_groups.get(vg_twist2_name))
            vg_twist3 = bool(mesh.vertex_groups.get(vg_twist3_name))

            vg_twist_name = vg_twist.name
            vg_parent_name = vg_parent.name

            mix_weights(mesh, vg_twist_name, vg_parent_name, mix_strength=0.2, delete_old_vg=False)
            mix_weights(mesh, vg_twist_name, vg_twist_name, mix_strength=0.2, mix_mode='SUB', delete_old_vg=False)

            if vg_twist1:
                bones_to_delete.append(vg_twist1_name)
                mix_weights(mesh, vg_twist1_name, vg_twist_name, mix_strength=0.25, delete_old_vg=False)
                mix_weights(mesh, vg_twist1_name, vg_parent_name, mix_strength=0.75)

            if vg_twist2:
                bones_to_delete.append(vg_twist2_name)
                mix_weights(mesh, vg_twist2_name, vg_twist_name, mix_strength=0.5, delete_old_vg=False)
                mix_weights(mesh, vg_twist2_name, vg_parent_name, mix_strength=0.5)

            if vg_twist3:
                bones_to_delete.append(vg_twist3_name)
                mix_weights(mesh, vg_twist3_name, vg_twist_name, mix_strength=0.75, delete_old_vg=False)
                mix_weights(mesh, vg_twist3_name, vg_parent_name, mix_strength=0.25)


def fix_twist_bone_names(armature):
    # This will fix MMD twist bone names after the vertex groups have been fixed
    for bone_type in ['Hand', 'Arm']:
        for suffix in ['L', 'R']:
            bone_twist = armature.data.edit_bones.get(bone_type + 'Twist_' + suffix)
            if bone_twist:
                bone_twist.name = 'z' + bone_twist.name


"""
HTML <-> text conversions.
http://stackoverflow.com/questions/328356/extracting-text-from-html-file-using-python
"""


class _HTMLToText(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self._buf = []
        self.hide_output = False

    def handle_starttag(self, tag, attrs):
        if tag in ('p', 'br') and not self.hide_output:
            self._buf.append('\n')
        elif tag in ('script', 'style'):
            self.hide_output = True

    def handle_startendtag(self, tag, attrs):
        if tag == 'br':
            self._buf.append('\n')

    def handle_endtag(self, tag):
        if tag == 'p':
            self._buf.append('\n')
        elif tag in ('script', 'style'):
            self.hide_output = False

    def handle_data(self, text):
        if text and not self.hide_output:
            self._buf.append(re.sub(r'\s+', ' ', text))

    def handle_entityref(self, name):
        if name in name2codepoint and not self.hide_output:
            c = chr(name2codepoint[name])
            self._buf.append(c)

    def handle_charref(self, name):
        if not self.hide_output:
            n = int(name[1:], 16) if name.startswith('x') else int(name)
            self._buf.append(chr(n))

    def get_text(self):
        return re.sub(r' +', ' ', ''.join(self._buf))


def html_to_text(html):
    """
    Given a piece of HTML, return the plain text it contains.
    This handles entities and char refs, but not javascript and stylesheets.
    """
    parser = _HTMLToText()
    try:
        parser.feed(html)
        parser.close()
    except:  # HTMLParseError: No good replacement?
        pass
    return parser.get_text()


# Default sorting for dynamic EnumProperty items
def _sort_enum_choices_by_identifier_lower(choices, in_place=True):
    """Sort a list of enum choices (items) by the lowercase of their identifier.

    Sorting is performed in-place by default, but can be changed by setting in_place=False.

    Returns the sorted list of enum choices."""

    def identifier_lower(choice):
        return choice[0].lower()

    if in_place:
        choices.sort(key=identifier_lower)
    else:
        choices = sorted(choices, key=identifier_lower)
    return choices


# Identifier to indicate that an EnumProperty is empty
# This is the default identifier used when a wrapped items function returns an empty list
# This identifier needs to be something that should never normally be used, so as to avoid the possibility of
# conflicting with an enum value that exists.
_empty_enum_identifier = 'Cats_empty_enum_identifier'


def _ensure_enum_choices_not_empty(choices, in_place=True):
    if not in_place:
        choices = choices.copy()

    num_choices = len(choices)
    if num_choices == 0:
        # An EnumProperty should always have at least one choice since enum properties work based on indices. If there
        # aren't any choices, Blender falls back to '' as the returned value (the identifier), but choices that have ''
        # as the identifier (or any other falsey value in the case of trying to use a subclass of str) get ignored for
        # some reason, so we have to use a different identifier.
        # format is (identifier, name, description)
        choices.append((_empty_enum_identifier, 'None', '(auto-generated)'))

    return choices


# Cache used to ensure that all strings used by an EnumProperty maintain a reference in Python
# Dict of {str: set(str)} where the keys are property paths and the values are sets of strings being cached
_enum_string_cache = {}


# Note: Assumes all properties belong to a scene and therefore only one instance of each property_path will exist at a
#       time due to the fact that only one scene is active at a time.
# Note: A CollectionProperty containing an EnumProperty will result in strings being left in the cache when elements in
#       the CollectionProperty get deleted.
#       These have a property_path like 'my_collection_prop[<index>].my_enum_prop' so if the number of indices decreases
#       then some strings will get left in the cache.
def _ensure_python_references(choices, property_path, in_place=True):
    # Blender docs for EnumProperty:
    #   "There is a known bug with using a callback, Python must keep a reference to the strings returned by the callback
    #   or Blender will misbehave or even crash."
    # This issue is much more visible in UI if you use row.props_enum(<property owner>, <property name>) instead of
    # row.prop(<property owner>, <property name>) with an EnumProperty
    # We'll make sure Python has its own references by interning all the strings and then putting them in a cache. Both
    # steps are necessary as each step only covers some cases where the issue appears.
    new_cache = set()

    def keep_string_reference(element):
        if isinstance(element, str):
            element = intern(element)
            new_cache.add(element)
        return element

    if in_place:
        for i, choice in enumerate(choices):
            choices[i] = tuple(map(keep_string_reference, choice))
    else:
        choices = [tuple(map(keep_string_reference, choice)) for choice in choices]

    # When updating the cache, it's important that we don't temporarily remove any strings that are still in use,
    # because UI may still be referencing and using those strings during the very brief time window where we've removed
    # them in preparation of updating the cache
    object_name_cache = _enum_string_cache.setdefault(property_path, set())
    # Add all the new values
    object_name_cache.update(new_cache)
    # Remove any values no longer being used
    object_name_cache.intersection_update(new_cache)
    return choices


# Keeps track of whether an enum property for a specific scene is scheduled to have its current choice fixed because
# the current choice is invalid.
# This is only used when the current choice is detected as being invalid while drawing UI, since UI drawing code cannot
# modify properties.
# Dictionary of {str: set(str)} where the keys are the scene name and the set elements are the property paths to be
# fixed
_enum_choice_fix_scheduled = {}


# Check for, and fix out of bounds enum choices, settings the index to the last choice and adding temporary duplicate
# choices so the index remains within the bounds for this call
def _fix_out_of_bounds_enum_choices(property_holder, scene, choices, property_name, property_path, in_place=True):
    """Check for and fix an EnumProperty if its index is out of bounds.

    If it isn't possible to change the index immediately, because this is being called as part of a UI drawing method,
    a task to change the active choice will be scheduled to run as soon as possible.

    Adds duplicates of the last choice to 'choices' to prevent warnings until the invalid choices are fixed.

    property_holder is the holder of the property, in an EnumProperty's items function, this is the 'self' argument

    scene is the scene that owns the property, either directly or held in a PropertyGroup or PropertyCollection. It must
    be the .id_data of the property.

    choices is the list of choices returned by the EnumProperty's items function.

    property_name is the name of the EnumProperty on the property_holder to be checked against whether the choices are
    valid.

    property_path is the full path from the owner of the EnumProperty (scene) to the EnumProperty itself. This can be
    retrieved with property_holder.path_from_id(property_name).

    By default, the passed in 'choices' argument is modified, this can be disabled by setting in_place=False.

    Returns 'choices' with enough extra elements to avoid warnings of the property's index being out of bounds."""

    if not in_place:
        choices = choices.copy()

    num_choices = len(choices)

    # Getting property_holder.property_name isn't possible since it will cause infinite recursion, but we can get the
    # index without issue
    current_choice_index = property_holder.get(property_name)
    # If the property is not yet initialised, it should get set to a valid index automatically, so we only care
    # if it has already been initialised
    is_initialised = current_choice_index is not None
    if is_initialised and current_choice_index >= num_choices:
        # If the index is out of bounds, the last choice is suitable
        replacement_idx = num_choices - 1
        replacement_choice = choices[replacement_idx]

        # Setting the current choice index won't affect the current process of getting the property value, e.g.
        # if current_choice_index was 5, setting scene[property_name] will have no affect until attempting to
        # get the property a second time.
        # What we can do is temporarily add duplicates of the replacement choice until there is a choice at the current,
        # invalid index.
        # Adding extra choices will prevent the console from being spammed with warnings about no enum existing for the
        # current, invalid index.
        # Note that Blender 2.79 would return the first choice when the index is out of bounds while newer versions
        # return '', so this is slightly different behaviour.
        num_extra_to_add = current_choice_index - num_choices + 1
        # print(f"Current index of {property_name} is {current_choice_index}, but there are only {num_choices} values. Temporarily adding {num_extra_to_add} extra choices")
        extra_choices = [replacement_choice, ] * num_extra_to_add
        choices.extend(extra_choices)

        try:
            # If possible, set the current choice index to a valid one, this will raise an Attribute error if called
            # when drawing UI.
            property_holder[property_name] = replacement_idx
            # print(f"Detected '{property_path}' enum in '{scene.name}' with an invalid value, it has been fixed automatically")
        except AttributeError:
            # bpy.app.timers is 2.80+
            # For older Blender versions, it is possible to use a Thread to run the task until it works, but this
            # would result in EnumProperty update functions being called from a separate Thread which does not
            # sound like a good idea. It also might not be safe in general to get a scene and update one if its
            # properties from a separate Thread, e.g., what if the scene is deleted in the time between getting the
            # scene and updating the property's value?
            # Without the scheduled task on 2.79, if the index is out of bounds, the temporary duplicates will
            # be added every time the items function is called, until the EnumProperty is updated or retrieved
            # outside of UI drawing. This causes the temporary duplicates to be visible in the UI. Though, selecting
            # any of the temporary duplicates poses no problem as it causes the property to be updated outside of UI
            # drawing, thus fixing the out-of-bounds index and causing the temporary duplicates to disappear.
            # No modification is allowed when called as part of drawing UI, so we must schedule a task instead
            # First check if a fix has not already been scheduled, otherwise around 4 or 5 tasks could get scheduled
            # before the first one fixes the invalid choice
            scene_name = scene.name
            # _enum_choice_fix_scheduled is a global variable
            scheduled_property_set = _enum_choice_fix_scheduled.setdefault(scene_name, set())
            if property_path not in scheduled_property_set:
                replacement_identifier = replacement_choice[0]

                scheduled_property_set.add(property_path)

                # Closure task to fix the property
                def fix_out_of_bounds_enum_choice_task():
                    scene_by_name = bpy.data.scenes.get(scene_name)
                    # It's unlikely, but it is possible that the scene could have been deleted or renamed by the
                    # time the task executes. If it was renamed, another task would end up getting scheduled with
                    # the new name, so no problems there.
                    if scene_by_name:
                        # False argument to not coerce into a Python object (the value of the property) and instead
                        # return the prop itself
                        prop = scene_by_name.path_resolve(property_path, False)
                        # .id_data is the owner of the property, the scene in this case, and .data is the holder of
                        # the property
                        prop_holder = prop.data
                        # Setting the index
                        #   prop_holder[property_name] = replacement_idx
                        # doesn't cause UI to update the list of items.
                        # However, setting the property itself does, and since this is scheduled and called
                        # separately, there's no issue of causing infinite recursion.
                        # This will result in fix_invalid_enum_choices getting called again, but that will only fix
                        # the index and not cause the UI to update.
                        # Equivalent to: scene_by_name.property = replacement_identifier
                        setattr(prop_holder, property_name, replacement_identifier)
                        # print(f"Fixed '{property_path}' EnumProperty in '{scene_name}'")
                    else:
                        print("An EnumProperty fix was scheduled to set '{}.{}' to '{}', but the scene '{}' could not be found."
                              .format(scene_name, property_path, replacement_identifier, scene_name))
                    scheduled_property_set.remove(property_path)
                    # Returning None indicates that the timer should be removed after being executed; here for
                    # clarity.
                    return None

                # Schedule the task to immediately execute when possible (this will be after UI drawing has
                # finished)
                bpy.app.timers.register(fix_out_of_bounds_enum_choice_task)
                # print(f"Detected '{property_path}' enum in '{scene_name}' with an invalid value during UI drawing, a fix has been scheduled")

    return choices


def is_enum_empty(string):
    """Returns True only if the tested string is the string that signifies that an EnumProperty is empty.

    Returns False in all other cases."""
    return _empty_enum_identifier == string


# This function isn't needed since you can 'not is_enum_empty(string)', but is included for code clarity and readability
def is_enum_non_empty(string):
    """Returns False only if the tested string is not the string that signifies that an EnumProperty is empty.

    Returns True in all other cases."""
    return _empty_enum_identifier != string


def wrap_dynamic_enum_items(items_func, property_name, sort=True, in_place=True, is_holder=True):
    """Wrap an EnumProperty items function to automatically fix the property when it goes out of bounds of the items list.
    Automatically adds at least one choice if the items function returns an empty list.
    By default, sorts the items by the lowercase of the identifiers, this can be disabled by setting sort=False.
    Interns and caches all strings in the items to avoid a known Blender UI bug.
    Only works for properties whose owner is a scene.
    By setting is_holder=false, the fix for out of bounds values will be disabled."""
    def wrapped_items_func(self, context):
        nonlocal in_place
        items = items_func(self, context)
        if sort:
            items = _sort_enum_choices_by_identifier_lower(items, in_place=in_place)
            if not in_place:
                # Sorting has already created a new list in this case, so the rest can be done in place
                in_place = True
        items = _ensure_enum_choices_not_empty(items, in_place=in_place)
        property_path = self.path_from_id(property_name) if is_holder else property_name
        # If ensuring the list wasn't empty wasn't done in place, then a new list has been created and the rest can
        # be done in place
        items = _ensure_python_references(items, property_path)
        if is_holder:
            return _fix_out_of_bounds_enum_choices(self, context.scene, items, property_name, property_path)
        else:
            return items

    return wrapped_items_func
    
if bpy.app.version >= (3, 2):
    # Passing in context_override as a positional-only argument is deprecated as of Blender 3.2, replaced with
    # Context.temp_override
    def op_override(operator, context_override: dict[str, Any], context: Optional[bpy.types.Context] = None,
                    execution_context: Optional[str] = None,
                    undo: Optional[bool] = None, **operator_args) -> set[str]:
        """Call an operator with a context override"""
        args = []
        if execution_context is not None:
            args.append(execution_context)
        if undo is not None:
            args.append(undo)

        if context is None:
            context = bpy.context
        with context.temp_override(**context_override):
            return operator(*args, **operator_args)
else:
    def op_override(operator, context_override: Dict[str, Any], context: Optional[bpy.types.Context] = None,
                    execution_context: Optional[str] = None,
                    undo: Optional[bool] = None, **operator_args) -> Set[str]:
        """Call an operator with a context override"""
        if context is not None:
            context_base = context.copy()
            context_base.update(context_override)
            context_override = context_base
        args = [context_override]
        if execution_context is not None:
            args.append(execution_context)
        if undo is not None:
            args.append(undo)

        return operator(*args, **operator_args)

def set_material_shading():
    # Set shading to 3D view
    for area in bpy.context.screen.areas:  # iterate through areas in current screen
        if area.type == 'VIEW_3D':
            for space in area.spaces:  # iterate through spaces in current VIEW_3D area
                if space.type == 'VIEW_3D':  # check if space is a 3D view
                    space.shading.type = 'MATERIAL'  # set the viewport shading to rendered
                    space.shading.studio_light = 'forest.exr'
                    space.shading.studiolight_rotate_z = 0.0
                    space.shading.studiolight_background_alpha = 0.0
                    if bpy.app.version >= (2, 82):
                        space.shading.render_pass = 'COMBINED'

def clear_unused_data():
    """
    Clear unused data blocks to improve memory usage.
    """
    # Purge orphan data blocks
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
