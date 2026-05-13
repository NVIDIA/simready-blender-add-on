# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from os.path import dirname, join, split

import bpy
import bpy.utils.previews


def get_icons_directory():
    head, tail = split(dirname(__file__))
    icons_directory = join(head, "resource", "icons")
    return icons_directory  # retrieve icons


icons = bpy.utils.previews.new()
icons_directory = get_icons_directory()
print(icons_directory)
icons.load("OMNIBLEND", join(icons_directory, "BlenderOMNI.png"), "IMAGE")
icons.load("OMNI", join(icons_directory, "ICON.png"), "IMAGE")
