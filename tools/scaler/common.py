# MIT License
#
# Immersive Scaler, integrated into Cats as a first-party feature.
# Originally based on the standalone Immersive Scaler add on by pager
# (https://github.com/teamneoneko/immersive_scaler). Reworked to reuse Cats'
# own armature/mesh/pose helpers and to target Blender 5.1+.

import bpy
from contextlib import contextmanager
from .. import common as Common


def obj_in_scene(obj):
    for o in bpy.context.view_layer.objects:
        if o is obj:
            return True
    return False


def get_body_meshes(arm=None):
    """Meshes belonging to the avatar armature that are present in the current scene."""
    if not arm:
        arm = Common.get_armature()
    if not arm:
        return []
    return [m for m in Common.get_meshes_objects(armature_name=arm.name, check=False)
            if obj_in_scene(m)]


@contextmanager
def temp_ensure_enabled(*objs):
    scene = bpy.context.scene

    # Remove any duplicates from the list of objects
    unique_objs = []
    found_objs = set()
    for obj in objs:
        if obj is not None and obj not in found_objs:
            unique_objs.append(obj)
            found_objs.add(obj)

    old_hide_viewports = [obj.hide_viewport for obj in unique_objs]

    added_to_collections = []
    try:
        objects = scene.collection.objects
        for obj in unique_objs:
            obj.hide_viewport = False
            if obj.name not in objects:
                objects.link(obj)
                added_to_collections.append(True)
            else:
                added_to_collections.append(False)
        yield
    finally:
        for obj, old_hide_viewport, added_to_collection in zip(
            unique_objs, old_hide_viewports, added_to_collections
        ):
            try:
                # While we could do `if old_hide_viewport: obj.hide_viewport = True`, this wouldn't always check that
                # obj is still a valid reference.
                obj.hide_viewport = old_hide_viewport

                if added_to_collection:
                    try:
                        objects = scene.collection.objects
                        if obj.name in objects:
                            objects.unlink(obj)
                    except ReferenceError:
                        # scene has been deleted
                        pass
            except ReferenceError:
                # obj has been deleted
                pass


class ArmatureOperator(bpy.types.Operator):
    """Base operator for scaler tools. Resolves the Cats armature and its meshes, makes
    sure they're enabled for the duration of the operation, and runs in OBJECT mode."""

    @classmethod
    def poll(cls, context):
        if Common.get_armature() is None:
            cls.poll_message_set(
                "Armature not found. Select an armature as active or set one in the Cats armature dropdown."
            )
            return False
        return True

    def execute_main(self, context, arm, meshes):
        # To be overridden in subclasses
        return {'FINISHED'}

    def execute(self, context):
        arm = Common.get_armature()
        meshes = get_body_meshes(arm)

        if context.mode != 'OBJECT':
            # Make sure we leave any EDIT modes so that data from edit modes is up-to-date.
            bpy.ops.object.mode_set(mode='OBJECT')

        with temp_ensure_enabled(arm, *meshes):
            return self.execute_main(context, arm, meshes)
