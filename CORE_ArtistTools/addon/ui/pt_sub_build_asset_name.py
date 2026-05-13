# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


import bpy

from ..library import *  # noqa F403
from ..resource.simready_standards import *  # noqa F403

# variables for tracking asset category, and class
assetcat = ""
assetclass = ""
showsub = False
typeflag = ""  # prototype: this variable will be used to enable different parms and name calculation
# allowable values are currently "vehicle" and "prop"


def type_enums_callback(scene, context):
    items = assetname_dict["types"]  # noqa F405
    return items


def veh_make_enums_callback(scene, context):
    items = assetname_dict["veh_make"]  # noqa F405
    return items


def cat_enums_callback(scene, context):
    items = assetname_dict["categories"]  # noqa F405
    return items


def class_enums_callback(scene, context):
    # use category to determine which classes to show
    assetcat = clean_text(bpy.context.scene.bld_a_nm_props.assetname_cat)  # noqa F405
    # print("callback_class",assetcat)
    items = []
    if assetcat == "traf":
        items = assetname_dict["classes_traffic"]  # noqa F405
    else:
        items = assetname_dict["classes_roadside"]  # noqa F405
    return items


def subclass_enums_callback(scene, context):
    # use category to determine which classes to show
    assetcat = clean_text(bpy.context.scene.bld_a_nm_props.assetname_cat)  # noqa F405
    assetclass = clean_text(bpy.context.scene.bld_a_nm_props.assetname_class)  # noqa F405
    # print("callback_subclass",assetclass)
    items = []
    if assetclass == "veg":
        items = assetname_dict["subclasses_vegetation"]  # noqa F405
    elif assetclass == "bldg":
        items = assetname_dict["subclasses_building"]  # noqa F405
    elif assetclass == "sgn":
        items = assetname_dict["subclasses_fxd_or_mov"]  # noqa F405
    elif assetclass == "pole":
        items = assetname_dict["subclasses_fxd_or_mov"]  # noqa F405
    elif assetclass == "strt":
        items = assetname_dict["subclasses_fxd_or_mov"]  # noqa F405
    elif assetclass == "constr":
        items = assetname_dict["subclasses_fxd_or_mov"]  # noqa F405
    elif assetclass == "emerg":
        items = assetname_dict["subclasses_fxd_or_mov"]  # noqa F405
    elif assetcat == "traf":
        items = assetname_dict["subclasses_fxd_or_mov"]  # noqa F405
    else:
        items = []
    return items


def size_enums_callback(scene, context):
    # use category to determine which classes to show
    items = assetname_dict["size"]  # noqa F405
    return items


def style_enums_callback(scene, context):
    # use category to determine which classes to show
    items = assetname_dict["style"]  # noqa F405
    return items


def condition_enums_callback(scene, context):
    # use category to determine which classes to show
    items = assetname_dict["condition"]  # noqa F405
    return items


def country_enums_callback(scene, context):
    # use category to determine which classes to show
    items = assetname_dict["country"]  # noqa F405
    return items


# PROPERTIES
class CORE_build_asset_name_common:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    bl_options = {"DEFAULT_CLOSED"}
