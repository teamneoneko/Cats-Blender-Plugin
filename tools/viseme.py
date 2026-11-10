# MIT License

import bpy
from . import common as Common
from .register import register_wrap
from collections import OrderedDict
from .translations import t

def preview_viseme(mesh, mix_data, shape_intensity):
    """Preview viseme shape in viewport and return original values"""
    original_values = {}
    for shape_key in mesh.data.shape_keys.key_blocks:
        original_values[shape_key.name] = shape_key.value
    
    for shape_data in mix_data:
        shape_name, value = shape_data
        if shape_name in mesh.data.shape_keys.key_blocks:
            mesh.data.shape_keys.key_blocks[shape_name].value = value * shape_intensity
    
    return original_values

class VisemePreview:
    _preview_data = {}
    _active = False
    _preview_shapes = None
    
    @classmethod
    def start_preview(cls, context, mesh, shapes):
        # Validate mesh and shape keys
        if not mesh or not mesh.data or not mesh.data.shape_keys:
            return False
            
        cls._active = True
        cls._preview_data = {}
        
        # Store original values
        for shape_key in mesh.data.shape_keys.key_blocks:
            cls._preview_data[shape_key.name] = shape_key.value
            
        # Generate preview shapes dictionary
        shape_a = context.scene.mouth_a
        shape_o = context.scene.mouth_o
        shape_ch = context.scene.mouth_ch
        
        cls._preview_shapes = OrderedDict()
        cls._preview_shapes['vrc.v_aa'] = {'mix': [[(shape_a), (0.9998)]]}
        cls._preview_shapes['vrc.v_ch'] = {'mix': [[(shape_ch), (0.9996)]]}
        cls._preview_shapes['vrc.v_dd'] = {'mix': [[(shape_a), (0.3)], [(shape_ch), (0.7)]]}
        cls._preview_shapes['vrc.v_ih'] = {'mix': [[(shape_ch), (0.7)], [(shape_o), (0.3)]]}
        cls._preview_shapes['vrc.v_ff'] = {'mix': [[(shape_a), (0.2)], [(shape_ch), (0.4)]]}
        cls._preview_shapes['vrc.v_e'] = {'mix': [[(shape_a), (0.5)], [(shape_ch), (0.2)]]}
        cls._preview_shapes['vrc.v_kk'] = {'mix': [[(shape_a), (0.7)], [(shape_ch), (0.4)]]}
        cls._preview_shapes['vrc.v_nn'] = {'mix': [[(shape_a), (0.2)], [(shape_ch), (0.7)]]}
        cls._preview_shapes['vrc.v_oh'] = {'mix': [[(shape_a), (0.2)], [(shape_o), (0.8)]]}
        cls._preview_shapes['vrc.v_ou'] = {'mix': [[(shape_o), (0.9994)]]}
        cls._preview_shapes['vrc.v_pp'] = {'mix': [[(shape_a), (0.0004)], [(shape_o), (0.0004)]]}
        cls._preview_shapes['vrc.v_rr'] = {'mix': [[(shape_ch), (0.5)], [(shape_o), (0.3)]]}
        cls._preview_shapes['vrc.v_sil'] = {'mix': [[(shape_a), (0.0002)], [(shape_ch), (0.0002)]]}
        cls._preview_shapes['vrc.v_ss'] = {'mix': [[(shape_ch), (0.8)]]}
        cls._preview_shapes['vrc.v_th'] = {'mix': [[(shape_a), (0.4)], [(shape_o), (0.15)]]}
        
        return True
    
    @classmethod
    def update_preview(cls, context):
        if not cls._active or not cls._preview_shapes:
            return
            
        mesh = Common.get_objects()[context.scene.mesh_name_viseme]
        viseme_data = cls._preview_shapes.get(context.scene.viseme_preview_selection)
        if viseme_data:
            cls.show_viseme(context, mesh, context.scene.viseme_preview_selection, viseme_data['mix'])
    
    @classmethod
    def show_viseme(cls, context, mesh, viseme_name, mix_data):
        if not cls._active:
            return
            
        # Reset all shape keys
        for shape_key in mesh.data.shape_keys.key_blocks:
            shape_key.value = 0
            
        # Apply preview shape
        for shape_name, value in mix_data:
            if shape_name in mesh.data.shape_keys.key_blocks:
                mesh.data.shape_keys.key_blocks[shape_name].value = value * context.scene.shape_intensity
                
        context.view_layer.update()
    
    @classmethod
    def end_preview(cls, mesh):
        if not cls._active:
            return
            
        # Restore original values
        for shape_name, value in cls._preview_data.items():
            if shape_name in mesh.data.shape_keys.key_blocks:
                mesh.data.shape_keys.key_blocks[shape_name].value = value
                
        cls._active = False
        cls._preview_data.clear()
        cls._preview_shapes = None

@register_wrap
class VisemePreviewOperator(bpy.types.Operator):
    bl_idname = 'cats_viseme.preview'
    bl_label = t('VisemePreviewOperator.label')
    bl_description = t('VisemePreviewOperator.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    
    def execute(self, context):
        mesh = Common.get_objects()[context.scene.mesh_name_viseme]
        
        if context.scene.viseme_preview_mode:
            VisemePreview.end_preview(mesh)
            context.scene.viseme_preview_mode = False
        else:
            if not mesh or not mesh.data or not mesh.data.shape_keys:
                self.report({'ERROR'}, t('AutoVisemeButton.error.noShapekeys'))
                return {'CANCELLED'}
                
            if VisemePreview.start_preview(context, mesh, [context.scene.mouth_a, context.scene.mouth_o, context.scene.mouth_ch]):
                context.scene.viseme_preview_mode = True
                context.scene.viseme_preview_selection = 'vrc.v_aa'
            
        return {'FINISHED'}

def validate_deformation(mesh, mix_data):
    """Validates if shape key deformations are within reasonable ranges"""
    base_coords = [v.co.copy() for v in mesh.data.shape_keys.key_blocks['Basis'].data]
    max_deform = 0
    
    for shape_data in mix_data:
        shape_name, value = shape_data
        if shape_name in mesh.data.shape_keys.key_blocks:
            shape_key = mesh.data.shape_keys.key_blocks[shape_name]
            for i, v in enumerate(shape_key.data):
                deform = (v.co - base_coords[i]).length * value
                max_deform = max(max_deform, deform)
    
    mesh_size = max(mesh.dimensions)
    return max_deform < (mesh_size * 0.4)

@register_wrap
class AutoVisemeButton(bpy.types.Operator):
    bl_idname = 'cats_viseme.create'
    bl_label = t('AutoVisemeButton.label')
    bl_description = t('AutoVisemeButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        if not Common.get_meshes_objects(check=False):
            return False
        return True

    def execute(self, context):
        mesh = Common.get_objects()[context.scene.mesh_name_viseme]

        if not Common.has_shapekeys(mesh):
            self.report({'ERROR'}, t('AutoVisemeButton.error.noShapekeys'))
            return {'CANCELLED'}

        if context.scene.mouth_a == "Basis" \
                or context.scene.mouth_o == "Basis" \
                or context.scene.mouth_ch == "Basis":
            self.report({'ERROR'}, t('AutoVisemeButton.error.selectShapekeys'))
            return {'CANCELLED'}

        saved_data = Common.SavedData()

        Common.set_default_stage()
        Common.remove_rigidbodies_global()

        wm = bpy.context.window_manager

        mesh = Common.get_objects()[context.scene.mesh_name_viseme]
        Common.set_active(mesh)

        # Fix a small bug
        bpy.context.object.show_only_shape_key = False

        # Rename selected shapes and rename them back at the end
        shapes = [context.scene.mouth_a, context.scene.mouth_o, context.scene.mouth_ch]
        renamed_shapes = [context.scene.mouth_a, context.scene.mouth_o, context.scene.mouth_ch]
        mesh = Common.get_objects()[context.scene.mesh_name_viseme]
        for index, shapekey in enumerate(mesh.data.shape_keys.key_blocks):
            if shapekey.name == context.scene.mouth_a:
                print(shapekey.name + " " + context.scene.mouth_a)
                shapekey.name = shapekey.name + "_old"
                context.scene.mouth_a = shapekey.name
                renamed_shapes[0] = shapekey.name
            if shapekey.name == context.scene.mouth_o:
                print(shapekey.name + " " + context.scene.mouth_a)
                if context.scene.mouth_a != context.scene.mouth_o:
                    shapekey.name = shapekey.name + "_old"
                context.scene.mouth_o = shapekey.name
                renamed_shapes[1] = shapekey.name
            if shapekey.name == context.scene.mouth_ch:
                print(shapekey.name + " " + context.scene.mouth_a)
                if context.scene.mouth_a != context.scene.mouth_ch and context.scene.mouth_o != context.scene.mouth_ch:
                    shapekey.name = shapekey.name + "_old"
                context.scene.mouth_ch = shapekey.name
                renamed_shapes[2] = shapekey.name
            wm.progress_update(index)

        shape_a = context.scene.mouth_a
        shape_o = context.scene.mouth_o
        shape_ch = context.scene.mouth_ch

        # Set up the shape keys
        shapekey_data = OrderedDict()
        shapekey_data['vrc.v_aa'] = {
            'mix': [
                [(shape_a), (0.9998)]
            ]
        }
        shapekey_data['vrc.v_ch'] = {
            'mix': [
                [(shape_ch), (0.9996)]
            ]
        }
        shapekey_data['vrc.v_dd'] = {
            'mix': [
                [(shape_a), (0.3)],
                [(shape_ch), (0.7)]
            ]
        }
        shapekey_data['vrc.v_ih'] = {
            'mix': [
                [(shape_ch), (0.7)],
                [(shape_o), (0.3)]
            ]
        }
        shapekey_data['vrc.v_ff'] = {
            'mix': [
                [(shape_a), (0.2)],
                [(shape_ch), (0.4)]
            ]
        }
        shapekey_data['vrc.v_e'] = {
            'mix': [
                [(shape_a), (0.5)],
                [(shape_ch), (0.2)]
            ]
        }
        shapekey_data['vrc.v_kk'] = {
            'mix': [
                [(shape_a), (0.7)],
                [(shape_ch), (0.4)]
            ]
        }
        shapekey_data['vrc.v_nn'] = {
            'mix': [
                [(shape_a), (0.2)],
                [(shape_ch), (0.7)]
            ]
        }
        shapekey_data['vrc.v_oh'] = {
            'mix': [
                [(shape_a), (0.2)],
                [(shape_o), (0.8)]
            ]
        }
        shapekey_data['vrc.v_ou'] = {
            'mix': [
                [(shape_o), (0.9994)]
            ]
        }
        shapekey_data['vrc.v_pp'] = {
            'mix': [
                [(shape_a), (0.0004)],
                [(shape_o), (0.0004)]
            ]
        }
        shapekey_data['vrc.v_rr'] = {
            'mix': [
                [(shape_ch), (0.5)],
                [(shape_o), (0.3)]
            ]
        }
        shapekey_data['vrc.v_sil'] = {
            'mix': [
                [(shape_a), (0.0002)],
                [(shape_ch), (0.0002)]
            ]
        }
        shapekey_data['vrc.v_ss'] = {
            'mix': [
                [(shape_ch), (0.8)]
            ]
        }
        shapekey_data['vrc.v_th'] = {
            'mix': [
                [(shape_a), (0.4)],
                [(shape_o), (0.15)]
            ]
        }

        total_fors = len(shapekey_data)
        wm.progress_begin(0, total_fors)

        for index, key in enumerate(shapekey_data):
            obj = shapekey_data[key]
            wm.progress_update(index)

            if context.scene.viseme_validate_deformation:
                if not validate_deformation(mesh, obj['mix']):
                    self.report({'WARNING'}, t('AutoVisemeButton.warning.deformation').format(key))
            
            if context.scene.viseme_preview_mode:
                original_values = preview_viseme(mesh, obj['mix'], context.scene.shape_intensity)
            
            self.mix_shapekey(context, renamed_shapes, obj['mix'], key, context.scene.shape_intensity)

            if context.scene.viseme_preview_mode:
                for shape_name, value in original_values.items():
                    if shape_name in mesh.data.shape_keys.key_blocks:
                        mesh.data.shape_keys.key_blocks[shape_name].value = value

        # Rename shapes back
        if shapes[0] not in mesh.data.shape_keys.key_blocks:
            shapekey = mesh.data.shape_keys.key_blocks.get(renamed_shapes[0])
            if shapekey:
                shapekey.name = shapes[0]
                if renamed_shapes[2] == renamed_shapes[0]:
                    renamed_shapes[2] = shapes[0]
                if renamed_shapes[1] == renamed_shapes[0]:
                    renamed_shapes[1] = shapes[0]
                renamed_shapes[0] = shapes[0]

        if shapes[1] not in mesh.data.shape_keys.key_blocks:
            shapekey = mesh.data.shape_keys.key_blocks.get(renamed_shapes[1])
            if shapekey:
                shapekey.name = shapes[1]
                if renamed_shapes[2] == renamed_shapes[1]:
                    renamed_shapes[2] = shapes[1]
                renamed_shapes[1] = shapes[1]

        if shapes[2] not in mesh.data.shape_keys.key_blocks:
            shapekey = mesh.data.shape_keys.key_blocks.get(renamed_shapes[2])
            if shapekey:
                shapekey.name = shapes[2]
                renamed_shapes[2] = shapes[2]

        # Reset context scenes
        try:
            context.scene.mouth_a = renamed_shapes[0]
        except TypeError:
            pass

        try:
            context.scene.mouth_o = renamed_shapes[1]
        except TypeError:
            pass

        try:
            context.scene.mouth_ch = renamed_shapes[2]
        except TypeError:
            pass

        # Set shapekey index back to 0
        bpy.context.object.active_shape_key_index = 0

        # Remove empty objects
        Common.switch('EDIT')
        Common.remove_empty()

        # Fix armature name
        Common.fix_armature_names()

        # Sort visemes
        Common.sort_shape_keys(mesh.name)

        saved_data.load()

        wm.progress_end()

        self.report({'INFO'}, t('AutoVisemeButton.success'))

        return {'FINISHED'}

    def mix_shapekey(self, context, shapes, shapekey_data, rename_to, intensity):
        mesh = Common.get_objects()[context.scene.mesh_name_viseme]

        # Remove existing shapekey
        for index, shapekey in enumerate(mesh.data.shape_keys.key_blocks):
            if shapekey.name == rename_to:
                bpy.context.active_object.active_shape_key_index = index
                bpy.ops.object.shape_key_remove()
                break

        # Reset all shape keys
        bpy.ops.object.shape_key_clear()

        # Set the shape key values
        for shapekey_data_context in shapekey_data:
            selector = shapekey_data_context[0]
            shapekey_value = shapekey_data_context[1]

            for index, shapekey in enumerate(mesh.data.shape_keys.key_blocks):
                if selector == shapekey.name:
                    shapekey.slider_max = 10
                    shapekey.value = shapekey_value * intensity

        # Create the new shape key
        mesh.shape_key_add(name=rename_to, from_mix=True)

        # Reset all shape keys and sliders
        bpy.ops.object.shape_key_clear()
        for index, shapekey in enumerate(mesh.data.shape_keys.key_blocks):
            if shapekey.name in shapes:
                shapekey.slider_max = 1
        mesh.active_shape_key_index = 0

        # Reset context scenes
        context.scene.mouth_a = shapes[0]
        context.scene.mouth_o = shapes[1]
        context.scene.mouth_ch = shapes[2]
