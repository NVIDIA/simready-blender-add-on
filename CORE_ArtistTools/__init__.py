# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from .addon.library import *  # noqa F403
from .addon.resource.core_blender_libs import *  # noqa F403
from .sys_functions import check_and_install_dependencies

bl_info = {
    "name": "Simready_Blender_Core",
    "description": "General Tools, Autochecker, UsdHook, Physics Tools",
    "author": "NVIDIA",
    "version": (0, 4, 0),  # <version number>, <hotfix iteration>, <if we run out of numbers>?
    "blender": (5, 0, 0),  # Aligns with Blender versions (3rd digit is always 0)
    "location": "View3D",
    "category": "3D View",
}

# Run dependency check and install if needed
# If False is returned, packages were just installed and Blender needs to be restarted
deps_ready = check_and_install_dependencies()


def register():
    # Only register if dependencies are ready
    if deps_ready:
        from .addon.register import register_addon

        register_addon()
    else:
        # Register minimal UI to show restart warning
        import bpy  # noqa F401
        from bpy.utils import register_class

        try:
            from .addon.utility.restart_warning import (
                CORE_OT_restart_warning,
                show_restart_warning,
            )

            register_class(CORE_OT_restart_warning)

            show_restart_warning(
                "CORE_ArtistTools has installed required dependencies.\n"
                "These packages are now available:\n"
                "- PySide6, Pillow, PyTorch, Transformers, and more\n\n"
                "Blender needs to restart to use them."
            )
        except Exception as e:
            print(f"Could not show UI warning: {e}")

        print("=" * 80)
        print("CORE_ArtistTools: Dependencies were just installed.")
        print("Please restart Blender to complete the installation.")
        print("=" * 80)


def unregister():
    # Only unregister if we fully registered
    if deps_ready:
        from .addon.register import unregister_addon

        unregister_addon()
    else:
        # Unregister minimal UI
        import bpy  # noqa F401
        from bpy.utils import unregister_class

        try:
            from .addon.utility.restart_warning import CORE_OT_restart_warning

            unregister_class(CORE_OT_restart_warning)
        except Exception as e:
            print(f"Could not unregister restart warning: {e}")


# GHOST OF STEVE'S EVIL PAST
SRAT_print_a_thing()  # noqa F405
