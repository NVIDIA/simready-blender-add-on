# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy

from ..library import *  # noqa F403
from ..utility import *  # noqa F403


# 'ASSET MANAGEMENT' PANEL
class CORE_PT_Asset(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    bl_idname = "CORE_PT_Asset"
    bl_label = "Asset Mgmt"
    bl_order = 2

    def draw(self, context):
        layout = self.layout  # noqa F841
        col1 = self.layout.column(align=True)  # noqa F841
