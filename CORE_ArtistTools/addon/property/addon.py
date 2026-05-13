# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy
from bpy.props import PointerProperty  # is this needed

from ..utility.addon import addon_name, get_prefs

# from .color import CORE_Color, draw_color
from .settings import CORE_Settings, draw_settings


class CORE_Props(bpy.types.AddonPreferences):
    bl_idname = addon_name

    # REF to preference property
    # prefs = bpy.context.preferences.addons[__name__].preferences

    # Property Groups
    # IMPORTANT to have pointer properties to the property groups, otherwise blender will error.
    # color: PointerProperty(type=CORE_Color)
    settings: PointerProperty(type=CORE_Settings)

    def draw(self, _context):

        prefs = get_prefs()
        layout = self.layout

        # # General Settings
        # box = layout.box()
        # draw_color(prefs, box)

        # # Drawing settings
        box = layout.box()
        draw_settings(prefs, box)
