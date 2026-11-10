# MIT License

from .. import common as Common
from ..translations import t
from .bones import BONE_LIST, get_bone_enum_items, NO_OVERRIDE


def draw_ui(context, layout):
    scn = context.scene

    box = layout.box()
    col = box.column(align=True)
    col.label(text=t('ScalerUI.avatarRescale'))

    # Target height + "get current height"
    split = col.row(align=True)
    row = split.row(align=True)
    row.prop(scn, "imscale_target_height", expand=True)
    row = split.row(align=True)
    row.alignment = "RIGHT"
    row.operator("armature.get_avatar_height", text="", icon="EMPTY_SINGLE_ARROW")

    if scn.imscale_scale_upper_body:
        row = col.row(align=True)
        row.prop(scn, "imscale_arm_to_legs", expand=True)
    else:
        split = col.row(align=True)
        row = split.row(align=True)
        row.prop(scn, "imscale_upper_body_percentage", expand=True)
        row = split.row(align=True)
        row.alignment = "RIGHT"
        row.operator("armature.get_upper_body_percentage", text="", icon="EMPTY_SINGLE_ARROW")

    split = col.row(align=True)
    row = split.row(align=True)
    row.prop(scn, "imscale_custom_scale_ratio", expand=True)
    row = split.row(align=True)
    row.alignment = "RIGHT"
    row.operator("armature.get_scale_ratio", text="", icon="EMPTY_SINGLE_ARROW")

    row = col.row(align=False)
    icon = "DOWNARROW_HLT" if scn.imscale_show_customize else "RIGHTARROW"
    row.prop(scn, "imscale_show_customize", icon=icon, text="", emboss=False)
    row.label(text=t('ScalerUI.customization'))

    if scn.imscale_show_customize:
        row = col.row(align=True)
        row.prop(scn, "imscale_arm_thickness", expand=True)
        row = col.row(align=True)
        row.prop(scn, "imscale_leg_thickness", expand=True)

        split = col.row(align=True)
        row = split.row(align=True)
        row.prop(scn, "imscale_thigh_percentage", expand=True)
        row = split.row(align=True)
        row.alignment = "RIGHT"
        row.operator("armature.get_avatar_upper_leg_percent", text="", icon="EMPTY_SINGLE_ARROW")

        if scn.imscale_scale_upper_body:
            row = col.row(align=True)
            row.prop(scn, "imscale_extra_leg_length", expand=True)
        row = col.row(align=True)
        row.prop(scn, "imscale_scale_eyes", expand=True)
        row = col.row(align=True)
        row.prop(scn, "imscale_show_bone_map", expand=True)

    row = col.row(align=False)
    icon = "DOWNARROW_HLT" if scn.imscale_show_debug else "RIGHTARROW"
    row.prop(scn, "imscale_show_debug", icon=icon, text="", emboss=False)
    row.label(text=t('ScalerUI.coreToggle'))
    if scn.imscale_show_debug:
        row = col.row(align=True)
        row.prop(scn, "imscale_debug_no_adjust", expand=True)
        row = col.row(align=True)
        row.prop(scn, "imscale_debug_no_floor", expand=True)
        row = col.row(align=True)
        row.prop(scn, "imscale_debug_no_scale", expand=True)
        row = col.row(align=False)
        row.prop(scn, "imscale_scale_upper_body", text=t('ScalerUI.scaleRelative'))
        row = col.row(align=False)
        row.prop(scn, "imscale_keep_head_size", text=t('ScalerUI.keepHeadSize'))

    row = col.row(align=True)
    row.prop(scn, "imscale_center_model", expand=True)

    row = col.row(align=True)
    row.scale_y = 1.1
    row.operator("armature.rescale", text=t('ScalerUI.rescale'))

    # Spread Fingers
    box = layout.box()
    col = box.column(align=True)
    col.label(text=t('ScalerUI.fingerSpreading'))

    row = col.row(align=False)
    icon = "DOWNARROW_HLT" if scn.imscale_show_sf_custom else "RIGHTARROW"
    row.prop(scn, "imscale_show_sf_custom", icon=icon, text="", emboss=False)
    row.label(text=t('ScalerUI.customization'))

    if scn.imscale_show_sf_custom:
        row = col.row(align=True)
        row.prop(scn, "imscale_spare_thumb")
        row = col.row(align=False)
        row.prop(scn, "imscale_spread_factor")

    row = col.row(align=True)
    row.scale_y = 1.1
    row.operator("armature.spreadfingers", text=t('ScalerUI.spreadFingers'))

    box = layout.box()
    col = box.column(align=True)
    col.label(text=t('ScalerUI.hipFix'))
    row = col.row(align=True)
    row.operator("armature.shrink_hips", text=t('ScalerUI.shrinkHip'))

    if scn.imscale_show_bone_map:
        box = layout.box()
        col = box.column(align=True)
        col.label(text=t('ScalerUI.boneOverrides'))
        for bone_name in BONE_LIST:
            prop = "override_" + bone_name
            current = Common.get_enum_property_value(scn, prop, get_bone_enum_items) or NO_OVERRIDE
            row = col.row(align=True)
            row.label(text=bone_name.replace("_", " "))
            row.operator(
                "scene.search_menu_bone_selection",
                text=current,
                icon="BONE_DATA",
            ).bone_name = bone_name

    arm_count = len(Common.get_armature_list(None, context))
    if arm_count > 1:
        box = layout.box()
        col = box.column(align=True)
        col.label(text=t('ScalerUI.scaleMatching'))
        row = col.row(align=True)
        row.label(text=t('ScalerUI.referenceArmature'))
        row.operator(
            "scene.search_menu_scale_armature_ref",
            text=Common.enum_display_text(
                Common.get_enum_property_value(scn, "imscale_scale_armature_ref", Common.get_armature_list),
                t('CustomPanel.selectArmature'),
            ),
            icon="ARMATURE_DATA",
        )
        row = col.row(align=True)
        row.label(text=t('ScalerUI.scalingArmature'))
        row.operator(
            "scene.search_menu_scale_armature_arm",
            text=Common.enum_display_text(
                Common.get_enum_property_value(scn, "imscale_scale_armature_arm", Common.get_armature_list),
                t('CustomPanel.selectArmature'),
            ),
            icon="ARMATURE_DATA",
        )
        row = col.row(align=True)
        row.operator("armature.imscale_align", text=t('ScalerUI.matchScale'))

    return None
