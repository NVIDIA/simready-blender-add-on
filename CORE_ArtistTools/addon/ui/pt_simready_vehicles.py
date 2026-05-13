# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup


class AVSim_OT_set_light_color(Operator):
    """
    Set Light Color Preset
    """

    bl_label = "Set Light Color"
    bl_idname = "avsim.set_light_color"
    bl_description = "Set light color preset"

    color: FloatVectorProperty(name="Color", subtype="COLOR", size=3, min=0.0, max=1.0)

    def execute(self, context):
        avsim_props = context.scene.avsim_props
        avsim_props.vehicle_light_color = self.color
        return {"FINISHED"}


class AVSimProps(PropertyGroup):
    selected_vehicle_part: EnumProperty(
        name="Vehicle Part",
        description="Select a vehicle part to configure",
        items=[
            ("NONE", "None", "No part selected"),
            ("body", "Body", "Body properties"),
            ("brakes", "Brakes", "Brakes properties"),
            ("door", "Door", "Door properties"),
            ("fork", "Fork", "Fork properties"),
            ("handlebars", "Handlebars", "Handlebars properties"),
            ("light", "Light", "Light properties"),
            ("pedal", "Pedal", "Pedal properties"),
            ("pedals", "Pedals", "Pedals properties"),
            ("plate", "License Plate", "License Plate properties"),
            ("task", "Task", "Task properties"),
            ("trunk", "Trunk", "Trunk properties"),
            ("vehicle", "Vehicle", "Vehicle properties"),
            ("wheel", "Wheel", "Wheel properties"),
            ("window", "Window", "Window properties"),
        ],
        default="NONE",
    )

    task_group: StringProperty(name="Task Group", description="Task group identifier", default="Passenger")

    task_effector: EnumProperty(
        name="Task Effector",
        description="Select the effector for the task",
        items=[
            ("leftHand", "Left Hand", "Left hand effector"),
            ("rightHand", "Right Hand", "Right hand effector"),
            ("leftFoot", "Left Foot", "Left foot effector"),
            ("rightFoot", "Right Foot", "Right foot effector"),
            ("pelvis", "Pelvis", "Pelvis effector"),
        ],
        default="leftHand",
    )

    task_type: EnumProperty(
        name="Task Type",
        description="Select the type of task",
        items=[
            ("pickupObject", "Pickup Object", "Pickup object task"),
            ("touchObject", "Touch Object", "Touch object task"),
            ("sitDown", "Sit Down", "Sit down task"),
            ("rideObject", "Ride Object", "Ride object task"),
        ],
        default="pickupObject",
    )

    vehicle_year: StringProperty(name="Year", description="Vehicle year", default="2015")

    vehicle_model: StringProperty(name="Model", description="Vehicle model", default="Macan")

    vehicle_make: StringProperty(name="Make", description="Vehicle make", default="Porsche")

    vehicle_engine_rpm: FloatProperty(name="Engine RPM", description="Engine RPM", default=66000.0)

    vehicle_light_type: EnumProperty(
        name="Light Type",
        description="Select the type of light",
        items=[
            ("brakeLights", "Brake Lights", "Brake lights"),
            ("emergencyLights", "Emergency Lights", "Emergency lights"),
            ("fogLights", "Fog Lights", "Fog lights"),
            ("headLights", "Head Lights", "Head lights"),
            ("highbeamLights", "Highbeam Lights", "Highbeam lights"),
            ("markerLights", "Marker Lights", "Marker lights"),
            ("nightLights", "Night Lights", "Night lights"),
            ("parkingLights", "Parking Lights", "Parking lights"),
            ("plateLights", "Plate Lights", "License plate lights"),
            ("reverseLights", "Reverse Lights", "Reverse lights"),
            ("runningLights", "Running Lights", "Running lights"),
            ("signalLights", "Signal Lights", "Signal lights"),
            ("signalLightsL", "Signal Lights Left", "Left signal lights"),
            ("signalLightsR", "Signal Lights Right", "Right signal lights"),
            ("tailLights", "Tail Lights", "Tail lights"),
        ],
        default="headLights",
    )

    vehicle_light_duration: FloatProperty(
        name="Duration(seconds)", description="Light duration in seconds", default=1.2, min=0.0
    )

    vehicle_light_intensity_min: FloatProperty(
        name="Intensity Min (lumens)", description="Minimum light intensity", default=0.0, min=0.0
    )

    vehicle_light_intensity_max: FloatProperty(
        name="Intensity Max (lumens)",
        description="Maximum light intensity (10k consumer vehicles, 30k emergency vehicles)",
        default=10000.0,
        min=0.0,
    )

    vehicle_light_color: FloatVectorProperty(
        name="Color",
        description="Light color (RGB)",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(1.0, 1.0, 0.0),
    )

    # Vehicle Attributes Properties
    vehicle_longitudinal_axis: EnumProperty(
        name="Longitudinal Axis",
        description="Select the longitudinal axis of the vehicle",
        items=[
            ("negX", "Negative X", "Negative X axis"),
            ("negY", "Negative Y", "Negative Y axis"),
            ("negZ", "Negative Z", "Negative Z axis"),
            ("posX", "Positive X", "Positive X axis"),
            ("posY", "Positive Y", "Positive Y axis"),
            ("posZ", "Positive Z", "Positive Z axis"),
        ],
        default="posX",
    )

    vehicle_drivetrain: EnumProperty(
        name="Drivetrain",
        description="Select the drivetrain type",
        items=[
            ("RWD", "Rear Wheel Drive", "Rear wheel drive"),
            ("4WD", "Four Wheel Drive", "Four wheel drive"),
            ("AWD", "All Wheel Drive", "All wheel drive"),
            ("FWD", "Front Wheel Drive", "Front wheel drive"),
        ],
        default="RWD",
    )

    vehicle_steering: EnumProperty(
        name="Steering",
        description="Select the steering type",
        items=[
            ("front", "Front", "Front wheel steering"),
            ("back", "Back", "Back wheel steering"),
            ("all", "All", "All wheel steering"),
            ("none", "None", "No steering"),
            ("tank", "Tank", "Tank steering"),
        ],
        default="front",
    )

    # Optional Asset Info Properties
    vehicle_engine_horsepower: FloatProperty(name="Engine Horsepower", description="Engine horsepower", default=439.0)

    vehicle_engine_mapping: StringProperty(name="Engine Mapping", description="Engine mapping", default="2.9 L V6")


class AVSim_OT_generate_vehicle_attributes(Operator):
    bl_label = "Add Vehicle Attributes"
    bl_idname = "avsim.add_vehicle_attributes"
    bl_description = "Add Vehicle Attributes"

    @classmethod
    def poll(cls, context):
        avsim_props = context.scene.avsim_props
        return (
            context.selected_objects is not None
            and len(context.selected_objects) > 0
            and avsim_props.selected_vehicle_part != "NONE"
        )

    def execute(self, context):
        # Check if an object is selected
        if not context.selected_objects:
            self.report({"ERROR"}, "No object selected")
            return {"CANCELLED"}

        obj = context.selected_objects[0]
        avsim_props = context.scene.avsim_props
        part_type = avsim_props.selected_vehicle_part

        # Remove all existing omni:simready:vehicle properties
        props_to_remove = [k for k in obj.keys() if k.startswith("omni:simready:vehicle")]
        for prop in props_to_remove:
            del obj[prop]

        if part_type == "NONE":
            return {"CANCELLED"}

        # Add the base vehicle part property
        obj["omni:simready:vehicle"] = part_type

        # Handle specific properties based on part type
        if part_type == "vehicle":
            if avsim_props.vehicle_longitudinal_axis:
                obj["omni:simready:vehicle:longitudinal_axis"] = avsim_props.vehicle_longitudinal_axis
            if avsim_props.vehicle_drivetrain:
                obj["omni:simready:vehicle:drivetrain"] = avsim_props.vehicle_drivetrain
            if avsim_props.vehicle_steering:
                obj["omni:simready:vehicle:steering"] = avsim_props.vehicle_steering

            # Optional vehicle properties
            # TODO: Not sure how they want this situated in the USD file, need to see example, looks like customLayerData
            if avsim_props.vehicle_engine_horsepower:
                obj["omni:simready:vehicle:engine_horsepower"] = avsim_props.vehicle_engine_horsepower
            if avsim_props.vehicle_engine_mapping:
                obj["omni:simready:vehicle:engine_mapping"] = avsim_props.vehicle_engine_mapping
            if avsim_props.vehicle_engine_rpm:
                obj["omni:simready:vehicle:engine_rpm"] = avsim_props.vehicle_engine_rpm
            if avsim_props.vehicle_make:
                obj["omni:simready:vehicle:make"] = avsim_props.vehicle_make
            if avsim_props.vehicle_model:
                obj["omni:simready:vehicle:model"] = avsim_props.vehicle_model
            if avsim_props.vehicle_year:
                obj["omni:simready:vehicle:year"] = avsim_props.vehicle_year

        elif part_type == "light":
            if avsim_props.vehicle_light_type:
                obj["omni:simready:vehicle:light_type"] = avsim_props.vehicle_light_type
            if avsim_props.vehicle_light_duration:
                obj["omni:simready:vehicle:light_duration"] = avsim_props.vehicle_light_duration
            if avsim_props.vehicle_light_intensity_min:
                obj["omni:simready:vehicle:light_intensity_min"] = avsim_props.vehicle_light_intensity_min
            if avsim_props.vehicle_light_intensity_max:
                obj["omni:simready:vehicle:light_intensity_max"] = avsim_props.vehicle_light_intensity_max
            if avsim_props.vehicle_light_color:
                obj["omni:simready:vehicle:light_color"] = avsim_props.vehicle_light_color

        elif part_type == "task":
            if avsim_props.task_type:
                obj["omni:simready:vehicle:task_type"] = avsim_props.task_type
            if avsim_props.task_effector:
                obj["omni:simready:vehicle:task_effector"] = avsim_props.task_effector
            if avsim_props.task_group:
                obj["omni:simready:vehicle:task_group"] = avsim_props.task_group

        self.report({"INFO"}, f"Added {part_type} attributes to {obj.name}")
        return {"FINISHED"}


class AVSim_PT_vehicle_attributes(Panel):
    bl_label = "SR Vehicle Attributes"
    bl_idname = "CORE_PT_veh_attributes"
    bl_description = "Simready | AVSim Vehicle Attribute Helper"
    bl_category = "AVSim"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Vehicle Parts Annotation Helper")
        avsim_props = context.scene.avsim_props

        # Show selected object info
        if context.selected_objects:
            layout.label(text=f"Selected: {context.selected_objects[0].name}")
        else:
            layout.label(text="No object selected", icon="ERROR")

        # Add dropdown menu for vehicle parts
        layout.prop(avsim_props, "selected_vehicle_part", text="Select Part Type:", icon="PROP_CON")

        # Show additional UI based on selection
        if avsim_props.selected_vehicle_part == "vehicle":
            box = layout.box()
            box.label(text=f"Properties for omni:simready:vehicle='{avsim_props.selected_vehicle_part}'")

            # Longitudinal Axis
            box.prop(avsim_props, "vehicle_longitudinal_axis", text="Longitudinal Axis")

            # Drivetrain
            box.prop(avsim_props, "vehicle_drivetrain", text="Drivetrain")

            # Steering
            box.prop(avsim_props, "vehicle_steering", text="Steering")

            # Optional Asset Info
            box.label(text="Optional Asset Info:")
            box.prop(avsim_props, "vehicle_engine_horsepower", text="Engine Horsepower")
            box.prop(avsim_props, "vehicle_engine_mapping", text="Engine Mapping")
            box.prop(avsim_props, "vehicle_engine_rpm", text="Engine RPM")
            box.prop(avsim_props, "vehicle_make", text="Make")
            box.prop(avsim_props, "vehicle_model", text="Model")
            box.prop(avsim_props, "vehicle_year", text="Year")

        if avsim_props.selected_vehicle_part == "body":
            box2 = layout.box()
            box2.label(
                text="Press Apply below to add omni:simready:vehicle = 'body' annotation to the selected object/empty."
            )

        if avsim_props.selected_vehicle_part == "door":
            box3 = layout.box()
            box3.label(
                text="Press Apply below to add omni:simready:vehicle = 'door' annotation to the selected object/empty."
            )

        if avsim_props.selected_vehicle_part == "window":
            box4 = layout.box()
            box4.label(
                text="Press Apply below to add omni:simready:vehicle = 'window' annotation to the selected object/empty."
            )

        if avsim_props.selected_vehicle_part == "trunk":
            box5 = layout.box()
            box5.label(
                text="Press Apply below to add omni:simready:vehicle = 'trunk' annotation to the selected object/empty."
            )

        if avsim_props.selected_vehicle_part == "wheel":
            box6 = layout.box()
            box6.label(
                text="Press Apply below to add omni:simready:vehicle = 'wheel' annotation to the selected object/empty."
            )

        if avsim_props.selected_vehicle_part == "brakes":
            box7 = layout.box()
            box7.label(
                text="Press Apply below to add omni:simready:vehicle = 'brakes' annotation to the selected object/empty."
            )

        if avsim_props.selected_vehicle_part == "light":
            box8 = layout.box()
            box8.label(text="Light Properties")

            # Light Type Dropdown
            box8.prop(avsim_props, "vehicle_light_type", text="Light Type")

            # Light Duration
            box8.prop(avsim_props, "vehicle_light_duration", text="Duration(seconds)")

            # Light Intensity Domain
            row = box8.row()
            row.prop(avsim_props, "vehicle_light_intensity_min", text="Intensity Min (lumens)")
            row.prop(avsim_props, "vehicle_light_intensity_max", text="Intensity Max (lumens)")

            # Light Color
            box8.label(text="Light Color (RGB)")
            row = box8.row()
            row.prop(avsim_props, "vehicle_light_color", text="")

            # Color Presets
            box8.label(text="Color Presets:")
            row = box8.row(align=True)
            op = row.operator("avsim.set_light_color", text="Orange")
            op.color = (1.0, 0.5, 0.0)  # Orange
            op = row.operator("avsim.set_light_color", text="Red")
            op.color = (1.0, 0.0, 0.0)  # Red
            op = row.operator("avsim.set_light_color", text="Blue-White")
            op.color = (0.9, 0.9, 1.0)  # Blueish white

        if avsim_props.selected_vehicle_part == "plate":
            box9 = layout.box()
            box9.label(
                text="Press Apply below to add omni:simready:vehicle = 'plate' annotation to the selected object/empty."
            )

        if avsim_props.selected_vehicle_part == "pedal":
            box10 = layout.box()
            box10.label(
                text="Press Apply below to add omni:simready:vehicle = 'pedal' annotation to the selected object/empty."
            )

        if avsim_props.selected_vehicle_part == "pedals":
            box11 = layout.box()
            box11.label(
                text="Press Apply below to add omni:simready:vehicle = 'pedals' annotation to the selected object/empty."
            )

        if avsim_props.selected_vehicle_part == "handlebars":
            box12 = layout.box()
            box12.label(
                text="Press Apply below to add omni:simready:vehicle = 'handlebars' annotation to the selected object/empty."
            )

        if avsim_props.selected_vehicle_part == "fork":
            box13 = layout.box()
            box13.label(
                text="Press Apply below to add omni:simready:vehicle = 'fork' annotation to the selected object/empty."
            )

        if avsim_props.selected_vehicle_part == "task":
            box14 = layout.box()
            box14.label(text="Task Properties")

            # Task Type
            box14.prop(avsim_props, "task_type", text="Task Type")

            # Task Effector
            box14.prop(avsim_props, "task_effector", text="Task Effector")

            # Task Group
            box14.prop(avsim_props, "task_group", text="Task Group")

        layout.operator("avsim.add_vehicle_attributes", text="Add Vehicle Parts Annotation Attributes", icon="TAG")

        # Show current properties
        if context.selected_objects:
            obj = context.selected_objects[0]
            simready_props = {k: v for k, v in obj.items() if k.startswith("omni:simready:vehicle")}

            if simready_props:
                box = layout.box()
                box.label(text="Applied Properties:", icon="LONGDISPLAY")
                for prop_name, prop_value in simready_props.items():
                    box.label(text=f"{prop_name}: {prop_value}")
            else:
                layout.label(text="No omni:simready:vehicle properties applied yet", icon="INFO")
