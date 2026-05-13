# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy


def check_if_in_geometry_collection(obj) -> bool:
    """Check if an object is in a geometrycollection"""
    for col in obj.users_collection:
        if col.name == "Geometry":
            return True
    return False


def force_switch_object_mode():
    """Switch to object mode and deselect all objects"""
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")


def get_correct_mesh_min_z(obj: bpy.types.Object) -> float:
    """Get the correct minimum Z coordinate of a mesh object in world space"""
    if obj.type != "MESH":
        return obj.location.z  # Non-mesh objects are not processed here
    min_z = float("inf")
    world_matrix = obj.matrix_world
    for vert in obj.data.vertices:
        world_vert = world_matrix @ vert.co
        if world_vert.z < min_z:
            min_z = world_vert.z
    return min_z


def get_top_parents(input_objects=[], skip_name_patterns=[]) -> list[bpy.types.Object]:
    """
    Get top-level parent objects, considering both direct parenting and Child Of constraints.
    """
    top_parents = []
    for obj in input_objects:
        # Check if object has a direct parent
        if obj.parent is not None:
            continue
        # Skip objects matching any of the provided name patterns
        if any(pattern in obj.name.lower() for pattern in skip_name_patterns):
            continue
        # Check if object has any Child Of constraints
        has_child_of = False
        for constraint in obj.constraints:
            if constraint.type == "CHILD_OF" and constraint.target is not None:
                # Check if constraint is enabled and has influence
                if not constraint.mute and constraint.influence > 0:
                    has_child_of = True
                    break
        # If no parent and no active Child Of constraint, it's a top parent
        if not has_child_of:
            top_parents.append(obj)
    return top_parents
