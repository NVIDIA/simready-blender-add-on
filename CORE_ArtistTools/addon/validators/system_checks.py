# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import platform

from CORE_ArtistTools.addon.validators.logging_controller import logger

platform = platform.system()

if platform == "Windows":
    system_type = "Windows"
elif platform == "Linux":
    system_type = "Linux"
elif platform == "Darwin":
    system_type = "Mac"
else:
    system_type = "Unknown"
    logger.logging.warning(f"Platform: {platform}")
