# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy
from bpy.props import EnumProperty

from ..library import *  # noqa F403
from ..resource.core_blender_libs import *  # noqa F403

# TODO: we will probably add more profiles in the future, but for now we only have one.
ASSET_PROFILE_LIST = [("NONE", "-- Select a Profile --", ""), ("NEUTRAL", "Neutral", "Neutral Asset")]


class AssetProfilesProps(bpy.types.PropertyGroup):
    selected_profile: EnumProperty(
        name="Asset Profiles", description="Select an Asset Profile to Apply", items=ASSET_PROFILE_LIST, default="NONE"
    )


class ASSET_panel_common:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    bl_options = {"DEFAULT_CLOSED"}


class CORE_OT_Apply_Profile(bpy.types.Operator):
    """Apply the profile data based on selected"""

    bl_idname = "core.apply_profile"
    bl_label = "Apply Profile"
    bl_description = ""

    def execute(self, context):
        selected = context.scene.asset_profiles.selected_profile
        self.report({"INFO"}, f"Applying profile data: {selected}")
        return {"FINISHED"}


class CORE_PT_Asset_Profiles_Validation(ASSET_panel_common, bpy.types.Panel):
    """Asset Profiles Validation Panel in N-Panel"""

    bl_idname = "CORE_PT_Asset_Profiles_Validation"
    bl_label = "Asset Profiles"
    bl_order = 15

    def draw(self, context):
        props = context.scene.asset_profiles

        col1 = self.layout.column(align=True)
        col1.prop(props, "selected_profile")
        box = col1.box()
        col2 = box.column(align=True)

        # disable button if no profile is selected
        is_disabled = context.scene.asset_profiles.selected_profile == "NONE"
        col2.enabled = not is_disabled
