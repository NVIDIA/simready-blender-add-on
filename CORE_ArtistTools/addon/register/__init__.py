# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


def register_addon():
    # Initialize logging system first
    from ..library.addon_logging import setup_logger

    setup_logger("CORE_ArtistTools")

    # Property - Register properties first so UI classes can reference them
    from ..property import register_properties

    register_properties()

    # UI
    # Menus and Panels used in addon
    from ..ui import register_ui

    register_ui()

    # Operator

    # Utility
    """from ..utility import register_utility
    register_utility()"""

    # Keymap
    from .keymap import register_keymap

    register_keymap()


def unregister_addon():

    # UI
    from ..ui import unregister_ui

    unregister_ui()

    # Utility
    """from ..utility import unregister_utility
    unregister_utility()"""

    # Property - Unregister properties after UI
    from ..property import unregister_properties

    unregister_properties()

    # Keymaps
    from .keymap import unregister_keymap

    unregister_keymap()
