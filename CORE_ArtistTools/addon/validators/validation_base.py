# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import CORE_ArtistTools.addon.validators.logging_controller as logger

# import bpy


class Action:
    """Base class for validation actions/fixes"""

    def __init__(self):
        self.log = logger.logging

    def process(self, context, plugin):
        raise NotImplementedError("Action must implement process method")


class InstancePlugin:
    """Base class for instance plugins"""

    label = "Base Validator"
    asset_types = ["all"]
    families = []

    def __init__(self):
        self.log = logger.logging
        self.warnings = []
        self.problematic_assets = []

    def process(self, instance):
        raise NotImplementedError("Plugin must implement process method")
