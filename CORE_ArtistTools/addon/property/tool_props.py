# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import bpy
from bpy.types import PropertyGroup

from ..library.helpers import clean_text
from ..resource.simready_standards import *  # noqa F403

# ===================================================
# HELPERS METHODS
# ===================================================

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
    assetcat = clean_text(bpy.context.scene.bld_a_nm_props.assetname_cat)
    # print("callback_class",assetcat)
    items = []
    if assetcat == "traf":
        items = assetname_dict["classes_traffic"]  # noqa F405
    else:
        items = assetname_dict["classes_roadside"]  # noqa F405
    return items


def subclass_enums_callback(scene, context):
    # use category to determine which classes to show
    assetcat = clean_text(bpy.context.scene.bld_a_nm_props.assetname_cat)  # noqa F841
    assetclass = clean_text(bpy.context.scene.bld_a_nm_props.assetname_class)  # noqa F841

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


def assemble_name(scene, context, typeflag="prop"):

    lst = []
    if typeflag == "prop":
        lst = [
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_cat)),  # noqa F841
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_class)),  # noqa F841
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_subclass)),  # noqa F841
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_what)),  # noqa F841
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_about)),  # noqa F841
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_size)),  # noqa F841
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_style)),  # noqa F841
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_country)),  # noqa F841
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_numstr)),  # noqa F841
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_condition)),  # noqa F841
        ]
    else:
        lst = [
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_veh_make)),  # noqa F841
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_veh_make_cust)),  # noqa F841
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_veh_model)),  # noqa F841
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_veh_year)),  # noqa F841
        ]

    # prepend mod if needed
    stnm = clean_text(bpy.context.scene.bld_a_nm_props.assetname_set_name)  # noqa F841
    if stnm:
        prt = lst[3]
        lst[3] = "set_" + stnm

        if prt:
            lst.append(prt)

    # update UI with proper enum values
    assetcat = clean_text(bpy.context.scene.bld_a_nm_props.assetname_cat)  # noqa F841
    assetclass = clean_text(bpy.context.scene.bld_a_nm_props.assetname_class)  # noqa F841

    s = "_"
    s = s.join(lst)

    s = s.strip("_")
    # Replace any number of consecutive underscores with a single underscore
    s = re.sub(r"_+", "_", s)  # noqa F841
    return s


##############################
##### PROPERTY CLASSES #######
##############################


class Build_Mat_Name_Properties(PropertyGroup):

    matname_part1: bpy.props.EnumProperty(
        name="part 1",
        items=get_mat1_enums(),  # noqa F405
        description="1. Material Type. This is the material used for rendering in simulation.",
        default=None,
        options={"ANIMATABLE"},
        update=None,
        get=None,
        set=None,
    )

    matname_part2: bpy.props.EnumProperty(
        name="part 2",
        items=get_mat2_enums(),  # noqa F405
        description="hello",
        default=None,
        options={"ANIMATABLE"},
        update=None,
        get=None,
        set=None,
    )

    matname_part3: bpy.props.StringProperty(
        name="part 3",
        description="description",
        default="",
        maxlen=64,
    )

    matname_string: bpy.props.StringProperty(
        name="",
        description="Concatenated name string.",
        default="",
        maxlen=128,
    )


class Build_Asset_Name_Properties(PropertyGroup):

    assetname_type: bpy.props.EnumProperty(
        name="",
        items=type_enums_callback,
        description="Asset Type",
        default=None,
        options={"ANIMATABLE"},
        update=None,
        get=None,
        set=None,
    )

    assetname_veh_make: bpy.props.EnumProperty(
        name="",
        items=veh_make_enums_callback,
        description="Vehicle Make",
        default=None,
        options={"ANIMATABLE"},
        update=None,
        get=None,
        set=None,
    )

    assetname_veh_make_cust: bpy.props.StringProperty(
        name="",
        description=("Type in your custom vehicle make. " + "" + ""),
        default="",
        maxlen=128,
    )

    assetname_veh_model: bpy.props.StringProperty(
        name="",
        description=("What is the vehicle model name? " + "" + ""),
        default="",
        maxlen=128,
    )

    assetname_veh_year: bpy.props.StringProperty(
        name="",
        description=("What year is the vehicle? " + "" + ""),
        default="",
        maxlen=128,
    )

    assetname_cat: bpy.props.EnumProperty(
        name="",
        items=cat_enums_callback,
        description="Category",
        default=None,
        options={"ANIMATABLE"},
        update=None,
        get=None,
        set=None,
    )

    assetname_class: bpy.props.EnumProperty(
        name="",
        items=class_enums_callback,
        description="Class",
        default=None,
        options={"ANIMATABLE"},
        update=None,
        get=None,
        set=None,
    )

    assetname_subclass: bpy.props.EnumProperty(
        name="",
        items=subclass_enums_callback,
        description="Subclass",
        default=None,
        options={"ANIMATABLE"},
        update=None,
        get=None,
        set=None,
    )

    assetname_what: bpy.props.StringProperty(
        name="",
        description=(
            "What is it? Enter the noun that describes the asset. "
            + "Describe what the asset is in the clearest and most succinct way. "
            + "\n\n(e.g. cart, box, wagon, etc. )"
        ),
        default="",
        maxlen=128,
    )

    assetname_about: bpy.props.StringProperty(
        name="",
        description=(
            "Only add a description if it is integral to understanding the asset. "
            + "\n\nChoose descriptors that give meaning to the asset name. "
            + "\n(e.g. enter park as the description where 'bench' is the asset name to make 'bench_park') "
            + ""
            + "\n\nUse a single word or two separated with an underscore. "
            + "\n\nDon't describe materials or colors unless critical"
        ),
        default="",
        maxlen=128,
    )

    assetname_set_name: bpy.props.StringProperty(
        name="",
        description=(
            "\n\nIf the asset is part of a modular set. Enter the name of that set."
            + "\n\nThe Name parameter will then be appended to the end of the name."
        ),
        default="",
        maxlen=128,
    )

    assetname_string: bpy.props.StringProperty(
        name="",
        description="xxx.",
        default="",
        maxlen=128,
    )

    assetname_exists_string: bpy.props.StringProperty(
        name="",
        description="Asset name already exists.",
        default="",
        maxlen=128,
    )

    assetname_numstr: bpy.props.StringProperty(
        name="",
        description="All asset names should include a two digit number unless " + "they are truly one of a kind",
        default="01",
        maxlen=128,
    )

    assetname_size: bpy.props.EnumProperty(
        name="",
        items=size_enums_callback,
        description="Size options are intentially limited. Use when meaningful.",
        default=None,
        options={"ANIMATABLE"},
        update=None,
        get=None,
        set=None,
    )

    assetname_style: bpy.props.EnumProperty(
        name="",
        items=style_enums_callback,
        description="Style",
        default=None,
        options={"ANIMATABLE"},
        update=None,
        get=None,
        set=None,
    )

    assetname_condition: bpy.props.EnumProperty(
        name="",
        items=condition_enums_callback,
        description="Condition",
        default=None,
        options={"ANIMATABLE"},
        update=None,
        get=None,
        set=None,
    )
    assetname_country: bpy.props.EnumProperty(
        name="",
        items=country_enums_callback,
        description="Country",
        default=None,
        options={"ANIMATABLE"},
        update=None,
        get=None,
        set=None,
    )

    assetname_toml_filepath: bpy.props.StringProperty(
        name="",
        description="xxx",
        default="",
        maxlen=128,
    )
