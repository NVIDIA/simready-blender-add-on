# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from CORE_ArtistTools.addon.utility.addon import get_prefs


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
    """Directory structure configuration for asset creation."""

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


@dataclass
class DirectoryInfo:
    """Directory information and descriptions."""

    info_dict: Dict[str, str]

    @classmethod
    def get_default_info(cls) -> "DirectoryInfo":
        """Get the default directory information."""
        info_dict = {
            "dcc_source": "This is your working directory. All wip source goes into working directory..",
            "working": "model, reference, and textures are where your wip source goes.",
            "model": "All geometry source files. Directories are created for commonly used file formats "
            "but it is ok to create new subdirectories as needed (i.e. obj) for exports out of ZBrush.",
            "texture": "All material and texture source files.  If textures are from shared library, autofix will move them to this directory.",
            "designer": "Adobe Substance 3D Designer source files.",
            "painter": "Adobe Substance 3D Painter source files.",
            "reference": "Reference images. A PureRef file with clean, organized reference images, and any other forms of reference.",
            "blender": "Blender (*.blend) files used in creation of geometry.",
            "3dsmax": "3ds max (*.max, *.mb) files used in creation of geometry. Best practice is to save 3ds max files.",
            "maya": "Maya (*.ma, *.mb) files used in creation of geometry.",
            "photoshop": "Photoshop (*.psd) files used in creation of geometry.",
        }
        return cls(info_dict)


def CreateDirectories(
    thepath: str,
    names: List[str],
    maketxt: bool,
    info_dict: Optional[Dict[str, str]] = None,
    root: bool = False,
) -> None:
    for n in names:
        dpath = os.path.join(thepath, n)
        if not os.path.exists(dpath):
            os.makedirs(dpath)
        if maketxt:
            if root:
                pass
            else:
                text_name = "placeholder.txt"
                text_content = ""

                if info_dict and n in info_dict:
                    text_name = n + ".txt"
                    text_content = info_dict[n]
                fpath = os.path.join(dpath, text_name)
                with open(fpath, "w") as file:
                    file.write(text_content)


def CORE_make_source_art_dirs(root_path: str, asset_name: str, asset_type: str = "prop") -> Dict[str, str]:
    """
    Create standardized source art directory for an asset.
    This standardized format includes directories and notes that explain the purpose
    of each directory.
    """
    # Initialize dataclasses
    asset_info = AssetInfo(name=asset_name, asset_type=asset_type, root_path=root_path)
    dir_structure = DirectoryStructure.get_default_structure()
    dir_info = DirectoryInfo.get_default_info()

    # Handle vehicle asset path formatting
    if asset_type == "vehicle":
        print(f"asset_name_vehicle: {asset_info.formatted_path}")

        if not asset_info.formatted_path:
            print(f"ERROR: Invalid asset name '{asset_name}' ... please conform to brand_model_year")
            return {"CANCELLED": ""}

        asset_path = os.path.join(root_path, asset_info.formatted_path)

        try:
            os.makedirs(asset_path)
        except FileExistsError:
            print("Directory already exists")
            return {"CANCELLED": ""}
    else:
        # Create root level directory for non-vehicle assets
        CreateDirectories(root_path, [asset_name], True, dir_info.info_dict, root=True)
        asset_path = os.path.join(root_path, asset_name)

    # Create asset level directories
    CreateDirectories(asset_path, list(dir_structure.asset_level), True, dir_info.info_dict)

    # Create project level directories
    project_path = os.path.join(asset_path, dir_structure.asset_level[0])
    CreateDirectories(project_path, list(dir_structure.dcc_project_level), True, dir_info.info_dict)

    # Create source directories
    source_path = os.path.join(project_path, dir_structure.dcc_project_level[0])
    CreateDirectories(source_path, list(dir_structure.source_level), True, dir_info.info_dict)

    # # Create model subdirectories
    model_path = os.path.join(source_path, dir_structure.source_level[1])
    CreateDirectories(model_path, list(dir_structure.model_subdirs), True, dir_info.info_dict)

    # # Create surface subdirectories
    surface_path = os.path.join(source_path, dir_structure.source_level[2])
    CreateDirectories(surface_path, list(dir_structure.surface_subdirs), True, dir_info.info_dict)

    return {"FINISHED": asset_path}


def CORE_save_and_open_current_file(save_path: str) -> None:
    """
    Save the current file and open a new file.
    """
    import bpy

    bpy.ops.wm.save_as_mainfile(filepath=save_path)
    bpy.ops.wm.open_mainfile(filepath=save_path)
    print(f"SAVING FILE: {save_path}")


def CORE_set_project_config_if_needed(root_path: str) -> None:
    """
    Set the project config if it is not already set.
    Scans up directories from root_path to find project_config.toml file.
    """
    if not root_path:
        return

    prefs = get_prefs()
    project_config_path = prefs.settings.ds_project_config_path

    # If project config path is already set and not empty, return early
    if project_config_path and project_config_path.strip():
        return

    # Start scanning from the provided root_path
    current_path = os.path.abspath(root_path)

    while True:
        # Check if project_config.toml exists in current directory
        config_file_path = os.path.join(current_path, "project_config.toml")

        if os.path.isfile(config_file_path):
            # Found the config file, set it in preferences
            prefs.settings.ds_project_config_path = config_file_path
            print(f"Found project config: {config_file_path}")
            return

        # Get parent directory
        parent_path = os.path.dirname(current_path)

        # If we've reached the root directory (parent is same as current), stop searching
        if parent_path == current_path:
            print("ERROR: Could not find project_config.toml file in any parent directory")
            return

        # Move up one directory
        current_path = parent_path


def CORE_find_simready_folder(blender_file_path: str) -> str:
    """Utility method to find the simready_usd folder"""

    if not blender_file_path:
        return

    current_path = os.path.dirname(os.path.abspath(blender_file_path))

    while True:
        test_path = os.path.join(current_path, "simready_usd")
        if os.path.isdir(test_path):
            return test_path
        parent_path = os.path.dirname(current_path)
        if parent_path == current_path:
            return
        current_path = parent_path
