# MIT License

import bpy
import addon_utils
from importlib import import_module

from .. import globs
from .main import ToolPanel, draw_info_box, draw_error_box
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
_smc_check_cache = None
_smc_cache_timestamp = 0


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
            draw_error_box(m_col, [
                t('OptimizePanel.matCombOutOfDate'),
                t('OptimizePanel.matCombUseMaster')
            ])
            m_col.separator()
            row = m_col.row(align=True)
            row.scale_y = 1.3
            row.operator(Atlas.ShotariyaButton.bl_idname, icon=globs.ICON_URL)
            return
        
        # Check if Material Combiner uses the old interface
        if not hasattr(main_panel_module.MaterialCombinerPanel, 'draw_pillow_installer'):
            draw_error_box(m_col, [
                t('OptimizePanel.matCombOutOfDate'),
                t('OptimizePanel.matCombUseMaster')
            ])
            m_col.separator()
            row = m_col.row(align=True)
            row.scale_y = 1.3
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
            col.scale_y = 1.3
            col.operator(
                "smc.refresh_ob_data",
                text="Update Material List" if hasattr(context.scene, 'smc_ob_data') and context.scene.smc_ob_data else "Generate Material List",
                icon='FILE_REFRESH'
            )
            col = m_col.column()
            col.scale_y = 1.3
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
                draw_error_box(m_col, t('OptimizePanel.matCombPillowRequired'))
                m_col.separator()
                row = m_col.row()
                row.scale_y = 1.3
                row.operator('smc.get_pillow', text='Install Pillow', icon='IMPORT')
            
    except Exception as e:
        # If there's any error, show a helpful message
        draw_error_box(m_col, [
            t('OptimizePanel.matCombInterfaceError'),
            t('OptimizePanel.matCombUseMainPanel')
        ])


def check_for_smc(force_refresh=False):
    global draw_smc_ui, old_smc_version, smc_is_disabled, found_very_old_smc
    global _smc_check_cache, _smc_cache_timestamp
    
    import time
    current_time = time.time()
    
    # Use cache if available and not expired (5 minutes)
    if not force_refresh and _smc_check_cache is not None and (current_time - _smc_cache_timestamp) < 300:
        return
    
    try:
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
        
        # Cache the result
        _smc_check_cache = True
        _smc_cache_timestamp = current_time
        
    except Exception as e:
        # Handle any errors during addon check
        print(f"Error checking for Material Combiner: {e}")
        draw_smc_ui = None

@register_wrap
class OptimizePanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_optimize_v3'
    bl_label = t('OptimizePanel.label')
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        # Parent panel is now just a container for sub-panels
        pass


@register_wrap
class AtlasSubPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_optimize_atlas_v3'
    bl_label = t('OptimizePanel.atlas.label')
    bl_parent_id = 'VIEW3D_PT_optimize_v3'
    bl_options = set()

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        self.draw_atlas_section(col, context)

    def draw_atlas_section(self, col, context):
        try:
            # PBR Info
            draw_info_box(col, "For PBR/Normal maps, use Tuxedo Blender Plugin.")

            col.separator()

            # Atlas description
            desc_col = col.column(align=True)
            desc_col.scale_y = 0.75
            desc_col.label(text=t('OptimizePanel.atlasDesc'))

            col.separator()

            # Author credit
            box = col.box()
            row = box.row(align=True)
            row.scale_y = 0.75
            split = row.split(factor=0.7)
            split.label(text=t('OptimizePanel.atlasAuthor'), 
                       icon_value=Iconloader.preview_collections["custom_icons"]["heart1"].icon_id)
            split.operator(Atlas.AtlasHelpButton.bl_idname, text="", icon='QUESTION')

            col.separator()

            # SMC Status section
            if smc_is_disabled:
                self.draw_smc_message(col, 'disabled')
            elif old_smc_version:
                self.draw_smc_message(col, 'outdated')
            elif found_very_old_smc:
                self.draw_smc_message(col, 'very_old')
            elif not draw_smc_ui:
                self.draw_smc_message(col, 'not_installed')
            elif hasattr(bpy.context.scene, 'smc_ob_data'):
                custom_draw_smc_ui(context, col)

            check_for_smc()
            
        except Exception as e:
            draw_error_box(col, [
                t('OptimizePanel.matCombInterfaceError'),
                t('OptimizePanel.matCombUseMainPanel')
            ])

    def draw_smc_message(self, col, message_type):
        messages = []
        button_operator = None
        button_icon = None
        
        if message_type == 'disabled':
            messages = [
                t('OptimizePanel.matCombDisabled1'),
                t('OptimizePanel.matCombDisabled2')
            ]
            button_operator = Atlas.EnableSMC.bl_idname
            button_icon = 'CHECKBOX_HLT'
            draw_error_box(col, messages)
            
        elif message_type == 'outdated':
            messages = [
                t('OptimizePanel.matCombOutdated1'),
                t('OptimizePanel.matCombOutdated2'),
                t('OptimizePanel.matCombOutdated3'),
                t('OptimizePanel.matCombOutdated4', location=t('OptimizePanel.matCombOutdated5_2.8')),
                t('OptimizePanel.matCombOutdated6')
            ]
            button_operator = Atlas.ShotariyaButton.bl_idname
            button_icon = globs.ICON_URL
            draw_error_box(col, messages)
            
        elif message_type == 'very_old':
            messages = [
                t('OptimizePanel.matCombOutdated1'),
                t('OptimizePanel.matCombOutdated2'),
                t('OptimizePanel.matCombOutdated6_alt')
            ]
            button_operator = Atlas.ShotariyaButton.bl_idname
            button_icon = globs.ICON_URL
            draw_error_box(col, messages)
            
        elif message_type == 'not_installed':
            messages = [
                t('OptimizePanel.matCombNotInstalled'),
                t('OptimizePanel.matCombOutdated6_alt')
            ]
            button_operator = Atlas.ShotariyaButton.bl_idname
            button_icon = globs.ICON_URL
            draw_error_box(col, messages)
        
        if button_operator:
            col.separator()
            row = col.row(align=True)
            row.scale_y = 1.3
            row.operator(button_operator, icon=button_icon)


@register_wrap
class MaterialSubPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_optimize_material_v3'
    bl_label = t('OptimizePanel.material.label')
    bl_parent_id = 'VIEW3D_PT_optimize_v3'
    bl_options = set()

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        self.draw_material_section(col, context)

    def draw_material_section(self, col, context):
        try:
            # Material operations
            box = col.box()
            box_col = box.column(align=True)
            box_col.scale_y = 1.3
            box_col.operator(Material.CombineMaterialsButton.bl_idname, icon='MATERIAL')
            box_col.operator(Material.ConvertAllToPngButton.bl_idname, icon='IMAGE_RGB_ALPHA')
            
            col.separator()
            
            # Mesh operations
            box = col.box()
            box_col = box.column(align=True)
            
            header_row = box_col.row(align=True)
            header_row.scale_y = 0.75
            header_row.label(text=t('OtherOptionsPanel.joinMeshes'), icon='AUTOMERGE_ON')
            
            ops_row = box_col.row(align=True)
            ops_row.scale_y = 1.3
            ops_row.operator(Armature_manual.JoinMeshes.bl_idname, text=t('OtherOptionsPanel.JoinMeshes.label'))
            ops_row.operator(Armature_manual.JoinMeshesSelected.bl_idname, text=t('OtherOptionsPanel.JoinMeshesSelected.label'))
            
            col.separator()
            
            # Cleanup
            box = col.box()
            box_col = box.column(align=True)

            header_row = box_col.row(align=True)
            header_row.scale_y = 0.75
            header_row.label(text="Remove Doubles", icon='X')

            box_col.prop(context.scene, 'remove_doubles_threshold')
            row = box_col.row(align=True)
            row.scale_y = 1.3
            row.operator(Armature_manual.RemoveDoubles.bl_idname, icon='X')
            
        except Exception as e:
            draw_error_box(col, ["Error loading material operations", str(e)])


@register_wrap
class BoneMergingSubPanel(ToolPanel, bpy.types.Panel):
    bl_idname = 'VIEW3D_PT_optimize_bonemerging_v3'
    bl_label = t('OptimizePanel.bonemerging.label')
    bl_parent_id = 'VIEW3D_PT_optimize_v3'
    bl_options = set()

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        self.draw_bone_merging_section(col, context)

    def draw_bone_merging_section(self, col, context):
        try:
            # Settings box
            box = col.box()
            box_col = box.column(align=True)
            
            if len(Common.get_meshes_objects(check=False)) > 1:
                row = box_col.row(align=True)
                row.scale_y = 1.0
                row.prop(context.scene, 'merge_mesh')
            
            box_col.prop(context.scene, 'merge_bone')
            box_col.prop(context.scene, 'merge_ratio')
            
            # Actions row
            actions_row = box_col.row(align=True)
            actions_row.scale_y = 1.3
            actions_row.operator(Rootbone.RefreshRootButton.bl_idname, icon='FILE_REFRESH')
            actions_row.operator(Bonemerge.BoneMergeButton.bl_idname, icon='AUTOMERGE_ON')
            
            col.separator()
            
            # Weights box
            box = col.box()
            box_col = box.column(align=True)
            
            header_row = box_col.row(align=True)
            header_row.scale_y = 0.75
            header_row.label(text=t('OtherOptionsPanel.mergeWeights'), icon='BONE_DATA')
            
            ops_row = box_col.row(align=True)
            ops_row.scale_y = 1.3
            ops_row.operator(Armature_manual.MergeWeights.bl_idname, text=t('OtherOptionsPanel.MergeWeights.label'))
            ops_row.operator(Armature_manual.MergeWeightsToActive.bl_idname, text=t('OtherOptionsPanel.MergeWeightsToActive.label'))
            
            # Options
            options_col = box_col.column(align=True)
            options_col.scale_y = 0.85
            options_col.separator()
            options_col.prop(context.scene, 'keep_merged_bones')
            options_col.prop(context.scene, 'merge_visible_meshes_only')
            
            col.separator()
            
            # Delete operations box
            box = col.box()
            box_col = box.column(align=True)
            
            header_row = box_col.row(align=True)
            header_row.scale_y = 0.75
            header_row.label(text=t('OtherOptionsPanel.delete'), icon='X')
            
            ops_col = box_col.column(align=True)
            ops_col.scale_y = 1.3
            row = ops_col.row(align=True)
            row.operator(Armature_manual.RemoveZeroWeightBones.bl_idname, text=t('OtherOptionsPanel.RemoveZeroWeightBones.label'))
            row.operator(Armature_manual.RemoveConstraints.bl_idname, text=t('OtherOptionsPanel.RemoveConstraints'))
            row.operator(Armature_manual.RemoveZeroWeightGroups.bl_idname, text=t('OtherOptionsPanel.RemoveZeroWeightGroups'))
            
            options_col = box_col.column(align=True)
            options_col.scale_y = 0.85
            options_col.separator()
            options_col.prop(context.scene, "delete_zero_weight_keep_twists")
            options_col.prop(context.scene, "delete_zero_weight_keep_empty_parents")
            options_col.prop(context.scene, "delete_zero_weight_skip_hidden_bones")

            col.separator()

            # Extra operations box
            box = col.box()
            box_col = box.column(align=True)
            box_col.scale_y = 1.3
            box_col.operator(Armature_manual.DuplicateBonesButton.bl_idname, icon='GROUP_BONE')
            box_col.operator(Armature_manual.ConnectBonesButton.bl_idname, icon='CONSTRAINT_BONE')
            
        except Exception as e:
            draw_error_box(col, ["Error loading bone merging operations", str(e)])


