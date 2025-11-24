# MIT License
import os
import pathlib

from .tools import common as Common
from .tools.common import wrap_dynamic_enum_items
from .tools import atlas as Atlas
from .tools import eyetracking as Eyetracking
from .tools import rootbone as Rootbone
from .tools import settings as Settings
from .tools import importer as Importer
from .tools import translations as Translations
from .tools.translations import t
from .tools import viseme as Viseme

from bpy.types import Scene
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

documents_folder = pathlib.Path.home() / "Documents"
default_exports_dir = os.path.join(documents_folder, "Cats")

def register(): 
    Scene.remove_rigidbodies_joints_global = BoolProperty(
        name=t('Scene.removerigidbodiesjointsglobal.label'),
        description=t('Scene.removerigidbodiesjointsglobal.desc'),
        default=True  
    )  
         
    Scene.custom_translate_csv_export_dir = StringProperty(
        name=t('Scene.customfoldershapekeycsv.label'),
        description=t('Scene.customfoldershapekeycsv.desc'),
        subtype = 'DIR_PATH',
        default = default_exports_dir
    )

    Scene.export_translate_csv = BoolProperty(
        name=t('Scene.shapekeycsv.label'),
        description=t('Scene.shapekeycsv.desc'),
        default = False
    )

    Scene.progress_update = FloatProperty(
        name=t('Scene.progress_update.label'),
        description=t('Scene.progress_update.desc'), 
        default=0.0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE',
        options={'HIDDEN'}
    )
    Scene.generate_twistbones_upper = BoolProperty(
        name=t('Scene.generate_twistbones_upper.label'),
        description=t('Scene.generate_twistbones_upper.desc'),
        default=True
    )
    
    Scene.armature = EnumProperty(
        name=t('Scene.armature.label'),
        description=t('Scene.armature.desc'),
        items=wrap_dynamic_enum_items(Common.get_armature_list, 'armature', sort=False, in_place=False),
        update=Common.update_armature_selection,
    )

    Scene.zip_content = EnumProperty(
        name=t('Scene.zip_content.label'),
        description=t('Scene.zip_content.desc'),
        items=wrap_dynamic_enum_items(Importer.get_zip_content, 'zip_content'),
    )

    Scene.keep_upper_chest = BoolProperty(
        name=t('Scene.keep_upper_chest.label'),
        description=t('Scene.keep_upper_chest.desc'),
        default=True
    )

    Scene.remove_zero_weight = BoolProperty(
        name=t('Scene.remove_zero_weight.label'),
        description=t('Scene.remove_zero_weight.desc'),
        default=True
    )

    Scene.eye_tracking_mode = EnumProperty(
        name=t('Scene.eye_tracking_mode.label'),
        description=t('Scene.eye_tracking_mode.desc'),
        items=[
            ('SDK3', t('Scene.eye_tracking_mode.sdk3.label'), t('Scene.eye_tracking_mode.sdk3.desc')),
            ('LEGACY', t('Scene.eye_tracking_mode.legacy.label'), t('Scene.eye_tracking_mode.legacy.desc'))
        ],
        default='SDK3'
    )

    Scene.keep_end_bones = BoolProperty(
        name=t('Scene.keep_end_bones.label'),
        description=t('Scene.keep_end_bones.desc'),
        default=False
    )

    Scene.keep_twist_bones = BoolProperty(
        name=t('Scene.keep_twist_bones.label'),
        description=t('Scene.keep_twist_bones.desc'),
        default=False
    )

    Scene.fix_twist_bones = BoolProperty(
        name=t('Scene.fix_twist_bones.label'),
        description=t('Scene.fix_twist_bones.desc'),
        default=True
    )

    Scene.join_meshes = BoolProperty(
        name=t('Scene.join_meshes.label'),
        description=t('Scene.join_meshes.desc'),
        default=True
    )

    Scene.connect_bones = BoolProperty(
        name=t('Scene.connect_bones.label'),
        description=t('Scene.connect_bones.desc'),
        default=True
    )

    Scene.remove_rigidbodies_joints = BoolProperty(
        name=t('Scene.remove_rigidbodies_joints.label'),
        description=t('Scene.remove_rigidbodies_joints.desc'),
        default=True
    )

    # Manual
    Scene.use_google_only = BoolProperty(
        name=t('Scene.use_google_only.label'),
        description=t('Scene.use_google_only.desc'),
        default=False
    )

    Scene.skip_locked_shape_keys = BoolProperty(
        name=t('Scene.skip_locked_shape_keys.label'),
        description=t('Scene.skip_locked_shape_keys.desc'),
        default=False
    )

    Scene.keep_merged_bones = BoolProperty(
        name=t('keep_merged_bones'),
        description=t('select_this_to_keep_the_bones_after_merging_them_to_their_parents_or_to_the_active_bone'),
        default=False
    )

    Scene.merge_visible_meshes_only = BoolProperty(
        name=t('merge_visible_meshes_only'),
        description=t('select_this_to_only_merge_the_weights_of_the_visible_meshes'),
        default=False
    )

    Scene.show_more_options = BoolProperty(
        name=t('Scene.show_more_options.label'),
        description=t('Scene.show_more_options.desc'),
        default=False
    )

    # Custom Avatar Creation
    Scene.merge_mode = EnumProperty(
        name=t('Scene.merge_mode.label'),
        description=t('Scene.merge_mode.desc'),
        items=[
            ("ARMATURE", t('Scene.merge_mode.armature.label'), t('Scene.merge_mode.armature.desc')),
            ("MESH", t('Scene.merge_mode.mesh.label'), t('Scene.merge_mode.mesh.desc')),
        ]
    )

    Scene.merge_armature_into = EnumProperty(
        name=t('Scene.merge_armature_into.label'),
        description=t('Scene.merge_armature_into.desc'),
        items=wrap_dynamic_enum_items(Common.get_armature_list, 'merge_armature_into'),
    )

    Scene.merge_armature = EnumProperty(
        name=t('Scene.merge_armature.label'),
        description=t('Scene.merge_armature.desc'),
        items=wrap_dynamic_enum_items(Common.get_armature_merge_list, 'merge_armature'),
    )

    Scene.attach_to_bone = EnumProperty(
        name=t('Scene.attach_to_bone.label'),
        description=t('Scene.attach_to_bone.desc'),
        items=wrap_dynamic_enum_items(Common.get_bones_merge, 'attach_to_bone', sort=False),
    )

    Scene.attach_mesh = EnumProperty(
        name=t('Scene.attach_mesh.label'),
        description=t('Scene.attach_mesh.desc'),
        items=wrap_dynamic_enum_items(Common.get_top_meshes, 'attach_mesh'),
    )

    Scene.merge_same_bones = BoolProperty(
        name=t('Scene.merge_same_bones.label'),
        description=t('Scene.merge_same_bones.desc'),
        default=False
    )

    Scene.apply_transforms = BoolProperty(
        name=t('Scene.apply_transforms.label'),
        description=t('Scene.apply_transforms.desc'),
        default=False
    )

    Scene.merge_armatures_join_meshes = BoolProperty(
        name=t('Scene.merge_armatures_join_meshes.label'),
        description=t('Scene.merge_armatures_join_meshes.desc'),
        default=True
    )

    Scene.merge_armatures_remove_zero_weight_bones = BoolProperty(
        name=t('Scene.merge_armatures_remove_zero_weight_bones.label'),
        description=t('Scene.merge_armatures_remove_zero_weight_bones.desc'),
        default=True
    )

    Scene.delete_zero_weight_keep_twists = BoolProperty(
        name=t('Scene.delete_zero_weight_keep_twists.label'),
        description=t('Scene.delete_zero_weight_keep_twists.desc'),
        default=False
    )

    Scene.delete_zero_weight_keep_empty_parents = BoolProperty(
        name=t('Scene.delete_zero_weight_keep_empty_parents.label'),
        description=t('Scene.delete_zero_weight_keep_empty_parents.desc'),
        default=False
    )

    Scene.delete_zero_weight_skip_hidden_bones = BoolProperty(
        name=t('Scene.delete_zero_weight_skip_hidden_bones.label'),
        description=t('Scene.delete_zero_weight_skip_hidden_bones.desc'),
        default=False
    )

    Scene.merge_armatures_cleanup_shape_keys = BoolProperty(
        name=t('Scene.merge_armatures_cleanup_shape_keys.label'),
        description=t('Scene.merge_armatures_cleanup_shape_keys.desc'),
        default=True
    )

    Scene.selection_mode = EnumProperty(
        name=t('Scene.selection_mode.label'),
        description=t('Scene.selection_mode.desc'),
        items=[
            ("SHAPES", t('Scene.selection_mode.shapekeys.label'), t('Scene.selection_mode.shapekeys.desc')),
            ("MESHES", t('Scene.selection_mode.meshes.label'), t('Scene.selection_mode.meshes.desc'))
        ]
    )

    # Eye Tracking
    Scene.eye_mode = EnumProperty(
        name=t('Scene.eye_mode.label'),
        description=t('Scene.eye_mode.desc'),
        items=[
            ("CREATION", t('Scene.eye_mode.creation.label'), t('Scene.eye_mode.creation.desc')),
            ("TESTING", t('Scene.eye_mode.testing.label'), t('Scene.eye_mode.testing.desc'))
        ],
        update=Eyetracking.stop_testing
    )

    Scene.mesh_name_eye = EnumProperty(
        name=t('Scene.mesh_name_eye.label'),
        description=t('Scene.mesh_name_eye.desc'),
        # get_meshes is used elsewhere than for EnumProperty items so must contain the sorting itself
        items=wrap_dynamic_enum_items(Common.get_meshes, 'mesh_name_eye', sort=False),
    )

    Scene.head = EnumProperty(
        name=t('Scene.head.label'),
        description=t('Scene.head.desc'),
        items=wrap_dynamic_enum_items(Common.get_bones_head, 'head'),
    )

    Scene.eye_left = EnumProperty(
        name=t('Scene.eye_left.label'),
        description=t('Scene.eye_left.desc'),
        items=wrap_dynamic_enum_items(Common.get_bones_eye_l, 'eye_left'),
    )
    Scene.eye_right = EnumProperty(
        name=t('Scene.eye_right.label'),
        description=t('Scene.eye_right.desc'),
        items=wrap_dynamic_enum_items(Common.get_bones_eye_r, 'eye_right'),
    )

    Scene.wink_left = EnumProperty(
        name=t('Scene.wink_left.label'),
        description=t('Scene.wink_left.desc'),
        items=wrap_dynamic_enum_items(Common.get_shapekeys_eye_blink_l, 'wink_left', sort=False),
    )

    Scene.wink_right = EnumProperty(
        name=t('Scene.wink_right.label'),
        description=t('Scene.wink_right.desc'),
        items=wrap_dynamic_enum_items(Common.get_shapekeys_eye_blink_r, 'wink_right', sort=False),
    )

    Scene.lowerlid_left = EnumProperty(
        name=t('Scene.lowerlid_left.label'),
        description=t('Scene.lowerlid_left.desc'),
        items=wrap_dynamic_enum_items(Common.get_shapekeys_eye_low_l, 'lowerlid_left', sort=False),
    )

    Scene.lowerlid_right = EnumProperty(
        name=t('Scene.lowerlid_right.label'),
        description=t('Scene.lowerlid_right.desc'),
        items=wrap_dynamic_enum_items(Common.get_shapekeys_eye_low_r, 'lowerlid_right', sort=False),
    )

    Scene.disable_eye_movement = BoolProperty(
        name=t('Scene.disable_eye_movement.label'),
        description=t('Scene.disable_eye_movement.desc'),
        subtype='DISTANCE'
    )

    Scene.disable_eye_blinking = BoolProperty(
        name=t('Scene.disable_eye_blinking.label'),
        description=t('Scene.disable_eye_blinking.desc'),
        subtype='NONE'
    )

    Scene.eye_distance = FloatProperty(
        name=t('Scene.eye_distance.label'),
        description=t('Scene.eye_distance.desc'),
        default=0.8,
        min=0.0,
        max=2.0,
        step=1.0,
        precision=2,
        subtype='FACTOR'
    )

    Scene.eye_rotation_x = IntProperty(
        name=t('Scene.eye_rotation_x.label'),
        description=t('Scene.eye_rotation_x.desc'),
        default=0,
        min=-19,
        max=25,
        step=1,
        subtype='FACTOR',
        update=Eyetracking.set_rotation
    )

    Scene.eye_rotation_y = IntProperty(
        name=t('Scene.eye_rotation_y.label'),
        description=t('Scene.eye_rotation_y.desc'),
        default=0,
        min=-19,
        max=19,
        step=1,
        subtype='FACTOR',
        update=Eyetracking.set_rotation
    )

    Scene.iris_height = IntProperty(
        name=t('Scene.iris_height.label'),
        description=t('Scene.iris_height.desc'),
        default=0,
        min=0,
        max=100,
        step=1,
        subtype='FACTOR'
    )

    Scene.eye_blink_shape = FloatProperty(
        name=t('Scene.eye_blink_shape.label'),
        description=t('Scene.eye_blink_shape.desc'),
        default=1.0,
        min=0.0,
        max=1.0,
        step=1.0,
        precision=2,
        subtype='FACTOR'
    )

    Scene.eye_lowerlid_shape = FloatProperty(
        name=t('Scene.eye_lowerlid_shape.label'),
        description=t('Scene.eye_lowerlid_shape.desc'),
        default=1.0,
        min=0.0,
        max=1.0,
        step=1.0,
        precision=2,
        subtype='FACTOR'
    )

    # Visemes

    Scene.viseme_preview_mode = BoolProperty(
        name=t('Scene.viseme_preview_mode.label'),
        description=t('Scene.viseme_preview_mode.desc'),
        default=False
    )
    
    Scene.viseme_preview_selection = EnumProperty(
        name=t('Scene.viseme_preview_selection.label'),
        description=t('Scene.viseme_preview_selection.desc'),
        items=[
            ('vrc.v_aa', 'A', 'Viseme A sound'),
            ('vrc.v_ch', 'CH', 'Viseme CH sound'),
            ('vrc.v_dd', 'DD', 'Viseme DD sound'),
            ('vrc.v_e', 'E', 'Viseme E sound'),
            ('vrc.v_ff', 'FF', 'Viseme FF sound'),
            ('vrc.v_ih', 'IH', 'Viseme IH sound'),
            ('vrc.v_kk', 'KK', 'Viseme KK sound'),
            ('vrc.v_nn', 'NN', 'Viseme NN sound'),
            ('vrc.v_oh', 'OH', 'Viseme OH sound'),
            ('vrc.v_ou', 'OU', 'Viseme OU sound'),
            ('vrc.v_pp', 'PP', 'Viseme PP sound'),
            ('vrc.v_rr', 'RR', 'Viseme RR sound'),
            ('vrc.v_sil', 'SIL', 'Viseme SIL sound'),
            ('vrc.v_ss', 'SS', 'Viseme SS sound'),
            ('vrc.v_th', 'TH', 'Viseme TH sound'),
        ],
        update=lambda self, context: Viseme.VisemePreview.update_preview(context)
    )
    
    Scene.viseme_validate_deformation = BoolProperty(
        name=t('Scene.viseme_validate_deformation.label'),
        description=t('Scene.viseme_validate_deformation.desc'),
        default=True
    )

    Scene.remove_doubles_threshold = FloatProperty(
        name=t('Scene.remove_doubles_threshold.label'),
        description=t('Scene.remove_doubles_threshold.desc'),
        default=0.00002,
        min=0.00001,
        max=0.01,
        precision=6,
        step=0.00001
    )

    Scene.mesh_name_viseme = EnumProperty(
        name=t('Scene.mesh_name_viseme.label'),
        description=t('Scene.mesh_name_viseme.desc'),
        # get_meshes is used elsewhere than for EnumProperty items so must contain the sorting itself
        items=wrap_dynamic_enum_items(Common.get_meshes, 'mesh_name_viseme', sort=False),
    )

    Scene.mouth_a = EnumProperty(
        name=t('Scene.mouth_a.label'),
        description=t('Scene.mouth_a.desc'),
        items=wrap_dynamic_enum_items(Common.get_shapekeys_mouth_ah, 'mouth_a', sort=False),
    )

    Scene.mouth_o = EnumProperty(
        name=t('Scene.mouth_o.label'),
        description=t('Scene.mouth_o.desc'),
        items=wrap_dynamic_enum_items(Common.get_shapekeys_mouth_oh, 'mouth_o', sort=False),
    )

    Scene.mouth_ch = EnumProperty(
        name=t('Scene.mouth_ch.label'),
        description=t('Scene.mouth_ch.desc'),
        items=wrap_dynamic_enum_items(Common.get_shapekeys_mouth_ch, 'mouth_ch', sort=False),
    )

    Scene.shape_intensity = FloatProperty(
        name=t('Scene.shape_intensity.label'),
        description=t('Scene.shape_intensity.desc'),
        default=1.0,
        min=0.0,
        max=10.0,
        step=0.1,
        precision=2,
        subtype='FACTOR'
    )

    # Bone Parenting
    Scene.root_bone = EnumProperty(
        name=t('Scene.root_bone.label'),
        description=t('Scene.root_bone.desc'),
        # Root bone choices get cached, so we don't want to fix them in-place, otherwise the cache would get modified
        items=wrap_dynamic_enum_items(Rootbone.get_parent_root_bones, 'root_bone', sort=False, in_place=False),
    )

    # Optimize
    Scene.optimize_mode = EnumProperty(
        name=t('Scene.optimize_mode.label'),
        description=t('Scene.optimize_mode.desc'),
        items=[
            ("ATLAS", t('Scene.optimize_mode.atlas.label'), t('Scene.optimize_mode.atlas.desc')),
            ("MATERIAL", t('Scene.optimize_mode.material.label'), t('Scene.optimize_mode.material.desc')),
            ("BONEMERGING", t('Scene.optimize_mode.bonemerging.label'), t('Scene.optimize_mode.bonemerging.desc')),
        ]
    )
    # Bone Merging
    Scene.merge_ratio = FloatProperty(
        name=t('Scene.merge_ratio.label'),
        description=t('Scene.merge_ratio.desc'),
        default=50,
        min=1,
        max=100,
        step=1,
        precision=0,
        subtype='PERCENTAGE'
    )

    Scene.merge_mesh = EnumProperty(
        name=t('Scene.merge_mesh.label'),
        description=t('Scene.merge_mesh.desc'),
        # get_meshes is used elsewhere than for EnumProperty items so must contain the sorting itself
        items=wrap_dynamic_enum_items(Common.get_meshes, 'merge_mesh', sort=False),
    )

    Scene.merge_bone = EnumProperty(
        name=t('Scene.merge_bone.label'),
        description=t('Scene.merge_bone.desc'),
        # Root bone choices get cached, so we don't want to fix them in-place, otherwise the cache would get modified
        items=wrap_dynamic_enum_items(Rootbone.get_parent_root_bones, 'merge_bone', sort=False, in_place=False),
    )

    # Settings
    Scene.embed_textures = BoolProperty(
        name=t('Scene.embed_textures.label'),
        description=t('Scene.embed_textures.desc'),
        default=False,
        update=Settings.update_settings
    )
    Scene.ui_lang = EnumProperty(
        name=t('Scene.ui_lang.label'),
        description=t('Scene.ui_lang.desc'),
        items=wrap_dynamic_enum_items(Translations.get_languages_list, 'ui_lang', sort=False),
        update=Translations.update_ui
    )
    Scene.debug_translations = BoolProperty(
        name=t('Scene.debug_translations.label'),
        description=t('Scene.debug_translations.desc'),
        default=False
    )
