# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy
from bpy.types import Operator

from ..library import *  # noqa F403
from ..resource.simready_standards import *  # noqa F403


# PROPERTIES
class ASSET_panel_common:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    bl_options = {"DEFAULT_CLOSED"}


# ASSET PROPERTIES
class Naming_Properties(bpy.types.PropertyGroup):

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

    namestring: bpy.props.StringProperty(
        name="",
        description="Concatenated name string.",
        default="",
        maxlen=128,
    )


# 'CHECK VEHICLE NAMES' OPERATOR ###
class CORE_OT_valname_veh_parts(Operator):
    bl_label = "Veh Parts"
    bl_description = ""
    bl_idname = "nvcat.valname_veh_parts"

    def execute(self, context):
        CORE_Create_Measure_Box()  # noqa F405
        return {"FINISHED"}


class CORE_OT_valname_veh_mats(Operator):
    bl_label = "Veh Mats"
    bl_description = ""
    bl_idname = "nvcat.valname_veh_mats"

    def execute(self, context):
        CORE_Create_Measure_Box()  # noqa F405
        return {"FINISHED"}


class CORE_OT_valname_prop_parts(Operator):
    bl_label = "Prop Parts"
    bl_description = ""
    bl_idname = "nvcat.valname_prop_parts"

    def execute(self, context):
        CORE_Create_Measure_Box()  # noqa F405
        return {"FINISHED"}


class CORE_OT_valname_prop_mats(Operator):
    bl_label = "Prop Mats"
    bl_description = ""
    bl_idname = "nvcat.valname_prop_mats"

    def execute(self, context):
        CORE_Create_Measure_Box()  # noqa F405
        return {"FINISHED"}


class CORE_OT_matname_copy(Operator):
    bl_label = "Copy Name"
    bl_description = ""
    bl_idname = "nvcat.copy_namestring"

    matname_part1: bpy.props.EnumProperty(items=get_mat1_enums())  # noqa F405
    matname_part2: bpy.props.EnumProperty(items=get_mat2_enums())  # noqa F405
    matname_part3: bpy.props.StringProperty()
    namestring: bpy.props.StringProperty()

    def execute(self, context):
        s1 = bpy.context.scene.name_props.matname_part1
        s2 = bpy.context.scene.name_props.matname_part2
        s3 = bpy.context.scene.name_props.matname_part3
        s3 = clean_text(s3)  # noqa F405
        s4 = [s1, s2, s3]
        self.namestring = "__".join(s4)  # noqa F841
        copy_string(self.namestring)  # noqa F405
        NVCAT_display_message(  # noqa F405
            [
                self.namestring,
            ],
            title="Name Copied",
        )
        return {"FINISHED"}


class CORE_PT_Sub_Naming(ASSET_panel_common, bpy.types.Panel):
    bl_idname = "CORE_PT_Sub_Naming"
    bl_label = "Naming Tools"

    matname_part1: bpy.props.EnumProperty()

    def draw(self, context):
        layout = self.layout  # noqa F841
        col1 = self.layout.column(align=True)
        box = col1.box()
        row1 = box.row(align=True)
        row1.label(text="Validate Names:")
        # row1.separator(factor = -8)
        row2 = box.row(align=True)
        row2.operator(CORE_OT_valname_veh_parts.bl_idname)
        row2.operator(CORE_OT_valname_veh_mats.bl_idname)

        row3 = box.row(align=True)
        row3.operator(CORE_OT_valname_prop_parts.bl_idname)
        row3.operator(CORE_OT_valname_prop_mats.bl_idname)

        col1.separator(factor=1)
        box2 = col1.box()
        box2.label(text="Generate Material Name:")
        box2.prop(bpy.context.scene.name_props, "matname_part1")
        box2.prop(bpy.context.scene.name_props, "matname_part2")
        box2.prop(bpy.context.scene.name_props, "matname_part3")
        # box2.prop(bpy.types.Object, 'nvcat_global_mat_namestring')

        s1 = bpy.context.scene.name_props.matname_part1
        s2 = bpy.context.scene.name_props.matname_part2
        s3 = bpy.context.scene.name_props.matname_part3
        s3 = clean_text(s3)  # noqa F405
        s = [s1, s2, s3]
        s = "__".join(s)
        box2.label(text=s)

        box2.operator(CORE_OT_matname_copy.bl_idname)
        # row4.enabled = False
