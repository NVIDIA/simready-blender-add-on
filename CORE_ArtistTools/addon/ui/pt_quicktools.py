# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import re
from typing import List

import bpy
from bpy.types import Operator, Panel

from ..library import *  # noqa F403
from ..library.material_utils import (
    append_template_mats,
    get_all_old_attrs,
    get_all_used_mats,
    replace_with_simpbr,
)
from ..resource.core_blender_libs import *  # noqa F403
from ..resource.simready_standards import *  # noqa F403


def assemble_name(scene, context, typeflag="prop"):

    lst = []
    if typeflag == "prop":
        lst = [
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_cat)),  # noqa F405
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_class)),  # noqa F405
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_subclass)),  # noqa F405
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_what)),  # noqa F405
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_about)),  # noqa F405
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_size)),  # noqa F405
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_style)),  # noqa F405
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_country)),  # noqa F405
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_numstr)),  # noqa F405
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_condition)),  # noqa F405
        ]
    else:
        lst = [
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_veh_make)),  # noqa F405
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_veh_make_cust)),  # noqa F405
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_veh_model)),  # noqa F405
            (clean_text(bpy.context.scene.bld_a_nm_props.assetname_veh_year)),  # noqa F405
        ]

    # prepend mod if needed
    stnm = clean_text(bpy.context.scene.bld_a_nm_props.assetname_set_name)  # noqa F405
    if stnm:
        prt = lst[3]
        lst[3] = "set_" + stnm

        if prt:
            lst.append(prt)

    # update UI with proper enum values
    assetcat = clean_text(bpy.context.scene.bld_a_nm_props.assetname_cat)  # noqa F405 # noqa F841
    assetclass = clean_text(bpy.context.scene.bld_a_nm_props.assetname_class)  # noqa F405 # noqa F841

    s = "_"
    s = s.join(lst)

    s = s.strip("_")
    # Replace any number of consecutive underscores with a single underscore
    s = re.sub(r"_+", "_", s)  # noqa F405
    return s


# POP UP MESSAGE
class DoneConversionPopup(bpy.types.Operator):
    bl_idname = "wm.popup_conversion"
    bl_label = "Conversion Completed"

    def draw(self, context):
        layout = self.layout
        layout.label(text="✅ Conversion completed successfully!")

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=250)


# TOOLS MISC PROPERTIES
class Asset_Properties(bpy.types.PropertyGroup):
    pass


# =====================
# OPERATORS: ACTIONS
# =====================


class CORE_OT_reference_figure(Operator):
    bl_label = "reference_figure"
    bl_description = "reference figure for veh platform (Y-fwd)"
    bl_idname = "nvcat.reference_figure"

    def execute(self, _context):
        CORE_ReferenceFigure()  # noqa F405
        return {"FINISHED"}


class CORE_OT_reference_figure_prop(Operator):
    bl_label = "reference_figure_prop"
    bl_description = "reference figure for prop platform (X-fwd)"
    bl_idname = "nvcat.reference_figure_prop"

    def execute(self, _context):
        CORE_ReferenceFigure_prop()  # noqa F405
        return {"FINISHED"}


class CORE_OT_vehicle_platform(Operator):
    bl_label = "vehicle_platform"
    bl_description = "orientation platform for vehicle scene"
    bl_idname = "nvcat.vehicle_platform"

    def execute(self, _context):
        CORE_VehiclePlatform()  # noqa F405
        return {"FINISHED"}


class CORE_OT_prop_platform(Operator):
    bl_label = "prop_platform"
    bl_desciption = "orientation widgets for prop scene"
    bl_idname = "nvcat.prop_platform"

    def execute(self, _context):
        CORE_PropOrient()  # noqa F405
        return {"FINISHED"}


class CORE_OT_add_locators(Operator):
    bl_label = "add_locators"
    bl_description = ""
    bl_idname = "nvcat.add_locators"

    def execute(self, _context):
        CORE_LocatorsAtOrigins(bpy.context.selected_objects)  # noqa F405
        return {"FINISHED"}


class CORE_OT_mesh_to_locators(Operator):
    bl_label = "mesh to locators"
    bl_description = "Turn selected meshes into locators"
    bl_idname = "nvcat.mesh_to_locators"

    def execute(self, context):
        print("RUNNING MESH -> LOCATORS")
        if bpy.context.selected_objects:
            for obj in bpy.context.selected_objects:
                if obj.type == "MESH":
                    location = obj.location
                    rotation = obj.rotation_euler
                    scale = obj.scale

                    obj_name = obj.name

                    bpy.ops.object.empty_add(type="PLAIN_AXES", location=location)

                    empty_obj = bpy.context.active_object
                    empty_obj.rotation_euler = rotation
                    empty_obj.scale = scale
                    empty_obj.name = obj_name

                    # remove the mesh
                    bpy.data.objects.remove(obj)
                else:
                    NVCAT_display_message(  # noqa F405
                        ["You don't have any meshes selected."], title="MESH TO LOCATORS:", icon="ERROR"
                    )
            return {"FINISHED"}
        else:
            NVCAT_no_sel_message()  # noqa F405
            return {"CANCELLED"}


class CORE_OT_convert_simpbr(Operator):
    bl_label = "convert_simpbr"
    bl_description = "convert all materials to simpbr or simpbr_translucent"
    bl_idname = "nvcat.convert_simpbr"

    def execute(self, context):
        materials = get_all_used_mats()  # noqa F405
        store_old_attrs = get_all_old_attrs(materials)  # noqa F405
        template_materials: List[bpy.types.Material] = append_template_mats()  # noqa F405
        replace_with_simpbr(template_materials, store_old_attrs)  # noqa F405
        bpy.ops.wm.popup_conversion("INVOKE_DEFAULT")  # noqa F405
        return {"FINISHED"}


# TODO: Add per slot conversion(s)
# Will keep these for now, but they are not used
class CORE_OT_add_simpbr(Operator):
    bl_label = "add_simpbr"
    bl_description = "convert to simpbr"
    bl_idname = "nvcat.add_simpbr"

    def execute(self, context):
        pass


class CORE_OT_add_simpbr_translucent(Operator):
    bl_label = "add_simpbr_translucent"
    bl_description = "convert to simpbr_translucent"
    bl_idname = "nvcat.add_simpbr_translucent"

    def execute(self, context):
        pass


class CORE_OT_matname_to_clip(Operator):
    bl_label = "Copy Name"
    bl_description = ""
    bl_idname = "nvcat.matname_to_clip"

    matname_part1: bpy.props.EnumProperty(items=get_mat1_enums())  # noqa F405
    matname_part2: bpy.props.EnumProperty(items=get_mat2_enums())  # noqa F405
    matname_part3: bpy.props.StringProperty()
    namestring: bpy.props.StringProperty()

    def execute(self, context):
        s1 = bpy.context.scene.bld_matname_props.matname_part1  # noqa F405
        s2 = bpy.context.scene.bld_matname_props.matname_part2  # noqa F405
        s3 = bpy.context.scene.bld_matname_props.matname_part3  # noqa F405
        s3 = clean_text(s3)  # noqa F405
        s4 = [s1, s2, s3]
        self.namestring = "__".join(s4)  # noqa F405
        copy_string(self.namestring)  # noqa F405
        NVCAT_display_message(  # noqa F405
            [
                self.namestring,
            ],
            title="Name Copied",
        )
        return {"FINISHED"}


class CORE_OT_objname_copy(Operator):
    bl_label = ""
    bl_description = (
        "Copy the generated name into the clipboard."
        + "\n\nWhen you click the button, a dialog will also display the full asset name "
        + "which is handy when the name is truncated in the Blender panel which will happen with"
        + "long names."
    )
    bl_idname = "nvcat.copy_namestring"

    def execute(self, context):
        typeflag = bpy.context.scene.bld_a_nm_props.assetname_type
        s = assemble_name(self, context, typeflag)  # noqa F405
        copy_string(s)  # noqa F405
        NVCAT_display_message(  # noqa F405
            [
                s,
            ],
            title="Name Copied",
        )
        return {"FINISHED"}


# ==================
# PANELS: UI LAYOUT
# ==================


class CORE_quicktools_common:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"


class CORE_PT_Build_Mat_Name(CORE_quicktools_common, Panel):
    bl_idname = "CORE_PT_Build_Mat_Name"
    bl_label = "Create Material Names"
    bl_parent_id = "CORE_PT_Tools"  # SUB PANEL
    bl_options = {"DEFAULT_CLOSED"}

    matname_part1: bpy.props.EnumProperty()

    def draw(self, context):

        col1 = self.layout.column(align=True)
        col1.prop(bpy.context.scene.bld_matname_props, "matname_part1")
        col1.prop(bpy.context.scene.bld_matname_props, "matname_part2")
        col1.prop(bpy.context.scene.bld_matname_props, "matname_part3")
        # box2.prop(bpy.types.Object, 'nvcat_global_mat_namestring')

        s1 = bpy.context.scene.bld_matname_props.matname_part1
        s2 = bpy.context.scene.bld_matname_props.matname_part2
        s3 = bpy.context.scene.bld_matname_props.matname_part3
        s3 = clean_text(s3)  # noqa F405
        s = [s1, s2, s3]
        s = "__".join(s)

        col1.separator(factor=0.5)
        row = col1.row()
        col1.separator(factor=0.5)
        row.label(text=s)

        row2 = col1.row()
        row2.operator(CORE_OT_matname_to_clip.bl_idname)
        row2.enabled = s3 != ""


class CORE_PT_Build_Asset_Name(CORE_quicktools_common, Panel):
    bl_idname = "CORE_PT_Build_Asset_Name"
    bl_label = "Build Asset Name"
    bl_parent_id = "CORE_PT_Tools"  # SUB PANEL
    bl_options = {"DEFAULT_CLOSED"}

    def draw(
        self,
        context,
    ):
        col1 = self.layout.column(align=True)

        # what type of flag, reset this value to reconfigure UI
        typeflag = bpy.context.scene.bld_a_nm_props.assetname_type
        iscustomflag = bpy.context.scene.bld_a_nm_props.assetname_veh_make == "!"
        issetflag = clean_text(bpy.context.scene.bld_a_nm_props.assetname_set_name) != ""  # noqa F405

        row1a = col1.row(align=True)
        split = row1a.split(factor=0.4)
        split.label(text="Asset Type")
        split.prop(bpy.context.scene.bld_a_nm_props, "assetname_type")
        col1.separator(factor=1.5)

        if typeflag == "prop":
            row_cat = col1.row(align=True)
            split = row_cat.split(factor=0.4)
            split.label(text="Category")
            split.prop(bpy.context.scene.bld_a_nm_props, "assetname_cat")
            row_class = col1.row(align=True)
            split1 = row_class.split(factor=0.4)
            split1.label(text="Class")
            split1.prop(bpy.context.scene.bld_a_nm_props, "assetname_class")
            row_name = col1.row(align=True)
            split1 = row_name.split(factor=0.4)
            if not issetflag:
                split1.label(text="Name (noun)")
            else:
                split1.label(text="Set => PartName")
            split1.prop(bpy.context.scene.bld_a_nm_props, "assetname_what")
            row_numstr = col1.row(align=True)
            split1 = row_numstr.split(factor=0.4)
            split1.label(text="Number")
            split1.prop(bpy.context.scene.bld_a_nm_props, "assetname_numstr")

            col1.separator(factor=1.5)
            col1.label(text="----------------- optional -----------------")
            col1.separator(factor=1.5)

            row_about = col1.row(align=True)
            split1 = row_about.split(factor=0.4)
            split1.label(text="Description (adj)")
            split1.prop(bpy.context.scene.bld_a_nm_props, "assetname_about")

            row_setname = col1.row(align=True)
            split1 = row_setname.split(factor=0.4)
            split1.label(text="Set: Name")
            split1.prop(bpy.context.scene.bld_a_nm_props, "assetname_set_name")

            row_size = col1.row(align=True)
            split1 = row_size.split(factor=0.4)
            split1.label(text="Size")
            split1.prop(bpy.context.scene.bld_a_nm_props, "assetname_size")

            row_style = col1.row(align=True)
            split1 = row_style.split(factor=0.4)
            split1.label(text="Style")
            split1.prop(bpy.context.scene.bld_a_nm_props, "assetname_style")

            row_condition = col1.row(align=True)
            split1 = row_condition.split(factor=0.4)
            split1.label(text="Condition")
            split1.prop(bpy.context.scene.bld_a_nm_props, "assetname_condition")

            row_region = col1.row(align=True)
            split1 = row_region.split(factor=0.4)
            split1.label(text="Region")
            split1.prop(bpy.context.scene.bld_a_nm_props, "assetname_country")

        if typeflag == "prop" and bpy.context.scene.bld_a_nm_props.assetname_subclass != "":
            row3 = col1.row(align=True)
            split1 = row3.split(factor=0.4)
            split1.label(text="Sublass")
            split1.prop(bpy.context.scene.bld_a_nm_props, "assetname_subclass")

        if typeflag == "vehicle":
            row_veh_make = col1.row(align=True)
            split1 = row_veh_make.split(factor=0.4)
            split1.label(text="Make")
            split1.prop(bpy.context.scene.bld_a_nm_props, "assetname_veh_make")

            # looking for make of type custom. "!" is used as its value is stripped on assembly
            if iscustomflag:
                row_veh_make_cust = col1.row(align=True)
                split1 = row_veh_make_cust.split(factor=0.4)
                split1.label(text="----->")
                split1.prop(bpy.context.scene.bld_a_nm_props, "assetname_veh_make_cust")
                col1.separator(factor=1.5)

            row_veh_model = col1.row(align=True)
            split1 = row_veh_model.split(factor=0.4)
            split1.label(text="Model")
            split1.prop(bpy.context.scene.bld_a_nm_props, "assetname_veh_model")

            row_veh_year = col1.row(align=True)
            split1 = row_veh_year.split(factor=0.4)
            split1.label(text="Year")
            split1.prop(bpy.context.scene.bld_a_nm_props, "assetname_veh_year")

        col1.separator(factor=1.7)

        # assemble name
        row_assetname = col1.row(align=True)

        row_assetname.label(icon="DOT", text=assemble_name(self, context, typeflag))
        row_assetname.operator(CORE_OT_objname_copy.bl_idname, icon="COPYDOWN")

        # research result
        if True:
            row_research = col1.row(align=True)
            row_research.label(icon="KEYTYPE_JITTER_VEC", text="(name is unique)")

        col1.separator(factor=1.7)

        row_copy2 = col1.row(align=True)
        row_copy2.operator(CORE_OT_objname_copy.bl_idname, text="source path")
        row_copy2.operator(CORE_OT_objname_copy.bl_idname, text="dest. path")

        row12 = col1.row(align=True)
        op = row12.operator(
            "wm.url_open",
            text="abbrv",
            icon="URL",
            text_ctxt="haloooo",
        )
        op.url = "https://www.abbreviations.com"

        col1.separator(factor=1.7)


class SRVIZ_PT_intersections_panel(CORE_quicktools_common, Panel):
    bl_label = "Debug Mesh Intersections"
    bl_idname = "SRVIZ_PT_intersections_panel"
    bl_parent_id = "CORE_PT_Tools"  # SUB PANEL
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text="Multi-Object Intersections")
        col.label(text="Select all meshes you want to check for intersections.", icon="INFO")
        col.label(text="Note: Sometimes you need to run this operation twice.", icon="INFO")


class CORE_PT_Tools_Misc(CORE_quicktools_common, Panel):
    bl_idname = "CORE_PT_Tools"
    bl_label = "Quick Tools"
    bl_options = {"DEFAULT_CLOSED"}

    core_icons = bpy.context.window_manager.custom_icon_previews["main"]

    def draw(self, context):
        layout = self.layout

        box = layout.column(align=True)
        box.scale_x = 1.2
        box.scale_y = 1.5
        line_01 = box.row(align=True)
        line_01.operator(
            CORE_OT_prop_platform.bl_idname, text="Prop Platform", icon_value=self.core_icons["PLATFORM1"].icon_id
        )
        line_02 = box.row(align=True)
        line_02.operator(CORE_OT_reference_figure_prop.bl_idname, text="Ref Figure Prop", icon="OUTLINER_OB_ARMATURE")

        box = layout.column(align=True)
        line_01 = box.row(align=True)
        line_01.scale_x = 1.2
        line_01.scale_y = 1.5
        line_01.operator(
            CORE_OT_vehicle_platform.bl_idname, text="Vehicle Platform", icon_value=self.core_icons["PLATFORM2"].icon_id
        )
        line_02 = box.row(align=True)
        line_02.operator(
            CORE_OT_reference_figure.bl_idname,
            text="Ref Figure Vehicle",
            icon_value=self.core_icons["TOOL_REF_FIGURE2"].icon_id,
        )
