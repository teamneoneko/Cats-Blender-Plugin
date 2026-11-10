# MIT License

import os
import bpy
import pathlib

import bpy.utils.previews
from bpy.utils.previews import ImagePreviewCollection
import typing


# global variables
preview_collections: typing.Type[ImagePreviewCollection] = {}
reloading = False

main_dir = pathlib.Path(os.path.dirname(__file__)).parent.resolve()
resources_dir = os.path.join(str(main_dir), "resources")

def load_other_icons():
    # Note that preview collections returned by bpy.utils.previews
    # are regular py objects - you can use them to store custom data.
    pcoll: typing.Type[ImagePreviewCollection] = bpy.utils.previews.new()

    # path to the folder where the icon is
    # the path is calculated relative to this py file inside the addon folder
    icons_dir = os.path.join(resources_dir, "icons")
    icons_other_dir = os.path.join(icons_dir, "other")

    # load a preview thumbnail of a file and store in the previews collection
    pcoll.load('heart1', os.path.join(icons_other_dir, 'heart1.png'), 'IMAGE')
    pcoll.load('discord1', os.path.join(icons_other_dir, 'discord1.png'), 'IMAGE')
    pcoll.load('help1', os.path.join(icons_other_dir, 'help1.png'), 'IMAGE')
    pcoll.load('cats1', os.path.join(icons_other_dir, 'cats1.png'), 'IMAGE')
    pcoll.load('empty', os.path.join(icons_other_dir, 'empty.png'), 'IMAGE')
    pcoll.load('mesh', os.path.join(icons_other_dir, 'mesh.png'), 'IMAGE')
    pcoll.load('UP_ARROW', os.path.join(icons_other_dir, 'blender_up_arrow.png'), 'IMAGE')
    pcoll.load('Resonite', os.path.join(icons_other_dir, 'rsn_logo128.png'), 'IMAGE')
    # pcoll.load('TRANSLATE', os.path.join(icons_other_dir, 'translate.png'), 'IMAGE')

    preview_collections['custom_icons'] = pcoll


def unload_icons():
    print('UNLOADING ICONS!')
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()
    print('DONE!')
    