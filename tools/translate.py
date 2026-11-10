# MIT License

import re
import os
import bpy
import copy
import json
import pathlib
import collections
import csv

from datetime import datetime, timezone
from collections import OrderedDict

from . import common as Common
from . import user_data
from . import translation_providers
from .register import register_wrap
from .. import globs
from .translations import t

from ..mmd_tools_local import translations as mmd_translations

dictionary = {}
dictionary_google = {}

curated_keys = set()

JP_CHARS_REGEX = re.compile(u'[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uff9f\u4e00-\u9faf\u3400-\u4dbf]+')
MMD_ENGLISH_NAMES_OFF = 'OFF'
MMD_ENGLISH_NAMES_FALLBACK = 'FALLBACK'  
MMD_ENGLISH_NAMES_PREFER = 'PREFER'   
SOURCE_AUTHOR = 'author'
SOURCE_TRANSLATED = 'translated'
SOURCE_NONE = 'none'
MMD_NAME_E_KEY = 'mmd_name_e'

main_dir = pathlib.Path(os.path.dirname(__file__)).parent.resolve()
resources_dir = os.path.join(str(main_dir), "resources")
BUNDLED_DICTIONARY_FILE = os.path.join(resources_dir, "dictionary.json")
LEGACY_GOOGLE_DICT_FILE = os.path.join(resources_dir, "dictionary_google.json")

DEFAULT_EXPORTS_DIR = os.path.join(pathlib.Path.home() / "Documents", "Cats")


def resolve_csv_export(operator, context, suffix):
    """Where the translation CSV for ``suffix`` (e.g. ``'_bones'``) should go."""
    if not context.scene.export_translate_csv:
        return True, None

    blend_path = bpy.data.filepath
    if not blend_path:
        operator.report({'ERROR'}, "Please save blend first!")
        return False, None

    cats_dir = bpy.path.abspath(context.scene.custom_translate_csv_export_dir) or DEFAULT_EXPORTS_DIR
    try:
        os.makedirs(cats_dir, exist_ok=True)
    except OSError:
        operator.report({'ERROR'}, "Unable to create export folder. Please manually set the export directory")
        return False, None
    if not os.access(cats_dir, os.W_OK):
        operator.report({'ERROR'}, "Unable to write to export folder. Please manually set the export directory")
        return False, None

    blend_name = os.path.splitext(os.path.basename(blend_path))[0]
    return True, os.path.join(cats_dir, blend_name + suffix + ".csv")


def write_translation_csv(export_path, header, rows):
    with open(export_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


@register_wrap
class TranslateShapekeyButton(bpy.types.Operator):
    bl_idname = 'cats_translate.shapekeys'
    bl_label = t('TranslateShapekeyButton.label')
    bl_description = t('TranslateShapekeyButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        ok, export_path = resolve_csv_export(self, context, '_shapekeys')
        if not ok:
            return {'CANCELLED'}

        saved_data = Common.SavedData()
        skip_locked_shape_keys = bpy.context.scene.skip_locked_shape_keys

        to_translate = []
        for mesh in Common.get_meshes_objects(mode=2):
            if Common.has_shapekeys(mesh):
                for shapekey in mesh.data.shape_keys.key_blocks:
                    if can_translate_shape_key(shapekey, skip_locked_shape_keys) and shapekey.name not in to_translate:
                        to_translate.append(shapekey.name)

        # Decide which keys the MMD author's English name covers before the online
        # provider runs, so those never get sent to it.
        author_names = collect_mmd_english_names(Common.get_armature())
        mode = context.scene.mmd_english_names_shapekeys
        picked, remaining = plan_author_names(to_translate, author_names, mode, translating_shapes=True)

        update_dictionary(remaining, translating_shapes=True, self=self)

        Common.update_shapekey_orders(picked)

        rows = []
        i = 0
        from_author = 0
        for mesh in Common.get_meshes_objects(mode=2):
            if Common.has_shapekeys(mesh):
                for shapekey in mesh.data.shape_keys.key_blocks:
                    if can_translate_shape_key(shapekey, skip_locked_shape_keys):
                        original_name = shapekey.name
                        shapekey.name, source = resolve_name(original_name, picked.get(original_name),
                                                             add_space=True, translating_shapes=True)
                        if source == SOURCE_NONE:
                            continue
                        i += 1
                        if source == SOURCE_AUTHOR:
                            from_author += 1
                        rows.append([mesh.name, original_name, shapekey.name, source])

        if export_path:
            write_translation_csv(export_path, ['mesh/object', 'original', 'translated', 'source'], rows)

        Common.ui_refresh()

        saved_data.load()

        self.report({'INFO'}, translation_report('TranslateShapekeyButton.success', i, from_author))
        return {'FINISHED'}


@register_wrap
class TranslateBonesButton(bpy.types.Operator):
    bl_idname = 'cats_translate.bones'
    bl_label = t('TranslateBonesButton.label')
    bl_description = t('TranslateBonesButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        ok, export_path = resolve_csv_export(self, context, '_bones')
        if not ok:
            return {'CANCELLED'}

        saved_data = Common.SavedData()

        to_translate = []
        for armature in Common.get_armature_objects():
            for bone in armature.data.bones:
                if bone.name not in to_translate:
                    to_translate.append(bone.name)

        update_dictionary(to_translate, self=self)

        rows = []
        i = 0
        for armature in Common.get_armature_objects():
            for bone in armature.data.bones:
                original_name = bone.name
                bone.name, translated = translate(bone.name)
                if translated:
                    i += 1
                    rows.append([armature.name, original_name, bone.name])

        if export_path:
            write_translation_csv(export_path, ['armature', 'original', 'translated'], rows)

        Common.ui_refresh()

        saved_data.load()

        self.report({'INFO'}, t('TranslateBonesButton.success', number=str(i)))
        return {'FINISHED'}


@register_wrap
class TranslateObjectsButton(bpy.types.Operator):
    bl_idname = 'cats_translate.objects'
    bl_label = t('TranslateObjectsButton.label')
    bl_description = t('TranslateObjectsButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        ok, export_path = resolve_csv_export(self, context, '_objects')
        if not ok:
            return {'CANCELLED'}

        saved_data = Common.SavedData()

        to_translate = []
        for obj in Common.get_objects():
            if obj.name not in to_translate:
                to_translate.append(obj.name)

        update_dictionary(to_translate, self=self)

        rows = []
        i = 0
        for obj in Common.get_objects():
            original_name = obj.name
            obj.name, translated = translate(obj.name)
            if translated:
                i += 1
                rows.append([obj.name, original_name, obj.name])

        if export_path:
            write_translation_csv(export_path, ['object', 'original', 'translated'], rows)

        Common.ui_refresh()

        saved_data.load()

        self.report({'INFO'}, t('TranslateObjectsButton.success', number=str(i)))
        return {'FINISHED'}


@register_wrap
class TranslateMaterialsButton(bpy.types.Operator):
    bl_idname = 'cats_translate.materials'
    bl_label = t('TranslateMaterialsButton.label')
    bl_description = t('TranslateMaterialsButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        ok, export_path = resolve_csv_export(self, context, '_materials')
        if not ok:
            return {'CANCELLED'}

        saved_data = Common.SavedData()
        meshes = Common.get_meshes_objects(mode=2)

        to_translate = []
        for mesh in meshes:
            for matslot in mesh.material_slots:
                if matslot.material and matslot.name not in to_translate:
                    to_translate.append(matslot.name)

        # Nothing downstream reads material names, so the MMD author's English name
        # simply wins when the user has that enabled.
        if context.scene.mmd_english_names_materials:
            author_names = collect_material_english_names(meshes)
            picked, remaining = plan_author_names(to_translate, author_names, MMD_ENGLISH_NAMES_PREFER)
        else:
            picked, remaining = {}, to_translate

        update_dictionary(remaining, self=self)

        rows = []
        i = 0
        from_author = 0
        seen = set()
        for mesh in meshes:
            for matslot in mesh.material_slots:
                material = matslot.material
                if not material or material.as_pointer() in seen:
                    continue
                seen.add(material.as_pointer())
                original_name = material.name
                material.name, source = resolve_name(original_name, picked.get(original_name))
                if source == SOURCE_NONE:
                    continue
                i += 1
                if source == SOURCE_AUTHOR:
                    from_author += 1
                rows.append([mesh.name, original_name, material.name, source])

        if export_path:
            write_translation_csv(export_path, ['mesh', 'original', 'translated', 'source'], rows)

        Common.ui_refresh()

        saved_data.load()

        self.report({'INFO'}, translation_report('TranslateMaterialsButton.success', i, from_author))
        return {'FINISHED'}

@register_wrap
class TranslateAllButton(bpy.types.Operator):
    bl_idname = 'cats_translate.all'
    bl_label = t('TranslateAllButton.label')
    bl_description = t('TranslateAllButton.desc')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        
        # Check if the export_translate_csv is checked and if the blend file is saved
        if context.scene.export_translate_csv:
            if not bpy.data.filepath:
                # Prompt the user to save the blend file
                self.report({'ERROR'}, "Please save the blend file before exporting translations.")
                return {'CANCELLED'}

        error_shown = False

        try:
            if Common.get_armature():
                bpy.ops.cats_translate.bones('INVOKE_DEFAULT')
        except RuntimeError as e:
            self.report({'ERROR'}, str(e).replace('Error: ', ''))
            error_shown = True

        try:
            bpy.ops.cats_translate.shapekeys('INVOKE_DEFAULT')
        except RuntimeError as e:
            if not error_shown:
                self.report({'ERROR'}, str(e).replace('Error: ', ''))
                error_shown = True

        try:
            bpy.ops.cats_translate.objects('INVOKE_DEFAULT')
        except RuntimeError as e:
            if not error_shown:
                self.report({'ERROR'}, str(e).replace('Error: ', ''))
                error_shown = True

        try:
            bpy.ops.cats_translate.materials('INVOKE_DEFAULT')
        except RuntimeError as e:
            if not error_shown:
                self.report({'ERROR'}, str(e).replace('Error: ', ''))
                error_shown = True

        if error_shown:
            return {'CANCELLED'}
        self.report({'INFO'}, t('TranslateAllButton.success'))
        return {'FINISHED'}


# Loads the dictionaries at the start of blender
def load_translations():
    global dictionary, curated_keys
    dictionary = OrderedDict()
    temp_dict = OrderedDict()
    dict_found = False

    # Migrate any legacy in package Google cache to the user data dir once.
    user_data.migrate_legacy_file(LEGACY_GOOGLE_DICT_FILE, user_data.google_dict_file())

    # Load internal dictionary (prefer a downloaded copy over the bundled one)
    dictionary_file = user_data.resolve_read_path(user_data.user_dictionary_file(), BUNDLED_DICTIONARY_FILE)
    try:
        with open(dictionary_file, encoding="utf8") as file:
            temp_dict = json.load(file, object_pairs_hook=collections.OrderedDict)
            dict_found = True
            # print('DICTIONARY LOADED!')
    except FileNotFoundError:
        print('DICTIONARY NOT FOUND!')
        pass
    except json.decoder.JSONDecodeError:
        print("ERROR FOUND IN DICTIONARY")
        pass

    # Everything loaded so far is curated; the provider cache merged in below is not.
    curated_keys = set(temp_dict.keys())

    try:
        with open(user_data.google_dict_file(), encoding="utf8") as file:
            global dictionary_google
            dictionary_google = json.load(file, object_pairs_hook=collections.OrderedDict)

            if 'created' not in dictionary_google \
                    or 'translations' not in dictionary_google \
                    or 'translations_full' not in dictionary_google:
                reset_google_dict()
            else:
                for name, trans in dictionary_google.get('translations').items():
                    if not name:
                        continue

                    if name in temp_dict.keys():
                        print(name, 'ALREADY IN INTERNAL DICT!')
                        continue

                    temp_dict[name] = trans
    except FileNotFoundError:
        print('GOOGLE DICTIONARY NOT FOUND!')
        reset_google_dict()
        pass
    except json.decoder.JSONDecodeError:
        print("ERROR FOUND IN GOOOGLE DICTIONARY")
        reset_google_dict()
        pass

    # Sort temp dictionary by lenght and put it into the global dict
    for key in sorted(temp_dict, key=lambda k: len(k), reverse=True):
        dictionary[key] = temp_dict[key]

    return dict_found


def update_dictionary(to_translate_list, translating_shapes=False, self=None):
    global dictionary, dictionary_google

    use_google_only = False
    if translating_shapes and bpy.context.scene.use_google_only:
        use_google_only = True

    # Check if single string is given and put it into an array
    if type(to_translate_list) is str:
        to_translate_list = [to_translate_list]

    google_input = []

    # Translate everything
    for to_translate in to_translate_list:
        length = len(to_translate)
        translated_count = 0

        to_translate = fix_jp_chars(to_translate)

        # Translate shape keys with Google Translator only, if the user chose this
        if use_google_only:
            # If name doesn't contain any jp chars, don't translate
            if not JP_CHARS_REGEX.search(to_translate):
                continue

            translated = False
            for key, value in dictionary_google.get('translations_full').items():
                if to_translate == key and value:
                    translated = True

            if not translated:
                google_input.append(to_translate)

        # Translate with internal dictionary
        else:
            for key, value in dictionary.items():
                if key in to_translate:
                    if value:
                        to_translate = to_translate.replace(key, value)
                    else:
                        continue

                    # Check if string is fully translated
                    translated_count += len(key)
                    if translated_count >= length:
                        break

            # If not fully translated, translate the rest with Google
            if translated_count < length:
                match = JP_CHARS_REGEX.findall(to_translate)
                if match:
                    for name in match:
                        if name not in google_input and name not in dictionary.keys():
                            google_input.append(name)

    if not google_input:
        # print('NO GOOGLE TRANSLATIONS')
        return

    # Fill the remaining gaps with the user's selected online provider.
    provider = translation_providers.get_active_provider()

    if not provider.is_available():
        # The chosen provider can't run right now (no `requests`, missing API key, or
        # offline). Cats already applied everything the local dictionary could, so stop
        # gracefully instead of erroring out.
        print(f'ONLINE TRANSLATION UNAVAILABLE ({provider.name}): skipping online translation.')
        if self:
            if translation_providers.online_access_allowed():
                self.report({'WARNING'}, t('update_dictionary.error.cantConnect'))
            else:
                self.report({'WARNING'}, t('online_access.disabled'))
        return

    # Translate the rest with the online provider. Providers fail soft internally
    # (returning the original text on error), so this batch call never raises for a
    # single bad item; we still guard the whole call defensively.
    print(f'ONLINE DICT UPDATE via {provider.name}!')
    try:
        raw_translations = provider.translate_batch(google_input, source_lang='ja', target_lang='en')
    except Exception as e:
        print('ONLINE TRANSLATE ERROR:', str(e))
        if self:
            self.report({'ERROR'}, t('update_dictionary.error.errorMsg') + t('update_dictionary.error.catsTranslated') + '\n' + str(e))
        return

    translations = [(text or '').strip() for text in raw_translations]

    # Update the dictionaries
    for i, translation in enumerate(translations):
        name = google_input[i]

        # Provider failed soft (returned the original, untranslated Japanese) — don't
        # poison the dictionary/cache with a non-translation.
        if not translation or translation == name:
            continue

        if use_google_only:
            dictionary_google['translations_full'][name] = translation
        else:
            # Capitalize words
            translation_words = translation.split(' ')
            translation_words = [word.capitalize() for word in translation_words]
            translation = ' '.join(translation_words)

            dictionary[name] = translation
            dictionary_google['translations'][name] = translation

        print(google_input[i], '->', translation)

    # Sort dictionary
    temp_dict = copy.deepcopy(dictionary)
    dictionary = OrderedDict()
    for key in sorted(temp_dict, key=lambda k: len(k), reverse=True):
        dictionary[key] = temp_dict[key]

    # Save the google dict locally
    save_google_dict()

    print('DICTIONARY UPDATE SUCCEEDED!')
    return


def translate(to_translate, add_space=False, translating_shapes=False):
    global dictionary

    pre_translation = to_translate
    length = len(to_translate)
    translated_count = 0

    # Figure out whether to use google only or not
    use_google_only = False
    if translating_shapes and bpy.context.scene.use_google_only:
        use_google_only = True

    # Add space for shape keys
    addition = ''
    if add_space:
        addition = ' '

    # Convert half chars into full chars
    to_translate = fix_jp_chars(to_translate)

    # Translate shape keys with Google Translator only, if the user chose this
    if use_google_only:
        for key, value in dictionary_google.get('translations_full').items():
            if to_translate == key and value:
                to_translate = value

    # Translate with internal dictionary
    else:
        for key, value in dictionary.items():
            if key in to_translate:
                # If string is empty, don't replace it. This will be done at the end
                if not value:
                    continue

                to_translate = to_translate.replace(key, addition + value)

                # Check if string is fully translated
                translated_count += len(key)
                if translated_count >= length:
                    break

    to_translate = to_translate.replace('.L', '_L').replace('.R', '_R').replace('  ', ' ').replace('し', '').replace('っ', '').strip()

    # print('"' + pre_translation + '"')
    # print('"' + to_translate + '"')

    return to_translate, pre_translation != to_translate


def fix_jp_chars(name):
    for values in mmd_translations.jp_half_to_full_tuples:
        if values[0] in name:
            name = name.replace(values[0], values[1])
    return name


# mmd_tools imports both PMX names: the Japanese one becomes the datablock name and
# the author's English one lands in mmd_morph.name_e / mmd_material.name_e. The
# functions below let Translate consult those instead of throwing them away.
def has_japanese(text):
    return bool(JP_CHARS_REGEX.search(text or ''))


def is_usable_english_name(name_e, name_j=''):
    """Whether an author's English name is worth using at all."""
    name_e = (name_e or '').strip()
    if not name_e or name_e == (name_j or '').strip():
        return False
    try:
        name_e.encode('ascii')
    except UnicodeEncodeError:
        return False
    return True


def _filter_english_names(raw_names):
    """{name_j: name_e} -> the usable subset, keyed both raw and half->full width."""
    counts = collections.Counter((name_e or '').strip() for name_e in raw_names.values())
    usable = {}
    for name_j, name_e in raw_names.items():
        if not is_usable_english_name(name_e, name_j):
            continue
        name_e = name_e.strip()
        if counts[name_e] > 1:
            continue
        usable[name_j] = name_e
        usable[fix_jp_chars(name_j)] = name_e
    return usable


def _find_mmd_root(armature):
    root = getattr(armature, 'parent', None)
    if root and getattr(root, 'mmd_type', '') == 'ROOT':
        return root.mmd_root
    return None


def _raw_mmd_morph_english_names(mmd_root):
    names = {}
    for collection in ('vertex_morphs', 'bone_morphs'):
        for morph in getattr(mmd_root, collection, []):
            if morph.name:
                names[morph.name] = morph.name_e
    return names


def store_mmd_english_names(armature):
    """Stash the author's English morph names on the armature.

    Fix Model deletes the MMD root empty, and mmd_root.vertex_morphs goes with it.
    Called right before that delete so Translate Shape Keys can still find the names
    afterwards. Stored unfiltered; usability rules are applied on read.
    """
    mmd_root = _find_mmd_root(armature)
    if mmd_root is None:
        return

    names = {name_j: name_e for name_j, name_e in _raw_mmd_morph_english_names(mmd_root).items() if name_e}
    if not names:
        return

    sys_props = armature.bl_system_properties_get(do_create=True)
    if sys_props is None:
        return
    custom_data = sys_props.get('CUSTOM')
    custom_data = custom_data.to_dict() if hasattr(custom_data, 'to_dict') else dict(custom_data or {})
    custom_data[MMD_NAME_E_KEY] = names
    sys_props['CUSTOM'] = custom_data


def collect_mmd_english_names(armature):
    """Usable author English names for this armature's morphs, keyed by Japanese name.

    Reads the live mmd_root while it exists, otherwise the snapshot Fix Model stored.
    Returns an empty dict for non-MMD models.
    """
    if armature is None:
        return {}

    mmd_root = _find_mmd_root(armature)
    if mmd_root is not None:
        return _filter_english_names(_raw_mmd_morph_english_names(mmd_root))

    sys_props = armature.bl_system_properties_get()
    custom_data = sys_props.get('CUSTOM') if sys_props is not None else None
    stored = custom_data.get(MMD_NAME_E_KEY) if custom_data else None
    if not stored:
        return {}
    return _filter_english_names({str(name_j): str(name_e) for name_j, name_e in stored.items()})


def collect_material_english_names(meshes):
    """Usable author English names for the materials on these meshes, keyed by name_j.

    Materials carry their own mmd_material.name_j / name_e, so no snapshot is needed.
    """
    raw_names = {}
    for mesh in meshes:
        for slot in mesh.material_slots:
            material = slot.material
            mmd_material = getattr(material, 'mmd_material', None)
            if mmd_material is not None and mmd_material.name_j:
                raw_names[mmd_material.name_j] = mmd_material.name_e
    return _filter_english_names(raw_names)


def dictionary_covers(name, translating_shapes=False):
    """Whether the curated dictionary alone leaves no Japanese in this name.

    Mirrors translate() but ignores provider-cache entries, so the answer is the same
    no matter which models were translated before. With "Skip Dictionary" on for shape
    keys the dictionary is out of the picture, so nothing counts as covered.
    """
    if translating_shapes and bpy.context.scene.use_google_only:
        return False

    name = fix_jp_chars(name)
    for key, value in dictionary.items():
        if key in curated_keys and value and key in name:
            name = name.replace(key, value)
    name = name.replace('し', '').replace('っ', '')
    return not has_japanese(name)


def pick_author_name(name, author_names, mode, translating_shapes=False):
    """The author's English name to use for `name`, or None to translate as usual.

    Decide this BEFORE update_dictionary() runs: names the author resolves must stay
    out of the online provider batch, and once the provider's results are merged into
    the dictionary the coverage check can no longer tell the two apart.
    """
    if mode == MMD_ENGLISH_NAMES_OFF or not author_names:
        return None

    author_name = author_names.get(name) or author_names.get(fix_jp_chars(name))
    if not author_name:
        # Blender may have suffixed a colliding datablock name; the PMX name has none.
        base_name = re.sub(r'\.\d{3}$', '', name)
        if base_name != name:
            author_name = author_names.get(base_name) or author_names.get(fix_jp_chars(base_name))
    if not author_name:
        return None

    if mode == MMD_ENGLISH_NAMES_PREFER:
        return author_name
    return None if dictionary_covers(name, translating_shapes) else author_name


def resolve_name(name, author_name=None, add_space=False, translating_shapes=False):
    """Final name for a datablock: the picked author name, else the dictionary result.

    Returns (new_name, source) with source one of SOURCE_AUTHOR / SOURCE_TRANSLATED /
    SOURCE_NONE. Author names get only the .L/.R swap translate() applies; the
    Japanese-specific cleanup makes no sense on an English string.
    """
    if author_name:
        new_name = author_name.strip().replace('.L', '_L').replace('.R', '_R')
        return new_name, SOURCE_AUTHOR

    new_name, changed = translate(name, add_space=add_space, translating_shapes=translating_shapes)
    return new_name, SOURCE_TRANSLATED if changed else SOURCE_NONE


def plan_author_names(names, author_names, mode, translating_shapes=False):
    """{name: author name or None} for a batch, plus the names still needing the dictionary."""
    picked = {}
    remaining = []
    for name in names:
        if name in picked:
            continue
        picked[name] = pick_author_name(name, author_names, mode, translating_shapes)
        if picked[name] is None:
            remaining.append(name)
    return picked, remaining


def reset_google_dict():
    global dictionary_google
    dictionary_google = OrderedDict()

    now_utc = datetime.now(timezone.utc).strftime(globs.time_format)

    dictionary_google['created'] = now_utc
    dictionary_google['translations'] = {}
    dictionary_google['translations_full'] = {}

    save_google_dict()
    print('GOOGLE DICT RESET')


def save_google_dict():
    try:
        with open(user_data.google_dict_file(ensure_dir=True), 'w', encoding="utf8") as outfile:
            json.dump(dictionary_google, outfile, ensure_ascii=False, indent=4)
    except OSError as e:
        print(f"CATS: could not save Google translation cache to {user_data.google_dict_file()}: {e}")


def translation_report(success_key, translated, from_author):
    """Success message, noting how many names came from the MMD author when any did."""
    message = t(success_key, number=str(translated))
    if from_author:
        message += ' ' + t('Translate.fromAuthor', number=str(from_author))
    return message


# Check if shape key meets translation conditions
def can_translate_shape_key(shapekey, skip_locked_shape_keys):
    if skip_locked_shape_keys:
        if not shapekey.lock_shape:
            if 'vrc.' not in shapekey.name:
                return True
    else:
        if 'vrc.' not in shapekey.name:
            return True
    return False
