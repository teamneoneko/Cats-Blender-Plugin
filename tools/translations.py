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
dictionary_download_link = "https://github.com/teamneoneko/Cats-Blender-Plugin-Unofficial-translations/blob/4.3-translations/dictionary.json"

def load_translations():
    global dictionary, languages
    dictionary = dict()
    languages = ["auto"]

    print("Loading translations")
    
    # Check the settings which translation to load
    language = get_language_from_settings()
    print(f"Selected language: {language}")
    
    # Set default language to "en_US" if language is None
    if language is None:
        language = "en_US"
    
    # Get all current languages
    for i in os.listdir(translations_dir):
        languages.append(i.split(".")[0])
    print(f"Available languages: {languages}")
    
    # Load the translation file
    translation_file = os.path.join(translations_dir, language + ".json")
    if os.path.exists(translation_file):
        print(f"Loading translation file: {translation_file}")
        with open(translation_file, 'r') as file:
            dictionary = json.load(fp=file)["messages"]
        print(f"Loaded {len(dictionary)} translations")
    else:
        print(f"Translation file not found for language: {language}")
        # Load the default "en_US" translation file
        default_file = os.path.join(translations_dir, "en_US.json")
        if os.path.exists(default_file):
            print(f"Loading default translation file: {default_file}")
            with open(default_file, 'r') as file:
                dictionary = json.load(fp=file)["messages"]
            print(f"Loaded {len(dictionary)} translations")
        else:
            print("Default translation file 'en_US.json' not found.")
    
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
    print("update_ui function called")
    if settings.update_settings_core(None, None):
        print("Reloading scripts")
        bpy.ops.script.reload()
    else:
        print("Settings not updated, scripts not reloaded")


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
        return locale

    return lang

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
        branch = "4.3-translations"
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
