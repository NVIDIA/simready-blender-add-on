# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


def __getattr__(name: str):
    """PEP 562 module __getattr__: forward _active_usd_hook reads to theme module.

    ot_simready_usdhook.py reads this flag via:
        getattr(run_export_gui, "_active_usd_hook", "")
    ValidationUI writes it via _theme._active_usd_hook in validation_ui.py.
    Both sides reference the same object in export_gui.theme.
    """
    if name == "_active_usd_hook":
        from .export_gui import theme

        return theme._active_usd_hook
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
