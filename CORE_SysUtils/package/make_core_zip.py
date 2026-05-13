# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import os
import re
import zipfile


def get_version_from_init(init_file_path):
    """Extract version tuple from __init__.py bl_info."""
    with open(init_file_path, "r") as f:
        content = f.read()
        # Look for version tuple in bl_info
        match = re.search(r'"version"\s*:\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', content)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


def zip_folders(zip_name, folder1, folder2):
    # Create a ZipFile object with the specified name and mode
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Helper function to add a folder to the zip
        def add_folder_to_zip(folder_path):
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    # Create the full path to the file
                    full_path = os.path.join(root, file)
                    # Add the file to the zip, specifying the arcname to maintain the correct folder structure
                    zipf.write(full_path, os.path.relpath(full_path, os.path.dirname(folder_path)))

        # Add both folders to the zip
        add_folder_to_zip(folder1)
        add_folder_to_zip(folder2)


# Get the directory of the script
script_dir = os.path.dirname(__file__)
base_dir = os.path.dirname(os.path.dirname(script_dir))


# Use os.path.join to define folders relative to the base_dir
folder1 = os.path.join(base_dir, "CORE_ArtistTools")
folder2 = os.path.join(base_dir, "CORE_ArtistTools_Resources")

# Get version from __init__.py
init_file = os.path.join(folder1, "__init__.py")
version = get_version_from_init(init_file)

if version:
    version_str = f"{version[0]}_{version[1]}_{version[2]}"
    zip_name = os.path.join(base_dir, f"SimReady_Blender_CORE_{version_str}.zip")
    print(f"Creating zip: SimReady_Blender_CORE_{version_str}.zip")
else:
    zip_name = os.path.join(base_dir, "SimReady_Blender_CORE.zip")
    print("Warning: Could not find version, using default name")

zip_folders(zip_name, folder1, folder2)
print(f"Successfully created: {zip_name}")
