# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import os
from os.path import exists

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup

from ..library import *  # noqa F403
from ..utility import *  # noqa F403
from ..utility.addon import get_prefs

if os.name == "nt":
    SYS_TYPE = "Windows"
elif os.name == "posix":
    SYS_TYPE = "Linux"
else:
    SYS_TYPE = "Mac"


# COMMON PANEL PROPERTIES
class CORE_asset_mgmt_common:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    # bl_options = {"DEFAULT_CLOSED"}


# ASSET PROPERTIES
class Asset_Mgmt_Props(PropertyGroup):
    asset_name: StringProperty(
        name="", description="Name of the asset you are planning to create.", default="", maxlen=100
    )
    path: StringProperty(
        name="",
        description="Choose a directory location where you would like to build new source asset directory structure.",
        default="",
        maxlen=1024,
        # subtype='DIR_PATH'
    )


class CORE_OT_OpenDirectoryBrowser(Operator):
    bl_idname = "wm.directory_browser"
    bl_label = "Select Directory"

    directory: bpy.props.StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        # Convert to absolute path if the path is relative (starts with //)
        if self.directory.startswith("//"):
            absolute_path = bpy.path.abspath(self.directory)
        else:
            absolute_path = self.directory

        # Check for broken paths and fix them
        if not os.path.exists(absolute_path):
            self.report({"WARNING"}, "Invalid path selected.")
            return {"CANCELLED"}

        # Store the cleaned up path in the scene property
        context.scene.a_props.path = absolute_path
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class CORE_OT_make_dir(Operator):
    bl_label = "Create, Save and Open Blender File"
    bl_description = "Create standardized source art directory structure using asset name and location specified."
    bl_idname = "nvcat.sourceart_dirs_setup"
    # bl_options = {'REGISTER', 'UNDO'} # allows to use undo system

    path: StringProperty()
    asset_name: StringProperty()
    selected_option: StringProperty()
    confirm_replace: BoolProperty(default=False)

    def execute(self, context):
        # user confirms to replace existing asset, proceed with creation
        if self.confirm_replace:
            return self._make_asset_dir(context)

        # check if asset already exists in the parent dir
        if self.path and self.asset_name:
            asset_path = os.path.join(self.path, self.asset_name)
            if os.path.exists(asset_path):
                self.confirm_replace = True  # enter confirmation mode
                # show confirmation dialog and call execute() again if user clicks OK
                return context.window_manager.invoke_props_dialog(self)

        # if no existing asset, proceed directly
        return self._make_asset_dir(context)

    def invoke(self, context, event):
        self.confirm_replace = False  # exit confirmation mode
        return self.execute(context)

    def draw(self, context):
        # draw dialog content if in confirmation mode
        if self.confirm_replace:
            layout = self.layout
            layout.label(text="Asset already exists.", icon="ERROR")
            layout.label(text="Asset: " + self.asset_name)
            layout.label(text="Location: " + self.path)
            layout.separator()
            layout.label(text="Do you want to replace the existing asset?")

    def _make_asset_dir(self, context):

        self.selected_option = context.scene.bld_a_nm_props.assetname_type

        if self.selected_option == "Prop".lower() or self.selected_option == "PROP":
            prop_dirs = CORE_make_source_art_dirs(self.path, self.asset_name, "prop")  # noqa F405

            if "CANCELLED" in prop_dirs:
                self.report({"ERROR"}, "Check your name conforms to prop naming")
                return {"CANCELLED"}

        elif self.selected_option == "Vehicle".lower() or self.selected_option == "VEHICLE":
            vehicle_dirs = CORE_make_source_art_dirs(self.path, self.asset_name, "vehicle")  # noqa F405

            if "CANCELLED" in vehicle_dirs:
                self.report({"ERROR"}, "Check your name conforms to brand_model_year")
                return {"CANCELLED"}
            veh_prefix_path = vehicle_dirs["FINISHED"]

        ShowMessageBox(message="Directory Created", title="Success", icon="INFO")  # noqa F405

        if self.selected_option == "Prop".lower() or self.selected_option == "PROP":
            prefix_path: str = self.path + self.asset_name
        else:
            prefix_path: str = veh_prefix_path

        if SYS_TYPE == "Windows":
            path_sep = "\\"
        else:
            path_sep = "/"

        # Check if project config is set... if not, set it through scanning up the directory tree
        CORE_set_project_config_if_needed(prefix_path)  # noqa F405

        blend_save_file: str = path_sep.join(
            [prefix_path, "dcc_source", "working", "model", "blender", self.asset_name + ".blend"]
        )
        print("blend_save_file:", blend_save_file)
        CORE_save_and_open_current_file(blend_save_file)  # noqa F405

        return {"FINISHED"}


class CORE_PT_make_source_dir(CORE_asset_mgmt_common, Panel):
    bl_idname = "CORE_PT_make_source_dir"
    bl_label = "Make Source Directories"
    bl_parent_id = "CORE_PT_Asset"  # SUB PANEL

    # assetname_type : bpy.props.EnumProperty()

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        prefs = get_prefs()

        layout.prop(scene.bld_a_nm_props, "assetname_type")
        col1 = layout.column(align=True)

        # UI - MAKE SOURCE ART DIR
        col1.label(text="Make Source Art Directory", icon="NODE_COMPOSITING")
        box = col1.box()
        col2 = box.column(align=True)

        # ui - parent dir
        row1 = col2.row(align=True)
        row1.label(text="Choose parent directory:")
        row2 = col2.row(align=True)
        row2.prop(scene.a_props, "path", text="")

        row2.operator("wm.directory_browser", icon="FILE_FOLDER", text="").directory = prefs.settings.ds_project_root

        # ui - asset name
        row3 = col2.row(align=True)
        row3.label(text="Asset Name:")
        row4 = col2.row(align=True)
        row4.prop(bpy.context.scene.a_props, "asset_name")

        # button operator
        row5 = col2.row(align=True)
        row5.separator(factor=2)
        row6 = col2.row(align=True)
        p = row6.operator(CORE_OT_make_dir.bl_idname)
        p.path = context.scene.a_props.path
        p.asset_name = context.scene.a_props.asset_name

        p.selected_option = scene.bld_a_nm_props.assetname_type
        row6.enabled = exists(p.path)
