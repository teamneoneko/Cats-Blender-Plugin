# MIT License
# Roles used by callers. Kept as plain strings so pure-Python tables can refer to
# them without importing bpy.
COLOR = 'color'
DATA = 'data'

_ROLES = {
    COLOR: ('srgb_rec709_display', 'sRGB'),
    DATA: ('data', 'Non-Color'),
}

# Both sRGB interop IDs use the sRGB transfer function, which is all the callers
# reading this care about.
_SRGB_INTEROP_IDS = {'srgb_rec709_scene', 'srgb_rec709_display'}


def set_role(image, role):
    """Tag ``image`` with the colour space for ``role`` (``COLOR`` or ``DATA``)."""
    interop_id, legacy_name = _ROLES[role]
    settings = image.colorspace_settings
    if hasattr(settings, 'interop_id'):
        try:
            settings.interop_id = interop_id
            return
        except (TypeError, ValueError):
            pass
    settings.name = legacy_name


def is_srgb(image):
    """Whether ``image`` is tagged with an sRGB-encoded colour space."""
    settings = image.colorspace_settings
    interop_id = getattr(settings, 'interop_id', '')
    if interop_id:
        return interop_id in _SRGB_INTEROP_IDS
    return settings.name == 'sRGB'
