# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

# INFO: don't use threading with blender.  Use QTimer instead
# Blender won't destroy threads when opening a new file...this will leave QTimers stranded
# So workaround is to process events every 10ms to keep the UI responsive and let Blender handle the threading
# Also Qtimer here is working within the Blender event system.
# import threading
import sys

import bpy
from PySide6.QtCore import QObject, QTimer, Slot
from PySide6.QtWidgets import QApplication

from ..library import *  # noqa F403
from ..library.export_gui import ValidationUI
from ..resource.core_blender_libs import *  # noqa F403


class ASSET_panel_common:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    bl_options = {"DEFAULT_CLOSED"}


class UIInvoker(QObject):
    """Helper class to run UI updates in the main thread."""

    # slots are QTs way of finding methods to call
    @Slot()
    def create_ui(self):
        global ui  # Prevent garbage collection
        ui = ValidationUI()
        ui.show()

        ui.destroyed.connect(self.cleanup)

    @Slot()
    def cleanup(self):
        print("Validation UI closed. Releasing Blender UI...")
        global app
        if app:
            app.quit()


def launch_validation_ui():

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    invoker = UIInvoker()
    QTimer.singleShot(0, invoker.create_ui)

    def process_qt_events():
        """
        Process Qt events every 10ms within event loop
        """
        app.processEvents()
        QTimer.singleShot(10, process_qt_events)

    process_qt_events()


class LAUNCH_VALIDATION_UI_OT_operator(bpy.types.Operator):
    """Launch Validation Autochecker UI"""

    bl_idname = "nvcat.launch_validation_ui"
    bl_label = "Open Validator UI"

    def execute(self, context):
        launch_validation_ui()
        return {"FINISHED"}


class EXPORT_OT_simready_usd(bpy.types.Operator):
    """Export SimReady USD - Launch validation and export UI"""

    bl_idname = "export_scene.simready_usd"
    bl_label = "SimReady USD (.usd)"
    bl_description = "Export asset as SimReady USD with validation"

    def execute(self, context):
        launch_validation_ui()
        return {"FINISHED"}


def menu_func_export(self, context):
    """Add SimReady USD to File > Export menu"""
    self.layout.operator(EXPORT_OT_simready_usd.bl_idname, text="SimReady USD (.usd)")


class AUTOCHECKER_PT_panel(ASSET_panel_common, bpy.types.Panel):
    """Validation Panel in N-Panel"""

    bl_label = "Preflight & Export"
    bl_idname = "CORE_PT_Export"
    bl_description = "Validate, Autofix and Export"
    bl_order = 16

    def draw(self, context):
        layout = self.layout
        export_props = context.scene.export_props
        layout.prop(export_props, "poseable_only", text="Poseable Only")
        layout.operator("nvcat.launch_validation_ui", text="Run Validation(s)")
