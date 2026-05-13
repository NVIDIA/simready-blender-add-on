# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy
import bpy.utils.previews
from bpy.app.handlers import depsgraph_update_post, load_post, persistent
from bpy.props import BoolProperty, EnumProperty, PointerProperty, StringProperty
from bpy.types import Scene

from ..library.simready_utils import get_wikidata_items  # noqa F402
from ..resource.core_blender_libs import *  # noqa F403

# setup icons
LoadCoreIcons()  # noqa F405

# main
from .main_menu import CORE_MT_Main_Menu  # noqa E402
from .mjcf_operators import (  # noqa E402
    SRCORE_OT_export_mjcf,
    SRCORE_OT_import_mjcf_with_converter,
    SRCORE_OT_repair_mujoco_converter,
    menu_func_import_mjcf,
)
from .ot_simready_object_and_mats import (  # noqa E402
    GLOBAL_OT_GenerateCaption,
    GLOBAL_OT_GenerateCaption_Manual,
    METADATA_OT_store_for_root,
    OT_GenerateCaption,
    OT_simready_AddEnumToList,
    OT_simready_AutoPop_Base,
    OT_simready_AutoPop_Coating,
    OT_simready_ClearList,
    SIMREADY_OT_assign_physx_properties,
    SIMREADY_OT_update_physx_properties,
    SimReadyMaterialProps,
    SimReadyProperties,
    WD_OT_apply_to_object,
    WD_OT_refresh_results,
    WD_OT_remove_from_object,
)

# USD Import
from .ot_simready_usd_import import (  # noqa E402
    SIMREADY_OT_import_usd,
    menu_func_import,
)

# Hook
from .ot_simready_usdhook import SimReadyUSDHook  # noqa E402

# Panel order configuration
from .panel_order_config import apply_panel_orders  # noqa E402
from .physics_operators import (  # noqa E402
    SRCORE_OT_apply_drive_preset,
    SRCORE_OT_apply_joint_settings,
    SRCORE_OT_build_unibody_constraints,
    SRCORE_OT_calc_min_max_limits_prismatic,
    SRCORE_OT_clear_grasp_points,
    SRCORE_OT_copy_empty_pos_prismatic,
    SRCORE_OT_copy_empty_position,
    SRCORE_OT_copy_empty_position_fixed,
    SRCORE_OT_create_grasp_points,
    SRCORE_OT_create_simready_collections,
    SRCORE_OT_remove_grasp_pair,
    SRCORE_OT_rename_simready_objects,
    SRCORE_OT_set_sphere_size,
    SRCORE_OT_sync_ui_from_object,
    SRCORE_OT_update_grasp_positions,
    cleanup_timers,
    on_object_selection_change,
    update_grasp_point_positions,
)
from .physics_panels import (  # noqa E402
    SRCORE_PT_grasp_setup,
    SRCORE_PT_JointAttributes,
    SRCORE_PT_MJCF_Import,
    SRCORE_PT_setup_sim_collections,
)
from .physics_playback_operators import (  # noqa E402
    SR_Psy_OT_add_objects_to_physics_env,
    SR_Psy_OT_create_physics_env,
    SR_Psy_OT_joints_to_rbds,
    SR_Psy_OT_reset,
    SR_Psy_OT_throw_rigidbody,
)

# physics
from .physics_properties import (  # noqa E402
    GraspPairProperties,
    GraspPointProperties,
    JointAttributeProperties,
    PhysicsThrowProperties,
    RigidBodyStateProperties,
    SR_Psy_VideoTutorialProps,
)
from .physics_visualizers_operators import (  # noqa E402
    JW_GizmoGroup_Prismatic,
    JW_GizmoGroup_Revolute,
    SRVIZ_OT_OT_find_intersections_multi,
    draw_text_overlay,
    sync_rna_to_constraint,
    sync_rna_to_constraint_prismatic,
)

# Logging
from .pt_add_logging import (  # noqa E402
    CORE_OT_CopyLatestLogPath,
    CORE_OT_OpenLogsFolder,
    CORE_VIEW3D_PT_AddonHelpPanel,
)
from .pt_artist_checklist import (  # noqa E402
    ArtistChecklistGroup,
    ArtistChecklistProps,
    ArtistChecklistSubItem,
    CORE_OT_artist_checklist_launch,
    CORE_OT_artist_checklist_mark_all,
    CORE_OT_artist_checklist_reset,
    CORE_OT_artist_checklist_tip,
    CORE_PT_artist_checklist,
)

# Asset
from .pt_asset_mgmt import CORE_PT_Asset  # noqa E402

# Autochecker
from .pt_autochecker import (  # noqa E402
    AUTOCHECKER_PT_panel,
    EXPORT_OT_simready_usd,
    LAUNCH_VALIDATION_UI_OT_operator,
    menu_func_export,
)
from .pt_learning import (  # noqa E402
    CORE_OT_open_docs,
    CORE_OT_open_docs_with_anchor,
    CORE_PT_documentation,
)

# Main Panel
from .pt_main import CORE_PT_MainPanel  # noqa E402

# profiles
from .pt_profiles_validation import (  # noqa E402
    AssetProfilesProps,
    CORE_OT_Apply_Profile,
    CORE_PT_Asset_Profiles_Validation,
)

# Quick Tools Operators
from .pt_quicktools import (  # noqa E402
    CORE_OT_add_simpbr,
    CORE_OT_add_simpbr_translucent,
    CORE_OT_convert_simpbr,
    CORE_OT_matname_to_clip,
    CORE_OT_mesh_to_locators,
    CORE_OT_objname_copy,
    CORE_OT_prop_platform,
    CORE_OT_reference_figure,
    CORE_OT_reference_figure_prop,
    CORE_OT_vehicle_platform,
    CORE_PT_Build_Asset_Name,
    CORE_PT_Build_Mat_Name,
    CORE_PT_Tools_Misc,
    SRVIZ_PT_intersections_panel,
)
from .pt_simready_meta_ui import (  # noqa E402
    CORE_SIMREADY_PT_top_panel,
)
from .pt_simready_object_and_mats import (  # noqa E402
    MATERIAL_PT_simready_nonvisual,
    WD_PT_data_panel,
    WD_PT_panel,
)

# Avsim
from .pt_simready_vehicles import (  # noqa E402
    AVSim_OT_generate_vehicle_attributes,
    AVSim_OT_set_light_color,
    AVSim_PT_vehicle_attributes,
    AVSimProps,
)

# make source art dir
from .pt_sub_make_sourceart_dir import (  # noqa E402
    Asset_Mgmt_Props,
    CORE_OT_make_dir,
    CORE_OT_OpenDirectoryBrowser,
    CORE_PT_make_source_dir,
)

# Thumbnails
from .pt_thumbnailer import (  # noqa E402
    LIGHTING_PRESET_ITEMS,
    AssetVariantProps,
    CameraSettingsProps,
    CameraTargetProps,
    CORE_OT_Auto_Thumbnail,
    CORE_OT_Load_Lighting_Rig,
    CORE_OT_Render_Thumbnail,
    CORE_OT_Render_Turntable,
    CORE_OT_Reset_Thumbnail_Camera,
    CORE_OT_Select_Light_Prim,
    CORE_OT_Toggle_Safe_Areas,
    CORE_PT_Thumbnailer,
    LightingOrientationProps,
    ProgressBarProps,
    cancel_light_exclude_retry_timer,
)

classes = (
    Asset_Mgmt_Props,
    CORE_OT_make_dir,
    CORE_OT_OpenDirectoryBrowser,
    CORE_OT_prop_platform,
    CORE_OT_reference_figure_prop,
    CORE_OT_reference_figure,
    CORE_OT_vehicle_platform,
    CORE_OT_mesh_to_locators,
    CORE_OT_convert_simpbr,
    CORE_OT_add_simpbr,
    CORE_OT_add_simpbr_translucent,
    # LOGGING
    CORE_OT_OpenLogsFolder,
    CORE_OT_CopyLatestLogPath,
    CORE_VIEW3D_PT_AddonHelpPanel,
    # EXPORT AND PREFLIGHT
    LAUNCH_VALIDATION_UI_OT_operator,
    EXPORT_OT_simready_usd,
    AUTOCHECKER_PT_panel,
    # USD IMPORT
    SIMREADY_OT_import_usd,
    # MAIN PANEL
    CORE_MT_Main_Menu,
    CORE_PT_MainPanel,
    # PRIMARY PANELS
    CORE_PT_Tools_Misc,
    CORE_PT_Asset,
    # SECONDARY PANELS
    CORE_PT_make_source_dir,
    CORE_PT_documentation,
    CORE_OT_open_docs,
    CORE_OT_open_docs_with_anchor,
    CORE_PT_artist_checklist,
    CORE_OT_artist_checklist_launch,
    CORE_OT_artist_checklist_reset,
    CORE_OT_artist_checklist_mark_all,
    CORE_OT_artist_checklist_tip,
    ArtistChecklistSubItem,
    ArtistChecklistGroup,
    ArtistChecklistProps,
    # MATERIALS
    CORE_PT_Build_Mat_Name,
    # Build_Mat_Name_Properties,
    CORE_OT_matname_to_clip,
    CORE_OT_objname_copy,
    CORE_PT_Build_Asset_Name,
    # ASSET PROFILES VALIDATION
    AssetProfilesProps,
    CORE_OT_Apply_Profile,
    CORE_PT_Asset_Profiles_Validation,
    # THUMBNAILS
    AssetVariantProps,
    CameraSettingsProps,
    CameraTargetProps,
    LightingOrientationProps,
    ProgressBarProps,
    CORE_PT_Thumbnailer,
    CORE_OT_Toggle_Safe_Areas,
    CORE_OT_Select_Light_Prim,
    CORE_OT_Load_Lighting_Rig,
    CORE_OT_Auto_Thumbnail,
    CORE_OT_Reset_Thumbnail_Camera,
    CORE_OT_Render_Thumbnail,
    CORE_OT_Render_Turntable,
    # SIMREADY
    MATERIAL_PT_simready_nonvisual,
    WD_PT_panel,
    WD_PT_data_panel,
    CORE_SIMREADY_PT_top_panel,
    OT_GenerateCaption,
    WD_OT_apply_to_object,
    WD_OT_remove_from_object,
    WD_OT_refresh_results,
    METADATA_OT_store_for_root,
    GLOBAL_OT_GenerateCaption,
    GLOBAL_OT_GenerateCaption_Manual,
    OT_simready_AutoPop_Coating,
    OT_simready_AutoPop_Base,
    OT_simready_ClearList,
    OT_simready_AddEnumToList,
    SimReadyMaterialProps,
    SimReadyUSDHook,
    SIMREADY_OT_update_physx_properties,
    SimReadyProperties,
    SIMREADY_OT_assign_physx_properties,
    AVSim_PT_vehicle_attributes,
    AVSim_OT_generate_vehicle_attributes,
    AVSim_OT_set_light_color,
    AVSimProps,
    # PHYSICS
    JointAttributeProperties,
    SR_Psy_VideoTutorialProps,
    GraspPairProperties,
    GraspPointProperties,
    RigidBodyStateProperties,
    PhysicsThrowProperties,
    # Physics Operators
    SRCORE_OT_apply_joint_settings,
    SRCORE_OT_sync_ui_from_object,
    SRCORE_OT_apply_drive_preset,
    SRCORE_OT_copy_empty_position,
    SRCORE_OT_copy_empty_position_fixed,
    SRCORE_OT_copy_empty_pos_prismatic,
    SRCORE_OT_calc_min_max_limits_prismatic,
    SRCORE_OT_create_simready_collections,
    SRCORE_OT_rename_simready_objects,
    SRCORE_OT_build_unibody_constraints,
    SRCORE_OT_create_grasp_points,
    SRCORE_OT_update_grasp_positions,
    SRCORE_OT_set_sphere_size,
    SRCORE_OT_clear_grasp_points,
    SRCORE_OT_remove_grasp_pair,
    # Physics Playback Operators
    SR_Psy_OT_throw_rigidbody,
    SR_Psy_OT_reset,
    SR_Psy_OT_create_physics_env,
    SR_Psy_OT_add_objects_to_physics_env,
    SR_Psy_OT_joints_to_rbds,
    # MJCF Operators
    SRCORE_OT_import_mjcf_with_converter,
    SRCORE_OT_export_mjcf,
    SRCORE_OT_repair_mujoco_converter,
    # Physics Panels
    SRCORE_PT_setup_sim_collections,
    SRCORE_PT_JointAttributes,
    SRCORE_PT_MJCF_Import,
    SRCORE_PT_grasp_setup,
    SRVIZ_PT_intersections_panel,
    # Physics Visualizers
    SRVIZ_OT_OT_find_intersections_multi,
    JW_GizmoGroup_Revolute,
    JW_GizmoGroup_Prismatic,
)

# global var for icons
core_icons = None

# Global draw handler for text overlay
_draw_handler_text = None

# Re-entrancy guard for depsgraph handlers registered in this module
_in_ui_depsgraph_handler = False

# Keymaps for this addon
addon_keymaps = []


def register_keymap():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
        kmi = km.keymap_items.new(SR_Psy_OT_throw_rigidbody.bl_idname, "RIGHTMOUSE", "PRESS", shift=True)
        addon_keymaps.append((km, kmi))


def unregister_keymap():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()


# Clean up any invalid wikidata_results values on scene load
@persistent
def cleanup_wikidata_enum(dummy):
    """Clean up invalid enum values when scene loads"""
    for scene in bpy.data.scenes:
        try:
            # Check if the property exists and has an invalid value
            if hasattr(scene, "wikidata_results"):
                current_value = getattr(scene, "wikidata_results", "NONE")
                # If the value is not 'NONE' (the safe default), reset it
                if current_value != "NONE":
                    scene.property_unset("wikidata_results")
        except (AttributeError, TypeError):
            # Property might not exist or have issues, skip
            continue


@persistent
def monitor_thumbnail_collection(dummy):
    """Monitor for removal of THUMBNAIL collection and disable lighting controls"""
    global _in_ui_depsgraph_handler
    if _in_ui_depsgraph_handler:
        return
    _in_ui_depsgraph_handler = True
    try:
        # Check all scenes for the lighting rig loaded flag
        for scene in bpy.data.scenes:
            # Only check if the flag was previously set to True
            if getattr(scene, "core_lighting_rig_loaded", False):
                # If THUMBNAIL collection is missing, set flag to False.
                # Assign only when the value actually changes to avoid re-triggering the depsgraph.
                if "THUMBNAIL" not in bpy.data.collections:
                    scene.core_lighting_rig_loaded = False
    except Exception:
        # Silently handle any errors during monitoring
        pass
    finally:
        _in_ui_depsgraph_handler = False


def register_ui():
    # Apply panel orders from config before registration
    applied_orders = apply_panel_orders()
    print(f"Applied panel orders to {len(applied_orders)} panels")

    # Register properties first
    bpy.types.Scene.blip_caption = StringProperty(name="Caption", default="")
    bpy.types.Scene.wikidata_query = StringProperty(name="Search Term", default="car")

    bpy.types.Scene.wikidata_results = EnumProperty(
        name="Wikidata Results", description="Search results from Wikidata", items=get_wikidata_items
    )

    # Register the scene load handler
    if cleanup_wikidata_enum not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(cleanup_wikidata_enum)

    bpy.types.Object.jw_rotation_limit_min_rna = bpy.props.FloatProperty(
        name="Rotation Limit Min",
        description="Minimum rotation limit in radians",
        default=-0.785,  # -45 degrees
        min=-math.pi,  # noqa F405
        max=math.pi,  # noqa F405
        soft_min=-math.pi,  # noqa F405
        soft_max=math.pi,  # noqa F405
        subtype="ANGLE",
        update=sync_rna_to_constraint,
    )

    bpy.types.Object.jw_rotation_limit_max_rna = bpy.props.FloatProperty(
        name="Rotation Limit Max",
        description="Maximum rotation limit in radians",
        default=0.785,  # 45 degrees
        min=-math.pi,  # noqa F405
        max=math.pi,  # noqa F405
        soft_min=-math.pi,  # noqa F405
        soft_max=math.pi,  # noqa F405
        subtype="ANGLE",
        update=sync_rna_to_constraint,
    )

    # Register RNA properties on Object type for prismatic joint limits
    bpy.types.Object.jw_translation_limit_min_rna = bpy.props.FloatProperty(
        name="Translation Limit Min",
        description="Minimum translation limit in world units",
        default=-1.0,
        min=-10.0,
        max=10.0,
        soft_min=-10.0,
        soft_max=10.0,
        unit="LENGTH",
        update=sync_rna_to_constraint_prismatic,
    )

    bpy.types.Object.jw_translation_limit_max_rna = bpy.props.FloatProperty(
        name="Translation Limit Max",
        description="Maximum translation limit in world units",
        default=1.0,
        min=-10.0,
        max=10.0,
        soft_min=-10.0,
        soft_max=10.0,
        unit="LENGTH",
        update=sync_rna_to_constraint_prismatic,
    )

    bpy.types.Object.jw_translation_default = bpy.props.FloatVectorProperty(
        name="Translation Default",
        description="Default translation value",
        size=3,
        subtype="XYZ",
    )

    bpy.types.Object.jw_rotation_default = bpy.props.FloatVectorProperty(
        name="Rotation Default",
        description="Default rotation value",
        size=3,
        subtype="EULER",
    )

    # Then register classes
    from bpy.utils import register_class

    for cls in classes:
        try:
            register_class(cls)
        except ValueError as e:
            if "already registered" in str(e):
                print(f"Warning: Class {cls.__name__} was already registered, skipping...")
            else:
                raise e

    # properties registered manually
    bpy.types.Scene.artist_checklist = PointerProperty(type=ArtistChecklistProps)
    bpy.types.Material.simready_props = PointerProperty(type=SimReadyMaterialProps)
    bpy.types.Scene.a_props = PointerProperty(type=Asset_Mgmt_Props)
    bpy.types.Scene.asset_profiles = PointerProperty(type=AssetProfilesProps)
    bpy.types.Scene.asset_variant_props = PointerProperty(type=AssetVariantProps)
    bpy.types.Scene.camera_settings_props = PointerProperty(type=CameraSettingsProps)
    bpy.types.Scene.camera_target_props = PointerProperty(type=CameraTargetProps)
    bpy.types.Scene.lighting_orientation_props = PointerProperty(type=LightingOrientationProps)
    bpy.types.Scene.progress_bar_props = bpy.props.PointerProperty(type=ProgressBarProps)
    bpy.types.Scene.core_lighting_preset = EnumProperty(
        name="Lighting Preset",
        description="Choose a lighting setup for the rig",
        items=LIGHTING_PRESET_ITEMS,
        default="STUDIO",
    )
    bpy.types.Scene.core_lighting_rig_loaded = BoolProperty(
        name="Lighting Rig Loaded",
        description="True after the lighting rig is successfully loaded",
        default=False,
    )
    bpy.types.Scene.type_dropdown = bpy.props.EnumProperty(
        name="Asset Type",
        description="Select an option",
        items=[
            ("VEHICLE", "Vehicle", ""),
            ("PROP", "Prop", ""),
        ],
        default="PROP",
    )

    bpy.types.Scene.core_export_format = bpy.props.EnumProperty(
        name="Export Format",
        description="Choose the export format for your workflow",
        items=[
            ("ALL", "All", "Export all formats", 0),
            ("MUJOCO", "MuJoCo", "Export for MuJoCo physics simulation", 1),
            # Add more formats here in the future:
            # ('CAD', "CAD", "Export for CAD software", 2),
            # ('URDF', "URDF", "Export URDF format", 3),
        ],
        default="ALL",
    )
    bpy.types.Scene.avsim_props = PointerProperty(type=AVSimProps)
    bpy.types.Scene.joint_attribute_props = PointerProperty(type=JointAttributeProperties)
    bpy.types.Scene.sr_psy_video_tutorial_props = PointerProperty(type=SR_Psy_VideoTutorialProps)
    bpy.types.Scene.grasp_point_props = PointerProperty(type=GraspPointProperties)
    bpy.types.Scene.throw_rb_props = PointerProperty(type=PhysicsThrowProperties)
    depsgraph_update_post.append(update_grasp_point_positions)
    depsgraph_update_post.append(on_object_selection_change)
    depsgraph_update_post.append(monitor_thumbnail_collection)
    load_post.append(cleanup_timers)

    # Register draw handler for text overlay
    from bpy.types import SpaceView3D

    global _draw_handler_text
    _draw_handler_text = SpaceView3D.draw_handler_add(draw_text_overlay, (), "WINDOW", "POST_PIXEL")

    # Add SimReady USD to File > Export menu
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

    # Add SimReady USD to File > Import menu
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

    # Add MJCF import to File > Import menu
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_mjcf)


def unregister_ui():
    from bpy.utils import unregister_class

    cancel_light_exclude_retry_timer()

    # Unregister draw handler for text overlay
    from bpy.types import SpaceView3D

    global _draw_handler_text
    if _draw_handler_text:
        try:
            SpaceView3D.draw_handler_remove(_draw_handler_text, "WINDOW")
        except Exception:
            pass
        _draw_handler_text = None

    # Remove SimReady USD from File > Export menu
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    # Remove SimReady USD from File > Import menu
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    # Remove MJCF import from File > Import menu
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_mjcf)

    for cls in reversed(classes):
        unregister_class(cls)

    # Remove the scene load handler
    if cleanup_wikidata_enum in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(cleanup_wikidata_enum)

    # cleanup manually registered properties
    del bpy.types.Scene.a_props
    del bpy.types.Scene.type_dropdown
    del bpy.types.Scene.core_export_format
    del bpy.types.Scene.blip_caption
    del bpy.types.Scene.wikidata_query
    del bpy.types.Scene.wikidata_results
    del bpy.types.Scene.avsim_props
    del bpy.types.Scene.asset_profiles
    del bpy.types.Scene.asset_variant_props
    del bpy.types.Scene.camera_settings_props
    del bpy.types.Scene.camera_target_props
    del bpy.types.Scene.lighting_orientation_props
    del bpy.types.Scene.progress_bar_props
    del bpy.types.Scene.core_lighting_preset
    del bpy.types.Scene.core_lighting_rig_loaded
    del bpy.types.Scene.artist_checklist
    del Scene.joint_attribute_props
    del Scene.sr_psy_video_tutorial_props
    del Scene.grasp_point_props
    del Scene.throw_rb_props
    del bpy.types.Object.jw_rotation_limit_min_rna
    del bpy.types.Object.jw_rotation_limit_max_rna
    del bpy.types.Object.jw_translation_limit_min_rna
    del bpy.types.Object.jw_translation_limit_max_rna
    del bpy.types.Object.jw_translation_default
    del bpy.types.Object.jw_rotation_default

    # Remove depsgraph handlers
    if update_grasp_point_positions in depsgraph_update_post:
        depsgraph_update_post.remove(update_grasp_point_positions)
    if on_object_selection_change in depsgraph_update_post:
        depsgraph_update_post.remove(on_object_selection_change)
    if monitor_thumbnail_collection in depsgraph_update_post:
        depsgraph_update_post.remove(monitor_thumbnail_collection)

    unregister_keymap()

    if cleanup_timers in load_post:
        load_post.remove(cleanup_timers)
