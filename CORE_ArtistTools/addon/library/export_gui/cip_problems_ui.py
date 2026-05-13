# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import bpy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from CORE_ArtistTools.addon.validators.logging_controller import logger

from .theme import FONT_FAMILY, THEME
from .utils import message_box


class CIPProblemAssetsUI(QDialog):
    def __init__(self, validation_results, parent_ui):
        """
        validation_results: list of validation results from CIP
        parent_ui: reference to the parent ValidationUI instance
        """
        super().__init__()
        self.log = logger
        self.setWindowTitle("CIP Validation: Problem Assets")
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        self.parent_ui = parent_ui
        self.validation_results = validation_results

        import json

        print("validation_results:")
        print(json.dumps(validation_results, indent=4, default=str))

        self.resize(800, 1000)

        layout = QVBoxLayout(self)

        self.setStyleSheet(f"""
            QDialog, QWidget {{
                background-color: {THEME['bg_base']};
                color: {THEME['text_primary']};
                font-family: {FONT_FAMILY};
            }}
            QLabel {{
                background-color: transparent;
            }}
            QTreeWidget {{
                background-color: {THEME['bg_card']};
                border: 1px solid {THEME['border']};
                color: {THEME['text_primary']};
            }}
            QHeaderView::section {{
                background-color: {THEME['bg_mid']};
                padding: 5px;
                font-weight: bold;
                border: 1px solid {THEME['border_strong']};
                color: {THEME['text_secondary']};
            }}
            QTreeWidget::item {{
                background-color: {THEME['bg_card']};
                border-bottom: 1px solid {THEME['border']};
                padding: 2px;
            }}
            QTreeWidget::item:selected {{
                background-color: {THEME['bg_mid']};
                border-left: 2px solid {THEME['accent']};
            }}
            QPushButton {{
                background-color: transparent;
                color: {THEME['text_primary']};
                border: 2px solid {THEME['border_strong']};
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: {THEME['accent']};
                color: {THEME['accent']};
            }}
            QPushButton:disabled {{
                background-color: {THEME['bg_mid']};
                color: {THEME['text_dim']};
                border-color: {THEME['border']};
            }}
            QScrollBar:vertical {{
                background-color: {THEME['bg_mid']};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {THEME['border_strong']};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Asset", "Actions", "Status"])
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.tree)

        # Group results by asset
        asset_groups = {}
        for result in validation_results:
            asset = result["Asset"]
            if asset not in asset_groups:
                asset_groups[asset] = []
            asset_groups[asset].append(result)

        for asset, results in asset_groups.items():
            asset_item = QTreeWidgetItem([asset])
            self.tree.addTopLevelItem(asset_item)

            for result in results:
                severity = result["Severity"].lower()
                if severity == "error":
                    status = "❌ Error"
                    item_status = "failed"
                elif severity == "warning":
                    status = "⚠️ Warning"
                    item_status = "warning"
                else:
                    status = "ℹ️ Info"
                    item_status = "info"

                child_item = QTreeWidgetItem(
                    [
                        result["Rule"],
                        status,
                        f"{result['Message']}\nSuggestion: {result['Suggestion']}\nLocation: {result['Location']}",
                    ]
                )

                child_item.setData(1, Qt.UserRole, item_status)
                asset_item.addChild(child_item)

                action_widget = QWidget()
                action_layout = QHBoxLayout(action_widget)
                action_layout.setContentsMargins(0, 0, 0, 0)

                select_button = QPushButton("Select")
                select_button.clicked.connect(lambda _, r=result: self.select_object(r))
                action_layout.addWidget(select_button)

                action_layout.addStretch()
                self.tree.setItemWidget(child_item, 1, action_widget)

        self.tree.expandAll()

    def select_object(self, result):
        """Select the object in Blender based on the CIP validation result location"""

        def location_mapping(location):
            location_list = location.split("/")
            collection_name = location_list[2]
            object_name = location_list[3].replace(">", "").replace("<", "")
            return collection_name, object_name

        try:
            collection_name, object_name = location_mapping(result["Location"])

            collection = bpy.data.collections.get(collection_name)
            if not collection:
                message_box("Error", f"Collection '{collection_name}' not found")
                return

            obj = None
            for o in collection.objects:
                if o.name == object_name:
                    obj = o
                    break

            if not obj:
                message_box("Error", f"Object '{object_name}' not found in collection '{collection_name}'")
                return

            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj

        except Exception as e:
            self.log.error(f"Error selecting object: {str(e)}")
            message_box("Error", f"Failed to select object: {str(e)}")
