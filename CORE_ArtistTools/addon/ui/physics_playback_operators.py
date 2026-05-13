# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import math
import time

import bpy
from bpy.props import FloatProperty
from bpy.types import Operator
from bpy_extras import view3d_utils
from mathutils import Vector

# Global storage for original states
_original_states = {}
_simulation_started = False
_state = {"was_playing": False}

# Handlers
# @persistent
# def on_playback_pre(scene):
#     capture(scene)


# def capture(scene):
#     # Are we currently playing?
#     scr = bpy.context.screen
#     playing = bool(scr and getattr(scr, "is_animation_playing", False))

#     # Trigger only on the rising edge (play button just pressed / spacebar toggled on)
#     if playing and not _state["was_playing"]:
#         print(f"[capture] Start playback @ frame {scene.frame_current} - Capturing all rigid bodies")

#         # Clear existing states
#         throw_rb_props = scene.throw_rb_props
#         throw_rb_props.rigid_body_states.clear()

#         # Scan all objects in the scene for rigid bodies
#         rigid_body_count = 0
#         for obj in bpy.data.objects:
#             if obj.rigid_body:
#                 rigid_body_count += 1

#                 # Get object-space transform
#                 loc_obj = obj.location.copy()
#                 if obj.rotation_mode == 'QUATERNION':
#                     rot_eul = obj.rotation_quaternion.to_euler()
#                 elif obj.rotation_mode == 'AXIS_ANGLE':
#                     ang, x, y, z = obj.rotation_axis_angle
#                     rot_eul = Quaternion((x, y, z), ang).to_euler()
#                 else:
#                     rot_eul = obj.rotation_euler.copy()

#                 # Create new state entry
#                 state_entry = throw_rb_props.rigid_body_states.add()
#                 state_entry.object_name = obj.name
#                 state_entry.location = list(loc_obj)
#                 state_entry.rotation = list(rot_eul)
#                 state_entry.scale = list(obj.scale)
#                 state_entry.kinematic = bool(obj.rigid_body.kinematic)
#                 state_entry.use_deactivation = bool(obj.rigid_body.use_deactivation)

#                 print(f"[capture] Captured {obj.name}: loc={loc_obj}, rot={rot_eul}, scale={obj.scale}")

#         print(f"[capture] Captured {rigid_body_count} rigid bodies total")

#         # Also store the active object for backward compatibility
#         active_obj = bpy.context.active_object
#         if active_obj and active_obj.rigid_body:
#             throw_rb_props.throw_rb_init_obj_name = active_obj.name
#             throw_rb_props.throw_rb_init_location = list(active_obj.location)
#             if active_obj.rotation_mode == 'QUATERNION':
#                 rot_eul = active_obj.rotation_quaternion.to_euler()
#             elif active_obj.rotation_mode == 'AXIS_ANGLE':
#                 ang, x, y, z = active_obj.rotation_axis_angle
#                 rot_eul = Quaternion((x, y, z), ang).to_euler()
#             else:
#                 rot_eul = active_obj.rotation_euler.copy()
#             throw_rb_props.throw_rb_init_rotation = list(rot_eul)
#             throw_rb_props.throw_rb_init_scale = list(active_obj.scale)
#             throw_rb_props.throw_rb_init_kinematic = bool(active_obj.rigid_body.kinematic)
#             throw_rb_props.throw_rb_init_use_deactivation = bool(active_obj.rigid_body.use_deactivation)

#     _state["was_playing"] = playing


def _has_active_rb(obj) -> bool:
    return obj and obj.rigid_body and obj.rigid_body.type == "ACTIVE"


# class SR_Psy_OT_restore_all_rigidbodies(Operator):
#     bl_idname = "sr_psy_core.restore_all_rigidbodies"
#     bl_label = "Restore All Rigid Bodies to Original Positions"
#     bl_description = "Restore all rigid bodies to their original captured positions"
#     bl_options = {'REGISTER', 'UNDO'}

#     @classmethod
#     def poll(cls, context):
#         props = context.scene.throw_rb_props
#         return len(props.rigid_body_states) > 0

#     def execute(self, context):
#         scene = context.scene
#         props = scene.throw_rb_props

#         restored_count = 0
#         for state in props.rigid_body_states:
#             obj = bpy.data.objects.get(state.object_name)
#             if obj and obj.rigid_body:
#                 # Restore transform
#                 obj.location = list(state.location)
#                 obj.rotation_euler = list(state.rotation)
#                 obj.scale = list(state.scale)

#                 # Restore rigid body properties
#                 obj.rigid_body.kinematic = state.kinematic
#                 obj.rigid_body.use_deactivation = state.use_deactivation

#                 # Force update
#                 obj.update_tag()
#                 restored_count += 1

#                 print(f"Debug: Restored {obj.name} to original position")

#         self.report({'INFO'}, f'Restored {restored_count} rigid bodies to original positions')
#         return {'FINISHED'}


# class SR_Psy_OT_restore_rigidbody(Operator):
#     bl_idname = "sr_psy_core.restore_rigidbody"
#     bl_label = "Restore the original position of the last thrown rigidbody"
#     bl_options = {'REGISTER', 'UNDO'}

#     @classmethod
#     def poll(cls, context):
#         props = context.scene.throw_rb_props
#         return (props.throw_rb_init_obj_name and
#                 props.throw_rb_init_obj_name in bpy.data.objects)

#     def execute(self, context):
#         scene = context.scene
#         props = scene.throw_rb_props
#         obj_name = props.throw_rb_init_obj_name
#         if not obj_name or obj_name not in bpy.data.objects:
#             self.report({'WARNING'}, 'No last thrown rigidbody found')
#             return {'CANCELLED'}

#         obj = bpy.data.objects.get(obj_name)

#         # Restore transform - convert bpy_prop_array to list
#         print(f"Debug: Restoring object {obj_name}")
#         print(f"Debug: Stored location: {props.throw_rb_init_location}")
#         print(f"Debug: Stored rotation: {props.throw_rb_init_rotation}")
#         print(f"Debug: Stored scale: {props.throw_rb_init_scale}")

#         # Set world position directly
#         obj.matrix_world.translation = list(props.throw_rb_init_location)
#         obj.rotation_euler = list(props.throw_rb_init_rotation)
#         obj.scale = list(props.throw_rb_init_scale)

#         print(f"Debug: After restore - Location: {obj.location}")
#         print(f"Debug: After restore - Rotation: {obj.rotation_euler}")
#         print(f"Debug: After restore - World Matrix Translation: {obj.matrix_world.translation}")

#         # Restore rigid body properties
#         if obj.rigid_body:
#             obj.rigid_body.kinematic = props.throw_rb_init_kinematic
#             obj.rigid_body.use_deactivation = props.throw_rb_init_use_deactivation

#         # Force update
#         obj.update_tag()

#         self.report({'INFO'}, f'Restored {obj_name} to original position')
#         return {'FINISHED'}


class SR_Psy_OT_throw_rigidbody(Operator):
    bl_idname = "sr_psy_core.throw_rigidbody"
    bl_label = "Throw Rigid Body (Shift+RMB) while simulation is running"
    bl_description = "Throw the selected rigidbody"
    bl_options = {"REGISTER"}

    speed_scale: FloatProperty(
        name="Speed Scale",
        description="Multiplier from screen drag (at object depth) to world velocity (in m/s)",
        default=12.0,
        min=0.0,
        soft_max=100.0,
    )

    max_speed: FloatProperty(
        name="Max Speed", description="Clamp linear speed (in m/s)", default=50.0, min=0.0, soft_max=500.0
    )

    # runtime vars
    _start_xy = None
    _start_time = None
    _last_xy = None
    _last_time = None
    _obj = None
    _depth_loc = None
    _start_world = None
    _last_world = None
    _was_kinematic = None
    _release_scheduled = None

    def invoke(self, context, event) -> set:
        region = context.region
        # Info: context.region data will give you access to the view matrix on viewport
        rv3d = context.region_data
        if region is None or rv3d is None:
            self.report({"WARNING"}, "Run from a 3D Viewport!")
            return {"CANCELLED"}

        # Try picking what's under your cursor, if None, use active object
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, (event.mouse_region_x, event.mouse_region_y))
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, (event.mouse_region_x, event.mouse_region_y))
        hit, loc, normal, face_index, obj, _ = context.scene.ray_cast(
            context.evaluated_depsgraph_get(), origin, direction
        )
        if hit and _has_active_rb(obj):
            self._obj = obj
        else:
            self._obj = context.object if _has_active_rb(context.object) else None

        if not _has_active_rb(self._obj):
            self.report({"WARNING"}, "Need an active rigidbody to throw!")
            return {"CANCELLED"}

        # Use the original state that was captured when playback started
        self._obj_name = self._obj.name
        print(f"Debug: Looking for original state for {self._obj_name}")

        # Check if we have stored original state from playback start
        if self._obj_name in _original_states:
            stored_state = _original_states[self._obj_name]
            self._original_world_matrix = stored_state["world_matrix"]
            self._original_location = stored_state["location"]
            self._original_rotation = stored_state["rotation_euler"]
            self._original_scale = stored_state["scale"]
            self._original_kinematic = stored_state["kinematic"]
            self._original_use_deactivation = stored_state["use_deactivation"]
            print("Debug: Using stored original state from playback start")
        else:
            # Fallback: capture current state if no stored state found
            print("Debug: No stored state found, capturing current state as fallback")
            self._original_world_matrix = self._obj.matrix_world.copy()
            self._original_location = self._obj.location.copy()
            self._original_rotation = self._obj.rotation_euler.copy()
            self._original_scale = self._obj.scale.copy()
            rb = self._obj.rigid_body
            self._original_kinematic = bool(rb.kinematic)
            self._original_use_deactivation = bool(rb.use_deactivation)

        print(f"Debug: Original state - Location: {self._original_location}")
        print(f"Debug: Original state - Rotation: {self._original_rotation}")
        print(f"Debug: Original state - World Matrix Translation: {self._original_world_matrix.translation}")

        # Now start the drag operation
        self._depth_loc = self._obj.matrix_world.translation.copy()
        self._start_xy = Vector((event.mouse_region_x, event.mouse_region_y))
        self._last_xy = self._start_xy.copy()

        # perf_counter is a monotonic clock value.  Needed stable clock to not be affected by internal ticks
        now = time.perf_counter()
        self._start_time = now
        self._last_time = now

        # blender 4.0+ has removed the ability to add linear impulse dynamically. Or I cannot find similar method to blender 3.x
        # setting to kinematic while user is dragging.

        rb.kinematic = True
        # from claude: added this to prevent object from falling asleep
        rb.use_deactivation = False
        self._start_world = self._obj.matrix_world.translation.copy()
        self._last_world = self._start_world.copy()
        self._start_world = self._obj.matrix_world.translation.copy()
        self._last_world = self._start_world.copy()

        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _screen_to_world_at_depth(self, context, xy) -> Vector:
        """
        converting screen coordinates to world coordinates at the depth of the object
        locks the grabbed object in Z plane..makes mouse drags feel a little more natural
        Args:
            context: bpy.context
            xy: tuple of (x, y) screen coordinates
        Returns:
            tuple of (x, y, z) world coordinates
        """
        region = context.region
        rv3d = context.region_data
        return view3d_utils.region_2d_to_location_3d(region, rv3d, xy, self._depth_loc)

    def modal(self, context, event) -> set:
        if event.type == "MOUSEMOVE":
            xy = Vector((event.mouse_region_x, event.mouse_region_y))
            world = self._screen_to_world_at_depth(context, xy)
            self._obj.location = world
            self._last_xy = xy
            self._last_world = world.copy()
            self._last_time = time.perf_counter()
            return {"RUNNING_MODAL"}

        # End mouse events
        if event.type == "RIGHTMOUSE" and event.value == "RELEASE":
            scene = context.scene

            # compute velocity from drag path
            dt = max(1e-4, self._last_time - self._start_time)
            v_est = (self._last_world - self._start_world) / dt

            # scale and clamp
            v = v_est * self.speed_scale
            speed = v.length
            if speed > self.max_speed > 0:
                v *= self.max_speed / speed

            rb = self._obj.rigid_body

            if context.screen.is_animation_playing:
                # hold kinematic state for 1 frame, then release back to physics
                if not self._release_scheduled:

                    def _release_on_next(scene):
                        if self._obj and self._obj.rigid_body:
                            self._obj.rigid_body.kinematic = False
                            self._obj.rigid_body.use_deactivation = False
                        try:
                            bpy.app.handlers.frame_change_post.remove(_release_on_next)
                        except Exception:
                            pass

                    bpy.app.handlers.frame_change_post.append(_release_on_next)
                    self._release_scheduled = True
            else:
                # Paused timeline: hacking in a frame a of motion using keyframes.. then release
                fps = max(1, scene.render.fps)
                f = scene.frame_current
                self._obj.keyframe_insert(data_path="location", frame=f)
                p_next = self._last_world + (v * (1.0 / fps))
                self._obj.location = p_next
                self._obj.keyframe_insert(data_path="location", frame=f + 1)
                # kinematic on at f, release at f+1
                self._obj.keyframe_insert(data_path="rigid_body.kinematic", frame=f)
                rb.kinematic = False
                self._obj.keyframe_insert(data_path="rigid_body.kinematic", frame=f + 1)
                # have to jump to f+1 to continue like nothing happened
                scene.frame_set(f + 1)

            self._store_original_state_in_scene(context)
            return {"FINISHED"}

        # Cancel on ESC or if focus lost
        if event.type in {"ESC"}:
            self._restore_original_state()
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}

    def _store_original_state_in_scene(self, context):
        """Store original state in scene for later restoration"""
        if self._obj and self._original_location is not None:
            scene = context.scene
            props = scene.throw_rb_props
            props.throw_rb_last_obj_name = self._obj_name
            # Store clean copies to avoid reference issues
            # Store the world position instead of local position
            world_pos = self._original_world_matrix.translation
            props.throw_rb_last_location = list(world_pos)
            props.throw_rb_last_rotation = list(self._original_rotation)
            props.throw_rb_last_scale = list(self._original_scale)
            print(f"Debug: Storing world position: {world_pos}")
            print(f"Debug: Storing rotation: {self._original_rotation}")
            props.throw_rb_last_kinematic = self._original_kinematic
            props.throw_rb_last_use_deactivation = self._original_use_deactivation
            print(f"Debug: Stored original state for {self._obj_name} in scene properties")

    def _restore_original_state(self):
        """Restore object to its original state before manipulation started"""
        if self._obj and self._original_location is not None:
            # Restore transform - use copy() to avoid reference issues
            self._obj.location = self._original_location.copy()
            self._obj.rotation_euler = self._original_rotation.copy()
            self._obj.scale = self._original_scale.copy()

            # Restore rigid body properties
            if self._obj.rigid_body:
                self._obj.rigid_body.kinematic = self._original_kinematic
                self._obj.rigid_body.use_deactivation = self._original_use_deactivation

            # Force update
            self._obj.update_tag()


class SR_Psy_OT_reset(Operator):
    bl_idname = "sr_psy_core.reset"
    bl_label = "Reset"
    bl_description = "Reset the scene"
    bl_options = {"REGISTER", "UNDO"}

    def _find_or_make_view3d_window(self):
        """Return (win, scr, area, region, restore_old_type_or_None)."""
        wm = bpy.context.window_manager
        if not wm.windows:
            return None, None, None, None, None

        win = bpy.context.window or wm.windows[0]
        scr = win.screen

        # 1) Try to find an existing VIEW_3D with a WINDOW region
        for area in scr.areas:
            if area.type == "VIEW_3D":
                region = next((r for r in area.regions if r.type == "WINDOW"), None)
                if region:
                    return win, scr, area, region, None

        # 2) Otherwise, temporarily convert the first area into VIEW_3D
        area = scr.areas[0] if scr.areas else None
        if not area:
            return None, None, None, None, None

        old_type = area.type
        area.type = "VIEW_3D"
        region = next((r for r in area.regions if r.type == "WINDOW"), None)
        if not region:
            # Fallback: restore and give up
            area.type = old_type
            return None, None, None, None, None
        return win, scr, area, region, old_type

    def execute(self, context):
        # Stop playback
        if any(getattr(w.screen, "is_animation_playing", False) for w in context.window_manager.windows):
            bpy.ops.screen.animation_play()

        # Jump to start
        context.scene.frame_set(context.scene.frame_start)

        # Simple deferred undo without context manipulation
        def do_undo():
            try:
                # Try undo with current context first
                bpy.ops.ed.undo()
            except RuntimeError:
                return 0.05  # retry if context not ready
            return None

        bpy.app.timers.register(do_undo, first_interval=0.02)
        return {"FINISHED"}


class SR_Psy_OT_add_objects_to_physics_env(Operator):
    bl_idname = "sr_psy_core.add_objects_to_physics_env"
    bl_label = "Add Objects to Physics Environment"
    bl_description = "Add objects to the physics environment"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        collection_name = "PhysicsTestEnv"
        if collection_name not in bpy.data.collections:
            self.report({"ERROR"}, "PhysicsTestEnv collection not found, making one")
            physics_collection = bpy.data.collections.new(collection_name)

        # Scan all objects in the scene for rigid body properties
        rigid_body_objects = []
        physics_collection = bpy.data.collections.get(collection_name)
        for obj in bpy.data.objects:
            if obj.rigid_body is not None:
                rigid_body_objects.append(obj)

        # Move all rigid body objects to PhysicsTestEnv collection
        if len(rigid_body_objects) == 0:
            self.report({"INFO"}, "No rigid body objects found")
            return {"FINISHED"}

        for obj in rigid_body_objects:
            if obj.name != "physics_groundplane":
                # Steal from physics world -> PhysicsTestEnv collection
                # keep them present in their current collections though...
                physics_collection.objects.link(obj)

        print(f"Moved {len(rigid_body_objects)} rigid body objects to PhysicsTestEnv collection")
        return {"FINISHED"}


class SR_Psy_OT_create_physics_env(Operator):
    bl_idname = "sr_psy_core.create_physics_env"
    bl_label = "Create Physics Environment for testing physics"
    bl_description = "Create a physics environment"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):

        # Check for a mesh named "physics_groundplane"
        if "physics_groundplane" in bpy.data.objects:
            self.report({"INFO"}, "Physics groundplane already exists")
            return {"FINISHED"}

        bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, 0))

        plane = bpy.context.active_object

        plane.name = "physics_groundplane"
        plane.location.z = -0.25
        plane.scale.x = 10
        plane.scale.y = 10

        bpy.ops.rigidbody.object_add()
        plane.rigid_body.type = "PASSIVE"

        # Create or get the PhysicsTestEnv collection
        collection_name = "PhysicsTestEnv"
        if collection_name not in bpy.data.collections:
            physics_collection = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(physics_collection)
        else:
            physics_collection = bpy.data.collections[collection_name]

        # Remove the plane from all current collections
        for collection in plane.users_collection:
            collection.objects.unlink(plane)

        # Add the plane to the PhysicsTestEnv collection
        physics_collection.objects.link(plane)

        # physics world is default for the physics scene...
        if not context.scene.rigidbody_world:
            bpy.ops.rigidbody.world_add()

        context.scene.rigidbody_world.collection = physics_collection

        # Extend timeline to 250 frames
        # This is the max default for physics caching in blender.
        context.scene.frame_start = 1
        context.scene.frame_end = 250

        return {"FINISHED"}


blender_to_usd_constraint_mapping = {
    "fixed": "FIXED",
    "revolute": "HINGE",
    "prismatic": "SLIDER",
    "spherical": "POINT",
    "d6": "GENERIC",
    "distance": "GENERIC_SPRING",
    "rack_and_pinion": "PISTON",
    # TODO: distance, gear, rack_and_pinion, d6, need to implement these.
    # TODO: don't know if they really align to USD physics constraint types.
}


class SR_Psy_OT_joints_to_rbds(Operator):
    bl_idname = "sr_psy_core.joints_to_rbds"
    bl_label = "Convert Joints to Rigid Bodies"
    bl_description = "Convert joints to rigid bodies"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        collection_name = "ReferencePrims"

        collection = bpy.data.collections.get(collection_name)
        if not collection:
            self.report({"ERROR"}, "ReferencePrims collection not found")
            return {"CANCELLED"}

        if len(collection.objects) == 1:
            self.report({"INFO"}, "ReferencePrims collection only has 1 object, this is a unibody object!")
            collection_geo_name = "Geometry"
            collection_geo = bpy.data.collections.get(collection_geo_name)
            if not collection_geo:
                self.report({"ERROR"}, "Geometry collection not found")
                return {"CANCELLED"}

            # loop through geometry collection and find only the obj that has a ChildOf constraint.
            for obj in collection_geo.objects:
                if obj.constraints:
                    for constraint in obj.constraints:
                        if constraint.type in [
                            "CHILD_OF",
                            "COPY_LOCATION",
                            "COPY_ROTATION",
                            "COPY_SCALE",
                            "COPY_TRANSFORMS",
                            "LIMIT_LOCATION",
                            "LIMIT_ROTATION",
                            "LIMIT_SCALE",
                            "TRANSFORM",
                            "CLAMP_TO",
                            "DAMPED_TRACK",
                            "IK",
                            "LOCKED_TRACK",
                            "SPLINE_IK",
                            "STRETCH_TO",
                            "TRACK_TO",
                            "ACTION",
                            "FOLLOW_PATH",
                        ]:
                            if not constraint.mute:
                                constraint.mute = True
                        if not obj.rigid_body:
                            bpy.context.view_layer.objects.active = obj
                            obj.select_set(True)
                            bpy.ops.rigidbody.object_add()
                            obj.select_set(False)
                            # Ensure rigid body is properly assigned
                            if obj.rigid_body:
                                obj.rigid_body.type = "ACTIVE"

                            return {"FINISHED"}

        converted_count = 0
        deactivated_constraints_count = 0

        for obj in collection.objects:
            if obj.type == "EMPTY":
                print(f"Checking empty: {obj.name}")

                # Check if object has the required joint attributes
                joint_type = obj.get("pxr:usd:physics:joint:type")
                body0 = obj.get("pxr:usd:physics:joint:body0")
                body1 = obj.get("pxr:usd:physics:joint:body1")

                if joint_type and body0 and body1:
                    print(f"Found joint: {obj.name} - Type: {joint_type}, Body0: {body0}, Body1: {body1}")

                    body0_obj = bpy.data.objects.get(body0)
                    body1_obj = bpy.data.objects.get(body1)
                    joint_type_mapped = blender_to_usd_constraint_mapping.get(joint_type, None)
                    lower_limit = obj.get("pxr:usd:physics:joint:lowerLimit")
                    upper_limit = obj.get("pxr:usd:physics:joint:upperLimit")
                    print(f"Lower limit: {lower_limit}, Upper limit: {upper_limit}")

                    # Deactivate rigging/animation constraints on body objects before adding physics
                    for body_obj in [body0_obj, body1_obj, obj]:
                        if body_obj and body_obj.constraints:
                            for constraint in body_obj.constraints:
                                # Mute common rigging/animation constraints that interfere with physics
                                if constraint.type in [
                                    "CHILD_OF",
                                    "COPY_LOCATION",
                                    "COPY_ROTATION",
                                    "COPY_SCALE",
                                    "COPY_TRANSFORMS",
                                    "LIMIT_LOCATION",
                                    "LIMIT_ROTATION",
                                    "LIMIT_SCALE",
                                    "TRANSFORM",
                                    "CLAMP_TO",
                                    "DAMPED_TRACK",
                                    "IK",
                                    "LOCKED_TRACK",
                                    "SPLINE_IK",
                                    "STRETCH_TO",
                                    "TRACK_TO",
                                    "ACTION",
                                    "FOLLOW_PATH",
                                ]:
                                    if not constraint.mute:
                                        constraint.mute = True
                                        deactivated_constraints_count += 1
                                        print(
                                            f"Deactivated {constraint.type} constraint '{constraint.name}' on {body_obj.name}"
                                        )

                    if body0_obj and body0_obj.type == "MESH":
                        if not body0_obj.rigid_body:
                            # Select and make active the body0 object
                            bpy.context.view_layer.objects.active = body0_obj
                            body0_obj.select_set(True)
                            bpy.ops.rigidbody.object_add()
                            body0_obj.select_set(False)
                            # Ensure rigid body is properly assigned
                            if body0_obj.rigid_body:
                                body0_obj.rigid_body.type = "ACTIVE"
                    if body1_obj and body1_obj.type == "MESH":
                        if not body1_obj.rigid_body:
                            # Select and make active the body1 object
                            bpy.context.view_layer.objects.active = body1_obj
                            body1_obj.select_set(True)
                            bpy.ops.rigidbody.object_add()
                            body1_obj.select_set(False)
                            # Ensure rigid body is properly assigned
                            if body1_obj.rigid_body:
                                body1_obj.rigid_body.type = "ACTIVE"

                    # now add physics constraint on the empty.
                    if body0_obj and body1_obj and body0_obj.rigid_body and body1_obj.rigid_body:
                        # Select and make active the empty object for constraint creation
                        bpy.context.view_layer.objects.active = obj
                        obj.select_set(True)
                        bpy.ops.rigidbody.constraint_add()
                        obj.select_set(False)

                        # Configure the constraint
                        if obj.rigid_body_constraint:
                            obj.rigid_body_constraint.type = joint_type_mapped
                            obj.rigid_body_constraint.object1 = body0_obj
                            obj.rigid_body_constraint.object2 = body1_obj

                            if lower_limit is not None and upper_limit is not None:
                                obj.rigid_body_constraint.use_limit_ang_z = True
                                print("Entering limit processing block")
                                # Convert from radians to degrees
                                lower_limit_deg = math.degrees(lower_limit)
                                upper_limit_deg = math.degrees(upper_limit)

                                print(f"Lower limit: {lower_limit_deg}, Upper limit: {upper_limit_deg}")
                                print(type(lower_limit_deg), type(upper_limit_deg))

                                # Handle angle limit inversion logic
                                # If limits span across 0° boundary (e.g., -180° to 0°),
                                # we need to invert and swap the limits
                                if lower_limit_deg < 0 and upper_limit_deg <= 0:
                                    # Case: -180° to 0° -> becomes 0° to 180°
                                    final_lower = 0
                                    final_upper = abs(lower_limit_deg)
                                    print(
                                        f"Case 1: {lower_limit_deg}° to {upper_limit_deg}° -> {final_lower}° to {final_upper}°"
                                    )
                                elif lower_limit_deg <= -180 and upper_limit_deg >= 180:
                                    # Case: -180° to 180° -> becomes 0° to 360° (full rotation)
                                    final_lower = 0
                                    final_upper = 360
                                    print(
                                        f"Case 2: {lower_limit_deg}° to {upper_limit_deg}° -> {final_lower}° to {final_upper}° (full rotation)"
                                    )
                                else:
                                    # Standard case: invert the values
                                    final_lower = -upper_limit_deg
                                    final_upper = -lower_limit_deg
                                    print(
                                        f"Case 3: {lower_limit_deg}° to {upper_limit_deg}° -> {final_lower}° to {final_upper}°"
                                    )

                                # Convert final degree values back to radians for Blender's rigid body constraints
                                final_lower_rad = math.radians(final_lower)
                                final_upper_rad = math.radians(final_upper)

                                # Set the limits in radians
                                obj.rigid_body_constraint.limit_ang_z_lower = float(final_lower_rad)
                                obj.rigid_body_constraint.limit_ang_z_upper = float(final_upper_rad)
                                print(
                                    f"Final limits set: {final_lower}° to {final_upper}° (in radians: {final_lower_rad:.4f} to {final_upper_rad:.4f})"
                                )
                            converted_count += 1
                            bpy.ops.object.select_all(action="DESELECT")
                            print(f"Created hinge constraint for {obj.name}")
                        else:
                            print(f"Failed to create constraint for {obj.name}")
                    else:
                        print(f"Skipping constraint creation for {obj.name} - missing rigid bodies")

        if converted_count == 0:
            self.report({"WARNING"}, "No joints found to convert")
        else:
            self.report({"INFO"}, f"Converted {converted_count} joints to rigid body constraints")

        return {"FINISHED"}
