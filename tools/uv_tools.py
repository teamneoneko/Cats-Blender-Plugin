# MIT License

"""UV editing helpers for Cats.

Currently provides "Align UV Edges to Target" takes a line of selected UV
points on each selected mesh and reshapes it to follow the line of selected UV
points on the active mesh. Handy when kitbashing one model's texture layout onto
another. The 2D cursor in the UV editor marks which end of each line is the
start, so both lines are walked in the same direction before interpolating.

Ported from the Avatar Toolkit implementation by @989onan.
"""

import math
import traceback
from collections import deque
from typing import Set, Dict, List, TypedDict

import bpy
import bmesh
import numpy as np
from bpy.types import Operator, Context, Mesh, MeshUVLoopLayer

from .translations import t
from .register import register_wrap


def get_uv_vertex_selection(mesh: Mesh) -> List[bool]:
    """Return per-loop UV selection state (Blender 5.x stores it in a mesh attribute)."""
    uv_select_attr = mesh.attributes['.uv_select_vert']
    selection = [False] * len(mesh.loops)
    uv_select_attr.data.foreach_get('value', selection)
    return selection


def set_uv_vertex_selection(mesh: Mesh, loop_index: int, value: bool) -> None:
    """Set the UV selection state for a single loop."""
    uv_select_attr = mesh.attributes['.uv_select_vert']
    uv_select_attr.data[loop_index].value = value


class GenerateLoopTreeResult(TypedDict):
    tree: Dict[str, Set[str]]
    selected_loops: Dict[str, List[int]]
    selected_verts: Dict[str, int]


def find_shortest_seam_path(start, goal):
    """Return the shortest list of seam edges connecting ``start`` to ``goal``.

    Breadth-first search across seam edges only, so the first time the goal is
    reached the path has the fewest edges. Returns ``[]`` if the two vertices are
    not connected through seams. Operates on any bmesh verts/edges, which keeps it
    unit-testable without an operator or scene context.
    """
    queue = deque([(start, [])])
    visited = {start}
    while queue:
        node, edges = queue.popleft()
        if node is goal:
            return edges
        for edge in node.link_edges:
            if not edge.seam:
                continue
            other = edge.other_vert(node)
            if other in visited:
                continue
            visited.add(other)
            queue.append((other, edges + [edge]))
    return []


@register_wrap
class AlignUVEdgesToTarget(Operator):
    """Align selected UV edges of every selected mesh to the active mesh's selected edge"""
    bl_idname = "cats_uv.align_edges"
    bl_label = t("UVToolsPanel.alignEdges.label")
    bl_description = t("UVToolsPanel.alignEdges.desc")
    bl_options = {'REGISTER', 'UNDO'}

    # All selected objects need to be meshes and we must be editing UVs (sync off).
    @classmethod
    def poll(cls, context: Context) -> bool:
        if not ((context.view_layer.objects.active is not None) and (len(context.view_layer.objects.selected) > 0)):
            return False
        if context.mode != "EDIT_MESH":
            return False
        for obj in context.view_layer.objects.selected:
            if obj.type != "MESH":
                return False
        if not context.space_data:
            return False
        if not hasattr(context.space_data, "show_uvedit"):
            return False
        if not context.space_data.show_uvedit:
            return False
        if context.scene.tool_settings.use_uv_select_sync:
            return False
        return True

    def execute(self, context: Context) -> Set[str]:
        # Active object is the target line; every selected object gets aligned to it.
        target: str = context.view_layer.objects.active.name
        sources: List[str] = [i.name for i in context.view_layer.objects.selected]

        prev_mode: str = bpy.context.object.mode
        bpy.ops.object.mode_set(mode='OBJECT')

        def generate_loop_tree(obj_name: str) -> GenerateLoopTreeResult:
            # A UV map stores one "loop" per face corner. Blender merges UV corners that
            # share the same coordinate into a single movable point, but never records
            # that grouping. We rebuild it: group selected corners by rounded UV
            # coordinate, then use face-loop adjacency to chain the groups into a line.
            vert_target_loops: Dict[str, List[int]] = {}
            vert_target_verts: Dict[str, int] = {}

            me: Mesh = bpy.data.objects[obj_name].data
            uv_lay: MeshUVLoopLayer = me.uv_layers.active
            bm: bmesh.types.BMesh = bmesh.new()
            bm.from_mesh(me)
            bm.verts.ensure_lookup_table()

            uv_selection = get_uv_vertex_selection(me)
            for k, is_selected in enumerate(uv_selection):
                if is_selected and bm.verts[me.loops[k].vertex_index].select and (not bm.verts[me.loops[k].vertex_index].hide):
                    key = np.array(uv_lay.uv[k].vector[:]).round(decimals=5)

                    if str(key) not in vert_target_loops:
                        vert_target_loops[str(key)] = []
                    vert_target_loops[str(key)].append(k)
                    vert_target_verts[str(key)] = me.loops[k].vertex_index

            if len(vert_target_loops) > 4000:
                self.report({'WARNING'}, t("UVToolsPanel.error.tooManyVertices"))
                return {"tree": {}, "selected_loops": {}, "selected_verts": {}}

            me.validate()

            bm = bmesh.new()
            bm.from_mesh(me)

            tree: Dict[str, Set[str]] = {}
            selected_verts = np.hstack(list(vert_target_loops.values()))
            bm.verts.ensure_lookup_table()

            for uvcoordsstr in vert_target_loops:
                uv_lay = me.uv_layers.active

                # For each coordinate group, follow its face-loop neighbours to find the
                # next/previous selected coordinate groups: those are its line neighbours.
                extension_loops = []
                loops = bm.verts[vert_target_verts[uvcoordsstr]].link_loops
                loops_indexes = [i.index for i in loops]
                for loop in vert_target_loops[uvcoordsstr]:
                    if loop in loops_indexes:
                        loop_obj = loops[loops_indexes.index(loop)]
                        extension_loops.append(loop_obj.link_loop_next.index)
                        extension_loops.append(loop_obj.link_loop_prev.index)

                tree[uvcoordsstr] = set()

                for i in extension_loops:
                    if i in selected_verts:
                        key = np.array(uv_lay.uv[i].vector[:]).round(decimals=5)
                        tree[uvcoordsstr].add(str(key))

                if uvcoordsstr in tree and len(tree[uvcoordsstr]) > 2:
                    # More than two neighbours means it isn't a single clean line.
                    self.report({'WARNING'}, t("UVToolsPanel.error.needLine", obj=obj_name))
                    return {"tree": {}, "selected_loops": {}, "selected_verts": {}}

            for uvcoordstr in vert_target_loops:
                for loop in vert_target_loops[uvcoordstr]:
                    set_uv_vertex_selection(me, loop, True)

            bm.free()
            me.validate()

            return {"tree": tree, "selected_loops": vert_target_loops, "selected_verts": vert_target_verts}

        def sort_uv_tree(originaltree: Dict[str, Set[str]], obj_name: str) -> List[str]:
            sortedtree: Dict[str, Set[str]] = originaltree.copy()
            startpoints: List[str] = [i for i in sortedtree if len(sortedtree[i]) < 2]

            if len(startpoints) != 2:
                self.report({'WARNING'}, t("UVToolsPanel.error.needLine", obj=obj_name))
                return []

            uvcoords1 = [float(x) for x in startpoints[0].replace("[", "").replace("]", "").split()]
            uvcoords2 = [float(x) for x in startpoints[1].replace("[", "").replace("]", "").split()]

            cursor = context.space_data.cursor_location

            # The line end furthest from the 2D cursor becomes the start, so target and
            # source lines are always walked in a consistent direction.
            dist1 = math.sqrt((uvcoords1[0] - cursor[0])**2 + (uvcoords1[1] - cursor[1])**2)
            dist2 = math.sqrt((uvcoords2[0] - cursor[0])**2 + (uvcoords2[1] - cursor[1])**2)
            startpoint = startpoints[0] if dist1 > dist2 else startpoints[1]

            def recursive_sort_uv_tree(point: str, sortedfinal: List[str]) -> List[str]:
                sortedfinal.append(point)

                new_point: str = ""
                for i in sortedtree:
                    if point in sortedtree[i]:
                        new_point = i
                        sortedtree.pop(i)
                        break

                if new_point == "":
                    return sortedfinal

                return recursive_sort_uv_tree(new_point, sortedfinal)

            sortedtree.pop(startpoint)
            return recursive_sort_uv_tree(startpoint, [])

        def lerp(v0: float, v1: float, factor: float) -> float:
            return v0 + factor * (v1 - v0)

        target_data = generate_loop_tree(target)
        sorted_target_tree = sort_uv_tree(target_data["tree"], target)

        for source in sources:
            if source == target:
                continue

            try:
                source_data = generate_loop_tree(source)
                sorted_source_tree = sort_uv_tree(source_data["tree"], source)

                vertex_factor = float(len(sorted_target_tree) - 1) / float(len(sorted_source_tree) - 1)

                for k, i in enumerate(sorted_source_tree):
                    try:
                        # Interpolate this source point's new position along the target line.
                        progress_along_edge = float(k) * vertex_factor
                        previous_vertex_index = math.floor(progress_along_edge)
                        next_vertex_index = math.ceil(progress_along_edge)

                        previous_point = [float(x) for x in sorted_target_tree[previous_vertex_index].replace("[", "").replace("]", "").split()]
                        next_point = [float(x) for x in sorted_target_tree[next_vertex_index].replace("[", "").replace("]", "").split()]

                        progress_between_points = progress_along_edge - int(progress_along_edge)
                        lerped_point = [
                            lerp(previous_point[0], next_point[0], progress_between_points),
                            lerp(previous_point[1], next_point[1], progress_between_points),
                        ]

                        uv_face_corners = source_data["selected_loops"][i]

                        me = bpy.data.objects[source].data
                        uv_lay = me.uv_layers.active
                        for corner in uv_face_corners:
                            uv_lay.uv[corner].vector = lerped_point

                    except (IndexError, KeyError, ZeroDivisionError, ValueError):
                        # A malformed point on one line shouldn't abort the whole align.
                        pass

            except Exception:
                print("CATS UV align error:", traceback.format_exc())
                bpy.ops.object.mode_set(mode=prev_mode)
                return {'CANCELLED'}

        bpy.ops.object.mode_set(mode=prev_mode)
        return {'FINISHED'}


@register_wrap
class FindShortestSeamPath(Operator):
    """Select the shortest run of seam edges between two selected vertices"""
    bl_idname = "cats_uv.find_seam_path"
    bl_label = t("UVToolsPanel.seamPath.label")
    bl_description = t("UVToolsPanel.seamPath.desc")
    bl_options = {'REGISTER', 'UNDO'}

    # Needs mesh edit mode with exactly two selected vertices, each touching a seam.
    @classmethod
    def poll(cls, context: Context) -> bool:
        obj = context.active_object
        if context.mode != "EDIT_MESH" or obj is None or obj.type != "MESH":
            return False
        bm = bmesh.from_edit_mesh(obj.data)
        selected = 0
        for vert in bm.verts:
            if vert.select:
                selected += 1
                if selected > 2:
                    return False
                if not any(edge.seam for edge in vert.link_edges):
                    return False
        return selected == 2

    def execute(self, context: Context) -> Set[str]:
        obj = context.active_object
        mesh_data = obj.data
        bm = bmesh.from_edit_mesh(mesh_data)

        endpoints = [vert for vert in bm.verts if vert.select]
        if len(endpoints) != 2:
            self.report({'WARNING'}, t("UVToolsPanel.seamPath.error.needTwo"))
            return {'CANCELLED'}
        start, goal = endpoints

        path = find_shortest_seam_path(start, goal)
        if not path:
            self.report({'WARNING'}, t("UVToolsPanel.seamPath.error.noPath"))
            return {'CANCELLED'}

        # Switch to edge select and highlight the path (endpoints stay selected too).
        context.tool_settings.mesh_select_mode = (False, True, False)
        for edge in path:
            edge.select = True
            for vert in edge.verts:
                vert.select = True
        bmesh.update_edit_mesh(mesh_data)

        self.report({'INFO'}, t("UVToolsPanel.seamPath.success", count=str(len(path))))
        return {'FINISHED'}
