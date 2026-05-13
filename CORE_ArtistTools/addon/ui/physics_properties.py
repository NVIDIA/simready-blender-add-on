# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy

from .physics_operators import (
    axis_items,
    bounce_threshold_items,
    break_strength_items,
    damping_items,
    joint_items,
    stiffness_items,
)


class JointAttributeProperties(bpy.types.PropertyGroup):

    # TODO: poll only empty objects
    #    def empty_object_filter(self, object):
    #        return object.type == 'EMPTY'

    # Panel update property
    panel_update: bpy.props.BoolProperty(
        name="Panel Update", description="Internal property to force panel updates", default=False, options={"HIDDEN"}
    )

    # Auto-sync property
    auto_sync_ui: bpy.props.BoolProperty(
        name="Auto Sync UI",
        description="Automatically sync UI when selecting objects with physics properties",
        default=True,
    )

    # UI refresh trigger property
    ui_refresh_trigger: bpy.props.IntProperty(
        name="UI Refresh Trigger", description="Internal property to trigger UI updates", default=0, options={"HIDDEN"}
    )

    # Constraint system state tracking
    constraint_system_setup: bpy.props.BoolProperty(
        name="Constraint System Setup",
        description="Internal property to track if constraint system is already set up",
        default=False,
        options={"HIDDEN"},
        update=lambda self, context: self._on_constraint_system_update(context),
    )

    def _on_constraint_system_update(self, context):
        """Called when constraint_system_setup property changes."""
        # Force UI refresh when constraint system state changes
        self.ui_refresh_trigger += 1

        # Force area redraw
        try:
            for area in context.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
            context.scene.update_tag()
        except Exception:
            pass  # Ignore errors during UI updates

    # Show applied properties toggle
    show_applied_properties: bpy.props.BoolProperty(
        name="Show Applied Properties", description="Show/hide the applied properties section", default=False
    )

    # MJCF import option checkbox
    use_included_colliders: bpy.props.BoolProperty(
        name="Use Included Colliders",
        description="If unchecked, colliders will be removed from the scene.",
        default=False,
    )

    def joint_type_update(self, context):
        # Force UI update when joint type changes
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

        # Also force a scene update to refresh all UI elements
        try:
            context.scene.update_tag()
        except Exception:
            pass

        # Reset properties based on joint type
        if self.joint_type == "fixed":
            # Fixed joint has minimal properties
            self.joint_axis = "X"  # Default axis
            self.lower_limit_deg = 0.0
            self.upper_limit_deg = 0.0
            self.min_dist_prismatic = 0.0
            self.max_dist_prismatic = 0.0
            self.min_dist = 0.0
            self.max_dist = 0.0
            self.cone_angle_0 = -1.0
            self.cone_angle_1 = -1.0

        elif self.joint_type == "revolute":
            # Revolute joint uses angular limits
            self.min_dist_prismatic = 0.0
            self.max_dist_prismatic = 0.0
            self.min_dist = 0.0
            self.max_dist = 0.0
            self.cone_angle_0 = -1.0
            self.cone_angle_1 = -1.0

        elif self.joint_type == "prismatic":
            # Prismatic joint uses linear limits
            self.lower_limit_deg = 0.0
            self.upper_limit_deg = 0.0
            self.min_dist = 0.0
            self.max_dist = 0.0
            self.cone_angle_0 = -1.0
            self.cone_angle_1 = -1.0

        elif self.joint_type == "spherical":
            # Spherical joint uses cone angles
            self.lower_limit_deg = 0.0
            self.upper_limit_deg = 0.0
            self.min_dist_prismatic = 0.0
            self.max_dist_prismatic = 0.0
            self.min_dist = 0.0
            self.max_dist = 0.0

        elif self.joint_type == "distance":
            # Distance joint uses min/max distance
            self.lower_limit_deg = 0.0
            self.upper_limit_deg = 0.0
            self.min_dist_prismatic = 0.0
            self.max_dist_prismatic = 0.0
            self.cone_angle_0 = -1.0
            self.cone_angle_1 = -1.0

        elif self.joint_type == "d6":
            # D6 joint uses all limits
            self.min_dist_prismatic = 0.0
            self.max_dist_prismatic = 0.0
            self.min_dist = 0.0
            self.max_dist = 0.0
            self.cone_angle_0 = -1.0
            self.cone_angle_1 = -1.0

        elif self.joint_type in {"rack_and_pinion", "gear"}:
            # These joint types use ratio and connected joints
            self.lower_limit_deg = 0.0
            self.upper_limit_deg = 0.0
            self.min_dist_prismatic = 0.0
            self.max_dist_prismatic = 0.0
            self.min_dist = 0.0
            self.max_dist = 0.0
            self.cone_angle_0 = -1.0
            self.cone_angle_1 = -1.0

    joint_type: bpy.props.EnumProperty(
        name="Joint Type",
        description="Select the type of joint for this REF_PRIM",
        items=joint_items,
        default="fixed",
        update=joint_type_update,
    )

    joint_local_pos_0: bpy.props.FloatVectorProperty(
        name="Joint Local Position 0",
        description="The local position of the joint in the object relative to the other body",
        default=(0.0, 0.0, 0.0),
        size=3,
    )

    joint_local_pos_1: bpy.props.FloatVectorProperty(
        name="Joint Local Position 1",
        description="The local position of the joint in the object relative to the other body",
        default=(0.0, 0.0, 0.0),
        size=3,
    )

    joint_local_rot_0: bpy.props.FloatVectorProperty(
        name="Joint Local Rotation 0",
        description="The local rotation of the joint in the object relative to the other body (quaternion: w, x, y, z)",
        default=(1.0, 0.0, 0.0, 0.0),
        size=4,
    )

    joint_local_rot_1: bpy.props.FloatVectorProperty(
        name="Joint Local Rotation 1",
        description="The local rotation of the joint in the object relative to the other body (quaternion: w, x, y, z)",
        default=(1.0, 0.0, 0.0, 0.0),
        size=4,
    )

    joint_axis: bpy.props.EnumProperty(
        name="Joint Axis", description="Select the joint axis (world or local)", items=axis_items, default="X"
    )

    # Axis mode property to track whether we're using world or local axes
    axis_mode: bpy.props.EnumProperty(
        name="Axis Mode",
        description="Choose between world axes or local object axes",
        items=[
            ("WORLD", "World Axes", "Use world coordinate system axes (X, Y, Z)"),
            ("LOCAL", "Local Axes", "Use object's local coordinate system axes"),
        ],
        default="WORLD",
        update=lambda self, context: self._on_axis_mode_update(context),
    )

    def _on_axis_mode_update(self, context):
        """Called when axis_mode changes - update joint_axis to match mode"""
        if self.axis_mode == "WORLD":
            # If switching to world mode, convert local axes to world axes
            if self.joint_axis == "LOCAL_X":
                self.joint_axis = "X"
            elif self.joint_axis == "LOCAL_Y":
                self.joint_axis = "Y"
            elif self.joint_axis == "LOCAL_Z":
                self.joint_axis = "Z"
        else:  # LOCAL mode
            # If switching to local mode, convert world axes to local axes
            if self.joint_axis == "X":
                self.joint_axis = "LOCAL_X"
            elif self.joint_axis == "Y":
                self.joint_axis = "LOCAL_Y"
            elif self.joint_axis == "Z":
                self.joint_axis = "LOCAL_Z"

    lower_limit_deg: bpy.props.FloatProperty(
        name="Lower Limit (°)",
        description="Lower rotational/positional limit in degrees",
        default=0.0,
        unit="ROTATION",
        precision=4,
        step=1,
        min=-180.0,
    )

    upper_limit_deg: bpy.props.FloatProperty(
        name="Upper Limit (°)",
        description="Upper rotational/positional limit in degrees",
        default=0.0,
        unit="ROTATION",
        precision=4,
        step=1,
        max=180.0,
    )

    infinite_limit_deg: bpy.props.BoolProperty(
        name="Infinite Limit (°)", description="If enabled, the joint will have an infinite limit", default=False
    )

    min_dist_prismatic: bpy.props.FloatProperty(
        name="Min Distance (m)", description="Where your joint starts", default=0.0, precision=4, step=1
    )

    max_dist_prismatic: bpy.props.FloatProperty(
        name="Max Distance (m)", description="where your joint ends", default=0.0, precision=4, step=1
    )

    min_dist: bpy.props.FloatProperty(
        name="Min Distance (m)", description="Where your joint starts", default=0.0, precision=4, step=1
    )

    max_dist: bpy.props.FloatProperty(
        name="Max Distance (m)", description="where your joint ends", default=0.0, precision=4, step=1
    )

    cone_angle_0: bpy.props.FloatProperty(
        name="Cone Angle 0 Limit (°)",
        description="Cone limit from primary joint to the next axis (i.e. X => Y)."
        "\nNegative values means no limits (-1).",
        default=-1.0,
        min=-1.0,
        max=360.0,
        unit="ROTATION",
        precision=4,
        step=1,
    )

    cone_angle_1: bpy.props.FloatProperty(
        name="Cone Angle 1 Limit (°)",
        description="Cone limit from primary joint to the next axis (i.e. X => Y)."
        "\nNegative values means no limits. (-1)",
        default=-1.0,
        min=-1.0,
        max=360.0,
        unit="ROTATION",
        precision=4,
        step=1,
    )

    body_0: bpy.props.PointerProperty(
        name="Body 0 (parent)",
        description="First object to connect (parent body)",
        type=bpy.types.Object,
        update=lambda self, context: self._on_body_assignment_update(context),
    )

    body_1: bpy.props.PointerProperty(
        name="Body 1 (child)",
        description="Second object to connect (child body)",
        type=bpy.types.Object,
        update=lambda self, context: self._on_body_assignment_update(context),
    )

    def _on_body_assignment_update(self, context):
        """Called when body_0 or body_1 assignments change."""
        # Update constraint system state when body assignments change
        try:
            from .physics_operators import update_constraint_system_state

            update_constraint_system_state(context)
        except Exception:
            pass  # Ignore errors during updates

    break_strength: bpy.props.EnumProperty(
        name="Break Strength",
        description="Defines how easily the joint breaks under force or torque",
        items=break_strength_items,
        default="unbreakable",
    )

    damping: bpy.props.EnumProperty(
        name="Damping", description="Choose damping level for this joint", items=damping_items, default="medium_damping"
    )

    damping_linear: bpy.props.EnumProperty(
        name="Damping", description="Choose damping level for this joint", items=damping_items, default="medium_damping"
    )
    damping_cone: bpy.props.EnumProperty(
        name="Damping", description="Choose damping level for this joint", items=damping_items, default="medium_damping"
    )
    damping_distance: bpy.props.EnumProperty(
        name="Damping", description="Choose damping level for this joint", items=damping_items, default="medium_damping"
    )

    restitution: bpy.props.FloatProperty(
        name="Restitution",
        description="How much the joint bounces after hitting a limit. 0 = no bounce, 1 = full bounce.",
        default=0.0,
        min=0.0,
        max=1.0,
        step=0.1,
        precision=2,
    )
    restitution_linear: bpy.props.FloatProperty(
        name="Restitution",
        description="How much the joint bounces after hitting a limit. 0 = no bounce, 1 = full bounce.",
        default=0.0,
        min=0.0,
        max=1.0,
        step=0.1,
        precision=2,
    )
    restitution_cone: bpy.props.FloatProperty(
        name="Restitution",
        description="How much the joint bounces after hitting a limit. 0 = no bounce, 1 = full bounce.",
        default=0.0,
        min=0.0,
        max=1.0,
        step=0.1,
        precision=2,
    )
    restitution_distance: bpy.props.FloatProperty(
        name="Restitution",
        description="How much the joint bounces after hitting a limit. 0 = no bounce, 1 = full bounce.",
        default=0.0,
        min=0.0,
        max=1.0,
        step=0.1,
        precision=2,
    )

    stiffness_enum: bpy.props.EnumProperty(
        name="Stiffness", description="Select joint stiffness level", items=stiffness_items, default="balanced"
    )
    stiffness_enum_linear: bpy.props.EnumProperty(
        name="Stiffness", description="Select joint stiffness level", items=stiffness_items, default="balanced"
    )
    stiffness_enum_distance: bpy.props.EnumProperty(
        name="Stiffness", description="Select joint stiffness level", items=stiffness_items, default="balanced"
    )
    stiffness_enum_cone: bpy.props.EnumProperty(
        name="Stiffness", description="Select joint stiffness level", items=stiffness_items, default="balanced"
    )

    bounce_threshold: bpy.props.EnumProperty(
        name="Bounce Threshold",
        description="Minimum collision speed to trigger bounce. Lower = bounces more easily.",
        items=bounce_threshold_items,
        default="medium",
    )

    bounce_threshold_linear: bpy.props.EnumProperty(
        name="Bounce Threshold",
        description="Minimum collision speed to trigger bounce. Lower = bounces more easily.",
        items=bounce_threshold_items,
        default="medium",
    )
    bounce_threshold_cone: bpy.props.EnumProperty(
        name="Bounce Threshold",
        description="Minimum collision speed to trigger bounce. Lower = bounces more easily.",
        items=bounce_threshold_items,
        default="medium",
    )
    bounce_threshold_distance: bpy.props.EnumProperty(
        name="Bounce Threshold",
        description="Minimum collision speed to trigger bounce. Lower = bounces more easily.",
        items=bounce_threshold_items,
        default="medium",
    )

    joint_friction: bpy.props.FloatProperty(
        name="Joint Friction",
        description="Resistive force applied to joint when there's no motion.",
        default=0.0,
        min=0.0,
        max=1000.0,
    )

    maximum_joint_velocity: bpy.props.FloatProperty(
        name="Maximum Joint Velocity",
        description="The speed limit of this joint in meters/sec or radians/sec",
        default=1000000,
        min=0.0,
        max=1000000,
        step=1.0,
    )

    armature: bpy.props.FloatProperty(
        name="Armature",
        description="Inertia of an actuator driving this joint...Artificial mass/inertia added",
        default=0.0,
        min=0.0,
        max=1000000,
        step=1.0,
    )

    physx_enabled: bpy.props.BoolProperty(
        name="Enable Physx Attrs",
        description="Checking this on will provide a lot of advanced attributes for Physx control."
        "\nPhysx attributes are used in Omniverse applications ONLY.",
        default=False,
    )

    uni_body: bpy.props.BoolProperty(
        name="Uni-body",
        description="Is this a uni-body joint? Uni-body has no joints or connected bodies... i.e. a piece of wood.",
        default=False,
    )

    # Distance Joint attributes
    spring_enabled: bpy.props.BoolProperty(name="Set spring enabled", description="is spring on or off?", default=False)

    # D6 joint attributes

    # X ROT
    d6_xrot_low_limit: bpy.props.FloatProperty(
        name="X Rot Low Limit (°)", description="set lower limits in degrees.", default=0.0, unit="ROTATION"
    )

    d6_xrot_upper_limit: bpy.props.FloatProperty(
        name="X Rot Upper Limit (°)", description="set upper limits in degrees.", default=0.0, unit="ROTATION"
    )

    d6_xrot_restitution: bpy.props.FloatProperty(
        name="X Rot Restitution",
        description="How much the joint bounces after hitting a limit. 0 = no bounce, 1 = full bounce.",
        default=0.0,
        min=0.0,
        max=1.0,
        step=0.1,
        precision=2,
    )

    d6_xrot_bounce_thresh: bpy.props.FloatProperty(
        name="X Rot Bounce Threshold",
        description="Minimum collision speed to trigger bounce. Lower = bounces more easily.",
        default=1.0,
        min=0.0,
        max=10.0,
        step=0.1,
        precision=2,
    )

    d6_xrot_stiffness: bpy.props.EnumProperty(
        name="X Rot Stiffness", description="Select joint stiffness level", items=stiffness_items, default="balanced"
    )

    d6_xrot_damping: bpy.props.EnumProperty(
        name="X Rot Damping",
        description="Choose damping level for this joint",
        items=damping_items,
        default="medium_damping",
    )

    # Y ROT
    d6_yrot_low_limit: bpy.props.FloatProperty(
        name="Y Rot Low Limit (°)", description="set lower limits in degrees.", default=0.0, unit="ROTATION"
    )

    d6_yrot_upper_limit: bpy.props.FloatProperty(
        name="Y Rot Upper Limit (°)", description="set upper limits in degrees.", default=0.0, unit="ROTATION"
    )

    d6_yrot_restitution: bpy.props.FloatProperty(
        name="Y Rot Restitution",
        description="How much the joint bounces after hitting a limit. 0 = no bounce, 1 = full bounce.",
        default=0.0,
        min=0.0,
        max=1.0,
        step=0.1,
        precision=2,
    )

    d6_yrot_bounce_thresh: bpy.props.FloatProperty(
        name="Y Rot Bounce Threshold",
        description="Minimum collision speed to trigger bounce. Lower = bounces more easily.",
        default=1.0,
        min=0.0,
        max=10.0,
        step=0.1,
        precision=2,
    )

    d6_yrot_stiffness: bpy.props.EnumProperty(
        name="Y Rot Stiffness", description="Select joint stiffness level", items=stiffness_items, default="balanced"
    )

    d6_yrot_damping: bpy.props.EnumProperty(
        name="Y Rot Damping",
        description="Choose damping level for this joint",
        items=damping_items,
        default="medium_damping",
    )

    # Z rot
    d6_zrot_low_limit: bpy.props.FloatProperty(
        name="Z Rot Low Limit (°)", description="set lower limits in degrees.", default=0.0, unit="ROTATION"
    )

    d6_zrot_upper_limit: bpy.props.FloatProperty(
        name="Z Rot Upper Limit (°)", description="set upper limits in degrees.", default=0.0, unit="ROTATION"
    )

    d6_zrot_restitution: bpy.props.FloatProperty(
        name="Z Rot Restitution",
        description="How much the joint bounces after hitting a limit. 0 = no bounce, 1 = full bounce.",
        default=0.0,
        min=0.0,
        max=1.0,
        step=0.1,
        precision=2,
    )

    d6_zrot_bounce_thresh: bpy.props.FloatProperty(
        name="Z Rot Bounce Threshold",
        description="Minimum collision speed to trigger bounce. Lower = bounces more easily.",
        default=1.0,
        min=0.0,
        max=10.0,
        step=0.1,
        precision=2,
    )

    d6_zrot_stiffness: bpy.props.EnumProperty(
        name="Z Rot Stiffness", description="Select joint stiffness level", items=stiffness_items, default="balanced"
    )

    d6_zrot_damping: bpy.props.EnumProperty(
        name="Z Rot Damping",
        description="Choose damping level for this joint",
        items=damping_items,
        default="medium_damping",
    )

    # X Pos
    d6_xpos_low_limit: bpy.props.FloatProperty(
        name="X Pos Low Limit (m)", description="set lower limits in meters.", default=0.0
    )

    d6_xpos_upper_limit: bpy.props.FloatProperty(
        name="X Pos Upper Limit (m)", description="set upper limits in meters.", default=0.0
    )

    d6_xpos_restitution: bpy.props.FloatProperty(
        name="X Pos Restitution",
        description="How much the joint bounces after hitting a limit. 0 = no bounce, 1 = full bounce.",
        default=0.0,
        min=0.0,
        max=1.0,
        step=0.1,
        precision=2,
    )

    d6_xpos_bounce_thresh: bpy.props.FloatProperty(
        name="X Pos Bounce Threshold",
        description="Minimum collision speed to trigger bounce. Lower = bounces more easily.",
        default=1.0,
        min=0.0,
        max=10.0,
        step=0.1,
        precision=2,
    )

    d6_xpos_stiffness: bpy.props.EnumProperty(
        name="X Pos Stiffness", description="Select joint stiffness level", items=stiffness_items, default="balanced"
    )

    d6_xpos_damping: bpy.props.EnumProperty(
        name="X Pos Damping",
        description="Choose damping level for this joint",
        items=damping_items,
        default="medium_damping",
    )

    # Y Pos
    d6_ypos_low_limit: bpy.props.FloatProperty(
        name="Y Pos Low Limit (m)", description="set lower limits in meters.", default=0.0
    )

    d6_ypos_upper_limit: bpy.props.FloatProperty(
        name="Y Pos Upper Limit (m)", description="set upper limits in meters.", default=0.0
    )

    d6_ypos_restitution: bpy.props.FloatProperty(
        name="Y Pos Restitution",
        description="How much the joint bounces after hitting a limit. 0 = no bounce, 1 = full bounce.",
        default=0.0,
        min=0.0,
        max=1.0,
        step=0.1,
        precision=2,
    )

    d6_ypos_bounce_thresh: bpy.props.FloatProperty(
        name="Y Pos Bounce Threshold",
        description="Minimum collision speed to trigger bounce. Lower = bounces more easily.",
        default=1.0,
        min=0.0,
        max=10.0,
        step=0.1,
        precision=2,
    )

    d6_ypos_stiffness: bpy.props.EnumProperty(
        name="Y Pos Stiffness", description="Select joint stiffness level", items=stiffness_items, default="balanced"
    )

    d6_ypos_damping: bpy.props.EnumProperty(
        name="Y Pos Damping",
        description="Choose damping level for this joint",
        items=damping_items,
        default="medium_damping",
    )

    # Z Pos
    d6_zpos_low_limit: bpy.props.FloatProperty(
        name="Z Pos Low Limit (m)", description="set lower limits in meters.", default=0.0
    )

    d6_zpos_upper_limit: bpy.props.FloatProperty(
        name="Z Pos Upper Limit (m)", description="set upper limits in meters.", default=0.0
    )

    d6_zpos_restitution: bpy.props.FloatProperty(
        name="Z Pos Restitution",
        description="How much the joint bounces after hitting a limit. 0 = no bounce, 1 = full bounce.",
        default=0.0,
        min=0.0,
        max=1.0,
        step=0.1,
        precision=2,
    )

    d6_zpos_bounce_thresh: bpy.props.FloatProperty(
        name="Z Pos Bounce Threshold",
        description="Minimum collision speed to trigger bounce. Lower = bounces more easily.",
        default=1.0,
        min=0.0,
        max=10.0,
        step=0.1,
        precision=2,
    )

    d6_zpos_stiffness: bpy.props.EnumProperty(
        name="Z Pos Stiffness", description="Select joint stiffness level", items=stiffness_items, default="balanced"
    )

    d6_zpos_damping: bpy.props.EnumProperty(
        name="Z Pos Damping",
        description="Choose damping level for this joint",
        items=damping_items,
        default="medium_damping",
    )

    # Rack and Pinion Attrs
    rp_hinge: bpy.props.PointerProperty(
        name="Hinge (Reference Locator)",
        description="The rotation part of the Rack and Pinion (steering wheel)"
        "\nPlease point this at a Reference Locator, usually a Blender empty",
        type=bpy.types.Object,
    )
    rp_prismatic: bpy.props.PointerProperty(
        name="Prismatic (Reference Locator)",
        description="The sliding joint (will slide left and right and turn a car wheel.",
        type=bpy.types.Object,
    )
    rp_ratio: bpy.props.FloatProperty(
        name="Rack and Pinion Ratio",
        description="The amount of influence between each joint.",
        default=0.5,
        min=0.0,
        max=1.0,
    )

    # Rack and Pinion Attrs
    # TODO: Should try to Poll only certain items, right now it looks at any obj
    gear_hinge_0: bpy.props.PointerProperty(
        name="Hinge 0 (Reference Locator)",
        description="The first gear joint."
        "\nPlease point this at a Reference Locator, usually a Blender empty"
        "\nThis will usually be a Blender locator, with revolute joint attributes.",
        type=bpy.types.Object,
        #        poll=empty_object_filter
    )
    gear_hinge_1: bpy.props.PointerProperty(
        name="Hinge 1 (Reference Locator)",
        description="The second gear joint."
        "\nThis will usually be a Blender locator, with revolute joint attributes.",
        type=bpy.types.Object,
        #        poll=empty_object_filter
    )
    gear_ratio: bpy.props.FloatProperty(
        name="Gear Joint(s) Ratio",
        description="The amount of influence between each joint.",
        default=0.5,
        min=0.0,
        max=1.0,
    )

    # Drive API Properties - Linear
    drive_linear_enabled: bpy.props.BoolProperty(
        name="Enable Linear Drive", description="Enable linear drive for this joint", default=False
    )

    drive_linear_preset: bpy.props.EnumProperty(
        name="Linear Drive Preset",
        description="Select a preset configuration for linear drive",
        items=[
            ("button", "Button (Return to Rest)", "Button that returns to rest position - moves back to position 0.0"),
            ("drawer", "Drawer (Open and Close)", "Drawer that opens and closes"),
        ],
        default="button",
    )

    drive_linear_type: bpy.props.EnumProperty(
        name="Drive Type",
        description="The type of drive: force or acceleration",
        items=[("force", "Force", "Force-based drive"), ("acceleration", "Acceleration", "Acceleration-based drive")],
        default="force",
    )

    drive_linear_max_force: bpy.props.FloatProperty(
        name="Max Force", description="Maximum force that the drive can apply", default=0.0, min=0.0, soft_max=10000.0
    )

    drive_linear_target_position: bpy.props.FloatProperty(
        name="Target Position", description="Target position for the drive", default=0.0, precision=4
    )

    drive_linear_target_velocity: bpy.props.FloatProperty(
        name="Target Velocity", description="Target velocity for the drive", default=0.0, precision=4
    )

    drive_linear_damping: bpy.props.FloatProperty(
        name="Damping", description="Damping coefficient for the drive", default=0.0, min=0.0, soft_max=1000.0
    )

    drive_linear_stiffness: bpy.props.FloatProperty(
        name="Stiffness", description="Stiffness coefficient for the drive", default=0.0, min=0.0, soft_max=10000.0
    )

    # Drive API Properties - Angular
    drive_angular_enabled: bpy.props.BoolProperty(
        name="Enable Angular Drive", description="Enable angular drive for this joint", default=False
    )

    drive_angular_preset: bpy.props.EnumProperty(
        name="Angular Drive Preset",
        description="Select a preset configuration for angular drive",
        items=[
            ("button", "Button (Return to Rest)", "Button that returns to rest position - moves back to position 0.0"),
        ],
        default="button",
    )

    drive_angular_type: bpy.props.EnumProperty(
        name="Drive Type",
        description="The type of drive: force or acceleration",
        items=[("force", "Force", "Force-based drive"), ("acceleration", "Acceleration", "Acceleration-based drive")],
        default="force",
    )

    drive_angular_max_force: bpy.props.FloatProperty(
        name="Max Force", description="Maximum force that the drive can apply", default=0.0, min=0.0, soft_max=10000.0
    )

    drive_angular_target_position: bpy.props.FloatProperty(
        name="Target Position",
        description="Target position for the drive (in degrees)",
        default=0.0,
        unit="ROTATION",
        precision=4,
    )

    drive_angular_target_velocity: bpy.props.FloatProperty(
        name="Target Velocity",
        description="Target velocity for the drive (in degrees/sec)",
        default=0.0,
        unit="ROTATION",
        precision=4,
    )

    drive_angular_damping: bpy.props.FloatProperty(
        name="Damping", description="Damping coefficient for the drive", default=0.0, min=0.0, soft_max=1000.0
    )

    drive_angular_stiffness: bpy.props.FloatProperty(
        name="Stiffness", description="Stiffness coefficient for the drive", default=0.0, min=0.0, soft_max=10000.0
    )

    show_widgets: bpy.props.BoolProperty(
        name="Show Widgets",
        default=True,
        update=lambda s, c: set_collection_visibility(not s.show_widgets),  # noqa F841
    )


class GraspPairProperties(bpy.types.PropertyGroup):
    """Properties for a single grasp point pair"""

    # Grasp point objects
    grasp_point_1: bpy.props.PointerProperty(
        name="Grasp Point 1", description="First grasp point (empty with sphere display)", type=bpy.types.Object
    )

    grasp_point_2: bpy.props.PointerProperty(
        name="Grasp Point 2", description="Second grasp point (empty with sphere display)", type=bpy.types.Object
    )

    # Line object that connects the grasp points
    line_object: bpy.props.PointerProperty(
        name="Line Object", description="Line object that connects the two grasp points", type=bpy.types.Object
    )

    # Position tracking properties
    point_1_position: bpy.props.FloatVectorProperty(
        name="Point 1 Position",
        description="Current position of grasp point 1",
        default=(0.0, 0.0, 0.0),
        size=3,
        subtype="TRANSLATION",
    )

    point_2_position: bpy.props.FloatVectorProperty(
        name="Point 2 Position",
        description="Current position of grasp point 2",
        default=(0.0, 0.0, 0.0),
        size=3,
        subtype="TRANSLATION",
    )

    # Distance between points
    point_distance: bpy.props.FloatProperty(
        name="Distance Between Points", description="Distance between the two grasp points", default=0.0, unit="LENGTH"
    )

    # Sphere size for display
    sphere_size: bpy.props.FloatProperty(
        name="Sphere Size",
        description="Size of the sphere display for grasp points",
        default=0.1,
        min=0.01,
        max=10.0,
        unit="LENGTH",
    )


class GraspPointProperties(bpy.types.PropertyGroup):
    """Properties for grasp point setup - manages multiple grasp pairs"""

    # Collection of grasp pairs
    grasp_pairs: bpy.props.CollectionProperty(
        name="Grasp Pairs", description="Collection of grasp point pairs", type=GraspPairProperties
    )

    # Active pair index
    active_pair_index: bpy.props.IntProperty(
        name="Active Pair Index", description="Index of the currently active grasp pair", default=0, min=0
    )

    # Global sphere size for all pairs
    global_sphere_size: bpy.props.FloatProperty(
        name="Global Sphere Size",
        description="Size of the sphere display for all grasp points",
        default=0.025,
        min=0.01,
        max=10.0,
        unit="LENGTH",
    )


SR_PSY_VIDEO_ENUM_ITEMS = [
    ("NONE", "-- Select a Video --", ""),
    ("chapter1_fixed_joint.mp4", "1: Fixed Joint", ""),
    ("chapter2_revolute_joint.mp4", "2: Revolute Joint", ""),
    ("chapter3_grasp_vectors.mp4", "3: Grasp Vectors", ""),
]


class SR_Psy_VideoTutorialProps(bpy.types.PropertyGroup):
    selected_video: bpy.props.EnumProperty(
        name="Tutorial Video", description="Pick a video to view", items=SR_PSY_VIDEO_ENUM_ITEMS, default="NONE"
    )


class RigidBodyStateProperties(bpy.types.PropertyGroup):
    """Properties for storing individual rigid body states"""

    object_name: bpy.props.StringProperty(name="Object Name", description="Name of the rigid body object")

    location: bpy.props.FloatVectorProperty(
        name="Original Location", description="Original location of the rigid body", size=3
    )

    rotation: bpy.props.FloatVectorProperty(
        name="Original Rotation", description="Original rotation of the rigid body", size=3
    )

    scale: bpy.props.FloatVectorProperty(name="Original Scale", description="Original scale of the rigid body", size=3)

    kinematic: bpy.props.BoolProperty(
        name="Original Kinematic", description="Original kinematic state of the rigid body"
    )

    use_deactivation: bpy.props.BoolProperty(
        name="Original Use Deactivation", description="Original use deactivation state of the rigid body", default=True
    )


class PhysicsThrowProperties(bpy.types.PropertyGroup):
    speed_scale: bpy.props.FloatProperty(
        name="Speed Scale",
        description="Multiplier from screen drag (at object depth) to world velocity (in m/s)",
        default=12.0,
        min=0.0,
        soft_max=100.0,
    )
    max_speed: bpy.props.FloatProperty(
        name="Max Speed", description="Clamp linear speed (in m/s)", default=50.0, min=0.0, soft_max=500.0
    )

    # Collection to store states of all rigid bodies
    rigid_body_states: bpy.props.CollectionProperty(
        name="Rigid Body States",
        description="Collection of all rigid body original states",
        type=RigidBodyStateProperties,
    )

    # Active state index for UI
    active_state_index: bpy.props.IntProperty(
        name="Active State Index", description="Index of the currently active rigid body state", default=0, min=0
    )

    # Legacy properties for backward compatibility (keeping the old single-object approach)
    throw_rb_init_obj_name: bpy.props.StringProperty(
        name="Last Thrown Rigidbody Name", description="Name of the last thrown rigidbody"
    )
    throw_rb_init_location: bpy.props.FloatVectorProperty(
        name="Last Original Location", description="Original location of the last thrown rigidbody", size=3
    )
    throw_rb_init_rotation: bpy.props.FloatVectorProperty(
        name="Last Original Rotation", description="Original rotation of the last thrown rigidbody", size=3
    )
    throw_rb_init_scale: bpy.props.FloatVectorProperty(
        name="Last Original Scale", description="Original scale of the last thrown rigidbody", size=3
    )
    throw_rb_init_kinematic: bpy.props.BoolProperty(
        name="Last Original Kinematic", description="Original kinematic of the last thrown rigidbody"
    )
    throw_rb_init_use_deactivation: bpy.props.BoolProperty(
        name="Last Original Use Deactivation",
        description="Original use deactivation of the last thrown rigidbody",
        default=True,
    )
