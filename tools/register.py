# MIT License

import bpy
import typing

__bl_classes = []
__bl_ordered_classes = []


def register_wrap(cls):
    if hasattr(cls, 'bl_rna'):
        __bl_classes.append(cls)
    return cls


def order_classes():
    """Order classes so each one comes after its dependencies, otherwise keeping declaration order."""
    global __bl_ordered_classes
    own_classes = set(__bl_classes)
    classes_by_idname = {getattr(cls, 'bl_idname', None): cls for cls in __bl_classes}
    deps_dict = {cls: set(iter_own_register_deps(cls, own_classes, classes_by_idname)) for cls in __bl_classes}
    __bl_ordered_classes = toposort(__bl_classes, deps_dict)


def iter_own_register_deps(cls, own_classes, classes_by_idname):
    for dep in iter_register_deps(cls, classes_by_idname):
        if dep in own_classes and dep is not cls:
            yield dep


def iter_register_deps(cls, classes_by_idname):
    # PropertyGroups used by Pointer/CollectionProperty annotations
    for value in typing.get_type_hints(cls, {}, {}).values():
        dependency = get_dependency_from_annotation(value)
        if dependency is not None:
            yield dependency

    # Parent panels of sub-panels
    if issubclass(cls, bpy.types.Panel):
        parent = classes_by_idname.get(getattr(cls, 'bl_parent_id', None))
        if parent is not None:
            yield parent


def get_dependency_from_annotation(value):
    if isinstance(value, bpy.props._PropertyDeferred):
        if value.function in (bpy.props.PointerProperty, bpy.props.CollectionProperty):
            return value.keywords.get('type')
    return None


# Find order to register to solve dependencies
#################################################

def toposort(classes, deps_dict):
    """Depth-first topological sort that keeps the given order wherever dependencies allow."""
    sorted_list = []
    done = set()
    visiting = set()

    def visit(cls):
        if cls in done or cls in visiting:
            return
        visiting.add(cls)
        for dep in deps_dict.get(cls, ()):
            visit(dep)
        visiting.discard(cls)
        done.add(cls)
        sorted_list.append(cls)

    for cls in classes:
        visit(cls)
    return sorted_list
