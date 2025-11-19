# MIT License

import bpy

# for bone root parenting
root_bones = {}
root_bones_choices = {}

# Keeps track of operations done for unit testing
testing = []

dev_branch = False
dict_found = False
version = None
version_str = ''

# other
time_format = "%Y-%m-%d %H:%M:%S"
time_format_github = "%Y-%m-%dT%H:%M:%SZ"

# Icons for UI
ICON_ADD, ICON_REMOVE = 'ADD', 'REMOVE'
ICON_URL = 'URL'
ICON_SETTINGS = 'SETTINGS'
ICON_ALL = 'PROP_ON'
ICON_MOD_ARMATURE = 'MOD_ARMATURE'
ICON_FIX_MODEL = 'SHADERFX'
ICON_EYE_ROTATION = 'DRIVER_ROTATIONAL_DIFFERENCE'
ICON_POSE_MODE = 'POSE_HLT'
ICON_SHADING_TEXTURE = 'SHADING_TEXTURE'
ICON_PROTECT = 'LOCKED'
ICON_UNPROTECT = 'UNLOCKED'
ICON_EXPORT = 'EXPORT'

# Additional commonly used icons
ICON_ERROR = 'ERROR'
ICON_WARNING = 'ERROR'  # Blender uses same icon for warnings
ICON_INFO = 'INFO'
ICON_QUESTION = 'QUESTION'
ICON_REFRESH = 'FILE_REFRESH'
ICON_PLAY = 'PLAY'
ICON_PAUSE = 'PAUSE'
ICON_EXECUTE = 'TRIA_RIGHT'
ICON_ARMATURE = 'ARMATURE_DATA'
ICON_MESH = 'MESH_DATA'
ICON_BONE = 'BONE_DATA'
ICON_MATERIAL = 'MATERIAL'
ICON_SHAPEKEY = 'SHAPEKEY_DATA'
ICON_HEART = 'HEART'

