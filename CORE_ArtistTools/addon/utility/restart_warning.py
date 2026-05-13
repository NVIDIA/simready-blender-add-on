# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy


class CORE_OT_restart_warning(bpy.types.Operator):
    """Show a warning that Blender needs to be restarted"""

    bl_idname = "core.restart_warning"
    bl_label = "Restart Required"
    bl_options = {"INTERNAL"}

    message: bpy.props.StringProperty(
        name="Message",
        description="The message to display",
        default="Dependencies were installed. Please restart Blender.",
    )

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.alert = True  # Makes it red/warning style

        col = layout.column(align=True)
        col.label(text="⚠ RESTART REQUIRED ⚠", icon="ERROR")
        col.separator()

        # Split the message into lines
        for line in self.message.split("\n"):
            if line.strip():
                col.label(text=line)

        col.separator()
        col.label(text="Please save your work and restart Blender now.", icon="INFO")


def show_restart_warning(message="Dependencies were installed.\nPlease restart Blender for changes to take effect."):
    """Show a restart warning popup in Blender's UI.

    This needs to be called from a timer because Blender's UI might not be ready
    during addon initialization.
    """

    def show_popup():
        try:
            bpy.ops.core.restart_warning("INVOKE_DEFAULT", message=message)
        except Exception as e:
            print(f"Could not show restart warning popup: {e}")
        return None  # Don't repeat the timer

    # Use a timer to defer the popup until Blender's UI is ready
    if not bpy.app.background:  # Only show in GUI mode
        bpy.app.timers.register(show_popup, first_interval=0.1)


__all__ = ["CORE_OT_restart_warning", "show_restart_warning"]
