# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
# Go up two levels: export_gui/ -> library/ -> addon/
_addon_dir = os.path.join(current_dir, "..", "..")
PLUGIN_DIR = os.path.join(_addon_dir, "validators")

# Module-level flag for USD hook (avoids writing to Scene from timer context
# where ID writes are disallowed). Read by ot_simready_usdhook via getattr().
_active_usd_hook = ""

# Constants
BLEND_FILE_EXTENSION = ".blend"
BYPASS_VALIDATION_CHECKS = "Bypass Validation Checks"
USE_MATERIAL_X = "Use Material X"

# --- Neon Graphite theme palette ---
THEME = {
    "bg_base": "#121212",
    "bg_card": "#1A1A1A",
    "bg_mid": "#202020",
    "border": "#2A2A2A",
    "border_strong": "#333333",
    "accent": "#76B900",
    "text_primary": "#FFFFFF",
    "text_secondary": "#AAAAAA",
    "text_dim": "#666666",
    "passed_text": "#76B900",
    "warning_text": "#C8A000",
    "warning_bg": "#1E1900",
    "failed_text": "#CC4444",
    "failed_bg": "#1E0A0A",
}
FONT_FAMILY = "Space Grotesk, Segoe UI, Arial, sans-serif"
