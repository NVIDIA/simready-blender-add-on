# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import math
import re
from os.path import dirname, join, normpath, realpath, split

import bpy
import bpy.utils.previews
import mathutils


def LoadCoreIcons():
    # icons
    def get_icons_directory():
        head, tail = split(dirname(__file__))
        icons_directory = join(head, "resource", "icons")
        return icons_directory  # retrieve icons

    core_icons = {}

    core_icons["main"] = bpy.utils.previews.new()
    core_icons_directory = get_icons_directory()
    # print(core_icons_directory)
    core_icons["main"].load("OMNIBLEND", join(core_icons_directory, "BlenderOMNI.png"), "IMAGE")
    core_icons["main"].load("OMNI", join(core_icons_directory, "ICON.png"), "IMAGE")
    core_icons["main"].load("TOOL_REF_FIGURE", join(core_icons_directory, "TOOL_REF_FIGURE.png"), "IMAGE")
    core_icons["main"].load("TOOL_REF_FIGURE2", join(core_icons_directory, "TOOL_REF_FIGURE2.png"), "IMAGE")
    core_icons["main"].load("TOOL_MEASURE", join(core_icons_directory, "CORE_icons_measure_box.png"), "IMAGE")
    core_icons["main"].load("TOOL_MEASURE2", join(core_icons_directory, "TOOL_MEASURE2.png"), "IMAGE")
    core_icons["main"].load("UNIFY_NAMES", join(core_icons_directory, "UNIFY_NAMES.png"), "IMAGE")
    core_icons["main"].load("UNIFY_MATS", join(core_icons_directory, "UNIFY_MATS.png"), "IMAGE")
    core_icons["main"].load("WHEEL_ACROSS", join(core_icons_directory, "WHEEL_ACROSS.png"), "IMAGE")
    core_icons["main"].load("WHEEL_ACROSS_2", join(core_icons_directory, "WHEEL_ACROSS_2.png"), "IMAGE")
    core_icons["main"].load("WHEEL_BACK", join(core_icons_directory, "WHEEL_BACK.png"), "IMAGE")
    core_icons["main"].load("WHEEL_BACK_2", join(core_icons_directory, "WHEEL_BACK_2.png"), "IMAGE")
    core_icons["main"].load("WHEELS_CENTER", join(core_icons_directory, "WHEELS_CENTER.png"), "IMAGE")
    core_icons["main"].load("AXLES_CENTER", join(core_icons_directory, "AXLES_CENTER.png"), "IMAGE")
    core_icons["main"].load("AXLES_CENTER_2", join(core_icons_directory, "AXLES_CENTER_2.png"), "IMAGE")
    core_icons["main"].load("LOCATOR", join(core_icons_directory, "LOCATOR.png"), "IMAGE")
    core_icons["main"].load("CLEAN_AND_OFFSET", join(core_icons_directory, "CLEAN_AND_OFFSET.png"), "IMAGE")
    core_icons["main"].load("PLANAR_SURFACE", join(core_icons_directory, "PLANAR_SURFACE.png"), "IMAGE")
    core_icons["main"].load("PLATFORM1", join(core_icons_directory, "CORE_icons_prop_platform.png"), "IMAGE")
    core_icons["main"].load("PLATFORM2", join(core_icons_directory, "CORE_icons_veh_platform.png"), "IMAGE")
    core_icons["main"].load("GLASS_THICK", join(core_icons_directory, "GLASS_THICK.png"), "IMAGE")
    core_icons["main"].load("LOCATORS_RIG", join(core_icons_directory, "LOCATORS_RIG.png"), "IMAGE")
    core_icons["main"].load("CONVERT_SIMPBR", join(core_icons_directory, "CORE_icons_convert_simpbr.png"), "IMAGE")
    core_icons["main"].load(
        "ADD_SIMPBR_TRANSLUCENT", join(core_icons_directory, "CORE_icons_add_simpbr_trans.png"), "IMAGE"
    )
    core_icons["main"].load("ADD_SIMPBR", join(core_icons_directory, "CORE_icons_add_simpbr.png"), "IMAGE")
    bpy.types.WindowManager.custom_icon_previews = core_icons
    return


def CORE_get_shading_mode():

    mode = None

    for spc in bpy.context.screen.areas:
        if spc.type == "VIEW_3D":
            mode = spc.spaces[0].shading.type
            break  # VIEW_3D space found
    return mode


def CORE_set_shading_mode(mode="MATERIAL"):

    for spc in bpy.context.screen.areas:
        if spc.type == "VIEW_3D":
            spc.spaces[0].shading.type = mode
            break  # VIEW_3D space found


def FindCenterOfSelection(whls, pintoz=False, ctraxles=False):
    # find center of selected objects
    # setup

    # get selection
    count = len(whls)
    C = bpy.context
    D = bpy.data = bpy.context
    D = bpy.data  # noqa F841

    if whls:
        # calculate center location
        loc = mathutils.Vector((0.0, 0.0, 0.0))
        for each in whls:
            # loc += each.location
            loc += each.matrix_world.to_translation()
        loc /= count

        # center between axles if needed
        if ctraxles:
            # going to make an assumption that 1cm is enough accuracy to be same axle
            yrnd_lst = []
            ypos_lst = []
            for each in whls:
                yrnd_lst.append(round(each.matrix_world.to_translation().y, 2))
                ypos_lst.append(each.matrix_world.to_translation().y)
            yrnd_set = set(yrnd_lst)
            ypos_set = set(ypos_lst)
            print("yrnd_set", yrnd_set)
            if len(yrnd_set) == 2:
                # older method wanted an odd number of wheels:if (len(whls) % 2 ) != 0 and len(yset)==2:
                loc.y = sum(ypos_set) / len(ypos_set)
            else:
                pass  # TODO: give user notice about why this didn't work

        # pint to ground plane if needed
        if pintoz:
            loc.z = 0.0

        # create empty at wheel center
        bpy.ops.object.empty_add(type="ARROWS")

        C.active_object.location = loc
        C.active_object.name = "sel_center"

        return {"FINISHED"}
    else:
        print("nothing selected")
        return {"CANCELLED"}


def DuplicateWheels(objs, method=2):
    """
    1: duplicate across
    2: duplicate rearward
    """
    C = bpy.context
    D = bpy.data  # noqa F841

    if objs:
        # set increment for naming items
        inc = 1
        # remove all items from selection set
        for each in objs:
            each.select_set(False)
        # create a list of new objects to select at end
        obj_new = []
        for obj in objs:
            C.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.duplicate(linked=False)
            obj_copy = C.active_object

            # An alternate method for doing this using copy
            # I was not able to maintain the hierarchy of objects using this method
            # obj_data = obj.data.copy()
            # obj_parent = obj.parent
            # obj_copy = obj.copy()
            # obj_copy.data = obj_data
            # obj_copy.parent = obj_parent
            # bpy.context.collection.objects.link(obj_copy)

            C.view_layer.objects.active = obj_copy
            bpy.ops.object.make_single_user(object=True, obdata=True, material=False, animation=True)

            if method == 1:
                obj_copy.location.x = -obj.location.x
                obj_copy.rotation_euler = [0, 0, math.radians(180)]
            else:
                if obj.location.y > 0:
                    obj_copy.location.y = obj.location.y + obj.location.y
                else:
                    obj_copy.location.y = -obj.location.y
                inc = 2

            namesplit = obj.name.split("_")
            print(namesplit[-1].isdigit())
            if namesplit[-1].isdigit():
                num = str(int(namesplit[-1]) + inc)
                obj_copy.name = obj.name.strip((namesplit[-1])) + num
                obj_copy.data.name = obj_copy.name

            # rename data to match new object name
            obj_copy.data.name = obj_copy.name
            # remove current objects from selection
            obj.select_set(False)
            obj_copy.select_set(False)
            obj_new.append(obj_copy)
        for each in obj_new:
            each.select_set(True)
        return {"FINISHED"}
    else:
        return {"CANCELLED"}


def DataNameToObjectName(objs):
    if objs:
        for each in objs:
            each.data.name = each.name
        return {"FINISHED"}
    else:
        return {"CANCELLED"}


def NVCAT_UnifyMaterials(objs):
    if objs:
        matnames = []
        # gather material names in scene
        for ob in bpy.context.scene.objects:
            bpy.context.view_layer.objects.active = ob
            if bpy.context.object.type == "MESH":
                if ob.data.materials:
                    for mat in ob.material_slots:
                        matnames.append(mat.name)
        # work through materials in selected objects
        for o in objs:
            if bpy.context.object.type == "MESH":
                mats = o.data.materials
                if mats:
                    for i, m in enumerate(mats):
                        clean_name = re.sub(r"[0-9.]", "", m.name)
                        if clean_name in matnames:
                            mats[i] = bpy.data.materials[clean_name]
                            o.material_slots[i].material.name = clean_name  # read only
        return {"FINISHED"}
    else:
        return {"CANCELLED"}


def CORE_ReturnAssetLibraryPath(file_name):
    script_path = realpath(__file__)
    dir_path = normpath(dirname(script_path))
    file_path = join(dir_path, "model/core_library", file_name)
    return file_path


def CORE_ImportLibraryAsset(file_name, assetname="undefined", do_rotate=False):
    """Import an asset from the CORE library"""

    file_path = CORE_ReturnAssetLibraryPath(file_name)
    if bpy.data:
        if "CORE_library_objects" not in bpy.data.collections:
            core_coll = bpy.data.collections.new("CORE_library_objects")
            bpy.context.scene.collection.children.link(core_coll)

        core_coll = bpy.data.collections["CORE_library_objects"]

    # print("core_coll",core_coll)

    if assetname != "undefined":
        # import by name
        with bpy.data.libraries.load(str(file_path), link=True) as (data_from, data_to):
            if assetname in data_from.objects:  # Check if it's an object
                print(f"{assetname} is an object.")
                data_to.objects = [assetname]
            elif assetname in data_from.collections:  # Check if it's a collection
                print(f"{assetname} is a collection.")
                data_to.collections = [assetname]
            else:
                print(f"{assetname} not found in objects or collections.")
    else:
        # import all
        with bpy.data.libraries.load(str(file_path)) as (data_from, data_to):
            data_to.objects = data_from.objects

    # link new objects TODO: fix this too
    for ob in data_to.objects:
        core_coll.objects.link(ob)

    for co in data_to.collections:
        core_coll.children.link(co)

    collection = bpy.data.collections.get("CORE_library_objects")

    if collection and do_rotate:
        # Select all empties and meshes in the collection
        for obj in collection.objects:
            if obj.type in {"EMPTY", "MESH"}:
                obj.select_set(True)
            else:
                obj.select_set(False)

        bpy.context.scene.tool_settings.transform_pivot_point = "CURSOR"
        bpy.ops.transform.rotate(value=math.radians(-90), orient_axis="Z")

    # return
    return {"FINISHED"}


def CORE_PropOrient():
    CORE_ImportLibraryAsset("core_reference_library.blend", "OrientationProps")


def CORE_ReferenceFigure():
    CORE_ImportLibraryAsset("core_reference_library.blend", "scale_ref_02_t_pose_veh_orient")
    return


def CORE_ReferenceFigure_prop():
    CORE_ImportLibraryAsset("core_reference_library.blend", "scale_ref_02_t_pose_prop_orient")


def CORE_VehiclePlatform():
    CORE_ImportLibraryAsset("core_reference_library.blend", "platform_vehicle_round_01")


def CORE_LocatorsRig():
    CORE_ImportLibraryAsset("core_vehicle_locators.blend")


def CORE_LocatorsRigProp():
    CORE_ImportLibraryAsset("core_vehicle_locators.blend", "undefined", True)


def CORE_GetMaterialsByName(objs, terms):

    print("running_NVCAT_TestMaterials")
    if objs:
        matnames = []
        matdata = []

        terms = terms.lower().split(" ")
        if len(terms) == 1:
            terms = list(terms)
        print(terms)
        # gather material names in scene
        for ob in objs:
            bpy.context.view_layer.objects.active = ob
            if bpy.context.object.type == "MESH":
                if ob.data.materials:
                    for mat in ob.material_slots:

                        flag = True
                        for term in terms:
                            print("term:", term)
                            if term not in mat.name.lower():
                                flag = False
                        # We have found a material that matches our search criteria
                        if flag:
                            print("currentname:", mat.name)
                            # add current material name to matnames if unique
                            if mat.name not in matnames:
                                matnames.append(mat.name)

                            # add data to matdata
                            if mat not in matdata:
                                matdata.append([ob.name, mat, mat.name])
        # work through materials in selected objects
        """
        for o in objs:
            if bpy.context.object.type == 'MESH':
                mats = o.data.materials
                if mats:
                    for i,m in enumerate(mats):
                        clean_name = re.sub(r'[0-9.]', '', m.name )
                        if clean_name in matnames:
                            mats[i] = bpy.data.materials[clean_name]
                            o.material_slots[i].material.name = clean_name # read only
        """
        return matnames, matdata
    else:
        return []


def CORE_GetMaterialsFromObjects(objs):

    if objs:
        matnames = []
        matdata = []

        # gather material names in scene
        for ob in objs:
            bpy.context.view_layer.objects.active = ob
            if bpy.context.object.type == "MESH":
                if ob.data.materials:
                    for mat in ob.material_slots:

                        if mat.name not in matnames:
                            matnames.append(mat.name)

                        # add data to matdata
                        if mat not in matdata:
                            matdata.append([ob.name, mat, mat.name])

        return matnames, matdata
    else:
        return []


def CORE_HighlightMaterials(objs, matdata, blinkstate=1):
    # Create the pink material if it doesn't exist

    highlight_color = None

    mode_user = CORE_get_shading_mode()
    if mode_user != "MATERIAL":
        CORE_set_shading_mode()

    # Make sure blinky material is present
    if "CORE_highlight" not in bpy.data.materials:
        core_highlight = bpy.data.materials.new(name="CORE_highlight")
        core_highlight.use_nodes = True
        highlight_color = (0, 1.0, 0.0, 1)
        core_highlight.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = highlight_color

    # Make sure blinky material is present
    if "CORE_black" not in bpy.data.materials:
        core_black = bpy.data.materials.new(name="CORE_black")
        core_black.use_nodes = True
        core_black.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1)  # Pink

    # If blinkstate is true then let's swap current materials for something flashy
    if blinkstate:
        for mat in matdata:
            mat[1].material = bpy.data.materials["CORE_highlight"]

        blinkval = True  # noqa F841

        def blink_interval():
            # highlight_color = (0.0, 0.0, 0.0, 1)
            # blinkval = not blinkval
            # CORE_HighlightMaterials(objs, matdata, 0)
            # print ('blink')
            # return 1.0
            pass

        def in_5_seconds():
            CORE_HighlightMaterials(objs, matdata, 0)
            CORE_set_shading_mode(mode_user)

            # CORE_set_shading_mode(mode)

        bpy.app.timers.register(in_5_seconds, first_interval=0.25)
        # bpy.app.timers.register(blink_interval,first_interval=1)

    else:
        # restore the original materials
        for mat in matdata:
            mat[1].material = bpy.data.materials[mat[2]]


def CORE_LocatorsAtOrigins(objs):
    if objs:
        for obj in objs:
            bpy.ops.object.empty_add(type="PLAIN_AXES")
            empty = bpy.context.active_object

            empty.location = obj.matrix_world.to_translation()
            empty.rotation_euler = obj.rotation_euler
            empty.scale = obj.scale
            empty.name = "placeholder_" + obj.name
        return {"FINISHED"}
    else:
        return {"CANCELLED"}


def CORE_ReturnListOfWatertightMeshes(objs):
    watertight_objects = []

    for obj in objs:
        if obj.type == "MESH":
            if obj.visible_get():
                bpy.context.view_layer.objects.active = obj
                obj.data.update()

                is_watertight = True

                # Create a dictionary to hold edge face counts
                edge_face_count = {}
                for poly in obj.data.polygons:
                    for edge_key in poly.edge_keys:
                        edge_face_count[edge_key] = edge_face_count.get(edge_key, 0) + 1

                # Check for watertightness
                for count in edge_face_count.values():
                    # If any edge is part of more or less than 2 faces, the mesh is not watertight
                    if count != 2:
                        is_watertight = False
                        break

                # If object is watertight, add it to the list
                if is_watertight:
                    watertight_objects.append(obj)

    print("watertights:", watertight_objects)
    return watertight_objects
