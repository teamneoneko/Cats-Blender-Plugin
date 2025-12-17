# GPL License

# Thanks to https://www.thegrove3d.com/learn/how-to-translate-a-blender-addon/ for the idea

import os
import csv
import ssl
import bpy
import json
import urllib
import pathlib
import addon_utils
import requests
from bpy.app.translations import locale

from .register import register_wrap
from . import settings

main_dir = pathlib.Path(os.path.dirname(__file__)).parent.resolve()
resources_dir = os.path.join(str(main_dir), "resources")
settings_file = os.path.join(resources_dir, "settings.json")
translations_dir = os.path.join(resources_dir, "translations")

dictionary: dict[str, str] = dict()
languages = []
verbose = True
last_loaded_language = None
dictionary_download_link = "https://github.com/teamneoneko/Cats-Blender-Plugin-Unofficial-translations/blob/4.3-translations/dictionary.json"
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

    # Get all current languages
    for i in os.listdir(translations_dir):
        languages.append(i.split(".")[0])
    print(f"Available languages: {languages}")

    # Determine the language to load
    language_to_load = language if language and language in languages else None

    # If language is not available, fallback to en_US
    if language_to_load is None:
        print(f"Language '{language}' not available, defaulting to en_US")
        language_to_load = "en_US"

    # Load the translation file
    translation_file = os.path.join(translations_dir, language_to_load + ".json")
    if os.path.exists(translation_file):
        print(f"Loading translation file: {translation_file}")
        with open(translation_file, 'r') as file:
            dictionary = json.load(fp=file)["messages"]
        last_loaded_language = language_to_load
        print(f"Loaded {len(dictionary)} translations from {language_to_load}")
    else:
        print(f"Translation file not found for language: {language_to_load}")
        # Load the default "en_US" translation file as last resort
        default_file = os.path.join(translations_dir, "en_US.json")
        if os.path.exists(default_file):
            print(f"Loading fallback translation file: {default_file}")
            with open(default_file, 'r') as file:
                dictionary = json.load(fp=file)["messages"]
            last_loaded_language = "en_US"
            print(f"Loaded {len(dictionary)} translations from en_US (fallback)")
        else:
            print("DEFAULT TRANSLATION FILE 'en_US.json' NOT FOUND.")

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
        settings.update_settings_core(None, None)

        load_translations()

        # Automatically reload scripts after a delay to apply new translations (old method was unreliable)
        def delayed_reload():
            try:
                print("Auto-reloading scripts to apply new language...")
                bpy.ops.script.reload()
                print("Language changed successfully!")
            except Exception as e:
                print(f"Script reload failed: {e}")
            return None

        # Delay by 2 seconds to ensure all dialogs are closed and operations complete (Or we get crashes due to gotchaes situation)
        bpy.app.timers.register(delayed_reload, first_interval=2.0)
    else:
        print("Language unchanged, no reload needed")


def get_language_from_settings():
    # Load settings file
    try:
        with open(settings_file, encoding="utf8") as file:
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
    for lang_file in os.listdir(translations_dir):
        lang_code = lang_file.split(".")[0]
        if locale_str == lang_code:
            print(f"Found exact locale match: {lang_code}")
            return lang_code

    # Try to match by language code (first part before underscore)
    language_only = locale_str.split("_")[0].lower() if "_" in locale_str else locale_str.lower()
    for lang_file in os.listdir(translations_dir):
        lang_code = lang_file.split(".")[0]
        if lang_code.lower().startswith(language_only):
            print(f"Found language match: {lang_code}")
            return lang_code

    # Fallback to English if no match
    print(f"No language match found for locale: {locale_str}, defaulting to en_US")
    return None

@register_wrap
class DownloadTranslations(bpy.types.Operator):
    bl_idname = 'cats_translations.download_latest'
    bl_label = 'Download Latest Translations'
    bl_description = 'Download the latest translations for cats UI and internal dictionary'   
    bl_options = {'INTERNAL'}

    def execute(self, context):
        # GitHub repository and folder information
        repo_owner = "teamneoneko"
        repo_name = "Cats-Blender-Plugin-Unofficial-translations"
        branch = "5x-translations"
        folder_path = "UI%20Tanslations"

        # Construct the API URL to get the list of files in the folder
        api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{folder_path}?ref={branch}"

        try:
            # Send a GET request to the API URL
            response = requests.get(api_url)
            response.raise_for_status()  # Raise an exception if the request was unsuccessful

            # Parse the JSON response
            files = response.json()

            # Download each translation file
            for file in files:
                if file["type"] == "file" and file["name"].endswith(".json"):
                    file_url = file["download_url"]
                    file_name = file["name"]
                    file_path = os.path.join(translations_dir, file_name)

                    # Download the translation file
                    file_response = requests.get(file_url)
                    file_response.raise_for_status()

                    # Save the translation file
                    with open(file_path, 'wb') as file:
                        file.write(file_response.content)

                    print(f"Downloaded: {file_name}")

        except requests.exceptions.RequestException as e:
            print("TRANSLATIONS FILES COULD NOT BE DOWNLOADED")
            self.report({'ERROR'}, "TRANSLATIONS FILES COULD NOT BE DOWNLOADED: " + str(e))
            return {'CANCELLED'}

        print('TRANSLATIONS DOWNLOAD FINISHED')

        # Define the dictionary file path
        dictionary_file = os.path.join(resources_dir, "dictionary.json")

        # Download dictionary.json from GitHub
        print('DOWNLOAD DICTIONARY FILE')
        try:
            response = requests.get(dictionary_download_link)
            response.raise_for_status()  # Raise an exception if the request was unsuccessful
            with open(dictionary_file, 'wb') as file:
                file.write(response.content)
        except requests.exceptions.RequestException as e:
            print("DICTIONARY FILE COULD NOT BE DOWNLOADED")
            self.report({'ERROR'}, "DICTIONARY FILE COULD NOT BE DOWNLOADED: " + str(e))
            return {'CANCELLED'}
        print('DICTIONARY DOWNLOAD FINISHED')

        bpy.ops.script.reload()

        self.report({'INFO'}, "Successfully downloaded the translations and dictionary")
        return {'FINISHED'}




load_translations()
