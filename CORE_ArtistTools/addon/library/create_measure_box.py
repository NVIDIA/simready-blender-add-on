# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

# measure tool with lots of other junk

import math

import bmesh
import bpy
import mathutils

from ..library import *  # noqa F403


def CORE_Create_Measure_Box():

    C = bpy.context  # noqa F841
    D = bpy.data  # noqa F841
    objs = C.selected_objects  # noqa F841
    obj = None  # noqa F841

    val = check_user_sel(objs)  # noqa F821

    print("val:", val)

    def MakeAStick(
        r: float, l: float, loc: tuple[float, float, float], rot: tuple[float, float, float]  # noqa F741
    ) -> bpy.types.Object:
        bpy.ops.mesh.primitive_cylinder_add(
            radius=r, depth=l, enter_editmode=False, align="WORLD", location=loc, scale=(1, 1, 1)
        )
        stick = C.active_object
        stick.rotation_euler = rot
        print("rot:", rot)
        return stick

    def GimmeText(
        str: str, loc: tuple[float, float, float], rot: tuple[float, float, float], ctr: bool = True  # noqa F741
    ) -> bpy.types.Object:
        font_curve = bpy.data.curves.new(type="FONT", name="Font Curve")
        font_curve.body = str
        txt = bpy.data.objects.new(name="tmp_label.001", object_data=font_curve)
        txt.location = loc
        txt.rotation_euler = rot
        txt.data.align_x = "CENTER"
        txt.data.size = 0.2
        bpy.context.scene.collection.objects.link(txt)
        return txt

    def ConvertCurveToMesh(obj: bpy.types.Object):
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.convert(target="MESH")

    def CombineObjects(
        objs: list[bpy.types.Object], name: str = "combined_meshes", keep_geo: bool = True  # noqa F741
    ) -> tuple[bpy.types.Object, list[float], list[float], mathutils.Vector, mathutils.Vector]:
        bm = bmesh.new()
        dim = []
        bbox = []

        for each in objs:
            obj = each.copy()
            count_new = len(obj.data.vertices)
            print("count:", count_new)
            wm = obj.matrix_world

            count = len(bm.verts)
            bm.from_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            for i in range(count, (count + count_new)):
                v = bm.verts[i]
                v.co = wm @ v.co

        mesh_data = D.meshes.new(name)

        bm.to_mesh(mesh_data)
        bm.free()

        mesh_obj = D.objects.new(mesh_data.name, mesh_data)

        if keep_geo:
            C.collection.objects.link(mesh_obj)
        bpy.ops.object.select_all(action="DESELECT")
        dim = mesh_obj.dimensions
        bbox = mesh_obj.bound_box

        xx = []
        yy = []
        zz = []

        for i, val in enumerate(bbox):
            xx.append(bbox[i][0])
            yy.append(bbox[i][1])
            zz.append(bbox[i][2])

        vec = mathutils.Vector((0.0, 0.0, 1.0))  # noqa F841
        minv = mathutils.Vector((min(xx), min(yy), min(zz)))
        maxv = mathutils.Vector((max(xx), max(yy), max(zz)))

        bpy.data.objects.remove(obj, do_unlink=True)
        # bpy.data.objects.remove(mesh_obj, do_unlink=True)
        return (mesh_obj, bbox, dim, minv, maxv)

    # get combined mesh and measures for user selected objects
    mesh_object, bbox, dim, minv, maxv = CombineObjects(objs, "", False)

    # build measure objects
    stick_r = 0.02
    stick_s = 0.1
    stick_g = 0.05
    part_collection = []
    unt = " m"

    # x objects
    xtext = str(round(dim[0], 2)) + unt
    xloc = ((minv.x + maxv.x) / 2, minv[1], minv[2] - stick_s)
    xrot = [math.radians(90), 0, 0]
    xobj = GimmeText(xtext, xloc, xrot)
    ConvertCurveToMesh(xobj)
    xstick = MakeAStick(
        stick_r, dim[0], ((minv.x + maxv.x) / 2, minv[1], minv[2] - stick_s - stick_g), [0, math.radians(90), 0]
    )
    part_collection.append(xobj)
    part_collection.append(xstick)

    # y objects
    ytext = str(round(dim[1], 2)) + unt
    yloc = (maxv.x, ((minv.y + maxv.y) / 2), minv[2] - stick_s)
    yrot = [math.radians(90), 0, math.radians(90)]
    yobj = GimmeText(ytext, yloc, yrot)
    ConvertCurveToMesh(yobj)
    ystick = MakeAStick(
        stick_r,
        dim[1],
        (maxv.x, ((minv.y + maxv.y) / 2), minv[2] - stick_s - stick_g),
        [0, math.radians(90), math.radians(90)],
    )
    part_collection.append(yobj)
    part_collection.append(ystick)

    # z objects
    ztext = str(round(dim[2], 2)) + unt
    zloc = ((maxv.x + (stick_g * 5)), minv.y, (maxv[2] + stick_g))
    zrot = [math.radians(90), 0, 0]
    zobj = GimmeText(ztext, zloc, zrot)
    ConvertCurveToMesh(zobj)
    zstick = MakeAStick(stick_r, dim[2], (maxv.x + (stick_g * 5), minv.y, (maxv[2] - (dim[2] / 2))), [0, 0, 0])
    part_collection.append(zobj)
    part_collection.append(zstick)

    # combine measure objects
    measure_object, bbox, dim, minv, maxv = CombineObjects(part_collection, "measure.001", True)

    # cleanup
    for each in part_collection:
        bpy.data.objects.remove(each, do_unlink=True)

    # select and make measure object active
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = measure_object
    measure_object.select_set(True)
    # bpy.context.scene.update()

    return "FINISHED"


if __name__ == "__main__":
    CORE_Create_Measure_Box()
