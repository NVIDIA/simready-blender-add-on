# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import difflib
import os
import shutil
from typing import Dict, List, Optional

import bpy
from pxr import Gf, Sdf, UsdShade

# from CORE_ArtistTools.addon.property.settings import CORE_Settings

CURRENT_DIR = os.path.dirname(__file__)
FALLBACK_TEX = os.path.join(CURRENT_DIR, "resources", "missing_texture.jpg")

# Material type constants
MAT_TYPE_SIMPBR = "SimPBR"
MAT_TYPE_SIMPBR_TRANSLUCENT = "SimPBR_Translucent"
MAT_TYPE_OMNIPBR = "OmniPBR Compute"
MAT_TYPE_OMNIGLASS = "OmniGlass Compute"
MAT_TYPE_PRINCIPLED_BSDF = "Principled BSDF"
MAT_TYPE_NON_NODE = "Non-Node Material"

# Valid material group node names
VALID_MATERIAL_GROUPS = [MAT_TYPE_OMNIPBR, MAT_TYPE_OMNIGLASS, MAT_TYPE_SIMPBR, MAT_TYPE_SIMPBR_TRANSLUCENT]

# Material Attribute Name Constants - SimPBR / Blender Node Inputs
# These are used across multiple mapping dictionaries to avoid magic strings
ATTR_ALBEDO_MAP = "Albedo Map"
ATTR_ALBEDO_TINT = "Albedo Tint"
ATTR_SPECULAR_AMOUNT = "Specular Amount"
ATTR_ORM_MAP = "ORM Map"
ATTR_AO_MAP = "Ambient Occlusion Map"
ATTR_AO_TO_DIFFUSE = "AO to Diffuse"
ATTR_METALLIC_AMOUNT = "Metallic Amount"
ATTR_METALLIC_MAP = "Metallic Map"
ATTR_METALLIC_MAP_INFLUENCE = "Metallic Map Influence"
ATTR_ROUGHNESS_AMOUNT = "Roughness Amount"
ATTR_ROUGHNESS_MAP = "Roughness Map"
ATTR_ROUGHNESS_MAP_INFLUENCE = "Roughness Map Influence"
ATTR_EMISSIVE_INTENSITY = "Emissive Intensity"
ATTR_EMISSIVE_COLOR = "Emissive Color"
ATTR_EMISSIVE_MASK_MAP = "Emissive Mask Map"
ATTR_NORMAL_MAP = "Normal Map"
ATTR_NORMAL_MAP_STRENGTH = "Normal Map Strength"
ATTR_OPACITY_MAP = "Opacity Map"
ATTR_OPACITY_RATIO = "Opacity Ratio"
ATTR_ALPHA_CUTOUT_CUTOFF = "Alpha Cutout Cutoff"
ATTR_ENABLE_ORM_TEXTURE = "Enable ORM Texture"
ATTR_ENABLE_OPACITY = "Enable Opacity"
ATTR_ENABLE_EMISSION = "Enable Emission"
ATTR_ENABLE_THIN_WALLED = "Enable Thin Walled"
ATTR_ENABLE_DIFFUSE_TRANSMISSION = "Enable Diffuse Transmission"
ATTR_ENABLE_CLEARCOAT_LAYER = "Enable Clearcoat Layer"
ATTR_ENABLE_RETRO_REFLECTION = "Enable Retro-reflection"
ATTR_ENABLE_ALPHA_CUTOUT = "Enable Alpha Cutout"
ATTR_DIFFUSE_TRANSMISSION_MULTIPLIER = "Diffuse Transmission Multiplier"
ATTR_DIFFUSE_TRANSMISSION_TINT = "Diffuse transmission tint"
ATTR_ANISOTROPY_AMOUNT = "Anisotropy Amount"
ATTR_ANISOTROPY_MAP = "Anisotropy Map"
ATTR_ANISOTROPY_MAP_INFLUENCE = "Anisotropy Map Influence"
ATTR_SPECULAR_MAP = "Specular Map"
ATTR_CLEARCOAT_TRANSPARENCY = "Clearcoat Transparency"
ATTR_CLEARCOAT_ROUGHNESS = "Clearcoat Roughness"
ATTR_CLEARCOAT_WEIGHT = "Clearcoat Weight"
ATTR_CLEARCOAT_FLATTEN = "Clearcoat Flatten"
ATTR_CLEARCOAT_IOR = "Clearcoat IOR"
ATTR_CLEARCOAT_TINT = "Clearcoat Tint"
ATTR_CLEARCOAT_NORMAL_MAP = "Clearcoat Normal Map"
ATTR_CLEARCOAT_NORMAL_MAP_STRENGTH = "Clearcoat Normal Map Strength"
ATTR_RETRO_REFLECTION_WEIGHT_FACING = "Retro-reflection weight facing"
ATTR_RETRO_REFLECTION_WEIGHT_EDGE = "Retro-reflection weight edge"
ATTR_RETRO_REFLECTION_TINT = "Retro-reflection tint"
ATTR_TRANSMITTANCE_COLOR = "Transmittance Color"
ATTR_TRANSMITTANCE_MEASUREMENT_DISTANCE = "Transmittance Measurement Distance"
ATTR_INDEX_OF_REFRACTION = "Index of Refraction"


def determine_asset_type(filepath) -> str:
    filepath_lower = filepath.lower()
    if "props" in filepath_lower:
        return "prop"
    elif "vehicles" in filepath_lower:
        return "vehicle"
    else:
        return "none"


def resolve_blender_path(relative_path):
    """
    Convert Blender's relative path to an absolute path.
    Handles Blender's relative path notation (//) properly.
    """
    if not relative_path:
        return None

    # Handle Blender's relative path notation
    if relative_path.startswith("//"):
        # Get the .blend file location
        blend_file_path = bpy.data.filepath
        if not blend_file_path:
            raise ValueError("Cannot resolve relative path: Blender file has not been saved")

        # Get the directory of the .blend file
        blend_dir = os.path.dirname(os.path.abspath(blend_file_path))

        # Remove the // prefix and resolve relative to .blend file location
        rel_path = relative_path[2:]  # Remove //
        abs_path = os.path.join(blend_dir, rel_path)
        return os.path.abspath(os.path.normpath(abs_path))
    else:
        # Already absolute or regular relative path
        return os.path.abspath(os.path.normpath(relative_path))


def get_blender_file_path():
    """
    Get the absolute path to the currently open Blender file.
    Returns None if the file hasn't been saved yet.
    """
    filepath = bpy.data.filepath
    if not filepath:
        print("The Blender file has not been saved yet.")
        return None
    return os.path.abspath(filepath)


# --------------------------------
# Blender Utils
# --------------------------------


def get_all_used_mats() -> Dict[str, str]:
    """
    Step 1.
    Get all materials used in scenes. Return a dictionary of type of material.
    Types: SimPBR, SimPBR_Translucent, Principled_BSDF, OmniPBR Compute, OmniGlass Compute

    """

    def classify_material(mat) -> str:
        """Classify a material based on its node setup."""
        if not mat.use_nodes:
            return MAT_TYPE_NON_NODE

        # NEED to break to prevent false positives
        # OmniPBR and OmniPBR glass have principled node in graph
        for node in mat.node_tree.nodes:
            if node.type == "GROUP" and node.name in VALID_MATERIAL_GROUPS:
                print("\n")
                print("--------------------")
                print(f"MATNAME: {mat.name}")
                print(f"Found GROUP node: {node.name}")
                print("--------------------")
                return node.name

            if node.type != "GROUP":
                # Found a non-group node, assume Principled BSDF workflow
                print("\n")
                print("--------------------")
                print(f"MATNAME: {mat.name}")
                print(f"Found non-group node, using: {MAT_TYPE_PRINCIPLED_BSDF}")
                print("--------------------")
                return MAT_TYPE_PRINCIPLED_BSDF

        return f"Error: {mat.name} is an unknown type of material: Need at least a principled BSDF!"

    used_materials = {}

    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue

        mesh = obj.data

        # Check all materials linked to mesh or object
        for mat in obj.material_slots:
            material = mat.material
            if material and material.name not in used_materials:
                used_materials[material.name] = classify_material(material)

        # Extra: per-face material assignment check
        if hasattr(mesh, "materials"):
            for material in mesh.materials:
                if material and material.name not in used_materials:
                    used_materials[material.name] = classify_material(material)

    return used_materials


def find_principled_node(node_tree):
    """
    Recursively find the Principled BSDF node in node groups
    """
    for node in node_tree.nodes:
        # BLENDER 3.6 and 4.2 have different names for the Principled BSDF node
        if node.type == "BSDF_PRINCIPLED" or node.name == MAT_TYPE_PRINCIPLED_BSDF:
            return node
        elif node.type == "GROUP" and node.node_tree:
            result = find_principled_node(node.node_tree)
            if result:
                return result
    return None


def get_principled_bsdf_attributes(material_name):
    """
    Captures all attributes of a Principled BSDF node in the specified material.
    Returns a dictionary of parameters and their values.
    """
    material = bpy.data.materials.get(material_name)

    if not material or not material.node_tree:
        return None

    # Find the Principled BSDF node
    principled = find_principled_node(material.node_tree)

    if not principled:
        print("FOUND NO PRINCIPLED SHADER")
        return None

    attributes = {}  # noqa F841

    def clean_socket_value(value):
        # Sanitize <bpy_float[3]> or <bpy_float[4]> to tuples
        if hasattr(value, "__iter__") and not isinstance(value, str):
            return tuple(value)
        return value

    def find_texture_node(node):
        """
        Recursively search for a TEX_IMAGE node linked to this node's inputs.
        """
        if node.type == "TEX_IMAGE":
            return node

        for input in node.inputs:
            if input.is_linked:
                from_node = input.links[0].from_node
                result = find_texture_node(from_node)
                if result:
                    return result

        return None

    # Recursively loop through nodes until you found the texture node
    # Unfortunately this might ignore any artistic usage of nodes to recolor
    # TODO: perhaps extract color/alpha using PIL and bake image automagically.
    # we can most likely just determine the type of node and then trigger a bake
    # from there... Nodes like SEPXYZ won't triger a bake, but Color Ramp should.
    inputs_dict = {}
    for socket in principled.inputs:
        texture_info = {}
        if socket.is_linked:

            linked_node = socket.links[0].from_node
            tex_node = find_texture_node(linked_node)
            if tex_node:
                texture_info[socket.name + "_file_path"] = tex_node.image.filepath
                texture_info[socket.name + "_colorspace"] = tex_node.image.colorspace_settings.name

            inputs_dict[socket.name + "_connection"] = {linked_node.name: texture_info}

        else:
            try:
                texture_info[socket.name] = clean_socket_value(socket.default_value)
            except AttributeError:
                texture_info[socket.name] = None

    return inputs_dict


def _find_omnipbr_node(material, glass=False):
    """Find the OmniPBR or OmniGlass Compute node in a material."""
    target_name = "OmniGlass Compute" if glass else "OmniPBR Compute"

    for node in material.node_tree.nodes:
        if node.name == target_name:
            return node
    return None


def _get_input_default_value(input):
    """Extract the default value from an input based on its type."""
    type_handlers = {
        "RGBA": lambda inp: list(inp.default_value),
        "VALUE": lambda inp: inp.default_value,
        "VECTOR": lambda inp: list(inp.default_value),
        "INT": lambda inp: inp.default_value if "use" not in inp.name else None,
    }

    handler = type_handlers.get(input.type)
    return handler(input) if handler else None


def _get_texture_connection_info(input):
    """Extract texture information from a connected input."""
    if not (input.links or input.is_linked):
        return None

    connected_node = input.links[0].from_node
    if connected_node.type != "TEX_IMAGE" or not connected_node.image:
        return None

    texture_info = {
        input.name + "_file_path": connected_node.image.filepath,
        input.name + "_colorspace": connected_node.image.colorspace_settings.name,
    }

    return {input.name + "_connection": {connected_node.name: texture_info}}


def get_omnipbr_attributes(material_name, glass=False) -> dict:
    """
    Get all inputs from an OmniPBR Compute node in the specified material
    """
    # TODO: return absolute paths
    material = bpy.data.materials.get(material_name)
    if not material or not material.use_nodes:
        return None

    omnipbr_node = _find_omnipbr_node(material, glass)
    if not omnipbr_node:
        return None

    inputs_dict = {}

    for input in omnipbr_node.inputs:
        if not input.enabled:
            continue

        # Get default value
        default_value = _get_input_default_value(input)
        if default_value is not None:
            inputs_dict[input.name] = default_value

        # Get texture connection info
        connection_info = _get_texture_connection_info(input)
        if connection_info:
            inputs_dict.update(connection_info)

    return inputs_dict


def get_all_old_attrs(all_used_mats: set) -> list:
    """
    Step 2.
    Returns a list of dicts that houses all the attributes from the old material (before conversion)
    """

    all_PBR_attrs = []
    close_glass_matches = [
        "Glass",
        "Window",
        "Transparent",
        "Translucent",
        "Seethrough",
    ]

    def is_glass_related(mat_name, threshold=0.8):
        mat_name_lower = mat_name.lower()
        for keyword in close_glass_matches:
            keyword_lower = keyword.lower()
            if keyword_lower in mat_name_lower:
                return True
            # Fuzzy fallback
            if difflib.SequenceMatcher(None, keyword_lower, mat_name_lower).ratio() > threshold:
                return True
        return False

    def create_attr_dict(curr_mat_type, conversion_type, mat_name, attributes):
        """Create standardized attribute dictionary structure."""
        return {curr_mat_type: {conversion_type: {mat_name: attributes}}}

    def handle_principled_bsdf(mat_name, curr_mat_type):
        """Handle Principled BSDF material conversion."""
        is_glass = is_glass_related(mat_name, 0.7)
        print(is_glass)

        conversion_type = "to_SimPBR_trans" if is_glass else "to_SimPBR"
        attributes = get_principled_bsdf_attributes(mat_name)
        return create_attr_dict(curr_mat_type, conversion_type, mat_name, attributes)

    def handle_omnipbr(mat_name, curr_mat_type):
        """Handle OmniPBR material conversion."""
        attributes = get_omnipbr_attributes(mat_name)
        return create_attr_dict(curr_mat_type, "to_SimPBR", mat_name, attributes)

    def handle_omniglass(mat_name, curr_mat_type):
        """Handle OmniGlass material conversion."""
        attributes = get_omnipbr_attributes(mat_name, glass=True)
        return create_attr_dict(curr_mat_type, "to_SimPBR_trans", mat_name, attributes)

    # Material type handlers mapping
    material_handlers = {
        MAT_TYPE_PRINCIPLED_BSDF: handle_principled_bsdf,
        MAT_TYPE_OMNIPBR: handle_omnipbr,
        MAT_TYPE_OMNIGLASS: handle_omniglass,
    }

    for mat_name, curr_mat_type in all_used_mats.items():
        handler = material_handlers.get(curr_mat_type)

        if handler:
            attrs = handler(mat_name, curr_mat_type)
            all_PBR_attrs.append(attrs)
        else:
            print(f"ignoring: {mat_name}, is already: {curr_mat_type}, no need to convert")

    return all_PBR_attrs


def append_template_mats() -> List[bpy.types.Material]:
    """
    Step 3.
    Function that will find blender templates and import them into scene.
    Will Import: SimPBR and SimPBR_translucent.
    Return templates if succeeds.
    """
    CURRENT_DIR = os.path.dirname(__file__)
    template_dir = os.path.join(CURRENT_DIR, "resources")

    # Template definitions: (file_name, material_name)
    templates = [
        ("simpbr_translucent_42.blend", "trans__simpbr__template"),
        ("simpbr_42.blend", "opaque__simpbr__template"),
    ]

    def remove_existing_material(material_name):
        """Remove existing material from scene if present."""
        if material_name in bpy.data.materials:
            print(f"Removing existing material '{material_name}'")
            bpy.data.materials.remove(bpy.data.materials[material_name], do_unlink=True)

    def load_template_material(file_path, material_name):
        """Load a template material from a blend file."""
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return None

        bpy.ops.wm.append(
            filepath=f"{file_path}/Material/{material_name}",
            directory=f"{file_path}/Material/",
            filename=material_name,
        )

        material = bpy.data.materials.get(material_name)
        if material:
            print(f"Material '{material_name}' successfully appended.")
            return material
        else:
            print(f"Material '{material_name}' not found in {file_path}.")
            return None

    blender_materials: List[bpy.types.Material] = []

    for blend_file, material_name in templates:
        file_path = os.path.join(template_dir, blend_file)

        remove_existing_material(material_name)
        material = load_template_material(file_path, material_name)

        if material:
            blender_materials.append(material)

    return blender_materials


def replace_with_simpbr(template_materials: List[bpy.types.Material], store_old_attrs: list):
    """
    STEP 4.
    Function to search all materials in graph and replace
    """

    # ---------------
    # MAPPING TABLES: DEFAULTS
    # Ensures Default Values for Template materials
    # ---------------

    node_defaults_simbpr = {
        MAT_TYPE_SIMPBR: {
            0: (0.5, 0.5, 0.5, 1.0),  # Albedo Map
            1: (1.0, 1.0, 1.0, 1.0),  # Albedo Tint
            2: False,  # Enable Diffuse Transmission
            3: 0.0,  # Opacity Ratio
            4: (1.0, 1.0, 1.0, 1.0),  # Diffuse Tranmission Tint
            5: 1.0,  # Diffuse Transmission Multiplier
            6: 0.5,  # Roughness Amount
            7: 0.0,  # Roughness Map Influence
            8: 0.0,  # Roughness Map
            9: 0.0,  # Anisotropy Amount
            10: 0.0,  # Anisotropy Map Influence
            11: 0.0,  # Anisotrphy Map,
            12: 0.0,  # Metallic Amount
            13: 0.0,  # Metallic Map Influence
            14: 0.0,  # Metallic Map
            15: 1.0,  # Specular Amount
            16: 0.0,  # Specular Map
            17: True,  # Enable ORM Texture
            18: (1.0, 1.0, 1.0, 1.0),  # ORM Map
            19: False,  # Enable Clearcoat Layer
            20: (1.0, 1.0, 1.0, 1.0),  # Clearcoat Tint
            21: 1.0,  # Clearcoat Transparency
            22: 0.0,  # Clearcoat Roughness
            23: 1.0,  # Clearcoat Weight
            24: 1.0,  # Clearcoat Flatten
            25: 1.0,  # Clearcoat IOR
            26: 0.0,  # ClearcoatNormalMap Strength
            27: (0.0, 0.0, 0.0, 1.0),  # Clearcoat Normal Map
            28: False,  # Enable Retro-reflection
            29: (0.181998, 0.8, 0.0, 1.0),  # Retro-reflection tint
            30: 0.5,  # Retro-reflection weight facing
            31: 1.0,  # Retro-reflection weight edge
            32: 0.0,  # AO to Diffuse
            33: 1.0,  # Ambient Occlusion Map
            34: False,  # Enable Emission
            35: (0.0, 0.0, 0.0, 1.0),  # Emissive Color
            36: (0.0, 0.0, 0.0, 1.0),  # Emissive Mask Map
            37: 40.0,  # Emissive Intensity
            38: False,  # Enable Opacity
            39: 0.0,  # Opacity Map
            40: False,  # Enable Alpha Cutout
            41: 0.0,  # Alpha Cutout Cutoff
            42: 0.0,  # Normal Map Strength
            43: (0.0, 0.0, 0.0, 1.0),  # Normal Map
        }
    }

    node_defaults_simbpr_trans = {
        MAT_TYPE_SIMPBR_TRANSLUCENT: {
            0: 1.05,  # IOR Default
            1: 0.01,  # Roughness
            2: False,  # Rougness Map Influence on?
            3: 0.0,  # Roughness Map Influence
            4: (1.0, 1.0, 1.0, 1.0),  # Transmittance Color (RGBA)
            5: 1000.0,  # Transmittance distance
            6: True,  # Enable Thin Walled
            7: False,  # Enable Emission
            8: (0.0, 0.0, 0.0, 1.0),  # Emissive Color
            9: (0.0, 0.0, 0.0, 1.0),  # Emissive Map
            10: 0.0,  # Emissive Intensity
            11: False,  # Enable Flipbook
            14: 0.0,  # Normal Map Strength
            15: (0.0, 0.0, 0.0, 1.0),  # Normal Map Color
        }
    }

    # ---------------
    # MAPPING TABLES
    # Maps all possible inputs to SimPBR Attributes
    # ---------------

    omnipbr_simpbr_map = {
        ATTR_ALBEDO_MAP: ATTR_ALBEDO_MAP,
        ATTR_ALBEDO_TINT: ATTR_ALBEDO_TINT,
        "Specular": ATTR_SPECULAR_AMOUNT,
        ATTR_ORM_MAP: ATTR_ORM_MAP,
        "AO Map": ATTR_AO_MAP,
        ATTR_AO_TO_DIFFUSE: ATTR_AO_TO_DIFFUSE,
        ATTR_METALLIC_AMOUNT: ATTR_METALLIC_AMOUNT,
        ATTR_METALLIC_MAP: ATTR_METALLIC_MAP,
        ATTR_METALLIC_MAP_INFLUENCE: ATTR_METALLIC_MAP_INFLUENCE,
        ATTR_ROUGHNESS_AMOUNT: ATTR_ROUGHNESS_AMOUNT,
        ATTR_ROUGHNESS_MAP: ATTR_ROUGHNESS_MAP,
        ATTR_ROUGHNESS_MAP_INFLUENCE: ATTR_ROUGHNESS_MAP_INFLUENCE,
        ATTR_EMISSIVE_INTENSITY: ATTR_EMISSIVE_INTENSITY,
        ATTR_EMISSIVE_COLOR: ATTR_EMISSIVE_COLOR,
        ATTR_EMISSIVE_MASK_MAP: ATTR_EMISSIVE_MASK_MAP,
        ATTR_NORMAL_MAP: ATTR_NORMAL_MAP,
        ATTR_NORMAL_MAP_STRENGTH: ATTR_NORMAL_MAP_STRENGTH,
        "Opacity Amount": ATTR_OPACITY_MAP,
        "Opacity Threshold": ATTR_ALPHA_CUTOUT_CUTOFF,
        "Use ORM Map": ATTR_ENABLE_ORM_TEXTURE,
        ATTR_ENABLE_OPACITY: ATTR_ENABLE_OPACITY,
        ATTR_ENABLE_EMISSION: ATTR_ENABLE_EMISSION,
    }

    omniglass_translucent_map = {
        "Absorbtion Coeff": "",
        "Glass Color": ATTR_TRANSMITTANCE_COLOR,
        "Glass Roughness": ATTR_ROUGHNESS_AMOUNT,
        "Roughness Texture": ATTR_ROUGHNESS_MAP,
        "Roughness Texture Influence": "",
        "Glass IOR": ATTR_INDEX_OF_REFRACTION,
        "Thin Walled": ATTR_ENABLE_THIN_WALLED,
        "Normal Map Texture": ATTR_NORMAL_MAP,
        "Normal Map Strength": "Normal Map Stength",
    }

    principle_simpbr_map = {
        "Base Color": ATTR_ALBEDO_MAP,
        "Metallic": ATTR_METALLIC_AMOUNT,
        "Roughness": ATTR_ROUGHNESS_AMOUNT,
        "Alpha": ATTR_ALPHA_CUTOUT_CUTOFF,
        "Normal": ATTR_NORMAL_MAP,
        "Anisotropic": ATTR_ANISOTROPY_AMOUNT,
        "Transmission Weight": ATTR_DIFFUSE_TRANSMISSION_MULTIPLIER,
        "Coat Weight": ATTR_CLEARCOAT_WEIGHT,
        "Coat Roughness": ATTR_CLEARCOAT_ROUGHNESS,
        "Coat IOR": ATTR_CLEARCOAT_IOR,
        "Coat Tint": ATTR_CLEARCOAT_TINT,
        "Coat Normal": ATTR_CLEARCOAT_NORMAL_MAP,
        "Emission Color": ATTR_EMISSIVE_COLOR,
        "Emission Strength": ATTR_EMISSIVE_INTENSITY,
    }

    def replace_with_simpbr_temp(material, template_mat, node_defaults):
        """
        Clear out material tree
        Build new node graph from template tree
        """

        def copy_node_attributes(source_node, target_node):
            """Copy attributes from source node to target node safely."""
            for attr in dir(source_node):
                if not attr.startswith("_") and hasattr(target_node, attr):
                    try:
                        setattr(target_node, attr, getattr(source_node, attr))
                    except (AttributeError, TypeError):
                        pass

        def apply_node_default(new_node, input_index, default_value, material_name, node_label):
            """Apply a default value to a node input socket."""
            try:
                if isinstance(default_value, tuple):
                    # Check if the input socket exists and set the default color
                    if hasattr(new_node.inputs[input_index], "default_value"):
                        new_node.inputs[input_index].default_value = default_value
                else:
                    # Set default float or boolean values
                    new_node.inputs[input_index].default_value = default_value
            except (IndexError, AttributeError, TypeError) as e:
                print(f"Problem with material:{material_name}")
                print(f"Could not set default value {input_index} on {node_label}: {e}")

        def apply_node_defaults(new_node, node_label, node_defaults, material_name):
            """Apply all default values for a node based on its label."""
            if node_label not in node_defaults:
                return

            for input_index, default_value in node_defaults[node_label].items():
                apply_node_default(new_node, input_index, default_value, material_name, node_label)

        def copy_template_node(node, node_tree, node_defaults, material_name):
            """Copy a single node from template to material node tree."""
            try:
                new_node = node_tree.nodes.new(type=node.bl_idname)
                new_node.location = node.location

                copy_node_attributes(node, new_node)
                apply_node_defaults(new_node, node.label, node_defaults, material_name)

                return new_node
            except (RuntimeError, AttributeError, TypeError) as e:
                print(f"Error copying node {node.name}: {e}")
                return None

        def reconnect_node_link(link, node_mapping, node_tree):
            """Reconnect a single link between nodes."""
            from_node = node_mapping.get(link.from_node)
            to_node = node_mapping.get(link.to_node)

            if not (from_node and to_node):
                return

            try:
                from_socket = from_node.outputs[link.from_socket.name]
                to_socket = to_node.inputs[link.to_socket.name]
                node_tree.links.new(from_socket, to_socket)
            except (KeyError, IndexError, AttributeError):
                print(f"Failed to connect sockets: {link.from_node.name} -> {link.to_node.name}")

        # Main function logic
        if template_mat.library:
            material.make_local()

        material.use_nodes = True
        node_tree = material.node_tree
        node_tree.nodes.clear()

        # Copy all nodes from template
        node_mapping = {}
        for node in template_mat.node_tree.nodes:
            new_node = copy_template_node(node, node_tree, node_defaults, material.name)
            if new_node:
                node_mapping[node] = new_node

        # Reconnect all links
        for link in template_mat.node_tree.links:
            reconnect_node_link(link, node_mapping, node_tree)

    def apply_old_vals(material: bpy.types.Material, old_mat_attrs: dict, mapping_table: dict, glass=False) -> None:
        """
        Copys all old values from previous shader to new template shader
        Attribute: mapping_table is various dicts that map:
            omniglass -> simPBR_translucent,
            omnipbr -> simPBR,
            principleBSDF -> simPBR
        """

        for old_attr, new_attr in mapping_table.items():
            try:
                value = old_mat_attrs.get(old_attr)
            except AttributeError:
                value = None

            if material.use_nodes:
                node_tree = material.node_tree
                links = material.node_tree.links
                sim_pbr_node = None
                for node in node_tree.nodes:
                    if not glass and node.label == MAT_TYPE_SIMPBR:
                        sim_pbr_node = node
                        break
                    elif glass and node.label == MAT_TYPE_SIMPBR_TRANSLUCENT:
                        sim_pbr_node = node
                        break

                for node in node_tree.nodes:
                    if hasattr(node, "inputs"):
                        for input_socket in node.inputs:
                            if input_socket.name == new_attr:
                                try:
                                    value = old_mat_attrs.get(old_attr)
                                except AttributeError:
                                    value = None

                                if isinstance(value, list) and value:
                                    try:
                                        if len(value) == 4:  # RGBA / color
                                            # check if it's a map
                                            if "map" not in input_socket.name.lower():
                                                if any(c > 1 for c in value):
                                                    normalized_color = [c / 255 for c in value]
                                                else:
                                                    normalized_color = [float(c) for c in value]

                                                blender_color = tuple(normalized_color)

                                                input_socket.default_value = blender_color
                                            else:
                                                new_val = float(1.0)
                                                input_socket.default_value = new_val
                                        else:
                                            print(f"Unhandled value type for input '{new_attr}': {blender_color}")
                                            print(f"type of new attr is {type(blender_color)}")
                                    except (ValueError, TypeError, AttributeError) as e:
                                        print(f"Error converting color value for '{new_attr}': {e}")
                                        blender_color = tuple(value)
                                        input_socket.default_value = blender_color

                                elif isinstance(value, float):
                                    try:
                                        input_socket.default_value = value
                                    except (AttributeError, TypeError) as e:
                                        print(f"Could not set float value for socket '{new_attr}': {e}")
                                elif isinstance(value, int):
                                    try:
                                        input_socket.default_value = bool(value)
                                    except (AttributeError, TypeError) as e:
                                        print(f"Could not set bool value for socket '{new_attr}': {e}")
                                else:
                                    print(f"Unknown value type of {type(value)} for input {new_attr}")

        # start adding texture maps back into sockets.
        i_offset = 0

        for old_attr, old_attr_vals in old_mat_attrs.items():
            if "_connection" in old_attr:
                connection_data = old_attr_vals[list(old_attr_vals.keys())[0]]

                if connection_data:
                    start_loc_x = -263
                    start_loc_y = 838
                    offset = i_offset * -300
                    set_y = start_loc_y + offset
                    connection_name = mapping_table[old_attr.replace("_connection", "")]
                    nodes = node_tree.nodes
                    texture_node = nodes.new(type="ShaderNodeTexImage")
                    texture_node.location = (start_loc_x, set_y)

                    for connection_attr, connection_val in connection_data.items():
                        if "file_path" in connection_attr:
                            try:
                                texture_node.image = bpy.data.images.load(connection_val)
                            except (OSError, RuntimeError) as e:
                                print(f"Missing image: {connection_val} - {e}")
                                texture_node.image = bpy.data.images.load(FALLBACK_TEX)

                        if "colorspace" in connection_attr and texture_node.image:
                            texture_node.image.colorspace_settings.name = connection_val

                    links.new(texture_node.outputs["Color"], sim_pbr_node.inputs[connection_name])
                    i_offset += 1

    # ------------------------------------------------------------
    # GRAB TEMPLATE(S), APPLY TEMPLATE DEFAULTS, APPLY OLD ATTRS
    # -------------------------------------------------------------
    try:
        simpbr_glass_template = template_materials[0]
        simpbr_template = template_materials[1]
    except IndexError as e:
        print(f"Can't get one or both template materials: {e}")
        simpbr_glass_template = None
        simpbr_template = None

    if not simpbr_glass_template or not simpbr_template:
        print(f"Template materials '{template_materials}' not found.")
    else:
        for material_dict in store_old_attrs:
            for curr_mat, transition_dict in material_dict.items():
                for target_mat in transition_dict.keys():
                    attribute_dict = transition_dict[target_mat]
                    for mat_name, all_attrs_dict in attribute_dict.items():
                        if curr_mat == MAT_TYPE_OMNIGLASS and target_mat == "to_SimPBR_trans":
                            print(f"Changing this material: {mat_name} to simPBR_translucent")
                            material = bpy.data.materials.get(mat_name)
                            print(material)
                            template_material = simpbr_glass_template
                            print(template_material)
                            replace_with_simpbr_temp(material, template_material, node_defaults_simbpr_trans)
                            # MAP OLD ATTRS
                            apply_old_vals(material, all_attrs_dict, omniglass_translucent_map, True)

                        elif curr_mat == MAT_TYPE_OMNIPBR and target_mat == "to_SimPBR":
                            print(f"Changing this material: {mat_name} to SimPBR")
                            material = bpy.data.materials.get(mat_name)
                            template_material = simpbr_template
                            replace_with_simpbr_temp(material, template_material, node_defaults_simbpr)
                            apply_old_vals(material, all_attrs_dict, omnipbr_simpbr_map, False)

                        elif curr_mat == MAT_TYPE_PRINCIPLED_BSDF and target_mat == "to_SimPBR":
                            print(f"Changing this material: {mat_name} to SimPBR")
                            material = bpy.data.materials.get(mat_name)
                            template_material = simpbr_template
                            replace_with_simpbr_temp(material, template_material, node_defaults_simbpr)

                            # MAP OLD ATTRS
                            apply_old_vals(material, all_attrs_dict, principle_simpbr_map, False)

                        else:  # principled bsdf -> simpbr_trans
                            print(f"Changing this material: {mat_name} to SimPBR_translucent")
                            material = bpy.data.materials.get(mat_name)
                            template_material = simpbr_glass_template
                            replace_with_simpbr_temp(material, template_material, node_defaults_simbpr_trans)
                            print("\n")
                            print("No Mappable attributes from PrincipledShader as glass -> SimPBR_translucent!")
                            print("Material will receive defaults!")

        print("\n")
        print("---------------------------------")
        print("finished converting all materials")
        print("---------------------------------")


# --------------------------------
# USD MATERIAL UTILS
# --------------------------------

# USD Material Attribute Mapping - SimPBR Translucent
USD_ATTRS_MAP_SIMPBR_TRANS = {
    ATTR_INDEX_OF_REFRACTION: ["ior_constant", "float"],
    ATTR_ROUGHNESS_AMOUNT: ["reflection_roughness_constant", "float"],
    ATTR_ROUGHNESS_MAP_INFLUENCE: ["reflection_roughness_texture_influence", "float"],
    "Rougness Map": ["reflectionroughness_texture", "texture"],
    ATTR_TRANSMITTANCE_COLOR: ["transmittance_color", "color"],
    ATTR_TRANSMITTANCE_MEASUREMENT_DISTANCE: ["transmittance_measurement_distance", "float"],
    ATTR_ENABLE_THIN_WALLED: ["enable_thin_walled", "bool"],
    ATTR_ENABLE_EMISSION: ["enable_emission", "bool"],
    ATTR_EMISSIVE_COLOR: ["emissive_color", "color"],
    ATTR_EMISSIVE_MASK_MAP: ["emissive_mask_texture", "texture"],
    ATTR_EMISSIVE_INTENSITY: ["emissive_intensity", "float"],
    ATTR_NORMAL_MAP_STRENGTH: ["bump_factor", "float"],
    ATTR_NORMAL_MAP: ["normalmap_texture", "texture"],
}

# USD Material Attribute Mapping - SimPBR
USD_ATTRS_MAP_SIMPBR = {
    # Float attributes
    ATTR_OPACITY_RATIO: ["opacity_ratio", "float"],
    ATTR_DIFFUSE_TRANSMISSION_MULTIPLIER: ["opacity_multiplier", "float"],
    ATTR_ROUGHNESS_AMOUNT: ["reflection_roughness_constant", "float"],
    ATTR_ROUGHNESS_MAP_INFLUENCE: ["reflection_roughness_texture_influence", "float"],
    ATTR_ANISOTROPY_AMOUNT: ["anisotropy_constant", "float"],
    ATTR_ANISOTROPY_MAP_INFLUENCE: ["anisotropy_texture_influence", "float"],
    ATTR_METALLIC_AMOUNT: ["metallic_constant", "float"],
    ATTR_METALLIC_MAP_INFLUENCE: ["metallic_texture_influence", "float"],
    ATTR_SPECULAR_AMOUNT: ["specular_constant", "float"],
    ATTR_CLEARCOAT_TRANSPARENCY: ["clearcoat_transparency", "float"],
    ATTR_CLEARCOAT_ROUGHNESS: ["clearcoat_reflection_roughness", "float"],
    ATTR_CLEARCOAT_WEIGHT: ["clearcoat_weight", "float"],
    ATTR_CLEARCOAT_FLATTEN: ["clearcoat_flatten", "float"],
    ATTR_CLEARCOAT_IOR: ["clearcoat_ior", "float"],
    ATTR_CLEARCOAT_NORMAL_MAP_STRENGTH: ["clearcoat_bump_factor", "float"],
    ATTR_RETRO_REFLECTION_WEIGHT_FACING: ["normal_reflectivity", "float"],
    ATTR_RETRO_REFLECTION_WEIGHT_EDGE: ["grazing_reflectivity", "float"],
    ATTR_AO_TO_DIFFUSE: ["ao_to_diffuse", "float"],
    ATTR_EMISSIVE_INTENSITY: ["emissive_intensity", "float"],
    ATTR_NORMAL_MAP_STRENGTH: ["bump_factor", "float"],
    ATTR_ALPHA_CUTOUT_CUTOFF: ["alpha_cutout_cutoff", "float"],
    # Boolean attributes
    ATTR_ENABLE_DIFFUSE_TRANSMISSION: ["enable_transmission", "bool"],
    ATTR_ENABLE_ORM_TEXTURE: ["enable_ORM_texture", "bool"],
    ATTR_ENABLE_CLEARCOAT_LAYER: ["enable_clearcoat", "bool"],
    ATTR_ENABLE_RETRO_REFLECTION: ["enable_retroreflection", "bool"],
    ATTR_ENABLE_EMISSION: ["enable_emission", "bool"],
    ATTR_ENABLE_OPACITY: ["enable_opacity", "bool"],
    ATTR_ENABLE_ALPHA_CUTOUT: ["enable_opacity_cutout", "bool"],
    # Color attributes
    ATTR_ALBEDO_TINT: ["diffuse_tint", "color"],
    ATTR_DIFFUSE_TRANSMISSION_TINT: ["opacity_tint", "color"],
    ATTR_CLEARCOAT_TINT: ["clearcoat_tint", "color"],
    ATTR_RETRO_REFLECTION_TINT: ["retroreflection_tint", "color"],
    ATTR_EMISSIVE_COLOR: ["emissive_color", "color"],
    # Texture attributes
    ATTR_AO_MAP: ["ao_texture", "texture"],
    ATTR_EMISSIVE_MASK_MAP: ["emissive_mask_texture", "texture"],
    ATTR_OPACITY_MAP: ["opacity_texture", "texture"],
    ATTR_NORMAL_MAP: ["normalmap_texture", "texture"],
    ATTR_ROUGHNESS_MAP: ["roughness_texture", "texture"],
    ATTR_ANISOTROPY_MAP: ["anisotrophy_texture", "texture"],
    ATTR_METALLIC_MAP: ["metallic_texture", "texture"],
    ATTR_SPECULAR_MAP: ["specular_texture", "texture"],
    ATTR_ORM_MAP: ["ORM_texture", "texture"],
    ATTR_CLEARCOAT_NORMAL_MAP: ["clearcoat_normalmap_texture", "texture"],
    # Special case for Albedo Map (can be either color or texture)
    ATTR_ALBEDO_MAP: {"color": ["diffuse_color_constant", "color"], "texture": ["diffuse_texture", "texture"]},
}


def color_to_vec3f(color_value: list) -> Gf.Vec3f:
    """Convert a color list to USD Vec3f."""
    return Gf.Vec3f(color_value[0], color_value[1], color_value[2])


def blender_to_kit_color_space(color_space: str) -> str:
    """Convert Blender color space name to Kit/USD color space."""
    return "raw" if color_space == "Non-Color" else "sRGB"


def determine_material_path(blender_file_path: str, root_path: str, material_name: str) -> str:
    """Determine USD material path based on asset type."""
    blender_abs_path = resolve_blender_path(blender_file_path)
    blender_type = determine_asset_type(blender_abs_path)

    if blender_type == "prop":
        return f"{root_path}/Looks/{material_name}"
    elif blender_type == "vehicle":
        return f"{root_path}/materials/{material_name}"
    else:
        raise ValueError(f"Asset: {blender_abs_path} has unknown asset type: {blender_type}")


def setup_usd_shader(shader, material_type: str, mdl_path: str):
    """Set up USD shader with MDL source and identifier."""
    if material_type == MAT_TYPE_SIMPBR:
        shader.CreateIdAttr(f"mdl:{MAT_TYPE_SIMPBR}")
        shader.CreateInput("mdl:sourceAsset", Sdf.ValueTypeNames.String)
        shader.SetSourceAsset(Sdf.AssetPath(mdl_path), "mdl")
        shader.SetSourceAssetSubIdentifier(MAT_TYPE_SIMPBR, "mdl")
    elif material_type == MAT_TYPE_SIMPBR_TRANSLUCENT:
        shader.CreateIdAttr(f"mdl:{MAT_TYPE_SIMPBR_TRANSLUCENT}")
        shader.CreateInput("mdl:sourceAsset", Sdf.ValueTypeNames.String)
        shader.SetSourceAsset(Sdf.AssetPath(mdl_path), "mdl")
        shader.SetSourceAssetSubIdentifier(MAT_TYPE_SIMPBR_TRANSLUCENT, "mdl")
    else:
        raise ValueError(f"Material type: {material_type} is unknown")


def connect_shader_outputs(material, shader):
    """Create and connect shader outputs to material."""
    shader_output = shader.CreateOutput("out", Sdf.ValueTypeNames.Token)
    if not shader_output:
        raise ValueError("Failed to create shader output for the shader")

    material_output = material.CreateSurfaceOutput()
    if not material_output:
        raise ValueError("Failed to create surface output for the material")

    material_output.ConnectToSource(shader_output)


def get_attribute_mapping(input_attr: str, material_type: str, connection: dict):
    """Get the USD attribute mapping info for a given input attribute."""
    attr_map = USD_ATTRS_MAP_SIMPBR if material_type == MAT_TYPE_SIMPBR else USD_ATTRS_MAP_SIMPBR_TRANS

    # Handle the special case for Albedo Map (only for SimPBR)
    if input_attr == ATTR_ALBEDO_MAP and material_type == MAT_TYPE_SIMPBR:
        if input_attr in connection:  # If connected, it's a texture
            return USD_ATTRS_MAP_SIMPBR[ATTR_ALBEDO_MAP]["texture"]
        else:  # If not connected, it's a color
            return USD_ATTRS_MAP_SIMPBR[ATTR_ALBEDO_MAP]["color"]

    return attr_map.get(input_attr)


def process_texture_attribute(input_attr: str, connection: dict, export_file_path: str):
    """Process texture attribute and copy texture file to export directory."""
    color_space = blender_to_kit_color_space(connection[input_attr]["texture_colorspace"])
    map_name = input_attr.replace("_connection", "")
    texture_path = connection[map_name]["texture_path"]
    abs_file_path = resolve_blender_path(texture_path)

    if not abs_file_path or not os.path.exists(abs_file_path):
        print(f"Texture file not found for {input_attr}: {texture_path}")
        print(f"  Resolved to: {abs_file_path}")
        print("  Skipping texture attribute...")
        return None, None

    parent_dir = os.path.dirname(export_file_path)
    textures_dir = os.path.join(parent_dir, "textures")

    if not os.path.exists(textures_dir):
        os.makedirs(textures_dir, exist_ok=True)

    file_name = os.path.basename(abs_file_path)
    dest_path = os.path.join(textures_dir, file_name)

    if not os.path.exists(dest_path):
        shutil.copy(abs_file_path, dest_path)

    return dest_path, color_space


def convert_attribute_value(input_type: str, o_value, input_attr: str, connection: dict, export_file_path: str):
    """Convert attribute value to appropriate USD type and value."""
    if input_type == "float":
        return Sdf.ValueTypeNames.Float, o_value, None
    elif input_type == "bool":
        return Sdf.ValueTypeNames.Bool, o_value, None
    elif input_type == "color":
        return Sdf.ValueTypeNames.Color3f, color_to_vec3f(o_value), None
    elif input_type == "texture":
        try:
            value, color_space = process_texture_attribute(input_attr, connection, export_file_path)
            if value is None:
                return None, None, None
            return Sdf.ValueTypeNames.Asset, value, color_space
        except KeyError as e:
            print(f"Texture information not found for {input_attr}: {e}")
            return None, None, None
        except (OSError, IOError, shutil.Error) as e:
            print(f"Error processing texture for {input_attr}: {e}")
            return None, None, None

    return None, None, None


def set_usd_shader_input(shader, shader_input, usd_attr_name: str, sdf_type, value, color_space: Optional[str]):
    """Set a USD shader input attribute with the given value."""
    if value is None or sdf_type is None:
        return False

    shader.CreateInput(usd_attr_name, sdf_type)
    curr_input = shader_input.GetAttribute(f"inputs:{usd_attr_name}")
    curr_input.Set(value)

    if color_space:
        curr_input.SetColorSpace(color_space)

    return True


def create_usd_material_attribute(
    input_attr: str, values: dict, connection: dict, shader, shader_input, export_file_path: str, material_type: str
):
    """Create a single USD material attribute based on input type and values."""
    o_value = values[input_attr]

    # Get attribute mapping
    attr_info = get_attribute_mapping(input_attr, material_type, connection)
    if not attr_info:
        print(f"Unknown attribute: {input_attr}")
        return

    # Extract USD attribute name and type
    if isinstance(attr_info, list):
        usd_attr_name, input_type = attr_info
    else:
        usd_attr_name, input_type = attr_info

    # Convert value to USD format
    sdf_type, value, color_space = convert_attribute_value(
        input_type, o_value, input_attr, connection, export_file_path
    )

    # Set the shader input
    if not set_usd_shader_input(shader, shader_input, usd_attr_name, sdf_type, value, color_space):
        print(f"Could not set value for {input_attr}: value={value}, type={input_type}")


def apply_material_attributes(
    possible_inputs: list,
    values: dict,
    connection: dict,
    shader,
    shader_input,
    export_file_path: str,
    material_type: str,
):
    """Apply all material attributes to the USD shader."""
    attr_map = USD_ATTRS_MAP_SIMPBR if material_type == MAT_TYPE_SIMPBR else USD_ATTRS_MAP_SIMPBR_TRANS

    for input_attr in possible_inputs:
        if input_attr in attr_map:
            create_usd_material_attribute(
                input_attr, values, connection, shader, shader_input, export_file_path, material_type
            )


def get_socket_value(socket):
    """
    Get the actual value of a socket, whether it's connected or not
    """
    if socket.is_linked:
        from_node = socket.links[0].from_node
        if from_node.type == "VALUE":
            return from_node.outputs[0].default_value
        elif from_node.type == "RGB":
            return list(from_node.outputs[0].default_value)
    return list(socket.default_value) if hasattr(socket.default_value, "__len__") else socket.default_value


def simpbr_attrs(material) -> dict:
    """
    Function to get all simpbr attrs from a single material
    """

    def find_simpbr_node(node_tree):
        """Find SimPBR or SimPBR Translucent node in the material."""
        for node in node_tree.nodes:
            if node.label in (MAT_TYPE_SIMPBR, MAT_TYPE_SIMPBR_TRANSLUCENT):
                return node
            if node.name in (MAT_TYPE_SIMPBR, MAT_TYPE_SIMPBR_TRANSLUCENT):
                return node
        return None

    def collect_enabled_inputs(sim_pbr_node):
        """Collect all enabled input names from the SimPBR node."""
        return [input.name for input in sim_pbr_node.inputs if input.enabled]

    def extract_connection_info(from_node):
        """Extract connection information from a linked node."""
        connection_info = {"node_type": from_node.type, "node_name": from_node.name}

        # Capture texture information if it's a texture node
        if from_node.type == "TEX_IMAGE" and from_node.image:
            connection_info.update(
                {
                    "texture_path": from_node.image.filepath,
                    "texture_colorspace": from_node.image.colorspace_settings.name,
                    "projection_type": from_node.projection,
                    "extension_type": from_node.extension,
                }
            )

        return connection_info

    def extract_input_attributes(sim_pbr_node, possible_inputs):
        """Extract values and connections for all enabled inputs."""
        attributes = {"values": {}, "connections": {}}

        for input_name in possible_inputs:
            socket = sim_pbr_node.inputs.get(input_name)
            attributes["values"][input_name] = get_socket_value(socket)

            # Get connection information if the socket is linked
            if socket.is_linked:
                from_node = socket.links[0].from_node
                attributes["connections"][input_name] = extract_connection_info(from_node)

        return attributes

    def debug_print_attributes(material_name, attributes, possible_inputs):
        """Debug helper to print attributes for specific materials."""
        if material_name == "CarPaint":
            from pprint import pprint

            print("simpbr_attrs:")
            pprint(attributes, indent=4)
            print("possible_inputs:")
            pprint(possible_inputs, indent=4)

    # Main function logic
    if not material.use_nodes:
        return {}, []

    sim_pbr_node = find_simpbr_node(material.node_tree)
    if not sim_pbr_node:
        print(f"Warning: No {MAT_TYPE_SIMPBR} or {MAT_TYPE_SIMPBR_TRANSLUCENT} node found in material {material.name}")
        return {}, []

    possible_inputs = collect_enabled_inputs(sim_pbr_node)
    attributes = extract_input_attributes(sim_pbr_node, possible_inputs)

    # Debug output for specific materials
    debug_print_attributes(material.name, attributes, possible_inputs)

    return attributes, possible_inputs


def create_usd_material(stage, material_name, mdl_path, root_path, material_type, export_file_path):
    """
    Creates a USD material that references the SimPBR MDL shader
    """

    material = bpy.data.materials.get(material_name)
    attrs, possible_inputs = simpbr_attrs(material)

    if not attrs:
        print(f"No {MAT_TYPE_PRINCIPLED_BSDF} found in material {material_name}")
        return

    # Create material
    # base this on the asset type
    blender_file_path = get_blender_file_path()
    blender_abs_path = resolve_blender_path(blender_file_path)
    blender_type = determine_asset_type(blender_abs_path)

    if blender_type == "prop":
        material_path = f"{root_path}/Looks/{material_name}"
    elif blender_type == "vehicle":
        material_path = f"{root_path}/materials/{material_name}"
    else:
        raise ValueError(f"Asset: {blender_abs_path} has unknown asset type: {blender_type}")

    material = UsdShade.Material.Define(stage, material_path)

    # Create shader
    shader = UsdShade.Shader.Define(stage, f"{material_path}/Shader")

    # Set MDL shader identifier and source asset
    if material_type == MAT_TYPE_SIMPBR:
        shader.CreateIdAttr(f"mdl:{MAT_TYPE_SIMPBR}")
        shader.CreateInput("mdl:sourceAsset", Sdf.ValueTypeNames.String)
        shader.SetSourceAsset(Sdf.AssetPath(mdl_path), "mdl")
        shader.SetSourceAssetSubIdentifier(MAT_TYPE_SIMPBR, "mdl")
    elif material_type == MAT_TYPE_SIMPBR_TRANSLUCENT:
        shader.CreateIdAttr(f"mdl:{MAT_TYPE_SIMPBR_TRANSLUCENT}")
        shader.CreateInput("mdl:sourceAsset", Sdf.ValueTypeNames.String)
        shader.SetSourceAsset(Sdf.AssetPath(mdl_path), "mdl")
        shader.SetSourceAssetSubIdentifier(MAT_TYPE_SIMPBR_TRANSLUCENT, "mdl")
    else:
        raise ValueError(f"Material type: {material_type} is unknown")

    # Define shader output
    shader_output = shader.CreateOutput("out", Sdf.ValueTypeNames.Token)
    if not shader_output:
        raise ValueError("Failed to create shader output for the shader")

    # Create material surface output and connect it to shader output
    material_output = material.CreateSurfaceOutput()
    if not material_output:
        raise ValueError("Failed to create surface output for the material")

    # Connect the material's surface output to the shader's surface output
    material_output.ConnectToSource(shader_output)

    def color_to_vec3f(color_value: list) -> Gf.Vec3f:
        return Gf.Vec3f(color_value[0], color_value[1], color_value[2])

    def blender_to_kit_color(color_space) -> str:
        if color_space == "Non-Color":
            return "raw"
        else:
            return "sRGB"

    if "values" in attrs or "connections" in attrs:
        values = attrs["values"]
        connection = attrs["connections"]
        shader_input = stage.GetPrimAtPath(f"{material_path}/Shader")

        b_attrs_map_simpbr_trans = {
            ATTR_INDEX_OF_REFRACTION: ["ior_constant", "float"],
            ATTR_ROUGHNESS_AMOUNT: ["reflection_roughness_constant", "float"],
            ATTR_ROUGHNESS_MAP_INFLUENCE: ["reflection_roughness_texture_influence", "float"],
            "Rougness Map": ["reflectionroughness_texture", "texture"],
            ATTR_TRANSMITTANCE_COLOR: ["transmittance_color", "color"],
            ATTR_TRANSMITTANCE_MEASUREMENT_DISTANCE: ["transmittance_measurement_distance", "float"],
            ATTR_ENABLE_THIN_WALLED: ["enable_thin_walled", "bool"],
            ATTR_ENABLE_EMISSION: ["enable_emission", "bool"],
            ATTR_EMISSIVE_COLOR: ["emissive_color", "color"],
            ATTR_EMISSIVE_MASK_MAP: ["emissive_mask_texture", "texture"],
            ATTR_EMISSIVE_INTENSITY: ["emissive_intensity", "float"],
            ATTR_NORMAL_MAP_STRENGTH: ["bump_factor", "float"],
            ATTR_NORMAL_MAP: ["normalmap_texture", "texture"],
        }

        b_attrs_map_simpbr = {
            # Float attributes
            ATTR_OPACITY_RATIO: ["opacity_ratio", "float"],
            ATTR_DIFFUSE_TRANSMISSION_MULTIPLIER: ["opacity_multiplier", "float"],
            ATTR_ROUGHNESS_AMOUNT: ["reflection_roughness_constant", "float"],
            ATTR_ROUGHNESS_MAP_INFLUENCE: ["reflection_roughness_texture_influence", "float"],
            ATTR_ANISOTROPY_AMOUNT: ["anisotropy_constant", "float"],
            ATTR_ANISOTROPY_MAP_INFLUENCE: ["anisotropy_texture_influence", "float"],
            ATTR_METALLIC_AMOUNT: ["metallic_constant", "float"],
            ATTR_METALLIC_MAP_INFLUENCE: ["metallic_texture_influence", "float"],
            ATTR_SPECULAR_AMOUNT: ["specular_constant", "float"],
            ATTR_CLEARCOAT_TRANSPARENCY: ["clearcoat_transparency", "float"],
            ATTR_CLEARCOAT_ROUGHNESS: ["clearcoat_reflection_roughness", "float"],
            ATTR_CLEARCOAT_WEIGHT: ["clearcoat_weight", "float"],
            ATTR_CLEARCOAT_FLATTEN: ["clearcoat_flatten", "float"],
            ATTR_CLEARCOAT_IOR: ["clearcoat_ior", "float"],
            ATTR_CLEARCOAT_NORMAL_MAP_STRENGTH: ["clearcoat_bump_factor", "float"],
            ATTR_RETRO_REFLECTION_WEIGHT_FACING: ["normal_reflectivity", "float"],
            ATTR_RETRO_REFLECTION_WEIGHT_EDGE: ["grazing_reflectivity", "float"],
            ATTR_AO_TO_DIFFUSE: ["ao_to_diffuse", "float"],
            ATTR_EMISSIVE_INTENSITY: ["emissive_intensity", "float"],
            ATTR_NORMAL_MAP_STRENGTH: ["bump_factor", "float"],
            ATTR_ALPHA_CUTOUT_CUTOFF: ["alpha_cutout_cutoff", "float"],
            # Boolean attributes
            ATTR_ENABLE_DIFFUSE_TRANSMISSION: ["enable_transmission", "bool"],
            ATTR_ENABLE_ORM_TEXTURE: ["enable_ORM_texture", "bool"],
            ATTR_ENABLE_CLEARCOAT_LAYER: ["enable_clearcoat", "bool"],
            ATTR_ENABLE_RETRO_REFLECTION: ["enable_retroreflection", "bool"],
            ATTR_ENABLE_EMISSION: ["enable_emission", "bool"],
            ATTR_ENABLE_OPACITY: ["enable_opacity", "bool"],
            ATTR_ENABLE_ALPHA_CUTOUT: ["enable_opacity_cutout", "bool"],
            # Color attributes
            ATTR_ALBEDO_TINT: ["diffuse_tint", "color"],
            ATTR_DIFFUSE_TRANSMISSION_TINT: ["opacity_tint", "color"],
            ATTR_CLEARCOAT_TINT: ["clearcoat_tint", "color"],
            ATTR_RETRO_REFLECTION_TINT: ["retroreflection_tint", "color"],
            ATTR_EMISSIVE_COLOR: ["emissive_color", "color"],
            # Texture attributes
            ATTR_AO_MAP: ["ao_texture", "texture"],
            ATTR_EMISSIVE_MASK_MAP: ["emissive_mask_texture", "texture"],
            ATTR_OPACITY_MAP: ["opacity_texture", "texture"],
            ATTR_NORMAL_MAP: ["normalmap_texture", "texture"],
            ATTR_ROUGHNESS_MAP: ["roughness_texture", "texture"],
            ATTR_ANISOTROPY_MAP: ["anisotrophy_texture", "texture"],
            ATTR_METALLIC_MAP: ["metallic_texture", "texture"],
            ATTR_SPECULAR_MAP: ["specular_texture", "texture"],
            ATTR_ORM_MAP: ["ORM_texture", "texture"],
            ATTR_CLEARCOAT_NORMAL_MAP: ["clearcoat_normalmap_texture", "texture"],
            # Special case for Albedo Map (can be either color or texture)
            ATTR_ALBEDO_MAP: {"color": ["diffuse_color_constant", "color"], "texture": ["diffuse_texture", "texture"]},
        }

        def create_usd_mat_attr(input, values, connection, shader, shader_input, export_file_path, material_type):
            """
            Create USD material attributes based on input type and values
            """
            o_value = values[input]
            color_space = None
            texture_path = None
            value = None
            sdf_type = None

            # Select the appropriate attribute map based on material type
            attr_map = b_attrs_map_simpbr if material_type == MAT_TYPE_SIMPBR else b_attrs_map_simpbr_trans

            # Handle the special case for Albedo Map (only for SimPBR)
            if input == ATTR_ALBEDO_MAP and material_type == MAT_TYPE_SIMPBR:
                if input in connection:  # If connected, it's a texture
                    attr_info = b_attrs_map_simpbr[ATTR_ALBEDO_MAP]["texture"]
                else:  # If not connected, it's a color
                    attr_info = b_attrs_map_simpbr[ATTR_ALBEDO_MAP]["color"]
            else:
                # Handle all other attributes normally
                attr_info = attr_map.get(input)

            if not attr_info:
                print(f"Unknown attribute: {input}")
                return

            # For regular attributes (not Albedo Map)
            if isinstance(attr_info, list):
                usd_attr_name, input_type = attr_info
            else:
                # For Albedo Map, we already determined which version to use above
                usd_attr_name, input_type = attr_info

            if input_type == "float":
                sdf_type = Sdf.ValueTypeNames.Float
                value = o_value
            elif input_type == "bool":
                sdf_type = Sdf.ValueTypeNames.Bool
                value = o_value
            elif input_type == "color":
                sdf_type = Sdf.ValueTypeNames.Color3f
                value = color_to_vec3f(o_value)
            elif input_type == "texture":
                sdf_type = Sdf.ValueTypeNames.Asset
                try:
                    color_space = blender_to_kit_color(connection[input]["texture_colorspace"])
                    map_name = input.replace("_connection", "")
                    texture_path = connection[map_name]["texture_path"]
                    abs_file_path = resolve_blender_path(texture_path)

                    if not abs_file_path or not os.path.exists(abs_file_path):
                        print(f"Texture file not found for {input}: {texture_path}")
                        print(f"  Resolved to: {abs_file_path}")
                        print("  Skipping texture attribute...")
                        return

                    parent_dir = os.path.dirname(export_file_path)
                    textures_dir = os.path.join(parent_dir, "textures")

                    if not os.path.exists(textures_dir):
                        os.makedirs(textures_dir, exist_ok=True)

                    file_name = os.path.basename(abs_file_path)
                    dest_path = os.path.join(textures_dir, file_name)
                    value = dest_path

                    if not os.path.exists(dest_path):
                        shutil.copy(abs_file_path, dest_path)
                except KeyError as e:
                    print(f"Texture information not found for {input}: {e}")
                    return
                except (OSError, IOError, shutil.Error) as e:
                    print(f"Error processing texture for {input}: {e}")
                    print(f"  Texture path: {texture_path if 'texture_path' in locals() else 'unknown'}")
                    return

            if value is not None and sdf_type:
                shader.CreateInput(usd_attr_name, sdf_type)
                curr_input = shader_input.GetAttribute(f"inputs:{usd_attr_name}")
                curr_input.Set(value)

                if color_space:
                    curr_input.SetColorSpace(color_space)
            else:
                print(f"Could not set value for {input}: value={value}, type={input_type}")

        for input in possible_inputs:
            if material_type == MAT_TYPE_SIMPBR:
                if input in b_attrs_map_simpbr.keys():
                    create_usd_mat_attr(
                        input, values, connection, shader, shader_input, export_file_path, material_type
                    )
            else:  # SimPBR_Translucent
                if input in b_attrs_map_simpbr_trans.keys():
                    create_usd_mat_attr(
                        input, values, connection, shader, shader_input, export_file_path, material_type
                    )

    print("Successfully created USD material")


def move_prim(stage, source_path, target_path):
    # Get the source prim
    source_prim = stage.GetPrimAtPath(source_path)
    if not source_prim:
        print(f"Source prim not found at {source_path}")
        return

    # Define the target prim
    target_prim = stage.DefinePrim(target_path, source_prim.GetTypeName())

    # Copy all properties from source to target
    for attr in source_prim.GetAttributes():
        if attr.Get():
            target_attr = target_prim.CreateAttribute(attr.GetName(), attr.GetTypeName())
            target_attr.Set(attr.Get())

    for rel in source_prim.GetRelationships():
        target_rel = target_prim.CreateRelationship(rel.GetName())
        target_rel.SetTargets(rel.GetTargets())

    # Copy all children recursively
    for child in source_prim.GetChildren():
        child_source_path = child.GetPath()
        child_target_path = f"{target_path}/{child.GetName()}"
        move_prim(stage, child_source_path, child_target_path)

    # Remove the original prim
    stage.RemovePrim(source_path)
    print(f"Moved prim from {source_path} to {target_path}")
