# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy
from bpy.props import BoolProperty


class ExportProperties(bpy.types.PropertyGroup):

    poseable_only: BoolProperty(
        name="Poseable Only",
        description="Poseable only means it's an asset setup to work with keyframes and animation.  Physics will be disabled.",
        default=False,
    )

    use_materialx: BoolProperty(
        name="Use MaterialX",
        description="Export MaterialX shader networks. When enabled, post-processing will modify MaterialX shader prims.",
        default=False,
    )
