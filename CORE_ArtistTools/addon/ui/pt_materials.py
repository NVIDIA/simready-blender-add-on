# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy


class CORE_materials_common:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    bl_options = {"DEFAULT_CLOSED"}


class CORE_PT_materials(CORE_materials_common, bpy.types.Panel):
    bl_idname = "CORE_PT_Materials"
    bl_label = "Materials"
    bl_order = 6

    core_icons = bpy.context.window_manager.custom_icon_previews["main"]

    def draw(self, context):
        layout = self.layout  # noqa F841
        col1 = self.layout.column(align=True)  # noqa F841
