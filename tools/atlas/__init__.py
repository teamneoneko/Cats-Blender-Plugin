# MIT License
if "bpy" not in locals():
    import bpy
    from . import maps
    from . import pack
    from . import compose
    from . import remap
    from . import detect
    from . import sample
    from . import bake
    from . import props
    from . import migrate
    from . import build
else:
    import importlib
    importlib.reload(maps)
    importlib.reload(pack)
    importlib.reload(compose)
    importlib.reload(remap)
    importlib.reload(detect)
    importlib.reload(sample)
    importlib.reload(bake)
    importlib.reload(props)
    importlib.reload(migrate)
    importlib.reload(build)

from .build import CatsAtlasBuild, CatsAtlasRefreshList
from .migrate import CatsAtlasImportSMC  
from .props import CatsAtlasItem, CatsAtlasMaterialSettings
