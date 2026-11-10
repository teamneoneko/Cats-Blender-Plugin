# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

import logging
import math
from typing import Optional

import bpy
from mathutils import Matrix, Vector

from ..bpyutils import FnContext, Props
from ..compat import action_compat


class FnCamera:
    @staticmethod
    def find_root(obj: bpy.types.Object) -> Optional[bpy.types.Object]:
        if obj is None:
            return None
        if FnCamera.is_mmd_camera_root(obj):
            return obj
        if obj.parent is not None and FnCamera.is_mmd_camera_root(obj.parent):
            return obj.parent
        return None

    @staticmethod
    def is_mmd_camera(obj: bpy.types.Object) -> bool:
        return obj.type == "CAMERA" and FnCamera.find_root(obj.parent) is not None

    @staticmethod
    def is_mmd_camera_root(obj: bpy.types.Object) -> bool:
        return obj.type == "EMPTY" and obj.mmd_type == "CAMERA"

    @staticmethod
    def add_drivers(camera_object: bpy.types.Object):
        def __add_driver(id_data: bpy.types.ID, data_path: str, expression: str, index: int = -1):
            d = id_data.driver_add(data_path, index).driver
            d.type = "SCRIPTED"
            if "$empty_distance" in expression:
                v = d.variables.new()
                v.name = "empty_distance"
                v.type = "TRANSFORMS"
                v.targets[0].id = camera_object
                v.targets[0].transform_type = "LOC_Y"
                v.targets[0].transform_space = "LOCAL_SPACE"
                expression = expression.replace("$empty_distance", v.name)
            if "$is_perspective" in expression:
                v = d.variables.new()
                v.name = "is_perspective"
                v.type = "SINGLE_PROP"
                v.targets[0].id_type = "OBJECT"
                v.targets[0].id = camera_object.parent
                v.targets[0].data_path = "mmd_camera.is_perspective"
                expression = expression.replace("$is_perspective", v.name)
            if "$angle" in expression:
                v = d.variables.new()
                v.name = "angle"
                v.type = "SINGLE_PROP"
                v.targets[0].id_type = "OBJECT"
                v.targets[0].id = camera_object.parent
                v.targets[0].data_path = "mmd_camera.angle"
                expression = expression.replace("$angle", v.name)
            if "$sensor_height" in expression:
                # Use fixed sensor_height instead of dynamic reference.
                # When controlled by MMD angle, sensor_height shouldn't change.
                # This avoids unnecessary dependency cycles.
                # Reference: https://github.com/MMD-Blender/blender_mmd_tools/issues/227
                current_sensor_height = camera_object.data.sensor_height
                expression = expression.replace("$sensor_height", str(current_sensor_height))

            d.expression = expression

        __add_driver(camera_object.data, "ortho_scale", "25*abs($empty_distance)/45")
        __add_driver(camera_object, "rotation_euler", "pi if $is_perspective == False and $empty_distance > 1e-5 else 0", index=1)
        __add_driver(camera_object.data, "type", "not $is_perspective")
        __add_driver(camera_object.data, "lens", "$sensor_height/tan($angle/2)/2")

    @staticmethod
    def remove_drivers(camera_object: bpy.types.Object):
        camera_object.data.driver_remove("ortho_scale")
        camera_object.driver_remove("rotation_euler")
        camera_object.data.driver_remove("type")
        camera_object.data.driver_remove("lens")


class MigrationFnCamera:
    @staticmethod
    def update_mmd_camera():
        for camera_object in bpy.data.objects:
            if camera_object.type != "CAMERA":
                continue

            root_object = FnCamera.find_root(camera_object)
            if root_object is None:
                # It's not a MMD Camera
                continue

            FnCamera.remove_drivers(camera_object)
            FnCamera.add_drivers(camera_object)


class MMDCamera:
    def __init__(self, obj):
        root_object = FnCamera.find_root(obj)
        if root_object is None:
            raise ValueError(f"{str(obj)} is not MMDCamera")

        self.__emptyObj = getattr(root_object, "original", obj)

    @staticmethod
    def isMMDCamera(obj: bpy.types.Object) -> bool:
        return FnCamera.find_root(obj) is not None

    @staticmethod
    def addDrivers(cameraObj: bpy.types.Object):
        FnCamera.add_drivers(cameraObj)

    @staticmethod
    def removeDrivers(cameraObj: bpy.types.Object):
        if cameraObj.type != "CAMERA":
            return
        FnCamera.remove_drivers(cameraObj)

    @staticmethod
    def _lens_to_angle(cameraObj: bpy.types.Object, factor: float, lens_val: float = None) -> float:
        """Convert Focal Length to FOV (deg)"""
        current_lens = lens_val if lens_val is not None else cameraObj.data.lens
        if current_lens <= 0:
            logging.warning("Invalid Focal Length. Falling back to 0.001")
            current_lens = 0.001

        tan_val = cameraObj.data.sensor_height / current_lens / 2
        if cameraObj.data.sensor_fit != "VERTICAL":
            ratio = cameraObj.data.sensor_width / cameraObj.data.sensor_height
            if cameraObj.data.sensor_fit == "HORIZONTAL":
                tan_val *= factor * ratio
            else:  # cameraObj.data.sensor_fit == 'AUTO'
                tan_val *= min(ratio, factor * ratio)
        return 2 * math.atan(tan_val)

    @staticmethod
    def convertToMMDCamera(cameraObj: bpy.types.Object, scale=1.0, init_mmd=True):
        if FnCamera.is_mmd_camera(cameraObj):
            return MMDCamera(cameraObj)

        scene = bpy.context.scene
        empty = bpy.data.objects.new(name="MMD_Camera", object_data=None)
        FnContext.link_object(FnContext.ensure_context(), empty)

        render = scene.render
        factor = (render.resolution_y * render.pixel_aspect_y) / (render.resolution_x * render.pixel_aspect_x)

        if not init_mmd:
            original_angle = MMDCamera._lens_to_angle(cameraObj, factor)
            original_persp = cameraObj.data.type != "ORTHO"

        cameraObj.parent = empty
        cameraObj.data.sensor_fit = "VERTICAL"
        cameraObj.data.lens_unit = "MILLIMETERS"  # MILLIMETERS, FOV
        cameraObj.data.ortho_scale = 25 * scale
        cameraObj.data.clip_end = 500 * scale
        setattr(cameraObj.data, Props.display_size, 5 * scale)
        cameraObj.location = (0, -45 * scale, 0)
        cameraObj.rotation_mode = "XYZ"
        cameraObj.rotation_euler = (math.radians(90), 0, 0)
        cameraObj.lock_location = (True, False, True)
        cameraObj.lock_rotation = (True, True, True)
        cameraObj.lock_scale = (True, True, True)
        cameraObj.data.dof.focus_object = empty
        FnCamera.add_drivers(cameraObj)

        empty.location = (0, 0, 10 * scale)
        empty.rotation_mode = "YXZ"
        setattr(empty, Props.empty_display_size, 5 * scale)
        empty.lock_scale = (True, True, True)
        empty.mmd_type = "CAMERA"
        if init_mmd:
            empty.mmd_camera.angle = math.radians(30)
            empty.mmd_camera.persp = True
        else:
            cameraObj.location = (0, 0, 0)
            empty.mmd_camera.angle = original_angle
            empty.mmd_camera.persp = original_persp

        return MMDCamera(empty)

    @staticmethod
    def newMMDCameraAnimation(cameraObj, cameraTarget=None, scale=1.0, min_distance=0.1, bake_mode="ALL"):
        def copy_fcurve(src_fcurve, dst_action, data_path, index=0, transform_func=None):
            """Create new fcurve with optional transform (e.g. lens -> fov)"""
            dst_fcurve = dst_action.fcurves.find(data_path=data_path, index=index)
            if not dst_fcurve:
                dst_fcurve = dst_action.fcurves.new(data_path=data_path, index=index)

            for src_key in src_fcurve.keyframe_points:
                new_val = transform_func(src_key.co[1]) if transform_func else src_key.co[1]
                dst_key = dst_fcurve.keyframe_points.insert(frame=src_key.co[0], value=new_val)

                if transform_func:
                    dst_key.handle_left = (src_key.handle_left[0], transform_func(src_key.handle_left[1]))
                    dst_key.handle_right = (src_key.handle_right[0], transform_func(src_key.handle_right[1]))
                else:
                    dst_key.handle_left = src_key.handle_left
                    dst_key.handle_right = src_key.handle_right

                dst_key.interpolation = src_key.interpolation
                dst_key.easing = src_key.easing
                dst_key.handle_left_type = src_key.handle_left_type
                dst_key.handle_right_type = src_key.handle_right_type

        scene = bpy.context.scene
        mmd_cam = bpy.data.objects.new(name="Camera", object_data=bpy.data.cameras.new("Camera"))
        FnContext.link_object(FnContext.ensure_context(), mmd_cam)
        MMDCamera.convertToMMDCamera(mmd_cam, scale=scale, init_mmd=False)
        mmd_cam_root = mmd_cam.parent

        _camera_override_func = None
        if cameraObj is None:
            if scene.camera is None:
                scene.camera = mmd_cam
                return MMDCamera(mmd_cam_root)

            def _camera_override_func():
                return scene.camera

        _target_override_func = None
        if cameraTarget is None:

            def _target_override_func(camObj):
                return camObj.data.dof.focus_object or camObj

        cam_obj_anim = getattr(cameraObj, "animation_data", None)
        cam_dat_anim = getattr(cameraObj.data, "animation_data", None)
        if not ((cam_obj_anim and cam_obj_anim.action) or (cam_dat_anim and cam_dat_anim.action)):
            return MMDCamera(mmd_cam_root)

        action_name = mmd_cam_root.name
        parent_action = bpy.data.actions.new(name=action_name)
        distance_action = bpy.data.actions.new(name=action_name + "_dis")
        FnCamera.remove_drivers(mmd_cam)

        render = scene.render
        factor = (render.resolution_y * render.pixel_aspect_y) / (render.resolution_x * render.pixel_aspect_x)
        matrix_rotation = Matrix(([1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]))
        neg_z_vector = Vector((0, 0, -1))
        frame_start, frame_end, frame_current = scene.frame_start, scene.frame_end + 1, scene.frame_current
        frame_count = frame_end - frame_start
        frames = range(frame_start, frame_end)

        if bake_mode == "ALL":
            baked_curves = [parent_action.fcurves.new(data_path="location", index=i) for i in range(3)]  # x, y, z
            baked_curves.extend(parent_action.fcurves.new(data_path="rotation_euler", index=i) for i in range(3))  # rx, ry, rz
            baked_curves.append(parent_action.fcurves.new(data_path="mmd_camera.angle"))  # fov
            baked_curves.append(parent_action.fcurves.new(data_path="mmd_camera.is_perspective"))  # persp
            baked_curves.append(distance_action.fcurves.new(data_path="location", index=1))  # dis

            for c in baked_curves:
                c.keyframe_points.add(frame_count)

            for f, x, y, z, rx, ry, rz, fov, persp, dis in zip(frames, *(c.keyframe_points for c in baked_curves), strict=False):
                scene.frame_set(f)
                if _camera_override_func:
                    cameraObj = _camera_override_func()
                if _target_override_func:
                    cameraTarget = _target_override_func(cameraObj)
                cam_matrix_world = cameraObj.matrix_world
                cam_target_loc = cameraTarget.matrix_world.translation
                cam_rotation = (cam_matrix_world @ matrix_rotation).to_euler(mmd_cam_root.rotation_mode)
                cam_vec = cam_matrix_world.to_3x3() @ neg_z_vector
                if cameraObj.data.type == "ORTHO":
                    cam_dis = -(9 / 5) * cameraObj.data.ortho_scale
                    if cameraObj.data.sensor_fit != "VERTICAL":
                        if cameraObj.data.sensor_fit == "HORIZONTAL":
                            cam_dis *= factor
                        else:
                            cam_dis *= min(1, factor)
                else:
                    target_vec = cam_target_loc - cam_matrix_world.translation
                    cam_dis = -max(target_vec.length * cam_vec.dot(target_vec.normalized()), min_distance)
                cam_target_loc = cam_matrix_world.translation - cam_vec * cam_dis

                x.co, y.co, z.co = ((f, i) for i in cam_target_loc)
                rx.co, ry.co, rz.co = ((f, i) for i in cam_rotation)
                dis.co = (f, cam_dis)
                fov.co = (f, MMDCamera._lens_to_angle(cameraObj, factor))
                persp.co = (f, cameraObj.data.type != "ORTHO")
                persp.interpolation = "CONSTANT"
                for kp in (x, y, z, rx, ry, rz, fov, dis):
                    kp.interpolation = "LINEAR"

        else:
            mmd_cam_root.location = cameraObj.matrix_world.translation
            mmd_cam_root.mmd_camera.angle = MMDCamera._lens_to_angle(cameraObj, factor)
            mmd_cam_root.mmd_camera.persp = cameraObj.data.type != "ORTHO"

            baked_curves = [parent_action.fcurves.new(data_path="rotation_euler", index=i) for i in range(3)]  # rx, ry, rz

            for c in baked_curves:
                c.keyframe_points.add(frame_count)

            for f, rx, ry, rz in zip(frames, *(c.keyframe_points for c in baked_curves), strict=False):
                scene.frame_set(f)
                if _camera_override_func:
                    cameraObj = _camera_override_func()
                cam_matrix_world = cameraObj.matrix_world
                cam_rotation = (cam_matrix_world @ matrix_rotation).to_euler(mmd_cam_root.rotation_mode)

                rx.co, ry.co, rz.co = ((f, i) for i in cam_rotation)
                for kp in (rx, ry, rz):
                    kp.interpolation = "LINEAR"

            if cam_obj_anim and cam_obj_anim.action:
                for fcurve in cam_obj_anim.action.fcurves:
                    dp = fcurve.data_path
                    idx = fcurve.array_index
                    if dp == "location":
                        copy_fcurve(fcurve, parent_action, "location", index=idx)

            if cam_dat_anim and cam_dat_anim.action:
                for fcurve in cam_dat_anim.action.fcurves:
                    dp = fcurve.data_path
                    idx = fcurve.array_index
                    if dp == "lens":
                        copy_fcurve(fcurve, parent_action, "mmd_camera.angle", transform_func=lambda v: MMDCamera._lens_to_angle(cameraObj, factor, lens_val=v))
                    elif dp == "type":
                        copy_fcurve(fcurve, parent_action, "mmd_camera.is_perspective", transform_func=lambda v: 0.0 if round(v) == 1 else 1.0)

        FnCamera.add_drivers(mmd_cam)
        action_compat.assign_action_to_datablock(mmd_cam_root, parent_action)
        action_compat.assign_action_to_datablock(mmd_cam, distance_action)
        scene.frame_set(frame_current)
        return MMDCamera(mmd_cam_root)

    def object(self):
        return self.__emptyObj

    def camera(self):
        for i in self.__emptyObj.children:
            if i.type == "CAMERA":
                return i
        raise KeyError
