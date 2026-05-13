# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import bpy

from CORE_ArtistTools.addon.library.make_source_art_dirs import (
    CORE_make_source_art_dirs,
)

current_dir = os.path.dirname(os.path.abspath(__file__))

from CORE_ArtistTools.addon.validators.validation_base import *  # noqa F403

# ------------------------------------------------------------------------------------------------
# DIRECTORY STRUCTURE DEFINITIONS
# ------------------------------------------------------------------------------------------------


@dataclass
class SystemConfig:
    """System configuration and path separators."""

    system_type: str
    path_separator: str

    @classmethod
    def detect_system(cls) -> "SystemConfig":
        """Detect the current system and return appropriate configuration."""
        if os.name == "nt":
            return cls("Windows", "\\")
        elif os.name == "posix":
            return cls("Linux", "/")
        else:
            return cls("Mac", "/")


@dataclass
class AssetInfo:
    """Asset information and metadata."""

    name: str
    asset_type: str
    root_path: str
    formatted_path: Optional[str] = None

    def __post_init__(self):
        """Post-initialization processing."""
        if self.asset_type == "vehicle":
            self.formatted_path = self._format_vehicle_path()

    def _format_vehicle_path(self) -> Optional[str]:
        """Format vehicle asset path based on naming convention."""
        parts = self.name.split("_")

        if len(parts) < 2:
            print(f"ERROR: Invalid asset name '{self.name}'")
            return None

        # Detect the last part as the year (assuming it's a 4-digit number)
        match = re.match(r"^\d{4}$", parts[-1])
        if match:
            year = parts.pop()
        else:
            year = None

        brand = parts[0]
        model_section = "_".join(parts[1:])

        if year:
            system_config = SystemConfig.detect_system()
            return f"{brand}{system_config.path_separator}{model_section}{system_config.path_separator}{year}"
        else:
            print(f"WARNING: No year detected in asset name '{self.name}'")
            return None


@dataclass
class DirectoryStructure:
    """Directory structure configuration for asset validation."""

    asset_root: Tuple[str, ...]
    asset_level: Tuple[str, ...]
    dcc_project_level: Tuple[str, ...]
    source_level: Tuple[str, ...]
    model_subdirs: Tuple[str, ...]
    surface_subdirs: Tuple[str, ...]

    @classmethod
    def get_default_structure(cls) -> "DirectoryStructure":
        """Get the default directory structure configuration."""
        return cls(
            asset_root=("dcc_source",),
            asset_level=("dcc_source",),
            dcc_project_level=("working",),
            source_level=("reference", "model", "texture"),
            model_subdirs=("blender", "3dsmax", "maya"),
            surface_subdirs=("designer", "painter", "photoshop"),
        )


# ------------------------------------------------------------------------------------------------
# AUTOFIXERS (HIEARCHY)
# ------------------------------------------------------------------------------------------------
class Fix_CreateFolders_Props(Action):  # noqa E405
    """Create missing folders in the expected structure using the same logic as make_source_art_dirs.py"""

    label = "Create Missing Folders"
    icon = "wrench"  # Icon for the action
    on = "failed"  # This action is available on failed validators

    def process(self, context, plugin):
        # Get the instance that failed validation
        instance = context[0]
        success = True

        # Get asset information from instance
        asset_name = instance.data.get("asset_name", "unknown_asset")
        asset_type = instance.data.get("asset_type", "prop")

        # Get the blend file path
        blend_filepath = bpy.data.filepath
        if not blend_filepath:
            self.log.error("Blender file must be saved before creating folders")
            instance.data["fix_success"] = False
            return

        blend_dir = os.path.dirname(blend_filepath)

        # Try to find the asset root directory
        asset_root_dir = self._find_asset_root_directory(blend_dir, asset_name, asset_type)

        if not asset_root_dir or asset_root_dir == dummy_obj:  # noqa F405
            self.log.error(f"Could not locate asset root directory for '{asset_name}'")
            instance.data["fix_success"] = False
            return

        try:
            result = CORE_make_source_art_dirs(asset_root_dir, asset_name, asset_type)

            if result.get("FINISHED"):
                self.log.info(f"Successfully created directory structure for asset: {asset_name}")
                success = True
            else:
                self.log.error(f"Failed to create directory structure: {result.get('CANCELLED', 'Unknown error')}")
                success = False

        except Exception as e:
            self.log.error(f"Failed to create folder structure: {e}")
            success = False

        instance.data["fix_success"] = success

    def _find_asset_root_directory(self, blend_dir: str, asset_name: str, asset_type: str) -> Optional[str]:
        """Find the asset root directory by traversing up from the blend file location."""
        current_path = os.path.abspath(blend_dir)

        # For vehicle assets, we need to handle the special path format
        if asset_type == "vehicle":
            asset_info = AssetInfo(name=asset_name, asset_type=asset_type, root_path="")
            if asset_info.formatted_path:
                # Look for the formatted vehicle path
                while current_path != os.path.dirname(current_path):  # Not at root
                    potential_asset_path = os.path.join(current_path, asset_info.formatted_path)
                    if os.path.exists(potential_asset_path):
                        return current_path
                    current_path = os.path.dirname(current_path)
        else:
            # For non-vehicle assets, look for the asset name directory
            while current_path != os.path.dirname(current_path):  # Not at root
                potential_asset_path = os.path.join(current_path, asset_name)
                if os.path.exists(potential_asset_path):
                    return current_path
                current_path = os.path.dirname(current_path)

        # If we can't find an existing asset directory, use the parent of the blend file
        # This allows creating new asset structures
        return os.path.dirname(blend_dir)


# ------------------------------------------------------------------------------------------------
# VALIDATORS (HIEARCHY)
# ------------------------------------------------------------------------------------------------


class Validate_SR_FolderStructure(InstancePlugin):  # noqa E405
    """Validate that the asset follows the expected directory structure."""

    label = "Validate Source Art Folders"

    families = ["mesh"]
    asset_types = ["all"]
    actions = []

    def process(self, instance):
        issues_all = []
        issues_warn_all = []

        # Why a dummy object? Because validator needs to return some kind of object.
        dummy_obj = bpy.data.lights.get("Light")  # noqa F405

        # Get asset information from instance
        asset_name = instance.data.get("asset_name", "unknown_asset")
        asset_type = instance.data.get("asset_type", "prop")

        # print(f"DEBUG: Validating directory structure for asset: '{asset_name}' (type: '{asset_type}')")

        # Get blend file path and determine root directory
        blend_filepath = bpy.data.filepath
        if not blend_filepath:

            issues_all.append((dummy_obj, "Blender file must be saved before validation"))
            self.problematic_assets = issues_all
            raise ValueError("Blender file must be saved before validation")

        blend_dir = os.path.dirname(blend_filepath)

        # Try to find the asset root directory by looking for the asset name
        asset_root_dir = self._find_asset_root_directory(blend_dir, asset_name, asset_type)

        if not asset_root_dir:
            # If we can't find the asset directory, that's a warning (not a failure)
            issues_warn_all.append(
                (
                    dummy_obj,
                    f"Asset directory not found for '{asset_name}'.\n Your asset will not export to the expected folders. \nSee Documentation (Core Tools: Asset Management) for project structure setup.",
                )
            )
            self.problematic_assets = issues_warn_all
            self.warnings = issues_warn_all
            return  # Return early since we can't continue without a valid root directory

        # Initialize structure configuration
        dir_structure = DirectoryStructure.get_default_structure()
        asset_info = AssetInfo(name=asset_name, asset_type=asset_type, root_path=asset_root_dir)

        # Validate the directory structure
        self._validate_directory_structure(asset_info, dir_structure, issues_all, issues_warn_all)

        issues = list(set(issues_all))
        self.problematic_assets = issues

        if issues_warn_all:
            issues_warn = list(set(issues_warn_all))
            self.warnings = issues_warn

        # Only raise an error if there are actual errors (not warnings)
        if issues:
            raise ValueError("\n".join(msg for _, msg in issues))

    def _find_asset_root_directory(self, blend_dir: str, asset_name: str, asset_type: str) -> Optional[str]:
        """Find the asset root directory by traversing up from the blend file location."""
        current_path = os.path.abspath(blend_dir)

        # For non-vehicle assets, look for the asset name directory
        while current_path != os.path.dirname(current_path):  # Not at root
            potential_asset_path = os.path.join(current_path, asset_name)

            if os.path.exists(potential_asset_path):
                return current_path

            current_path = os.path.dirname(current_path)
        return None

    def _validate_directory_structure(
        self, asset_info: AssetInfo, dir_structure: DirectoryStructure, issues_all: List, issues_warn_all: List
    ):
        """Validate the complete directory structure for an asset."""

        # Get dummy object for warnings
        dummy_obj = bpy.data.lights.get("Light")  # noqa F405

        # Check if we're dealing with a dummy object (when asset root couldn't be found)
        if asset_info.root_path is None:
            issues_warn_all.append(
                (
                    dummy_obj,
                    f"Asset directory not found for '{asset_info.name}'.\nYour asset will not export to the expected folders.\nSee CORE_ArtistTools_README.md for project structure setup.",
                )
            )
            return

        asset_path = os.path.join(asset_info.root_path, asset_info.name)

        # Check if asset directory exists
        if not os.path.exists(asset_path):
            issues_warn_all.append((dummy_obj, f"Asset directory missing: {os.path.basename(asset_path)}"))

        # Only validate subdirectories if the asset directory exists
        if os.path.exists(asset_path):
            # Validate asset level directories
            self._validate_directory_level(
                asset_path, list(dir_structure.asset_level), "asset level", issues_warn_all, dummy_obj
            )

            # Validate project level directories
            project_path = os.path.join(asset_path, dir_structure.asset_level[0])
            if os.path.exists(project_path):
                self._validate_directory_level(
                    project_path, list(dir_structure.dcc_project_level), "project level", issues_warn_all, dummy_obj
                )

                # Validate source directories
                source_path = os.path.join(project_path, dir_structure.dcc_project_level[0])
                if os.path.exists(source_path):
                    self._validate_directory_level(
                        source_path, list(dir_structure.source_level), "source level", issues_warn_all, dummy_obj
                    )

                    # Validate model subdirectories
                    model_path = os.path.join(source_path, "model")
                    if os.path.exists(model_path):
                        self._validate_directory_level(
                            model_path, list(dir_structure.model_subdirs), "model", issues_warn_all, dummy_obj
                        )

                    # Validate texture subdirectories
                    texture_path = os.path.join(source_path, "texture")
                    if os.path.exists(texture_path):
                        self._validate_directory_level(
                            texture_path, list(dir_structure.surface_subdirs), "texture", issues_warn_all, dummy_obj
                        )

    def _validate_directory_level(
        self, base_path: str, expected_dirs: List[str], level_name: str, issues_warn_all: List, dummy_obj
    ):
        """Validate that expected directories exist at a given level."""
        for dir_name in expected_dirs:
            dir_path = os.path.join(base_path, dir_name)
            if not os.path.exists(dir_path):
                issues_warn_all.append((dummy_obj, f"Missing {level_name} folder: {dir_name}"))


class Validate_BlenderFileNotSaved(InstancePlugin):  # noqa E405
    """Validate that the Blender file is not saved"""

    label = "Validate Blender File Not Saved"

    families = ["mesh"]
    asset_types = ["all"]
    actions = []

    def process(self, _instance):
        issues_all = []
        issues_warn_all = []  # noqa: F841

        blend_filepath = bpy.data.filepath

        is_startup_file = False

        if blend_filepath == "":
            is_startup_file = True

        if is_startup_file:
            dummy_obj = bpy.data.lights.get("Light")  # noqa F405

            issues_all.append(
                (
                    dummy_obj,
                    "This appears to be a Blender startup file or you haven't saved the file yet. Please save your file with an appropriate name before publishing.",
                )
            )

        issues = list(set(issues_all))
        self.problematic_assets = issues

        if issues:
            raise ValueError("\n".join(msg for _, msg in issues))
