# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import filecmp
import logging
import os
import shutil

import bpy
from bpy.types import Operator
from opencc import OpenCC

from ..core.material import FnMaterial
from ..core.model import FnModel
from ..preferences import get_additional_unallowed_chars, get_replacement_char

cc_s2t = OpenCC("s2t")

# The opencc-python-reimplemented wheel ships the JPVariants dictionary but not the t2jp
# configuration, so load the bundled configuration by absolute path. OpenCC appends ".json"
# to the given name, so the path is passed without the extension.
_T2JP_CONFIG_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "opencc", "t2jp"))
cc_t2jp = OpenCC(_T2JP_CONFIG_PATH)


def _find_additional_unallowed_chars(name: str, unallowed: str) -> list[str]:
    """Return sorted list of unallowed characters found in name (deduplicated)."""
    return sorted({ch for ch in unallowed if ch in name})


def _replace_additional_unallowed_chars(name: str, unallowed: str, replacement: str) -> str:
    """Replace each unallowed character in name with replacement (or remove if empty)."""
    for ch in unallowed:
        name = name.replace(ch, replacement)
    return name


# Scene property to store validation results
def register():
    bpy.types.Scene.mmd_validation_results = bpy.props.StringProperty(
        name="Validation Results",
        default="",
    )


def unregister():
    if hasattr(bpy.types.Scene, "mmd_validation_results"):
        del bpy.types.Scene.mmd_validation_results


def log_message(prefix, message, level="INFO"):
    """Log message with prefix for each line at the specified level.

    Args:
        prefix (str): Prefix for the log message.
        message (str): Message to log.
        level (str): Log level ('INFO', 'WARNING', 'ERROR').
    """
    logger = logging.getLogger()
    original_level = logger.level
    # Set to DEBUG to ensure all messages are output.
    logger.setLevel(logging.DEBUG)

    try:
        level = level.upper()
        for line in message.split("\n"):
            if level == "WARNING":
                logging.warning("[%s] %s", prefix, line)
            elif level == "ERROR":
                logging.error("[%s] %s", prefix, line)
            else:  # Default to INFO
                logging.info("[%s] %s", prefix, line)
    finally:
        logger.setLevel(original_level)


def force_ui_update(context):
    """Force all areas in all windows to redraw."""
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


class MMDModelValidateModel(Operator):
    """Check MMD model name for encoding issues"""

    bl_idname = "mmd_tools_local.validate_model"
    bl_label = "Validate Model Name"
    bl_description = "Check MMD model name and english name for encoding issues"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        root = FnModel.find_root_object(context.active_object)
        if root is None:
            self.report({"ERROR"}, "No MMD model selected")
            log_message("MMD Validation", "No MMD model selected", "ERROR")
            return {"CANCELLED"}

        issues = []
        mmd_root = root.mmd_root

        # Check Name
        try:
            mmd_root.name.encode("cp932")
        except UnicodeEncodeError:
            issues.append(f"Model Name '{mmd_root.name}' contains characters that cannot be encoded in cp932")

        # Check Name (English)
        try:
            mmd_root.name_e.encode("cp932")
        except UnicodeEncodeError:
            issues.append(f"Model English Name '{mmd_root.name_e}' contains characters that cannot be encoded in cp932")

        # Check additional unallowed characters
        unallowed = get_additional_unallowed_chars("model")
        if unallowed:
            for field, value in (("Model Name", mmd_root.name), ("Model English Name", mmd_root.name_e)):
                found = _find_additional_unallowed_chars(value, unallowed)
                if found:
                    issues.append(f"{field} '{value}' contains additional unallowed characters: {found}")

        results = "\n".join(issues) or "No model issues found"
        context.scene.mmd_validation_results = results
        log_level = "WARNING" if issues else "INFO"
        log_message("MMD Model Name Validation", results, log_level)

        return {"FINISHED"}


class MMDModelValidateBones(Operator):
    """Check MMD model bones for encoding issues and name length limits"""

    bl_idname = "mmd_tools_local.validate_bones"
    bl_label = "Validate Bone Limits"
    bl_description = "Check MMD model bones for encoding issues and name length limits"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        root = FnModel.find_root_object(context.active_object)
        if root is None:
            self.report({"ERROR"}, "No MMD model selected")
            log_message("MMD Validation", "No MMD model selected", "ERROR")
            return {"CANCELLED"}

        armature = FnModel.find_armature_object(root)
        if armature is None:
            self.report({"ERROR"}, "No armature found in model")
            log_message("MMD Validation", "No armature found in model", "ERROR")
            return {"CANCELLED"}

        issues = []
        # Set to track bone names for duplicate checking
        bone_names = set()

        for pose_bone in armature.pose.bones:
            # Skip shadow bones
            is_shadow = getattr(pose_bone, "is_mmd_shadow_bone", False) is True
            if is_shadow:
                continue

            name_j = pose_bone.mmd_bone.name_j

            # Check for duplicates
            if name_j in bone_names:
                issues.append(f"Duplicate bone name: '{name_j}'")
            else:
                bone_names.add(name_j)

            # Check cp932 encoding and length
            try:
                encoded_name = name_j.encode("cp932")
                if len(encoded_name) > 15:
                    issues.append(f"Bone '{name_j}' exceeds 15 bytes in cp932")
            except UnicodeEncodeError:
                issues.append(f"Bone '{name_j}' contains characters that cannot be encoded in cp932")

        # Check additional unallowed characters
        unallowed = get_additional_unallowed_chars("bone")
        if unallowed:
            for pose_bone in armature.pose.bones:
                if getattr(pose_bone, "is_mmd_shadow_bone", False):
                    continue
                name_j = pose_bone.mmd_bone.name_j
                found = _find_additional_unallowed_chars(name_j, unallowed)
                if found:
                    issues.append(f"Bone '{name_j}' contains additional unallowed characters: {found}")

        results = "\n".join(issues) or "No bone issues found"
        context.scene.mmd_validation_results = results
        log_level = "WARNING" if issues else "INFO"
        log_message("MMD Bone Validation", results, log_level)

        return {"FINISHED"}


class MMDModelValidateMorphs(Operator):
    """Check MMD model morphs for encoding issues, name length limits, and duplicate names"""

    bl_idname = "mmd_tools_local.validate_morphs"
    bl_label = "Validate Morphs"
    bl_description = "Check MMD model morphs for encoding issues, name length limits, and duplicate names"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        root = FnModel.find_root_object(context.active_object)
        if root is None:
            self.report({"ERROR"}, "No MMD model selected")
            log_message("MMD Validation", "No MMD model selected", "ERROR")
            return {"CANCELLED"}

        issues = []
        morph_names = set()

        morph_types = ["vertex_morphs", "bone_morphs", "material_morphs", "uv_morphs", "group_morphs"]
        for morph_type in morph_types:
            if not hasattr(root.mmd_root, morph_type):
                continue

            morphs = getattr(root.mmd_root, morph_type)
            for morph in morphs:
                if morph.name in morph_names:
                    issues.append(f"Duplicate morph name: '{morph.name}'")
                else:
                    morph_names.add(morph.name)

                try:
                    encoded_name = morph.name.encode("cp932")
                    if len(encoded_name) > 15:
                        issues.append(f"Morph '{morph.name}' name too long (exceeds 15 bytes in cp932)")
                except UnicodeEncodeError:
                    issues.append(f"Morph '{morph.name}' contains characters that cannot be encoded in cp932")

        # Check additional unallowed characters
        unallowed = get_additional_unallowed_chars("morph")
        if unallowed:
            for morph_type in morph_types:
                if not hasattr(root.mmd_root, morph_type):
                    continue
                for morph in getattr(root.mmd_root, morph_type):
                    found = _find_additional_unallowed_chars(morph.name, unallowed)
                    if found:
                        issues.append(f"Morph '{morph.name}' contains additional unallowed characters: {found}")

        results = "\n".join(issues) or "No morph issues found"
        context.scene.mmd_validation_results = results
        log_level = "WARNING" if issues else "INFO"
        log_message("MMD Morph Validation", results, log_level)

        return {"FINISHED"}


class MMDModelValidateTextures(Operator):
    """Check MMD model textures for missing files, path conflicts, and duplicate filenames"""

    bl_idname = "mmd_tools_local.validate_textures"
    bl_label = "Validate Textures"
    bl_description = "Check MMD model textures for missing files, path conflicts, and duplicate filenames"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        root = FnModel.find_root_object(context.active_object)
        if root is None:
            self.report({"ERROR"}, "No MMD model selected")
            log_message("MMD Validation", "No MMD model selected", "ERROR")
            return {"CANCELLED"}

        issues = []
        texture_paths = {}
        texture_names = {}
        filename_conflicts = {}
        missing_files = {}

        for material in FnModel.iterate_unique_materials(root):
            if not material.node_tree:
                continue

            for node in material.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    img = node.image
                    if not img.filepath:
                        continue

                    # Check for file existence on disk
                    abs_path = bpy.path.abspath(img.filepath)
                    if not os.path.exists(abs_path) and not img.packed_file:
                        material_name = material.name
                        # Store missing files by material for better reporting
                        if material_name not in missing_files:
                            missing_files[material_name] = []
                        missing_files[material_name].append((img.name, img.filepath))

                    # Check for different textures with same path
                    if img.filepath in texture_paths:
                        if img.name != texture_paths[img.filepath]:
                            issues.append(f"Different textures with same path: '{img.filepath}'")
                    else:
                        texture_paths[img.filepath] = img.name

                    # Check for filename conflicts in different directories
                    img_filename = os.path.basename(img.filepath)
                    if img_filename in texture_names:
                        for existing_path in texture_names[img_filename]:
                            if existing_path != img.filepath:
                                if img_filename not in filename_conflicts:
                                    filename_conflicts[img_filename] = set()
                                filename_conflicts[img_filename].add(existing_path)
                                filename_conflicts[img_filename].add(img.filepath)
                        texture_names[img_filename].append(img.filepath)
                    else:
                        texture_names[img_filename] = [img.filepath]

        # Format conflict messages
        for filename, paths in filename_conflicts.items():
            conflict_msg = f"Texture filename conflict: '{filename}' found in:\n"
            path_list = list(paths)
            for idx, path in enumerate(path_list):
                if idx < len(path_list) - 1:
                    conflict_msg += f"  {idx + 1}. {path}\n"
                else:
                    conflict_msg += f"  {idx + 1}. {path}"
            issues.append(conflict_msg)

        # Check additional unallowed characters in texture filenames (disk path only, extension excluded)
        unallowed = get_additional_unallowed_chars("texture")
        if unallowed:
            seen_filepaths = set()
            for material in FnModel.iterate_unique_materials(root):
                if not material.node_tree:
                    continue
                for node in material.node_tree.nodes:
                    if node.type != "TEX_IMAGE" or not node.image or not node.image.filepath:
                        continue
                    img = node.image
                    if img.filepath in seen_filepaths:
                        continue
                    seen_filepaths.add(img.filepath)

                    basename = os.path.basename(bpy.path.abspath(img.filepath))
                    stem, ext = os.path.splitext(basename)
                    found = _find_additional_unallowed_chars(stem, unallowed)
                    if found:
                        issues.append(f"Texture '{basename}' stem contains additional unallowed characters: {', '.join(repr(c) for c in found)}")

        # Format missing file messages
        if missing_files:
            issues.append("MISSING TEXTURE FILES:")
            for material_name, missing_list in missing_files.items():
                issues.append(f"Material '{material_name}' has missing textures:")
                for img_name, filepath in missing_list:
                    issues.append(f"  - '{img_name}' at path: '{filepath}'")

        results = "\n".join(issues) or "No texture issues found"
        context.scene.mmd_validation_results = results
        log_level = "WARNING" if issues else "INFO"
        log_message("MMD Texture Validation", results, log_level)

        return {"FINISHED"}


# Fix operators
class MMDModelFixModelIssues(Operator):
    """Automatically fix model name encoding issues"""

    bl_idname = "mmd_tools_local.fix_model_issues"
    bl_label = "Fix Model Issues"
    bl_description = "Fix model name encoding issues automatically"
    bl_options = {"REGISTER", "UNDO"}

    def _fix_text(self, text, default_text="New MMD Model"):
        # Check if needs fixing
        try:
            text.encode("cp932")
            return text, False
        except UnicodeEncodeError:
            pass

        # Convert/remove non-Japanese characters
        converted_name = cc_s2t.convert(text)
        converted_name = cc_t2jp.convert(converted_name)

        new_name = ""
        for char in converted_name:
            try:
                char.encode("cp932")
                new_name += char
            except UnicodeEncodeError:
                continue

        # If name becomes empty after filtering, use default
        if not new_name:
            new_name = default_text

        return new_name, True

    def execute(self, context):
        root = FnModel.find_root_object(context.active_object)
        if root is None:
            self.report({"ERROR"}, "No MMD model selected")
            log_message("MMD Fix", "No MMD model selected", "ERROR")
            return {"CANCELLED"}

        fixed = []
        mmd_root = root.mmd_root

        # Fix Name
        new_name, was_fixed = self._fix_text(mmd_root.name, "New MMD Model")
        if was_fixed and new_name != mmd_root.name:
            old_name = mmd_root.name
            mmd_root.name = new_name
            fixed.append(f"Fixed Model Name: '{old_name}' -> '{new_name}'")

        # Fix English Name
        new_name_e, was_fixed_e = self._fix_text(mmd_root.name_e, "New MMD Model")
        if was_fixed_e and new_name_e != mmd_root.name_e:
            old_name_e = mmd_root.name_e
            mmd_root.name_e = new_name_e
            fixed.append(f"Fixed Model English Name: '{old_name_e}' -> '{new_name_e}'")

        # Fix additional unallowed characters
        unallowed = get_additional_unallowed_chars("model")
        if unallowed:
            replacement = get_replacement_char()
            for attr in ("name", "name_e"):
                old_val = getattr(mmd_root, attr)
                new_val = _replace_additional_unallowed_chars(old_val, unallowed, replacement)
                if new_val != old_val:
                    setattr(mmd_root, attr, new_val)
                    label = "Model Name" if attr == "name" else "Model English Name"
                    fixed.append(f"Fixed {label} additional unallowed chars: '{old_val}' -> '{new_val}'")

        results = "\n".join(fixed) if fixed else "No model issues to fix"
        context.scene.mmd_validation_results = results
        log_message("MMD Model Name Fix", results, "INFO")

        force_ui_update(context)
        return {"FINISHED"}


class MMDModelFixBoneIssues(Operator):
    """Automatically fix bone name encoding and length issues"""

    bl_idname = "mmd_tools_local.fix_bone_issues"
    bl_label = "Fix Bone Issues"
    bl_description = "Fix bone name encoding issues automatically"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        root = FnModel.find_root_object(context.active_object)
        if root is None:
            self.report({"ERROR"}, "No MMD model selected")
            log_message("MMD Fix", "No MMD model selected", "ERROR")
            return {"CANCELLED"}

        armature = FnModel.find_armature_object(root)
        if armature is None:
            self.report({"ERROR"}, "No armature found in model")
            log_message("MMD Fix", "No armature found in model", "ERROR")
            return {"CANCELLED"}

        fixed = []
        name_counts = {}
        processed_names = set()

        # First collect all names and mark duplicates
        for pose_bone in armature.pose.bones:
            if getattr(pose_bone, "is_mmd_shadow_bone", False):
                continue
            name_j = pose_bone.mmd_bone.name_j
            name_counts[name_j] = name_counts.get(name_j, 0) + 1

        # Process all bones - fix both length and duplicates
        for pose_bone in armature.pose.bones:
            if getattr(pose_bone, "is_mmd_shadow_bone", False):
                continue

            original_name = pose_bone.mmd_bone.name_j

            # Check if name is too long in cp932
            name_too_long = False
            has_non_japanese = False
            try:
                encoded = original_name.encode("cp932")
                name_too_long = len(encoded) > 15
            except UnicodeEncodeError:
                has_non_japanese = True

            is_duplicate = original_name in processed_names or name_counts.get(original_name, 0) > 1

            # Only process bones that need fixing
            if not (name_too_long or has_non_japanese or is_duplicate):
                processed_names.add(original_name)
                continue

            # First convert/remove non-Japanese characters
            converted_name = cc_s2t.convert(original_name)
            converted_name = cc_t2jp.convert(converted_name)

            new_name = ""
            for char in converted_name:
                try:
                    char.encode("cp932")
                    new_name += char
                except UnicodeEncodeError:
                    continue

            # If name becomes empty after filtering, use a default name
            if not new_name:
                new_name = "bone"

            # Generate a unique name within the 15-byte CP932 limit
            suffix = 1
            while True:
                suffix_str = "" if suffix == 1 else str(suffix)
                max_bytes = 15 - len(suffix_str)
                temp_base = new_name
                while temp_base:
                    try:
                        if len(temp_base.encode("cp932")) <= max_bytes:
                            break
                        temp_base = temp_base[:-1]
                    except UnicodeEncodeError:
                        temp_base = temp_base[:-1]
                test_name = f"{temp_base}{suffix_str}"
                if test_name not in processed_names:
                    final_name = test_name
                    break
                suffix += 1

            # Apply the final name and update processed_names
            pose_bone.mmd_bone.name_j = final_name
            processed_names.add(final_name)

            # Only add one message per bone, showing the original and final name
            if original_name != final_name:
                fixed.append(f"Fixed bone name: '{original_name}' -> '{final_name}'")

        # Fix additional unallowed characters
        unallowed = get_additional_unallowed_chars("bone")
        if unallowed:
            replacement = get_replacement_char()
            # Collect names of bones that won't be modified, as the baseline for uniqueness check
            additional_used_names = set()
            for pb in armature.pose.bones:
                if getattr(pb, "is_mmd_shadow_bone", False):
                    continue
                additional_used_names.add(pb.mmd_bone.name_j)

            for pose_bone in armature.pose.bones:
                if getattr(pose_bone, "is_mmd_shadow_bone", False):
                    continue
                old_name = pose_bone.mmd_bone.name_j
                new_name = _replace_additional_unallowed_chars(old_name, unallowed, replacement)
                if new_name == old_name:
                    continue

                # Resolve collision
                additional_used_names.discard(old_name)
                candidate = new_name
                suffix = 2
                while candidate in additional_used_names:
                    candidate = f"{new_name}{suffix}"
                    suffix += 1
                pose_bone.mmd_bone.name_j = candidate
                additional_used_names.add(candidate)
                fixed.append(f"Fixed bone additional unallowed chars: '{old_name}' -> '{candidate}'")

        results = "\n".join(fixed) if fixed else "No bone issues to fix"
        context.scene.mmd_validation_results = results
        log_message("MMD Bone Fix", results, "INFO")

        force_ui_update(context)
        return {"FINISHED"}


class MMDModelFixMorphIssues(Operator):
    """Automatically fix morph name encoding, length and duplicate issues"""

    bl_idname = "mmd_tools_local.fix_morph_issues"
    bl_label = "Fix Morph Issues"
    bl_description = "Fix morph name issues automatically"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        root = FnModel.find_root_object(context.active_object)
        if root is None:
            self.report({"ERROR"}, "No MMD model selected")
            log_message("MMD Fix", "No MMD model selected", "ERROR")
            return {"CANCELLED"}

        fixed = []
        processed_names = set()
        morph_types = ["vertex_morphs", "group_morphs", "bone_morphs", "material_morphs", "uv_morphs"]

        for morph_type in morph_types:
            if not hasattr(root.mmd_root, morph_type):
                continue

            morphs = getattr(root.mmd_root, morph_type)
            for morph in morphs:
                original_name = morph.name

                # Check if name is too long in cp932
                name_too_long = False
                has_non_japanese = False
                try:
                    encoded = original_name.encode("cp932")
                    name_too_long = len(encoded) > 15
                except UnicodeEncodeError:
                    has_non_japanese = True

                # Skip if name is valid length and not a duplicate
                if not (name_too_long or has_non_japanese) and original_name not in processed_names:
                    processed_names.add(original_name)
                    continue

                # First convert/remove non-Japanese characters
                converted_name = cc_s2t.convert(original_name)
                converted_name = cc_t2jp.convert(converted_name)

                new_name = ""
                for char in converted_name:
                    try:
                        char.encode("cp932")
                        new_name += char
                    except UnicodeEncodeError:
                        continue

                # If name becomes empty after filtering, use a default name
                if not new_name:
                    new_name = "morph"

                # Generate a unique name within the 15-byte CP932 limit
                suffix = 1
                while True:
                    suffix_str = "" if suffix == 1 else str(suffix)
                    max_bytes = 15 - len(suffix_str)
                    temp_base = new_name
                    while temp_base:
                        try:
                            if len(temp_base.encode("cp932")) <= max_bytes:
                                break
                            temp_base = temp_base[:-1]
                        except UnicodeEncodeError:
                            temp_base = temp_base[:-1]
                    test_name = f"{temp_base}{suffix_str}"
                    if test_name not in processed_names:
                        final_name = test_name
                        break
                    suffix += 1

                # Apply the final name and update processed_names
                morph.name = final_name
                processed_names.add(final_name)

                # Only add one message per morph, showing the original and final name
                if original_name != final_name:
                    fixed.append(f"Fixed morph name: '{original_name}' -> '{final_name}'")

        # Fix additional unallowed characters
        unallowed = get_additional_unallowed_chars("morph")
        if unallowed:
            replacement = get_replacement_char()
            # Collect all current morph names as baseline
            additional_used_names = set()
            for mt in morph_types:
                if hasattr(root.mmd_root, mt):
                    additional_used_names.update(m.name for m in getattr(root.mmd_root, mt))

            for morph_type in morph_types:
                if not hasattr(root.mmd_root, morph_type):
                    continue
                for morph in getattr(root.mmd_root, morph_type):
                    old_name = morph.name
                    new_name = _replace_additional_unallowed_chars(old_name, unallowed, replacement)
                    if new_name == old_name:
                        continue

                    additional_used_names.discard(old_name)
                    candidate = new_name
                    suffix = 2
                    while candidate in additional_used_names:
                        candidate = f"{new_name}{suffix}"
                        suffix += 1
                    morph.name = candidate
                    additional_used_names.add(candidate)
                    fixed.append(f"Fixed morph additional unallowed chars: '{old_name}' -> '{candidate}'")

        results = "\n".join(fixed) if fixed else "No morph issues to fix"
        context.scene.mmd_validation_results = results
        log_message("MMD Morph Fix", results, "INFO")

        force_ui_update(context)
        return {"FINISHED"}


class MMDModelFixTextureIssues(Operator):
    """Automatically fix texture name and path issues"""

    bl_idname = "mmd_tools_local.fix_texture_issues"
    bl_label = "Fix Texture Issues"
    bl_description = "Fix texture name and path issues automatically"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        root = FnModel.find_root_object(context.active_object)
        if root is None:
            self.report({"ERROR"}, "No MMD model selected")
            log_message("MMD Fix", "No MMD model selected", "ERROR")
            return {"CANCELLED"}

        fixed = []
        missing_textures = []
        fixed_toon_textures = []  # Track fixed toon textures
        fixed_material_image_pairs = set()  # Track which material-image pairs have been fixed

        # First pass: collect all textures and identify missing ones
        texture_filepaths = {}  # Maps filepath to a list of image objects using it
        filepath_by_filename = {}  # Maps filename to a set of filepaths
        toon_textures_to_fix = []  # Missing toon textures that need fixing

        for material in FnModel.iterate_unique_materials(root):
            if not material.node_tree:
                continue

            for node in material.node_tree.nodes:
                if node.type != "TEX_IMAGE" or not node.image or not node.image.filepath:
                    continue

                img = node.image
                filepath = img.filepath

                # Track images using this filepath
                if filepath not in texture_filepaths:
                    texture_filepaths[filepath] = []
                if img not in texture_filepaths[filepath]:
                    texture_filepaths[filepath].append(img)

                # Track filepaths by filename
                filename = os.path.basename(filepath)
                if filename not in filepath_by_filename:
                    filepath_by_filename[filename] = set()
                filepath_by_filename[filename].add(filepath)

                # Check for missing files
                abs_path = bpy.path.abspath(filepath)
                if not os.path.exists(abs_path) and not img.packed_file:
                    item = (material.name, img.name, filepath, node.name)
                    missing_textures.append(item)
                    # Immediately identify if it's a toon texture that needs fixing
                    if node.name == "mmd_toon_tex":
                        toon_textures_to_fix.append(item)

        # Second pass: Fix toon textures first
        if toon_textures_to_fix:
            fixed.append("FIXED MISSING TOON TEXTURES:")

            for material_name, img_name, filepath, _ in toon_textures_to_fix:
                filename = os.path.basename(filepath).lower()
                material = next((m for m in bpy.data.materials if m.name == material_name), None)

                if material:
                    mmd_mat = material.mmd_material

                    # Check if it's in the shared_toon_texture list (toon01.bmp ~ toon10.bmp)
                    if filename.startswith("toon") and filename.endswith(".bmp"):
                        try:
                            # Extract number from filename (e.g., "toon01.bmp" -> 1)
                            toon_num = int(filename[4:6]) if len(filename) >= 6 else 0

                            if 1 <= toon_num <= 10:
                                # It's a standard shared toon, set to use shared version
                                mmd_mat.is_shared_toon_texture = True
                                mmd_mat.shared_toon_texture = toon_num - 1  # 0-based index
                                fixed_toon_textures.append(f"Fixed toon texture in '{material_name}': '{filename}' -> Using shared toon{toon_num:02d}.bmp")
                            elif filename == "toon0.bmp":
                                # Special case for toon0.bmp -> use toon10.bmp
                                mmd_mat.is_shared_toon_texture = True
                                mmd_mat.shared_toon_texture = 9  # toon10.bmp (0-based index)
                                fixed_toon_textures.append(f"Fixed toon texture in '{material_name}': '{filename}' -> Using shared toon10.bmp")
                            else:
                                # Any other toon*.bmp -> use toon01.bmp
                                mmd_mat.is_shared_toon_texture = True
                                mmd_mat.shared_toon_texture = 0  # toon01.bmp (0-based index)
                                fixed_toon_textures.append(f"Fixed toon texture in '{material_name}': '{filename}' -> Using shared toon01.bmp")
                        except (ValueError, IndexError):
                            # If we can't parse the number, default to toon01.bmp
                            mmd_mat.is_shared_toon_texture = True
                            mmd_mat.shared_toon_texture = 0  # toon01.bmp
                            fixed_toon_textures.append(f"Fixed toon texture in '{material_name}': '{filename}' -> Using shared toon01.bmp")
                    else:
                        # Non-standard toon texture, default to toon01.bmp
                        mmd_mat.is_shared_toon_texture = True
                        mmd_mat.shared_toon_texture = 0  # toon01.bmp
                        fixed_toon_textures.append(f"Fixed toon texture in '{material_name}': '{filename}' -> Using shared toon01.bmp")

                    # Update toon texture to apply changes
                    FnMaterial(material).update_toon_texture()

                    # Track this material-image pair as fixed
                    fixed_material_image_pairs.add((material_name, img_name))

            # Add fixed toon texture information to results
            fixed.extend(fixed_toon_textures)

        # Third pass: Reevaluate texture filepaths after toon texture fixes
        # This is important because fixing toon textures may have resolved some conflicts
        if fixed_material_image_pairs:
            # Clear old data
            texture_filepaths = {}
            filepath_by_filename = {}

            # Rebuild texture path data
            for material in FnModel.iterate_unique_materials(root):
                if not material.node_tree:
                    continue

                for node in material.node_tree.nodes:
                    if node.type != "TEX_IMAGE" or not node.image or not node.image.filepath:
                        continue

                    img = node.image
                    filepath = img.filepath

                    # Skip if this material-image pair was fixed as a toon texture
                    if (material.name, img.name) in fixed_material_image_pairs and node.name == "mmd_toon_tex":
                        continue

                    # Track images using this filepath
                    if filepath not in texture_filepaths:
                        texture_filepaths[filepath] = []
                    if img not in texture_filepaths[filepath]:
                        texture_filepaths[filepath].append(img)

                    # Track filepaths by filename
                    filename = os.path.basename(filepath)
                    if filename not in filepath_by_filename:
                        filepath_by_filename[filename] = set()
                    filepath_by_filename[filename].add(filepath)

        # Fourth pass: fix name inconsistencies for images with the same filepath
        filename_conflicts_fixed = False
        for filepath, images in texture_filepaths.items():
            if len(images) > 1:
                # Use the first image's name as the standard
                standard_name = images[0].name
                for img in images[1:]:
                    if img.name != standard_name:
                        if not filename_conflicts_fixed:
                            if fixed:  # If we already have content in the fixed list
                                fixed.append("")  # Add a blank line
                            fixed.append("NAME INCONSISTENCIES FIXED:")
                            filename_conflicts_fixed = True
                        old_name = img.name
                        img.name = standard_name
                        fixed.append(f"Unified texture name: '{old_name}' -> '{standard_name}' for path '{filepath}'")

        # Fifth pass: fix filepath conflicts (same filename in different directories)
        filepath_conflicts_fixed = False
        for filename, filepaths in filepath_by_filename.items():
            if len(filepaths) <= 1:
                continue

            # Skip conflicts involving only toon textures that were fixed
            all_fixed = True
            for filepath in filepaths:
                for img in texture_filepaths.get(filepath, []):
                    material_names = [m.name for m in bpy.data.materials if m.node_tree and any(n.type == "TEX_IMAGE" and n.image == img for n in m.node_tree.nodes)]
                    if not any((mat_name, img.name) in fixed_material_image_pairs for mat_name in material_names):
                        all_fixed = False
                        break
                if not all_fixed:
                    break

            if all_fixed:
                continue

            conflict_fixed = [f"Fix texture filename conflict: '{filename}':"]

            # Sort paths to ensure consistent results
            sorted_paths = sorted(filepaths)
            # Keep the first path, modify others
            for i, filepath in enumerate(sorted_paths[1:], 1):
                # Get all images using this filepath
                if filepath not in texture_filepaths:
                    continue

                for img in texture_filepaths[filepath]:
                    old_path = img.filepath

                    # Skip already fixed toon textures
                    material_names = [m.name for m in bpy.data.materials if m.node_tree and any(n.type == "TEX_IMAGE" and n.image == img for n in m.node_tree.nodes)]
                    if any((mat_name, img.name) in fixed_material_image_pairs for mat_name in material_names):
                        continue

                    # Make absolute path for file operations
                    abs_path = bpy.path.abspath(old_path)

                    # Check if file exists
                    if not os.path.exists(abs_path):
                        conflict_fixed.append(f"Warning: File not found on disk: '{abs_path}'")
                        continue

                    # Create new path with proper suffix checking
                    base_path, ext = os.path.splitext(old_path)
                    suffix = i + 1  # Start from 2
                    new_path = f"{base_path}{suffix}{ext}"
                    abs_new_path = bpy.path.abspath(new_path)

                    # Check if target file already exists and try incremental suffixes
                    while os.path.exists(abs_new_path):
                        # If the file is identical to source, use this path
                        if os.path.exists(abs_path) and filecmp.cmp(abs_path, abs_new_path, shallow=False):
                            break
                        # Try next suffix
                        suffix += 1
                        new_path = f"{base_path}{suffix}{ext}"
                        abs_new_path = bpy.path.abspath(new_path)

                    # Unpack if needed
                    if img.packed_file:
                        img.unpack(method="WRITE_ORIGINAL")

                    try:
                        # Only copy if target doesn't exist or is different
                        if not os.path.exists(abs_new_path):
                            shutil.copy2(abs_path, abs_new_path)
                            conflict_fixed.append(f"Modified texture path and copied file: '{old_path}' -> '{new_path}'")
                        else:
                            conflict_fixed.append(f"Reusing existing file for: '{old_path}' -> '{new_path}'")

                        # Update filepath in Blender
                        img.filepath = new_path
                    except Exception as e:
                        conflict_fixed.append(f"Error copying texture file: {str(e)}")

                        # Only add to fixed list if we actually fixed conflicts (more than just the header)
            if len(conflict_fixed) > 1:
                if not filepath_conflicts_fixed:
                    if fixed:  # If we already have content in the fixed list
                        fixed.append("")  # Add a blank line
                    fixed.append("TEXTURE FILENAME CONFLICTS FIXED:")
                    filepath_conflicts_fixed = True
                fixed.extend(conflict_fixed)

        # Fix additional unallowed characters in texture filenames (disk path only, extension excluded)
        unallowed = get_additional_unallowed_chars("texture")
        if unallowed:
            replacement = get_replacement_char()
            seen_images = set()

            for material in FnModel.iterate_unique_materials(root):
                if not material.node_tree:
                    continue
                for node in material.node_tree.nodes:
                    if node.type != "TEX_IMAGE" or not node.image or not node.image.filepath:
                        continue
                    img = node.image
                    if img.filepath in seen_images:
                        continue
                    seen_images.add(img.filepath)

                    abs_path = bpy.path.abspath(img.filepath)
                    dir_path = os.path.dirname(abs_path)
                    basename = os.path.basename(abs_path)
                    stem, ext = os.path.splitext(basename)

                    # Only process the stem, leave extension untouched
                    new_stem = _replace_additional_unallowed_chars(stem, unallowed, replacement)
                    if new_stem == stem:
                        continue

                    # Resolve filename collision on disk
                    candidate_stem = new_stem
                    suffix = 2
                    while os.path.exists(os.path.join(dir_path, f"{candidate_stem}{ext}")):
                        candidate_stem = f"{new_stem}{suffix}"
                        suffix += 1

                    new_abs_path = os.path.join(dir_path, f"{candidate_stem}{ext}")

                    if not os.path.exists(abs_path):
                        fixed.append(f"Warning: Source file not found, skipping: '{abs_path}'")
                        continue

                    try:
                        shutil.copy2(abs_path, new_abs_path)
                        # Update filepath in Blender (keep relative if original was relative)
                        if img.filepath.startswith("//"):
                            img.filepath = "//" + os.path.relpath(new_abs_path, bpy.path.abspath("//"))
                        else:
                            img.filepath = new_abs_path
                        fixed.append(f"Fixed texture filename unallowed chars: '{basename}' -> '{candidate_stem}{ext}'")
                    except Exception as e:
                        fixed.append(f"Error renaming texture file '{basename}': {str(e)}")

        # Report remaining missing textures that couldn't be fixed
        remaining_missing = [(mat, img, path) for mat, img, path, node in missing_textures if (mat, img) not in fixed_material_image_pairs and node != "mmd_toon_tex"]

        if remaining_missing:
            if fixed:  # If we already have content in the fixed list
                fixed.append("")  # Add a blank line
            fixed.append("REMAINING MISSING TEXTURES (cannot be fixed automatically):")
            for material_name, img_name, filepath in remaining_missing:
                fixed.append(f"Material '{material_name}' missing texture: '{img_name}' at path: '{filepath}'")

        # Clean up unused image blocks with missing files
        removed_images = []
        for img in reversed(bpy.data.images):
            if img.users == 0 and (not os.path.exists(bpy.path.abspath(img.filepath)) and not img.packed_file):
                removed_images.append(f"Removed unused image block: '{img.name}'")
                bpy.data.images.remove(img)

        if removed_images:
            if fixed:  # If we already have content in the fixed list
                fixed.append("")  # Add a blank line
            fixed.append("REMOVED UNUSED IMAGE BLOCKS:")
            fixed.extend(removed_images)

        results = "\n".join(fixed) if fixed else "No texture issues to fix"
        context.scene.mmd_validation_results = results
        log_message("MMD Texture Fix", results, "INFO")

        force_ui_update(context)
        return {"FINISHED"}
