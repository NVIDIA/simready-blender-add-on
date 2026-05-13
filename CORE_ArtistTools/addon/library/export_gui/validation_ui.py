# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import io
import json
import os
import re
import sys
from datetime import datetime

import bpy
from pxr import Sdf, Usd, UsdShade
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import (
    QGuiApplication,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from CORE_ArtistTools.addon.library.material_utils import create_usd_material
from CORE_ArtistTools.addon.utility.addon import get_prefs
from CORE_ArtistTools.addon.validators.logging_controller import logger
from CORE_ArtistTools.addon.validators.system_checks import system_type

from . import theme as _theme
from .asset_problems_ui import AssetProblemsUI
from .cip_problems_ui import CIPProblemAssetsUI
from .models import ValidationContext, ValidationInstance
from .theme import (
    BLEND_FILE_EXTENSION,
    BYPASS_VALIDATION_CHECKS,
    FONT_FAMILY,
    THEME,
    USE_MATERIAL_X,
)
from .utils import (
    determine_asset_type,
    message_box,
    orbitron_header_title_stylesheet_font_block,
    svg_config_icon_label,
    svg_config_qicon,
    window_icon_qicon,
)
from .widgets import BlenderEventListener, ValidationCard


class _StdoutTee:
    """Write to both the original stdout and an in-memory buffer simultaneously.

    Used during export to capture print() output so it can be surfaced in the
    failure message box 'Show Details...' section without losing console output.
    """

    def __init__(self, original, buffer: io.StringIO):
        self._orig = original
        self._buf = buffer

    def write(self, text: str):
        self._orig.write(text)
        self._buf.write(text)

    def flush(self):
        self._orig.flush()

    def fileno(self):
        return self._orig.fileno()


class ValidationUI(QDialog):
    def __init__(self):
        super().__init__()
        self.log = logger
        self.setWindowTitle("SimReady Autochecker")
        self.setWindowIcon(window_icon_qicon())
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.nv_core = ""

        # Stylesheet font-* overrides setFont(); QWidget rule below would else force FONT_FAMILY.
        _header_title_font = orbitron_header_title_stylesheet_font_block()

        self.setStyleSheet(f"""
            QDialog, QWidget {{
                background-color: {THEME['bg_base']};
                color: {THEME['text_primary']};
                font-family: {FONT_FAMILY};
            }}
            QLabel {{
                background-color: transparent;
            }}
            QPushButton {{
                background-color: transparent;
                color: {THEME['text_primary']};
                border: 2px solid {THEME['border_strong']};
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 12px;
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
            QPushButton#PrimaryAction {{
                background-color: {THEME['accent']};
                color: #000000;
                border: none;
                font-weight: bold;
            }}
            QPushButton#PrimaryAction:hover {{
                background-color: #8FD400;
            }}
            QPushButton#PrimaryAction:disabled {{
                background-color: #2A3A00;
                color: {THEME['text_dim']};
                border: none;
            }}
            QPushButton#SecondaryAction {{
                background-color: transparent;
                color: {THEME['text_primary']};
                border: 2px solid #444444;
            }}
            QPushButton#SecondaryAction:hover {{
                border-color: {THEME['accent']};
                color: {THEME['accent']};
            }}
            QPushButton#FilterTab {{
                background-color: transparent;
                color: {THEME['text_dim']};
                border: none;
                border-bottom: 2px solid transparent;
                border-radius: 0px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton#FilterTab:hover {{
                color: {THEME['text_secondary']};
            }}
            QPushButton#FilterTab[active="true"] {{
                color: {THEME['text_primary']};
                border-bottom: 2px solid {THEME['accent']};
            }}
            QLabel#SectionHeader {{
                color: {THEME['text_dim']};
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
            QLabel#HeaderTitle {{
                color: {THEME['text_primary']};
                {_header_title_font}
            }}
            QFrame#ConfigRow {{
                background-color: {THEME['bg_card']};
                border: 1px solid {THEME['border']};
                border-radius: 6px;
            }}
            QCheckBox {{
                color: {THEME['text_primary']};
                spacing: 8px;
            }}
            QCheckBox:hover {{
                color: {THEME['accent']};
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 2px solid #555555;
                border-radius: 3px;
                background-color: {THEME['bg_mid']};
            }}
            QCheckBox::indicator:hover {{
                border-color: {THEME['accent']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {THEME['accent']};
                border-color: {THEME['accent']};
            }}
            QLineEdit {{
                background-color: {THEME['bg_mid']};
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
                color: {THEME['text_primary']};
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {THEME['accent']};
            }}
            QScrollArea {{
                background-color: {THEME['bg_base']};
                border: none;
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
            QMessageBox {{
                background-color: {THEME['bg_mid']};
                color: {THEME['text_primary']};
            }}
        """)

        self.problematic_assets = []
        self.export_button = None
        self.validation_label = None
        self.asset_name = None
        self.asset_type = None
        self._cards: list = []
        self._cards_by_label: dict = {}
        self.review_button = None
        self._num_cols: int = 3
        self._CARD_COL_MIN_WIDTH: int = 200

        self.setupUI()
        self.setDynamicSize()
        self.setScreenLeft()
        self.get_prefs()
        self.event_listener = BlenderEventListener()
        self.event_listener.assetOpened.connect(self.on_asset_opened)

    #########################
    ### SUPPORT FUNCTIONS ###
    #########################

    def setDynamicSize(self):
        """Dynamically resize window based on available screen space"""
        screen = QGuiApplication.primaryScreen()
        available_geometry = screen.availableGeometry()

        target_width = min(int(available_geometry.width() * 0.45), 1000)
        target_height = min(int(available_geometry.height() * 0.85), 1000)

        target_width = max(target_width, 600)
        target_height = max(target_height, 400)

        self.resize(target_width, target_height)

    def get_prefs(self):
        prefs = get_prefs()
        if not prefs:
            addon_name = __name__.partition(".")[0]
            prefs = bpy.context.preferences.addons[addon_name].preferences

        if prefs and hasattr(prefs, "settings") and hasattr(prefs.settings, "ds_source_folder"):
            self.nv_core = prefs.settings.ds_nv_core
            self.project_root = prefs.settings.ds_project_root

        else:
            self.nv_core = ""
            self.project_root = ""
            # TODO: store all materials in back library core tools
            raise ValueError("NV_CORE is not set!!!")

    def setScreenLeft(self):
        """Set the window to the left side of the screen"""
        screen = QGuiApplication.primaryScreen()
        available_geometry = screen.availableGeometry()

        padding = 10

        x = available_geometry.x() + padding

        window_height = self.height()

        ideal_y = available_geometry.y() + (available_geometry.height() - window_height) // 2 - 50

        min_y = available_geometry.y() + padding
        max_y = available_geometry.y() + available_geometry.height() - window_height - padding

        y = max(min_y, min(ideal_y, max_y))

        self.move(int(x), int(y))

    def on_asset_opened(self, _asset_path):
        """Update UI when a new asset is opened."""
        self.problematic_assets = []
        self._clear_cards()

        asset_type = self.get_asset_type()
        asset_name = self.get_asset_name()
        self.asset_type = asset_type
        self.asset_name = asset_name

        if self.validation_label:
            self.validation_label.setText(f'VALIDATING: <span style="color: {THEME["accent"]};">{asset_name}</span>')
        if hasattr(self, "type_label"):
            self.type_label.setText(
                f'TYPE: <span style="color: {THEME["text_secondary"]};">{asset_type.upper()}</span>'
            )

        if hasattr(self, "use_material_x_checkbox"):
            try:
                self.use_material_x_checkbox.setChecked(bpy.context.scene.export_props.use_materialx)
            except (AttributeError, KeyError):
                self.use_material_x_checkbox.setChecked(False)

        if self.export_button:
            if self.bypass_checkbox.isChecked():
                self.export_button.setEnabled(True)
            else:
                self.export_button.setEnabled(False)
            self.export_button.setToolTip(f"Enable by resolving all errors or checking {BYPASS_VALIDATION_CHECKS}")

    def setupUI(self):
        self.asset_type: str = self.get_asset_type()
        self.asset_name: str = self.get_asset_name()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # --- Header: "SRS AUTOCHECKER" ---
        header_widget = QWidget()
        header_widget.setStyleSheet(f"background-color: {THEME['bg_base']};")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 8)

        title_label = QLabel("SimReady AutoChecker")
        title_label.setObjectName("HeaderTitle")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addWidget(header_widget)

        # --- Accent line ---
        accent_line = QFrame()
        accent_line.setFrameShape(QFrame.HLine)
        accent_line.setStyleSheet(f"background-color: {THEME['accent']}; border: none;")
        accent_line.setFixedHeight(2)
        layout.addWidget(accent_line)

        # --- Asset info ---
        self.validation_label = QLabel(f'VALIDATING: <span style="color: {THEME["accent"]};">{self.asset_name}</span>')
        self.validation_label.setTextFormat(Qt.TextFormat.RichText)
        self.validation_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #EDEDED; padding-top: 4px;")
        layout.addWidget(self.validation_label)

        type_label_text = f'TYPE: <span style="color: {THEME["text_secondary"]};">{self.asset_type.upper()}</span>'
        self.type_label = QLabel(type_label_text)
        self.type_label.setTextFormat(Qt.TextFormat.RichText)
        self.type_label.setStyleSheet("font-size: 11px; color: #AAAAAA; padding-bottom: 4px;")
        layout.addWidget(self.type_label)

        # --- Validation Configuration section ---
        section_header = QLabel("VALIDATION CONFIGURATION")
        section_header.setObjectName("SectionHeader")
        layout.addWidget(section_header)

        # Config row: Bypass Validation Checks
        bypass_row = QFrame()
        bypass_row.setObjectName("ConfigRow")
        bypass_row_layout = QHBoxLayout(bypass_row)
        bypass_row_layout.setContentsMargins(12, 8, 12, 8)
        bypass_icon = svg_config_icon_label(
            "config_bypass.svg",
            THEME["text_primary"],
            fallback_text="⚡",
        )
        bypass_text_col = QVBoxLayout()
        bypass_text_col.setSpacing(1)
        bypass_main_lbl = QLabel(BYPASS_VALIDATION_CHECKS)
        bypass_main_lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {THEME['text_primary']};")
        bypass_sub_lbl = QLabel("Force export regardless of state")
        bypass_sub_lbl.setStyleSheet(f"font-size: 10px; color: {THEME['text_dim']};")
        bypass_text_col.addWidget(bypass_main_lbl)
        bypass_text_col.addWidget(bypass_sub_lbl)
        self.bypass_checkbox = QCheckBox()
        self.bypass_checkbox.stateChanged.connect(self.on_bypass_changed)
        bypass_row_layout.addWidget(bypass_icon)
        bypass_row_layout.addSpacing(8)
        bypass_row_layout.addLayout(bypass_text_col)
        bypass_row_layout.addStretch()
        bypass_row_layout.addWidget(self.bypass_checkbox)
        layout.addWidget(bypass_row)

        # Config row: Use Material X
        matx_row = QFrame()
        matx_row.setObjectName("ConfigRow")
        matx_row_layout = QHBoxLayout(matx_row)
        matx_row_layout.setContentsMargins(12, 8, 12, 8)
        matx_icon = svg_config_icon_label(
            "config_materialx.svg",
            THEME["text_primary"],
            fallback_text="◈",
        )
        matx_text_col = QVBoxLayout()
        matx_text_col.setSpacing(1)
        matx_main_lbl = QLabel(USE_MATERIAL_X)
        matx_main_lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {THEME['text_primary']};")
        matx_sub_lbl = QLabel("Convert textures to .mtlx standard")
        matx_sub_lbl.setStyleSheet(f"font-size: 10px; color: {THEME['text_dim']};")
        matx_text_col.addWidget(matx_main_lbl)
        matx_text_col.addWidget(matx_sub_lbl)
        self.use_material_x_checkbox = QCheckBox()
        self.use_material_x_checkbox.stateChanged.connect(self.on_use_material_x_changed)
        try:
            self.use_material_x_checkbox.setChecked(bpy.context.scene.export_props.use_materialx)
        except (AttributeError, KeyError):
            pass
        matx_row_layout.addWidget(matx_icon)
        matx_row_layout.addSpacing(8)
        matx_row_layout.addLayout(matx_text_col)
        matx_row_layout.addStretch()
        matx_row_layout.addWidget(self.use_material_x_checkbox)
        layout.addWidget(matx_row)

        # --- Variant row ---
        variant_row = QWidget()
        variant_row.setStyleSheet(f"background-color: {THEME['bg_mid']}; border-radius: 4px;")
        variant_layout = QHBoxLayout(variant_row)
        variant_layout.setContentsMargins(12, 6, 12, 6)
        variant_lbl = QLabel("Asset Variant:")
        variant_lbl.setStyleSheet(f"font-size: 12px; color: {THEME['text_primary']};")
        try:
            initial_variant = bpy.context.scene.asset_variant_props.variant_number
            if not initial_variant or len(initial_variant) != 2 or not initial_variant.isdigit():
                initial_variant = "01"
        except (AttributeError, KeyError):
            initial_variant = "01"
        self.variant_input = QLineEdit(initial_variant)
        self.variant_input.setMaxLength(2)
        self.variant_input.setFixedWidth(50)
        self.variant_input.setToolTip("Enter a 2-digit variant number (e.g., 01, 02, 10)")
        self.variant_input.textChanged.connect(self.validate_variant_input)
        self.variant_input.textChanged.connect(self.sync_variant_to_blender)
        variant_info = QLabel("(2-digit format: 01–99)")
        variant_info.setStyleSheet(f"font-size: 10px; color: {THEME['text_dim']};")
        variant_layout.addWidget(variant_lbl)
        variant_layout.addWidget(self.variant_input)
        variant_layout.addWidget(variant_info)
        variant_layout.addStretch()
        layout.addWidget(variant_row)

        # --- Action buttons row ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        _action_icon_fill = THEME["text_primary"]
        _action_icon_size = QSize(16, 16)

        self.run_button = QPushButton(" VALIDATE")
        self.run_button.setObjectName("SecondaryAction")
        self.run_button.setIcon(svg_config_qicon("config_checks.svg", _action_icon_fill))
        self.run_button.setIconSize(_action_icon_size)
        self.run_button.clicked.connect(self.run_validation)

        self.export_button = QPushButton(" EXPORT SIMREADY")
        self.export_button.setObjectName("PrimaryAction")
        self.export_button.setIcon(svg_config_qicon("config_export.svg", _action_icon_fill))
        self.export_button.setIconSize(_action_icon_size)
        self.export_button.setEnabled(False)
        self.export_button.setToolTip(f"Enable by resolving all errors or checking {BYPASS_VALIDATION_CHECKS}")
        btn_row.addWidget(self.run_button)
        btn_row.addWidget(self.export_button)
        layout.addLayout(btn_row)

        # --- Filter tab row ---
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 4, 0, 0)
        filter_row.setSpacing(0)

        self._filter_btn_all = QPushButton("ALL")
        self._filter_btn_all.setObjectName("FilterTab")
        self._filter_btn_all.setProperty("active", "true")
        self._filter_btn_all.clicked.connect(lambda: self._apply_filter("all"))

        self._filter_btn_passed = QPushButton("PASSED  0")
        self._filter_btn_passed.setObjectName("FilterTab")
        self._filter_btn_passed.clicked.connect(lambda: self._apply_filter("passed"))

        self._filter_btn_warnings = QPushButton("WARNINGS  0")
        self._filter_btn_warnings.setObjectName("FilterTab")
        self._filter_btn_warnings.clicked.connect(lambda: self._apply_filter("warning"))

        self._filter_btn_failed = QPushButton("FAILED  0")
        self._filter_btn_failed.setObjectName("FilterTab")
        self._filter_btn_failed.clicked.connect(lambda: self._apply_filter("failed"))

        for btn in (self._filter_btn_all, self._filter_btn_passed, self._filter_btn_warnings, self._filter_btn_failed):
            filter_row.addWidget(btn)
        filter_row.addStretch()

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet(f"background-color: {THEME['border']}; border: none;")
        separator.setFixedHeight(1)

        layout.addLayout(filter_row)
        layout.addWidget(separator)

        # --- Card scroll area ---
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._card_container = QWidget()
        self._card_container.setStyleSheet(f"background-color: {THEME['bg_base']};")
        self._card_grid = QGridLayout(self._card_container)
        self._card_grid.setContentsMargins(0, 8, 0, 8)
        self._card_grid.setSpacing(8)
        self._scroll_area.setWidget(self._card_container)
        layout.addWidget(self._scroll_area, stretch=1)

        self.setMinimumWidth(700)
        self.setMinimumHeight(500)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def get_asset_type(self) -> str:
        return str(determine_asset_type(bpy.data.filepath))

    def get_asset_name(self) -> str:
        asset_path = str(bpy.data.filepath)
        if system_type == "Windows":
            return asset_path.split("\\")[-1].replace(BLEND_FILE_EXTENSION, "") if asset_path else "Untitled"
        return asset_path.split("/")[-1].replace(BLEND_FILE_EXTENSION, "") if asset_path else "Untitled"

    def validate_variant_input(self, text):
        """Validate the variant input to ensure it's a 2-digit number"""
        if text == "":
            return

        if not text.isdigit():
            self.variant_input.setText("".join(filter(str.isdigit, text)))
            return

        if len(text) == 1:
            pass
        elif len(text) == 2:
            pass
        else:
            self.variant_input.setText(text[:2])

    def get_variant_number(self) -> str:
        """Get the variant number from input, ensuring it's 2 digits"""
        variant = self.variant_input.text()
        if not variant or not variant.isdigit():
            return "01"

        if len(variant) == 1:
            return f"0{variant}"
        elif len(variant) == 2:
            return variant
        else:
            return "01"

    def sync_variant_to_blender(self, text):
        """Sync the variant number to the Blender property whenever it changes"""
        if text and text.isdigit() and len(text) == 2:
            try:
                bpy.context.scene.asset_variant_props.variant_number = text
            except (AttributeError, KeyError) as e:
                self.log.warning(f"Could not sync variant to Blender property: {e}")

    def apply_variant_to_filename(self, filename: str, variant_number: str) -> str:
        """
        Apply variant number to filename, replacing existing variant suffix if present.

        Looks for a pattern of _XX at the end of the filename (where XX is 2 digits)
        and replaces it with the new variant number. If no variant suffix exists,
        appends the variant number.

        Examples:
            "sm_asset_01" + "02" -> "sm_asset_02"
            "sm_asset_v01_05" + "03" -> "sm_asset_v01_03"
            "sm_asset" + "01" -> "sm_asset_01"
        """
        pattern = r"_(\d{2})$"
        match = re.search(pattern, filename)

        if match:
            existing_variant = match.group(1)
            if existing_variant != variant_number:
                return re.sub(pattern, f"_{variant_number}", filename)
            else:
                return filename
        else:
            return f"{filename}_{variant_number}"

    def discover_validators(self):
        """Discover and import validator plugins from the validators directory"""
        validators = []

        try:
            from CORE_ArtistTools.addon.validators import (
                geo_checks,
                hiearchy_checks,
                mat_checks,
            )

            for module in [mat_checks, geo_checks, hiearchy_checks]:
                for name in dir(module):
                    obj = getattr(module, name)
                    if (
                        isinstance(obj, type)
                        and hasattr(obj, "label")
                        and hasattr(obj, "process")
                        and hasattr(obj, "asset_types")
                        and name not in "InstancePlugin"
                    ):
                        if "all" in obj.asset_types or self.asset_type in obj.asset_types:
                            validators.append(obj)

        except ImportError as e:
            self.log.error(f"Failed to import validators: {e}")

        return validators

    def update_export_button(self):
        if hasattr(self, "bypass_checkbox") and self.bypass_checkbox.isChecked():
            self.export_button.setEnabled(True)
            self.export_button.clicked.connect(self.export_asset)
            return

        has_errors = any(card.getState() in ("failed", "critical") for card in self._cards)

        self.export_button.setEnabled(not has_errors)
        if not has_errors:
            self.export_button.clicked.connect(self.export_asset)

    def update_after_fixes(self):
        """Update card states and export button after AssetProblemsUI applies fixes."""
        if not self.problematic_assets:
            message_box("All Issues Fixed", "All validation issues have been fixed. You can now export the asset.")
        self.update_validation_display()

    def update_validation_display(self):
        """Refresh card states from the current problematic_assets list."""
        for card in self._cards:
            plugin_label = card._check_label
            plugin_still_has_problems = False
            for plugin, objects, instance in self.problematic_assets:
                if getattr(plugin, "label", None) == plugin_label:
                    plugin_still_has_problems = True
                    error_count = sum(1 for _, msg in objects if "❌ Error:" in msg)
                    warning_count = sum(1 for _, msg in objects if "⚠️ Warning:" in msg)
                    if error_count > 0:
                        card.setState("failed", f"{error_count} errors, {warning_count} warnings")
                    elif warning_count > 0:
                        card.setState("warning", f"{warning_count} warnings")
                    break
            if not plugin_still_has_problems and card.getState() != "passed":
                card.setState("passed", "All checks passed")
        self._update_filter_counts()
        self.update_export_button()

    def export_asset(self):

        # DEBUG:
        print("exporting asset")

        if hasattr(self, "_export_in_progress") and self._export_in_progress:
            self.log.warning("Export already in progress, please wait...")
            return

        self._export_in_progress = True

        asset_type = self.get_asset_type()
        blender_file_path = bpy.data.filepath
        file_name_raw, _file_ext = os.path.splitext(os.path.basename(blender_file_path))

        # TODO: Today art team uses this _flat convention to indicate flattened assets.
        if file_name_raw.lower().endswith("_flat"):
            file_name = file_name_raw[:-5]
        else:
            file_name = file_name_raw

        blender_folder = os.path.dirname(blender_file_path)

        # Up 4 levels from blender folder to get to the root asset folder
        # blender folder -> model -> working -> dcc_source -> asset folder
        ascend_folders = 4

        expected_asset_dir = os.path.abspath(os.path.join(blender_folder, *[".."] * ascend_folders))
        usd_dir = os.path.abspath(os.path.join(expected_asset_dir, "simready_usd"))

        if not file_name.lower().startswith("sm_"):
            file_name_with_prefix = f"sm_{file_name}"
        else:
            file_name_with_prefix = file_name

        variant_number = self.get_variant_number()
        file_name_with_variant = self.apply_variant_to_filename(file_name_with_prefix, variant_number)

        usd_file_path = os.path.join(usd_dir, f"{file_name_with_variant}.usd")
        usd_file_name, _usd_ext = os.path.splitext(os.path.basename(usd_file_path))
        glb_file_name = f"{usd_file_name}.glb"
        glb_path = f"{usd_dir}/web/{glb_file_name}"
        meta_file_path = f"{usd_dir}/{usd_file_name}.json"

        os.makedirs(usd_dir, exist_ok=True)

        glb_export_params = {
            "filepath": glb_path,
            "export_format": "GLB",
            "use_selection": True,
            "export_apply": True,
            "export_materials": "EXPORT",
            "export_cameras": False,
            "export_lights": False,
        }

        if bpy.app.version < (4, 2, 0):

            export_params = {
                "filepath": usd_file_path,
                "start": 0,
                "end": 0,
                "frame_step": 1,
                "selected_objects_only": False,
                "visible_objects_only": True,
                "convert_orientation": False,
                "usdz_is_arkit": False,
                "convert_to_cm": False,
                "relative_paths": True,
                "export_as_overs": False,
                "merge_transform_and_shape": False,
                "xform_op_mode": "SRT",
                "export_transforms": True,
                "export_meshes": True,
                "export_materials": True,
                "export_lights": False,
                "export_cameras": False,
                "export_curves": False,
                "apply_subdiv": True,
                "export_vertex_colors": True,
                "export_vertex_groups": False,
                "export_normals": True,
                "export_uvmaps": True,
                "convert_uv_to_st": True,
                "triangulate_meshes": False,
                "quad_method": "SHORTEST_DIAGONAL",
                "ngon_method": "BEAUTY",
                "generate_preview_surface": True,
                "generate_cycles_shaders": False,
                "generate_mdl": True,
                "export_textures": True,
                "overwrite_textures": True,
                "light_intensity_scale": 1.0,
                "convert_light_to_nits": True,
                "scale_light_radius": True,
                "convert_world_material": True,  # TODO: might need to throw away world materials on export
                "export_armatures": False,
                "fix_skel_root": True,
                "export_blendshapes": False,
                "export_animation": False,
                "export_particles": True,
                "export_hair": True,
                "export_child_particles": False,
                "use_instancing": False,
            }
        elif bpy.app.version >= (4, 2, 0):
            export_params = {
                "filepath": usd_file_path,
                "selected_objects_only": False,
                "export_animation": False,
                "export_custom_properties": True,
                "custom_properties_namespace": "",
                "author_blender_name": False,
                "relative_paths": True,
                "convert_orientation": False,
                "evaluation_mode": "RENDER",
                "xform_op_mode": "TRS",
                "export_meshes": True,
                "export_materials": True,
                "export_lights": False,
                "export_cameras": False,
                "export_curves": True,
                "export_points": True,
                "export_volumes": True,
                "export_hair": True,
                "export_subdivision": "BEST_MATCH",
                "export_normals": True,
                "export_uvmaps": True,
                "rename_uvmaps": True,
                "triangulate_meshes": False,
                "quad_method": "SHORTEST_DIAGONAL",
                "ngon_method": "BEAUTY",
                "generate_preview_surface": True,
                "generate_materialx_network": self.use_material_x_checkbox.isChecked(),
                "convert_world_material": False,
                "export_textures_mode": "NEW",
                "overwrite_textures": True,
                "usdz_downscale_size": "KEEP",
                "export_armatures": False,
                "export_shapekeys": False,
                "only_deform_bones": False,
                "use_instancing": False,
            }

        # Add asset-specific parameters
        if asset_type == "vehicle":
            self.log.info("vehicle export started")
            export_params.update(
                {
                    "root_prim_path": "/root",
                }
            )
        elif asset_type == "prop":
            self.log.info("prop export started")
            export_params.update(
                {
                    "root_prim_path": "/RootNode",
                }
            )
        else:
            self.log.error(f"Unknown asset type: {asset_type}")
            self._export_in_progress = False
            return

        def has_materials_to_convert() -> bool:
            """Check if there are any active materials with SimPBR or SimPBR_Translucent nodes."""
            for material in bpy.data.materials:
                if material.users == 0:
                    continue
                if not material.use_nodes or not material.node_tree:
                    continue
                for node in material.node_tree.nodes:
                    if node.label in ["SimPBR", "SimPBR_Translucent"]:
                        self.log.info(f"Found material '{material.name}' with {node.label} node")
                        return True
            return False

        def convert_materials(usd_file_path, asset_type):
            # Re-open stage and convert materials to SimPBR or SimPBR_Translucent
            stage_export = Usd.Stage.Open(usd_file_path)

            default_prim = stage_export.GetDefaultPrim()
            if default_prim is None:
                self.log.error(f"Failed to get default prim at {usd_file_path}")
                return

            if asset_type == "vehicle":
                material_path = f"{default_prim.GetPath()}/materials"
            elif asset_type == "prop":
                material_path = f"{default_prim.GetPath()}/Looks"
            else:
                self.log.error(f"Unknown asset type: {asset_type}")
                return

            material_prims = [prim for prim in stage_export.Traverse() if prim.IsA(UsdShade.Material)]

            def get_material_type(material_name) -> str:
                material = bpy.data.materials.get(material_name)

                for node in material.node_tree.nodes:
                    if node.label == "SimPBR":
                        return "SimPBR"
                    elif node.label == "SimPBR_Translucent":
                        return "SimPBR_Translucent"

            for material in material_prims:
                material_name = material.GetName()
                material_path = material.GetPath()
                material_type = get_material_type(material_name)

                for child in material.GetChildren():
                    stage_export.RemovePrim(child.GetPath())
                stage_export.RemovePrim(material_path)

                sanitize_nv_core = self.nv_core.replace("\\", "/")

                create_usd_material(
                    stage=stage_export,
                    material_name=material_name,
                    mdl_path=f"{sanitize_nv_core}/materials/{material_type}.mdl",
                    root_path=default_prim.GetPath(),
                    material_type=material_type,
                    export_file_path=usd_file_path,
                )

                stage_export.Save()

                self.log.info(f"Created USD material for {material_name} at {material_path}")

        def add_custom_metadata():
            """Create custom metadata to be merged with existing USD metadata"""
            try:
                profile = "NONE"
                if hasattr(bpy.context.scene, "asset_profiles"):
                    selected_profile = bpy.context.scene.asset_profiles.selected_profile
                    if selected_profile != "NONE":
                        profile_mapping = {
                            "NEUTRAL": "Prop-Robotics-Neutral",
                        }
                        profile = profile_mapping.get(selected_profile, selected_profile)
                        self.log.info(f"Using profile from Blender properties: {profile}")
                    else:
                        self.log.warning("No profile selected in Blender properties")
                else:
                    self.log.warning("Asset profiles property not found in scene")

                normalized_blender_path = blender_file_path.replace("\\", "/") if blender_file_path else ""
                normalized_usd_path = usd_file_path.replace("\\", "/") if usd_file_path else ""
                normalized_project_root = self.project_root.replace("\\", "/") if self.project_root else ""
                normalized_asset_dir = (
                    expected_asset_dir.replace("\\", "/").replace(normalized_project_root, "")[1:]
                    if expected_asset_dir
                    else ""
                )

                relative_blender_path = ""
                if normalized_blender_path and normalized_usd_path:
                    try:
                        usd_dir = os.path.dirname(normalized_usd_path)
                        relative_blender_path = os.path.relpath(normalized_blender_path, usd_dir)
                        relative_blender_path = relative_blender_path.replace("\\", "/")
                    except ValueError as e:
                        self.log.warning(f"Could not calculate relative path: {str(e)}")
                        relative_blender_path = normalized_blender_path

                if not self.project_root:
                    raise ValueError("Project root is not set")

                anchored_relative_path = f"@{relative_blender_path}@" if relative_blender_path else ""

                custom_metadata = {
                    "asset_type": asset_type,
                    "asset_name": file_name,
                    "source_file": anchored_relative_path,
                    "asset_dir": normalized_asset_dir,
                    "profile": profile,
                    "usd_date_generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "used_dsrs_exporter": True,
                }
                return custom_metadata
            except Exception as e:
                self.log.error(f"Failed to create custom metadata: {str(e)}")
                raise Exception(f"Failed to create custom metadata: {str(e)}")

        if hasattr(self, "export_button"):
            self.export_button.setEnabled(False)

        _export_retry_count = [0]
        _max_export_retries = 30
        _export_retry_interval = 0.5

        # Capture stdout/print output produced during export so it can be shown
        # in failure message boxes via the "Show Details..." button.
        _capture_buf = io.StringIO()

        def _is_context_restricted_error(exc):
            msg = str(exc).lower()
            return (
                "drawing/rendering" in msg
                or "writing to id classes" in msg
                or "not allowed" in msg
                or "cannot modify blend data" in msg
            )

        def do_export():
            # Write to the module-level flag via the theme module (module-scoped state,
            # not function-scoped global) so ot_simready_usdhook can read it via getattr().
            _theme._active_usd_hook = "SIMREADY_CORE"
            self.log.debug("Set active_usd_hook = 'SIMREADY_CORE'")

            # Reset capture buffer and redirect stdout through the tee so that all
            # print() calls during this export run are captured for the Details pane.
            _capture_buf.truncate(0)
            _capture_buf.seek(0)
            _orig_stdout = sys.stdout
            sys.stdout = _StdoutTee(_orig_stdout, _capture_buf)

            try:
                _run_export()
            except Exception as e:
                if _is_context_restricted_error(e) and _export_retry_count[0] < _max_export_retries:
                    _export_retry_count[0] += 1
                    self.log.warning(
                        f"Export deferred (context restricted), retry {_export_retry_count[0]}/{_max_export_retries}: {e}"
                    )
                    bpy.app.timers.register(do_export, first_interval=_export_retry_interval)
                    return
                if _is_context_restricted_error(e):
                    _theme._active_usd_hook = ""

                    def _export_once_after_depsgraph():
                        try:
                            bpy.app.handlers.depsgraph_update_post.remove(_export_once_after_depsgraph)
                        except ValueError:
                            pass
                        _theme._active_usd_hook = "SIMREADY_CORE"
                        try:
                            _run_export()
                        except Exception as err:
                            self.log.error(f"Export failed (depsgraph fallback): {err}")
                            message_box(
                                title="Export Failed",
                                message=f"Export could not run (Blender was busy). Try closing the validation window and exporting again, or restart Blender.\n\n{err}",
                                details=_capture_buf.getvalue(),
                            )
                        finally:
                            _theme._active_usd_hook = ""
                            self._export_in_progress = False
                            if hasattr(self, "export_button"):
                                self.export_button.setEnabled(True)

                    if _export_once_after_depsgraph not in bpy.app.handlers.depsgraph_update_post:
                        bpy.app.handlers.depsgraph_update_post.append(_export_once_after_depsgraph)
                        self.log.info("Export deferred to depsgraph callback (one more try)")
                        return None
                    self.log.error(f"Export failed after {_max_export_retries} retries (context restricted)")
                    message_box(
                        title="Export Failed",
                        message="Export could not run (Blender was busy). Try closing the validation window and exporting again, or restart Blender.",
                        details=_capture_buf.getvalue(),
                    )
                    self._export_in_progress = False
                    if hasattr(self, "export_button"):
                        self.export_button.setEnabled(True)
                    return None
                raise
            finally:
                sys.stdout = _orig_stdout
                _theme._active_usd_hook = ""

        def _run_export():
            try:
                export_col = bpy.data.collections.get("Export")

                def safe_deselect_all():
                    try:
                        for obj in bpy.context.scene.objects:
                            obj.select_set(False)
                        return True
                    except Exception as e:
                        self.log.error(f"Failed to deselect objects manually: {e}")
                        return False

                if not safe_deselect_all():
                    self.log.error("Failed to deselect objects, aborting export")
                    return

                if export_col:
                    export_params.update({"selected_objects_only": True})
                    for obj in export_col.all_objects:
                        obj.select_set(True)
                else:
                    self.log.error("No Export collection found")
                    message_box(
                        title="Export Failed",
                        message="Failed to export USD file. Error: No Export collection found!",
                        details=_capture_buf.getvalue(),
                    )
                    safe_deselect_all()
                    return

                if bpy.context.mode != "OBJECT":
                    self.log.info(f"Switching from {bpy.context.mode} mode to OBJECT mode for export")
                    try:
                        bpy.ops.object.mode_set(mode="OBJECT")
                    except Exception as e:
                        self.log.warning(f"Failed to switch to object mode: {e}")

                normalized_usd_path = usd_file_path.replace("\\", "/")
                try:
                    existing_layer = Sdf.Layer.Find(normalized_usd_path)
                    if existing_layer is not None:
                        self.log.info(f"Closing existing USD layer at {normalized_usd_path} before export")
                        del existing_layer
                        import gc

                        gc.collect()
                except Exception as e:
                    self.log.debug(f"Could not check/close existing layer: {e}")

                area_types_to_try = ["VIEW_3D", "PROPERTIES", "OUTLINER", "INFO"]
                export_successful = False

                if bpy.context.area is not None:
                    try:
                        bpy.ops.wm.usd_export(**export_params)
                        export_successful = True
                        self.log.info(f"{asset_type} exported to {usd_file_path}")
                    except Exception as e:
                        if _is_context_restricted_error(e):
                            raise
                        self.log.warning(f"Export failed with current context: {e}")

                if not export_successful:
                    for window in bpy.context.window_manager.windows:
                        for area in window.screen.areas:
                            if area.type in area_types_to_try:
                                try:
                                    override = {
                                        "window": window,
                                        "screen": window.screen,
                                        "area": area,
                                        "region": area.regions[-1] if area.regions else None,
                                        "scene": bpy.context.scene,
                                        "space_data": area.spaces[0] if area.spaces else None,
                                    }

                                    override = {k: v for k, v in override.items() if v is not None}

                                    with bpy.context.temp_override(**override):
                                        bpy.ops.wm.usd_export(**export_params)
                                        export_successful = True
                                        self.log.info(
                                            f"{asset_type} exported to {usd_file_path} using {area.type} context"
                                        )
                                        break
                                except Exception as e:
                                    if _is_context_restricted_error(e):
                                        raise
                                    self.log.warning(f"Export failed with {area.type} context: {e}")
                                    continue
                        if export_successful:
                            break

                if not export_successful:
                    try:
                        minimal_override = {
                            "scene": bpy.context.scene,
                            "window": (
                                bpy.context.window_manager.windows[0] if bpy.context.window_manager.windows else None
                            ),
                        }
                        minimal_override = {k: v for k, v in minimal_override.items() if v is not None}

                        with bpy.context.temp_override(**minimal_override):
                            bpy.ops.wm.usd_export(**export_params)
                            export_successful = True
                            self.log.info(f"{asset_type} exported to {usd_file_path} using minimal context")
                    except Exception as e:
                        if _is_context_restricted_error(e):
                            raise
                        self.log.error(f"All export attempts failed: {e}")
                        message_box(
                            title="Export Failed",
                            message=f"Failed to export USD file. Error: {e}\n\nPlease try switching to a different view mode or restart Blender.",
                            details=_capture_buf.getvalue(),
                        )
                        return

                if export_successful:
                    self.log.info(f"{asset_type} exported to {usd_file_path}")

                    layer_data = Sdf.Layer.FindOrOpen(usd_file_path)
                    if layer_data is None:
                        self.log.error(f"Failed to open USD layer at {usd_file_path}")
                        return

                    self.log.info(f"Adding custom metadata to {usd_file_path}")
                    existing_metadata = layer_data.customLayerData or {}
                    new_metadata = add_custom_metadata()
                    existing_metadata.update(new_metadata)
                    layer_data.customLayerData = existing_metadata

                    # Set default prim kind to 'component'
                    default_prim_name = layer_data.defaultPrim
                    default_prim_spec = layer_data.GetPrimAtPath(f"/{default_prim_name}")
                    if default_prim_spec:
                        default_prim_spec.SetInfo("kind", "component")

                    layer_data.Save()

                    self.log.info(f"Adding metadata sidecar {meta_file_path}")

                    with open(meta_file_path, "w") as f:
                        json.dump(layer_data.customLayerData, f, indent=4)

                    # Re-open stage and convert materials to SimPBR or SimPBR_Translucent
                    # if self.nv_core != "":
                    #     if has_materials_to_convert():
                    #         convert_materials(usd_file_path, asset_type)
                    #         self.log.info(f"Materials converted to SimPBR or SimPBR_Translucent at {usd_file_path}")
                    #     else:
                    #         self.log.info("No materials with SimPBR or SimPBR_Translucent nodes found, skipping conversion")

                    message_box(
                        title="Export Successful",
                        message=f"Export completed successfully!\n\nFile saved to:\n{usd_file_path}",
                    )

            except Exception as e:
                if _is_context_restricted_error(e):
                    raise
                error_msg = f"Export failed: {str(e)}"
                self.log.error(error_msg)
                message_box(
                    title="Export Failed", message=f"Export failed!\n\n{error_msg}", details=_capture_buf.getvalue()
                )
                return

            # GLB export
            try:
                export_col = bpy.data.collections.get("Export")
                if export_col:
                    for obj in export_col.all_objects:
                        obj.select_set(True)
                    bpy.ops.export_scene.gltf(**glb_export_params)
                    self.log.info(f"GLB exported to {glb_path}")
                else:
                    self.log.error("GLB export failed: No Export collection found!")
                    message_box(
                        title="Export Failed",
                        message="Failed to export GLTF file. Error: No Export collection found!",
                        details=_capture_buf.getvalue(),
                    )
            except Exception as e:
                if _is_context_restricted_error(e) and _export_retry_count[0] < _max_export_retries:
                    _export_retry_count[0] += 1
                    self.log.warning(
                        f"GLB export deferred (context restricted), retry {_export_retry_count[0]}/{_max_export_retries}: {e}"
                    )
                    bpy.app.timers.register(do_export, first_interval=_export_retry_interval)
                    return
                self.log.error(f"GLB export failed: {str(e)}")
                message_box(
                    title="Export Failed",
                    message=f"Failed to export GLTF file. Error: GLB export failed: {str(e)}",
                    details=_capture_buf.getvalue(),
                )
            finally:
                _export_retry_count[0] = 0
                self._export_in_progress = False
                if hasattr(self, "export_button"):
                    self.export_button.setEnabled(True)

        bpy.app.timers.register(do_export, first_interval=_export_retry_interval)

    def open_problem_assets_ui(self):
        dialog = AssetProblemsUI(self.problematic_assets, parent_ui=self)
        dialog.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, "_scroll_area") or not self._cards:
            return
        available_width = self._scroll_area.viewport().width()
        spacing = self._card_grid.spacing()
        new_cols = max(1, (available_width + spacing) // (self._CARD_COL_MIN_WIDTH + spacing))
        new_cols = min(new_cols, 3)
        if new_cols != self._num_cols:
            self._num_cols = new_cols
            self._rebuild_card_grid()

    ############################
    ### VALIDATION FUNCTIONS ###
    ############################

    def run_validation(self):
        """Run all validations and populate the card grid."""
        self._clear_cards()
        self.problematic_assets = []
        self.run_button.setEnabled(False)

        validation_context = ValidationContext()

        mesh_instance = ValidationInstance("Meshes", "mesh")
        for obj in bpy.data.objects:
            if obj.type == "MESH":
                mesh_instance.add(obj)

        material_instance = ValidationInstance("Materials", "material")
        for mat in bpy.data.materials:
            material_instance.add(mat)

        self.asset_type: str = self.get_asset_type()
        self.asset_name: str = self.get_asset_name()

        mesh_instance.data["asset_type"] = self.asset_type
        mesh_instance.data["asset_name"] = self.asset_name
        material_instance.data["asset_type"] = self.asset_type
        material_instance.data["asset_name"] = self.asset_name

        validation_context.add(mesh_instance)
        validation_context.add(material_instance)

        self.plugins = self.discover_validators()

        # Pre-create all cards in "running" state so the grid is visible immediately
        for idx, plugin_class in enumerate(self.plugins):
            card = ValidationCard(plugin_class.label, parent=self._card_container)
            card._parent_ui = self
            row, col = divmod(idx, self._num_cols)
            self._card_grid.addWidget(card, row, col)
            self._cards.append(card)
            self._cards_by_label[plugin_class.label] = card

        self._set_grid_column_stretches()
        self._update_filter_counts()
        QApplication.processEvents()

        def run_plugin(index):
            if index >= len(self.plugins):
                self.run_button.setEnabled(True)
                self._update_filter_counts()
                self.update_export_button()
                return

            plugin_class = self.plugins[index]
            plugin_instance = plugin_class()
            card = self._cards[index]

            if hasattr(plugin_instance, "families") and "material" in plugin_instance.families:
                instance = material_instance
            else:
                instance = mesh_instance

            try:
                plugin_instance.process(instance)

                if hasattr(plugin_instance, "warnings") and plugin_instance.warnings:
                    has_not_fixable_flag = len(plugin_instance.warnings[0]) > 2 if plugin_instance.warnings else False
                    warning_objects = []

                    if has_not_fixable_flag:
                        for obj, msg, is_not_fixable in plugin_instance.warnings:
                            if obj is None:
                                continue
                            if isinstance(obj, bpy.types.Material) and obj.name in bpy.data.materials:
                                warning_objects.append((obj, f"⚠️ Warning: {msg}", is_not_fixable))
                                continue
                            if isinstance(obj, bpy.types.Object) and obj.name in bpy.data.objects:
                                warning_objects.append((obj, f"⚠️ Warning: {msg}", is_not_fixable))
                            if isinstance(obj, bpy.types.Light) and obj.name in bpy.data.lights:
                                warning_objects.append((obj, f"⚠️ Warning: {msg}", is_not_fixable))
                    else:
                        for obj, msg in plugin_instance.warnings:
                            if obj is None:
                                continue
                            if isinstance(obj, bpy.types.Material) and obj.name in bpy.data.materials:
                                warning_objects.append((obj, f"⚠️ Warning: {msg}"))
                                continue
                            if isinstance(obj, bpy.types.Object) and obj.name in bpy.data.objects:
                                warning_objects.append((obj, f"⚠️ Warning: {msg}"))
                            if isinstance(obj, bpy.types.Light) and obj.name in bpy.data.lights:
                                warning_objects.append((obj, f"⚠️ Warning: {msg}"))

                    if warning_objects:
                        self.problematic_assets.append((plugin_instance, warning_objects, instance))
                        card.setProblematicData(plugin_instance, warning_objects, instance)
                        self.set_status(card, "warning", f"{len(warning_objects)} warnings detected.")
                    else:
                        self.set_status(card, "passed", "No issues (filtered warnings)")
                else:
                    self.set_status(card, "passed", "No issues")

            except Exception as e:
                self.log.error(f"Plugin error: {str(e)}")
                error_objects = []

                if hasattr(plugin_instance, "problematic_assets") and plugin_instance.problematic_assets:
                    for obj, msg in list(plugin_instance.problematic_assets):
                        if not obj:
                            self.log.warning(f"This Obj None: {obj}")
                        elif obj is not None:
                            if isinstance(obj, bpy.types.Material) and obj.name in bpy.data.materials:
                                self.log.warning(f"error objects: {obj.name}")
                                error_objects.append((obj, f"❌ Error: {msg}"))
                                continue
                            if isinstance(obj, bpy.types.Object) and obj.name in bpy.data.objects:
                                error_objects.append((obj, f"❌ Error: {msg}"))
                                continue
                            if isinstance(obj, bpy.types.Light) and obj.name in bpy.data.lights:
                                error_objects.append((obj, f"❌ Error: {msg}"))
                                continue
                else:
                    error_message = f"❌ Error: {str(e)}"
                    self.log.info(f"error_message: {error_message}")

                if error_objects:
                    self.problematic_assets.append((plugin_instance, error_objects, instance))
                    card.setProblematicData(plugin_instance, error_objects, instance)

                    if len(error_objects) == 1:
                        error_message = error_objects[0][1]
                    else:
                        unique_messages = list(set(msg for _, msg in error_objects))
                        if len(unique_messages) == 1:
                            error_message = f"❌ Multiple issues detected: {unique_messages[0]}"
                        else:
                            error_message = f"❌ Multiple issues detected ({len(error_objects)} assets affected). Please Use the Review Problems UI to fix them."

                    self.set_status(card, "failed", error_message)
                else:
                    if hasattr(plugin_instance, "problematic_assets") and plugin_instance.problematic_assets:
                        error_messages = [msg for _, msg in plugin_instance.problematic_assets if msg]
                        if error_messages:
                            self.set_status(card, "failed", error_messages[0])
                        else:
                            self.set_status(card, "passed", "No valid issues (filtered errors)")
                    else:
                        self.set_status(card, "failed", f"❌ Error: {str(e)}")

            QTimer.singleShot(300, lambda: run_plugin(index + 1))

        run_plugin(0)

    def get_latest_version_folder(self, base_path):
        """Find the latest version folder based on semantic versioning (vx.y.z) or create first version if none exists"""
        try:
            version_folders = []
            for item in os.listdir(base_path):
                if os.path.isdir(os.path.join(base_path, item)):
                    if item.startswith("v") and all(part.isdigit() for part in item[1:].split(".")):
                        version_folders.append(item)

            if not version_folders:
                first_version = "v1.0.0"
                first_version_path = os.path.join(base_path, first_version)
                os.makedirs(first_version_path, exist_ok=True)
                self.log.info(f"Created first version folder: {first_version_path}")
                return first_version

            latest_version = max(version_folders, key=lambda v: tuple(map(int, v[1:].split("."))))

            return latest_version

        except Exception as e:
            self.log.error(f"Error finding/creating version folder: {str(e)}")
            return None

    def run_cip_validation(self):
        """Run the temporary CIP validation and update the tree view"""
        self.problematic_assets = []

        blender_file_path = bpy.data.filepath
        file_name, _file_ext = os.path.splitext(os.path.basename(blender_file_path))
        blender_folder = os.path.dirname(blender_file_path)
        temp_dir = os.path.abspath(os.path.join(blender_folder, "cip_temp"))
        usd_file_path = os.path.join(temp_dir, f"{file_name}.usd")
        temp_dir = temp_dir

        def location_mapping(location):
            location_list = location.split("\\")
            collection_name = location_list[2]
            object_name = location_list[3]
            return collection_name, object_name

        os.makedirs(temp_dir, exist_ok=True)

        # TODO: Implement CIP validation logic here
        # Only starting with export params for blender 4.3+
        # Won't support blender 4.3 or less
        export_params = {
            "root_prim_path": "/RootNode",
            "filepath": usd_file_path,
            "selected_objects_only": False,
            "export_animation": False,
            "export_custom_properties": True,
            "custom_properties_namespace": "userProperties",
            "author_blender_name": True,
            "relative_paths": True,
            "convert_orientation": False,
            "evaluation_mode": "RENDER",
            "xform_op_mode": "TRS",
            "export_meshes": True,
            "export_materials": True,
            "export_lights": False,
            "export_cameras": False,
            "export_curves": False,
            "export_points": True,
            "export_volumes": True,
            "export_hair": True,
            "export_subdivision": "BEST_MATCH",
            "export_normals": True,
            "export_uvmaps": True,
            "rename_uvmaps": True,
            "triangulate_meshes": False,
            "quad_method": "SHORTEST_DIAGONAL",
            "ngon_method": "BEAUTY",
            "generate_preview_surface": True,
            "generate_materialx_network": False,
            "convert_world_material": False,
            "export_textures_mode": "NEW",
            "overwrite_textures": True,
            "usdz_downscale_size": "KEEP",
            "export_armatures": False,
            "export_shapekeys": False,
            "only_deform_bones": False,
            "use_instancing": False,
        }
        try:
            if bpy.context.area is None:
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == "VIEW_3D":
                            override = {
                                "window": window,
                                "screen": window.screen,
                                "area": area,
                                "region": area.regions[-1],
                                "scene": bpy.context.scene,
                                "space_data": area.spaces[0],
                            }
                            with bpy.context.temp_override(**override):
                                bpy.ops.wm.usd_export(**export_params)

            # After USD export, run CIP validation and get CSV results
            # TODO: CIP valiation also has location... result['Location'] ... store this for autofix
            # TODO: How does cip determine the object type?  Looks like vehicles and props start with /RootNode... is there metadata somewhere?
            version_base_path = os.path.join(temp_dir, "prop", ".packages", file_name)
            latest_version = self.get_latest_version_folder(version_base_path)

            if not latest_version:
                self.log.error("Could not find latest version folder")
                return

            csv_path = os.path.join(version_base_path, latest_version, "validator_issues.csv")

            import csv

            validation_results = []
            try:
                with open(csv_path, "r") as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        validation_results.append(row)
            except FileNotFoundError:
                self.log.error(f"Validation results file not found: {csv_path}")
                return
            except Exception as e:
                self.log.error(f"Error reading validation results: {str(e)}")
                return

            asset_groups = {}
            for result in validation_results:
                asset = result["Asset"]
                if asset not in asset_groups:
                    asset_groups[asset] = []
                asset_groups[asset].append(result)

            if validation_results:
                self.open_cip_problems_ui(validation_results)

        except Exception as e:
            self.log.error(f"Error in CIP validation: {str(e)}")
            message_box("CIP Validation Error", f"An error occurred during validation: {str(e)}")

    def open_cip_problems_ui(self, validation_results):
        """Open the CIP Problem Assets UI dialog"""
        dialog = CIPProblemAssetsUI(validation_results, parent_ui=self)
        dialog.show()

    def _clear_cards(self):
        """Remove all validation cards from the grid and reset tracking state."""
        for card in self._cards:
            self._card_grid.removeWidget(card)
            card.deleteLater()
        self._cards = []
        self._cards_by_label = {}
        self._reset_filter_counts()

    def _reset_filter_counts(self):
        """Reset filter tab badge counts to zero."""
        if hasattr(self, "_filter_btn_passed"):
            self._filter_btn_passed.setText("PASSED  0")
            self._filter_btn_warnings.setText("WARNINGS  0")
            self._filter_btn_failed.setText("FAILED  0")

    def _update_filter_counts(self):
        """Update filter tab badge counts based on current card states."""
        if not hasattr(self, "_filter_btn_passed"):
            return
        passed = sum(1 for c in self._cards if c.getState() == "passed")
        warned = sum(1 for c in self._cards if c.getState() in ("warning", "perf"))
        failed = sum(1 for c in self._cards if c.getState() in ("failed", "critical"))
        self._filter_btn_passed.setText(f"PASSED  {passed}")
        self._filter_btn_warnings.setText(f"WARNINGS  {warned}")
        self._filter_btn_failed.setText(f"FAILED  {failed}")

    def _apply_filter(self, state_filter: str):
        """Show/hide cards and update active tab highlight."""
        for btn in (self._filter_btn_all, self._filter_btn_passed, self._filter_btn_warnings, self._filter_btn_failed):
            btn.setProperty("active", "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        active_map = {
            "all": self._filter_btn_all,
            "passed": self._filter_btn_passed,
            "warning": self._filter_btn_warnings,
            "failed": self._filter_btn_failed,
        }
        active_btn = active_map.get(state_filter, self._filter_btn_all)
        active_btn.setProperty("active", "true")
        active_btn.style().unpolish(active_btn)
        active_btn.style().polish(active_btn)

        for card in self._cards:
            if state_filter == "all":
                card.setVisible(True)
            elif state_filter == "passed":
                card.setVisible(card.getState() == "passed")
            elif state_filter == "warning":
                card.setVisible(card.getState() in ("warning", "perf"))
            elif state_filter == "failed":
                card.setVisible(card.getState() in ("failed", "critical"))

        self._rebuild_card_grid()

    def _set_grid_column_stretches(self):
        """Set equal column stretches for the current column count, clear unused ones."""
        for col in range(3):
            self._card_grid.setColumnStretch(col, 0)
        for col in range(self._num_cols):
            self._card_grid.setColumnStretch(col, 1)

    def _rebuild_card_grid(self):
        """Re-place visible cards in the grid using the current column count."""
        for card in self._cards:
            self._card_grid.removeWidget(card)
        visible_idx = 0
        for card in self._cards:
            if card.isVisible():
                row, col = divmod(visible_idx, self._num_cols)
                self._card_grid.addWidget(card, row, col)
                visible_idx += 1
        self._set_grid_column_stretches()

    def set_status(self, card: "ValidationCard", state: str, description: str):
        """Update a card's visual state."""
        card.setState(state, description)
        QApplication.processEvents()

    def on_bypass_changed(self, state):
        # TODO: why does qt return 2 for True?  Qt.Checked is supposed to work. Need to investigate.
        if state == Qt.Checked or state == 2:
            self.export_button.setEnabled(True)
            self.export_button.setToolTip(f"Enable by resolving all errors or checking {BYPASS_VALIDATION_CHECKS}")
            self.export_button.clicked.connect(self.export_asset)
        else:
            self.export_button.setEnabled(False)
            self.export_button.setToolTip("Enable by resolving all errors.")

    def on_use_material_x_changed(self, state):
        """
        Handle checkbox state change for using Material X
        Sync to Blender property state as well
        """
        if state == Qt.Checked or state == 2:
            self.log.info("Using Material X + MDL")
            self.use_material_x_checkbox.setChecked(True)
            bpy.context.scene.export_props.use_materialx = True
        else:
            self.log.info("Only using MDL")
            self.use_material_x_checkbox.setChecked(False)
            bpy.context.scene.export_props.use_materialx = False
