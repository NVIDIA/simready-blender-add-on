# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import os
import re

current_dir = os.path.dirname(os.path.abspath(__file__))
import bmesh  # noqa E402
import bpy  # noqa E402
import mathutils  # noqa E402
from mathutils.bvhtree import BVHTree  # noqa E402

from CORE_ArtistTools.addon.validators.validate_utils import (  # noqa F402
    check_if_in_geometry_collection,
    force_switch_object_mode,
    get_correct_mesh_min_z,
    get_top_parents,
)
from CORE_ArtistTools.addon.validators.validation_base import (  # noqa F402
    Action,
    InstancePlugin,
)

# ------------------------------------------------------------------------------------------------
# AUTOFIXERS (GEOMETRY)
# ------------------------------------------------------------------------------------------------


class Review_HighPolyMeshes(Action):
    label = "Review High Poly Meshes"
    on = "fail"


class Fix_Scale(Action):
    """ "Fix objects that are not at default scale (1,1,1)"""

    label = "Apply Default Scale"
    on = "failed"

    def process(self, context, plugin):
        def fix_scale_to_default():
            # Get the Geometry collection
            geometry_collection = bpy.data.collections.get("Geometry")
            if not geometry_collection:
                self.log.error("No Geometry collection found")
                return None

            # Get all mesh objects in the Geometry collection
            all_mesh_objects = [obj for obj in geometry_collection.objects if obj.type == "MESH"]

            if not all_mesh_objects:
                self.log.warning("No mesh objects found in Geometry collection")
                return None

            # Apply scale to all mesh objects
            bpy.ops.object.select_all(action="DESELECT")
            for obj in all_mesh_objects:
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj

                self.log.info(f"Applying scale to {obj.name} (current scale: {obj.scale})")

                bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

                self.log.info(f"Applied scale to {obj.name}, new scale: {obj.scale}")

            return None

        bpy.app.timers.register(fix_scale_to_default, first_interval=0.1)


class Fix_NeutralPosition(Action):
    """Fix objects that are penetrating below the ground plane (Z=0)"""

    label = "Align Objects to Neutral Position"
    on = "failed"

    def process(self, context, plugin):
        def fix_neutral_position():
            # Get the Geometry collection
            geometry_collection = bpy.data.collections.get("Geometry")
            if not geometry_collection:
                self.log.error("No Geometry collection found")
                return None

            # Get all mesh objects in the Geometry collection
            all_mesh_objects = [obj for obj in geometry_collection.objects if obj.type == "MESH"]

            if not all_mesh_objects:
                self.log.warning("No mesh objects found in Geometry collection")
                return None

            # Find the global minimum Z across all objects
            global_min_z = float("inf")
            objects_below_ground = []

            for obj in all_mesh_objects:
                # Get the world-space bounding box
                bbox_corners = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
                min_z = min(corner.z for corner in bbox_corners)

                # Use the more accurate mesh vertex method for rotated/scaled objects
                if min_z < 0.0:
                    min_z = get_correct_mesh_min_z(obj)

                # Track which objects are below ground
                if min_z < 0.0:
                    objects_below_ground.append(obj)

                # Track the global minimum
                if min_z < global_min_z:
                    global_min_z = min_z

            # If nothing is below ground, we're done
            if global_min_z >= 0.0:
                self.log.info("All mesh objects are already at or above ground plane")
                return None

            # Calculate how much we need to move everything up
            offset_z = abs(global_min_z)

            self.log.info(f"Moving all objects up by {offset_z:.4f} units to align with ground plane")

            # Move top-level parent objects up by the same amount
            collections_for_fix = ["Geometry", "ReferencePrims", "JOINT_WIDGETS_COLL"]
            objects_to_fix = []
            for col_name in collections_for_fix:
                collection = bpy.data.collections.get(col_name)
                if collection:
                    objects_to_fix.extend(collection.objects)
            top_parents = get_top_parents(objects_to_fix, ["grasp_identifier"])
            for obj in top_parents:
                obj.location.z += offset_z
                self.log.info(f"Moved {obj.name} up by {offset_z:.4f} units")

            return None

        bpy.app.timers.register(fix_neutral_position, first_interval=0.1)


class Fix_ObjMeshNaming(Action):
    """Fix object mesh data naming to match the expected pattern"""

    def process(self, context, plugin):
        # Pattern to match object names ending with _obj_XX
        obj_pattern = re.compile(r"^(.+)_obj_(\d+)$")

        # Get the problematic assets from the plugin
        for obj, issue_msg in plugin.problematic_assets:
            if obj and obj.type == "MESH" and obj.data:
                # Check if this object follows the _obj_XX pattern
                match = obj_pattern.match(obj.name)
                if match:
                    base_name = match.group(1)
                    number = match.group(2)
                    expected_mesh_name = f"{base_name}_mesh_{number}"

                    # Rename the mesh data
                    old_name = obj.data.name
                    obj.data.name = expected_mesh_name

                    self.log.info(
                        f"Renamed mesh data from '{old_name}' to '{expected_mesh_name}' for object '{obj.name}'"
                    )


class Fix_MeshTopology(Action):
    """Convert n-gons to triangles using stored bad meshes"""

    label = "Fix Mesh Topology"
    on = "failed"

    def process(self, context, plugin):
        def fix_ngons():
            success = True
            for instance in context:
                bad_meshes = instance.data.get("members", []) or instance.data.get("topology_issues", [])

                if not bad_meshes:
                    self.log.info("No meshes found to fix.")
                    success = False
                    for instance in context:
                        instance.data["fix_success"] = success
                    return None

                for mesh_name in bad_meshes:
                    self.log.info(f"mesh_name: {mesh_name}")
                    obj = bpy.data.objects.get(mesh_name.name)
                    if not obj:
                        self.log.error(f"Object '{mesh_name}' not found in scene.")
                        success = False
                        continue

                    # Add a triangulate modifier rather than bake it into the geometry
                    # Artist can then decide to triangulate or not
                    triangulate_modifier = obj.modifiers.new(name="Triangulate", type="TRIANGULATE")
                    triangulate_modifier.min_vertices = 5
                    self.log.info(f"Added triangulate modifier to {mesh_name}")

            for instance in context:
                instance.data["fix_success"] = success

            return None

        bpy.app.timers.register(fix_ngons, first_interval=0.1)


class Fix_LoneVerticesandEdges(Action):
    """Fix lone vertices and edges"""

    label = "Fix Lone Vertices and Edges"
    on = "failed"

    def process(self, context, plugin):
        def fix_lone_vertices_and_edges():
            success = True
            for instance in context:
                lone_rangers = instance.data.get("members", []) or instance.data.get("lone_vertices_issues", [])

                if not lone_rangers:
                    self.log.error("No lone vertices or edges found to fix.")
                    success = False
                    for instance in context:
                        instance.data["fix_success"] = success
                    return None

                for obj in instance:
                    if obj.type != "MESH":
                        continue

                    force_switch_object_mode()

                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj

                    bpy.ops.object.mode_set(mode="EDIT")

                    bm = bmesh.from_edit_mesh(obj.data)

                    lone_vertices = [v for v in bm.verts if not v.link_edges]
                    bmesh.ops.delete(bm, geom=lone_vertices, context="VERTS")

                    lone_edges = [e for e in bm.edges if not e.link_faces]
                    bmesh.ops.delete(bm, geom=lone_edges, context="EDGES")

                    bmesh.update_edit_mesh(obj.data)

                    force_switch_object_mode()

                    bm.free()

                    self.log.info(
                        f"Removed {len(lone_vertices)} lone vertices and {len(lone_edges)} lone edges from {obj.name}"
                    )

            for instance in context:
                instance.data["fix_success"] = success

            return None

        bpy.app.timers.register(fix_lone_vertices_and_edges, first_interval=0.1)


# ------------------------------------------------------------------------------------------------
# VALIDATORS (GEOMETRY)
# ------------------------------------------------------------------------------------------------
class Validate_MeshTopologies(InstancePlugin):

    label = "Validate Mesh Topology"

    families = ["mesh"]
    asset_types = ["prop"]
    actions = [Fix_MeshTopology]

    def process(self, instance):
        issues = []
        issues_warn = []
        bad_meshes = []

        for obj in bpy.context.view_layer.objects:
            if obj.type != "MESH":
                continue

            # Get the evaluated mesh with modifiers applied
            depsgraph = bpy.context.evaluated_depsgraph_get()
            eval_obj = obj.evaluated_get(depsgraph)
            eval_mesh = eval_obj.to_mesh()

            try:
                # Check for n-gons in the evaluated mesh
                ngons = [p for p in eval_mesh.polygons if len(p.vertices) > 4]
                if ngons:
                    issues_warn.append((obj, f"{obj.name} has {len(ngons)} n-gons after modifiers"))
                    bad_meshes.append(obj)
            finally:
                eval_obj.to_mesh_clear()

        instance.data["topology_issues"] = bad_meshes
        self.problematic_assets = issues

        if issues_warn:
            self.warnings = issues_warn


class Validate_HighPolyMeshes(InstancePlugin):

    label = "Validate Mesh High Poly"

    families = ["mesh"]
    asset_types = ["all"]

    def process(self, instance):
        issues = []
        issues_warn = []
        hi_meshes = []

        for obj in bpy.data.objects:
            if obj.type == "MESH":
                if len(obj.data.polygons) > 200000:
                    issues_warn.append((obj, f"object: {obj.name} has {len(obj.data.polygons)} faces"))
                if len(obj.data.polygons) > 1000000:
                    issues.append((obj, f"object: {obj.name} has {len(obj.data.polygons)} faces"))
                    hi_meshes.append(obj)

        instance.data["high_poly_meshes"] = hi_meshes
        self.problematic_assets = issues

        if issues_warn:
            self.warnings = issues_warn

        if issues:
            raise ValueError("\n".join(msg for _, msg in issues))


class Validate_OverlappingFaces(InstancePlugin):

    label = "Validate Mesh Overlapping Faces"

    families = ["mesh"]
    asset_types = ["all"]

    def process(self, instance):
        issues = []
        issues_warn = []
        threshold = 0.0001

        for obj in bpy.context.view_layer.objects:
            if obj.type != "MESH":
                continue

            # Check if object still exists in the scene
            if obj.name not in bpy.data.objects:
                continue

            # Skip objects that don't exist in a collection called "Geometry"
            if not check_if_in_geometry_collection(obj):
                continue

            bm = bmesh.new()
            bm.from_mesh(obj.data)

            kd = mathutils.kdtree.KDTree(len(bm.faces))

            face_data = {}
            for i, face in enumerate(bm.faces):
                center = face.calc_center_median()
                kd.insert(center, i)
                face_data[i] = face

            kd.balance()

            overlapping_faces = set()

            # Find overlapping faces
            for i, face in enumerate(bm.faces):
                center = face.calc_center_median()
                co, index, dist = kd.find(center)
                if dist < threshold and i != index:
                    overlapping_faces.add(i)
                    overlapping_faces.add(index)

            bm.free()

            if overlapping_faces:
                issues_warn.append((obj, f"{obj.name} has {len(overlapping_faces)} overlapping faces"))

        self.problematic_assets = issues

        if issues_warn:
            self.warnings = issues_warn

        if issues:
            raise ValueError("\n".join(msg for _, msg in issues))


class Validate_Lone_Vertices(InstancePlugin):
    label = "Validate Mesh Lone Vertices"

    families = ["mesh"]
    asset_types = ["all"]
    actions = [Fix_LoneVerticesandEdges]

    def process(self, instance):
        issues = []  # noqa: F841
        issues_warn = []

        mesh_to_fix = set()
        combined_issues = {}

        for obj in bpy.context.view_layer.objects:

            if obj.type != "MESH":
                continue

            bm = bmesh.new()
            bm.from_mesh(obj.data)

            # Check for lone vertices
            lone_vertices = [v for v in bm.verts if not v.link_edges]
            if lone_vertices:
                issues_warn.append((obj, f"{obj.name} has {len(lone_vertices)} lone vertices"))

                if obj not in combined_issues:
                    combined_issues[obj] = []
                    issue_msg = f"lone vertices detected: {obj.name}"
                    combined_issues[obj].append(issue_msg)
                    mesh_to_fix.add(obj)

            # Check for lone edges
            lone_edges = [e for e in bm.edges if not e.link_faces]
            if lone_edges:
                issues_warn.append((obj, f"{obj.name} has {len(lone_edges)} lone edges"))

                if obj not in combined_issues:
                    combined_issues[obj] = []
                    issue_msg = f"lone vertices detected: {obj.name}"
                    combined_issues[obj].append(issue_msg)
                    mesh_to_fix.add(obj)

            bm.free()

        combined_issues_list = []
        for mat, issue_msgs in combined_issues.items():
            if issue_msgs:
                combined_msg = "\n".join(issue_msgs)
                combined_issues_list.append((mat, combined_msg))

        instance.data["lone_vertices_issues"] = list(issues_warn)
        self.problematic_assets = combined_issues_list

        if issues_warn:
            self.warnings = issues_warn

        if combined_issues_list:
            error_messages = [msg for _, msg in combined_issues_list]
            error_message = "\n".join(error_messages) if len(error_messages) > 1 else error_messages[0]
            raise ValueError(error_message)


class Validate_Neutral_Position(InstancePlugin):
    """Validate asset sits on the ground plane (Z=0)"""

    label = "Validate Neutral Position"

    families = ["mesh"]
    asset_types = ["all"]
    actions = [Fix_NeutralPosition]

    def process(self, instance):
        issues = []
        issues_warn = []

        # Get the Export/Geometry collection
        geometry_collection = bpy.data.collections.get("Geometry")
        if not geometry_collection:
            self.log.error("No Geometry collection found")
            return

        # Track all objects below ground and find the worst offender
        objects_below_ground = []
        worst_object = None
        worst_min_z = 0.0

        # Check all mesh objects in the Geometry collection
        for obj in geometry_collection.objects:
            if obj.type != "MESH":
                continue

            # Get the world-space bounding box
            # Bounding box corners are in local space, so we transform them to world space
            bbox_corners = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]

            # Find the minimum Z value across all bounding box corners
            min_z = min(corner.z for corner in bbox_corners)

            # Use the more accurate mesh vertex method for rotated/scaled objects
            if min_z < 0.0:
                min_z = get_correct_mesh_min_z(obj)

            # Check if any part of the mesh is below the ground plane (Z=0)
            if min_z < 0.0:
                objects_below_ground.append((obj, min_z))

                # Track the worst offender (most negative Z)
                if min_z < worst_min_z:
                    worst_min_z = min_z
                    worst_object = obj

        # If we found objects below ground, report only the worst one
        # The autofix will handle all of them together
        if worst_object is not None:
            # Create a descriptive message listing all affected objects
            object_list = ", ".join([obj.name for obj, _ in objects_below_ground])
            issue_msg = (
                f"{len(objects_below_ground)} object(s) extend below ground plane. "
                f"Worst: {worst_object.name} (min Z: {worst_min_z:.4f}). "
                f"Affected objects: {object_list}. "
                f"Autofix will align all objects to Z=0 for consistent simulation."
            )

            # Report only the worst object, but the message shows all affected objects
            issues.append((worst_object, issue_msg))

        instance.data["neutral_position_issues"] = issues
        self.problematic_assets = issues

        if issues_warn:
            self.warnings = issues_warn

        if issues:
            error_messages = [msg for _, msg in issues]
            error_message = "\n".join(error_messages) if len(error_messages) > 1 else error_messages[0]
            raise ValueError(error_message)


class Validate_Scale(InstancePlugin):
    """Validate asset is at default scale (1,1,1)"""

    label = "Validate Scale"

    families = ["mesh"]
    asset_types = ["all"]
    actions = [Fix_Scale]

    # TODO: implementation of Fix_Scale will work for flattened meshes
    # TODO: but for parented objects, we need to check the scale of the parent and child
    # TODO: if this is the parent of a child or children, we need to then freeze transforms of the child
    # TODO: the order could get tricky, as then we'd need to send 2 objects to the Fix_Scale action (maybe)

    def process(self, instance):
        issues = []
        issues_warn = []

        # Get the Geometry collection
        geometry_collection = bpy.data.collections.get("Geometry")
        if not geometry_collection:
            self.log.error("No Geometry collection found")
            return

        # Algorithm to find scaled objects
        scaled_objects = []
        tolerance = 0.0001  # Small tolerance for floating point comparison

        # Check all mesh objects in the Geometry collection
        for obj in geometry_collection.objects:
            # Get object's scale
            scale = obj.scale

            # Check if any scale axis deviates from 1.0 (default scale)
            is_scaled = (
                abs(scale.x - 1.0) > tolerance or abs(scale.y - 1.0) > tolerance or abs(scale.z - 1.0) > tolerance
            )

            if is_scaled:
                # Found a scaled object
                scale_str = f"({scale.x:.4f}, {scale.y:.4f}, {scale.z:.4f})"
                self.log.warning(f"Object '{obj.name}' has non-default scale: {scale_str}")
                scaled_objects.append(obj)

                issue_msg = (
                    f"Object '{obj.name}' has non-default scale: {scale_str}. "
                    f"Apply scale (Ctrl+A > Scale) before export to ensure proper simulation behavior."
                )
                issues.append((obj, issue_msg))

        # Store results
        instance.data["scale_issues"] = issues
        self.problematic_assets = issues

        if issues_warn:
            self.warnings = issues_warn

        # Raise error if any scaled objects were found
        if issues:
            error_messages = [msg for _, msg in issues]
            error_message = "\n".join(error_messages) if len(error_messages) > 1 else error_messages[0]
            raise ValueError(error_message)


class Validate_Object_Mesh_Naming(InstancePlugin):
    label = "Validate Object To Mesh Naming"

    families = ["mesh"]
    asset_types = ["all"]
    actions = [Fix_ObjMeshNaming]

    def process(self, instance):
        issues = []
        issues_warn = []
        combined_issues = {}

        # Pattern to match object names ending with _obj_XX
        obj_pattern = re.compile(r"^(.+)_obj_(\d+)$")

        # Get Geometry collection
        geometry_collection = bpy.data.collections.get("Geometry")
        if not geometry_collection:
            self.log.error("No Geometry collection found")
            return

        # Get all objects in the Geometry collection
        geometry_objects = geometry_collection.objects

        # Find all parent objects that match the _obj_XX pattern
        parent_objects = {}
        for obj in geometry_objects:
            match = obj_pattern.match(obj.name)
            if match:
                base_name = match.group(1)
                number = match.group(2)
                parent_objects[obj] = {
                    "base_name": base_name,
                    "number": number,
                    "expected_mesh_name": f"{base_name}_mesh_{number}",
                }

        # Check each parent object for proper mesh data naming
        for parent_obj, naming_info in parent_objects.items():
            expected_mesh_name = naming_info["expected_mesh_name"]

            # Check if this object has mesh data and if it's named correctly
            if parent_obj.type == "MESH" and parent_obj.data:
                mesh_data_name = parent_obj.data.name
                if mesh_data_name != expected_mesh_name:
                    issue_msg = f"Object '{parent_obj.name}' has mesh data named '{mesh_data_name}' but expected '{expected_mesh_name}'"
                    issues.append(issue_msg)
                    combined_issues[parent_obj] = [issue_msg]
            else:
                # Object doesn't have mesh data
                issue_msg = (
                    f"Object '{parent_obj.name}' has no mesh data. Expected mesh data name: '{expected_mesh_name}'"
                )
                issues.append(issue_msg)
                combined_issues[parent_obj] = [issue_msg]

        # Check for mesh data that might be incorrectly named
        for obj in geometry_objects:
            if obj.type == "MESH" and obj.data:
                # Check if this object follows the _obj_XX pattern
                obj_match = obj_pattern.match(obj.name)
                if obj_match:
                    base_name = obj_match.group(1)
                    number = obj_match.group(2)
                    expected_mesh_name = f"{base_name}_mesh_{number}"

                    if obj.data.name != expected_mesh_name:
                        issue_msg = f"Object '{obj.name}' has mesh data named '{obj.data.name}' but expected '{expected_mesh_name}'"
                        issues.append(issue_msg)
                        if obj not in combined_issues:
                            combined_issues[obj] = []
                        combined_issues[obj].append(issue_msg)

        # Convert combined_issues to the expected format
        combined_issues_list = []
        for obj, issue_msgs in combined_issues.items():
            if issue_msgs:
                combined_msg = "\n".join(issue_msgs)
                combined_issues_list.append((obj, combined_msg))

        instance.data["object_mesh_naming_issues"] = list(issues)
        self.problematic_assets = combined_issues_list

        # Add warnings
        if issues_warn:
            self.warnings = issues_warn

        # Raise error if there are critical issues
        if issues:
            error_messages = [msg for _, msg in combined_issues_list]
            error_message = "\n".join(error_messages) if len(error_messages) > 1 else error_messages[0]
            raise ValueError(error_message)


class Validate_Intersecting_Colliders(InstancePlugin):
    label = "Validate Mesh Intersecting Colliders"

    families = ["mesh"]
    asset_types = ["all"]
    actions = []

    def process(self, instance):
        issues = []  # noqa: F841
        issues_warn = []
        combined_issues = {}

        collection = bpy.data.collections.get("Geometry")

        if not collection:
            self.log.error("No Geometry collection found")
            return

        meshes = [obj for obj in collection.objects if obj.type == "MESH"]
        intersecting_objects = set()

        # Check all unique pairs
        if len(meshes) > 1:
            for i in range(len(meshes)):
                for j in range(i + 1, len(meshes)):
                    obj1, obj2 = meshes[i], meshes[j]

                    # Create BMesh with world transformations
                    bm1 = bmesh.new()
                    bm1.from_mesh(obj1.data)
                    bm1.transform(obj1.matrix_world)

                    bm2 = bmesh.new()
                    bm2.from_mesh(obj2.data)
                    bm2.transform(obj2.matrix_world)

                    # Build BVH trees
                    bvh1 = BVHTree.FromBMesh(bm1)
                    bvh2 = BVHTree.FromBMesh(bm2)

                    # Check for overlaps
                    if bvh1.overlap(bvh2):
                        combined_issues[obj1] = []
                        issue_msg = f"{obj1.name} is intersecting with {obj2.name}"
                        combined_issues[obj1].append(issue_msg)
                        intersecting_objects.add(obj1)
                        intersecting_objects.add(obj2)
                    bm1.free()
                    bm2.free()

        combined_issues_list = []
        for obj, issue_msgs in combined_issues.items():
            if issue_msgs:
                combined_msg = "\n".join(issue_msgs)
                combined_issues_list.append((obj, combined_msg))

        # Store intersection data for potential fixes/actions
        instance.data["intersecting_colliders"] = list(intersecting_objects)

        # Add intersecting collider issues to warnings
        if combined_issues_list:
            for obj, msg in combined_issues_list:
                issues_warn.append((obj, msg))

        if issues_warn:
            self.warnings = issues_warn


class Validate_Joints_Hierarchy(InstancePlugin):
    label = "Validate Joints Hierarchy"

    families = ["mesh"]
    asset_types = ["all"]
    actions = []

    def process(self, instance):
        issues = []  # noqa: F841
        issues_warn = []
        combined_issues = {}

        collections_for_check = ["Geometry", "ReferencePrims", "JOINT_WIDGETS_COLL"]
        objects_to_check = []
        for col_name in collections_for_check:
            collection = bpy.data.collections.get(col_name)
            if collection:
                objects_to_check.extend(collection.objects)

        top_parents = get_top_parents(objects_to_check, ["grasp_identifier"])
        if len(top_parents) > 1:
            for obj in top_parents:
                combined_issues[obj] = []
                issue_msg = f"Multiple top-level parents found: {obj.name}"
                combined_issues[obj].append(issue_msg)

        combined_issues_list = []
        for obj, issue_msgs in combined_issues.items():
            if issue_msgs:
                combined_msg = "\n".join(issue_msgs)
                combined_issues_list.append((obj, combined_msg))

        instance.data["joints_hierarchy_issues"] = top_parents

        if combined_issues_list:
            for obj, msg in combined_issues_list:
                issues_warn.append((obj, msg))

        if issues_warn:
            self.warnings = issues_warn
