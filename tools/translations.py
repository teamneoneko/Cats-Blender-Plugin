# MIT License

# Thanks to https://www.thegrove3d.com/learn/how-to-translate-a-blender-addon/ for the idea

import os
import bpy
import json
import pathlib
try:
    import requests
except ImportError:
    requests = None

from .register import register_wrap
from . import user_data

main_dir = pathlib.Path(os.path.dirname(__file__)).parent.resolve()
resources_dir = os.path.join(str(main_dir), "resources")
LEGACY_SETTINGS_FILE = os.path.join(resources_dir, "settings.json")
translations_dir = os.path.join(resources_dir, "translations")


def list_language_codes():
    """Language codes available from the bundled and user translation dirs."""
    codes = []
    seen = set()
    for directory in (translations_dir, user_data.user_translations_dir()):
        try:
            names = os.listdir(directory)
        except OSError:
            continue
        for name in names:
            if not name.endswith(".json"):
                continue
            code = name.split(".")[0]
            if code not in seen:
                seen.add(code)
                codes.append(code)
    return codes


def translation_file_candidates(language_code):
    """Paths to try for a language file: the downloaded copy first, then the bundled one."""
    return [
        os.path.join(user_data.user_translations_dir(), language_code + ".json"),
        os.path.join(translations_dir, language_code + ".json"),
    ]


def read_translation_messages(path):
    """The "messages" dict of a language file, or None if it is missing or unreadable."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r', encoding='utf8') as file:
            messages = json.load(file)["messages"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        # A corrupt or half-downloaded file must not stop Cats from loading
        print(f"Could not read translation file {path}: {e}")
        return None
    return messages if isinstance(messages, dict) else None

dictionary: dict[str, str] = dict()
languages = []
verbose = True
last_loaded_language = None
translation_branch = f"{bpy.app.version[0]}.{bpy.app.version[1]}"
translation_repo_api = "https://git.neoneko.org/api/v1/repos/NeoNeko/Cats-Blender-Plugin"
dictionary_download_link = f"https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/raw/branch/{translation_branch}/resources/dictionary.json"
DOWNLOAD_TIMEOUT = 15
_addon_startup_time = None

def load_translations(override_language=None):
    global dictionary, languages, last_loaded_language, _addon_startup_time
    import time

    # Set startup time on first load
    if _addon_startup_time is None:
        _addon_startup_time = time.time()

    dictionary = dict()
    languages = ["auto"]

    print("Loading translations")

    if override_language:
        language = override_language
        print(f"Using override language: {language}")
    else:
        language = get_language_from_settings()
        print(f"Selected language: {language}")
    for code in list_language_codes():
        languages.append(code)
    print(f"Available languages: {languages}")

    # Determine the language to load
    language_to_load = language if language and language in languages else None

    # If language is not available, fallback to en_US
    if language_to_load is None:
        print(f"Language '{language}' not available, defaulting to en_US")
        language_to_load = "en_US"

    # Load the first readable file: the chosen language (downloaded, then bundled), then en_US as last resort
    loaded = False
    for code in dict.fromkeys((language_to_load, "en_US")):
        for translation_file in translation_file_candidates(code):
            messages = read_translation_messages(translation_file)
            if messages is not None:
                dictionary = messages
                last_loaded_language = code
                loaded = True
                print(f"Loaded {len(dictionary)} translations from {translation_file}")
                break
        if loaded:
            break
    if not loaded:
        print("NO READABLE TRANSLATION FILE FOUND, falling back to raw phrase keys.")

    check_missing_translations()


def t(phrase: str, *args, **kwargs):
    # Translate the given phrase into Blender's current language.
    output = dictionary.get(phrase)
    if output is None:
        if verbose:
            print('Warning: Unknown phrase: ' + phrase)
        return phrase

    return output.format(*args, **kwargs)


def check_missing_translations():
    for key, value in dictionary.items():
        if not value and verbose:
            print('Translations en_US: Value missing for key: ' + key)


def get_languages_list(self, context):
    choices = []

    for language in languages:
        # 1. Will be returned by context.scene
        # 2. Will be shown in lists
        # 3. will be shown in the hover description (below description)
        choices.append((language, language, language))

    return choices


def update_ui(self, context):
    global _addon_startup_time
    import time

    print("update_ui function called")

    # Don't trigger reload during the first 2 seconds after addon load (initialization period or crashes may occur)
    if _addon_startup_time and (time.time() - _addon_startup_time) < 2.0:
        print("Skipping reload during initialization period")
        return

    # Get the NEW language value directly from the scene property (not from file)
    # because the update callback is triggered BEFORE the settings file is saved
    current_language = context.scene.ui_lang if context and hasattr(context, 'scene') else None

    # Handle "auto" mode - detect from Blender locale
    if current_language and "auto" in current_language.lower():
        from bpy.app.translations import locale
        current_language = convert_locale_to_language_code(locale)
        if not current_language:
            current_language = "en_US"

    print(f"Current language from scene: {current_language}, Last loaded: {last_loaded_language}")

    if current_language != last_loaded_language:
        print(f"Language changed from {last_loaded_language} to {current_language}, reloading translations")

        # Save the settings first so get_language_from_settings() will return the new value
        from . import settings
        settings.update_settings_core(None, None)

        load_translations()
        
        bpy.app.timers.register(reload_cats, first_interval=2.0)
    else:
        print("Language unchanged, no reload needed")


def reload_cats():
    """Unregister, re-import and re-register the Cats package so class labels are rebuilt."""
    import sys
    import importlib

    root = sys.modules.get(__package__.rpartition('.')[0])
    if root is None:
        print("Cats reload failed: package module not found")
        return None

    print("Reloading Cats to apply new language...")
    try:
        root.unregister()
        importlib.reload(root)
        root.register()
        print("Language changed successfully!")
    except Exception as e:
        print(f"Cats reload failed: {e}")
    return None


def get_language_from_settings():
    user_data.migrate_legacy_file(LEGACY_SETTINGS_FILE, user_data.settings_file())
    try:
        with open(user_data.settings_file(), encoding="utf8") as file:
            settings_data = json.load(file)
    except FileNotFoundError:
        print("SETTINGS FILE NOT FOUND!")
        return
    except json.decoder.JSONDecodeError:
        print("ERROR FOUND IN SETTINGS FILE")
        return

    if not settings_data:
        print("NO DATA IN SETTINGS FILE")
        return

    lang = settings_data.get("ui_lang")
    if not lang or "auto" in lang.lower():
        # Auto-detect language from Blender's locale
        from bpy.app.translations import locale as current_locale
        detected_lang = convert_locale_to_language_code(current_locale)
        print(f"Auto-detecting language from Blender locale: {current_locale} -> {detected_lang}")
        return detected_lang

    return lang


def convert_locale_to_language_code(blender_locale):
    """
    Convert Blender's locale format to supported language code format.
    Blender uses formats like 'en_US', 'ja_JP', 'ko_KR', etc.
    """
    if not blender_locale:
        return None

    # Blender locale is already in the format we need (e.g., 'en_US')
    locale_str = str(blender_locale)

    # Check if exact match exists in available languages
    for lang_code in list_language_codes():
        if locale_str == lang_code:
            print(f"Found exact locale match: {lang_code}")
            return lang_code

    # Try to match by language code (first part before underscore)
    language_only = locale_str.split("_")[0].lower() if "_" in locale_str else locale_str.lower()
    for lang_code in list_language_codes():
        if lang_code.lower().startswith(language_only):
            print(f"Found language match: {lang_code}")
            return lang_code

    # Fallback to English if no match
    print(f"No language match found for locale: {locale_str}, defaulting to en_US")
    return None

load_translations()


@register_wrap
class DownloadTranslations(bpy.types.Operator):
    bl_idname = 'cats_translations.download_latest'
    bl_label = t('DownloadTranslations.label')
    bl_description = t('DownloadTranslations.desc')
    bl_options = {'INTERNAL'}

    def execute(self, context):
        if requests is None:
            self.report({'ERROR'}, t('DownloadTranslations.error.noRequests'))
            return {'CANCELLED'}

        if not bpy.app.online_access:
            self.report({'ERROR'}, t('online_access.disabled'))
            return {'CANCELLED'}

        folder_path = "resources/translations"
        api_url = f"{translation_repo_api}/contents/{folder_path}?ref={translation_branch}"

        try:
            # Send a GET request to the API URL
            response = requests.get(api_url, timeout=DOWNLOAD_TIMEOUT)
            response.raise_for_status()  # Raise an exception if the request was unsuccessful

            # Parse the JSON response
            files = response.json()

            user_translations_dir = user_data.user_translations_dir(ensure_dir=True)

            # Download each translation file
            for file in files:
                if file["type"] == "file" and file["name"].endswith(".json"):
                    file_url = file["download_url"]
                    file_name = file["name"]
                    file_path = os.path.join(user_translations_dir, file_name)

                    # Download the translation file
                    file_response = requests.get(file_url, timeout=DOWNLOAD_TIMEOUT)
                    file_response.raise_for_status()

                    # Save the translation file
                    with open(file_path, 'wb') as file:
                        file.write(file_response.content)

                    print(f"Downloaded: {file_name}")

        except requests.exceptions.RequestException as e:
            print("TRANSLATIONS FILES COULD NOT BE DOWNLOADED")
            self.report({'ERROR'}, t('DownloadTranslations.error.downloadFailed') + ': ' + str(e))
            return {'CANCELLED'}

        print('TRANSLATIONS DOWNLOAD FINISHED')

        dictionary_file = user_data.user_dictionary_file(ensure_dir=True)

        # Download dictionary.json from the matching Blender-version branch.
        print('DOWNLOAD DICTIONARY FILE')
        try:
            response = requests.get(dictionary_download_link, timeout=DOWNLOAD_TIMEOUT)
            response.raise_for_status()  # Raise an exception if the request was unsuccessful
            with open(dictionary_file, 'wb') as file:
                file.write(response.content)
        except requests.exceptions.RequestException as e:
            print("DICTIONARY FILE COULD NOT BE DOWNLOADED")
            self.report({'ERROR'}, t('DownloadTranslations.error.dictFailed') + ': ' + str(e))
            return {'CANCELLED'}
        print('DICTIONARY DOWNLOAD FINISHED')

        load_translations()

        self.report({'INFO'}, t('DownloadTranslations.success'))
        return {'FINISHED'}
