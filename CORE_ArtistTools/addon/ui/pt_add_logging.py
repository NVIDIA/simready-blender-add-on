# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import bpy
from bpy.types import Operator, Panel

from ..library.addon_logging import *  # noqa F403


class CORE_OT_OpenLogsFolder(bpy.types.Operator):
    bl_idname = "core.open_logs_folder"
    bl_label = "Open Logs Folder"

    def execute(self, context):
        folder = logs_dir()  # noqa F405
        folder.mkdir(parents=True, exist_ok=True)
        import webbrowser

        webbrowser.open(folder.as_uri())
        get_logger().info("Artist opened logs folder: %s", str(folder))  # noqa F405
        return {"FINISHED"}


class CORE_OT_CopyLatestLogPath(Operator):
    bl_idname = "core.dst_copy_latest_log"
    bl_label = "Copy Latest Log Path"

    def execute(self, context):
        p = latest_log_path()  # noqa F405
        if not p:
            self.report({"WARNING"}, "No log file found yet.")
            return {"CANCELLED"}
        context.window_manager.clipboard = str(p)
        get_logger().info("Artist copied log path: %s", str(p))  # noqa F405
        self.report({"INFO"}, f"Copied: {p.name}")
        return {"FINISHED"}


class CORE_VIEW3D_PT_AddonHelpPanel(Panel):
    bl_label = "SimReady Blender Core — Logs"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, ctx):
        col = self.layout.column(align=True)
        col.operator("core.open_logs_folder", icon="FILE_FOLDER")
        col.operator("core.dst_copy_latest_log", icon="COPYDOWN")
