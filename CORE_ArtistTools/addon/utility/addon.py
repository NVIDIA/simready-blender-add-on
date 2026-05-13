# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy

addon_name = __name__.partition(".")[0]
# addon_name = __package__.partition('.')[0]


def get_prefs():
    return bpy.context.preferences.addons[addon_name].preferences
