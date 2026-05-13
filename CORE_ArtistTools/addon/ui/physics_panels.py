# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from bpy.types import Panel

from .physics_operators import (
    joint_items,
)


class SRCORE_PT_JointAttributes(Panel):
    bl_label = "Usd PhysicsJoint Attributes"
    bl_idname = "SRCORE_PT_joint_attributes"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    bl_order = 5

    @classmethod
    def poll(cls, context):
        """Poll method to ensure panel updates when constraint system state changes."""
        if not hasattr(context.scene, "joint_attribute_props"):
            return False

        return True

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        props = context.scene.joint_attribute_props
        jt = props.joint_type
        physx_enabled = props.physx_enabled
        uni_body = props.uni_body

        # Hidden property to trigger UI refresh when syncing
        # layout.prop(props, "ui_refresh_trigger", text="", emboss=False)

        # Physx or Not?
        box = layout.box()
        row = box.row(align=True)

        # REMOVED Physx Attributes, but leaving the code in case we need it later
        # row.prop(props, "physx_enabled", text="Use Physx Attributes")
        physx_enabled = False

        row = box.row(align=True)
        row.prop(props, "uni_body", text="Is uni-body?")

        box_alot = layout.box()
        box_alot.label(text="", icon="INFO")
        if props.auto_sync_ui:
            box_alot.label(text="The UI will update when you select objects with physics properties.")
            brow = box_alot.split(factor=0.65)
            brow.label(text="View the object properties tab to see the changes. The icon looks like:")
            brow.label(icon="OBJECT_DATA")
        else:
            box_alot.label(text="Auto-sync is disabled. Use the 'Applied Properties' section to view the properties..")

        # Auto-sync option
        box_alot.separator()
        box_alot.prop(props, "auto_sync_ui", text="Auto-sync UI when selecting objects")

        layout.separator()
        box2 = layout.box()
        row_context = box2.row(align=True)
        if obj:
            row_context.label(text=f"Current Object Selected: {obj.name}")
        else:
            row_context.label(text="Nothing selected, Please select an Empty/Reference Prim")

        if not uni_body:

            multi_hierarchy_box = layout.box()
            multi_hierarchy_box.label(text="1. Hierarchy Setup:")
            # Joint type
            multi_hierarchy_box.label(text="Assign Joint Type:", icon="MOD_NORMALEDIT")
            multi_hierarchy_box.prop(props, "joint_type", text="")

            selected = next((item for item in joint_items if item[0] == props.joint_type), None)

            if selected:
                multi_hierarchy_box.label(text="Description:")
                multi_hierarchy_box.label(text=selected[2], icon="INFO")

                multi_hierarchy_box.separator()

            # Connected bodies
            multi_hierarchy_box.label(text="Assign Connected Bodies:", icon="PIVOT_BOUNDBOX")
            multi_hierarchy_box.prop(props, "body_0")
            multi_hierarchy_box.prop(props, "body_1")

            layout.separator()

            # Joint local position
            joint_attr_box = layout.box()
            joint_attr_box.label(text="2. Setup Joint Attributes:")
            joint_attr_box.separator()

            if jt in {"revolute", "fixed"}:
                joint_attr_box.label(text="Joint Local Position:", icon="EMPTY_ARROWS")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "joint_local_pos_0")

                if obj and obj.type == "EMPTY":
                    if jt == "fixed":
                        # op = row.operator("sr_core.copy_empty_position_fixed", text="", icon='COPYDOWN')
                        op = joint_attr_row.operator("sr_core.copy_empty_position", text="", icon="COPYDOWN")
                    else:
                        op = joint_attr_row.operator("sr_core.copy_empty_position", text="", icon="COPYDOWN")

                    op.target_prop = "joint_local_pos_0"
            elif jt in {"prismatic"}:
                joint_attr_box.label(text="Joint Local Position:", icon="EMPTY_ARROWS")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "joint_local_pos_0")
                joint_attr_row.prop(props, "joint_local_pos_1")
                if obj and obj.type == "EMPTY":
                    if jt == "prismatic":
                        op = joint_attr_row.operator("sr_core.copy_empty_pos_prismatic", text="", icon="COPYDOWN")
                        op.target_prop = "joint_local_pos_0"
                        op.target_prop_2 = "joint_local_pos_1"

            elif jt in {"spherical"}:
                joint_attr_box.label(text="Joint Local Position:", icon="EMPTY_ARROWS")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "joint_local_pos_0")
                if obj and obj.type == "EMPTY":
                    op = joint_attr_row.operator("sr_core.copy_empty_position", text="", icon="COPYDOWN")
                    op.target_prop = "joint_local_pos_0"

            # Joint axis
            if jt in {"revolute", "prismatic", "spherical"}:
                joint_attr_box.label(text="Assign Joint Axis:", icon="ORIENTATION_GIMBAL")

                # Axis mode selection
                axis_mode_row = joint_attr_box.row()  # noqa F841

                # Joint axis selection
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "joint_axis")

                joint_attr_box.separator()

            # Limits
            if jt in {"revolute"}:
                joint_attr_box.label(text="Set Limits (Degrees):", icon="ORIENTATION_PARENT")

                # Add checkbox for infinite limits
                infinite_row = joint_attr_box.row()
                infinite_row.prop(props, "infinite_limit_deg", text="Infinite Limit")

                # Limit input fields - disabled when infinite limit is checked
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.enabled = not props.infinite_limit_deg
                joint_attr_row.prop(props, "lower_limit_deg")
                joint_attr_row.prop(props, "upper_limit_deg")

                joint_attr_box.separator()

            if jt in {"prismatic"}:
                joint_attr_box.label(text="Set Limits (Distance):", icon="ORIENTATION_PARENT")
                joint_attr_box.label(text="These values are in world coordinates.", icon="INFO")
                joint_attr_row2 = joint_attr_box.row()
                joint_attr_row2.prop(props, "min_dist_prismatic")
                op2 = joint_attr_row2.operator("sr_core.calc_min_max_limits_prismatic", text="", icon="COPYDOWN")
                op2.target_prop = "min_dist_prismatic"
                joint_attr_row3 = joint_attr_box.row()
                joint_attr_row3.prop(props, "max_dist_prismatic")
                op3 = joint_attr_row3.operator("sr_core.calc_min_max_limits_prismatic", text="", icon="COPYDOWN")
                op3.target_prop = "max_dist_prismatic"

            if jt in {"distance"}:
                joint_attr_box.label(text="Set Limits (Distance):", icon="ORIENTATION_PARENT")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "min_dist")
                joint_attr_row.prop(props, "max_dist")

                joint_attr_box.separator()

                if physx_enabled:
                    joint_attr_box.prop(props, "spring_enabled", text="Enable Spring", icon="GP_ONLY_SELECTED")
                    joint_attr_row_a = joint_attr_box.row()
                    joint_attr_row_a.enabled = props.spring_enabled
                    joint_attr_row_a.prop(props, "spring_stiffness_enum")

                    joint_attr_box.separator()

            if jt in {"spherical"}:
                joint_attr_box.label(text="Set Limits (Degrees):", icon="ORIENTATION_PARENT")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "cone_angle_0")
                joint_attr_row.prop(props, "cone_angle_1")

            joint_attr_box.label(text="Set Break Strength (BreakForce | BreakTorque):", icon="MOD_PHYSICS")
            joint_attr_row = joint_attr_box.row()
            joint_attr_row.prop(props, "break_strength")

            # Advanced physx options in all joints
            if physx_enabled:
                joint_attr_box.separator()
                joint_attr_box.label(text="Set Joint Friction (if static):", icon="GP_MULTIFRAME_EDITING")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "joint_friction")

                joint_attr_box.separator()
                joint_attr_box.label(text="Set Max Joint Velocity:", icon="OUTLINER_DATA_CURVES")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "maximum_joint_velocity")

                joint_attr_box.separator()
                joint_attr_box.label(text="Set Armature (extra speed from outside):", icon="CON_KINEMATIC")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "armature")

            if physx_enabled and jt in {"revolute"}:
                joint_attr_box.separator()
                joint_attr_box.label(text="Set Damping:", icon="OUTLINER_OB_FORCE_FIELD")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "damping")

                joint_attr_box.separator()
                joint_attr_box.label(text="Set Restitution (Bounce):", icon="HANDLE_AUTO")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "restitution")

                joint_attr_box.separator()
                joint_attr_box.label(text="Set Bounce Threshold:", icon="HANDLE_AUTOCLAMPED")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "bounce_threshold")

                joint_attr_box.separator()
                joint_attr_box.label(text="Set Stiffness (Joint Resistance):", icon="IPO_BOUNCE")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "stiffness_enum")

            if physx_enabled and jt in {"prismatic"}:
                joint_attr_box.separator()
                joint_attr_box.label(text="Set Damping:", icon="OUTLINER_OB_FORCE_FIELD")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "damping_linear")

                joint_attr_box.separator()
                joint_attr_box.label(text="Set Restitution (Bounce):", icon="HANDLE_AUTO")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "restitution_linear")

                joint_attr_box.separator()
                joint_attr_box.label(text="Set Bounce Threshold:", icon="HANDLE_AUTOCLAMPED")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "bounce_threshold_linear")

                joint_attr_box.separator()
                joint_attr_box.label(text="Set Stiffness (Joint Resistance):", icon="IPO_BOUNCE")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "stiffness_enum_linear")

            if physx_enabled and jt in {"spherical"}:
                joint_attr_box.separator()
                joint_attr_box.label(text="Set Damping:", icon="OUTLINER_OB_FORCE_FIELD")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "damping_cone")

                joint_attr_box.separator()
                joint_attr_box.label(text="Set Restitution (Bounce):", icon="HANDLE_AUTO")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "restitution_cone")

                joint_attr_box.separator()
                joint_attr_box.label(text="Set Bounce Threshold:", icon="HANDLE_AUTOCLAMPED")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "bounce_threshold_cone")

                joint_attr_box.separator()
                joint_attr_box.label(text="Set Stiffness (Joint Resistance):", icon="IPO_BOUNCE")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "stiffness_enum_cone")

            if physx_enabled and jt in {"distance"}:
                joint_attr_box.separator()
                joint_attr_box.label(text="Set Damping:", icon="OUTLINER_OB_FORCE_FIELD")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "damping_distance")

                joint_attr_box.separator()
                joint_attr_box.label(text="Set Restitution (Bounce):", icon="HANDLE_AUTO")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "restitution_distance")

                joint_attr_box.separator()
                joint_attr_box.label(text="Set Bounce Threshold:", icon="HANDLE_AUTOCLAMPED")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "bounce_threshold_distance")

                joint_attr_box.separator()
                joint_attr_box.label(text="Set Stiffness (Joint Resistance):", icon="IPO_BOUNCE")
                joint_attr_row = joint_attr_box.row()
                joint_attr_row.prop(props, "stiffness_enum_distance")

            # D6 Joints
            if jt in {"d6"}:
                joint_attr_box.label(text="D6 Constraint Settings:")
                joint_attr_box.label(text="X Rotation Constraints")
                joint_attr_box.prop(props, "d6_xrot_low_limit")
                joint_attr_box.prop(props, "d6_xrot_upper_limit")

                if physx_enabled:
                    joint_attr_box.prop(props, "d6_xrot_restitution")
                    joint_attr_box.prop(props, "d6_xrot_bounce_thresh")
                    joint_attr_box.prop(props, "d6_xrot_stiffness")
                    joint_attr_box.prop(props, "d6_xrot_damping")

                joint_attr_box.separator()
                joint_attr_box.label(text="Y Rotation Constraints")
                joint_attr_box.prop(props, "d6_yrot_low_limit")
                joint_attr_box.prop(props, "d6_yrot_upper_limit")

                if physx_enabled:
                    joint_attr_box.prop(props, "d6_yrot_restitution")
                    joint_attr_box.prop(props, "d6_yrot_bounce_thresh")
                    joint_attr_box.prop(props, "d6_yrot_stiffness")
                    joint_attr_box.prop(props, "d6_yrot_damping")

                joint_attr_box.separator()

                joint_attr_box.label(text="Z Rotation Constraints")
                joint_attr_box.prop(props, "d6_zrot_low_limit")
                joint_attr_box.prop(props, "d6_zrot_upper_limit")

                if physx_enabled:
                    joint_attr_box.prop(props, "d6_zrot_restitution")
                    joint_attr_box.prop(props, "d6_zrot_bounce_thresh")
                    joint_attr_box.prop(props, "d6_zrot_stiffness")
                    joint_attr_box.prop(props, "d6_zrot_damping")

                joint_attr_box.separator()

                joint_attr_box.label(text="X Position Constraints")
                joint_attr_box.prop(props, "d6_xpos_low_limit")
                joint_attr_box.prop(props, "d6_xpos_upper_limit")

                if physx_enabled:
                    joint_attr_box.prop(props, "d6_xpos_restitution")
                    joint_attr_box.prop(props, "d6_xpos_bounce_thresh")
                    joint_attr_box.prop(props, "d6_xpos_stiffness")
                    joint_attr_box.prop(props, "d6_xpos_damping")

                joint_attr_box.separator()

                joint_attr_box.label(text="Y Position Constraints")
                joint_attr_box.prop(props, "d6_ypos_low_limit")
                joint_attr_box.prop(props, "d6_ypos_upper_limit")

                if physx_enabled:
                    joint_attr_box.prop(props, "d6_ypos_restitution")
                    joint_attr_box.prop(props, "d6_ypos_bounce_thresh")
                    joint_attr_box.prop(props, "d6_ypos_stiffness")
                    joint_attr_box.prop(props, "d6_ypos_damping")

                joint_attr_box.separator()

                joint_attr_box.label(text="Z Position Constraints")
                joint_attr_box.prop(props, "d6_zpos_low_limit")
                joint_attr_box.prop(props, "d6_zpos_upper_limit")

                if physx_enabled:
                    joint_attr_box.prop(props, "d6_zpos_restitution")
                    joint_attr_box.prop(props, "d6_zpos_bounce_thresh")
                    joint_attr_box.prop(props, "d6_zpos_stiffness")
                    joint_attr_box.prop(props, "d6_zpos_damping")

            # Rack and Pinion type
            if jt in {"rack_and_pinion"}:
                joint_attr_box.label(text="Assign Joints")
                joint_attr_box.prop(props, "rp_hinge")
                joint_attr_box.prop(props, "rp_prismatic")
                joint_attr_box.prop(props, "rp_ratio")
                joint_attr_box.separator()

            if jt in {"gear"}:
                joint_attr_box.label(text="Assign Joints")
                joint_attr_box.prop(props, "gear_hinge_0")
                joint_attr_box.prop(props, "gear_hinge_1")
                joint_attr_box.prop(props, "gear_ratio")
                joint_attr_box.separator()

        else:
            layout.label(text="Choose Body:", icon="PIVOT_BOUNDBOX")
            layout.prop(props, "body_0")

            layout.operator(
                "sr_core.build_unibody_constraints", text="Build Uni-body Constraint", icon="CONSTRAINT_BONE"
            )

        # Drive API section (only shown when not uni_body)
        if not uni_body:
            # Check if we should show drive settings based on joint type
            show_linear_drive = jt == "prismatic"
            show_angular_drive = jt == "revolute"

            # Only show drive box if at least one drive type is applicable
            if show_linear_drive or show_angular_drive:
                layout.separator()
                drive_box = layout.box()
                drive_box.label(text="3. Drive API Settings (Optional):", icon="DRIVER")

                # Linear Drive (only for prismatic joints)
                if show_linear_drive:
                    linear_header = drive_box.row()
                    linear_header.prop(props, "drive_linear_enabled", text="Linear Drive", icon="TRACKING_FORWARDS")

                    if props.drive_linear_enabled:
                        linear_box = drive_box.box()
                        linear_box.label(text="Linear Drive Parameters:", icon="CON_LOCLIKE")

                        # Preset dropdown and apply button
                        preset_row = linear_box.row()
                        preset_row.label(text="Preset:", icon="PRESET")
                        preset_select_row = linear_box.row(align=True)
                        preset_select_row.prop(props, "drive_linear_preset", text="")
                        op = preset_select_row.operator("sr_core.apply_drive_preset", text="Apply", icon="CHECKMARK")
                        op.drive_mode = "linear"

                        linear_box.separator()

                        linear_box.prop(props, "drive_linear_type")
                        linear_box.prop(props, "drive_linear_max_force")
                        linear_box.prop(props, "drive_linear_target_position")
                        linear_box.prop(props, "drive_linear_target_velocity")
                        linear_box.prop(props, "drive_linear_damping")
                        linear_box.prop(props, "drive_linear_stiffness")

                # Angular Drive (only for revolute joints)
                if show_angular_drive:
                    angular_header = drive_box.row()
                    angular_header.prop(
                        props, "drive_angular_enabled", text="Angular Drive", icon="TRACKING_BACKWARDS_SINGLE"
                    )

                    if props.drive_angular_enabled:
                        angular_box = drive_box.box()
                        angular_box.label(text="Angular Drive Parameters:", icon="CON_ROTLIKE")

                        # Preset dropdown and apply button
                        preset_row = angular_box.row()
                        preset_row.label(text="Preset:", icon="PRESET")
                        preset_select_row = angular_box.row(align=True)
                        preset_select_row.prop(props, "drive_angular_preset", text="")
                        op = preset_select_row.operator("sr_core.apply_drive_preset", text="Apply", icon="CHECKMARK")
                        op.drive_mode = "angular"

                        angular_box.separator()

                        angular_box.prop(props, "drive_angular_type")
                        angular_box.prop(props, "drive_angular_max_force")
                        angular_box.prop(props, "drive_angular_target_position")
                        angular_box.prop(props, "drive_angular_target_velocity")
                        angular_box.prop(props, "drive_angular_damping")
                        angular_box.prop(props, "drive_angular_stiffness")

        layout.separator()

        # Show current properties and sync functionality
        if context.active_object:
            obj = context.active_object
            joint_props = {
                k: v for k, v in obj.items() if k.startswith(("pxr:usd:physics", "omni:simready:physx", "drive:"))
            }

            if joint_props:
                # Create collapsible box for properties display
                box = layout.box()

                # Header row with collapse/expand functionality
                header_row = box.row()
                header_row.prop(
                    props,
                    "show_applied_properties",
                    text="",
                    icon="TRIA_DOWN" if props.show_applied_properties else "TRIA_RIGHT",
                    emboss=False,
                )
                header_row.label(text="Applied Properties:", icon="LONGDISPLAY")

                # Only show content if expanded AND auto-sync is disabled
                if props.show_applied_properties and not props.auto_sync_ui:
                    # Add sync button
                    sync_row = box.row()
                    sync_row.operator("sr_core.sync_ui_from_object", text="Sync UI from Object", icon="FILE_REFRESH")
                    sync_row.label(text="", icon="INFO")

                    # Show properties
                    for prop_name, prop_value in joint_props.items():
                        box.label(text=f"{prop_name}: {prop_value}")
                elif props.auto_sync_ui:
                    # Show auto-sync message when auto-sync is enabled
                    box.label(text="Auto-sync is enabled", icon="INFO")
            else:
                layout.label(text="No physics:joint properties applied yet", icon="INFO")

        # Apply button - disabled when uni_body is enabled
        # This button now builds constraints AND applies joint settings in one step
        layout.separator()
        layout.label(text="Build Joint System:", icon="CONSTRAINT_BONE")
        apply_row = layout.row()
        apply_row.enabled = not uni_body
        apply_row.operator("sr_core.apply_joint_settings", text="Build & Apply Joint Settings", icon="CHECKMARK")


class SRCORE_PT_setup_sim_collections(Panel):
    bl_label = "Setup SimReady Export Collections"
    bl_idname = "SRCORE_PT_simready_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        layout.operator("sr_core.create_simready_collections", icon="OUTLINER_COLLECTION")


class SRCORE_PT_grasp_setup(Panel):
    bl_label = "Grasp Setup"
    bl_idname = "SRCORE_PT_grasp_setup"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        grasp_props = scene.grasp_point_props

        # Main controls
        box = layout.box()
        box.label(text="Grasp Point Controls", icon="SPHERE")

        # Create/Clear buttons
        row = box.row(align=True)
        row.operator("sr_core.create_grasp_points", icon="ADD")
        row.operator("sr_core.clear_grasp_points", icon="REMOVE")

        # Global sphere size control
        row = box.row()
        row.prop(grasp_props, "global_sphere_size", text="Global Sphere Size")
        row.operator("sr_core.set_sphere_size", icon="CONSTRAINT", text="")

        # Update positions button
        # box.operator("sr_core.update_grasp_positions", icon='FILE_REFRESH')

        # Only show additional controls if pairs exist
        if len(grasp_props.grasp_pairs) > 0:
            # Grasp pairs list
            box = layout.box()
            box.label(text="Grasp Pairs", icon="OUTLINER_OB_EMPTY")

            # Active pair selector
            row = box.row()
            row.prop(grasp_props, "active_pair_index", text="Active Pair")

            # Show active pair details
            if grasp_props.active_pair_index < len(grasp_props.grasp_pairs):
                active_pair = grasp_props.grasp_pairs[grasp_props.active_pair_index]

                # Position tracking for active pair
                pos_box = layout.box()
                pos_box.label(text=f"Pair {grasp_props.active_pair_index + 1} - Position Tracking", icon="TRACKING")

                # Point 1 position
                col = pos_box.column()
                col.label(text="Point 1 Position:")
                row = col.row()
                row.prop(active_pair, "point_1_position", text="")

                # Point 2 position
                col = pos_box.column()
                col.label(text="Point 2 Position:")
                row = col.row()
                row.prop(active_pair, "point_2_position", text="")

                # Distance display
                col = pos_box.column()
                col.label(text="Distance Between Points:")
                row = col.row()
                row.prop(active_pair, "point_distance", text="")

                # Remove pair button
                row = pos_box.row()
                row.operator("sr_core.remove_grasp_pair", text="Remove This Pair", icon="REMOVE").pair_index = (
                    grasp_props.active_pair_index
                )

            # Status info
            layout.label(text=f"✓ {len(grasp_props.grasp_pairs)} grasp pair(s) active", icon="CHECKMARK")
        else:
            layout.label(text="No grasp pairs created", icon="INFO")


class SRCORE_PT_MJCF_Import(Panel):
    bl_label = "MJCF (MuJoCo) to USD"
    bl_idname = "SRCORE_PT_mjcf_import"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene.joint_attribute_props, "use_included_colliders")
        layout.operator("sr_core.import_mjcf_with_converter", icon="FILE_FOLDER")
        layout.operator("sr_core.export_mjcf", icon="EXPORT")

        # Add repair tool in a separate section
        layout.separator()
        box = layout.box()
        box.label(text="Troubleshooting:", icon="TOOL_SETTINGS")
        box.operator("sr_core.repair_mujoco_converter", icon="FILE_REFRESH", text="Repair Converter")


class SRCORE_RUNTIME_PT_throw_rigidbody(Panel):
    bl_idname = "SRCORE_RUNTIME_PT_throw_rigidbody"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SR_Physics_Runtime"
    bl_label = "Throw Rigid Body"

    def draw(self, context):
        layout = self.layout
        scene = context.scene  # noqa F841
        speed_props = context.scene.throw_rb_props

        intro_ui = layout.box()
        intro_ui.label(text="This UI is for testing physics.", icon="SHADERFX")
        intro_ui.label(text="1. Convert jnts to rbds.")
        intro_ui.label(text="2. Create physics environment.")
        intro_ui.label(text="3. Add rbds to physics environment.")
        intro_ui.label(text="This portion is a work in progress...")

        body_ui = layout.box()

        body_ui.label(text="Shift+RMB to start, release to throw")
        body_ui.label(text="IMPORTANT:PLEASE READ!!!")
        body_ui.label(text="PRESS Undo after stopping timeline to restore original state.")
        body_ui.operator("sr_psy_core.throw_rigidbody", text="Start Throw (also Shift+RMB)")
        body_ui.separator()
        body_ui.prop(speed_props, "speed_scale")
        body_ui.prop(speed_props, "max_speed")

        # Restore button
        body_ui.separator()
        body_ui.operator("sr_psy_core.reset", text="Reset")

        body_2_ui = layout.box()
        body_2_ui.label(text="Create Physics Environment for testing physics")
        body_2_ui.operator("sr_psy_core.joints_to_rbds", text="Convert Joints to Rigid Bodies", icon="BONE_DATA")
        body_2_ui.operator("sr_psy_core.create_physics_env", text="Create Physics Environment", icon="CUBE")
        body_2_ui.operator(
            "sr_psy_core.add_objects_to_physics_env", text="Add rbd obj(s) to Physics Environment", icon="RNA_ADD"
        )


# DEBUG
# def main():
#     # Set up file path
#     file_path = r"C:\git\mujoco\doc\_static\example.xml"  # Change this to your file path

#     # Import MJCF
#     import_mjcf(file_path)
