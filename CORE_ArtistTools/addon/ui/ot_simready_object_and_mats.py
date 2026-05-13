# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import difflib
import json
import os
from typing import Dict

import bmesh
import bpy
import mathutils
import numpy as np
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, StringProperty
from bpy.types import Operator, PropertyGroup

from ..library.simready_utils import (
    generate_caption,
    load_blip_model,
    update_enum_items,
)

NONVISUAL_BASE_TOKENS = [
    "",
    "none",
    # Metals:
    "aluminum",
    "steel",
    "oxidized_steel",
    "iron",
    "oxidized_iron",
    "silver",
    "brass",
    "bronze",
    "oxidized_Bronze_Patina",
    "tin",
    # Polymers:
    "plastic",
    "fiberglass",
    "carbon_fiber",
    "vinyl",
    "plexiglass",
    "pvc",
    "nylon",
    "polyester",
    # Glass:
    "clear_glass",
    "frosted_glass ",
    "one_way_mirror",
    "mirror",
    "ceramic_glass",
    # Other:
    "asphalt",
    "concrete",
    "leaf_grass",
    "dead_leaf_grass",
    "rubber",
    "wood",
    "bark",
    "cardboard",
    "paper",
    "fabric",
    "skin",
    "fur_hair",
    "leather",
    "marble",
    "brick",
    "stone",
    "gravel",
    "dirt",
    "mud",
    "water",
    "salt_water",
    "snow",
    "ice",
    "calibration_lambertian",
]

NONVISUAL_COATING_TOKENS = ["", "none", "clearcoat", "paint", "paint_clearcoat"]

NONVISUAL_ATTR_TOKENS = ["", "none", "emissive", "retroreflective", "single_sided", "visually_transparent"]

# Safety:
NONVISUAL_BASE_TOKENS = [t.strip() for t in NONVISUAL_BASE_TOKENS if t]
NONVISUAL_COATING_TOKENS = [t.strip() for t in NONVISUAL_COATING_TOKENS if t]
NONVISUAL_ATTR_TOKENS = [t.strip() for t in NONVISUAL_ATTR_TOKENS if t]


# Sort all tokens, leave None as the first
NONVISUAL_BASE_TOKENS = sorted(NONVISUAL_BASE_TOKENS, key=lambda x: (x != "none", x))

NONVISUAL_COATING_TOKENS = sorted(NONVISUAL_COATING_TOKENS, key=lambda x: (x != "none", x))

NONVISUAL_ATTR_TOKENS = sorted(NONVISUAL_ATTR_TOKENS, key=lambda x: (x != "none", x))


SYNONYM_MAP = {
    "plexi-glass": "plexiglass",
    "plexiglas": "plexiglass",
    "plexi": "plexiglass",
    "mirror glass": "mirror",
    "patina bronze": "oxidized_Bronze_Patina",
    "oxidized bronze": "oxidized_Bronze_Patina",
    "dead leaf": "dead_leaf_grass",
    "leaf": "leaf_grass",
    "nylone": "nylon",
    "fur": "fur_hair",
    "hair": "fur_hair",
    "lether": "leather",
    "wooden": "wood",
    "concret": "concrete",
    "muddy": "mud",
    "icey": "ice",
    "snowy": "snow",
    "clear": "clear_glass",
    "frosted": "frosted_glass",
    "paint_clearcoat": "none",
    "paint": "none",
    "cardboard": "cardboard",
    "glass": "clear_glass",
    "metal": "steel",
    "metal1": "steel",
    "steel": "steel",
    "rail": "steel",
    "concrete": "concrete",
    "concrete1": "concrete",
    "pavement": "concrete",
    "sidewalk": "concrete",
    "side": "concrete",
    "gravel": "gravel",
    "cement": "concrete",
    "asphalt": "asphalt",
    "wood": "wood",
    "rubber": "rubber",
    "plastic": "plastic",
    "vinyl": "vinyl",
    "stone": "stone",
    "rock": "stone",
    "leather": "leather",
    "fabric": "fabric",
    "organic": "skin",
    "lights": "clear_glass",
    "traffic": "aluminum",
    "aluminum": "aluminum",
    "terrain": "dirt",
    "brick": "brick",
    "bark": "bark",
    "ice": "ice",
    "salt_water": "salt_water",
    "water": "water",
    "snow": "snow",
    "paper": "paper",
    "mirror": "mirror",
}

SYNONYM_MAP_COATING = {
    "opaque": "none",
    "clearcoat": "clearcoat",
    "traffic": "paint",
    "paint": "paint",
    "lanemarking": "paint",
    "lanemark": "paint",
    "lanemarkings": "paint",
    "retropaint": "paint",
    "retroreflective": "paint",
    "retro": "paint",
    "paint_clearcoat": "paint_clearcoat",
}


# Make a fuzzy match helper
def fuzzy_find_material_token(user_input, token_list, synonyms=None, cutoff=0.65):
    synonyms = synonyms or {}
    normalized_input = user_input.strip().lower().replace("-", "_").replace(" ", "_")

    # 1. Check synonyms
    if normalized_input in synonyms:
        return synonyms[normalized_input]

    # 2. Fallback to difflib fuzzy matching
    matches = difflib.get_close_matches(normalized_input, token_list, n=1, cutoff=cutoff)
    return matches[0] if matches else None


# Define the dropdown options
nonvisual_base_items = []
nonvisual_coating_items = []
nonvisual_attributes_items = []

for token in NONVISUAL_BASE_TOKENS:
    if token == "":
        nonvisual_base_items.append(("", "None", "No base set"))
    else:
        label = token
        tooltip = f"Set base material to {label}"
        nonvisual_base_items.append((token, label, tooltip))

for token in NONVISUAL_COATING_TOKENS:
    if token == "":
        nonvisual_coating_items.append(("", "None", "No coating set"))
    else:
        label = token
        tooltip = f"Set coating material to {label}"
        nonvisual_coating_items.append((token, label, tooltip))

for token in NONVISUAL_ATTR_TOKENS:
    if token == "":
        nonvisual_attributes_items.append(("", "None", "No attribute set"))
    else:
        label = token
        tooltip = f"Set attribute material to {label}"
        nonvisual_attributes_items.append((token, label, tooltip))


def get_attribute_items(self, context):
    return [(token, token, f"Add '{token}' to attributes") for token in NONVISUAL_ATTR_TOKENS]


def get_physx_material_types(self, context):
    addon_path = os.path.dirname(os.path.dirname(__file__))
    json_path = os.path.join(addon_path, "resource", "physics_materials.json")

    try:
        with open(json_path, "r") as f:
            physics_materials = json.load(f)
            # Create list of tuples with formatted names, sorted alphabetically
            material_items = [(name, name.replace("_", " ").title(), "") for name in sorted(physics_materials.keys())]
            # Add default none option at the beginning
            return [("none", "None", "")] + material_items
    except Exception:
        return [("none", "None", "")]


def get_physx_material_types_overload() -> dict:
    addon_path = os.path.dirname(os.path.dirname(__file__))
    json_path = os.path.join(addon_path, "resource", "physics_materials.json")

    try:
        with open(json_path, "r") as f:
            physics_materials = json.load(f)
            return physics_materials
    except Exception:
        return {}


def update_physx_properties_callback(self, context):
    """Update PhysX properties when material type changes.

    This is called directly from the property update callback, so 'self' is the
    SimReadyMaterialProps instance that owns the material.

    Args:
        self: The SimReadyMaterialProps instance
        context: The Blender context
    """
    material_type = self.physx_material_type

    if material_type == "none":
        return

    # Get the path to the physics_materials.json file
    addon_path = os.path.dirname(os.path.dirname(__file__))
    json_path = os.path.join(addon_path, "resource", "physics_materials.json")

    try:
        with open(json_path, "r") as f:
            physics_materials = json.load(f)

        if material_type in physics_materials:
            material = physics_materials[material_type]

            # Update the properties directly on self (SimReadyMaterialProps)
            for prop_name, value in material.items():
                prop_id = f"physx_{prop_name.replace('physics:', '')}"
                if hasattr(self, prop_id):
                    setattr(self, prop_id, value)
    except Exception as e:
        print(f"Error updating PhysX properties: {str(e)}")


class SimReadyMaterialProps(PropertyGroup):
    def add_attribute(self):
        current = [a.strip() for a in self.combined_attrs.split(",") if a.strip()]
        if self.selected_attr not in current:
            current.append(self.selected_attr)
        self.combined_attrs = ", ".join(current)

    base: EnumProperty(
        name="Base",
        items=nonvisual_base_items,
        update=lambda self, context: self.update_material_property(context, "omni:simready:nonvisual:base", self.base),
    )

    coating: EnumProperty(
        name="Coating",
        items=nonvisual_coating_items,
        update=lambda self, context: self.update_material_property(
            context, "omni:simready:nonvisual:coating", self.coating
        ),
    )

    attributes: EnumProperty(
        name="Attributes",
        items=get_attribute_items,
        # update=lambda self, context: self._update_material_property(context, "omni:simready:nonvisual:attributes", self.attributes)
    )

    combined_attrs: StringProperty(
        name="Attributes",
        description="Comma-separated attributes",
        # update=lambda self, context: self._update_material_property(context, "omni:simready:nonvisual:attributes", self.attributes),
        default="",
    )

    # PhysX Material Properties
    physx_material_type: EnumProperty(
        name="Physics Material Type",
        description="Select a physics material type",
        items=get_physx_material_types,
        update=lambda self, context: update_physx_properties_callback(self, context),
    )

    # Dynamic PhysX properties
    physx_density: FloatProperty(name="Density", default=1000.0, min=0.0)

    physx_dynamicFriction: FloatProperty(name="Dynamic Friction", default=0.5, min=0.0, max=1.0)

    physx_restitution: FloatProperty(name="Restitution", default=0.5, min=0.0, max=1.0)

    physx_staticFriction: FloatProperty(name="Static Friction", default=0.5, min=0.0, max=1.0)

    physx_fillRatio: FloatProperty(name="Fill Ratio", default=0.5, min=0.0, max=1.0)

    physx_thickness: FloatProperty(name="Thickness", default=0.005, min=0.0)

    # Calculated mass properties
    physx_mass: FloatProperty(
        name="Calculated Mass", description="Mass calculated from density and volume", default=0.0, min=0.0
    )

    physx_centerofmass: FloatVectorProperty(
        name="Center of Mass", description="Calculated center of mass", size=3, default=(0.0, 0.0, 0.0)
    )

    selected_items: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    selected_items_display: bpy.props.StringProperty(default="")

    def clear_attributes(self, context, key):
        self.combined_attrs = ""
        mat = context.material
        if mat:
            mat[key] = "none"

    def update_material_property(self, context, key, value):
        mat = context.material
        if mat:
            mat[key] = value


class SimReadyProperties(bpy.types.PropertyGroup):
    # Existing properties
    base: StringProperty(name="Base Material", default="")

    coating: StringProperty(name="Coating", default="")

    attributes: StringProperty(name="Attributes", default="")

    selected_items_display: StringProperty(name="Selected Items", default="")


class OT_simready_AddEnumToList(Operator):
    bl_idname = "simready.add_enum_to_list"
    bl_label = "Add Nonvisual Attributes"
    bl_description = "Add the selected attribute to the list. Requires Base and Coating to be set first."

    def execute(self, context):
        props = context.material.simready_props

        # ENFORCEMENT: Check if Base and Coating are set before allowing attributes to be added
        # Allow "none", "None", "NONE" as valid string values, but prevent None (null), empty string, etc.
        if props.base is None or props.base == "" or props.coating is None or props.coating == "":
            self.report({"WARNING"}, "Please set Base and Coating materials first before adding attributes")
            return {"CANCELLED"}

        new_item = props.attributes

        # Also check that the attribute itself is not null/empty
        if new_item is None or new_item == "":
            self.report({"WARNING"}, "Please select a valid attribute to add")
            return {"CANCELLED"}

        idx = None
        current_names = [item.name for item in props.selected_items]

        if "none" in current_names:
            idx = current_names.index("none")
            props.selected_items.remove(idx)

        if new_item == "none":
            props.selected_items.clear()

        # Check for duplicates before appending
        if new_item not in [item.name for item in props.selected_items]:
            if idx:
                props.selected_items.remove(idx)
            item = props.selected_items.add()
            item.name = new_item
            props.selected_items_display = ", ".join(item.name for item in props.selected_items)
            props.update_material_property(
                bpy.context, "omni:simready:nonvisual:attributes", props.selected_items_display
            )

            # Also ensure Base and Coating are applied to the material
            props.update_material_property(bpy.context, "omni:simready:nonvisual:base", props.base)
            props.update_material_property(bpy.context, "omni:simready:nonvisual:coating", props.coating)

            self.report({"INFO"}, f"Added '{new_item}' attribute. All SimReady properties set!")
        else:
            self.report({"INFO"}, f"Attribute '{new_item}' already in list")

        return {"FINISHED"}


class OT_simready_ClearList(Operator):
    bl_idname = "simready.clear_enum_list"
    bl_label = "Clear List"

    def execute(self, context):
        props = context.material.simready_props
        props.selected_items.clear()
        none_item = props.selected_items.add()
        none_item.name = "none"
        props.selected_items_display = "none"
        props.clear_attributes(bpy.context, "omni:simready:nonvisual:attributes")
        return {"FINISHED"}


class OT_simready_AutoPop_Base(Operator):
    bl_idname = "simready.autopop_base"
    bl_label = "Try Autopopulate Base"
    bl_description = "Will try and match surfaces based on <name>__<THIS>__<name>. 'none' is default."

    def execute(self, context):
        mat = context.material
        mat_name = mat.name
        normalized_name = mat_name.lower()
        sim_props = mat.simready_props

        try:  # Standard material conventions (usually props)
            mat_split = normalized_name.split("__")

            # failed to split because name is using "_"
            if len(mat_split) > 1:
                base = mat_split[1]

                match_base = fuzzy_find_material_token(base, NONVISUAL_BASE_TOKENS, synonyms=SYNONYM_MAP)
                print(f"{base!r} → {match_base}")

                sim_props.base = match_base

        except (AttributeError, TypeError, IndexError):
            # Vehicle material conventions need to be hardcoded cause there is no discernable convention for them
            print("could not find standard material naming convention")

        return {"FINISHED"}


class OT_simready_AutoPop_Coating(Operator):
    bl_idname = "simready.autopop_coating"
    bl_label = "Try Autopopulate Coating"

    def execute(self, context):
        mat = context.material
        mat_name = mat.name
        normalized_name = mat_name.lower()
        sim_props = mat.simready_props

        try:  # Standard material conventions (usually props)
            mat_split = normalized_name.split("__")

            # failed to split because name is using "_"
            if len(mat_split) > 1:
                coating = mat_split[1]
                if SYNONYM_MAP_COATING.get(coating):
                    match_coating = fuzzy_find_material_token(
                        coating, NONVISUAL_COATING_TOKENS, synonyms=SYNONYM_MAP_COATING
                    )
                    print(f"{coating!r} → {match_coating}")
                else:
                    # go down secondary path ...
                    coating = mat_split[0]
                    match_coating = fuzzy_find_material_token(
                        coating, NONVISUAL_COATING_TOKENS, synonyms=SYNONYM_MAP_COATING
                    )
                    print(f"{coating!r} → {match_coating}")

                sim_props.coating = match_coating

        except (AttributeError, TypeError, IndexError) as e:
            # Vehicle material conventions need to be hardcoded cause there is no discernable convention for them
            print(e)
            print("could not find standard material naming convention")

        return {"FINISHED"}


class WD_OT_refresh_results(Operator):
    bl_idname = "wd.refresh_results"
    bl_label = "Refresh Wikidata Results"

    # Class variable to store the last query
    _last_query = ""

    def execute(self, context):
        # Check if we're in ID mode
        use_id_mode = getattr(context.scene.global_metadata, "wikidata_use_id", False)

        # Get the appropriate query field based on mode
        if use_id_mode:
            query = getattr(context.scene.global_metadata, "wikidata_query_id", "")
            query_type = "Wikidata ID"
        else:
            query = getattr(context.scene, "wikidata_query", "")
            query_type = "search term"

        if not query or query.strip() == "":
            self.report({"WARNING"}, f"Please enter a {query_type} before refreshing")
            return {"CANCELLED"}

        # Create a key that includes the mode to track changes properly
        query_key = f"ID:{query.strip()}" if use_id_mode else query.strip()

        # Check if query is the same as last time
        if query_key == WD_OT_refresh_results._last_query:
            self.report({"INFO"}, "Query unchanged - results already current")
            return {"CANCELLED"}

        # Rebuild the enum list
        enum_items = update_enum_items(None, context)
        # Set the first item as selected, but only if it's valid
        if enum_items and len(enum_items) > 0:
            # valid enum items only please...
            first_item_id = enum_items[0][0]
            try:
                context.scene.wikidata_results = first_item_id
            except TypeError:
                # Fallback to safe default if there's still an issue
                context.scene.wikidata_results = "NONE"

        # Store the current query key as last query
        WD_OT_refresh_results._last_query = query_key
        return {"FINISHED"}


class METADATA_OT_store_for_root(Operator):
    bl_idname = "metadata.store_for_root"
    bl_label = "Store for Root Level metadata"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected_id = context.scene.wikidata_results

        # Get the global metadata properties
        global_metadata = context.scene.global_metadata

        # Store the selected result data globally
        if selected_id and selected_id != "NONE":
            global_metadata.wikidata_result_id = selected_id

            # Get the full result data from the current enum items
            # We need to find the matching item to get label and description
            from ..library.simready_utils import _current_enum_items

            label = None
            for item_id, display_text, description in _current_enum_items:
                if item_id == selected_id:
                    # Extract label from display text (format: "label — description")
                    if " — " in display_text:
                        label = display_text.split(" — ")[0]
                    else:
                        label = display_text

                    global_metadata.wikidata_result_label = label
                    global_metadata.wikidata_result_description = description
                    break
            else:
                # Fallback if we can't find the item
                label = "Unknown"
                global_metadata.wikidata_result_label = label
                global_metadata.wikidata_result_description = ""

            # Store the label as the query (this is the actual entity name from Wikidata)
            global_metadata.wikidata_query = label

            self.report({"INFO"}, f"Stored global metadata: Label='{label}', ID='{selected_id}'")
        else:
            # Clear the result data if no valid selection
            global_metadata.wikidata_query = ""
            global_metadata.wikidata_result_id = ""
            global_metadata.wikidata_result_label = ""
            global_metadata.wikidata_result_description = ""
            self.report({"WARNING"}, "No valid Wikidata ID selected")

        return {"FINISHED"}


class WD_OT_apply_to_object(Operator):
    bl_idname = "wd.apply_to_object"
    bl_label = "Apply Wikidata ID to Object and Mesh"

    def execute(self, context):
        obj = context.active_object
        selected_id = context.scene.wikidata_results
        user_label = context.scene.wikidata_query
        user_id = context.scene.global_metadata.wikidata_query_id

        if not obj:
            self.report({"WARNING"}, "No active object selected")
            return {"CANCELLED"}

        if not selected_id or selected_id == "NONE":
            self.report({"WARNING"}, "No valid Wikidata ID selected")
            return {"CANCELLED"}

        # Get the actual label from the Wikidata API response
        from ..library.simready_utils import _current_enum_items

        label = None
        for item_id, display_text, description in _current_enum_items:
            if item_id == selected_id:
                # Extract label from display text (format: "label — description")
                if " — " in display_text:
                    label = display_text.split(" — ")[0]
                else:
                    label = display_text
                break

        # Fallback to ID if we couldn't find the label
        if not label:
            label = user_label
            if not user_label:
                label = user_id
            self.report({"WARNING"}, f"Could not retrieve label for {selected_id}, using ID as label")

        # Delete all existing Wikidata properties from object
        for key in list(obj.keys()):
            if key.startswith("semantics:labels:wikidata"):
                del obj[key]

        # Delete all existing Wikidata properties from mesh (if it's a mesh object)
        if obj.type == "MESH":
            mesh = obj.data
            for key in list(mesh.keys()):
                if key.startswith("semantics:labels:wikidata"):
                    del mesh[key]

        # Apply to object
        obj["semantic:wikidata_class:params:semanticData"] = label
        obj["semantic:wikidata_qcode:params:semanticData"] = selected_id

        # Apply to mesh if it's a mesh object
        if obj.type == "MESH":
            mesh = obj.data
            mesh["semantic:wikidata_class:params:semanticData"] = label
            mesh["semantic:wikidata_qcode:params:semanticData"] = selected_id
            self.report(
                {"INFO"},
                f"Assigned QCode {selected_id} and label '{label}' to object {obj.name} and mesh {mesh.name}",
            )
        else:
            self.report({"INFO"}, f"Assigned QCode {selected_id} and label '{label}' to object {obj.name}")

        return {"FINISHED"}


class WD_OT_remove_from_object(Operator):
    bl_idname = "wd.remove_from_object"
    bl_label = "Remove Wikidata Properties from Object and Mesh"

    def execute(self, context):
        obj = context.active_object

        if not obj:
            self.report({"WARNING"}, "No active object selected")
            return {"CANCELLED"}

        # Remove all Wikidata properties from object
        obj_removed_count = 0
        for key in list(obj.keys()):
            if key.startswith("semantics:labels:wikidata"):
                del obj[key]
                obj_removed_count += 1

        # Remove all Wikidata properties from mesh (if it's a mesh object)
        mesh_removed_count = 0
        if obj.type == "MESH":
            mesh = obj.data
            for key in list(mesh.keys()):
                if key.startswith("semantics:labels:wikidata"):
                    del mesh[key]
                    mesh_removed_count += 1

        total_removed = obj_removed_count + mesh_removed_count
        if total_removed > 0:
            self.report(
                {"INFO"},
                f"Removed {total_removed} Wikidata properties from {obj.name} (object: {obj_removed_count}, mesh: {mesh_removed_count})",
            )
        else:
            self.report({"INFO"}, f"No Wikidata properties found on {obj.name}")

        return {"FINISHED"}


class OT_GenerateCaption(Operator):
    bl_idname = "simready.generate_caption"
    bl_label = "Generate Caption"
    bl_description = "Generate an image caption using BLIP and apply it to the active object"

    def execute(self, context):
        load_blip_model()

        # Save current render
        output_path = bpy.path.abspath("//temp_render.jpg")

        if os.path.exists(output_path):
            os.remove(output_path)

        bpy.ops.render.render(write_still=True)
        bpy.data.images["Render Result"].save_render(filepath=output_path)

        try:
            caption = generate_caption(output_path)
            active_obj = context.object
            if active_obj:
                active_obj["omni:simready:documentation"] = caption
                print(f"Set caption on active object: {active_obj.name}")
            else:
                self.report({"ERROR"}, "No active object selected.")
                return {"CANCELLED"}
            context.scene.blip_caption = caption
        except Exception as e:
            self.report({"ERROR"}, f"Failed to generate caption: {e}")
            return {"CANCELLED"}

        return {"FINISHED"}


class SIMREADY_OT_update_physx_properties(Operator):
    """Update PhysX Properties Operator

    This operator is kept for backward compatibility and manual invocation from UI.
    The property update callback now calls update_physx_properties_callback() directly
    to avoid context issues.
    """

    bl_idname = "simready.update_physx_properties"
    bl_label = "Update PhysX Properties"
    bl_description = "Update PhysX material properties based on selected material type"

    def execute(self, context):
        # Try to get material from context first, then from active object
        mat = None
        try:
            mat = context.material
        except (AttributeError, ReferenceError):
            # context.material not available, try to get from active object
            if context.active_object and context.active_object.active_material:
                mat = context.active_object.active_material
            else:
                # No material available in any context
                self.report({"WARNING"}, "No material available to update")
                return {"CANCELLED"}

        if mat is None:
            self.report({"WARNING"}, "No material selected")
            return {"CANCELLED"}

        sim_props = mat.simready_props
        material_type = sim_props.physx_material_type

        if material_type == "none":
            return {"CANCELLED"}

        # # Get the path to the physics_materials.json file
        addon_path = os.path.dirname(os.path.dirname(__file__))
        json_path = os.path.join(addon_path, "resource", "physics_materials.json")

        try:
            with open(json_path, "r") as f:
                physics_materials = json.load(f)

            if material_type in physics_materials:
                material = physics_materials[material_type]

                # Update the properties
                for prop_name, value in material.items():
                    prop_id = f"physx_{prop_name.replace('physics:', '')}"
                    if hasattr(sim_props, prop_id):
                        setattr(sim_props, prop_id, value)

        except Exception as e:
            self.report({"ERROR"}, f"Error updating PhysX properties: {str(e)}")
            return {"CANCELLED"}

        return {"FINISHED"}


def calcuate_voxelized_volume(obj, voxel_size=0.01):
    """
    Duplicates the selected object, voxelizes it, and calculates the volume of the voxelized object.
    Deletes the voxelized object after calculation.
    """
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.object.duplicate()

    voxel_obj = bpy.context.active_object
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=True)
    remesh_mod = voxel_obj.modifiers.new(name="VoxelRemesh", type="REMESH")
    remesh_mod.mode = "VOXEL"
    remesh_mod.voxel_size = voxel_size
    remesh_mod.use_remove_disconnected = False
    bpy.context.view_layer.objects.active = voxel_obj
    bpy.ops.object.modifier_apply(modifier=remesh_mod.name)

    mesh = voxel_obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    def signed_volume(v1, v2, v3):
        return (v1.dot(v2.cross(v3))) / 6.0

    volume = 0.0
    for face in bm.faces:
        verts = face.verts
        if len(verts) == 3:
            v1, v2, v3 = [v.co for v in verts]
            volume += signed_volume(v1, v2, v3)
        elif len(verts) == 4:
            v1, v2, v3, v4 = [v.co for v in verts]
            volume += signed_volume(v1, v2, v3) + signed_volume(v1, v3, v4)

    bm.free()

    bpy.ops.object.delete()

    return volume


def convex_hull_volume(obj):
    # TODO: i'm not actually doing convex hull here, it's just using the volume
    obj = bpy.context.active_object
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    print(f"Object scale: {obj.scale}")
    print(f"Scene unit scale: {bpy.context.scene.unit_settings.scale_length}")

    bm = bmesh.new()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()

    bm.from_mesh(mesh)
    volume = bm.calc_volume(signed=False)

    # Apply unit scale correction
    unit_scale = bpy.context.scene.unit_settings.scale_length
    adjusted_volume = volume * (unit_scale**3)

    print(f"Raw BMESH volume: {volume}")
    print(f"Adjusted (scene-scale) volume: {adjusted_volume}")

    bm.free()
    eval_obj.to_mesh_clear()
    return adjusted_volume


def estimate_material_mass(obj) -> Dict[str, float]:
    mat_areas = {}
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    for face in bm.faces:
        mat_index = face.material_index
        area = face.calc_area()
        # print(f"Face area: {area}")
        mat_areas[mat_index] = mat_areas.get(mat_index, 0) + area

    bm.free()
    mat_masses = {}
    physics_lib = get_physx_material_types_overload()

    for idx, area in mat_areas.items():
        print(f"Processing material index {idx}, total area: {area}")
        if idx < len(obj.material_slots) and obj.material_slots[idx].material:
            mat = obj.material_slots[idx].material
            name = mat.get("pxr:usd:physics_type")
            print(f"Material physics type: {name}")

            # get name from physics library
            mat_type = physics_lib.get(name, None)
            if mat_type:
                thickness = mat_type.get("thickness", 0.00)
                density = mat_type.get("density", 0.00)
                fill = mat_type.get("fillRatio", 0.00)
                volume = area * thickness * fill
                mass = volume * density

                # Accumulate mass for materials of the same type
                if name in mat_masses:
                    mat_masses[name] += mass
                else:
                    mat_masses[name] = mass

                print(f"  Thickness: {thickness}, Density: {density}, Fill: {fill}")
                print(f"  Volume: {volume}, Mass: {mass}")
            else:
                print(f"  Warning: No physics data found for material type '{name}'")
        else:
            print(f"  Warning: Material slot {idx} is empty or doesn't exist")

    return mat_masses


# TODO: start calculating mass here, and adding it back to the object custom properties.
# class SIMREADY_OT_assign_usd_physics_mass(Operator):
#     bl_idname = "simready.assign_usd_physics_mass"
#     bl_label = "Assign USD Physics Mass"
#     bl_description = "Assign USD Physics Mass to object custom properties"

#     def execute(self, context):
#         mat = context.material
#         obj = context.object

#         if not mat:
#             return {'CANCELLED'}

#         if not obj:
#             return {'CANCELLED'}

#         sim_props = mat.simready_props
#         material_type = sim_props.physx_material_type

#         if material_type == "none":
#             return {'CANCELLED'}


def tetrahedron_volume(v0, v1, v2, v3):
    return np.abs(np.dot(v1 - v0, np.cross(v2 - v0, v3 - v0))) / 6.0


def tetrahedron_com(v0, v1, v2, v3):
    return (v0 + v1 + v2 + v3) / 4.0


def calculate_diagonal_inertia_tensor(obj, material_masses, center_of_mass):
    """
    Calculate diagonal inertia tensor using existing material mass calculations.

    Args:
        obj: Blender mesh object
        material_masses: Dictionary of material names to masses from estimate_material_mass()
        center_of_mass: Vector3 of the object's center of mass

    Returns:
        numpy array: 3x3 diagonal inertia tensor
    """
    import bmesh
    import numpy as np

    # Initialize inertia tensor
    Ixx = Iyy = Izz = 0.0

    try:
        # Get mesh data
        mesh = obj.data
        if not mesh or len(mesh.vertices) == 0:
            print("Warning: Empty mesh, returning zero inertia tensor")
            return np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])

        # Create bmesh safely
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()

        # Get transformation matrix for coordinate transformation
        # Use object's local matrix, accounting for parent influence if needed
        if obj.parent:
            # If object has a parent, use the parent-relative matrix
            transform_matrix = obj.matrix_parent_inverse
        else:
            # If no parent, use identity matrix (no transformation needed)
            transform_matrix = mathutils.Matrix.Identity(4)

        # Pre-calculate material areas to avoid repeated calculations
        material_areas = {}
        for face in bm.faces:
            mat_index = face.material_index
            if mat_index not in material_areas:
                material_areas[mat_index] = 0.0
            material_areas[mat_index] += face.calc_area()

        # Process each face and its material
        for face in bm.faces:
            mat_index = face.material_index

            # Skip faces with invalid material indices
            if mat_index < 0 or mat_index >= len(obj.material_slots):
                continue

            # Get material name for this face
            if obj.material_slots[mat_index].material:
                mat = obj.material_slots[mat_index].material
                material_name = mat.get("pxr:usd:physics_type")

                if material_name and material_name in material_masses:
                    # Calculate face area and get material mass
                    face_area = face.calc_area()
                    if face_area <= 0:
                        continue

                    total_material_mass = material_masses[material_name]
                    total_material_area = material_areas.get(mat_index, 0.0)

                    if total_material_area > 0:
                        mass_per_area = total_material_mass / total_material_area
                        face_mass = face_area * mass_per_area

                        # Calculate face center in object space coordinates
                        face_center = mathutils.Vector((0.0, 0.0, 0.0))
                        vert_count = 0
                        for vert in face.verts:
                            if vert.co is not None:
                                # Transform vertex to object space, accounting for parent if needed
                                face_center += transform_matrix @ vert.co
                                vert_count += 1

                        if vert_count > 0:
                            face_center /= vert_count

                            # Calculate distance from face center to center of mass
                            r = face_center - center_of_mass
                            x, y, z = r.x, r.y, r.z

                            # Add contribution to diagonal inertia tensor elements
                            # Using point mass approximation for each face
                            Ixx += face_mass * (y * y + z * z)
                            Iyy += face_mass * (x * x + z * z)
                            Izz += face_mass * (x * x + y * y)

    except Exception as e:
        print(f"Error calculating inertia tensor: {str(e)}")
        # Return zero tensor on error
        Ixx = Iyy = Izz = 0.0

    finally:
        # Always free bmesh
        if "bm" in locals():
            bm.free()

    # Create diagonal inertia tensor
    inertia_tensor = np.array([[Ixx, 0.0, 0.0], [0.0, Iyy, 0.0], [0.0, 0.0, Izz]])

    return inertia_tensor


class SIMREADY_OT_assign_physx_properties(Operator):
    bl_idname = "simready.assign_physx_properties"
    bl_label = "Assign PhysX Properties"
    bl_description = "Assign PhysX properties to materials on the selected objects"

    """
    Multiple objects can be selected, and the operator will run through and calculate
    on everything selected.
    """

    def execute(self, context):
        # Get all selected objects
        selected_objects = [obj for obj in context.selected_objects if obj.type == "MESH"]

        if not selected_objects:
            self.report({"ERROR"}, "Please select at least one mesh object")
            return {"CANCELLED"}

        # Get the path to the physics_materials.json file
        addon_path = os.path.dirname(os.path.dirname(__file__))
        json_path = os.path.join(addon_path, "resource", "physics_materials.json")

        try:
            with open(json_path, "r") as f:
                physics_materials = json.load(f)

            processed_count = 0

            # Process each selected object
            for obj in selected_objects:
                print(f"Processing object: {obj.name}")

                # Process each material slot on the object
                for slot in obj.material_slots:
                    if not slot.material:
                        continue

                    mat = slot.material
                    sim_props = mat.simready_props
                    material_type = sim_props.physx_material_type

                    if material_type == "none":
                        continue

                    if material_type in physics_materials:
                        # fill ratio is guestimating the approximate air to <material> ratio
                        # a typical oak chair has a 15% fill ratio
                        fill_ratio = 0.15  # noqa F841
                        material = physics_materials[material_type]

                        # Assign the material type
                        mat["pxr:usd:physics_type"] = material_type

                        # Assign all other properties
                        for prop_name, value in material.items():
                            clean_name = prop_name.replace("physics:", "")
                            mat[f"pxr:usd:physics_{clean_name}"] = value

                        # Calculate material masses for this object
                        material_masses = estimate_material_mass(obj)

                        print(f"Material masses for {obj.name}: {material_masses}")

                        total_mass = 0.0
                        for _material_name, mass in material_masses.items():
                            total_mass += mass

                        # Calculate volume using convex hull
                        # volume = convex_hull_volume(obj)

                        # Calculate center of mass for this object using vertices in object space
                        obj_com = mathutils.Vector((0.0, 0.0, 0.0))
                        mesh = obj.data

                        # Calculate COM in object's local space (before any transformations)
                        for vertex in mesh.vertices:
                            obj_com += vertex.co
                        obj_com /= len(mesh.vertices)

                        # If object has a parent, we need to account for the parent's influence
                        # on the object's local coordinate system
                        if obj.parent:
                            # Get the object's matrix relative to its parent
                            parent_relative_matrix = obj.matrix_parent_inverse
                            # Transform the COM to account for parent's influence on object space
                            obj_com = parent_relative_matrix @ obj_com

                        # Get density from material properties (in kg/m³)
                        # density = sim_props.physx_density

                        # Calculate mass (volume is already in m³)
                        # mass = density * volume * fill_ratio

                        # Update material properties for display
                        sim_props.physx_mass = total_mass
                        sim_props.physx_centerofmass = obj_com

                        # Assign mass and center of mass to object properties
                        obj["pxr:usd:physics_mass"] = total_mass
                        obj["pxr:usd:physics_centerofmass"] = obj_com

                        # Calculate and assign diagonal inertia tensor of thin shells
                        # TODO: double check isaacsim methods for doing this.
                        try:
                            inertia_tensor = calculate_diagonal_inertia_tensor(obj, material_masses, obj_com)
                            if inertia_tensor is not None:
                                # Extract diagonal elements as float3 for USD/Kit compatibility
                                # Ensure all values are non-negative (inertia tensor values should always be positive)
                                diagonal_inertia = [
                                    max(0.0, inertia_tensor[0, 0]),
                                    max(0.0, inertia_tensor[1, 1]),
                                    max(0.0, inertia_tensor[2, 2]),
                                ]
                                obj["pxr:usd:physics_inertia"] = diagonal_inertia

                                print(f"Inertia Tensor (diagonal) for {obj.name}:")
                                print(f"  Ixx: {diagonal_inertia[0]:.6f}")
                                print(f"  Iyy: {diagonal_inertia[1]:.6f}")
                                print(f"  Izz: {diagonal_inertia[2]:.6f}")
                            else:
                                print(f"Warning: Inertia tensor calculation returned None for {obj.name}")
                        except Exception as e:
                            print(f"Error calculating inertia tensor for {obj.name}: {str(e)}")
                            # Continue without inertia tensor rather than failing completely

                # Calculate and assign principal axis as quaternion
                # Principal axis represents the orientation of the object
                try:
                    # Get object's rotation as quaternion (w, x, y, z)
                    rotation_quat = obj.rotation_euler.to_quaternion()
                    # Store as list for USD/Kit compatibility: (w, x, y, z)
                    principal_axes = [rotation_quat.w, rotation_quat.x, rotation_quat.y, rotation_quat.z]
                    obj["pxr:physics:principalAxes"] = principal_axes

                    print(f"Principal Axes (quaternion) for {obj.name}:")
                    print(
                        f"  w: {rotation_quat.w:.6f}, x: {rotation_quat.x:.6f}, y: {rotation_quat.y:.6f}, z: {rotation_quat.z:.6f}"
                    )
                except Exception as e:
                    print(f"Error calculating principal axis for {obj.name}: {str(e)}")
                    # don't raise, kit can autocompute the principal axis

                processed_count += 1

            self.report({"INFO"}, f"Processed {processed_count} object(s)")

        except Exception as e:
            print(f"Error assigning PhysX properties: {str(e)}")
            return {"CANCELLED"}

        return {"FINISHED"}


class GLOBAL_OT_ManualCaption(Operator):
    bl_idname = "global.manual_caption"
    bl_label = "Apply Manual Global Caption"
    bl_description = "Apply a manually entered caption globally"

    def execute(self, context):
        global_metadata = context.scene.global_metadata

        print(f"Applying manual global caption: {global_metadata.global_caption_manual_text}")
        print(f"Global caption: {global_metadata.global_caption}")

        if global_metadata.global_caption_manual_text:
            global_metadata.global_caption = global_metadata.global_caption_manual_text
        return {"FINISHED"}


class GLOBAL_OT_GenerateCaption(Operator):
    bl_idname = "global.generate_caption"
    bl_label = "Generate Global Caption"
    bl_description = "Generate a dense caption for the entire scene and store it globally"

    def execute(self, context):
        try:
            from ..library.simready_utils import (
                generate_caption_for_scene,
                load_blip_model,
            )

            # Load the BLIP model if not already loaded
            load_blip_model()

            # Generate caption for the entire scene
            caption = generate_caption_for_scene()

            if caption:
                # Store the caption globally
                global_metadata = context.scene.global_metadata
                global_metadata.global_caption = caption
                global_metadata.global_caption_generation_failed = False

                self.report({"INFO"}, f"Generated global caption: {caption[:50]}...")
                return {"FINISHED"}
            else:
                # Mark as failed
                global_metadata = context.scene.global_metadata
                global_metadata.global_caption_generation_failed = True

                self.report({"WARNING"}, "Failed to generate global caption")
                return {"CANCELLED"}

        except Exception as e:
            print(f"Error generating global caption: {str(e)}")
            global_metadata = context.scene.global_metadata
            global_metadata.global_caption_generation_failed = True

            self.report({"ERROR"}, f"Error generating global caption: {str(e)}")
            return {"CANCELLED"}


class GLOBAL_OT_GenerateCaption_Manual(Operator):
    bl_idname = "global.generate_caption_manual"
    bl_label = "Apply Manual Global Caption"
    bl_description = "Apply a manually entered caption globally"

    def execute(self, context):
        global_metadata = context.scene.global_metadata

        if global_metadata.global_caption:
            # Clear the failed flag since we're applying a manual caption
            global_metadata.global_caption_generation_failed = False

            self.report({"INFO"}, f"Applied manual global caption: {global_metadata.global_caption[:50]}...")
            return {"FINISHED"}
        else:
            self.report({"WARNING"}, "No global caption to apply")
            return {"CANCELLED"}
