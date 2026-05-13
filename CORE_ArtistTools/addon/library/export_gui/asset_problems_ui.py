# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import bpy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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

from .models import ValidationContext, ValidationInstance
from .theme import FONT_FAMILY, THEME
from .utils import message_box


class AssetProblemsUI(QDialog):
    def __init__(self, problems, parent_ui):
        """
        problems: list of tuples (plugin, invalid_objects, instance)
        parent_ui: reference to the parent ValidationUI instance
        """
        super().__init__()
        self.log = logger
        self.setWindowTitle("DS Blender: Eval and Fix")

        self.parent_ui = parent_ui

        # Filter out any None objects or deleted materials/objects from problems
        self.problems = []
        for plugin, invalid_objects, instance in problems:
            valid_objects = []
            for obj_tuple in invalid_objects:
                obj = obj_tuple[0]

                if isinstance(obj, bpy.types.Material):
                    if obj.name not in bpy.data.materials:
                        continue

                if isinstance(obj, bpy.types.Object):
                    if obj.name not in bpy.data.objects:
                        continue

                valid_objects.append(obj_tuple)

            if valid_objects:
                self.problems.append((plugin, valid_objects, instance))

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
            QCheckBox {{
                color: {THEME['text_primary']};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid #555555;
                border-radius: 3px;
                background-color: {THEME['bg_mid']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {THEME['accent']};
                border-color: {THEME['accent']};
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
        self.tree.setHeaderLabels(["Plugin / Asset", "Actions", "Status"])
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.tree)

        for plugin, invalid_objects, instance in self.problems:
            plugin_item = QTreeWidgetItem([getattr(plugin, "label")])
            self.tree.addTopLevelItem(plugin_item)

            if hasattr(plugin, "actions") and plugin.actions:
                fix_actions = [action for action in plugin.actions if hasattr(action, "process")]
                if fix_actions:
                    action_instance = fix_actions[0]()
                    action_label = getattr(action_instance, "label", "Autofix All")

                    if "select" in action_label.lower():
                        button_text = "Select Objects"
                    else:
                        button_text = "Autofix All"

                    fix_button = QPushButton(button_text)
                    fix_button.clicked.connect(
                        lambda _, p=plugin, inst=instance, item=plugin_item: self.run_plugin_autofix(p, inst, item)
                    )
                    self.tree.setItemWidget(plugin_item, 1, fix_button)

            for item in invalid_objects:
                is_not_fixable = False
                if len(item) > 2:
                    obj, message, is_not_fixable = item
                else:
                    obj, message = item

                if is_not_fixable and "[NOT FIXABLE]" not in message:
                    message = f"[NOT FIXABLE] {message}"

                status_text = "⚠️ Warning" if "⚠️" in message else "❌ Error"
                if is_not_fixable:
                    status_text = "⛔ Not Fixable"

                child_item = QTreeWidgetItem([obj, "", status_text])
                plugin_item.addChild(child_item)

                if is_not_fixable:
                    child_item.setData(0, Qt.UserRole, "not-fixable")
                elif "warning" in status_text.lower():
                    child_item.setData(0, Qt.UserRole, "warning")
                elif "failed" in status_text.lower():
                    child_item.setData(0, Qt.UserRole, "failed")

                if obj is not None:
                    if hasattr(obj, "name") and obj.name == "Light":
                        child_item.setText(0, "Scene")
                    else:
                        child_item.setText(0, obj.name)

                child_item.setText(2, str(message))

                action_widget = QWidget()
                action_layout = QHBoxLayout(action_widget)
                action_layout.setContentsMargins(0, 0, 0, 0)

                select_button = QPushButton("Select")

                if obj is not None:
                    select_button.clicked.connect(lambda _, o=obj: self.select_object(o))
                else:
                    select_button.setEnabled(False)
                    select_button.setToolTip("Cannot select: Object is None or missing")
                action_layout.addWidget(select_button)

                if hasattr(plugin, "actions") and plugin.actions and not is_not_fixable:
                    fix_actions = [action for action in plugin.actions if hasattr(action, "process")]
                    if fix_actions:
                        action_instance = fix_actions[0]()
                        action_label = getattr(action_instance, "label", "Autofix")

                        if "select" in action_label.lower():
                            button_text = "Select"
                        else:
                            button_text = "Autofix"

                        fix_button = QPushButton(button_text)
                        fix_button.clicked.connect(
                            lambda _, p=plugin, inst=instance, o=obj, item=child_item, btn=fix_button: self.run_object_autofix(
                                p, inst, o, item, btn
                            )
                        )
                        action_layout.addWidget(fix_button)

                if (
                    hasattr(plugin, "label")
                    and "Source Art Folders" in plugin.label
                    and "directory" in message.lower()
                    and ("README" in message or "Documentation" in message)
                ):
                    print("DEBUG: Adding View Docs button")
                    docs_button = QPushButton("View Docs")
                    docs_button.clicked.connect(lambda: self.open_documentation())
                    action_layout.addWidget(docs_button)
                else:
                    print("DEBUG: View Docs button conditions not met")
                    if is_not_fixable:
                        not_fixable_label = QPushButton("Not Fixable")
                        not_fixable_label.setEnabled(False)
                        not_fixable_label.setToolTip(
                            "This issue cannot be automatically fixed because the material name is too different from any valid name"
                        )
                        action_layout.addWidget(not_fixable_label)

                action_layout.addStretch()
                self.tree.setItemWidget(child_item, 1, action_widget)

        # "Fix All" button
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)
        self.fix_all_checkbox = QCheckBox("Fix All Assets")
        bottom_layout.addWidget(self.fix_all_checkbox)
        fix_all_button = QPushButton("Apply Fixes")
        fix_all_button.clicked.connect(self.apply_fix_all)
        bottom_layout.addWidget(fix_all_button)
        layout.addWidget(bottom_widget)

    def select_object(self, obj):
        if obj is None:
            message_box("Error", "Cannot select: Object is None or missing")
            return

        if isinstance(obj, bpy.types.Material):
            if obj.name not in bpy.data.materials:
                message_box(
                    "Error",
                    f"Cannot select: Material '{obj.name if hasattr(obj, 'name') else 'Unknown'}' no longer exists",
                )
                return

            found = False
            for blender_obj in bpy.data.objects:
                if blender_obj.type == "MESH":
                    for slot in blender_obj.material_slots:
                        if slot.material == obj:
                            bpy.ops.object.select_all(action="DESELECT")
                            blender_obj.select_set(True)
                            bpy.context.view_layer.objects.active = blender_obj
                            found = True
                            break
                    if found:
                        break
            if not found:
                message_box("Info", f"Material '{obj.name}' exists but is not assigned to any objects")
            return

        if isinstance(obj, bpy.types.Object):
            if obj.name not in bpy.data.objects:
                message_box(
                    "Error",
                    f"Cannot select: Object '{obj.name if hasattr(obj, 'name') else 'Unknown'}' no longer exists",
                )
                return
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            return

        message_box("Error", f"Cannot select: Unknown object type {type(obj)}")

    def run_object_autofix(self, plugin, instance, obj, item, fixbtn) -> bool:
        if obj is None:
            item.setText(2, "❌ Cannot fix: Object is None or missing")
            return False

        if isinstance(obj, bpy.types.Material):
            self.log.info(f"run autofix: {obj.name}")
            if obj.name not in bpy.data.materials:
                item.setText(
                    2, f"❌ Cannot fix: Material '{obj.name if hasattr(obj, 'name') else 'Unknown'}' no longer exists"
                )
                return False

        if isinstance(obj, bpy.types.Object):
            if obj.name not in bpy.data.objects:
                item.setText(
                    2, f"❌ Cannot fix: Object '{obj.name if hasattr(obj, 'name') else 'Unknown'}' no longer exists"
                )
                return False

        try:
            fix_actions = [action for action in plugin.actions if hasattr(action, "process")]
            if not fix_actions:
                raise RuntimeError("No fix actions available.")

            new_context = ValidationContext()
            new_instance = ValidationInstance("Single Object", "mesh")
            new_instance.add(obj)

            new_instance.copy_data_from(instance)
            new_context.add(new_instance)

            selected_action = fix_actions[0]
            selected_action().process(new_context, plugin)
            item.setText(2, "✅ Fixed")
            fixbtn.setEnabled(False)

            for i, (p, objs, inst) in enumerate(self.parent_ui.problematic_assets):
                if p == plugin:
                    updated_objects = []
                    for o, msg in objs:
                        if o != obj:
                            updated_objects.append((o, msg))
                        elif "❌ Error:" not in msg and "⚠️ Warning:" in msg:
                            updated_objects.append((o, msg))

                    if updated_objects:
                        self.parent_ui.problematic_assets[i] = (p, updated_objects, inst)
                    else:
                        self.parent_ui.problematic_assets.pop(i)
                    break

            self.parent_ui.update_export_button()
            self.parent_ui.update_after_fixes()

            return True
        except Exception as e:
            self.log.error(f"❌ Fix failed: {str(e)}")
            item.setText(2, f"❌ Fix failed: {str(e)}")
            return False

    def run_plugin_autofix(self, plugin, instance, item):
        try:
            fix_actions = [action for action in plugin.actions if hasattr(action, "process")]
            if not fix_actions:
                raise RuntimeError("No fix actions available.")

            selected_action = fix_actions[0]
            fix_context = ValidationContext()
            fix_context.add(instance)
            selected_action().process(fix_context, plugin)

            if instance.data.get("fix_success", False):
                item.setText(2, "❌ Fix failed")
            else:
                item.setText(2, "✅ Fixed All Items")

            for i in range(item.childCount()):
                child = item.child(i)
                child.setText(2, "✅ Fixed")

                button_widget = self.tree.itemWidget(child, 1)
                if button_widget:
                    for j in range(button_widget.layout().count()):
                        widget = button_widget.layout().itemAt(j).widget()
                        if isinstance(widget, QPushButton) and widget.text() == "Autofix":
                            widget.setEnabled(False)

            for i, (p, objs, inst) in enumerate(self.parent_ui.problematic_assets):
                if p == plugin:
                    error_free_objects = [(obj, msg) for obj, msg in objs if "❌ Error:" not in msg]
                    if error_free_objects:
                        self.parent_ui.problematic_assets[i] = (p, error_free_objects, inst)
                    else:
                        self.parent_ui.problematic_assets.pop(i)
                    break

            self.parent_ui.update_export_button()
            self.parent_ui.update_after_fixes()

            return True
        except Exception as e:
            self.log.error(f"SANTA CLAUSE, {str(e)}")
            return False

    def apply_fix_all(self):
        if self.fix_all_checkbox.isChecked():
            fixed_any = False
            for i in range(self.tree.topLevelItemCount()):
                plugin_item = self.tree.topLevelItem(i)
                for plugin, _invalid_objects, instance in self.problems:
                    if getattr(plugin, "label") == plugin_item.text(0):
                        success = self.run_plugin_autofix(plugin, instance, plugin_item)
                        if success:
                            fixed_any = True

            self.parent_ui.update_export_button()

            if fixed_any:
                self.parent_ui.update_after_fixes()

            message_box("Fixes Applied", "All selected fixes have been applied.")

    def open_documentation(self):
        """Open the CORE_ArtistTools_README.md documentation to the Asset Management section"""
        try:
            bpy.ops.core.open_docs_with_anchor(anchor="core-tools:-asset-management")
        except Exception as e:
            self.log.error(f"Failed to open documentation: {e}")
            message_box("Error", f"Could not open documentation: {e}")

    def closeEvent(self, event):
        try:
            self.parent_ui.update_after_fixes()
            super().closeEvent(event)
        except Exception as e:
            self.log.error(f"Error updating parent UI on close: {str(e)}")
