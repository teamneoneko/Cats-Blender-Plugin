# MIT License

if "bpy" not in locals():
    import bpy
    from . import main
    from . import quickaccess
    from . import optimization
    from . import custom
    from . import mmdoptions
    from . import otheroptions
    from . import visemes
    from . import bone_root
    from . import scale
    from . import eye_tracking
    from . import settings_updates
    from . import credits
else:
    import importlib
    importlib.reload(main)
    importlib.reload(quickaccess)
    importlib.reload(optimization)
    importlib.reload(custom)
    importlib.reload(mmdoptions)
    importlib.reload(otheroptions)
    importlib.reload(visemes)
    importlib.reload(bone_root)
    importlib.reload(scale)
    importlib.reload(eye_tracking)
    importlib.reload(settings_updates)
    importlib.reload(credits)