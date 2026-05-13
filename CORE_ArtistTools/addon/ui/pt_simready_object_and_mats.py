# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import json
import os

from bpy.types import Panel

# Panel UI

# TODO: create an object panel for the usd physics mass
# usually artists have materials as instances of each other
# using the material properties panel is not ideal for this reason.  Each mass must apply to each object.

# class OBJECT_PT_usd_physics_mass(Panel):
#     bl_label = "Usd Physics Mass"
#     bl_idname = "OBJECT_PT_usd_physics_mass"
#     bl_space_type = "PROPERTIES"
#     bl_region_type = "WINDOW"
#     bl_context = "object"

#     @classmethod
#     def poll(cls, context):
#         return context.object is not None

#     def draw(self, context):
#         layout = self.layout
#         obj = context.object
#         sim_props = obj.simready_props


class MATERIAL_PT_simready_nonvisual(Panel):
    bl_label = "SimReady Non-Visual Settings"
    bl_idname = "MATERIAL_PT_simready_nonvisual"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        return context.material is not None

    def draw(self, context):
        layout = self.layout
        mat = context.material
        sim_props = mat.simready_props

        # Check if attributes are properly set
        # Allow "none", "None", "NONE" as valid string values, but prevent None (null), empty string, etc.
        base_set = sim_props.base is not None and sim_props.base != ""
        coating_set = sim_props.coating is not None and sim_props.coating != ""
        attributes_set = sim_props.selected_items_display is not None and sim_props.selected_items_display != ""
        all_attributes_set = base_set and coating_set and attributes_set

        # Show status and main controls
        if not all_attributes_set:
            # Show warning
            warning_box = layout.box()
            warning_box.alert = True
            warning_box.label(text="⚠️ SimReady Attributes Required")
            warning_box.label(text="Set Base, Coating, and Attributes below")
        else:
            # Show success message
            success_box = layout.box()
            success_box.alert = False
            success_box.label(text="✅ SimReady Attributes Set")

            # Display current values
            info_row = success_box.row()
            info_row.label(text=f"Base: {sim_props.base}")
            info_row = success_box.row()
            info_row.label(text=f"Coating: {sim_props.coating}")
            info_row = success_box.row()
            info_row.label(text=f"Attributes: {sim_props.selected_items_display}")

        layout.separator()

        # Main controls - these are the primary way to set attributes
        layout.prop(sim_props, "base")
        layout.prop(sim_props, "coating")
        layout.prop(sim_props, "attributes")

        # The main enforcement button - users must click this to add attributes
        main_button = layout.row()
        main_button.scale_y = 1.2
        main_button.operator("simready.add_enum_to_list", text="Set Nonvisual Attributes", icon="ADD")

        layout.label(text="Current Attributes:")
        layout.label(text=sim_props.selected_items_display)
        layout.operator("simready.clear_enum_list", icon="X")

        layout.label(text="")
        row = layout.row()
        row.operator("simready.autopop_base", icon="DISC")
        row.operator("simready.autopop_coating", icon="DISC")

        # Add separator
        layout.separator()

        # Physics Material Properties
        box = layout.box()
        box.label(text="Usd Physics Material Properties")

        # Get the path to the physics_materials.json file
        addon_path = os.path.dirname(os.path.dirname(__file__))
        json_path = os.path.join(addon_path, "resource", "physics_materials.json")

        try:
            with open(json_path, "r") as f:
                physics_materials = json.load(f)

            # Add dropdown for material selection
            row = box.row()
            row.prop(sim_props, "physx_material_type", text="Material Type")

            # If a material is selected, show its properties
            if sim_props.physx_material_type in physics_materials:
                material = physics_materials[sim_props.physx_material_type]

                # Create a row for each property
                for prop_name, value in material.items():
                    row = box.row()
                    row.label(text=prop_name.replace("physics:", "").title())
                    row.prop(sim_props, f"physx_{prop_name.replace('physics:', '')}", text="")

                # Display calculated mass and center of mass
                if context.object and context.object.type == "MESH":
                    # Add a separator
                    box.separator()

                    # Display calculated properties
                    box.label(text="Calculated Properties:")

                    # Mass
                    row = box.row()
                    row.label(text="Mass:")
                    row.label(text=f"{sim_props.physx_mass:.2f} kg")

                    # Center of Mass
                    row = box.row()
                    row.label(text="Center of Mass:")
                    com = sim_props.physx_centerofmass
                    row.label(text=f"({com[0]:.2f}, {com[1]:.2f}, {com[2]:.2f})")

                # Add button to assign properties
                row = box.row()
                row.operator(
                    "simready.assign_physx_properties", text="Assign to Material (can be multiple)", icon="CHECKMARK"
                )

        except Exception as e:
            box.label(text=f"Error loading PhysX materials: {str(e)}")


class WD_PT_panel(Panel):
    bl_label = "Wikidata Metadata"
    bl_idname = "WD_PT_object_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Show the use id checkbox
        layout.prop(scene.global_metadata, "wikidata_use_id")

        # Show the search input - disabled when using ID mode
        query_row = layout.row()
        query_row.enabled = not scene.global_metadata.wikidata_use_id
        query_row.prop(scene, "wikidata_query")

        query_id_row = layout.row()
        query_id_row.enabled = scene.global_metadata.wikidata_use_id
        query_id_row.prop(scene.global_metadata, "wikidata_query_id")

        # Check if the appropriate field is valid based on mode
        use_id_mode = scene.global_metadata.wikidata_use_id
        if use_id_mode:
            query = getattr(scene.global_metadata, "wikidata_query_id", "")
        else:
            query = getattr(scene, "wikidata_query", "")
        has_valid_query = bool(query and query.strip())

        # Search button - only enabled if we have a valid search term or ID
        search_row = layout.row(align=True)
        search_row.enabled = has_valid_query
        if not has_valid_query:
            search_row.label(text="", icon="ERROR")
        btn_text = "Search by ID" if use_id_mode else "Search"
        search_row.operator("wd.refresh_results", text=btn_text)

        # Results section - only show if we have valid query AND valid results
        has_results = hasattr(scene, "wikidata_results") and scene.wikidata_results and scene.wikidata_results != "NONE"

        if has_valid_query and has_results:
            layout.separator()
            layout.prop(scene, "wikidata_results", text="Result")

            # Apply button - only enabled if we have a selected result
            apply_row = layout.row()
            apply_row.enabled = scene.wikidata_results != "NONE"
            apply_row.operator("wd.apply_to_object", text="Apply to Object & Mesh")
        elif has_valid_query and not has_results:
            # Show a hint when query is valid but no results yet
            info_row = layout.row()
            info_row.label(text="Click Search to find results", icon="INFO")
        elif not has_valid_query:
            # Show a hint when no valid search term
            info_row = layout.row()
            info_row.label(text="Enter a search term above", icon="QUESTION")


class WD_PT_data_panel(Panel):
    bl_label = "Wikidata Metadata"
    bl_idname = "WD_PT_data_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == "MESH"

    def draw(self, context):
        layout = self.layout
        obj = context.object
        scene = context.scene

        if obj and obj.type == "MESH":
            mesh = obj.data

            # Show existing Wikidata properties on the object
            obj_wikidata_props = {k: v for k, v in obj.items() if k.startswith("semantics:labels:wikidata")}

            # Show existing Wikidata properties on the mesh
            mesh_wikidata_props = {k: v for k, v in mesh.items() if k.startswith("semantics:labels:wikidata")}

            # Combined Properties Section
            if obj_wikidata_props or mesh_wikidata_props:
                box = layout.box()
                box.label(text="Applied Wikidata Properties:")

                if obj_wikidata_props:
                    box.label(text="Object Properties:")
                    for prop_name, prop_value in obj_wikidata_props.items():
                        row = box.row()
                        row.label(text=f"  {prop_name}:")
                        row.label(text=str(prop_value))

                if mesh_wikidata_props:
                    box.label(text="Mesh Properties:")
                    for prop_name, prop_value in mesh_wikidata_props.items():
                        row = box.row()
                        row.label(text=f"  {prop_name}:")
                        row.label(text=str(prop_value))

                # Add button to remove Wikidata properties from both
                box.operator("wd.remove_from_object", text="Remove All Wikidata Properties", icon="X")
            else:
                layout.label(text="No Wikidata properties applied.")

            # Add separator
            layout.separator()

            # Add button to apply to both object and mesh
            if hasattr(scene, "wikidata_results") and scene.wikidata_results != "NONE":
                layout.operator("wd.apply_to_object", text="Apply Wikidata to Object & Mesh", icon="CHECKMARK")
            else:
                layout.label(text="Search for Wikidata data in the Object Properties panel first.")


# TODO: Keeping this here in case it's needed, but it is unused currently.
class DOCSTRING_PT_CaptionPanel(Panel):
    bl_label = "DOCSTRING Caption Generator"
    bl_idname = "DOCSTRING_PT_caption_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        layout = self.layout
        layout.operator("simready.generate_caption")
        obj = context.object
        if obj and "omni:simready:documentation" in obj:
            layout.prop(obj, '["omni:simready:documentation"]', text="Description")
        else:
            layout.label(text="No caption found on this object.")
