# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""
Central configuration file for controlling the display order of all panels in the CORE Artist Tools.
The bl_order property determines the order in which panels appear in Blender's N-Panel sidebar.
Lower numbers appear first (at the top).

Usage:
    1. Import this config in __init__.py
    2. Call apply_panel_orders() after all classes are imported but before registration
    3. Modify the order values here to control panel appearance in the UI

Panel Order Configuration:
    - 0-10:  Main/Primary panels
"""

# ========================================
# MAIN PANELS (Order 0-10)
# ========================================

PANEL_ORDER_CONFIG = {
    # Main entry panel
    "CORE_PT_MainPanel": 0,
    # Documentation and Learning
    "CORE_PT_documentation": 1,
    # Asset Management
    "CORE_PT_Asset": 2,
    "SRCORE_PT_MJCF_Import": 3,
    "SRCORE_PT_setup_sim_collections": 4,
    "SRCORE_PT_JointAttributes": 5,
    # SimReady Metadata (Primary workflow)
    "CORE_SIMREADY_PT_top_panel": 6,
    "SRCORE_PT_grasp_setup": 7,
    # Thumbnailer
    "CORE_PT_Thumbnailer": 8,
    "AUTOCHECKER_PT_panel": 9,
    # Tools
    "CORE_PT_Tools_Misc": 10,  # Quick Tools
    "SRVIZ_PT_intersections_panel": 11,  # Intersections
    "CORE_PT_Asset_Profiles_Validation": 12,
    # "SRCORE_RUNTIME_PT_throw_rigidbody": 26,
    # Logging and Help
    # "CORE_VIEW3D_PT_AddonHelpPanel": 28,
    # Commented/Disabled Panels (for reference)
    # "SRCORE_PT_open_docs": 29,
    # "SRCORE_PT_run_validation": 30,
}


def apply_panel_orders():
    """
    Apply bl_order values to all panel classes based on PANEL_ORDER_CONFIG.

    This function should be called after all panel classes are imported
    but before they are registered with Blender.

    Returns:
        dict: A dictionary of successfully applied orders {class_name: order_value}
    """
    applied_orders = {}

    # Import all panel modules to get access to their classes
    from . import (
        _naming,
        physics_panels,
        pt_add_logging,
        pt_asset_mgmt,
        pt_autochecker,
        pt_learning,
        pt_main,
        pt_profiles_validation,
        pt_quicktools,
        pt_simready_meta_ui,
        pt_simready_object_and_mats,
        pt_simready_vehicles,
        pt_sub_make_sourceart_dir,
        pt_thumbnailer,
    )

    # Map module names to their imported modules
    modules = {
        "pt_main": pt_main,
        "pt_simready_meta_ui": pt_simready_meta_ui,
        "pt_asset_mgmt": pt_asset_mgmt,
        "pt_learning": pt_learning,
        "pt_quicktools": pt_quicktools,
        "pt_sub_make_sourceart_dir": pt_sub_make_sourceart_dir,
        "pt_profiles_validation": pt_profiles_validation,
        "pt_autochecker": pt_autochecker,
        "pt_thumbnailer": pt_thumbnailer,
        "pt_simready_object_and_mats": pt_simready_object_and_mats,
        "pt_simready_vehicles": pt_simready_vehicles,
        "pt_add_logging": pt_add_logging,
        "physics_panels": physics_panels,
        "_naming": _naming,
    }

    # Apply bl_order to each panel class
    for class_name, order_value in PANEL_ORDER_CONFIG.items():
        # Search for the class in all imported modules
        for module_name, module in modules.items():
            if hasattr(module, class_name):
                panel_class = getattr(module, class_name)
                panel_class.bl_order = order_value
                applied_orders[class_name] = order_value
                break

    return applied_orders


def get_panel_order(class_name):
    """
    Get the configured bl_order value for a specific panel class.

    Args:
        class_name (str): The name of the panel class

    Returns:
        int or None: The bl_order value if configured, None otherwise
    """
    return PANEL_ORDER_CONFIG.get(class_name)


def list_all_panel_orders():
    """
    Returns a formatted string listing all panels and their orders.
    Useful for debugging and documentation.

    Returns:
        str: Formatted string showing all panel orders
    """
    sorted_panels = sorted(PANEL_ORDER_CONFIG.items(), key=lambda x: x[1])

    output = ["Panel Order Configuration:", "=" * 50]
    for class_name, order in sorted_panels:
        output.append(f"{order:3d} - {class_name}")

    return "\n".join(output)


# Optional: Print configuration when module is loaded (for debugging)
if __name__ == "__main__":
    print(list_all_panel_orders())
