# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from bpy.types import Panel

from ..library import *  # noqa F403
from ..utility import *  # noqa F403


class CORE_MainPanel_info:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    bl_idname = "main_info"
    bl_label = "CORE Artist Tools"

    @property
    def version(self):
        try:
            # Get the addon module and access its bl_info
            import CORE_ArtistTools

            version_tuple = CORE_ArtistTools.bl_info["version"]
            return ".".join(str(x) for x in version_tuple)
        except (ImportError, KeyError, AttributeError):
            return "Version cannot be read!!"

    # bl_options = {"DEFAULT_CLOSED"}


# ------------------------PANEL---------------------
class CORE_PT_MainPanel(CORE_MainPanel_info, Panel):
    bl_idname = "CORE_PT_main_panel"
    bl_label = "SimReady Blender Core"

    def draw(self, _context):
        layout = self.layout  # noqa F841
        layout.label(text="addon version: " + self.version)
        layout.label(text="version: 2026.04.0")
