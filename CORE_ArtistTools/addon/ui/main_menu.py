# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy


class CORE_MT_Main_Menu(bpy.types.Menu):
    bl_idname = "CORE_MT_Main_Menu"
    bl_label = "SimReady Art Tools"

    def draw(self, context):

        layout = self.layout

        layout.operator_context = "INVOKE_DEFAULT"
        layout.label(text="Hello Artists")

        layout.operator("gem.add_lights", text="one", icon="LIGHT")
        layout.operator("gem.solidify", text="two", icon="LIGHTPROBE_PLANAR")
        # layout.StringProperty(name="dfd")
        # bpy.props.StringProperty(name="", description="", default="", maxlen=0, options={'ANIMATABLE'}, subtype='NONE', update=None, get=None, set=None)
