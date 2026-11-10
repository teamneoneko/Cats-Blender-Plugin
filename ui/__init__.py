# MIT License

if "bpy" not in locals():
    import bpy
    from . import main
    from . import quickaccess
    from . import optimization
    from . import mmdoptions
    from . import custom
    from . import translation
    from . import bone_tools
    from . import visemes
    from . import bone_root
    from . import scale
    from . import eye_tracking
    from . import uv_tools
    from . import settings_updates
    from . import credits
else:
    import importlib
    importlib.reload(main)
    importlib.reload(quickaccess)
    importlib.reload(optimization)
    importlib.reload(mmdoptions)
    importlib.reload(custom)
    importlib.reload(translation)
    importlib.reload(bone_tools)
    importlib.reload(visemes)
    importlib.reload(bone_root)
    importlib.reload(scale)
    importlib.reload(eye_tracking)
    importlib.reload(uv_tools)
    importlib.reload(settings_updates)
    importlib.reload(credits)