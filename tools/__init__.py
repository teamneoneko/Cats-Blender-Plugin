# MIT License

if "bpy" not in locals():
    # print('STARTUP TOOLS!!')
    import bpy
    from . import register
    from . import armature
    from . import armature_bones
    from . import colorspace
    from . import armature_manual
    from . import armature_custom
    from . import common
    from . import bonemerge
    # atlas imports tools.common, so it has to follow it.
    from . import atlas
    from . import credits
    from . import eyetracking
    from . import importer
    from . import material
    from . import rootbone
    from . import rigify_convert
    from . import settings
    from . import scaler
    from . import shapekey
    from . import translate
    from . import translations
    from . import uv_tools
    from . import viseme
    from . import iconloader
else:
    # print('RELOAD TOOLS!!')
    import importlib
    importlib.reload(register)  # Has to be first
    importlib.reload(armature)
    importlib.reload(armature_bones)
    importlib.reload(colorspace)
    importlib.reload(armature_manual)
    importlib.reload(armature_custom)
    importlib.reload(common)
    importlib.reload(bonemerge)
    importlib.reload(atlas)
    importlib.reload(credits)
    importlib.reload(eyetracking)
    importlib.reload(importer)
    importlib.reload(material)
    importlib.reload(rootbone)
    importlib.reload(rigify_convert)
    importlib.reload(settings)
    importlib.reload(scaler)
    importlib.reload(shapekey)
    importlib.reload(translate)
    importlib.reload(translations)
    importlib.reload(uv_tools)
    importlib.reload(viseme)
    importlib.reload(iconloader)
