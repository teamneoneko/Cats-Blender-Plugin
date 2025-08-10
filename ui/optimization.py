# MIT License

import bpy
import addon_utils
from importlib import import_module

from .. import globs
from .main import ToolPanel
from ..tools import common as Common
from ..tools import iconloader as Iconloader
from ..tools import atlas as Atlas
from ..tools import material as Material
from ..tools import bonemerge as Bonemerge
from ..tools import rootbone as Rootbone
from ..tools import armature_manual as Armature_manual
from ..tools import armature_bones as Armature_bones

from ..tools.register import register_wrap
from ..tools.translations import t

draw_smc_ui = None
old_smc_version = False
smc_is_disabled = False
found_very_old_smc = False


def custom_draw_smc_ui(context, m_col):
    """Custom wrapper for Material Combiner UI that handles interface changes"""
    try:
        # Try to import the Material Combiner modules
        smc_module = None
        globs_module = None
        main_panel_module = None
        
        for mod in addon_utils.modules():
            if mod.bl_info['name'] == "Shotariya's Material Combiner" and addon_utils.check(mod.__name__)[0]:
                try:
                    smc_module = import_module(mod.__name__ + '.operators.ui.include')
                    globs_module = import_module(mod.__name__ + '.globs')
                    main_panel_module = import_module(mod.__name__ + '.ui.main_panel')
                    break
                except ImportError:
                    continue
        
        if not smc_module or not globs_module or not main_panel_module:
            col = m_col.column()
            col.label(text="Your Material Combiner is out of date,", icon='ERROR')
            col.label(text="please use the master branch as releases are outdated", icon='BLANK1')
            col.separator()
            row = col.row(align=True)
            row.scale_y = 1.2
            row.operator(Atlas.ShotariyaButton.bl_idname, icon=globs.ICON_URL)
            return
        
        # Check if Material Combiner uses the old interface
        if not hasattr(main_panel_module.MaterialCombinerPanel, 'draw_pillow_installer'):
            col = m_col.column()
            col.label(text="Your Material Combiner is out of date,", icon='ERROR')
            col.label(text="please use the master branch as releases are outdated", icon='BLANK1')
            col.separator()
            row = col.row(align=True)
            row.scale_y = 1.2
            row.operator(Atlas.ShotariyaButton.bl_idname, icon=globs.ICON_URL)
            return
            
        # Check Pillow availability using Material Combiner's globals
        if globs_module.pil_available:
            # Pillow is available, show the materials list
            if hasattr(context.scene, 'smc_ob_data') and context.scene.smc_ob_data:
                m_col.template_list(
                    "SMC_UL_Combine_List",
                    "combine_list", 
                    context.scene,
                    "smc_ob_data",
                    context.scene,
                    "smc_ob_data_id",
                    rows=12,
                    type="DEFAULT",
                )
            col = m_col.column(align=True)
            col.scale_y = 1.2
            col.operator(
                "smc.refresh_ob_data",
                text="Update Material List" if hasattr(context.scene, 'smc_ob_data') and context.scene.smc_ob_data else "Generate Material List",
                icon='FILE_REFRESH'
            )
            col = m_col.column()
            col.scale_y = 1.5
            col.operator("smc.combiner", text="Save Atlas to..", icon='TEXTURE').cats = True
            
        elif globs_module.pil_install_attempted:
            # Installation complete, restart required
            col = m_col.box().column()
            col.label(text="Installation complete", icon='CHECKMARK')
            col.label(text="Please restart Blender")
            
        else:
            # Pillow needs to be installed - use Material Combiner's installer
            if hasattr(main_panel_module.MaterialCombinerPanel, 'draw_pillow_installer'):
                main_panel_module.MaterialCombinerPanel.draw_pillow_installer(context, m_col)
            else:
                # Fallback for older versions
                col = m_col.box().column()
                col.label(text="Python Imaging Library Required", icon='ERROR')
                col.separator()
                row = col.row()
                row.scale_y = 1.5
                row.operator('smc.get_pillow', text='Install Pillow', icon='IMPORT')
            
    except Exception as e:
        # If there's any error, show a helpful message
        col = m_col.column()
        col.label(text="Material Combiner interface error", icon='ERROR')
        col.label(text="Use the main Material Combiner panel", icon='BLANK1')


def check_for_smc():
    global draw_smc_ui, old_smc_version, smc_is_disabled, found_very_old_smc

    draw_smc_ui = None
    found_very_old_smc = False

    for mod in addon_utils.modules():
        if mod.bl_info['name'] == "Shotariya-don":
            if hasattr(bpy.context.scene, 'shotariya_tex_idx'):
                found_very_old_smc = True
            continue
        if mod.bl_info['name'] == "Shotariya's Material Combiner":
            if mod.bl_info['version'] < (2, 1, 2, 9):
                old_smc_version = True
                continue
            if not addon_utils.check(mod.__name__)[0]:
                smc_is_disabled = True
                continue

            old_smc_version = False
            smc_is_disabled = False
            found_very_old_smc = False
            draw_smc_ui = getattr(import_module(mod.__name__ + '.operators.ui.include'), 'draw_ui')
            break

@register_wrap
class OptimizePanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_optimize_v3'
    bl_label = t('OptimizePanel.label')
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        box = layout.box()

        # Mode selector section
        mode_box = box.box()
        col = mode_box.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.2
        row.prop(context.scene, 'optimize_mode', expand=True)

        # Content section based on mode
        content_box = box.box()
        if context.scene.optimize_mode == 'ATLAS':
            self.draw_atlas_section(content_box, context)
        elif context.scene.optimize_mode == 'MATERIAL':
            self.draw_material_section(content_box, context)
        elif context.scene.optimize_mode == 'BONEMERGING':
            self.draw_bone_merging_section(content_box, context)

    def draw_atlas_section(self, box, context):
        col = box.column(align=True)
        
        # PBR Info
        info_col = col.column(align=True)
        info_col.scale_y = 0.9
        info_col.label(text="For PBR/Normal maps, use Tuxedo Blender Plugin.", icon='INFO')

        col.separator(factor=1.5)

        # Atlas description
        desc_col = col.column(align=True)
        desc_col.scale_y = 0.75
        desc_col.label(text=t('OptimizePanel.atlasDesc'))

        col.separator(factor=1.0)

        # Author credit
        author_box = col.box()
        author_col = author_box.column(align=True)
        row = author_col.row(align=True)
        row.scale_y = 0.9
        split = row.split(factor=0.7)
        split.label(text=t('OptimizePanel.atlasAuthor'), 
                   icon_value=Iconloader.preview_collections["custom_icons"]["heart1"].icon_id)
        split.operator(Atlas.AtlasHelpButton.bl_idname, text="", icon='QUESTION')

        col.separator(factor=1.5)

        # SMC Status section
        status_box = col.box()
        if smc_is_disabled:
            self.draw_smc_message(status_box, 'disabled')
        elif old_smc_version:
            self.draw_smc_message(status_box, 'outdated')
        elif found_very_old_smc:
            self.draw_smc_message(status_box, 'very_old')
        elif not draw_smc_ui:
            self.draw_smc_message(status_box, 'not_installed')
        elif hasattr(bpy.context.scene, 'smc_ob_data'):
            custom_draw_smc_ui(context, status_box.column(align=True))

        check_for_smc()

    def draw_material_section(self, box, context):
        # Material operations
        mat_box = box.box()
        mat_col = mat_box.column(align=True)
        mat_col.scale_y = 1.2
        mat_col.operator(Material.CombineMaterialsButton.bl_idname, icon='MATERIAL')
        mat_col.operator(Material.ConvertAllToPngButton.bl_idname, icon='IMAGE_RGB_ALPHA')
        
        # Mesh operations
        mesh_box = box.box()
        mesh_col = mesh_box.column(align=True)
        
        header_row = mesh_col.row(align=True)
        header_row.scale_y = 1.1
        header_row.label(text=t('OtherOptionsPanel.joinMeshes'), icon='AUTOMERGE_ON')
        
        ops_row = mesh_col.row(align=True)
        ops_row.scale_y = 1.2
        ops_row.operator(Armature_manual.JoinMeshes.bl_idname, text=t('OtherOptionsPanel.JoinMeshes.label'))
        ops_row.operator(Armature_manual.JoinMeshesSelected.bl_idname, text=t('OtherOptionsPanel.JoinMeshesSelected.label'))
        
        # Cleanup
        cleanup_box = box.box()
        cleanup_col = cleanup_box.column(align=True)
        cleanup_col.scale_y = 1.2

        header_row = cleanup_col.row(align=True)
        header_row.scale_y = 1.1
        header_row.label(text="Remove Doubles", icon='X')

        cleanup_col.prop(context.scene, 'remove_doubles_threshold')
        cleanup_col.operator(Armature_manual.RemoveDoubles.bl_idname, icon='X')

    def draw_bone_merging_section(self, box, context):
        # Settings box
        settings_box = box.box()
        settings_col = settings_box.column(align=True)
        
        if len(Common.get_meshes_objects(check=False)) > 1:
            row = settings_col.row(align=True)
            row.scale_y = 1.0
            row.prop(context.scene, 'merge_mesh')
        
        settings_col.prop(context.scene, 'merge_bone')
        settings_col.prop(context.scene, 'merge_ratio')
        
        # Actions row
        actions_row = settings_col.row(align=True)
        actions_row.scale_y = 1.2
        actions_row.operator(Rootbone.RefreshRootButton.bl_idname, icon='FILE_REFRESH')
        actions_row.operator(Bonemerge.BoneMergeButton.bl_idname, icon='AUTOMERGE_ON')
        
        # Weights box
        weights_box = box.box()
        weights_col = weights_box.column(align=True)
        
        header_row = weights_col.row(align=True)
        header_row.scale_y = 1.1
        header_row.label(text=t('OtherOptionsPanel.mergeWeights'), icon='BONE_DATA')
        
        ops_row = weights_col.row(align=True)
        ops_row.scale_y = 1.2
        ops_row.operator(Armature_manual.MergeWeights.bl_idname, text=t('OtherOptionsPanel.MergeWeights.label'))
        ops_row.operator(Armature_manual.MergeWeightsToActive.bl_idname, text=t('OtherOptionsPanel.MergeWeightsToActive.label'))
        
        # Options
        options_col = weights_col.column(align=True)
        options_col.scale_y = 0.75
        options_col.separator()
        options_col.prop(context.scene, 'keep_merged_bones')
        options_col.prop(context.scene, 'merge_visible_meshes_only')
        
        # Delete operations box
        delete_box = box.box()
        delete_col = delete_box.column(align=True)
        
        header_row = delete_col.row(align=True)
        header_row.scale_y = 1.1
        header_row.label(text=t('OtherOptionsPanel.delete'), icon='X')
        
        ops_col = delete_col.column(align=True)
        ops_col.scale_y = 1.2
        row = ops_col.row(align=True)
        row.operator(Armature_manual.RemoveZeroWeightBones.bl_idname, text=t('OtherOptionsPanel.RemoveZeroWeightBones.label'))
        row.operator(Armature_manual.RemoveConstraints.bl_idname, text=t('OtherOptionsPanel.RemoveConstraints'))
        row.operator(Armature_manual.RemoveZeroWeightGroups.bl_idname, text=t('OtherOptionsPanel.RemoveZeroWeightGroups'))
        
        options_col = delete_col.column(align=True)
        options_col.scale_y = 0.75
        options_col.separator()
        options_col.prop(context.scene, "delete_zero_weight_keep_twists")
        options_col.prop(context.scene, "delete_zero_weight_keep_empty_parents")
        options_col.prop(context.scene, "delete_zero_weight_skip_hidden_bones")

        # Extra operations box
        extra_box = box.box()
        extra_col = extra_box.column(align=True)
        extra_col.scale_y = 1.2
        extra_col.operator(Armature_manual.DuplicateBonesButton.bl_idname, icon='GROUP_BONE')
        extra_col.operator(Armature_manual.ConnectBonesButton.bl_idname, icon='CONSTRAINT_BONE')


    def draw_smc_message(self, box, message_type):
        col = box.column(align=True)
        
        message_col = col.column(align=True)
        message_col.scale_y = 0.75
        
        if message_type == 'disabled':
            message_col.label(text=t('OptimizePanel.matCombDisabled1'), icon='ERROR')
            message_col.label(text=t('OptimizePanel.matCombDisabled2'), icon='BLANK1')
            col.separator()
            row = col.row(align=True)
            row.scale_y = 1.2
            row.operator(Atlas.EnableSMC.bl_idname, icon='CHECKBOX_HLT')
            
        elif message_type == 'outdated':
            message_col.label(text=t('OptimizePanel.matCombOutdated1'), icon='ERROR')
            message_col.label(text=t('OptimizePanel.matCombOutdated2'), icon='BLANK1')
            message_col.label(text=t('OptimizePanel.matCombOutdated3'), icon='BLANK1')
            message_col.label(text=t('OptimizePanel.matCombOutdated4', location=t('OptimizePanel.matCombOutdated5_2.8')), icon='BLANK1')
            message_col.label(text=t('OptimizePanel.matCombOutdated6'), icon='BLANK1')
            col.separator()
            row = col.row(align=True)
            row.scale_y = 1.2
            row.operator(Atlas.ShotariyaButton.bl_idname, icon=globs.ICON_URL)
            
        elif message_type == 'very_old':
            message_col.label(text=t('OptimizePanel.matCombOutdated1'), icon='ERROR')
            message_col.label(text=t('OptimizePanel.matCombOutdated2'), icon='BLANK1')
            message_col.label(text=t('OptimizePanel.matCombOutdated6_alt'), icon='BLANK1')
            col.separator()
            row = col.row(align=True)
            row.scale_y = 1.2
            row.operator(Atlas.ShotariyaButton.bl_idname, icon=globs.ICON_URL)
            
        elif message_type == 'not_installed':
            message_col.label(text=t('OptimizePanel.matCombNotInstalled'), icon='ERROR')
            message_col.label(text=t('OptimizePanel.matCombOutdated6_alt'), icon='BLANK1')
            col.separator()
            row = col.row(align=True)
            row.scale_y = 1.2
            row.operator(Atlas.ShotariyaButton.bl_idname, icon=globs.ICON_URL)

