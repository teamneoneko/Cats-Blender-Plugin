# MIT License
#
# Central helpers for CATS runtime data that must live in a user-writable
# location instead of the extension package directory.

import os
import shutil
import bpy

_ADDON_PACKAGE = __package__.rsplit('.', 1)[0]


def get_user_data_dir():
    """Return the user-writable base directory for CATS runtime data.

    The directory is not created here; use the ``ensure_dir`` options on the
    path helpers below when you are about to write.
    """
    try:
        # Blender 5.x extension platform, a per-extension, per-user directory
        # that survives add-on updates.
        return bpy.utils.extension_path_user(_ADDON_PACKAGE, path="")
    except (AttributeError, ValueError, TypeError):
        # Legacy add-on install, or a Blender build without the extension
        # platform: fall back to the user datafiles directory.
        return os.path.join(bpy.utils.user_resource('DATAFILES'), "cats-blender-plugin")


def user_data_path(*relative, ensure_dir=False):
    """Path to a file/dir inside the user data directory."""
    path = os.path.join(get_user_data_dir(), *relative)
    if ensure_dir:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def settings_file(ensure_dir=False):
    return user_data_path("settings.json", ensure_dir=ensure_dir)


def google_dict_file(ensure_dir=False):
    return user_data_path("dictionary_google.json", ensure_dir=ensure_dir)


def user_dictionary_file(ensure_dir=False):
    return user_data_path("dictionary.json", ensure_dir=ensure_dir)


def user_translations_dir(ensure_dir=False):
    path = user_data_path("translations")
    if ensure_dir:
        os.makedirs(path, exist_ok=True)
    return path


def resolve_read_path(user_path, bundled_path):
    """Prefer a user-written file, falling back to the bundled default."""
    return user_path if os.path.isfile(user_path) else bundled_path


def migrate_legacy_file(legacy_path, user_path):
    """One-time copy of a file older CATS builds wrote inside the package.

    Older versions stored runtime data in resources/. If such a file is still
    present after an in-place upgrade and no user copy exists yet, copy it so the
    user keeps their settings / translation cache. Best-effort: failures are
    logged and ignored.
    """
    try:
        if os.path.isfile(legacy_path) and not os.path.exists(user_path):
            os.makedirs(os.path.dirname(user_path), exist_ok=True)
            shutil.copy2(legacy_path, user_path)
            print(f"CATS: migrated {legacy_path} -> {user_path}")
    except OSError as e:
        print(f"CATS: could not migrate {legacy_path} -> {user_path}: {e}")
