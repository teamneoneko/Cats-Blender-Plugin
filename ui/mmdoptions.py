# MIT License

import bpy

from .. import globs
from .main import ToolPanel, draw_section, draw_wiki_button
from .quickaccess import FixArmatureWarning, ModelSettings
from ..tools import common as Common
from ..tools import rigify_convert as Rigify_convert
from ..tools import armature_manual as Armature_manual
from ..tools.register import register_wrap
from ..tools.translations import t

WIKI = 'ConvertersPanel.wikiURL'


@register_wrap
class MMDOptions(ToolPanel, bpy.types.Panel):
    # Home for cross-target conversions (Rigify, Source/Valve, VRM) plus MMD cleanup.
    bl_idname = 'VIEW3D_PT_mmdoptions_stuff'
    bl_label = t('ConvertersPanel.label')
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 30

    def draw_header_preset(self, context):
        draw_wiki_button(self.layout, WIKI, pad=1.5)

    def draw(self, context):
        col = self.layout.column(align=True)

        self.draw_rigify_section(col, context)
        col.separator()
        self.draw_platform_section(col, context)
        col.separator()
        self.draw_mmd_section(col, context)

    def draw_rigify_section(self, col, context):
        box_col = draw_section(col, t('ConvertersPanel.rigifySection'), 'OUTLINER_OB_ARMATURE',
                               WIKI, 'rigify-cats')

        is_rigify = Rigify_convert.is_rigify_armature(Common.get_armature())
        body = box_col.column(align=True)
        body.enabled = is_rigify
        if is_rigify:
            info_col = body.column(align=True)
            info_col.scale_y = 0.7
            info_col.label(text=t('ConvertRigify.info1'), icon='INFO')
            info_col.label(text=t('ConvertRigify.info2'), icon='BLANK1')
            body.separator(factor=0.5)
            body.prop(context.scene, 'rigify_merge_twist_bones')

        row = body.row(align=True)
        row.scale_y = 1.3
        row.operator(Rigify_convert.ConvertRigifyToCats.bl_idname, icon='OUTLINER_OB_ARMATURE')

    def draw_platform_section(self, col, context):
        box_col = draw_section(col, t('ConvertersPanel.platformSection'), 'EXPORT',
                               WIKI, 'platform-conversion')

        ops_col = box_col.column(align=True)
        ops_col.scale_y = 1.3
        ops_col.operator(Armature_manual.ConvertToValveButton.bl_idname, icon='SMALL_CAPS')
        ops_col.operator(Armature_manual.FixKoikatsuShapekeysButton.bl_idname, icon='SHAPEKEY_DATA')

    def draw_mmd_section(self, col, context):
        box_col = draw_section(col, t('ConvertersPanel.mmdSection'), 'ARMATURE_DATA',
                               WIKI, 'mmd-cleanup')

        # Fix MMD Model (also lives in Quick Access) only for freshly imported
        # MMD / VRM models, not for models already set up for Unity / VRChat.
        warn_col = box_col.column(align=True)
        warn_col.scale_y = 0.7
        warn_col.label(text=t('FixArmature.warnMMDVRM1'), icon='ERROR')
        warn_col.label(text=t('FixArmature.warnMMDVRM2'), icon='BLANK1')
        warn_col.label(text=t('FixArmature.warnMMDVRM3'), icon='BLANK1')

        box_col.separator(factor=0.5)
        row = box_col.row(align=True)
        row.scale_y = 1.3
        split = row.split(factor=0.85, align=True)
        split.operator(FixArmatureWarning.bl_idname, icon=globs.ICON_FIX_MODEL)
        split.operator(ModelSettings.bl_idname, text="", icon='MODIFIER')

        box_col.separator()

        info_col = box_col.column(align=True)
        info_col.scale_y = 0.7
        info_col.label(text=t('MMDOptions.RemoveRigidBodiesManaulInfo1'), icon='INFO')
        info_col.label(text=t('MMDOptions.RemoveRigidBodiesManaulInfo2'), icon='BLANK1')

        box_col.separator(factor=0.5)
        row = box_col.row(align=True)
        row.scale_y = 1.3
        row.operator(Armature_manual.RemoveRigidbodiesJointsOperator.bl_idname, icon='RIGID_BODY')
