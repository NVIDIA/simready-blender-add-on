# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import os
from pathlib import Path

import bpy
from bpy.props import IntProperty


class CORE_Settings(bpy.types.PropertyGroup):
    # TODO: not sure if this is needed
    bl_idname = __name__

    font_size: IntProperty(name="Font Size", description="Font Size", min=10, max=32, default=12)

    def update_ds_project_config_path(self, context):
        """Ensure the path is always absolute and Windows-compliant"""
        if self.ds_project_config_path:
            abs_path = bpy.path.abspath(self.ds_project_config_path)
            normalized_path = os.path.normpath(abs_path)

            # Only update if the path actually changed to prevent recursion
            if self.ds_project_config_path != normalized_path:
                self.ds_project_config_path = normalized_path

    ds_project_config_path: bpy.props.StringProperty(
        name="",
        default="",
        description="Please locate the project_config.toml file located within the DRIVE Sim content directory"
        + "\n\nThis file contains information needed to properly find and create assets.",
        maxlen=1024,
        subtype="FILE_PATH",
        update=update_ds_project_config_path,  # Call the update function whenever the path is set
    )

    ds_project_root: bpy.props.StringProperty(
        name="",
        default="",
        description="This path is set automatically based on the project_config.toml file location.",
        maxlen=1024,
    )

    ds_nv_core: bpy.props.StringProperty(
        name="",
        default="",
        description="This path is set automatically based on the project_config.toml file location.",
        maxlen=1024,
    )

    ds_source_folder: bpy.props.StringProperty(
        name="",
        default="",
        description="This path is set automatically based on the project_config.toml file location.",
        maxlen=1024,
    )

    debug_no_usd_hook: bpy.props.BoolProperty(
        name="No USD Hook",
        description="If enabled, the USD hook will not be used.  This is useful for debugging.",
        default=False,
    )

    debug_no_mdl: bpy.props.BoolProperty(
        name="No MDL",
        description="If enabled, the MDL shader will not be used.  This is useful for debugging.",
        default=False,
    )


def draw_settings(prefs, layout):
    """Draws the settings UI for the add-on"""

    def set_project_root(prj_cfg_path) -> str:
        """Sets the project root path based on the project_config.toml file location"""
        if prj_cfg_path:
            blend_abs_prj_cfg_path = bpy.path.abspath(prj_cfg_path)
            proj_cfg_clean_path = os.path.normpath(blend_abs_prj_cfg_path)
            root_path = Path(proj_cfg_clean_path)
            return str(root_path.parents[1])
        return ""

    def set_nv_core(prj_cfg_path) -> str:
        """Sets the nv_core path based on the project_config.toml file location"""
        if prj_cfg_path:
            blend_abs_prj_cfg_path = bpy.path.abspath(prj_cfg_path)
            proj_cfg_clean_path = os.path.normpath(blend_abs_prj_cfg_path)
            prj_path = Path(proj_cfg_clean_path)
            root_path = str(prj_path.parents[1])
            return os.path.join(root_path, "nv_core")
        return ""

    def set_source_folder(prj_cfg_path) -> str:
        """Sets the source folder path based on the project_config.toml file location"""
        if prj_cfg_path:
            blend_abs_prj_cfg_path = bpy.path.abspath(prj_cfg_path)
            proj_cfg_clean_path = os.path.normpath(blend_abs_prj_cfg_path)
            prj_path = Path(proj_cfg_clean_path)
            root_path = str(prj_path.parents[1])
            return os.path.join(root_path, "dcc_core_tools")
        return ""

    layout.label(text="General Settings", icon="TOOL_SETTINGS")

    # Tools
    box = layout.box()

    # row = box.row()
    # split = row.split(factor=0.3)
    # split.label(text="Font Size")
    # row.label(text='Font Size')
    # split.prop(prefs.settings, 'font_size')
    row_alpha = box.row()
    row_alpha.prop(prefs.settings, "debug_no_usd_hook")
    row_beta = box.row()
    row_beta.prop(prefs.settings, "debug_no_mdl")

    row = box.row()
    split = row.split(factor=0.3)
    split.label(text="Pick config file")
    split.prop(prefs.settings, "ds_project_config_path")

    row2 = box.row()
    split2 = row2.split(factor=0.3)
    split2.label(text="Project Root")

    prefs.settings.ds_project_root = set_project_root(prefs.settings.ds_project_config_path)
    split2.prop(prefs.settings, "ds_project_root")

    row3 = box.row()
    split3 = row3.split(factor=0.3)
    split3.label(text="nv_core")

    prefs.settings.ds_nv_core = set_nv_core(prefs.settings.ds_project_config_path)
    split3.prop(prefs.settings, "ds_nv_core")

    row4 = box.row()
    split4 = row4.split(factor=0.3)
    split4.label(text="Source Folder")

    prefs.settings.ds_source_folder = set_source_folder(prefs.settings.ds_project_config_path)
    split4.prop(prefs.settings, "ds_source_folder")
