# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""Names and paths shared by the thumbnailer rig and operators."""

# Collections
COL_THUMBNAIL = "THUMBNAIL"
COL_EXPORT = "Export"
COL_GEOMETRY = "Geometry"

# Objects
OBJ_THUMBNAIL_CAMERA = "Thumbnail_Camera"
OBJ_THUMBNAIL_TARGET = "Thumbnail_Target"
OBJ_GROUND_PLANE = "Ground_Plane"

# Rig lights (object names)
LIGHT_KEY = "Light_Key"
LIGHT_FILL = "Light_Fill"
LIGHT_RIM = "Light_Rim"
LIGHT_SHADOW = "Light_Shadow"

LIGHT_NAMES = (LIGHT_KEY, LIGHT_FILL, LIGHT_RIM, LIGHT_SHADOW)

# Light linking collection names (receiver / blocker)
COL_LIGHT_LINKING_EXPORT = "Light_Linking_Export"
COL_SHADOW_LINKING_EXPORT = "Shadow_Linking_Export"

# Core addon (for resource path discovery)
ADDON_SIMREADY_CORE_NAME = "Simready_Blender_Core"

# Asset layout: walk up from blend until this folder name (case-insensitive)
DCC_SOURCE_DIR = "dcc_source"

# Relative to asset root
REL_SIMREADY_THUMBS = ("simready_usd", ".thumbs")

# Lighting rig filenames
RIG_STUDIO_BLEND = "thumbnail_environment_studio.blend"
RIG_OUTDOOR_BLEND = "thumbnail_environment_outdoor.blend"
REL_TEMPLATE_ENVIRONMENTS = ("template_environments",)

# Preset enum values (must match LIGHTING_PRESET_ITEMS in pt_thumbnailer)
PRESET_STUDIO = "STUDIO"
PRESET_OUTDOOR = "OUTDOOR"
