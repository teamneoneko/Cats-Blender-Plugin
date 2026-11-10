# MIT License

CATS_VERSION = "5.3.1.0"
dev_branch = False

import os
import sys

import shutil
import pathlib

# `requests` is normally bundled with Blender's Python, but don't let a missing copy stop CATS
# from registering, the core rig tools don't need it. Only the network features do (This should not
# happen with Downloaded versions of Blender from blender.org, This is mainly for Linux Users who use
# There distros blender from the package manager.)
try:
    import requests
    _requests_available = True
except ImportError:
    requests = None
    _requests_available = False

from . import globs

globs.requests_available = _requests_available

# Check if cats is reloading or started fresh
if "bpy" not in locals():
    import bpy
    is_reloading = False
else:
    is_reloading = True

# Load or reload all cats modules
if not is_reloading:
    # This order is important
    from . import mmd_tools_local
    from . import updater
    from . import tools
    from . import ui
    from . import extentions
else:
    import importlib
    importlib.reload(updater)
    importlib.reload(mmd_tools_local)
    importlib.reload(tools)
    importlib.reload(ui)
    importlib.reload(extentions)

from .tools import translations
from .tools.translations import t


# How to update mmd_tools_local:
# It is vendored from https://github.com/MMD-Blender/blender_mmd_tools by a script.
# Run (from the repo root):
#     python scripts/vendor_mmd_tools.py <version>   e.g. 4.5.13
# That downloads the release, moves operators into the mmd_tools_local.* namespace
# (so it can't clash with an official MMD Tools install), strips the nested
# blender_manifest.toml, and lifts the opencc wheel into ./wheels/ remember to
# update the `wheels` list in blender_manifest.toml if the script reports a change.
# See the docstring in scripts/vendor_mmd_tools.py for the full rationale.

# Online translation is handled by tools/translation_providers.py (Google, DeepL,
# LibreTranslate, MyMemory) there is no longer a bundled google_trans_new package.

# How to set up PyCharm with Blender:
# https://b3d.interplanety.org/en/using-external-ide-pycharm-for-writing-blender-scripts/


def remove_corrupted_files():
    to_remove = [
        'googletrans',
        'mmd_tools_local',
        'extern_tools',
        'resources',
        'tests',
        'tools',
        'ui',
        '.gitignore',
        '.travis.yml',
        'LICENSE',
        'README.md',
        '__init__.py',
        'addon_updater.py',
        'addon_updater_ops.py',
        'extensions.py',
        'globs.py',
        'updater.py',
    ]

    no_perm = False
    os_error = False
    wrong_path = False
    faulty_installation = False
    main_dir = str(pathlib.Path(os.path.dirname(__file__)).resolve())

    if main_dir.endswith('addons'):
        print(os.path.dirname(__file__))
        print(main_dir)
        print('Wrong installation path')
        wrong_path = True
    else:
        main_dir = str(pathlib.Path(os.path.dirname(__file__)).parent.resolve())

    # print('Checking for CATS files in the addon directory:\n' + main_dir)
    files = [f for f in os.listdir(main_dir) if os.path.isfile(os.path.join(main_dir, f))]
    folders = [f for f in os.listdir(main_dir) if os.path.isdir(os.path.join(main_dir, f))]

    for file in files:
        if file in to_remove:
            file_path = os.path.join(main_dir, file)
            try:
                os.remove(file_path)
                faulty_installation = True
                print('REMOVED', file)
            except PermissionError:
                no_perm = True
                print("Permissions: Failed to remove file " + file)
            except OSError:
                os_error = True
                print("OS: Failed to remove file " + file)

    for folder in folders:
        if folder in to_remove:
            folder_path = os.path.join(main_dir, folder)
            try:
                shutil.rmtree(folder_path)
                faulty_installation = True
                print('REMOVED', folder)
            except PermissionError:
                no_perm = True
                print("Permissions: Failed to remove folder " + folder)
            except OSError:
                os_error = True
                print("Failed to remove folder " + folder)

    if no_perm:
        unregister()
        sys.tracebacklimit = 0
        raise ImportError(t('Main.error.restartAdmin'))

    if os_error:
        unregister()
        sys.tracebacklimit = 0
        message = t('Main.error.deleteFollowing')

        for folder in folders:
            if folder in to_remove:
                message += "\n- " + os.path.join(main_dir, folder)

        for file in files:
            if file in to_remove:
                message += "\n- " + os.path.join(main_dir, file)

        raise ImportError(message)

    if wrong_path:
        unregister()
        sys.tracebacklimit = 0
        raise ImportError(t('Main.error.installViaPreferences'))

    if faulty_installation:
        unregister()
        sys.tracebacklimit = 0
        raise ImportError(t('Main.error.restartAndEnable'))


def check_unsupported_blender_versions():
    # Blender enforces blender_version_min from the manifest before the add-on loads,
    # so only the upper bound needs a runtime guard here now.

    # Escape hatch for the test suite's advisory run against an unreleased Blender:
    # it needs Cats to actually load so it can report what breaks there. Nothing
    # sets this during normal use, so users are still blocked from running Cats on
    # a version it does not support.
    if os.environ.get('CATS_ALLOW_UNSUPPORTED_BLENDER'):
        print(f"### CATS: loading on unsupported Blender {bpy.app.version} because "
              "CATS_ALLOW_UNSUPPORTED_BLENDER is set. Expect breakage.")
        return

    # Don't allow Blender versions newer than the current supported series
    if bpy.app.version >= (5, 4):
        sys.tracebacklimit = 0
        raise ImportError(t('Main.error.40unsupportedVersion'))

def set_cats_version_string():
    version_parts = CATS_VERSION.split(".")

    # Convert version parts to integers
    version_parts = [int(part) for part in version_parts]

    # Increment the last version component if in dev branch
    if dev_branch:
        version_parts[-1] += 1

    # Convert version back to string
    version_str = ".".join(str(part) for part in version_parts)

    # Add -dev if in dev version
    if dev_branch:
        version_str += "-dev"

    return version_str

def register():
    print("\n### Loading CATS...")

    # Check for unsupported Blender versions
    check_unsupported_blender_versions()

    # Check for faulty CATS installations
    remove_corrupted_files()

    # Set cats version string
    version_str = set_cats_version_string()

    # Register Updater and check for CATS update
    updater.register(dev_branch, version_str)

    # Set some global settings, first allowed use of globs
    globs.dev_branch = dev_branch
    globs.version_str = version_str

    # Load settings and show error if a faulty installation was deleted recently
    try:
        tools.settings.load_settings()
    except FileNotFoundError:
        sys.tracebacklimit = 0
        raise ImportError(t('Main.error.restartAndEnable_alt'))

    # if not tools.settings.use_custom_mmd_tools_local():
    #     bpy.utils.unregister_module("mmd_tools_local")

    # Load mmd_tools_local
    try:
        mmd_tools_local.register()
    except NameError:
        print('Could not register local mmd_tools_local')
    except AttributeError:
        print('Could not register local mmd_tools_local')
    except ValueError:
        print('mmd_tools_local is already registered')

    # Register all classes
    count = 0
    tools.register.order_classes()
    for cls in tools.register.__bl_ordered_classes:
        try:
            bpy.utils.register_class(cls)
            count += 1
        except ValueError as e:
            print(f'CATS: failed to register {cls!r}: {e}')
    if count < len(tools.register.__bl_ordered_classes):
        print('CATS: skipped', len(tools.register.__bl_ordered_classes) - count, 'classes (see errors above).')

    # Register Scene types
    extentions.register()
    
    # Load Icon Loader and settings icons and buttons
    tools.iconloader.load_other_icons()

    # Load the dictionaries and check if they are found.
    globs.dict_found = tools.translate.load_translations()

    # Add shapekey button to shapekey menu
    bpy.types.MESH_MT_shape_key_context_menu.append(tools.shapekey.addToShapekeyMenu)

    # Disable request warning when using google translate
    if globs.requests_available:
        requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

    # Apply the settings after a short time, because you can't change checkboxes during register process
    tools.settings.start_apply_settings_timer()

    # Re-apply the user's settings whenever a .blend is opened (scene props are
    # per-file, so a freshly opened file would otherwise override them).
    tools.settings.register_load_post_handler()

    # Kick off the background update check once at startup instead of on every
    # panel redraw.
    updater.check_for_update_background(check_on_startup=True)

    print("### Loaded CATS successfully!\n")


def unregister():
    print("### Unloading CATS...")

    # Unregister updater
    updater.unregister()

    # Unload mmd_tools_local
    try:
        mmd_tools_local.unregister()
    except NameError:
        print('mmd_tools_local was not registered')
        pass
    except AttributeError:
        print('Could not unregister local mmd_tools_local')
        pass
    except ValueError:
        print('mmd_tools_local was not registered')
        pass

    # Remove Scene/Material properties before the PropertyGroups they point to
    extentions.unregister()

    # Unload all classes in reverse order
    count = 0
    for cls in reversed(tools.register.__bl_ordered_classes):
        try:
            bpy.utils.unregister_class(cls)
            count += 1
        except ValueError:
            pass
        except RuntimeError:
            pass
    print('Unregistered', count, 'CATS classes.')

    # Unregister all dynamic buttons and icons
    tools.iconloader.unload_icons()

    # Remove shapekey button from shapekey menu
    try:
        bpy.types.MESH_MT_shape_key_context_menu.remove(tools.shapekey.addToShapekeyMenu)
    except AttributeError:
        print('shapekey button was not registered')
        pass
    except ValueError:
        print('shapekey button was not registered')
        pass

    tools.settings.stop_apply_settings_timer()
    tools.settings.unregister_load_post_handler()

    print("### Unloaded CATS successfully!\n")


if __name__ == '__main__':
    register()
