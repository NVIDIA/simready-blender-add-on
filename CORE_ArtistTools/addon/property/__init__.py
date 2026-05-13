# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy
from bpy.props import PointerProperty

from .addon import CORE_Props
from .export_props import ExportProperties
from .global_metadata import GlobalMetadataProps
from .settings import CORE_Settings
from .tool_props import Build_Asset_Name_Properties, Build_Mat_Name_Properties

classes = (
    CORE_Settings,
    CORE_Props,
    ExportProperties,
    GlobalMetadataProps,
    Build_Mat_Name_Properties,
    Build_Asset_Name_Properties,
)


def register_properties():
    from bpy.utils import register_class

    for cls in classes:
        try:
            register_class(cls)
        except ValueError as e:
            if "already registered" in str(e):
                print(f"Warning: Class {cls.__name__} was already registered, skipping...")
            else:
                raise e
    bpy.types.Scene.export_props = PointerProperty(type=ExportProperties)
    bpy.types.Scene.global_metadata = PointerProperty(type=GlobalMetadataProps)
    bpy.types.Scene.bld_matname_props = PointerProperty(type=Build_Mat_Name_Properties)
    bpy.types.Scene.bld_a_nm_props = PointerProperty(type=Build_Asset_Name_Properties)


def unregister_properties():
    from bpy.utils import unregister_class

    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.export_props
    del bpy.types.Scene.global_metadata
    del bpy.types.Scene.bld_matname_props
    del bpy.types.Scene.bld_a_nm_props
