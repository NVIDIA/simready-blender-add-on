# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import bpy
from bpy.app.handlers import persistent
from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)


class BlenderEventListener(QObject):
    """
    Listen for blender events and emit a signal when a new file is opened.
    """

    assetOpened = Signal(str)

    def __init__(self):
        super().__init__()
        self.setup_blender_event()

    def setup_blender_event(self):
        @persistent
        def on_asset_opened(dummy):
            """Triggered when a new .blend file is opened."""
            file_path = bpy.data.filepath
            QMetaObject.invokeMethod(self, "emitSignal", Qt.QueuedConnection, Q_ARG(str, file_path))

        """Registers a handler to detect when Blender opens a new file."""
        bpy.app.handlers.load_post.append(on_asset_opened)

    @Slot(str)
    def emitSignal(self, file_path):
        """Ensures thread-safe signal emission."""
        self.assetOpened.emit(file_path)


class ValidationCard(QFrame):
    """Card widget representing a single validation check result."""

    _STATE_STYLES = {
        "running": {"label": "RUNNING", "label_color": "#AAAAAA", "icon": "⟳", "icon_color": "#AAAAAA"},
        "passed": {"label": "PASSED", "label_color": "#76B900", "icon": "✓", "icon_color": "#76B900"},
        "warning": {"label": "WARNING", "label_color": "#C8A000", "icon": "⚠", "icon_color": "#C8A000"},
        "failed": {"label": "FAILED", "label_color": "#CC4444", "icon": "✕", "icon_color": "#CC4444"},
        "critical": {"label": "CRITICAL FAILURE", "label_color": "#CC4444", "icon": "✕", "icon_color": "#CC4444"},
        "perf": {"label": "PERFORMANCE RISK", "label_color": "#C8A000", "icon": "⚠", "icon_color": "#C8A000"},
    }

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ValidationCard")
        self._state = "running"
        self._check_label = label
        self._problematic_data = None
        self._parent_ui = None
        self._setup()

    def _setup(self):
        self.setFixedHeight(90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 8)
        outer.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        self._status_label = QLabel("RUNNING")
        self._status_label.setStyleSheet("font-size: 9px; font-weight: bold; letter-spacing: 1px; color: #AAAAAA;")
        self._icon_label = QLabel("⟳")
        self._icon_label.setStyleSheet("font-size: 16px; color: #AAAAAA;")
        top_row.addWidget(self._status_label)
        top_row.addStretch()
        top_row.addWidget(self._icon_label)

        self._name_label = QLabel(self._check_label)
        self._name_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #FFFFFF;")

        self._desc_label = QLabel("Checking...")
        self._desc_label.setStyleSheet("font-size: 11px; color: #AAAAAA;")
        self._desc_label.setWordWrap(False)

        outer.addLayout(top_row)
        outer.addWidget(self._name_label)
        outer.addWidget(self._desc_label)
        outer.addStretch()

        self._apply_border("running")

    def _apply_border(self, state: str):
        border_colors = {
            "running": "#444444",
            "passed": "#76B900",
            "warning": "#C8A000",
            "failed": "#CC4444",
            "critical": "#CC4444",
            "perf": "#C8A000",
        }
        border_color = border_colors.get(state, "#444444")
        self.setStyleSheet(
            f"QFrame#ValidationCard {{"
            f"  background-color: #1A1A1A;"
            f"  border: 1px solid #2A2A2A;"
            f"  border-left: 3px solid {border_color};"
            f"  border-radius: 4px;"
            f"}}"
        )

    def setState(self, state: str, description: str):
        self._state = state
        style = self._STATE_STYLES.get(state, self._STATE_STYLES["running"])
        self._status_label.setText(style["label"])
        self._status_label.setStyleSheet(
            f"font-size: 9px; font-weight: bold; letter-spacing: 1px; color: {style['label_color']};"
        )
        self._icon_label.setText(style["icon"])
        self._icon_label.setStyleSheet(f"font-size: 16px; color: {style['icon_color']};")
        truncated = description[:55] + "..." if len(description) > 55 else description
        self._desc_label.setText(truncated)
        self._desc_label.setToolTip(description)
        self._apply_border(state)
        if state in ("failed", "critical", "warning", "perf"):
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def getState(self) -> str:
        return self._state

    def setProblematicData(self, plugin_instance, error_objects, instance):
        self._problematic_data = (plugin_instance, error_objects, instance)

    def mousePressEvent(self, event):
        if self._state in ("failed", "critical", "warning", "perf") and self._problematic_data and self._parent_ui:
            # Lazy import to avoid circular dependency (widgets -> asset_problems_ui)
            from .asset_problems_ui import AssetProblemsUI

            dialog = AssetProblemsUI([self._problematic_data], parent_ui=self._parent_ui)
            dialog.show()
        super().mousePressEvent(event)
