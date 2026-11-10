import os
import bpy
import numpy as np

from . import common as Common
from .register import register_wrap
from .translations import t
mmd_tools_local_installed = True

@register_wrap
class CombineMaterialsButton(bpy.types.Operator):
    bl_idname = 'cats_material.combine_mats'
    bl_label = t('CombineMaterialsButton.label')
    bl_description = t('CombineMaterialsButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    combined_tex = {}

    @classmethod
    def poll(cls, context):
        if Common.get_armature() is None:
            return False
        return len(Common.get_meshes_objects(check=False)) > 0

    def hash_material(self, material):
        if not material or not material.node_tree:
            return 'empty'
        
        ignore_nodes = {'Material Output', 'mmd_tex_uv', 'Cats Export Shader'}
        hash_components = []
        
        for node in material.node_tree.nodes:
            if node.name in ignore_nodes or node.label in ignore_nodes:
                continue

            if node.type == 'TEX_IMAGE':
                if any(x in node.name.lower() for x in ['toon', 'sphere']):
                    continue
                if node.image:
                    hash_components.append(f"{node.name}{node.image.name}")
                continue

            if node.name == 'mmd_shader' and node.inputs:
                diffuse = tuple(node.inputs['Diffuse Color'].default_value[:])
                alpha = node.inputs['Alpha'].default_value
                hash_components.append(f"mmd_shader{diffuse}{alpha}")
                continue

            if node.inputs:
                node_data = [node.name]
                for input in node.inputs:
                    if hasattr(input, 'default_value'):
                        try:
                            node_data.append(str(tuple(input.default_value[:])))
                        except TypeError:
                            node_data.append(str(input.default_value))
                    else:
                        node_data.append(input.name)
                hash_components.append(''.join(node_data))

        return hash(''.join(hash_components))

    def generate_combined_tex(self):
        """Map each duplicate material (by pointer) to the first material seen with the same hash."""
        self.combined_tex = {}
        canonical_by_hash = {}
        for ob in Common.get_meshes_objects():
            for mat_slot in ob.material_slots:
                material = mat_slot.material
                if material is None:
                    continue
                canonical = canonical_by_hash.setdefault(self.hash_material(material), material)
                if canonical.as_pointer() != material.as_pointer():
                    self.combined_tex[material.as_pointer()] = canonical

    def combine_mesh_materials(self, mesh):
        """Fold every duplicate slot on ``mesh`` into the slot holding its canonical material."""
        slots = mesh.material_slots
        if not slots:
            return 0

        # First slot on this mesh per material; duplicates fold into these.
        first_slot = {}
        for index, slot in enumerate(slots):
            if slot.material is not None:
                first_slot.setdefault(slot.material.as_pointer(), index)

        remap = list(range(len(slots)))
        combined = 0
        for index, slot in enumerate(slots):
            material = slot.material
            if material is None:
                continue
            canonical = self.combined_tex.get(material.as_pointer(), material)
            target = first_slot.setdefault(canonical.as_pointer(), index)
            if target != index:
                remap[index] = target
                combined += 1
            elif canonical.as_pointer() != material.as_pointer():
                slot.material = canonical
                combined += 1

        if any(target != index for index, target in enumerate(remap)):
            polygons = mesh.data.polygons
            indices = np.empty(len(polygons), dtype=np.int32)
            polygons.foreach_get('material_index', indices)
            lookup = np.array(remap, dtype=np.int32)
            valid = indices < len(lookup)
            indices[valid] = lookup[indices[valid]]
            polygons.foreach_set('material_index', indices)
            mesh.data.update()

        return combined

    def execute(self, context):
        print('COMBINE MATERIALS!')
        saved_data = Common.SavedData()
        
        # Setup
        Common.set_default_stage()
        Common.remove_rigidbodies_global()
        self.generate_combined_tex()
        Common.switch('OBJECT')
        
        total_combined = 0
        wm = context.window_manager
        meshes = Common.get_meshes_objects()
        wm.progress_begin(0, len(meshes))

        for index, mesh in enumerate(meshes):
            Common.unselect_all()
            Common.set_active(mesh)

            total_combined += self.combine_mesh_materials(mesh)

            # Drop the slots that no longer own any polygons
            bpy.ops.object.material_slot_remove_unused()
            Common.clean_material_names(mesh)
            
            wm.progress_update(index)

        wm.progress_end()
        Common.update_material_list()
        saved_data.load()

        # Report results
        if total_combined == 0:
            self.report({'INFO'}, t('CombineMaterialsButton.error.noChanges'))
        else:
            self.report({'INFO'}, t('CombineMaterialsButton.success', number=str(total_combined)))

        return {'FINISHED'}

@register_wrap
class ConvertAllToPngButton(bpy.types.Operator):
    bl_idname = 'cats_material.convert_all_to_png'
    bl_label = t('ConvertAllToPngButton.label')
    bl_description = t('ConvertAllToPngButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bpy.data.images

    def execute(self, context):
        images_to_convert = self.get_convert_list()

        if images_to_convert:
            current_step = 0
            wm = bpy.context.window_manager
            wm.progress_begin(current_step, len(images_to_convert))

            for image in images_to_convert:
                self.convert(image)
                current_step += 1
                wm.progress_update(current_step)

            wm.progress_end()

        self.report({'INFO'}, t('ConvertAllToPngButton.success', number=str(len(images_to_convert))))
        return {'FINISHED'}

    def get_convert_list(self):
        images_to_convert = []
        for image in bpy.data.images:
            tex_path = bpy.path.abspath(image.filepath)
            if tex_path.endswith(('.png', '.spa', '.sph')) or not os.path.isfile(tex_path):
                print('IGNORED:', image.name, tex_path)
                continue
            images_to_convert.append(image)
        return images_to_convert

    def convert(self, image):
        image_name = image.name
        print(image_name)
        image_name_new = ''
        for s in image_name.split('.')[0:-1]:
            image_name_new += s + '.'
        image_name_new += 'png'
        print(image_name_new)

        tex_path = bpy.path.abspath(image.filepath)
        print(tex_path)
        tex_path_new = ''
        for s in tex_path.split('.')[0:-1]:
            tex_path_new += s + '.'
        tex_path_new += 'png'
        print(tex_path_new)

        view_transform = bpy.context.scene.view_settings.view_transform
        bpy.context.scene.view_settings.view_transform = 'Standard'

        scene = bpy.context.scene
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.color_mode = 'RGBA'
        scene.render.image_settings.color_depth = '16'
        scene.render.image_settings.compression = 100
        image.save_render(tex_path_new, scene=scene)  

        bpy.context.scene.view_settings.view_transform = view_transform

        bpy.data.images[image_name].filepath = tex_path_new
        bpy.data.images[image_name].name = image_name_new

        return True
    