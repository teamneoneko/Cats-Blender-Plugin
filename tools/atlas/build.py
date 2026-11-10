# MIT License
from collections import Counter, OrderedDict

import bpy
import numpy as np

from . import bake, compose, detect, maps, pack, props, remap, sample
from .props import ATLAS_IMAGE_PREFIX, ATLAS_MATERIAL_PREFIX
from .. import colorspace
from .. import common as Common
from ..register import register_wrap
from ..translations import t


SECONDARY_SCALES = {'FULL': 1.0, 'HALF': 0.5, 'QUARTER': 0.25}


class _Cell:
    """One material group's slot in the atlas, from selection through to remapping."""

    __slots__ = (
        'key', 'sets', 'materials', 'objects', 'multiply_diffuse',
        'bounds', 'span', 'content_w', 'content_h', 'x', 'y',
    )

    def __init__(self, key, sets, multiply_diffuse):
        self.key = key
        self.sets = sets
        self.multiply_diffuse = multiply_diffuse
        self.materials = []
        self.objects = set()
        self.bounds = (0.0, 0.0, 1.0, 1.0)
        self.span = (1.0, 1.0)
        self.content_w = 1
        self.content_h = 1
        self.x = 0
        self.y = 0

    @property
    def texture_set(self):
        """The albedo set, which is what drives layout and UV remapping."""
        return self.sets['albedo']


def enabled_maps(scene):
    """Maps to generate for this build, in build order, albedo always first."""
    return [
        map_kind for map_kind, spec in maps.SPECS.items()
        if spec.scene_prop is None or getattr(scene, spec.scene_prop, False)
    ]


def _unique_objects_per_mesh(by_object):
    """The objects of ``by_object``, keeping only the first one per mesh."""
    seen = set()
    unique = []
    for ob in by_object:
        if ob.data in seen:
            continue
        seen.add(ob.data)
        unique.append(ob)
    return unique


def _atlas_names_taken(base_name):
    """Whether any datablock a build named ``base_name`` would write already exists."""
    material_name = ATLAS_MATERIAL_PREFIX + base_name[len(ATLAS_IMAGE_PREFIX):]
    if bpy.data.materials.get(material_name) is not None:
        return True
    suffixes = [spec.suffix for spec in maps.SPECS.values()] + [maps.PACKED_SPEC.suffix]
    return any(bpy.data.images.get(base_name + suffix) is not None for suffix in suffixes)


def unique_atlas_base_name(layer_index):
    """Image base name for a layer that no earlier build in this file has used."""
    base_name = '{}{:02d}'.format(ATLAS_IMAGE_PREFIX, layer_index)
    candidate = base_name
    number = 2
    while _atlas_names_taken(candidate):
        candidate = '{}_{}'.format(base_name, number)
        number += 1
    return candidate


# Principled inputs that change how bright the surface looks without being a map
_SURFACE_INPUTS = (
    'Roughness', 'Metallic', 'Specular IOR Level', 'IOR', 'Coat Weight', 'Sheen Weight',
)


def _copy_surface_settings(principled, cells):
    """Give the atlas material the same surface response as the materials it replaces."""
    source = next(
        (shader for cell in cells for material in cell.materials
         for shader in (detect.principled_shader(material),) if shader is not None),
        None,
    )
    principled.inputs['Roughness'].default_value = 1.0
    if source is None:
        principled.inputs['Specular IOR Level'].default_value = 0.0
        return

    for name in _SURFACE_INPUTS:
        source_input = source.inputs.get(name)
        target_input = principled.inputs.get(name)
        if source_input is None or target_input is None or source_input.links:
            continue
        target_input.default_value = source_input.default_value


def _slots_by_material(ob):
    """Every material slot index per material name on ``ob``."""
    slots = {}
    for index, slot in enumerate(ob.material_slots):
        if slot.material is not None:
            slots.setdefault(slot.material.name, []).append(index)
    return slots


@register_wrap
class CatsAtlasRefreshList(bpy.types.Operator):
    bl_idname = 'cats_atlas.refresh_list'
    bl_label = t('CatsAtlas.refresh.label')
    bl_description = t('CatsAtlas.refresh.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        count = props.build_list(context.scene)
        self.report({'INFO'}, t('CatsAtlas.refresh.success', number=str(count)))
        return {'FINISHED'}


@register_wrap
class CatsAtlasBuild(bpy.types.Operator):
    bl_idname = 'cats_atlas.build'
    bl_label = t('CatsAtlas.build.label')
    bl_description = t('CatsAtlas.build.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    dry_run: bpy.props.BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})

    _baked = {}
    _missing_layers = set()

    @classmethod
    def poll(cls, context):
        return bool(getattr(context.scene, 'cats_atlas_items', None))

    def execute(self, context):
        scene = context.scene
        layers = props.selected_materials(scene)
        if not layers:
            self.report({'ERROR'}, t('CatsAtlas.error.noSelection'))
            return {'CANCELLED'}

        saved = None if self.dry_run else Common.SavedData()
        sample.CACHE.clear()
        self._baked = {}
        self._missing_layers = set()
        reports = []
        try:
            if not self.dry_run:
                self._run_bakes(context, scene, layers)
            for layer_index in sorted(layers):
                result = self._build_layer(scene, layer_index, layers[layer_index])
                if result:
                    reports.append(result)
        except (pack.PackError, bake.BakeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        finally:
            # Runs on success, on a reported error and on an unexpected exception
            # alike: the user's selection and the temporary bake state must never
            # be left behind whatever went wrong.
            sample.CACHE.clear()
            bake.cleanup(self._baked)
            self._baked = {}
            if saved is not None:
                saved.load()

        if not reports:
            self.report({'ERROR'}, t('CatsAtlas.error.nothingToCombine'))
            return {'CANCELLED'}

        self.report({'INFO'}, ' | '.join(reports))
        return {'FINISHED'}

    def _run_bakes(self, context, scene, layers):
        """Bake every material that opted in, before any layout work happens."""
        wanted = enabled_maps(scene)
        by_object = {}
        for layer_materials in layers.values():
            for ob, materials in layer_materials.items():
                flagged = by_object.setdefault(ob, [])
                for material in materials:
                    if material in flagged:
                        continue
                    if getattr(props.material_settings(material), 'bake', False):
                        flagged.append(material)
        by_object = {ob: flagged for ob, flagged in by_object.items() if flagged}

        if not by_object:
            return

        skipped = [k for k in wanted if maps.SPECS[k].bake_pass is None]
        if skipped:
            self.report(
                {'WARNING'},
                t('CatsAtlas.warn.bakeUnsupported', maps=', '.join(skipped)),
            )

        self._baked = bake.bake_objects(
            context, by_object, wanted,
            size=scene.cats_atlas_bake_size,
            samples=scene.cats_atlas_bake_samples,
            margin=scene.cats_atlas_padding,
        )

    def _build_layer(self, scene, layer_index, by_object):
        cells = self._collect(scene, by_object)
        material_count = sum(len(cell.materials) for cell in cells)
        if material_count < 2 and not self.dry_run:
            return ''

        self._check_blend_modes(layer_index, cells)
        self._measure(scene, cells, by_object)
        merge_only = len(cells) == 1
        padding = 0 if merge_only else scene.cats_atlas_padding
        size_mode = 'AUTO' if merge_only else scene.cats_atlas_size_mode

        placed, atlas_size = self._layout(scene, cells, padding, size_mode)
        if not placed:
            return ''

        occupancy = pack.occupancy(placed, atlas_size)
        report = dict(
            layer=str(layer_index),
            width=str(atlas_size[0]),
            height=str(atlas_size[1]),
            materials=str(material_count),
            count=str(len(cells)),
            fill=str(int(occupancy * 100)),
        )
        if self.dry_run:
            key = 'CatsAtlas.dryRun.merged' if merge_only else 'CatsAtlas.dryRun.result'
            return t(key, **report)

        base_name = unique_atlas_base_name(layer_index)
        images = self._build_maps(scene, cells, atlas_size, base_name, padding)
        material = self._make_material(base_name, images, cells)
        self._remap_and_assign(scene, cells, atlas_size, material, by_object, padding)

        if scene.cats_atlas_remove_originals:
            self._remove_unused_slots(by_object, material)
        else:
            self.report({'INFO'}, t('CatsAtlas.build.originalsKept'))

        if merge_only:
            return t('CatsAtlas.build.merged', **report)
        return t('CatsAtlas.build.result', maps=str(len(images)), **report)

    def _build_maps(self, scene, cells, atlas_size, base_name, padding):
        """Compose, write and save every map that carries real data."""
        wanted = enabled_maps(scene)
        scale = SECONDARY_SCALES.get(scene.cats_atlas_secondary_scale, 1.0)

        canvases = {}
        for map_kind in wanted:
            if not any(
                detect.set_has_data(cell.sets[map_kind], map_kind) for cell in cells
            ):
                continue
            # Albedo defines the UV space, so it is never scaled down. The rest are
            # normalised against the same layout, so a smaller canvas needs no UV
            # change at all.
            map_scale = 1.0 if map_kind == 'albedo' else scale
            canvases[map_kind] = self._compose_map(
                scene, cells, atlas_size, map_kind, padding, map_scale
            )

        canvases = self._apply_channel_packing(scene, canvases)

        images = {}
        failed_save = False
        for map_kind, canvas in canvases.items():
            name = base_name + maps.spec(map_kind).suffix
            image = sample.write_atlas(
                name, canvas, map_kind,
                colorspace_from=self._colour_source_image(cells, map_kind),
            )
            images[map_kind] = image

            if scene.cats_atlas_output == 'DISK':
                if not sample.save_atlas(image, scene.cats_atlas_save_path):
                    failed_save = True
                    image.pack()
            else:
                image.pack()

        if failed_save:
            self.report({'WARNING'}, t('CatsAtlas.warn.saveFailed'))
        return images

    @staticmethod
    def _colour_source_image(cells, map_kind):
        """An sRGB-encoded source texture of a colour map, to copy its colour space from."""
        if maps.spec(map_kind).colorspace != colorspace.COLOR:
            return None
        for cell in cells:
            texture_set = cell.sets.get(map_kind)
            image = texture_set.image if texture_set is not None else None
            if detect.is_usable(image) and sample.is_srgb_encoded(image):
                return image
        return None

    @staticmethod
    def _apply_channel_packing(scene, canvases):
        """Fold metallic and roughness into one Unity MetallicSmoothness map.

        Replaces both inputs rather than adding to them: keeping all three would
        ship the same data twice."""
        if not scene.cats_atlas_pack_metallic_smoothness:
            return canvases
        if not (scene.cats_atlas_map_metallic and scene.cats_atlas_map_roughness):
            return canvases

        metallic = canvases.get('metallic')
        roughness = canvases.get('roughness')
        if metallic is None and roughness is None:
            return canvases

        reference = metallic if metallic is not None else roughness
        height, width = reference.shape[:2]
        if metallic is None:
            metallic = compose.new_canvas(width, height, maps.NEUTRAL['metallic'])
        if roughness is None:
            roughness = compose.new_canvas(width, height, maps.NEUTRAL['roughness'])

        packed = dict(canvases)
        packed[maps.PACKED_METALLIC_SMOOTHNESS] = compose.pack_metallic_smoothness(
            metallic, roughness
        )
        packed.pop('metallic', None)
        packed.pop('roughness', None)
        return packed

    def _collect(self, scene, by_object):
        """Group the layer's materials into cells, merging visual duplicates.

        Two materials with the same texture and tint share a cell, so a model with
        twenty variants of one texture packs as one.
        """
        wanted = enabled_maps(scene)
        cells = OrderedDict()
        for ob, materials in by_object.items():
            for material in materials:
                settings = props.material_settings(material)
                multiply = settings.multiply_diffuse if settings else True

                baked = self._baked.get(material.name)
                if baked:
                    # The bake already resolved the whole material, tint included,
                    # so multiplying the diffuse in again would apply it twice.
                    sets = bake.texture_sets_from_bake(baked, wanted)
                    multiply = False
                else:
                    sets = detect.texture_sets(material, wanted)

                key = detect.duplicate_key(sets, multiply, wanted)

                cell = cells.get(key)
                if cell is None:
                    cell = _Cell(key, sets, multiply)
                    cells[key] = cell
                if material not in cell.materials:
                    cell.materials.append(material)
                cell.objects.add(ob)
        return list(cells.values())

    def _check_blend_modes(self, layer_index, cells):
        """Warn when a layer merges materials with different blend modes."""
        modes = {
            material.blend_method
            for cell in cells for material in cell.materials
            if hasattr(material, 'blend_method')
        }
        if len(modes) > 1:
            self.report(
                {'WARNING'},
                t(
                    'CatsAtlas.warn.blendModeMismatch',
                    layer=str(layer_index),
                    modes=', '.join(sorted(modes)),
                ),
            )

    def _measure(self, scene, cells, by_object):
        """Work out each cell's UV bounds and its requested content size."""
        bounds_by_cell = {}
        for ob in _unique_objects_per_mesh(by_object):
            mesh = ob.data
            slot_for_material = _slots_by_material(ob)
            target_name = remap.render_uv_layer_name(mesh)
            by_layer = {}
            for cell in cells:
                slots = [
                    index
                    for m in cell.materials
                    for index in slot_for_material.get(m.name, ())
                ]
                if not slots:
                    continue
                layer_name = self._source_layer(
                    ob, cell.texture_set.uv_layer, target_name
                )
                by_layer.setdefault(layer_name, []).append((cell, slots))

            if not by_layer:
                continue

            loop_materials = remap.read_loop_materials(mesh)
            for layer_name, entries in by_layer.items():
                found = remap.slot_uv_bounds(
                    remap.read_uv_layer(mesh, layer_name),
                    loop_materials,
                    [slot for _, slots in entries for slot in slots],
                )
                for cell, slots in entries:
                    for slot in slots:
                        measured = found.get(slot)
                        if measured is None:
                            continue
                        existing = bounds_by_cell.get(cell.key)
                        bounds_by_cell[cell.key] = (
                            measured if existing is None
                            else remap.union_bounds(existing, measured)
                        )

        max_tiles = scene.cats_atlas_max_tiles
        for cell in cells:
            width, height = sample.source_size(
                cell.texture_set, scene.cats_atlas_color_size
            )

            # The cell holds exactly the texels under the material's UV bounds, so
            # the bounds are snapped to the texel grid and the transform, the crop
            # and the cell size all describe the same rectangle. Without the snap
            # the pixels and the UVs drift apart by a fraction of a texel; without
            # the crop, the UVs land on a cell that still holds the whole texture,
            # shifted by wherever the island started.
            bounds = bounds_by_cell.get(cell.key, (0.0, 0.0, 1.0, 1.0))
            if not scene.cats_atlas_crop_uv:
                bounds = remap.whole_tiles(bounds)
            bounds = remap.snap_bounds(bounds, (width, height))
            span = remap.uv_span(bounds, max_tiles=max_tiles)
            cell.bounds = (bounds[0], bounds[1], bounds[0] + span[0], bounds[1] + span[1])
            cell.span = span

            settings = props.material_settings(cell.materials[0]) if cell.materials else None
            if settings is not None and settings.size_override:
                width = min(width, settings.size_width)
                height = min(height, settings.size_height)

            cell.content_w = max(1, int(round(width * span[0])))
            cell.content_h = max(1, int(round(height * span[1])))

    def _layout(self, scene, cells, padding, size_mode):
        """Pack the cells, shrinking uniformly if they exceed the size cap."""
        cap = (scene.cats_atlas_max_width, scene.cats_atlas_max_height)
        requests = {cell.key: (cell.content_w, cell.content_h) for cell in cells}
        granted = pack.cell_sizes_for_budget(requests, cap, padding)

        if size_mode in ('PO2', 'QUAD') and padding > 0:
            unpadded = pack.bounds(pack.pack((k, w, h) for k, (w, h) in granted.items()))
            natural = pack.apply_size_mode(unpadded, size_mode, cap)
            tight_cap = (min(cap[0], natural[0]), min(cap[1], natural[1]))
            tight = pack.cell_sizes_for_budget(granted, tight_cap, padding)
            cost = min(
                min(tw / float(gw), th / float(gh))
                for (gw, gh), (tw, th) in ((granted[k], tight[k]) for k in granted)
            )
            if cost >= 0.9:
                granted = tight

        by_key = {cell.key: cell for cell in cells}
        for key, (width, height) in granted.items():
            by_key[key].content_w = width
            by_key[key].content_h = height

        placed = pack.pack(
            (cell.key, cell.content_w + 2 * padding, cell.content_h + 2 * padding)
            for cell in cells
        )
        for entry in placed:
            by_key[entry.key].x = entry.x
            by_key[entry.key].y = entry.y

        size = pack.apply_size_mode(pack.bounds(placed), size_mode, cap)
        return placed, size

    def _compose_map(self, scene, cells, atlas_size, map_kind, padding, scale=1.0):
        """Blit every cell into a canvas and dilate it into its padding ring."""
        pixel_art = scene.cats_atlas_pixel_art
        width = max(1, int(round(atlas_size[0] * scale)))
        height = max(1, int(round(atlas_size[1] * scale)))
        padding = max(0, int(round(padding * scale)))
        fill = (0.0, 0.0, 0.0, 0.0) if map_kind == 'albedo' else maps.NEUTRAL[map_kind]
        canvas = compose.new_canvas(width, height, fill)
        colour = maps.spec(map_kind).colorspace == colorspace.COLOR

        # Decoded sources are large (256 MB for a 4K texture), so each one is dropped
        # from the cache as soon as the last cell using it has been placed.
        remaining = Counter(
            cell.sets[map_kind].image.name_full for cell in cells
            if cell.sets[map_kind].image is not None
        )

        for cell in cells:
            texture_set = cell.sets[map_kind]
            try:
                cell_w = max(1, int(round(cell.content_w * scale)))
                cell_h = max(1, int(round(cell.content_h * scale)))
                x = int(round(cell.x * scale))
                y = int(round(cell.y * scale))

                # Rounding each cell independently can push the last one a pixel past
                # the canvas edge; clamp rather than raise on a rounding artefact.
                cell_w = min(cell_w, width - x - 2 * padding)
                cell_h = min(cell_h, height - y - 2 * padding)
                if cell_w < 1 or cell_h < 1:
                    continue

                tile = sample.cell_source(
                    texture_set,
                    cell_w,
                    cell_h,
                    cell.multiply_diffuse if map_kind == 'albedo' else False,
                    bounds=cell.bounds,
                    pixel_art=pixel_art,
                    colour=colour,
                )
                # Wrapping the ring is only right when the cell's far edge is the same
                # texel column as its near edge, i.e. a whole number of repeats. A
                # cropped cell's neighbours are the texels outside the crop, which the
                # clamped ring approximates.
                wrap = all(s >= 1.0 and abs(s - round(s)) < 1e-6 for s in cell.span)
                compose.place(canvas, tile, x, y, padding=padding, wrap=wrap)
            finally:
                if texture_set.image is not None:
                    key = texture_set.image.name_full
                    remaining[key] -= 1
                    if remaining[key] <= 0:
                        sample.CACHE.discard(texture_set.image)
        return canvas

    def _remap_and_assign(self, scene, cells, atlas_size, material, by_object, padding):
        """Rewrite UVs into atlas space, then point the faces at the new material."""
        remap_all = scene.cats_atlas_remap_all_uv_layers
        
        for ob in _unique_objects_per_mesh(by_object):
            mesh = ob.data
            slot_for_material = _slots_by_material(ob)

            loop_materials = remap.read_loop_materials(mesh)
            if loop_materials.size == 0:
                continue

            target_name = remap.render_uv_layer_name(mesh)
            if not target_name:
                continue

            transforms = {}
            for cell in cells:
                transform = remap.cell_transform(
                    cell.x, cell.y, cell.content_w, cell.content_h,
                    atlas_size[0], atlas_size[1],
                    cell.bounds, cell.span, padding=padding,
                )
                source_name = self._source_layer(
                    ob, cell.texture_set.uv_layer, target_name
                )
                for m in cell.materials:
                    for slot in slot_for_material.get(m.name, ()):
                        transforms[slot] = (transform, source_name)

            if not transforms:
                continue

            target_uvs = remap.read_uv_layer(mesh, target_name)
            if target_uvs.shape[0] != loop_materials.size:
                continue
            by_source = {}
            for slot, (transform, source_name) in transforms.items():
                by_source.setdefault(source_name, []).append((slot, transform))

            touched = False
            for source_name, entries in by_source.items():
                source_uvs = (
                    target_uvs if source_name == target_name
                    else remap.read_uv_layer(mesh, source_name)
                )
                if source_uvs.shape[0] != loop_materials.size:
                    continue
                for slot, transform in entries:
                    mask = loop_materials == slot
                    if not mask.any():
                        continue
                    moved = source_uvs[mask]
                    remap.apply_transform(moved, transform)
                    target_uvs[mask] = moved
                    touched = True

            if touched:
                remap.write_uv_layer(mesh, target_name, target_uvs)
            if remap_all:
                self._remap_other_layers(mesh, loop_materials, transforms, target_name)

            self._assign_material(ob, mesh, material, set(transforms))

    def _source_layer(self, ob, requested, target_name):
        """The layer a material's UVs are actually read from on this object."""
        if not requested:
            return target_name
        if ob.data.uv_layers.get(requested) is not None:
            return requested

        key = (ob.name, requested)
        if key not in self._missing_layers:
            self._missing_layers.add(key)
            self.report(
                {'WARNING'},
                t('CatsAtlas.warn.missingUvLayer', object=ob.name, layer=requested),
            )
        return target_name

    @staticmethod
    def _remap_other_layers(mesh, loop_materials, transforms, target_name):
        """Carry the same transforms into the mesh's remaining UV layers."""
        for layer in mesh.uv_layers:
            if layer.name == target_name:
                continue
            uvs = remap.read_uv_layer(mesh, layer.name)
            if uvs.shape[0] != loop_materials.size:
                continue
            touched = False
            for slot, (transform, _source) in transforms.items():
                mask = loop_materials == slot
                if not mask.any():
                    continue
                remap.apply_transform(uvs, transform, mask=mask)
                touched = True
            if touched:
                remap.write_uv_layer(mesh, layer.name, uvs)

    @staticmethod
    def _assign_material(ob, mesh, material, slots):
        """Point every face using an atlassed slot at the new material.

        Non-destructive: the original slots stay in place, unused. Removing them is
        opt-in, so a build that came out wrong can be undone by reassigning rather
        than by relying on undo alone.
        """
        if material.name in mesh.materials:
            target_index = mesh.materials.find(material.name)
        else:
            mesh.materials.append(material)
            target_index = len(mesh.materials) - 1

        polygon_count = len(mesh.polygons)
        if polygon_count == 0:
            return

        indices = np.empty(polygon_count, dtype=np.int32)
        mesh.polygons.foreach_get('material_index', indices)
        mask = np.isin(indices, list(slots))
        if not mask.any():
            return
        indices[mask] = target_index
        mesh.polygons.foreach_set('material_index', indices)
        mesh.update()

    @staticmethod
    def _remove_unused_slots(by_object, keep):
        """Drop material slots no face references any more."""
        for ob in by_object:
            mesh = ob.data
            if not mesh.polygons:
                continue
            used = np.empty(len(mesh.polygons), dtype=np.int32)
            mesh.polygons.foreach_get('material_index', used)
            in_use = set(used.tolist())
            for index in reversed(range(len(mesh.materials))):
                if index in in_use:
                    continue
                if mesh.materials[index] is keep:
                    continue
                mesh.materials.pop(index=index)

    @staticmethod
    def _make_material(base_name, images, cells=()):
        """Build a Principled material around the generated atlas maps.

        Deliberately plain, the output has to survive FBX export into Unity, so it is
        one Principled BSDF with each map wired to its matching input."""
        name = ATLAS_MATERIAL_PREFIX + base_name[len(ATLAS_IMAGE_PREFIX):]
        material = bpy.data.materials.new(name=name)

        # Blender 5.x materials always carry a node tree; there is no use_nodes flag.
        tree = material.node_tree
        tree.nodes.clear()

        output = tree.nodes.new('ShaderNodeOutputMaterial')
        output.location = (400, 300)

        principled = tree.nodes.new('ShaderNodeBsdfPrincipled')
        principled.location = (100, 300)
        _copy_surface_settings(principled, cells)
        tree.links.new(principled.outputs['BSDF'], output.inputs['Surface'])

        def texture_node(map_kind, y):
            node = tree.nodes.new('ShaderNodeTexImage')
            node.location = (-500, y)
            node.image = images[map_kind]
            node.label = 'Cats Atlas ' + map_kind
            return node

        row = 600
        if 'albedo' in images:
            node = texture_node('albedo', row)
            tree.links.new(node.outputs['Color'], principled.inputs['Base Color'])
            tree.links.new(node.outputs['Alpha'], principled.inputs['Alpha'])
            row -= 300

        if 'normal' in images:
            node = texture_node('normal', row)
            normal_map = tree.nodes.new('ShaderNodeNormalMap')
            normal_map.location = (-180, row)
            tree.links.new(node.outputs['Color'], normal_map.inputs['Color'])
            tree.links.new(normal_map.outputs['Normal'], principled.inputs['Normal'])
            row -= 300

        if 'emission' in images:
            node = texture_node('emission', row)
            tree.links.new(node.outputs['Color'], principled.inputs['Emission Color'])
            principled.inputs['Emission Strength'].default_value = 1.0
            row -= 300

        for map_kind, socket_name in (('roughness', 'Roughness'), ('metallic', 'Metallic')):
            if map_kind in images:
                node = texture_node(map_kind, row)
                tree.links.new(node.outputs['Color'], principled.inputs[socket_name])
                row -= 300

        for map_kind in (maps.PACKED_METALLIC_SMOOTHNESS, 'ao', 'height'):
            if map_kind in images:
                texture_node(map_kind, row)
                row -= 300

        material.use_backface_culling = True
        return material
