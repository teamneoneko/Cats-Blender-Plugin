# MIT License

import os
import bpy
import json
import copy
import time
import pathlib
import collections
from datetime import datetime, timezone
from collections import OrderedDict
from contextlib import contextmanager
from bpy.app.handlers import persistent

from .. import globs
from ..tools.register import register_wrap
from . import translate as Translate
from . import translation_providers
from . import user_data
from .translations import t

main_dir = pathlib.Path(os.path.dirname(__file__)).parent.resolve()
resources_dir = os.path.join(str(main_dir), "resources")
# Runtime settings live in the user data directory, not inside the (possibly
# read-only, update-wiped) extension package. LEGACY_SETTINGS_FILE is the old
# in-package location, kept only so existing settings can be migrated once.
LEGACY_SETTINGS_FILE = os.path.join(resources_dir, "settings.json")

settings_data = None
settings_data_unchanged = None
settings_timer_running = False
settings_timer_started_at = None

# Settings name = [Default Value, Require Blender Restart]
settings_default = OrderedDict()
settings_default['embed_textures'] = [False, False]
settings_default['ui_lang'] = ["auto", False]
# Translation backend selection + credentials. Stored globally (not per-blend)
# so API keys never end up inside a .blend file. See tools/translation_providers.py.
settings_default['translation_service'] = [translation_providers.SERVICE_GOOGLE, False]
settings_default['deepl_api_key'] = ["", False]
settings_default['libretranslate_url'] = ["https://libretranslate.com", False]
settings_default['libretranslate_api_key'] = ["", False]
settings_default['mymemory_email'] = ["", False]

CREDENTIAL_SETTINGS = ('deepl_api_key', 'libretranslate_url', 'libretranslate_api_key', 'mymemory_email')

lock_settings = False

@contextmanager
def settings_lock_context():
    global lock_settings
    lock_settings = True
    try:
        yield
    finally:
        lock_settings = False

@register_wrap
class RevertChangesButton(bpy.types.Operator):
    bl_idname = 'cats_settings.revert'
    bl_label = t('RevertChangesButton.label')
    bl_description = t('RevertChangesButton.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        for setting in settings_default.keys():
            setattr(bpy.context.scene, setting, settings_data_unchanged.get(setting))
        save_settings()
        self.report({'INFO'}, t('RevertChangesButton.success'))
        return {'FINISHED'}

@register_wrap
class ResetGoogleDictButton(bpy.types.Operator):
    bl_idname = 'cats_settings.reset_google_dict'
    bl_label = t('ResetGoogleDictButton.label')
    bl_description = t('ResetGoogleDictButton.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        Translate.reset_google_dict()
        Translate.load_translations()
        self.report({'INFO'}, t('ResetGoogleDictButton.resetInfo'))
        return {'FINISHED'}

@register_wrap
class DebugTranslations(bpy.types.Operator):
    bl_idname = 'cats_settings.debug_translations'
    bl_label = t('DebugTranslations.label')
    bl_description = t('DebugTranslations.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        bpy.context.scene.debug_translations = True
        provider = translation_providers.get_active_provider()
        try:
            if not provider.is_available():
                raise translation_providers.TranslationError("provider unavailable")
            provider.translate_text('猫')
        except Exception:
            bpy.context.scene.debug_translations = False
            self.report({'INFO'}, t('DebugTranslations.error'))
            return {'FINISHED'}

        bpy.context.scene.debug_translations = False
        self.report({'INFO'}, t('DebugTranslations.success'))
        return {'FINISHED'}

def load_settings():
    global settings_data, settings_data_unchanged

    user_data.migrate_legacy_file(LEGACY_SETTINGS_FILE, user_data.settings_file())

    try:
        with open(user_data.settings_file(), encoding="utf8") as file:
            settings_data = json.load(file, object_pairs_hook=collections.OrderedDict)
    except FileNotFoundError:
        print("SETTINGS FILE NOT FOUND!")
        reset_settings(full_reset=True)
        return
    except json.decoder.JSONDecodeError:
        print("ERROR FOUND IN SETTINGS FILE")
        reset_settings(full_reset=True)
        return

    if not settings_data:
        print("NO DATA IN SETTINGS FILE")
        reset_settings(full_reset=True)
        return

    to_reset_settings = []

    for setting in ['last_supporter_update']:
        if setting not in settings_data and setting not in to_reset_settings:
            to_reset_settings.append(setting)
            print('RESET SETTING', setting)

    for setting in settings_default.keys():
        if setting not in settings_data and setting not in to_reset_settings:
            to_reset_settings.append(setting)
            print('RESET SETTING', setting)

    utc_now = datetime.strptime(datetime.now(timezone.utc).strftime(globs.time_format), globs.time_format)
    for setting in ['last_supporter_update']:
        if setting not in to_reset_settings and settings_data.get(setting):
            try:
                timestamp = datetime.strptime(settings_data.get(setting), globs.time_format)
            except ValueError:
                to_reset_settings.append(setting)
                print('RESET TIME', setting)
                continue

            time_delta = (utc_now - timestamp).total_seconds()
            if time_delta < 0:
                to_reset_settings.append(setting)
                print('TIME', setting, 'IN FUTURE!', time_delta)

    if to_reset_settings:
        reset_settings(to_reset_settings=to_reset_settings)
        return

    settings_data_unchanged = copy.deepcopy(settings_data)

def save_settings():
    try:
        with open(user_data.settings_file(ensure_dir=True), 'w', encoding="utf8") as outfile:
            json.dump(settings_data, outfile, ensure_ascii=False, indent=4)
    except OSError as e:
        print(f"CATS: could not save settings to {user_data.settings_file()}: {e}")

def reset_settings(full_reset=False, to_reset_settings=None):
    if not to_reset_settings:
        full_reset = True

    global settings_data, settings_data_unchanged

    if full_reset:
        settings_data = OrderedDict()
        settings_data['last_supporter_update'] = None

        for setting, value in settings_default.items():
            settings_data[setting] = value[0]

    else:
        for setting in to_reset_settings:
            if setting in settings_default.keys():
                settings_data[setting] = settings_default[setting][0]
            else:
                settings_data[setting] = None

    save_settings()

    settings_data_unchanged = copy.deepcopy(settings_data)
    print('SETTINGS RESET')

def start_apply_settings_timer():
    global settings_timer_running, settings_timer_started_at
    settings_timer_started_at = time.monotonic()
    settings_timer_running = True
    if not bpy.app.timers.is_registered(apply_settings_timer):
        bpy.app.timers.register(apply_settings_timer, first_interval=0.3)

def apply_settings_timer():
    global settings_timer_running
    if not settings_timer_running:
        return None

    if settings_timer_started_at and time.monotonic() - settings_timer_started_at > 5:
        release_lock()
        settings_timer_running = False
        return None

    with settings_lock_context():
        if apply_settings():
            settings_timer_running = False
            return None

    return 0.3

def release_lock():
    global lock_settings
    print("Settings lock timed out, releasing lock")
    lock_settings = False

def credential_accessors(setting):
    """get/set callbacks for a CREDENTIAL_SETTINGS scene property."""
    def getter(_self):
        if not settings_data:
            return settings_default[setting][0]
        return settings_data.get(setting) or ""

    def setter(_self, value):
        if settings_data is None or settings_data.get(setting) == value:
            return
        settings_data[setting] = value
        save_settings()

    return getter, setter

def purge_stored_credentials():
    """Remove credential values that older Cats versions stored inside the open .blend."""
    for scene in bpy.data.scenes:
        sys_props = scene.bl_system_properties_get()
        if sys_props is None:
            continue
        for setting in CREDENTIAL_SETTINGS:
            if setting in sys_props:
                del sys_props[setting]

def apply_settings():
    if not hasattr(bpy.context, 'scene'):
        return False

    try:
        purge_stored_credentials()
    except AttributeError:
        return False

    try:
        settings_to_reset = []
        for setting in settings_default.keys():
            try:
                setattr(bpy.context.scene, setting, settings_data.get(setting))
            except TypeError:
                settings_to_reset.append(setting)
        if settings_to_reset:
            reset_settings(to_reset_settings=settings_to_reset)
            print("RESET SETTING ON TIMER:", setting)
    except AttributeError:
        return False

    print('Settings applied successfully')
    return True

def stop_apply_settings_timer():
    global settings_timer_running

    print("Stopping settings timer...")
    settings_timer_running = False
    if bpy.app.timers.is_registered(apply_settings_timer):
        bpy.app.timers.unregister(apply_settings_timer)
    print("Settings timer stopped.")

@persistent
def apply_settings_on_load(_dummy):
    """Re-apply the user's global Cats settings after a .blend is opened."""
    if settings_data is None:
        return
    with settings_lock_context():
        apply_settings()

def register_load_post_handler():
    if apply_settings_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(apply_settings_on_load)

def unregister_load_post_handler():
    if apply_settings_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(apply_settings_on_load)

def settings_changed():
    for setting, value in settings_default.items():
        if value[1] and settings_data.get(setting) != settings_data_unchanged.get(setting):
            return True
    return False

def update_settings(self, context):
    update_settings_core(self, context)

def update_settings_core(self, context):
    print("update_settings_core function called")
    settings_changed_tmp = False
    if lock_settings:
        print("Settings are locked, returning")
        return settings_changed_tmp

    with settings_lock_context():
        for setting in settings_default.keys():
            old = settings_data[setting]
            new = getattr(bpy.context.scene, setting)
            print(f"Checking setting: {setting}")
            print(f"Old value: {old}")
            print(f"New value: {new}")
            if old != new:
                print(f"Setting {setting} changed")
                settings_data[setting] = new
                settings_changed_tmp = True

        if settings_changed_tmp:
            print("Settings changed, saving settings")
            save_settings()
        else:
            print("No settings changed")

    return settings_changed_tmp

def get_embed_textures():
    return settings_data.get('embed_textures')

def get_ui_lang():
    return settings_data.get('ui_lang')

def get_translation_service():
    return settings_data.get('translation_service') if settings_data else None

def get_deepl_api_key():
    return settings_data.get('deepl_api_key', "") if settings_data else ""

def get_libretranslate_url():
    return settings_data.get('libretranslate_url', "") if settings_data else ""

def get_libretranslate_api_key():
    return settings_data.get('libretranslate_api_key', "") if settings_data else ""

def get_mymemory_email():
    return settings_data.get('mymemory_email', "") if settings_data else ""
