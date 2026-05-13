# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import math
import time
from dataclasses import dataclass
from itertools import combinations
from math import degrees, radians

import blf
import bpy
import gpu
from bpy.types import Operator
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

# --------------------------
# Constants
# --------------------------

WIDGET_COLLECTION_NAME = "JOINT_WIDGETS_COLL"
LIMIT_CONSTRAINT_NAME = "JointLimit"

# Global draw handler for text overlay
_draw_handler = None

# --------------------------
# Collection Utilities
# --------------------------


def ensure_widget_collection():
    scene_collection = bpy.context.scene.collection  # noqa F841
    coll = bpy.data.collections.get(WIDGET_COLLECTION_NAME)
    if not coll:
        coll = bpy.data.collections.new(WIDGET_COLLECTION_NAME)
        bpy.context.scene.collection.children.link(coll)
    return coll


def set_collection_visibility(hidden: bool):
    coll = bpy.data.collections.get(WIDGET_COLLECTION_NAME)
    if not coll:
        return
    # Hide in viewport (and render, optional)
    coll.hide_viewport = hidden
    # In Blender 4.x, you might also want to toggle:
    # coll.hide_render = hidden


# ------------------------------------------------
# Utility Functions
# -----------------------------------------------
def debug_face_selections():
    """Print information about currently selected faces on all selected objects."""
    if bpy.context.mode != "EDIT_MESH":
        print("Must be in Edit mode to check face selections")
        return

    print("\n=== FACE SELECTION DEBUG ===")
    for obj in bpy.context.selected_objects:
        if obj.type == "MESH":
            selected_faces = [i for i, p in enumerate(obj.data.polygons) if p.select]
            print(f"{obj.name}: {len(selected_faces)} faces selected")
            if selected_faces:
                print(f"  Indices: {selected_faces[:10]}{'...' if len(selected_faces) > 10 else ''}")


def convert_to_radians_to_degrees(radians):
    return radians * (180 / math.pi)


# --------------------------
# Text Overlay Handler - Viewport text abels
# --------------------------

# Global storage for text labels to draw
_text_labels_to_draw = []


def draw_text_overlay():
    """Draw handler callback for text labels"""
    global _text_labels_to_draw

    try:
        for label_data in _text_labels_to_draw:
            text = label_data["text"]
            screen_pos = label_data["screen_pos"]
            color = label_data["color"]
            size = label_data["size"]

            if screen_pos is None:
                continue

            font_id = 0
            blf.size(font_id, size)
            blf.color(font_id, *color)
            blf.position(font_id, screen_pos[0], screen_pos[1], 0)
            blf.draw(font_id, text)
    except Exception:
        pass

    # Clear for next frame
    _text_labels_to_draw.clear()


def queue_text_label(text, screen_pos, color=(1, 1, 1, 1), size=16):
    """Queue a text label to be drawn this frame"""
    global _text_labels_to_draw
    _text_labels_to_draw.append({"text": text, "screen_pos": screen_pos, "color": color, "size": size})


# --------------------------
# Axis helpers
# --------------------------


def axis_basis(axis: str) -> Matrix:
    """
    Return a matrix whose local +Z is aligned to the chosen world axis.
    We treat local Z as the joint axis for both prismatic and revolute.
    """
    if axis == "Z":
        return Matrix.Identity(4)
    elif axis == "X":
        # Rotate +90° around Y so local Z -> world X
        return Matrix.Rotation(radians(90.0), 4, "Y")
    elif axis == "Y":
        # Rotate +90° around X so local Z -> world Y
        return Matrix.Rotation(radians(90.0), 4, "X")
    return Matrix.Identity(4)


# --------------------------
# Object helpers
# --------------------------


def add_empty(name, parent=None, matrix=Matrix.Identity(4), empty_display="ARROWS", size=0.15, coll=None):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = empty_display
    ob.empty_display_size = size

    # link to a collection
    target_coll = coll if coll else bpy.context.scene.collection
    target_coll.objects.link(ob)

    ob.matrix_world = matrix
    if parent:
        ob.parent = parent
        ob.matrix_parent_inverse = parent.matrix_world.inverted()
    return ob


def get_or_add_limit_constraint(obj, joint_type: str, axis=None) -> bpy.types.Constraint:
    """
    Making a LIMIT_LOCATION or LIMIT_ROTATION constraint.
    input: obj: bpy.types.Object, joint_type: str, axis: str
    """
    con = None
    for c in obj.constraints:
        if c.name == LIMIT_CONSTRAINT_NAME:
            con = c
            break

    if not con:
        if joint_type == "prismatic":
            con = obj.constraints.new("LIMIT_LOCATION")
        else:
            con = obj.constraints.new("LIMIT_ROTATION")
        con.name = LIMIT_CONSTRAINT_NAME

    if joint_type == "prismatic":
        # We'll use local Z as the joint axis
        con.use_min_x = con.use_max_x = False
        con.use_min_y = con.use_max_y = False
        con.use_min_z = True
        con.use_max_z = True
        con.use_transform_limit = True
    else:  # REVOLUTE
        con.use_limit_x = False
        con.use_limit_y = False
        con.use_limit_z = True

    return con


# --------------------------
# Driver helpers
# --------------------------


def clear_driver(datablock, path) -> None:
    """
    Clearing a driver from a constraint.
    input: datablock: bpy.types.Constraint, path: str
    """
    try:
        datablock.driver_remove(path)
    except Exception:
        pass


def add_transform_driver(
    datablock, path, target_obj, transform_type="LOC_Z", space="LOCAL_SPACE", var_name="var"
) -> bpy.types.FCurve:
    """
    Adding a transform driver to a constraint.
    input: datablock: bpy.types.Constraint, path: str, target_obj: bpy.types.Object, transform_type: str, space: str, var_name: str
    """
    clear_driver(datablock, path)
    fcurve = datablock.driver_add(path)
    drv = fcurve.driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = var_name
    var.type = "TRANSFORMS"
    targ = var.targets[0]
    targ.id = target_obj
    targ.transform_type = transform_type
    targ.transform_space = space
    drv.expression = var_name
    return fcurve


def add_euler_driver(
    datablock, path, target_obj, axis_index=2, space="LOCAL_SPACE", var_name="ang"
) -> bpy.types.FCurve:
    """
    Adding an euler driver to a constraint.
    input: datablock: bpy.types.Constraint, path: str, target_obj: bpy.types.Object, axis_index: int, space: str, var_name: str
    """
    clear_driver(datablock, path)
    fcurve = datablock.driver_add(path)
    drv = fcurve.driver
    drv.type = "SCRIPTED"
    var = drv.variables.new()
    var.name = var_name
    var.type = "TRANSFORMS"
    targ = var.targets[0]
    targ.id = target_obj
    targ.transform_type = ["ROT_X", "ROT_Y", "ROT_Z"][axis_index]
    targ.transform_space = space
    # pass-through angle (radians)
    drv.expression = var_name
    return fcurve


# --------------------------
# Locking helpers
# --------------------------


def lock_transforms_prismatic(handle):
    # Only allow motion along local Z (joint axis)
    handle.lock_location = (True, True, False)
    handle.lock_rotation = (True, True, True)
    handle.lock_scale = (True, True, True)


def lock_transforms_revolute(handle):
    # Only allow rotation around local Z (spin axis)
    handle.lock_location = (True, True, True)
    handle.lock_rotation = (True, True, False)
    handle.lock_scale = (True, True, True)


# --------------------------
# GPU Drawing helpers
# --------------------------


def draw_arc(matrix, min_angle, max_angle, radius=1.0, color=(0.3, 0.6, 1.0, 0.25), segments=64):
    """Draw a filled arc in 3D space"""
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")

    vertices = [(0, 0, 0)]
    angle_range = max_angle - min_angle
    for i in range(segments + 1):
        t = i / segments
        angle = min_angle + angle_range * t
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        vertices.append((x, y, 0))

    indices = []
    for i in range(segments):
        indices.append((0, i + 1, i + 2))

    batch = batch_for_shader(shader, "TRIS", {"pos": vertices}, indices=indices)

    gpu.state.blend_set("ALPHA")
    shader.bind()
    shader.uniform_float("color", color)

    gpu.matrix.push()
    gpu.matrix.multiply_matrix(matrix)
    batch.draw(shader)
    gpu.matrix.pop()

    gpu.state.blend_set("NONE")


def draw_arc_outline(matrix, min_angle, max_angle, radius=1.0, color=(0.5, 0.8, 1.0, 0.8), segments=64, line_width=2):
    """Draw arc outline"""
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")

    vertices = []
    angle_range = max_angle - min_angle
    for i in range(segments + 1):
        t = i / segments
        angle = min_angle + angle_range * t
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        vertices.append((x, y, 0))

    batch = batch_for_shader(shader, "LINE_STRIP", {"pos": vertices})

    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(line_width)

    shader.bind()
    shader.uniform_float("color", color)

    gpu.matrix.push()
    gpu.matrix.multiply_matrix(matrix)
    batch.draw(shader)
    gpu.matrix.pop()

    gpu.state.blend_set("NONE")


def draw_full_ring(matrix, radius=1.0, color=(0.3, 0.3, 0.3, 0.3), segments=64, line_width=1):
    """Draw a full circle outline for reference"""
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")

    vertices = []
    for i in range(segments + 1):
        angle = (math.tau * i) / segments
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        vertices.append((x, y, 0))

    batch = batch_for_shader(shader, "LINE_STRIP", {"pos": vertices})

    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(line_width)

    shader.bind()
    shader.uniform_float("color", color)

    gpu.matrix.push()
    gpu.matrix.multiply_matrix(matrix)
    batch.draw(shader)
    gpu.matrix.pop()

    gpu.state.blend_set("NONE")


# --------------------------
# GPU Drawing helpers - Prismatic
# --------------------------


def draw_line_segment(matrix, min_dist, max_dist, color=(0.3, 0.6, 1.0, 0.5), line_width=4):
    """Draw a thick line segment showing the translation range"""
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")

    # Create line along Z-axis (local axis)
    vertices = [(0, 0, min_dist), (0, 0, max_dist)]

    batch = batch_for_shader(shader, "LINES", {"pos": vertices})

    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(line_width)

    shader.bind()
    shader.uniform_float("color", color)

    gpu.matrix.push()
    gpu.matrix.multiply_matrix(matrix)
    batch.draw(shader)
    gpu.matrix.pop()

    gpu.state.blend_set("NONE")


def draw_limit_marker(matrix, distance, color=(1, 1, 1, 0.8), size=0.1):
    """Draw a small cross marker at min/max positions"""
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")

    # Create cross shape in XY plane at the given Z distance
    half_size = size / 2
    vertices = [
        (-half_size, 0, distance),
        (half_size, 0, distance),  # Horizontal line
        (0, -half_size, distance),
        (0, half_size, distance),  # Vertical line
    ]

    indices = [(0, 1), (2, 3)]

    batch = batch_for_shader(shader, "LINES", {"pos": vertices}, indices=indices)

    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(2)

    shader.bind()
    shader.uniform_float("color", color)

    gpu.matrix.push()
    gpu.matrix.multiply_matrix(matrix)
    batch.draw(shader)
    gpu.matrix.pop()

    gpu.state.blend_set("NONE")


def draw_rail_guides(matrix, min_dist, max_dist, color=(0.5, 0.5, 0.5, 0.3), num_guides=4):
    """Draw guide rails/lines perpendicular to the translation axis"""
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")

    vertices = []
    size = 0.15

    # Create perpendicular guide lines along the range
    for i in range(num_guides):
        t = i / (num_guides - 1) if num_guides > 1 else 0.5
        z = min_dist + (max_dist - min_dist) * t

        # X-axis guide
        vertices.extend([(-size, 0, z), (size, 0, z)])
        # Y-axis guide
        vertices.extend([(0, -size, z), (0, size, z)])

    batch = batch_for_shader(shader, "LINES", {"pos": vertices})

    gpu.state.blend_set("ALPHA")
    gpu.state.line_width_set(1)

    shader.bind()
    shader.uniform_float("color", color)

    gpu.matrix.push()
    gpu.matrix.multiply_matrix(matrix)
    batch.draw(shader)
    gpu.matrix.pop()

    gpu.state.blend_set("NONE")


def draw_3d_text(context, text, world_pos, color=(1, 1, 1, 1), size=16):
    """Queue text to be drawn in 3D space at the given world position"""
    from bpy_extras.view3d_utils import location_3d_to_region_2d

    region = context.region
    rv3d = context.region_data

    # Convert 3D world position to 2D screen position
    screen_pos = location_3d_to_region_2d(region, rv3d, world_pos)

    if screen_pos is None:
        return  # Position is behind the camera

    # Queue the text to be drawn by the draw handler
    queue_text_label(text, screen_pos, color, size)


# --------------------------
# Property sync callbacks
# --------------------------


def sync_rna_to_constraint(self, context):
    """Sync RNA property changes to constraint - called when user drags gizmo or changes slider (REVOLUTE)"""
    obj = self
    # print(f"[REVOLUTE SYNC Debug] Called for object: {obj.name}")

    # Find the constraint
    con = next((c for c in obj.constraints if c.name == LIMIT_CONSTRAINT_NAME), None)
    if con and con.type == "LIMIT_ROTATION":
        # print(f"[REVOLUTE SYNC debug] Found LIMIT_ROTATION constraint")
        # Find the axis from the widget metadata
        axis_frames = [
            ob
            for ob in bpy.data.objects
            if ob.type == "EMPTY" and ob.get("jw_target") == obj.name and ob.get("joint_type") == "revolute"
        ]

        # print(f"[REVOLUTE SYNC debug] Found {len(axis_frames)} axis frames")

        if axis_frames:
            axis = axis_frames[0].get("jw_axis", "Z")
            # print(f"[REVOLUTE SYNC debug] Axis: {axis}")

            # Update constraint limits based on the axis
            if axis == "X":
                con.min_x = obj.jw_rotation_limit_min_rna
                con.max_x = obj.jw_rotation_limit_max_rna
            elif axis == "Y":
                con.min_y = obj.jw_rotation_limit_min_rna
                con.max_y = obj.jw_rotation_limit_max_rna
            else:  # 'Z'
                con.min_z = obj.jw_rotation_limit_min_rna
                con.max_z = obj.jw_rotation_limit_max_rna

            # print(f"[REVOLUTE SYNC debug] Updated constraint limits")

            # Update the joint properties to sync back to Apply button UI
            if hasattr(context.scene, "joint_attribute_props"):
                props = context.scene.joint_attribute_props
                props.lower_limit_deg = convert_to_radians_to_degrees(obj.jw_rotation_limit_min_rna)
                props.upper_limit_deg = convert_to_radians_to_degrees(obj.jw_rotation_limit_max_rna)
                # print(f"[REVOLUTE SYNC debug] Updated UI props")

                # Force UI refresh by incrementing the refresh trigger
                try:
                    props.ui_refresh_trigger += 1
                except Exception:
                    pass

            # Update the pxr joint attributes on the reference prim (empty)
            # Find the empty that has body1 pointing to this object

            # Update the pxr attributes with the new limits (IN DEGREES)
            obj["pxr:usd:physics:joint:lowerLimit"] = convert_to_radians_to_degrees(obj.jw_rotation_limit_min_rna)
            obj["pxr:usd:physics:joint:upperLimit"] = convert_to_radians_to_degrees(obj.jw_rotation_limit_max_rna)
            # print(f"[REVOLUTE SYNC debug] ✓ Updated pxr limits on {obj.name}: lower={convert_to_radians_to_degrees(obj.jw_rotation_limit_min_rna):.2f}, upper={convert_to_radians_to_degrees(obj.jw_rotation_limit_max_rna):.2f}")

            # Force area redraw
            for area in context.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()

    else:
        print("[REVOLUTE SYNC] No LIMIT_ROTATION constraint found")


def sync_rna_to_constraint_prismatic(self, context):
    """Sync RNA property changes to constraint - called when user drags gizmo or changes slider (PRISMATIC)"""
    obj = self
    # print(f"[PRISMATIC SYNC debug] Called for object: {obj.name}")

    # Find the constraint
    con = next((c for c in obj.constraints if c.name == LIMIT_CONSTRAINT_NAME), None)
    if con and con.type == "LIMIT_LOCATION":
        # print(f"[PRISMATIC SYNC debug] Found LIMIT_LOCATION constraint")
        # Find the axis from the widget metadata
        axis_frames = [
            ob
            for ob in bpy.data.objects
            if ob.type == "EMPTY" and ob.get("jw_target") == obj.name and ob.get("joint_type") == "prismatic"
        ]

        # print(f"[PRISMATIC SYNC debug] Found {len(axis_frames)} axis frames")

        if axis_frames:
            axis = axis_frames[0].get("jw_axis", "Z")
            # print(f"[PRISMATIC SYNC debug] Axis: {axis}")

            # Get current location for offset calculation
            current_location = obj.location

            # Calculate relative/local transform values for USD export
            # Apply the same negation logic as in physics_operators.py calc_min_max_limits
            if axis == "X":
                local_min = obj.jw_translation_limit_min_rna - current_location.x
                local_max = obj.jw_translation_limit_max_rna - current_location.x
            elif axis == "Y":
                # Y axis is negated due to the +90° rotation around X axis (see axis_basis function)
                # After negation, min and max are swapped, so we swap them back
                local_max = -(obj.jw_translation_limit_min_rna - current_location.y)
                local_min = -(obj.jw_translation_limit_max_rna - current_location.y)
            else:  # 'Z'
                local_min = obj.jw_translation_limit_min_rna - current_location.z
                local_max = obj.jw_translation_limit_max_rna - current_location.z

            # Update constraint limits based on the axis
            if axis == "X":
                con.min_x = obj.jw_translation_limit_min_rna
                con.max_x = obj.jw_translation_limit_max_rna
            elif axis == "Y":
                con.min_y = obj.jw_translation_limit_min_rna
                con.max_y = obj.jw_translation_limit_max_rna
            else:  # 'Z'
                con.min_z = obj.jw_translation_limit_min_rna
                con.max_z = obj.jw_translation_limit_max_rna

            # print(f"[PRISMATIC SYNC] Updated constraint limits: min={obj.jw_translation_limit_min_rna:.4f}, max={obj.jw_translation_limit_max_rna:.4f}")

            # Update the joint properties to sync back to Apply button UI
            if hasattr(context.scene, "joint_attribute_props"):
                props = context.scene.joint_attribute_props

                # The RNA properties represent the actual absolute limits
                # They can be directly set to the props
                props.min_dist_prismatic = obj.jw_translation_limit_min_rna
                props.max_dist_prismatic = obj.jw_translation_limit_max_rna
                # print(f"[PRISMATIC SYNC debug] Updated UI props")

                # Force UI refresh by incrementing the refresh trigger
                try:
                    props.ui_refresh_trigger += 1
                except Exception:
                    pass

            # Update the pxr attributes with the LOCAL/RELATIVE limits for USD export
            obj["pxr:usd:physics:joint:lowerLimit"] = local_min
            obj["pxr:usd:physics:joint:upperLimit"] = local_max
            # print(f"[PRISMATIC SYNC] ✓ Updated pxr limits on {obj.name}: lower={local_min:.4f}, upper={local_max:.4f}")

            # Force area redraw
            for area in context.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    else:
        print("[PRISMATIC SYNC] No LIMIT_LOCATION constraint found")


# --------------------------
# Gizmo Group for Revolute Joint Visualization
# --------------------------


class JW_GizmoGroup_Revolute(bpy.types.GizmoGroup):
    """GPU-drawn visualization and dial gizmos for revolute joints"""

    bl_idname = "JW_GGT_revolute_viz"
    bl_label = "Revolute Joint Visualization"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"3D", "PERSISTENT"}

    @classmethod
    def poll(cls, context):
        """Only show if widgets are visible and there are revolute joints"""
        if context.mode != "OBJECT":
            return False

        if not hasattr(context.scene, "joint_attribute_props"):
            return False

        props = context.scene.joint_attribute_props
        if not props.show_widgets:
            return False

        # Yield fully to standard transform tools so their widgets are not blocked
        try:
            active_tool = context.workspace.tools.from_space_view3d_mode(context.mode)
            if active_tool and active_tool.idname in [
                "builtin.rotate",
                "builtin.move",
                "builtin.scale",
                "builtin.transform",
            ]:
                return False
        except Exception:
            pass

        # Also yield when transform gizmo overlays are enabled in the viewport
        # (e.g. Select tool with Move/Rotate/Scale gizmos shown via the header overlay)
        try:
            sd = context.space_data
            if sd and (sd.show_gizmo_object_translate or sd.show_gizmo_object_rotate or sd.show_gizmo_object_scale):
                return False
        except Exception:
            pass

        # Check if any revolute joint widgets exist
        for obj in bpy.data.objects:
            if obj.type == "EMPTY" and obj.get("joint_type") == "revolute":
                return True
        return False

    def setup(self, context):
        """Setup - gizmos will be managed dynamically in refresh"""
        # Initialize gizmo data dictionary
        self.gizmo_data = {}
        self.last_object_set = set()

    def refresh(self, context):
        """Update gizmos dynamically - recreate if scene objects changed"""
        try:
            # Get current set of revolute joint objects
            current_objects = set()
            for obj in bpy.data.objects:
                # Validate object still exists and is valid
                if not obj or obj.type != "EMPTY" or obj.get("joint_type") != "revolute":
                    continue

                target_name = obj.get("jw_target")
                if target_name:
                    target_obj = bpy.data.objects.get(target_name)
                    # Validate target object exists
                    if target_obj and target_obj.name in bpy.data.objects:
                        current_objects.add((target_name, obj.name))

            # Always rebuild if the object set changed OR if we have objects but no gizmos
            needs_rebuild = (current_objects != self.last_object_set) or (
                len(current_objects) > 0 and len(self.gizmo_data) == 0
            )

            if needs_rebuild:
                # Clear old gizmos safely
                self.gizmo_data.clear()
                for gz in list(self.gizmos):
                    try:
                        self.gizmos.remove(gz)
                    except Exception:
                        pass

                # Create new gizmos for all revolute joints
                for target_name, axis_frame_name in current_objects:
                    obj = bpy.data.objects.get(axis_frame_name)
                    target_obj = bpy.data.objects.get(target_name)

                    # Validate objects exist
                    if not obj or obj.name not in bpy.data.objects:
                        continue
                    if not target_obj or target_obj.name not in bpy.data.objects:
                        continue

                    # Find the ring root
                    ring_root = None
                    ring_root_name = f"RingRoot_{target_name}"
                    for child in obj.children:
                        if child.name == ring_root_name:
                            ring_root = child
                            break

                    if not ring_root or ring_root.name not in bpy.data.objects:
                        continue

                    # Create dial gizmos for min and max
                    try:
                        min_dial = self.gizmos.new("GIZMO_GT_dial_3d")
                        max_dial = self.gizmos.new("GIZMO_GT_dial_3d")
                    except Exception:
                        continue

                    # Visual settings for min dial (red)
                    min_dial.color = (1.0, 0.4, 0.4)
                    min_dial.alpha = 0.5
                    min_dial.alpha_highlight = 0.8
                    min_dial.scale_basis = ring_root.get("jw_radius", 0.5) * 1.0
                    min_dial.line_width = 2
                    min_dial.use_draw_value = True
                    min_dial.use_draw_modal = True

                    # Visual settings for max dial (green)
                    max_dial.color = (0.4, 1.0, 0.4)
                    max_dial.alpha = 0.5
                    max_dial.alpha_highlight = 0.8
                    max_dial.scale_basis = ring_root.get("jw_radius", 0.5) * 1.0
                    max_dial.line_width = 2
                    max_dial.use_draw_value = True
                    max_dial.use_draw_modal = True

                    # Store data for this joint
                    self.gizmo_data[target_name] = {
                        "target_obj": target_obj,
                        "ring_root": ring_root,
                        "min_dial": min_dial,
                        "max_dial": max_dial,
                        "axis_frame": obj,
                    }

                self.last_object_set = current_objects

            # Update gizmo bindings with validation (always do this to ensure bindings are current)
            for target_name, data in list(self.gizmo_data.items()):
                try:
                    target_obj = data["target_obj"]
                    min_dial = data["min_dial"]
                    max_dial = data["max_dial"]

                    # Validate objects still exist
                    if not target_obj or target_obj.name not in bpy.data.objects:
                        # Remove this entry if object no longer exists
                        self.gizmo_data.pop(target_name, None)
                        continue
                    if not hasattr(target_obj, "jw_rotation_limit_min_rna"):
                        continue

                    # Check if infinite limit is enabled by checking the actual limit values
                    # Limits can be stored as strings 'inf'/'-inf' or float inf/-inf
                    lower_limit = target_obj.get("pxr:usd:physics:joint:lowerLimit")
                    upper_limit = target_obj.get("pxr:usd:physics:joint:upperLimit")

                    has_infinite_limits = False
                    if lower_limit is not None:
                        if (isinstance(lower_limit, str) and lower_limit in ["inf", "-inf"]) or (
                            isinstance(lower_limit, float)
                            and (lower_limit == float("inf") or lower_limit == float("-inf"))
                        ):
                            has_infinite_limits = True
                    if upper_limit is not None:
                        if (isinstance(upper_limit, str) and upper_limit in ["inf", "-inf"]) or (
                            isinstance(upper_limit, float)
                            and (upper_limit == float("inf") or upper_limit == float("-inf"))
                        ):
                            has_infinite_limits = True

                    if not has_infinite_limits:
                        # Only bind gizmos to RNA properties if limits are not infinite
                        # This prevents users from accidentally turning off inf/-inf by manipulating the dials
                        min_dial.target_set_prop("offset", target_obj, "jw_rotation_limit_min_rna")
                        max_dial.target_set_prop("offset", target_obj, "jw_rotation_limit_max_rna")
                except Exception:
                    # If anything fails, remove this entry
                    self.gizmo_data.pop(target_name, None)
        except Exception:
            # Catch all to prevent crashes - but force rebuild next time
            self.last_object_set = set()

    def draw_prepare(self, context):
        """Called before drawing - renders arcs and positions gizmos"""
        try:
            if not hasattr(context.scene, "joint_attribute_props"):
                return

            props = context.scene.joint_attribute_props
            if not props.show_widgets:
                return

            # Get selected object names for context filtering
            selected_names = set(obj.name for obj in context.selected_objects if obj)

            # Update gizmo positions and draw arcs (only for selected objects)
            for target_name, data in list(self.gizmo_data.items()):
                try:
                    target_obj = data.get("target_obj")
                    ring_root = data.get("ring_root")
                    min_dial = data.get("min_dial")
                    max_dial = data.get("max_dial")

                    # Validate all required objects exist
                    if not target_obj or target_obj.name not in bpy.data.objects:
                        continue
                    if not ring_root or ring_root.name not in bpy.data.objects:
                        continue
                    if not min_dial or not max_dial:
                        continue

                    # Only draw if the target object is selected
                    if target_obj.name not in selected_names:
                        # Hide gizmos for unselected objects
                        min_dial.hide = True
                        max_dial.hide = True
                        continue

                    # Check if infinite limit is enabled by checking the actual limit values
                    # Limits can be stored as strings 'inf'/'-inf' or float inf/-inf
                    lower_limit = target_obj.get("pxr:usd:physics:joint:lowerLimit")
                    upper_limit = target_obj.get("pxr:usd:physics:joint:upperLimit")

                    has_infinite_limits = False
                    if lower_limit is not None:
                        if (isinstance(lower_limit, str) and lower_limit in ["inf", "-inf"]) or (
                            isinstance(lower_limit, float)
                            and (lower_limit == float("inf") or lower_limit == float("-inf"))
                        ):
                            has_infinite_limits = True
                    if upper_limit is not None:
                        if (isinstance(upper_limit, str) and upper_limit in ["inf", "-inf"]) or (
                            isinstance(upper_limit, float)
                            and (upper_limit == float("inf") or upper_limit == float("-inf"))
                        ):
                            has_infinite_limits = True

                    # Get common data
                    radius = ring_root.get("jw_radius", 0.5)
                    matrix = ring_root.matrix_world.copy()

                    if has_infinite_limits:
                        # Hide dial gizmos for infinite limits (can't manipulate infinite limits)
                        min_dial.hide = True
                        max_dial.hide = True

                        # Draw a full 360° circle to indicate infinite rotation (no limits)
                        # Draw filled full circle
                        draw_arc(matrix, 0.0, math.tau, radius=radius, color=(0.3, 0.6, 1.0, 0.15), segments=64)

                        # Draw full circle outline (thicker to indicate it's special)
                        draw_arc_outline(
                            matrix, 0.0, math.tau, radius=radius, color=(0.5, 0.8, 1.0, 0.6), segments=64, line_width=3
                        )

                        # Draw text label indicating infinite limits
                        text_radius = radius * 1.15
                        text_pos_local = Vector((text_radius, 0, 0))
                        text_pos_world = matrix @ text_pos_local
                        draw_3d_text(context, "∞ (Infinite)", text_pos_world, color=(0.5, 0.8, 1.0, 1.0), size=14)

                        # Continue to next joint (skip normal limit drawing)
                        continue

                    # Normal finite limits - draw interactive dial gizmos and limit arcs

                    # Check if a transform tool is active - hide dial gizmos but keep visuals
                    hide_dials = False
                    if context.space_data and context.space_data.show_gizmo:
                        try:
                            active_tool = context.workspace.tools.from_space_view3d_mode(context.mode)
                            if active_tool and active_tool.idname in [
                                "builtin.rotate",
                                "builtin.move",
                                "builtin.scale",
                                "builtin.transform",
                            ]:
                                hide_dials = True
                        except Exception:
                            pass

                    # Show/hide dial gizmos based on tool state
                    min_dial.hide = hide_dials
                    max_dial.hide = hide_dials

                    # Get angles from RNA properties
                    min_angle = getattr(target_obj, "jw_rotation_limit_min_rna", 0.0)
                    max_angle = getattr(target_obj, "jw_rotation_limit_max_rna", 0.0)

                    # Position dial gizmos (even if hidden, so they're ready when shown)
                    min_dial.matrix_basis = matrix
                    max_dial.matrix_basis = matrix

                    # Normalize angles for drawing
                    two_pi = math.tau
                    min_norm = min_angle % two_pi
                    max_norm = max_angle % two_pi
                    if max_norm < min_norm:
                        max_norm += two_pi

                    # Draw filled arc (larger radius)
                    draw_arc(matrix, min_norm, max_norm, radius=radius, color=(0.3, 0.6, 1.0, 0.25), segments=64)

                    # Draw arc outline (larger radius)
                    draw_arc_outline(
                        matrix, min_norm, max_norm, radius=radius, color=(0.5, 0.8, 1.0, 0.8), segments=64, line_width=2
                    )

                    # Draw full ring for reference (smaller radius)
                    draw_full_ring(matrix, radius=radius * 0.9, color=(0.3, 0.3, 0.3, 0.3), segments=64, line_width=1)

                    # Draw text labels for min and max angles
                    # Position text at the angle positions on the arc
                    text_radius = radius * 1.15  # Slightly outside the arc

                    # Min angle label position
                    min_x = text_radius * math.cos(min_angle)
                    min_y = text_radius * math.sin(min_angle)
                    min_text_pos_local = Vector((min_x, min_y, 0))
                    min_text_pos_world = matrix @ min_text_pos_local
                    min_text = f"{degrees(min_angle):.1f}°"
                    draw_3d_text(context, min_text, min_text_pos_world, color=(1.0, 0.4, 0.4, 1.0), size=14)

                    # Max angle label position
                    max_x = text_radius * math.cos(max_angle)
                    max_y = text_radius * math.sin(max_angle)
                    max_text_pos_local = Vector((max_x, max_y, 0))
                    max_text_pos_world = matrix @ max_text_pos_local
                    max_text = f"{degrees(max_angle):.1f}°"
                    draw_3d_text(context, max_text, max_text_pos_world, color=(0.4, 1.0, 0.4, 1.0), size=14)
                except Exception:
                    # If anything fails during drawing, skip this joint
                    pass
        except Exception:
            # Catch all to prevent crashes during drawing
            pass


# --------------------------
# Gizmo Group for Prismatic Joint Visualization
# --------------------------


class JW_GizmoGroup_Prismatic(bpy.types.GizmoGroup):
    """GPU-drawn visualization and arrow gizmos for prismatic joints"""

    bl_idname = "JW_GGT_prismatic_viz"
    bl_label = "Prismatic Joint Visualization"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"3D", "PERSISTENT"}

    @classmethod
    def poll(cls, context):
        """Only show if widgets are visible and there are prismatic joints"""
        if context.mode != "OBJECT":
            return False

        if not hasattr(context.scene, "joint_attribute_props"):
            return False

        props = context.scene.joint_attribute_props
        if not props.show_widgets:
            return False

        # Yield fully to standard transform tools so their widgets are not blocked
        try:
            active_tool = context.workspace.tools.from_space_view3d_mode(context.mode)
            if active_tool and active_tool.idname in [
                "builtin.rotate",
                "builtin.move",
                "builtin.scale",
                "builtin.transform",
            ]:
                return False
        except Exception:
            pass

        # Also yield when transform gizmo overlays are enabled in the viewport
        # (e.g. Select tool with Move/Rotate/Scale gizmos shown via the header overlay)
        try:
            sd = context.space_data
            if sd and (sd.show_gizmo_object_translate or sd.show_gizmo_object_rotate or sd.show_gizmo_object_scale):
                return False
        except Exception:
            pass

        # Check if any prismatic joint widgets exist
        for obj in bpy.data.objects:
            if obj.type == "EMPTY" and obj.get("joint_type") == "prismatic":
                return True
        # print("[Prismatic Gizmo] Poll returned False - no prismatic joints found")
        return False

    def setup(self, context):
        """Setup - gizmos will be managed dynamically in refresh"""
        self.gizmo_data = {}
        self.last_object_set = set()

    def refresh(self, context):
        """Update gizmos dynamically - recreate if scene objects changed"""
        try:
            # Get current set of prismatic joint objects
            current_objects = set()
            for obj in bpy.data.objects:
                if not obj or obj.type != "EMPTY" or obj.get("joint_type") != "prismatic":
                    continue

                target_name = obj.get("jw_target")
                if target_name:
                    target_obj = bpy.data.objects.get(target_name)
                    if target_obj and target_obj.name in bpy.data.objects:
                        current_objects.add((target_name, obj.name))

            # Always rebuild if the object set changed OR if we have objects but no gizmos
            needs_rebuild = (current_objects != self.last_object_set) or (
                len(current_objects) > 0 and len(self.gizmo_data) == 0
            )

            if needs_rebuild:
                # Clear old gizmos
                self.gizmo_data.clear()
                for gz in list(self.gizmos):
                    try:
                        self.gizmos.remove(gz)
                    except Exception:
                        pass

                # Create new gizmos for all prismatic joints
                for target_name, axis_frame_name in current_objects:
                    obj = bpy.data.objects.get(axis_frame_name)
                    target_obj = bpy.data.objects.get(target_name)

                    if not obj or obj.name not in bpy.data.objects:
                        continue
                    if not target_obj or target_obj.name not in bpy.data.objects:
                        continue

                    # Create arrow gizmos for min and max
                    try:
                        min_arrow = self.gizmos.new("GIZMO_GT_arrow_3d")
                        max_arrow = self.gizmos.new("GIZMO_GT_arrow_3d")
                    except Exception:
                        continue

                    # Visual settings for min arrow (red)
                    min_arrow.color = (1.0, 0.4, 0.4)
                    min_arrow.alpha = 0.5
                    min_arrow.alpha_highlight = 0.8
                    min_arrow.length = 0.3
                    min_arrow.use_draw_value = True

                    # Visual settings for max arrow (green)
                    max_arrow.color = (0.4, 1.0, 0.4)
                    max_arrow.alpha = 0.5
                    max_arrow.alpha_highlight = 0.8
                    max_arrow.length = 0.3
                    max_arrow.use_draw_value = True

                    # Store data for this joint
                    self.gizmo_data[target_name] = {
                        "target_obj": target_obj,
                        "axis_frame": obj,
                        "min_arrow": min_arrow,
                        "max_arrow": max_arrow,
                    }

                self.last_object_set = current_objects

            # Update gizmo bindings
            for target_name, data in list(self.gizmo_data.items()):
                try:
                    target_obj = data["target_obj"]
                    min_arrow = data["min_arrow"]
                    max_arrow = data["max_arrow"]

                    if not target_obj or target_obj.name not in bpy.data.objects:
                        self.gizmo_data.pop(target_name, None)
                        continue
                    if not hasattr(target_obj, "jw_translation_limit_min_rna"):
                        continue

                    # Link gizmos to RNA properties
                    min_arrow.target_set_prop("offset", target_obj, "jw_translation_limit_min_rna")
                    max_arrow.target_set_prop("offset", target_obj, "jw_translation_limit_max_rna")
                except Exception:
                    self.gizmo_data.pop(target_name, None)
        except Exception:
            self.last_object_set = set()

    def draw_prepare(self, context):
        """Called before drawing - renders lines and positions gizmos"""
        try:
            if not hasattr(context.scene, "joint_attribute_props"):
                return

            props = context.scene.joint_attribute_props
            if not props.show_widgets:
                return

            # Get selected object names
            selected_names = set(obj.name for obj in context.selected_objects if obj)

            # Update gizmo positions and draw visualizations
            for target_name, data in list(self.gizmo_data.items()):
                try:
                    target_obj = data.get("target_obj")
                    axis_frame = data.get("axis_frame")
                    min_arrow = data.get("min_arrow")
                    max_arrow = data.get("max_arrow")

                    if not target_obj or target_obj.name not in bpy.data.objects:
                        continue
                    if not axis_frame or axis_frame.name not in bpy.data.objects:
                        continue
                    if not min_arrow or not max_arrow:
                        continue

                    # Only draw if the target object is selected
                    if target_obj.name not in selected_names:
                        min_arrow.hide = True
                        max_arrow.hide = True
                        continue

                    # Check if transform tool is active
                    hide_arrows = False
                    if context.space_data and context.space_data.show_gizmo:
                        try:
                            active_tool = context.workspace.tools.from_space_view3d_mode(context.mode)
                            if active_tool and active_tool.idname in [
                                "builtin.rotate",
                                "builtin.move",
                                "builtin.scale",
                                "builtin.transform",
                            ]:
                                hide_arrows = True
                        except Exception:
                            pass

                    min_arrow.hide = hide_arrows
                    max_arrow.hide = hide_arrows

                    # Get distances from RNA properties
                    min_dist = getattr(target_obj, "jw_translation_limit_min_rna", -1.0)
                    max_dist = getattr(target_obj, "jw_translation_limit_max_rna", 1.0)

                    # Get the initial offset from the axis_frame metadata
                    # This was stored when the constraint was created and should not change
                    # If not found (old setup), fall back to calculating from midpoint
                    initial_offset = axis_frame.get("jw_initial_offset", (min_dist + max_dist) / 2.0)

                    # For visualization, we want to show the range centered at zero in the axis_frame
                    # So we need to subtract the initial offset
                    visual_min = min_dist - initial_offset
                    visual_max = max_dist - initial_offset

                    # Use axis_frame's world matrix for drawing
                    # The limits are FIXED positions in the axis_frame's local space
                    matrix = axis_frame.matrix_world.copy()

                    # TODO: WHY IS THIS SO FUCKING HARD...
                    # Position arrow gizmos at the fixed limit positions
                    # The offset property of the arrow gizmo controls distance along its local Z-axis
                    # The gizmos are bound to RNA properties (via target_set_prop), which control their offset

                    # Min arrow (pointing in negative direction)
                    # Since it's flipped 180°, its local +Z points in the opposite direction
                    min_matrix = matrix.copy()
                    min_matrix @= Matrix.Rotation(math.pi, 4, "X")  # Flip to point negative

                    # Compensate for the flipped offset direction
                    min_matrix.translation = matrix.translation + matrix.to_3x3() @ Vector(
                        (0, 0, visual_min + min_dist)
                    )
                    min_arrow.matrix_basis = min_matrix

                    # Max arrow (pointing in positive direction)
                    # The RNA binding uses max_dist, and we want it positioned at visual_max
                    # So: base + max_dist = visual_max
                    # base = visual_max - max_dist = -initial_offset
                    max_matrix = matrix.copy()
                    max_matrix.translation = matrix.translation + matrix.to_3x3() @ Vector((0, 0, -initial_offset))
                    max_arrow.matrix_basis = max_matrix

                    # Draw main line segment at the visual limit positions
                    draw_line_segment(matrix, visual_min, visual_max, color=(0.3, 0.6, 1.0, 0.6), line_width=5)

                    # Draw guide rails
                    draw_rail_guides(matrix, visual_min, visual_max, color=(0.4, 0.4, 0.4, 0.4), num_guides=5)

                    # Draw markers at limits
                    draw_limit_marker(matrix, visual_min, color=(1.0, 0.4, 0.4, 0.8), size=0.15)
                    draw_limit_marker(matrix, visual_max, color=(0.4, 1.0, 0.4, 0.8), size=0.15)

                    # Draw text labels
                    text_offset = 0.2
                    min_text_pos_local = Vector((0, 0, visual_min - text_offset))
                    min_text_pos_world = matrix @ min_text_pos_local
                    min_text = f"{min_dist:.2f}m"
                    draw_3d_text(context, min_text, min_text_pos_world, color=(1.0, 0.4, 0.4, 1.0), size=14)

                    max_text_pos_local = Vector((0, 0, visual_max + text_offset))
                    max_text_pos_world = matrix @ max_text_pos_local
                    max_text = f"{max_dist:.2f}m"
                    draw_3d_text(context, max_text, max_text_pos_world, color=(0.4, 1.0, 0.4, 1.0), size=14)

                except Exception:
                    pass
        except Exception:
            pass


# --------------------------
# Overlap Detection - Data Classes
# --------------------------


@dataclass
class EvalMesh:
    obj: bpy.types.Object
    mesh: bpy.types.Mesh
    world_verts: list
    loop_tris: list
    bvh: BVHTree
    tri2poly: list


# --------------------------
# Overlap Detection - Internal Methods
# --------------------------


def _evaluated_mesh_worldspace(obj, depsgraph) -> tuple:
    """Return mesh + world-space data for obj (with modifiers applied)."""
    eval_obj = obj.evaluated_get(depsgraph)
    me = bpy.data.meshes.new_from_object(eval_obj, preserve_all_data_layers=True, depsgraph=depsgraph)
    me.calc_loop_triangles()
    mw = obj.matrix_world
    world_verts = [mw @ v.co for v in me.vertices]
    return me, world_verts, list(me.loop_triangles)


def _build_bvh(world_verts, loop_tris) -> tuple[BVHTree, list[int]]:
    tri_indices = [tuple(lt.vertices) for lt in loop_tris]

    # Ensure we have valid data
    if not tri_indices or not world_verts:
        return BVHTree.FromPolygons([], []), []

    try:
        bvh = BVHTree.FromPolygons(world_verts, tri_indices, all_triangles=True)
    except Exception as e:
        print(f"BVH creation failed: {e}")
        return BVHTree.FromPolygons([], []), []

    tri2poly = [lt.polygon_index for lt in loop_tris]
    return bvh, tri2poly


def _prepare_eval_cache(objs) -> dict[str, EvalMesh]:
    # Force depsgraph update to ensure we have the latest object state
    bpy.context.view_layer.update()
    bpy.context.evaluated_depsgraph_get().update()
    # Force a second update after getting the depsgraph
    dg = bpy.context.evaluated_depsgraph_get()
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    cache = {}
    try:
        for o in objs:
            me, wv, lt = _evaluated_mesh_worldspace(o, dg)
            bvh, tri2poly = _build_bvh(wv, lt)
            cache[o.name_full] = EvalMesh(o, me, wv, lt, bvh, tri2poly)
        return cache
    except Exception as e:
        # clean up anything already created
        for em in cache.values():
            if em.mesh and em.mesh.users == 0:
                bpy.data.meshes.remove(em.mesh, do_unlink=True)
        raise e


def _free_eval_cache(cache) -> None:
    for em in cache.values():
        if em.mesh:
            bpy.data.meshes.remove(em.mesh, do_unlink=True)


def _select_faces(obj, poly_indices) -> None:
    """
    Select a list of polygon indices on a single object.
    Updated to work better with multi-object workflows.

    Args:
        obj (bpy.types.Object): The object to select the faces on
        poly_indices (list[int]): The list of polygon indices to select
    """
    if not poly_indices:
        return

    # Store the current context
    prev_mode = bpy.context.mode
    prev_active = bpy.context.active_object  # noqa F841
    prev_selected = bpy.context.selected_objects.copy()

    # Switch to object mode to access mesh data
    bpy.ops.object.mode_set(mode="OBJECT")

    # Make sure the target object is selected and active
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    # Clear all face selections first
    for p in obj.data.polygons:
        p.select = False

    # Select the specified faces
    for idx in poly_indices:
        if 0 <= idx < len(obj.data.polygons):
            obj.data.polygons[idx].select = True

    # Update mesh data
    obj.data.update()

    # Restore previous context if we were in edit mode
    if prev_mode == "EDIT_MESH":
        # If we had multiple objects selected before, restore that selection
        if len(prev_selected) > 1:
            for prev_obj in prev_selected:
                if prev_obj != obj:
                    prev_obj.select_set(True)

        # Switch back to edit mode
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.context.tool_settings.mesh_select_mode = (False, False, True)
    else:
        bpy.ops.object.mode_set(mode=prev_mode)


def _select_faces_multi_object(faces_to_select) -> None:
    """
    Select faces on multiple objects simultaneously in multi-object edit mode.

    Args:
        faces_to_select (dict): Dictionary mapping objects to their face indices
                               {obj: set/list of face indices}
    """
    if not faces_to_select:
        return

    # Ensure we're in object mode first
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    # Clear all selections first
    bpy.ops.object.select_all(action="DESELECT")

    # Clear face selections on all objects and select the objects
    objects_to_edit = []
    for obj, face_indices in faces_to_select.items():
        if face_indices:  # Only include objects that have faces to select
            # Clear all face selections on this object first
            for p in obj.data.polygons:
                p.select = False

            # Select the specified faces
            for idx in face_indices:
                if 0 <= idx < len(obj.data.polygons):
                    obj.data.polygons[idx].select = True

            # Update the mesh data
            obj.data.update()

            # Select the object for multi-object edit mode
            obj.select_set(True)
            objects_to_edit.append(obj)

    # Set active object to the first one with selections
    if objects_to_edit:
        bpy.context.view_layer.objects.active = objects_to_edit[0]

        # Switch to edit mode (this will include all selected objects)
        bpy.ops.object.mode_set(mode="EDIT")

        # Set face select mode
        bpy.context.tool_settings.mesh_select_mode = (False, False, True)


def triangles_intersect(va0, va1, va2, vb0, vb1, vb2, tolerance=1e-6) -> bool:
    """
    Test if two triangles intersect in 3D space.
    Uses separating axis theorem for accurate intersection testing.
    """
    try:
        # Test triangle A against plane of triangle B
        normal_b = (vb1 - vb0).cross(vb2 - vb0).normalized()

        # Distance of triangle A vertices from plane B
        d0 = (va0 - vb0).dot(normal_b)
        d1 = (va1 - vb0).dot(normal_b)
        d2 = (va2 - vb0).dot(normal_b)

        # If all vertices are on same side of plane (with tolerance), no intersection
        if (d0 > tolerance and d1 > tolerance and d2 > tolerance) or (
            d0 < -tolerance and d1 < -tolerance and d2 < -tolerance
        ):
            return False

        # Test triangle B against plane of triangle A
        normal_a = (va1 - va0).cross(va2 - va0).normalized()

        d0 = (vb0 - va0).dot(normal_a)
        d1 = (vb1 - va0).dot(normal_a)
        d2 = (vb2 - va0).dot(normal_a)

        if (d0 > tolerance and d1 > tolerance and d2 > tolerance) or (
            d0 < -tolerance and d1 < -tolerance and d2 < -tolerance
        ):
            return False

        # More detailed intersection testing could go here
        # For now, if we pass both plane tests, assume intersection
        return True

    except Exception:
        # If there's any error (e.g., degenerate triangles), assume no intersection
        return False


def overlap_pairs_precise(em_a: EvalMesh, em_b: EvalMesh, tolerance=1e-6):
    """
    More precise intersection detection using actual geometry intersection.
    This should reduce false positives from BVH overlap.
    """
    overlaps = em_a.bvh.overlap(em_b.bvh)  # Still start with BVH for performance
    polys_a = set()
    polys_b = set()

    if not overlaps:
        return polys_a, polys_b

    t2p_a = em_a.tri2poly
    t2p_b = em_b.tri2poly
    wv_a = em_a.world_verts
    wv_b = em_b.world_verts

    # For each BVH overlap, test actual triangle intersection
    for ta, tb in overlaps:
        # Get triangle vertices
        tri_a = em_a.loop_tris[ta]
        tri_b = em_b.loop_tris[tb]

        va0, va1, va2 = [Vector(wv_a[i]) for i in tri_a.vertices]
        vb0, vb1, vb2 = [Vector(wv_b[i]) for i in tri_b.vertices]

        # Test if triangles actually intersect (not just bounding boxes)
        if triangles_intersect(va0, va1, va2, vb0, vb1, vb2, tolerance):
            polys_a.add(t2p_a[ta])
            polys_b.add(t2p_b[tb])

    return polys_a, polys_b


def _overlap_pairs(em_a: EvalMesh, em_b: EvalMesh, method="precise", **kwargs):
    """
    Main intersection detection function with selectable methods.

    Args:
        em_a, em_b: EvalMesh objects to compare
        method: 'original', 'precise', 'distance', or 'polygon'
        **kwargs: Additional parameters for specific methods
    """
    if method == "precise":
        tolerance = kwargs.get("tolerance", 1e-6)
        return overlap_pairs_precise(em_a, em_b, tolerance)
    else:
        raise ValueError(f"Unknown method: {method}")


# --------------------------
# Operators
# --------------------------


class SRVIZ_OT_OT_find_intersections_multi(Operator):
    """Find intersecting faces across multiple selected mesh objects"""

    bl_idname = "sr_viz.find_intersections_multi"
    bl_label = "Find Intersections"
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        name="Mode",
        description="How to compare selected objects",
        items=[
            ("ACTIVE", "Active vs Others", "Intersect the active mesh against all other selected meshes"),
            ("PAIRWISE", "Pairwise (All vs All)", "Intersect every selected mesh against every other selected mesh"),
        ],
        default="ACTIVE",
    )

    select_faces_only: bpy.props.BoolProperty(
        name="Select Faces", description="Select faces that intersect", default=True
    )

    multi_object_edit: bpy.props.BoolProperty(
        name="Multi-Object Edit Mode",
        description="Select all objects and their faces simultaneously in edit mode",
        default=True,
    )

    def draw(self, context):
        col = self.layout.column(align=True)
        col.prop(self, "mode")
        col.prop(self, "select_faces_only")
        if self.select_faces_only:
            col.prop(self, "multi_object_edit")

    def execute(self, context):

        # Force scene update before anything else
        bpy.context.scene.update_tag()
        bpy.context.view_layer.update()

        # Force evaluation of all selected objects
        for obj in context.selected_objects:
            if obj.type == "MESH":
                obj.update_tag(refresh={"OBJECT", "DATA"})

        # Filter objects to only include those in Export/Geometry collection structure
        sel_meshes = []
        for o in context.selected_objects:
            if o.type == "MESH":
                # Check if object is in a "Geometry" collection that is a child of "Export"
                in_export_geometry = False
                for collection in o.users_collection:
                    # Check if this collection is named "Geometry"
                    if collection.name == "Geometry":
                        # Check if this Geometry collection is a child of Export
                        # We need to check if Export collection contains this Geometry collection
                        export_collection = bpy.data.collections.get("Export")
                        if export_collection:
                            # Check if the Geometry collection is in the Export collection's children
                            for child_collection in export_collection.children:
                                if child_collection == collection:
                                    in_export_geometry = True
                                    break
                        if in_export_geometry:
                            break

                if in_export_geometry:
                    sel_meshes.append(o)

        if len(sel_meshes) < 2:
            self.report(
                {"ERROR"},
                "No objects found within Export/Geometry collection. Select at least two mesh objects from the Export/Geometry collection.",
            )
            return {"CANCELLED"}
        if self.mode == "ACTIVE" and context.active_object not in sel_meshes:
            self.report({"ERROR"}, "Make one of the selected meshes from Export/Geometry collection the Active object.")
            return {"CANCELLED"}

        # Final update
        time.sleep(0.1)
        bpy.context.view_layer.update()
        bpy.context.evaluated_depsgraph_get().update()

        # Precompute BVHs for all selected meshes
        cache = _prepare_eval_cache(sel_meshes)
        try:
            # For each object, collect intersecting face indices (union across pairs)
            intersect_faces = {o.name_full: set() for o in sel_meshes}

            pairs = []
            if self.mode == "ACTIVE":
                a = context.active_object
                others = [o for o in sel_meshes if o != a]
                pairs = [(a, o) for o in others]
            else:  # PAIRWISE
                pairs = list(combinations(sel_meshes, 2))

            total_pairs = 0
            for o1, o2 in pairs:
                em1 = cache[o1.name_full]
                em2 = cache[o2.name_full]
                polys1, polys2 = _overlap_pairs(em1, em2)
                if polys1 or polys2:
                    intersect_faces[o1.name_full].update(polys1)
                    intersect_faces[o2.name_full].update(polys2)
                total_pairs += 1

            # Apply selections
            affected_counts = []
            hit_objects = []
            faces_to_select = {}  # Dictionary to store faces per object

            for obj in sel_meshes:
                faces = intersect_faces[obj.name_full]
                if self.select_faces_only and faces:
                    faces_to_select[obj] = faces
                affected_counts.append((obj.name, len(faces)))
                if len(faces) > 0:
                    hit_objects.append(obj)

            # Report summary
            hit_objs = [f"{n}({c})" for n, c in affected_counts if c > 0]
            if hit_objs:
                self.report(
                    {"INFO"}, "Intersections found on: " + ", ".join(hit_objs) + f". Pairs tested: {total_pairs}."
                )

                print(f"Faces to select: {faces_to_select}")

                if self.select_faces_only and faces_to_select:
                    if self.multi_object_edit:
                        # NEW: Use improved multi-object face selection
                        _select_faces_multi_object(faces_to_select)

                        # Enable xray mode for better visibility
                        if hasattr(bpy.context.space_data, "shading"):
                            bpy.context.space_data.shading.show_xray = True

                    else:
                        # ORIGINAL: Select faces on each object individually
                        if bpy.context.mode != "OBJECT":
                            bpy.ops.object.mode_set(mode="OBJECT")

                        bpy.ops.object.select_all(action="DESELECT")
                        for obj in hit_objects:
                            obj.select_set(True)

                        # Set the first hit object as active and switch to edit mode
                        if hit_objects:
                            bpy.context.view_layer.objects.active = hit_objects[0]
                            bpy.ops.object.mode_set(mode="EDIT")

                            # Enable xray mode
                            if hasattr(bpy.context.space_data, "shading"):
                                bpy.context.space_data.shading.show_xray = True

                            # Select faces on each object individually
                            for obj, faces in faces_to_select.items():
                                _select_faces(obj, faces)

            else:
                self.report({"INFO"}, f"No intersections detected. Pairs tested: {total_pairs}.")
            return {"FINISHED"}

        except Exception as e:
            self.report({"ERROR"}, f"Error: {e}")
            return {"CANCELLED"}
        finally:
            _free_eval_cache(cache)


class JW_OT_delete_widgets(Operator):
    """Delete widgets associated with the active object (keeps the constraint)."""

    bl_idname = "jw.delete_widgets"
    bl_label = "Delete Widgets"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({"ERROR"}, "Select the constrained object first.")
            return {"CANCELLED"}

        frames = [ob for ob in bpy.data.objects if ob.type == "EMPTY" and ob.get("jw_target") == obj.name]

        if not frames:
            self.report({"INFO"}, "No widgets found for this object.")
            return {"CANCELLED"}

        for fr in frames:
            # Delete children recursively
            def delete_with_children(o):
                for ch in list(o.children):
                    delete_with_children(ch)
                if o.name in bpy.data.objects:
                    bpy.data.objects.remove(o, do_unlink=True)

            delete_with_children(fr)

        self.report({"INFO"}, "Deleted joint widgets for active object.")
        return {"FINISHED"}


class JW_OT_sync_handles_from_limits(Operator):
    """Sync properties to match current constraint values."""

    bl_idname = "jw.sync_handles_from_limits"
    bl_label = "Sync Properties from Limits"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({"ERROR"}, "No active object.")
            return {"CANCELLED"}

        con = next((c for c in obj.constraints if c.name == LIMIT_CONSTRAINT_NAME), None)
        if not con:
            self.report({"ERROR"}, "No JointLimit constraint on the active object.")
            return {"CANCELLED"}

        frames = [ob for ob in bpy.data.objects if ob.type == "EMPTY" and ob.get("jw_target") == obj.name]
        if not frames:
            self.report({"ERROR"}, "No widgets found for this object.")
            return {"CANCELLED"}

        frame = frames[0]
        jtype = frame.get("jw_type", "PRISMATIC")

        if jtype == "PRISMATIC":
            hmin = frame.children.get(f"Min_{obj.name}")
            hmax = frame.children.get(f"Max_{obj.name}")
            if hmin:
                hmin.location.z = getattr(con, "min_z", 0.0)
            if hmax:
                hmax.location.z = getattr(con, "max_z", 0.0)

        else:  # REVOLUTE
            # Sync constraint values to RNA properties based on axis
            frame = frames[0]
            axis = frame.get("jw_axis", "Z")

            if hasattr(obj, "jw_rotation_limit_min_rna"):
                if axis == "X":
                    obj.jw_rotation_limit_min_rna = getattr(con, "min_x", 0.0)
                    obj.jw_rotation_limit_max_rna = getattr(con, "max_x", 0.0)
                elif axis == "Y":
                    obj.jw_rotation_limit_min_rna = getattr(con, "min_y", 0.0)
                    obj.jw_rotation_limit_max_rna = getattr(con, "max_y", 0.0)
                else:  # 'Z'
                    obj.jw_rotation_limit_min_rna = getattr(con, "min_z", 0.0)
                    obj.jw_rotation_limit_max_rna = getattr(con, "max_z", 0.0)

        self.report({"INFO"}, "Synced properties from current limits.")
        return {"FINISHED"}


class JW_OT_reset_to_default(Operator):
    """Reset object to its default position/rotation captured when joint was created."""

    bl_idname = "jw.reset_to_default"
    bl_label = "Reset to Default Pose"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({"ERROR"}, "No active object.")
            return {"CANCELLED"}

        # Check if object has joint widgets
        frames = [ob for ob in bpy.data.objects if ob.type == "EMPTY" and ob.get("jw_target") == obj.name]
        if not frames:
            self.report({"ERROR"}, "No joint widgets found for this object. Create a joint first.")
            return {"CANCELLED"}

        frame = frames[0]
        jtype = frame.get("jw_type", "PRISMATIC")

        if jtype == "PRISMATIC":
            # Reset translation
            if hasattr(obj, "jw_translation_default"):
                obj.location = obj.jw_translation_default.copy()
                self.report({"INFO"}, "Reset to default translation.")
            else:
                self.report({"WARNING"}, "No default translation stored.")
                return {"CANCELLED"}
        else:  # REVOLUTE
            # Reset rotation
            if hasattr(obj, "jw_rotation_default"):
                obj.rotation_euler = obj.jw_rotation_default.copy()
                self.report({"INFO"}, "Reset to default rotation.")
            else:
                self.report({"WARNING"}, "No default rotation stored.")
                return {"CANCELLED"}

        return {"FINISHED"}
