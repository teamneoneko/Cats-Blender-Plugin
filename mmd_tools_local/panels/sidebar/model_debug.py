# Copyright 2025 MMD Tools authors
# This file is part of MMD Tools.

import bpy

from ...core.model import FnModel
from . import PT_ProductionPanelBase


class MMDModelDebugPanel(PT_ProductionPanelBase, bpy.types.Panel):
    bl_idname = "OBJECT_PT_mmd_tools_model_debug"
    bl_label = "Model Debug"
    bl_order = 4

    def draw(self, context):
        active_obj = context.active_object

        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Model Validation:", icon="ERROR")

        # Check if we have a valid MMD model selected
        root = FnModel.find_root_object(active_obj)
        col.enabled = root is not None

        # Validation buttons section
        grid = col.grid_flow(row_major=True, columns=2, align=True, even_columns=True)
        grid.operator("mmd_tools_local.validate_model", text="Check Model", icon="EMPTY_DATA")
        grid.operator("mmd_tools_local.validate_textures", text="Check Textures", icon="TEXTURE")
        grid.operator("mmd_tools_local.validate_bones", text="Check Bones", icon="BONE_DATA")
        grid.operator("mmd_tools_local.validate_morphs", text="Check Morphs", icon="SHAPEKEY_DATA")

        # Results section
        box = layout.box()
        box.label(text="Validation Results:", icon="INFO")

        # Add this section to display the validation results
        if context.scene.mmd_validation_results:
            result_col = box.column(align=True)
            lines = context.scene.mmd_validation_results.split("\n")
            display_limit = 10
            for line in lines[:display_limit]:
                result_col.label(text=line)
            if len(lines) > display_limit:
                result_col.separator()
                result_col.label(text=f"... and {len(lines) - display_limit} more results.", icon="LINENUMBERS_ON")
                result_col.label(text="Check System Console for full log.", icon="CONSOLE")
        else:
            col = box.column(align=True)
            col.label(text="Run validation to see results")

        # Fix suggestions section
        col = layout.column(align=True)
        col.label(text="Quick Fixes:", icon="TOOL_SETTINGS")
        col.enabled = root is not None
        grid = col.grid_flow(row_major=True, align=True)

        grid = col.grid_flow(row_major=True, columns=2, align=True, even_columns=True)
        grid.operator("mmd_tools_local.fix_model_issues", text="Fix Model", icon="OUTLINER_OB_EMPTY")
        grid.operator("mmd_tools_local.fix_texture_issues", text="Fix Textures", icon="IMAGE_DATA")
        grid.operator("mmd_tools_local.fix_bone_issues", text="Fix Bones", icon="MODIFIER")
        grid.operator("mmd_tools_local.fix_morph_issues", text="Fix Morphs", icon="KEY_HLT")
