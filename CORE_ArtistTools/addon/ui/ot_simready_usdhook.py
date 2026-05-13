# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.
import math
import os
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Union

import bpy
import numpy as np
from pxr import Gf, Sdf, Tf, Usd, UsdGeom, UsdPhysics, UsdShade

# from ..validators_simready.simready_validator import validate_stage
from ..utility.addon import get_prefs

LOGICAL_HIERARCHY = False

# TODO: clean these up and move to library

USER_PROPERTY_PREFIX = "userProperties"

LEGACY_SEMANTICS_CLASS_DATA_ATTR_NAME = "semantic:wikidata_class:params:semanticData"
LEGACY_SEMANTICS_CLASS_TYPE_ATTR_NAME = "semantic:wikidata_class:params:semanticType"
LEGACY_SEMANTICS_CLASS_ATTR_VALUE = "wikidata_class"
SEMANTICS_CLASS_ATTR_NAME = "semantics:labels:wikidata_class"

LEGACY_SEMANTICS_QCODE_DATA_ATTR_NAME = "semantic:wikidata_qcode:params:semanticData"
LEGACY_SEMANTICS_QCODE_TYPE_ATTR_NAME = "semantic:wikidata_qcode:params:semanticType"
LEGACY_SEMANTICS_QCODE_ATTR_VALUE = "wikidata_qcode"
SEMANTICS_QCODE_ATTR_NAME = "semantics:labels:wikidata_qcode"

DOC_ATTR_NAME = "omni:simready:documentation"

NONVISUAL_BASE_ATTR_NAME = "omni:simready:nonvisual:base"
NONVISUAL_COATING_ATTR_NAME = "omni:simready:nonvisual:coating"
NONVISUAL_ATTRIBUTES_ATTR_NAME = "omni:simready:nonvisual:attributes"

VEHICLE_PART_ATTR_NAME = "omni:simready:vehicle"

LIGHT_ATTR_NAME = "omni:simready:light"

LIGHT_INTENSITY_ATTR_NAME_BLENDER_MIN = "omni:simready:light:intensityDomainMin"
LIGHT_INTENSITY_ATTR_NAME_BLENDER_MAX = "omni:simready:light:intensityDomainMax"
LIGHT_INTENSITY_ATTR_NAME = "omni:simready:light:intensityDomain"
LIGHT_COLOR_ATTR_NAME = "omni:simready:light:color"
LIGHT_DURATION_ATTR_NAME = "omni:simready:light:duration"


@dataclass
class BlenderMaterialMapping:
    """Mapping between Blender material attributes and USD/MDL material parameters.

    This class provides structured mappings for converting Blender shader node inputs
    to their corresponding USD/MDL material parameters for OmniPBR and OmniGlass materials.

    Supported Mappings:
        - OmniPBR Compute -> OmniPBR.mdl
        - OmniGlass Compute -> OmniGlass.mdl
        - OmniSurface Compute -> OmniSurface.mdl (not supported yet)
        - Principled BSDF -> OmniPBR.mdl
        - Principled BSDF -> OmniGlass.mdl

    Usage Examples:
        # Get OmniPBR Compute mapping
        pbr_map = BlenderMaterialMapping.get_omnipbr_mapping()

        # Get OmniGlass Compute mapping
        glass_map = BlenderMaterialMapping.get_omniglass_mapping()

        # Get Principled BSDF -> OmniPBR mapping
        principled_pbr = BlenderMaterialMapping.get_principled_to_omnipbr_mapping()

        # Get Principled BSDF -> OmniGlass mapping
        principled_glass = BlenderMaterialMapping.get_principled_to_omniglass_mapping()

        # Get mapping by shader type (flexible)
        mapping = BlenderMaterialMapping.get_mapping_for_shader("principled_to_omnipbr")

        # Get all mappings at once
        all_maps = BlenderMaterialMapping.get_all_mappings()
    """

    @classmethod
    def get_principled_to_omnipbr_mapping(cls) -> Dict[str, Union[List, Dict]]:
        """Get the Principled BSDF -> OmniPBR.mdl attribute mapping.

        Maps standard Blender Principled BSDF shader inputs to OmniPBR parameters.
        Uses dict format for inputs that can be either color/value or texture.

        Returns:
            Dictionary mapping Blender Principled BSDF inputs to [mdl_param, type] pairs.
        """
        return {
            # Base Material Properties - supports both color and texture
            "Base Color": {"color": ["diffuse_color_constant", "color"], "texture": ["diffuse_texture", "texture"]},
            "Metallic": {"color": ["metallic_constant", "float"], "texture": ["metallic_texture", "texture"]},
            "Roughness": {
                "color": ["reflection_roughness_constant", "float"],
                "texture": ["reflectionroughness_texture", "texture"],
            },
            "IOR": ["specular_level", "float"],  # Maps to specular in PBR workflow
            "Alpha": {"color": ["opacity_constant", "float"], "texture": ["opacity_texture", "texture"]},
            # Normal Mapping
            "Normal": {
                "color": ["bump_factor", "float"],  # Fallback if no texture
                "texture": ["normalmap_texture", "texture"],
            },
            "Normal Map Strength": ["bump_factor", "float"],  # Strength from Normal Map node
            # Specular Properties
            "Specular IOR Level": ["specular_level", "float"],
            # "Specular Tint": ["diffuse_tint", "color"],  # Approximate mapping
            # Emission
            "Emission Color": {"color": ["emissive_color", "color"], "texture": ["emissive_color_texture", "texture"]},
            "Emission Strength": ["emissive_intensity", "float"],
            # UV Transform
            "Texture Scale": ["texture_scale", "float2"],  # UV scale from Mapping node
            "Texture Rotate": ["texture_rotate", "float"],  # UV rotation from Mapping node (degrees)
            "Texture Translate": ["texture_translate", "float2"],  # UV offset from Mapping node
        }

    @classmethod
    def get_principled_to_omniglass_mapping(cls) -> Dict[str, Union[List, Dict]]:
        """Get the Principled BSDF -> OmniGlass.mdl attribute mapping.

        Maps Blender Principled BSDF shader inputs (when configured for glass)
        to OmniGlass parameters. Best used when Transmission Weight > 0.

        Returns:
            Dictionary mapping Blender Principled BSDF inputs to [mdl_param, type] pairs.
        """
        return {
            # Glass Color Properties
            # Supports both color values and texture maps
            "Base Color": {
                "color": ["glass_color", "color"],
                "texture": ["glass_color_texture", "texture"],  # Use actual texture, don't average
            },
            # Surface Properties
            "Roughness": ["frosting_roughness", "float"],
            "IOR": ["glass_ior", "float"],
            "Alpha": ["cutout_opacity", "float"],
            # Normal Mapping
            "Normal": ["normal_map_texture", "texture"],
            # UV Transform
            "Texture Scale": ["texture_scale", "float2"],  # UV scale from Mapping node
            "Texture Rotate": ["texture_rotate", "float"],  # UV rotation from Mapping node (degrees)
            "Texture Translate": ["texture_translate", "float2"],  # UV offset from Mapping node
        }

    @classmethod
    def get_omnipbr_mapping(cls) -> Dict[str, Union[List, Dict]]:
        """
        Get the OmniPBR Compute -> OmniPBR.mdl attribute mapping.

        Returns:
            Dictionary mapping Blender attribute names to [mdl_param, type] pairs.
            Special case for "Albedo Map" which has both color and texture sub-mappings.
        """
        return {
            # Albedo Group - Blender uses "Albedo RGB" not "Albedo Color"
            "Albedo RGB": ["diffuse_color_constant", "color"],
            "Albedo Map": {"color": ["diffuse_color_constant", "color"], "texture": ["diffuse_texture", "texture"]},
            "Albedo Desaturation": [
                "albedo_desaturation",
                "float",
            ],  # Blender: "Albedo Desaturation" not "Albedo Map Desaturation"
            "Albedo Add": ["albedo_add", "float"],
            "Albedo Brightness": ["albedo_brightness", "float"],
            "Albedo Tint": ["diffuse_tint", "color"],  # Blender: "Albedo Tint" not "Color Tint"
            # Reflectivity Group
            "Roughness Amount": ["reflection_roughness_constant", "float"],
            "Roughness Map Influence": ["reflection_roughness_texture_influence", "float"],
            "Roughness Map": ["reflectionroughness_texture", "texture"],
            "Metallic Amount": ["metallic_constant", "float"],
            "Metallic Map Influence": ["metallic_texture_influence", "float"],
            "Metallic Map": ["metallic_texture", "texture"],
            "Specular": ["specular_level", "float"],
            # ORM Group
            # When enable_ORM_texture is True, reflection_roughness_texture_influence and
            # metallic_texture_influence MUST be 0.0 because R/M channels come from ORM texture
            "Use ORM Map": ["enable_ORM_texture", "bool"],  # Blender: "Use ORM Map" not "Enable ORM Texture"
            "ORM Map": ["ORM_texture", "texture"],
            # AO Group - Blender uses "AO Map" and "AO to Diffuse"
            "AO to Diffuse": ["ao_to_diffuse", "float"],  # Case sensitive!
            "AO Map": ["ao_texture", "texture"],  # Blender: "AO Map" not "Ambient Occlusion Map"
            # Emission Group
            "Enable Emission": ["enable_emission", "bool"],
            "Emissive Color": ["emissive_color", "color"],
            "Emissive Color Map": ["emissive_color_texture", "texture"],  # Blender: "Emissive Color Map"
            "Emissive Mask Map": ["emissive_mask_texture", "texture"],  # Blender: "Emissive Mask Map"
            "Emissive Intensity": ["emissive_intensity", "float"],
            # Opacity Group
            "Enable Opacity": ["enable_opacity", "bool"],
            "Enable Opacity Texture": ["enable_opacity_texture", "bool"],
            "Opacity Amount": ["opacity_constant", "float"],
            "Opacity Map": ["opacity_texture", "texture"],
            "Opacity Threshold": ["opacity_threshold", "float"],
            # Normal Group - Blender uses "Normal Map Strength" not "Normal Strength"
            "Normal Map Strength": ["bump_factor", "float"],
            "Normal Map": ["normalmap_texture", "texture"],
            "Detail Normal Strength": ["detail_bump_factor", "float"],
            "Detail Normal Map": ["detail_normalmap_texture", "texture"],
            "Normal Map Flip U Tangent": ["flip_tangent_u", "bool"],
            "Normal Map Flip V Tangent": ["flip_tangent_v", "bool"],
            # UV Group
            "Enable Project UVW Coordinates": ["project_uvw", "bool"],
            "Enable World Space": ["world_or_object", "bool"],
            "UV Space Index": ["uv_space_index", "int"],
            "Texture Scale": ["texture_scale", "float2"],  # UV scale from Mapping node
            "Texture Rotate": ["texture_rotate", "float"],  # UV rotation from Mapping node (degrees)
            "Texture Translate": ["texture_translate", "float2"],  # UV offset from Mapping node
        }

    @classmethod
    def get_omniglass_mapping(cls) -> Dict[str, List[str]]:
        """Get the OmniGlass Compute -> OmniGlass.mdl attribute mapping.

        Returns:
            Dictionary mapping Blender attribute names to [mdl_param, type] pairs.
        """
        return {
            "Glass Color": ["glass_color", "color"],
            "Glass Color Texture": ["glass_color_texture", "texture"],
            "Volume Absorption Scale": ["depth", "float"],
            "Glass Roughness": ["frosting_roughness", "float"],
            "Roughness Texture Influence": ["roughness_texture_influence", "float"],
            "Roughness Texture": ["roughness_texture", "texture"],
            "Glass IOR": ["glass_ior", "float"],
            "Thin Walled": ["thin_walled", "bool"],
            "Reflection Color Texture": ["reflection_color_texture", "texture"],
            "Reflection Color": ["reflection_color", "color"],
            "Normal Map Texture": ["normal_map_texture", "texture"],
            "Normal Map Strength": ["normal_map_strength", "float"],
            "Enable Opacity": ["enable_opacity", "bool"],
            "Opacity Amount": ["cutout_opacity", "float"],
            "Opacity Map": ["cutout_opacity_texture", "texture"],
            # UV Transform
            "Texture Scale": ["texture_scale", "float2"],  # UV scale from Mapping node
            "Texture Rotate": ["texture_rotate", "float"],  # UV rotation from Mapping node (degrees)
            "Texture Translate": ["texture_translate", "float2"],  # UV offset from Mapping node
        }

    @classmethod
    def get_mapping_for_shader(cls, shader_type: str) -> Dict[str, Union[List, Dict]]:
        """Get the appropriate mapping table for the specified shader type.

        Args:
            shader_type: The shader type (e.g., "omnipbr", "omniglass", "principled_to_omnipbr", "principled_to_omniglass")

        Returns:
            Dictionary mapping for the specified shader type.

        Raises:
            ValueError: If shader_type is not recognized.
        """
        shader_type_lower = shader_type.lower()

        if shader_type_lower in ("omnipbr", "omni_pbr"):
            return cls.get_omnipbr_mapping()
        elif shader_type_lower in ("omniglass", "omni_glass"):
            return cls.get_omniglass_mapping()
        elif shader_type_lower in ("principled_to_omnipbr", "principled_omnipbr", "principled_pbr"):
            return cls.get_principled_to_omnipbr_mapping()
        elif shader_type_lower in ("principled_to_omniglass", "principled_omniglass", "principled_glass"):
            return cls.get_principled_to_omniglass_mapping()
        else:
            supported_types = "'omnipbr', 'omniglass', 'principled_to_omnipbr', 'principled_to_omniglass'"
            raise ValueError(f"Unknown shader type: {shader_type}. Supported types: {supported_types}")

    @classmethod
    def get_all_mappings(cls) -> Dict[str, Dict[str, Union[List, Dict]]]:
        """Get all available shader mappings.

        Returns:
            Dictionary with shader names as keys and their mappings as values.
        """
        return {
            "omnipbr": cls.get_omnipbr_mapping(),
            "omniglass": cls.get_omniglass_mapping(),
            "principled_to_omnipbr": cls.get_principled_to_omnipbr_mapping(),
            "principled_to_omniglass": cls.get_principled_to_omniglass_mapping(),
        }


def copy_dcc_attrs(source_prim: Usd.Prim, target_prim: Usd.Prim):
    """
    Copy omni:simready: attributes from source to target
    These are custom attributes that match PHYSX schema attr's.
    The CIP (Content Ingest Pipeline) can use these attrs in the PHYSX schema.
    """
    for attr in source_prim.GetAttributes():
        name = attr.GetName()
        type_name = attr.GetTypeName()

        # Avoid copying built-in attributes (like "extent", "points", etc.) if needed
        if name.startswith("usd:") or name.startswith("primvars:"):
            continue

        # Create same attribute on target
        new_attr = target_prim.CreateAttribute(name, type_name, custom=True)

        # Copy value (if authored)
        if attr.HasAuthoredValue():
            val = attr.Get()
            new_attr.Set(val)


def build_relationship_dict(is_logicial_hierarchy: bool = False) -> dict:
    """
    Builds a dictionary of parent-child relationships.
    If is_logicial_hierarchy is True, builds the tree from ReferencePrim collection, then adds Geometry objects under their ReferencePrim parents if they have one.
    If False, only uses Geometry collection constraints.
    """

    def normalize_geometry(geometry_name):
        return re.sub(r"\bgeometry\b", "Geometry", geometry_name, flags=re.IGNORECASE)

    result = defaultdict(list)

    if is_logicial_hierarchy:
        # Build tree from ReferencePrim collection
        ref_collection = bpy.data.collections.get("ReferencePrims")
        if ref_collection:
            for obj in ref_collection.all_objects:
                # Parent-child relationship
                if obj.parent:
                    result[obj.parent.name].append(obj.name)
                # Constraints
                for constraint in obj.constraints:
                    if constraint.type == "COPY_LOCATION" and constraint.target:
                        result[constraint.target.name].append(obj.name)
                    elif constraint.type == "CHILD_OF" and constraint.target:
                        result[constraint.target.name].append(obj.name)
        else:
            print("No collection found with name 'ReferencePrim'")

        # Now add Geometry objects under their ReferencePrim parents if they have one
        collection_name = "Geometry"
        geometry_collection = bpy.data.collections.get(normalize_geometry(collection_name))
        if geometry_collection:
            for obj in geometry_collection.all_objects:
                for constraint in obj.constraints:
                    if constraint.type == "COPY_LOCATION" and constraint.target:
                        result[constraint.target.name].append(obj.name)
                    elif constraint.type == "CHILD_OF" and constraint.target:
                        result[constraint.target.name].append(obj.name)
                else:
                    # If no ReferencePrim parent, treat as root (or skip, depending on needs)
                    pass
        else:
            print(f"No collection found with name '{collection_name}'")
    else:
        # Only use Geometry collection constraints
        collection_name = "Geometry"
        geometry_collection = bpy.data.collections.get(normalize_geometry(collection_name))
        if geometry_collection:
            for obj in geometry_collection.all_objects:
                for constraint in obj.constraints:
                    if constraint.type == "COPY_LOCATION" and constraint.target:
                        result[constraint.target.name].append(obj.name)
                    elif constraint.type == "CHILD_OF" and constraint.target:
                        result[constraint.target.name].append(obj.name)
        else:
            print(f"No collection found with name '{collection_name}'")

    return dict(result)


def define_collision_collection_geo():
    """
    Collect all geometry objects from the Collision collection into a list.
    Returns a list of collision geometry objects for storage later.
    """
    collider_objects = []
    collider_collection = bpy.data.collections.get("Colliders")
    if collider_collection:
        for obj in collider_collection.all_objects:
            collider_objects.append(obj.name)
        print(f"Collected {len(collider_objects)} objects from Colliders collection")
    else:
        print("No Colliders collection found")

    return collider_objects


def create_usd_collections_from_mapping(stage, mapping):
    for prim in stage.Traverse():
        name = prim.GetName()
        if name in mapping:
            collection_name = name
            target_obj_names = mapping[name]

            # Create the collection under the prim
            usd_collection = Usd.CollectionAPI.Apply(prim, collection_name)
            includes_rel = usd_collection.CreateIncludesRel()

            for target_name in target_obj_names:
                target_path = f"/RootNode/Geometry/{target_name}"
                includes_rel.AddTarget(target_path)
                print(f"Added '{target_path}' to collection '{collection_name}'")

            print(f"✅ Created collection '{collection_name}' on prim '{name}'")


def index_primvar(prim, primvar_name):
    """Pass Basic geometry checker validation"""

    # Check if prim is valid
    if not prim or not prim.IsValid():
        return

    # Only process mesh prims
    if not prim.IsA(UsdGeom.Mesh):
        return

    try:
        primvar = prim.GetPrimvar(primvar_name)
        if not primvar:
            print(f"Primvar {primvar_name} not found on {prim.GetPath()}")
            return

        if primvar.HasIndices():
            print(f"Primvar {primvar_name} is already indexed")
            return

        # Get full expanded data
        values = primvar.Get()
        if not values:
            print(f"No values found for {primvar_name}")
            return

        # Get full expanded data
        values = primvar.Get()
        if not values:
            print(f"⚠️ No values found for {primvar_name}")
            return

        # Build unique value list + indices map
        unique_values = []
        indices = []
        value_to_index = {}

        for v in values:
            # Convert Gf.Vec2f etc. to tuple for hashing
            key = tuple(v)
            if key not in value_to_index:
                value_to_index[key] = len(unique_values)
                unique_values.append(v)
            indices.append(value_to_index[key])

        # Write back indexed data
        primvar.Set(unique_values)
        primvar.SetIndices(indices)

        print(f"Indexed primvar {primvar_name} on {prim.GetPath()}: {len(unique_values)} unique values.")

    except Exception as e:
        print(f"Error processing primvar {primvar_name} on {prim.GetPath()}: {e}")
        return


def decompose_matrix(mat: Gf.Matrix4d) -> tuple[Gf.Vec3d, Gf.Vec3f, Gf.Vec3f]:
    # Extract translation (4th row, first 3 values)
    translation = Gf.Vec3d(mat[3][0], mat[3][1], mat[3][2])

    # Build 3x3 basis matrix
    basis = np.array(
        [
            [mat[0][0], mat[0][1], mat[0][2]],
            [mat[1][0], mat[1][1], mat[1][2]],
            [mat[2][0], mat[2][1], mat[2][2]],
        ]
    )

    # Compute scale factors
    sx = np.linalg.norm(basis[:, 0])
    sy = np.linalg.norm(basis[:, 1])
    sz = np.linalg.norm(basis[:, 2])
    scale = Gf.Vec3f(sx, sy, sz)

    # Normalize to get rotation matrix
    if sx:
        basis[:, 0] /= sx
    if sy:
        basis[:, 1] /= sy
    if sz:
        basis[:, 2] /= sz

    # Convert to Gf.Matrix3f
    rot = Gf.Matrix3f(
        basis[0, 0],
        basis[0, 1],
        basis[0, 2],
        basis[1, 0],
        basis[1, 1],
        basis[1, 2],
        basis[2, 0],
        basis[2, 1],
        basis[2, 2],
    )

    try:
        rot_euler = rot.ExtractEulerXYZ()
    except Exception:
        rot_euler = Gf.Vec3f(0, 0, 0)

    return translation, rot_euler, scale


def ensure_xformable_attributes(prim):
    """
    Ensures that a prim of type Xform has proper Xformable attributes and operations.
    If the prim doesn't have xformOpOrder, it adds basic transform operations.
    """
    if not prim.IsA(UsdGeom.Xform):
        return

    xformable = UsdGeom.Xformable(prim)

    # Check if xformOpOrder exists and has operations
    if not xformable.GetXformOpOrderAttr().HasValue():
        # Add basic transform operations if none exist
        xformable.ClearXformOpOrder()
        xformable.AddTranslateOp()
        xformable.AddRotateXYZOp()
        xformable.AddScaleOp()
        print(f"  ⮑ Added Xformable operations to '{prim.GetPath()}'")
    else:
        # Verify the operations are valid
        xform_ops = xformable.GetOrderedXformOps()
        if not xform_ops:
            # If xformOpOrder exists but no valid ops, clear and add defaults
            xformable.ClearXformOpOrder()
            xformable.AddTranslateOp()
            xformable.AddRotateXYZOp()
            xformable.AddScaleOp()
            print(f"  ⮑ Reset invalid Xformable operations on '{prim.GetPath()}'")


def move_prims_under_parents(stage, mapping):
    root_layer = stage.GetRootLayer()

    # 1. Process all prims according to the main mapping (move, no transform zeroing)
    for parent_name, child_names in mapping.items():
        parent_path = None
        # Find the full path to the parent prim
        for prim in stage.Traverse():
            if prim.GetName() == parent_name:
                parent_path = prim.GetPath()
                break
        if not parent_path:
            print(f"⚠️ Parent prim '{parent_name}' not found in stage.")
            continue
        for child_name in child_names:
            child_prim = None
            for prim in stage.Traverse():
                if prim.GetName() == child_name:
                    child_prim = prim
                    break
            if not child_prim:
                print(f"⚠️ Child prim '{child_name}' not found.")
                continue
            old_path = child_prim.GetPath()
            new_path = Sdf.Path(f"{parent_path}/{child_name}")

            # Copy the spec to new location
            Sdf.CopySpec(root_layer, old_path, root_layer, new_path)
            stage.RemovePrim(old_path)
            print(f"✅ Moved '{child_name}' under '{parent_name}'")

            # Ensure the moved prim has proper Xformable attributes if it's an Xform
            moved_prim = stage.GetPrimAtPath(new_path)  # noqa F841

    # 2. Find _joint prims that are siblings of _obj prims, and move _joint under _obj
    joint_move_mapping = {}
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Xform) and "_obj" in prim.GetName():
            parent_prim = prim.GetParent()
            if not parent_prim:
                continue
            # Find siblings
            for sibling in parent_prim.GetChildren():
                if sibling.GetName() != prim.GetName() and "_joint" in sibling.GetName():
                    print(f"  ⮑ Found _joint '{sibling.GetName()}' sibling to _obj '{prim.GetName()}' (post-move)")
                    joint_move_mapping[sibling.GetName()] = {
                        "original_path": sibling.GetPath(),
                        "target_path": Sdf.Path(f"{prim.GetPath()}/{sibling.GetName()}"),
                    }

    import json

    print("debug: joint_move_mapping:")
    print(json.dumps(joint_move_mapping, indent=2, default=str))

    # 3. Move _joint prims under their _obj sibling
    for joint_name, paths in joint_move_mapping.items():
        original_path = paths["original_path"]
        target_path = paths["target_path"]
        if original_path != target_path:

            Sdf.CopySpec(root_layer, original_path, root_layer, target_path)

            prim_orig = stage.GetPrimAtPath(original_path)
            prim_target = stage.GetPrimAtPath(target_path)

            world_transform_inverse = (
                UsdGeom.Xformable(prim_orig).ComputeLocalToWorldTransform(Usd.TimeCode.Default()).GetInverse()
            )
            local_transform = UsdGeom.Xformable(prim_target).ComputeParentToWorldTransform(Usd.TimeCode.Default())

            relative_matrix = world_transform_inverse * -local_transform

            translation, rotation, scale = decompose_matrix(relative_matrix)

            if translation != Gf.Vec3d(0, 0, 0):
                new_prim = stage.GetPrimAtPath(target_path)
                new_xform = UsdGeom.Xformable(new_prim)
                new_xform.ClearXformOpOrder()
                translate_op = new_xform.AddTranslateOp()
                rotate_op = new_xform.AddRotateXYZOp()
                scale_op = new_xform.AddScaleOp()

                translate_op.Set(translation)
                rotate_op.Set(rotation)
                scale_op.Set(scale)
                stage.RemovePrim(original_path)

            stage.RemovePrim(original_path)
            print(f"✅ Moved _joint '{joint_name}' under _obj at '{target_path}'")

            # Ensure the moved joint prim has proper Xformable attributes if it's an Xform
            moved_joint_prim = stage.GetPrimAtPath(target_path)  # noqa F841

        else:
            print(f"  ⮑ '{joint_name}' already at correct location '{target_path}'")

    # 4. Final pass - zero transforms on all appropriate prims
    print("\nZeroing transforms on appropriate prims...")

    all_prims = [prim for prim in stage.Traverse()]

    for prim in reversed(all_prims):
        if prim.IsA(UsdGeom.Xform) and "_obj" in prim.GetName():
            # Ensure the prim has proper Xformable attributes before zeroing
            ensure_xformable_attributes(prim)

            if prim.GetAttribute("xformOp:translate"):
                prim.GetAttribute("xformOp:translate").Set(Gf.Vec3d(0, 0, 0))

            print(f"  ⮑ Transforms zeroed on '{prim.GetPath()}'")


def move_colliders_to_matching_vis_meshes(stage: Usd.Stage, root_layer: Sdf.Layer) -> bool:
    """
    For multibody: move colliders under vis meshes that have the same joint constraints and return True.
    For unibody: break out of the function and return False.

    Args:
        stage (Usd.Stage): The USD stage
        root_layer (Sdf.Layer): The root layer

    Returns:
        bool: True if multibody; False if no collider or geometry found, or if unibody
    """
    colliders_collection = bpy.data.collections.get("Colliders")
    geometry_collection = bpy.data.collections.get("Geometry")

    if not colliders_collection or not geometry_collection:
        return False

    # Constraint-based matching
    moved_colliders = set()
    constraint_mapping = {}
    for collider_obj in colliders_collection.objects:
        for constraint in collider_obj.constraints:
            if constraint.type == "CHILD_OF" and hasattr(constraint, "target") and constraint.target:
                joint_target = constraint.target.name
                if joint_target not in constraint_mapping:
                    constraint_mapping[joint_target] = {"colliders": [], "vis_meshes": []}
                constraint_mapping[joint_target]["colliders"].append(collider_obj.name)
    for vis_obj in geometry_collection.objects:
        if "vis" in vis_obj.name.lower():
            for constraint in vis_obj.constraints:
                if constraint.type == "CHILD_OF" and hasattr(constraint, "target") and constraint.target:
                    joint_target = constraint.target.name
                    if joint_target not in constraint_mapping:
                        constraint_mapping[joint_target] = {"colliders": [], "vis_meshes": []}
                    constraint_mapping[joint_target]["vis_meshes"].append(vis_obj.name)

    # Unibody asset detected, skipping moving colliders
    if len(constraint_mapping) == 1 and len(list(constraint_mapping.values())[0]["vis_meshes"]) == 1:
        return False

    # Match and move colliders to their corresponding vis meshes
    for constraint_data in constraint_mapping.values():
        colliders = constraint_data["colliders"]
        vis_meshes = constraint_data["vis_meshes"]
        if not colliders or not vis_meshes:
            continue

        target_vis_mesh_name = vis_meshes[0]
        for collider_name in colliders:
            if collider_name in moved_colliders:
                continue

            # Find the collider prim in USD stage
            collider_prim = None
            for stage_prim in stage.Traverse():
                if stage_prim.GetName() == collider_name:
                    collider_prim = stage_prim
                    break
            if not collider_prim or not collider_prim.IsValid():
                continue

            # Find the vis mesh prim in USD stage
            target_vis_prim = None
            for stage_prim in stage.Traverse():
                if stage_prim.GetName() == target_vis_mesh_name:
                    target_vis_prim = stage_prim
                    break
            if not target_vis_prim or not target_vis_prim.IsValid():
                continue
            UsdPhysics.RigidBodyAPI.Apply(target_vis_prim)

            # Move collider under the vis mesh
            old_path = collider_prim.GetPath()
            new_path = target_vis_prim.GetPath().AppendChild(collider_name)
            Sdf.CopySpec(root_layer, old_path, root_layer, new_path)
            new_prim = stage.GetPrimAtPath(new_path)

            if new_prim and new_prim.IsA(UsdGeom.Xformable):
                xformable = UsdGeom.Xformable(new_prim)
                visibility_attr = xformable.CreateVisibilityAttr()
                if visibility_attr:
                    visibility_attr.Set(UsdGeom.Tokens.invisible)

            stage.RemovePrim(old_path)
            moved_colliders.add(collider_name)

    return len(constraint_mapping) > 0


def resolve_blender_path(relative_path):
    """
    Convert Blender's relative path to an absolute path.
    """
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


def find_node_by_name(material: bpy.types.Material, node_name: str):
    """
    Search through the material's node tree to find a node by name or label.

    Args:
        material: Blender material to search
        node_name: Name or label of the node to find

    Returns:
        The node if found, None otherwise
    """
    if not material.use_nodes or not material.node_tree:
        return None

    for node in material.node_tree.nodes:
        if node.name == node_name or node.label == node_name:
            return node

    return None


def get_node_output_value(node, output_name: str = None, output_index: int = 0):
    """
    Get the output value from a specific node.

    Args:
        node: The Blender node to extract value from
        output_name: Optional name of the output socket (if None, uses output_index)
        output_index: Index of the output socket (default: 0)

    Returns:
        The output value, or None if not found
    """
    if not node:
        return None

    try:
        if output_name:
            output = node.outputs.get(output_name)
        else:
            output = node.outputs[output_index]

        if output:
            # Get default_value if available
            if hasattr(output, "default_value"):
                value = output.default_value
                # Convert to list if it's a vector/color
                return list(value) if hasattr(value, "__len__") else value
    except (IndexError, KeyError):
        pass

    return None


def extract_average_color_from_texture(texture_path: str, sample_size: int = 100) -> tuple:
    """
    Extract the average color from a texture image.

    This function loads an image and calculates the average RGB color across
    all pixels (or a sampled subset for performance).

    Args:
        texture_path: Absolute path to the texture file
        sample_size: Maximum dimension to downsample to for performance (default: 100px)

    Returns:
        Tuple of (R, G, B) values in 0-1 range, or None if extraction fails
    """

    # TODO: This is a fallback function.  It's not used today, but keeping it for future use/reference.
    try:
        import bpy

        # Check if file exists
        if not os.path.exists(texture_path):
            print(f"    ⚠️ Texture file not found: {texture_path}")
            return None

        # Load the image into Blender if not already loaded
        image_name = os.path.basename(texture_path)  # noqa F841
        image = None

        # Check if image is already loaded - use safer path comparison
        for img in bpy.data.images:
            if img.filepath:
                try:
                    abs_img_path = bpy.path.abspath(img.filepath)
                    # Only use samefile if both paths exist
                    if os.path.exists(abs_img_path) and os.path.exists(texture_path):
                        if os.path.samefile(abs_img_path, texture_path):
                            image = img
                            break
                except (OSError, ValueError):
                    # Path comparison failed, skip this image
                    continue

        # If not loaded, load it temporarily
        temp_image = False
        if not image:
            try:
                image = bpy.data.images.load(texture_path)
                temp_image = True
            except Exception as e:
                print(f"    ⚠️ Could not load texture: {e}")
                return None

        # Get pixel data
        if not image.pixels or len(image.pixels) == 0:
            print("    ⚠️ Texture has no pixel data")
            if temp_image and image:
                bpy.data.images.remove(image)
            return None

        # Convert to numpy array for efficient processing
        width = image.size[0]
        height = image.size[1]
        channels = image.channels  # Usually 4 (RGBA) or 3 (RGB)

        # Get all pixels as numpy array
        pixels = np.array(image.pixels[:])
        pixels = pixels.reshape((height, width, channels))

        # Extract RGB channels (ignore alpha)
        rgb_pixels = pixels[:, :, :3]

        # Calculate average color
        avg_color = np.mean(rgb_pixels, axis=(0, 1))

        # Cleanup temporary image
        if temp_image and image:
            bpy.data.images.remove(image)

        return tuple(avg_color)

    except Exception as e:
        print(f"    ⚠️ Error extracting color from texture: {e}")
        import traceback

        traceback.print_exc()
        return None


def find_albedo_texture_in_material(material: bpy.types.Material) -> str:
    """
    Find the texture path from a node named or labeled "Albedo" in the material.

    Args:
        material: Blender material to search

    Returns:
        Absolute texture path if found, None otherwise
    """
    if not material.use_nodes or not material.node_tree:
        return None

    # Look for a texture node named or labeled "Albedo"
    for node in material.node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image:
            # Check both name and label
            if node.name == "Albedo" or node.label == "Albedo":
                raw_path = node.image.filepath
                resolved_path = bpy.path.abspath(raw_path) if raw_path.startswith("//") else raw_path
                return resolved_path

    return None


def extract_custom_nodes_data(material: bpy.types.Material) -> dict:
    """
    Extract data from custom/special nodes in the material graph.

    This function searches for specific named nodes that may be nested in the graph
    and extracts their values for use in material conversion.

    Args:
        material: Blender material to search

    Returns:
        Dictionary with custom node data
    """
    custom_data = {}

    if not material.use_nodes or not material.node_tree:
        return custom_data

    # List of special nodes to look for
    special_nodes = [
        "Albedo_Tint",
        "Albedo Tint",
        # Add more special node names here as needed
    ]

    for node_name in special_nodes:
        node = find_node_by_name(material, node_name)
        if node:
            # Store the node type and available data
            node_data = {"type": node.type, "bl_idname": node.bl_idname, "inputs": {}, "outputs": {}}

            # Extract all input values
            for i, input_socket in enumerate(node.inputs):
                if hasattr(input_socket, "default_value"):
                    value = input_socket.default_value
                    value = list(value) if hasattr(value, "__len__") else value
                    # Store by both name and index
                    node_data["inputs"][input_socket.name] = {"value": value, "index": i}
                    node_data["inputs"][i] = {"name": input_socket.name, "value": value}

            # Extract all output values
            for i, output in enumerate(node.outputs):
                if hasattr(output, "default_value"):
                    value = output.default_value
                    value = list(value) if hasattr(value, "__len__") else value
                    # Store by both name and index
                    node_data["outputs"][output.name] = {"value": value, "index": i}
                    node_data["outputs"][i] = {"name": output.name, "value": value}

            # Store by both the original name and a normalized key
            custom_data[node_name] = node_data
            normalized_key = node_name.replace(" ", "_").lower()
            if normalized_key != node_name:
                custom_data[normalized_key] = node_data

    # print(f"DEBUG: custom_data = {custom_data}")

    return custom_data


def find_texture_node_recursive(node, visited=None, max_depth=10):
    """
    Recursively traverse the node graph to find a TEX_IMAGE node.

    Blender node graphs can be deeply nested with mix nodes, math nodes, etc.
    between the shader input and the actual texture. This function walks
    backwards through the graph until it finds a texture node.

    Args:
        node: The starting node to search from
        visited: Set of already visited nodes (to prevent infinite loops)
        max_depth: Maximum recursion depth to prevent runaway searches

    Returns:
        The TEX_IMAGE node if found, None otherwise
    """
    if visited is None:
        visited = set()

    # Prevent infinite loops and excessive depth
    if node in visited or max_depth <= 0:
        return None

    visited.add(node)

    # Found a texture node!
    if node.type == "TEX_IMAGE" and node.image:
        return node

    # Search through all input sockets of this node
    for input_socket in node.inputs:
        if input_socket.is_linked:
            for link in input_socket.links:
                upstream_node = link.from_node
                result = find_texture_node_recursive(upstream_node, visited, max_depth - 1)
                if result:
                    return result

    return None


def collect_all_texture_info_from_node(start_node, visited=None, max_depth=10):
    """
    Collect information about all texture nodes connected upstream from a given node.

    This function traverses the entire node graph upstream from the start_node
    and collects information about every TEX_IMAGE node it finds.

    Args:
        start_node: The node to start searching from
        visited: Set of already visited nodes
        max_depth: Maximum recursion depth

    Returns:
        List of dicts containing texture information
    """
    if visited is None:
        visited = set()

    textures = []

    if start_node in visited or max_depth <= 0:
        return textures

    visited.add(start_node)

    # If this is a texture node, collect its info
    if start_node.type == "TEX_IMAGE" and start_node.image:
        raw_path = start_node.image.filepath
        resolved_path = bpy.path.abspath(raw_path) if raw_path.startswith("//") else raw_path
        textures.append(
            {
                "texture_path": resolved_path,
                "texture_path_raw": raw_path,
                "texture_name": start_node.image.name,
                "texture_colorspace": start_node.image.colorspace_settings.name,
                "projection_type": start_node.projection,
                "extension_type": start_node.extension,
                "node_name": start_node.name,
            }
        )

    # Continue searching upstream
    for input_socket in start_node.inputs:
        if input_socket.is_linked:
            for link in input_socket.links:
                upstream_textures = collect_all_texture_info_from_node(link.from_node, visited, max_depth - 1)
                textures.extend(upstream_textures)

    return textures


def get_material_attributes(material: bpy.types.Material) -> dict[str, any]:
    """
    Function to get all attributes of a Principled BSDF, OmniPBR Compute, OmniGlass Compute, or SimPBR node in the specified material.
    Returns a dictionary of attributes and connections.
    """

    if material.use_nodes:
        attributes: dict[str, any] = {"values": {}, "connections": {}, "custom_properties": {}}

        possible_inputs = []

        # determines the type of output node
        output_node = None

        # Parse the material to the end - collect all shader nodes
        # These collections determine type of shader
        collect_omnipbr = []
        collect_omniglass = []
        collect_principled = []
        collect_simpbr = []

        for node in material.node_tree.nodes:
            # we check for this, because if user has omni nodes in their material,
            # then we will build a OmniPBR material along with the usd preview.
            if node.label == "Principled BSDF" or node.name == "Principled BSDF":
                collect_principled.append(node)
            elif node.label == "OmniPBR Compute" or node.name == "OmniPBR Compute":
                collect_omnipbr.append(node)
            elif node.label == "OmniGlass Compute" or node.name == "OmniGlass Compute":
                collect_omniglass.append(node)
            elif node.label == "SimPBR" or node.name == "SimPBR":
                collect_simpbr.append(node)
            # Skip other node types - we only care about shader nodes

        # Check if we found any valid shader nodes
        if not (collect_principled or collect_omnipbr or collect_omniglass or collect_simpbr):
            print(
                "Your material is not exportable, need at least one of the following nodes: Principled BSDF, OmniPBR Compute, OmniGlass Compute, SimPBR"
            )
            return None, None

        # Determine which node to use as output_node
        if collect_principled and collect_omnipbr:
            # we collect [0] because generally there's only one of each node.
            # we check for principled and omnipbr because OMNI has both of these nodes in the graph.
            output_node = collect_omnipbr[0]
        elif collect_principled and collect_omniglass:
            output_node = collect_omniglass[0]
        elif collect_simpbr:
            # we only check for simpbr, because it only has this node in the graph.
            output_node = collect_simpbr[0]
        elif collect_principled:
            # only if there's no omnipbr or omniglass node, then use principled
            # this is the most likely case for simready.
            output_node = collect_principled[0]
        else:
            print("Could not determine output node from collected shader nodes")
            return None, None

        # Now process the selected output_node's inputs
        for input in output_node.inputs:
            if input.enabled:
                possible_inputs.append(input.name)

        for input_name in possible_inputs:
            socket = output_node.inputs.get(input_name)

            # Skip if socket doesn't exist (e.g., for extracted values like "Normal Map Strength")
            if socket is None:
                # Check if we already have a value for this (e.g., from Normal Map node extraction)
                if input_name not in attributes["values"]:
                    print(f"  DEBUG: Socket '{input_name}' not found on node '{output_node.name}', skipping")
                continue

            attributes["values"][input_name] = get_socket_value(socket)

            # Check linked nodes
            if socket.is_linked:
                from_node = socket.links[0].from_node
                connection_info = {"node_type": from_node.type, "node_name": from_node.name}

                # Special handling for Normal Map nodes - extract strength parameter
                if from_node.type == "NORMAL_MAP":
                    # Get the strength value from the Normal Map node
                    if hasattr(from_node.inputs["Strength"], "default_value"):
                        normal_strength = from_node.inputs["Strength"].default_value
                        attributes["values"]["Normal Map Strength"] = normal_strength
                        # Add to possible_inputs so it gets processed in the material conversion
                        if "Normal Map Strength" not in possible_inputs:
                            possible_inputs.append("Normal Map Strength")
                        # print(f"  DEBUG: Extracted Normal Map Strength = {normal_strength} from node '{from_node.name}'")

                # Try to find texture node - first check immediate connection
                texture_node = None
                mapping_node = None

                if from_node.type == "TEX_IMAGE" and from_node.image:
                    # Direct texture connection
                    texture_node = from_node
                else:
                    # Texture might be nested deeper in the graph - search recursively
                    texture_node = find_texture_node_recursive(from_node)

                # If we found a texture node, extract its properties
                if texture_node:
                    # Resolve Blender's relative paths (// prefix) to absolute paths
                    raw_path = texture_node.image.filepath
                    resolved_path = bpy.path.abspath(raw_path) if raw_path.startswith("//") else raw_path
                    texture_info = {
                        "texture_path": resolved_path,
                        "texture_path_raw": raw_path,  # Keep original for debugging
                        "texture_colorspace": texture_node.image.colorspace_settings.name,
                        "projection_type": texture_node.projection,
                        "extension_type": texture_node.extension,
                    }

                    # Check if texture was found through recursion
                    if texture_node != from_node:
                        texture_info["texture_node_name"] = texture_node.name
                        texture_info["is_nested"] = True

                    connection_info.update(texture_info)

                    # Now check for Mapping node connected to the texture node
                    # The Mapping node is typically connected to the Vector input of the texture
                    vector_input = texture_node.inputs.get("Vector")
                    if vector_input and vector_input.is_linked:
                        connected_node = vector_input.links[0].from_node
                        if connected_node.type == "MAPPING":
                            mapping_node = connected_node
                            # Extract Scale values (X, Y, Z) from the Mapping node
                            scale_input = mapping_node.inputs.get("Scale")
                            if scale_input:
                                scale_value = get_socket_value(scale_input)
                                if scale_value and len(scale_value) >= 2:
                                    connection_info["texture_scale"] = [scale_value[0], scale_value[1]]

                            # Extract Rotation Z from the Mapping node (radians -> degrees for MDL)
                            rotation_input = mapping_node.inputs.get("Rotation")
                            if rotation_input:
                                rotation_value = get_socket_value(rotation_input)
                                if rotation_value and len(rotation_value) >= 3:
                                    rot_z_deg = math.degrees(rotation_value[2])
                                    if abs(rot_z_deg) > 0.001:
                                        connection_info["texture_rotate"] = rot_z_deg

                            # Extract Location X, Y from the Mapping node (UV offset)
                            location_input = mapping_node.inputs.get("Location")
                            if location_input:
                                location_value = get_socket_value(location_input)
                                if location_value and len(location_value) >= 2:
                                    if abs(location_value[0]) > 0.0001 or abs(location_value[1]) > 0.0001:
                                        connection_info["texture_translate"] = [location_value[0], location_value[1]]

                attributes["connections"][input_name] = connection_info

        # Extract our reserved pipline nodes to 'custom properties'
        attributes["custom_properties"] = extract_custom_nodes_data(material)

    # import json
    # print(f"DEBUG: attributes = {json.dumps(attributes, indent=2, default=str)}")
    return attributes, possible_inputs


def cleanup_orphaned_materialx_nodes(stage):
    """
    Remove orphaned MaterialX nodes that have no real connections.

    Blender exports normal map nodes even when no normal texture is connected,
    which can cause MaterialX compilation failures. This function detects and
    removes these orphaned nodes.

    Specifically handles:
    - ND_normalmap_float nodes with no input connection (just default 0.5, 0.5, 1)
    """

    # Node types that should be removed if they have no input connections
    ORPHAN_CHECK_NODES = {
        "ND_normalmap_float": "in",  # shader_id: input_name to check for connection
    }

    nodes_to_remove = []
    connections_to_clear = []  # Track (shader_path, input_name) to disconnect

    # Find orphaned nodes
    for prim in stage.Traverse():
        if prim.GetTypeName() != "Shader":
            continue

        try:
            shader = UsdShade.Shader(prim)
            shader_path = prim.GetPath()

            shader_id_attr = shader.GetIdAttr()
            if not shader_id_attr:
                continue

            shader_id = str(shader_id_attr.Get())

            # Check if this is a node type we should check for orphans
            if shader_id not in ORPHAN_CHECK_NODES:
                continue

            input_to_check = ORPHAN_CHECK_NODES[shader_id]
            shader_input = shader.GetInput(input_to_check)

            if not shader_input:
                # No input attribute at all - this is definitely orphaned
                nodes_to_remove.append(shader_path)
                print(f"  ⮑ Found orphaned {shader_id} node (no '{input_to_check}' input): {shader_path}")
                continue

            # Check if the input has a connection
            if shader_input.HasConnectedSource():
                # Has a real connection - keep it
                continue

            # No connection - this is an orphaned node
            nodes_to_remove.append(shader_path)
            print(f"  ⮑ Found orphaned {shader_id} node ('{input_to_check}' has no connection): {shader_path}")

        except Exception as e:
            print(f"  ⚠️ Error checking node '{prim.GetPath()}': {e}")
            continue

    # Before removing nodes, find and clear any connections TO these nodes
    for orphan_path in nodes_to_remove:
        orphan_output_path = f"{orphan_path}.outputs:out"  # noqa F841

        # Search for shaders that connect to this orphaned node's output
        for prim in stage.Traverse():
            if prim.GetTypeName() != "Shader":
                continue

            try:
                shader = UsdShade.Shader(prim)

                # Check all inputs for connections to the orphaned node
                for shader_input in shader.GetInputs():
                    if not shader_input.HasConnectedSource():
                        continue

                    # Get the connection source
                    connected_source = shader_input.GetConnectedSource()
                    if connected_source and len(connected_source) >= 1:
                        source_shader = connected_source[0]
                        if source_shader:
                            source_path = source_shader.GetPath()
                            # Check if this connects to our orphaned node
                            if str(source_path).startswith(str(orphan_path)):
                                connections_to_clear.append((prim.GetPath(), shader_input.GetBaseName()))
                                print(
                                    f"  ⮑ Will clear connection: {prim.GetPath()}.inputs:{shader_input.GetBaseName()} -> {orphan_path}"
                                )

            except Exception:
                continue

    # Clear the connections first
    for shader_path, input_name in connections_to_clear:
        try:
            shader_prim = stage.GetPrimAtPath(shader_path)
            if shader_prim:
                shader = UsdShade.Shader(shader_prim)
                shader_input = shader.GetInput(input_name)
                if shader_input:
                    shader_input.ClearSources()
                    print(f"  ✅ Cleared connection on {shader_path}.inputs:{input_name}")
        except Exception as e:
            print(f"  ⚠️ Error clearing connection on {shader_path}: {e}")

    # Now remove the orphaned nodes
    for orphan_path in nodes_to_remove:
        try:
            # Also check if this node is inside a NodeGraph and remove the output on the NodeGraph
            parent_path = orphan_path.GetParentPath()
            parent_prim = stage.GetPrimAtPath(parent_path)

            if parent_prim and parent_prim.GetTypeName() == "NodeGraph":
                # Find and remove the NodeGraph output that connects to this orphaned node
                node_graph = UsdShade.NodeGraph(parent_prim)
                orphan_name = orphan_path.name

                # Look for outputs like "bnode_0_Normal_Map_out" that connect to this node
                for output in node_graph.GetOutputs():
                    output_name = output.GetBaseName()
                    if orphan_name in output_name:
                        # This output connects to our orphaned node - we need to remove it
                        # Unfortunately we can't easily remove outputs, but we can clear connections
                        output.ClearSources()
                        print(f"  ✅ Cleared NodeGraph output: {parent_path}.outputs:{output_name}")

            stage.RemovePrim(orphan_path)
            print(f"  ✅ Removed orphaned node: {orphan_path}")

        except Exception as e:
            print(f"  ❌ Error removing orphaned node '{orphan_path}': {e}")

    if nodes_to_remove:
        print(f"✅ Cleaned up {len(nodes_to_remove)} orphaned MaterialX node(s)")


def modify_materialx_shaders(stage):
    """
    Modify the MaterialX shaders in the stage:
    1. Clean up orphaned nodes (e.g., normal maps with no texture connection)
    2. Rename Blender's auto-generated 'bnode_*' shader prims to clearer names
    3. Future: Apply tinting and other modifications to match MDL settings

    Preview structure:
      /Materials/MyMaterial (Material)
      ├── Shader (UsdPreviewSurface)  -> outputs:surface (untouched)
      └── OmniPBR_Shader (OmniPBR.mdl)    -> outputs:mdl:surface
      └── OpenPBR_Shader (ND_open_pbr_surface)    -> outputs:mtlx:surface (renamed from bnode_*)
    """

    # First: Clean up orphaned nodes (must happen before renaming)
    cleanup_orphaned_materialx_nodes(stage)

    # MaterialX shader ID mappings to friendly names
    MTLX_SHADER_NAMES = {
        "ND_open_pbr_surface_surfaceshader": "OpenPBR_Shader",
        "ND_standard_surface_surfaceshader": "StandardSurface_Shader",
        "ND_gltf_pbr_surfaceshader": "glTF_PBR_Shader",
    }

    layer = stage.GetEditTarget().GetLayer()
    renamed_shaders = []  # Track (old_path, new_path, material_path) for connection updates

    # First pass: Find all MaterialX shaders that need renaming
    for prim in stage.Traverse():
        if prim.GetTypeName() != "Shader":
            continue

        try:
            shader = UsdShade.Shader(prim)
            shader_path = prim.GetPath()
            shader_name = shader_path.name

            # Check if this is a Blender-generated MaterialX shader (bnode_* pattern)
            if not shader_name.startswith("bnode_"):
                continue

            # Get the shader ID to determine what type of MaterialX shader this is
            shader_id_attr = shader.GetIdAttr()
            if not shader_id_attr:
                continue

            shader_id = shader_id_attr.Get()
            if not shader_id:
                continue

            # Check if this is a known MaterialX surface shader
            new_shader_name = MTLX_SHADER_NAMES.get(str(shader_id))
            if not new_shader_name:
                # Unknown MaterialX shader type - use generic name
                if "surfaceshader" in str(shader_id).lower():
                    new_shader_name = "MaterialX_Shader"
                else:
                    continue  # Not a surface shader, skip

            # Get the parent material path
            parent_path = shader_path.GetParentPath()
            new_shader_path = parent_path.AppendChild(new_shader_name)

            # Check if target path already exists
            if stage.GetPrimAtPath(new_shader_path):
                print(f"  ⮑ Target path '{new_shader_path}' already exists, skipping rename of '{shader_path}'")
                continue

            renamed_shaders.append((shader_path, new_shader_path, parent_path))
            print(f"  ⮑ Will rename MaterialX shader: '{shader_name}' -> '{new_shader_name}'")

        except Exception as e:
            print(f"  ⚠️ Error processing shader '{prim.GetPath()}': {e}")
            continue

    # Second pass: Perform the renames using Sdf.CopySpec
    for old_path, new_path, material_path in renamed_shaders:
        try:
            # Copy spec to new location (CopySpec remaps internal connections automatically)
            success = Sdf.CopySpec(layer, old_path, layer, new_path)

            if not success:
                print(f"  ❌ Failed to copy spec from '{old_path}' to '{new_path}'")
                continue

            # Update the material's mtlx:surface output connection
            material_prim = stage.GetPrimAtPath(material_path)
            if material_prim:
                material = UsdShade.Material(material_prim)
                mtlx_output = material.GetSurfaceOutput("mtlx")

                if mtlx_output:
                    # Create connection to new shader's surface output
                    new_shader = UsdShade.Shader.Get(stage, new_path)
                    if new_shader:
                        surface_output = new_shader.GetOutput("surface")
                        if surface_output:
                            mtlx_output.ConnectToSource(surface_output)
                            print(f"  ✅ Updated mtlx:surface connection to '{new_path}'")

            # Remove the old prim
            stage.RemovePrim(old_path)
            print(f"  ✅ Renamed MaterialX shader: '{old_path}' -> '{new_path}'")

        except Exception as e:
            print(f"  ❌ Error renaming shader '{old_path}': {e}")
            continue

    if renamed_shaders:
        print(f"✅ Renamed {len(renamed_shaders)} MaterialX shader(s)")

    # Then we need to have a mapping for material X from:
    # TODO:Principled BSDF -> Material X
    # TODO:OmniPBR Compute -> Material X
    # TODO:OmniGlass Compute -> Material X
    # TODO:SimPBR -> Material X
    # TODO:SimPBR_Translucent -> Material X


def copy_mdl_shaders_for_material(material_type, export_file_path, addon_path):
    """
    Copy MDL shader files and their dependencies to the materials directory next to the USD file.

    Args:
        material_type: The material type (e.g., "OmniPBR", "OmniGlass", "SimPBR", "SimPBR_Translucent")
        export_file_path: Path to the USD file being exported
        addon_path: Path to the addon directory

    Returns:
        str: Relative path to the main MDL file (e.g., "./materials/OmniPBR/OmniPBR.mdl")
    """
    import json

    if not export_file_path:
        # If no export path, use built-in shaders
        return f"{material_type}.mdl"

    # Load shader_includes.json to get dependencies
    shader_includes_path = os.path.join(addon_path, "resource", "shaders", "shader_includes.json")

    try:
        with open(shader_includes_path, "r") as f:
            shader_config = json.load(f)
    except Exception as e:
        print(f"  ⚠️ Could not load shader_includes.json: {e}")
        return f"{material_type}.mdl"

    # Get the list of MDL files needed for this material type
    mdl_files = shader_config.get("shader_includes", {}).get(material_type, [])

    if not mdl_files:
        print(f"  ⚠️ No shader includes found for material type '{material_type}'")
        return f"{material_type}.mdl"

    # Ensure mdl_files is a list
    if isinstance(mdl_files, str):
        mdl_files = [mdl_files]

    # Create materials directory next to USD file
    usd_dir = os.path.dirname(export_file_path)
    materials_dir = os.path.join(usd_dir, "materials")
    os.makedirs(materials_dir, exist_ok=True)

    # Source shaders directory
    shaders_source_dir = os.path.join(addon_path, "resource", "shaders")

    # Copy all MDL files for this material
    main_mdl_relative_path = None

    for mdl_file_path in mdl_files:
        # Source file path
        source_file = os.path.join(shaders_source_dir, mdl_file_path)

        # Destination file path (preserve subdirectory structure)
        dest_file = os.path.join(materials_dir, mdl_file_path)

        # Create subdirectories if needed
        dest_dir = os.path.dirname(dest_file)
        os.makedirs(dest_dir, exist_ok=True)

        # Copy the file
        try:
            shutil.copy2(source_file, dest_file)
            print(f"  📄 Copied MDL: {mdl_file_path}")

            # The first file in the list is the main shader
            if main_mdl_relative_path is None:
                main_mdl_relative_path = f"./materials/{mdl_file_path}"
        except Exception as e:
            print(f"  ⚠️ Error copying {mdl_file_path}: {e}")

    return main_mdl_relative_path if main_mdl_relative_path else f"{material_type}.mdl"


def append_neutral_materials(stage, export_file_path=None):
    """
    Traverse the stage and create NEW MDL or MATX shaders alongside existing UsdPreviewSurface shaders.
    Uses Blender material attributes (via get_material_attributes) to populate the MDL shader.
    Leaves UsdPreviewSurface untouched - both shaders live in the same Material.

    Result structure:
      /Materials/MyMaterial (Material)
      ├── Shader (UsdPreviewSurface)  -> outputs:surface (untouched)
      └── MDL_Shader (OmniPBR.mdl)    -> outputs:mdl:surface (default)
    """

    import traceback

    # Get addon path for shader resources
    addon_path = os.path.dirname(os.path.dirname(__file__))  # Go up from ui/ to addon/

    # MDL shader paths (will be updated per-material with copy_mdl_shaders_for_material)
    mdl_omnipbr_path = "OmniPBR.mdl"  # noqa F841
    mdl_omniglass_path = "OmniGlass.mdl"  # noqa F841
    simpbr_mdl_path = (  # noqa F841
        "SimPBR.mdl"  # SimPBR.mdl exists in kit runtime, but we might pass custom simpbr shaders.
    )
    simpbr_translucent_mdl_path = "SimPBR_Translucent.mdl"  # noqa F841

    # Matx config numbers
    mtlx_config = (  # noqa F841
        "1.39"  # 1.38 has no concept of OpenPBR, runtime needs to raise warning if it only has 1.38 definitions.
    )

    # Helper functions
    def color_to_vec3f(color_value):
        return Gf.Vec3f(float(color_value[0]), float(color_value[1]), float(color_value[2]))

    def linear_to_srgb(linear_value):
        """Convert a linear color value to sRGB.

        Blender stores colors in linear space internally, but USD/MDL often expects sRGB.
        This applies the standard sRGB gamma curve.

        Args:
            linear_value: Single float channel value in linear space (0.0-1.0)

        Returns:
            Float value in sRGB space (0.0-1.0)
        """
        if linear_value <= 0.0031308:
            return 12.92 * linear_value
        else:
            return 1.055 * (linear_value ** (1.0 / 2.4)) - 0.055

    def linear_color_to_srgb(linear_color):
        """Convert a linear RGB color to sRGB.

        Args:
            linear_color: Tuple/list of (R, G, B) or (R, G, B, A) in linear space

        Returns:
            Tuple of (R, G, B) in sRGB space
        """
        return (linear_to_srgb(linear_color[0]), linear_to_srgb(linear_color[1]), linear_to_srgb(linear_color[2]))

    def blender_to_kit_color(color_space):
        return "raw" if color_space == "Non-Color" else "sRGB"

    for prim in stage.Traverse():
        if prim.GetTypeName() != "Material":
            continue

        try:
            material = UsdShade.Material(prim)
            material_path = prim.GetPath()
            material_name = material_path.name

            try:
                mdl_output = material.GetSurfaceOutput("mdl")
                if mdl_output and mdl_output.HasConnectedSource():
                    print(f"  ⮑ Material '{material_path}' already has MDL shader, skipping")
                    continue
            except Exception as e:
                print(f"  ⮑ Error getting MDL output for '{material_path}': {e}")
                pass

            blender_mat = bpy.data.materials.get(material_name)
            if not blender_mat:
                print(f"  ⮑ No Blender material found for '{material_name}'")
                continue

            material_type = None
            is_principled = False  # noqa F841

            if blender_mat.use_nodes:
                collect_omniglass = []
                collect_omnipbr = []
                collect_simpbr = []
                collect_principled = []

                for node in blender_mat.node_tree.nodes:
                    if node.label == "OmniGlass Compute" or node.name == "OmniGlass Compute":
                        collect_omniglass.append(node)
                    elif node.label == "OmniPBR Compute" or node.name == "OmniPBR Compute":
                        collect_omnipbr.append(node)
                    elif node.label == "SimPBR" or node.name == "SimPBR":
                        collect_simpbr.append(node)
                    elif node.label == "Principled BSDF" or node.name == "Principled BSDF":
                        collect_principled.append(node)

                if collect_principled and collect_omnipbr:
                    material_type = "OmniPBR"
                elif collect_omniglass and collect_principled:
                    material_type = "OmniGlass"
                elif collect_simpbr:
                    material_type = "SimPBR"
                else:
                    material_type = "Principled"

            attrs, possible_inputs = get_material_attributes(blender_mat)

            if not attrs:
                print(f"  ⮑ No shader attributes found for '{material_name}'")
                continue

            # Check for "Invert Green" node to determine if we need to flip tangent U
            has_invert_green_node = False
            if blender_mat.use_nodes and blender_mat.node_tree:
                for node in blender_mat.node_tree.nodes:
                    if node.name == "Invert Green" or node.label == "Invert Green":
                        has_invert_green_node = True
                        print(
                            f"  ⮑ Found 'Invert Green' node in material '{material_name}' - will set flip_tangent_u=True"
                        )
                        break

            # print(f"DEBUG: material_type = {material_type}")

            # If omnipbr, we need to create a new OmniPBR.mdl
            # If omnglass, we need to create a new OmniGlass.mdl
            # If simpbr, we need to create a new SimPBR.mdl
            # If simpbr_translucent, we need to create a new SimPBR_Translucent.mdl
            # If principled, we need to create a new omnipbr.mdl or omnglass.mdl depending on the attrs in the  node.

            # now you know the type of material, we can get paths to the shaders

            # Get the appropriate attribute mapping based on material type
            # Copy MDL shaders to materials directory and get relative path
            if material_type == "OmniPBR":
                mdl_path = copy_mdl_shaders_for_material("OmniPBR", export_file_path, addon_path)
                attr_map = BlenderMaterialMapping.get_omnipbr_mapping()
            elif material_type == "OmniGlass":
                mdl_path = copy_mdl_shaders_for_material("OmniGlass", export_file_path, addon_path)
                attr_map = BlenderMaterialMapping.get_omniglass_mapping()
            elif material_type == "SimPBR":
                mdl_path = copy_mdl_shaders_for_material("SimPBR", export_file_path, addon_path)
                # TODO: Implement simpbr mapping.
                # attr_map = BlenderMaterialMapping.get_simpbr_mapping()
            elif material_type == "SimPBR_Translucent":
                mdl_path = copy_mdl_shaders_for_material("SimPBR_Translucent", export_file_path, addon_path)
                # TODO: Implement simpbr_translucent mapping.
                # attr_map = BlenderMaterialMapping.get_simpbr_translucent_mapping()
            elif material_type == "Principled":
                # For Principled BSDF, check Alpha value to determine if it's a glass material
                # If Alpha < 1.0, treat as glass material and use OmniGlass mapping
                # TODO: dunno how we're gonna deal with OmniSurface glass or MaterialX glass.
                alpha_value = attrs.get("values", {}).get("Alpha", 1.0)

                if isinstance(alpha_value, (list, tuple)):
                    # Handle RGBA or multi-component values
                    alpha_value = alpha_value[0] if len(alpha_value) > 0 else 1.0

                if alpha_value < 1.0:
                    print(f"  ⮑ Principled BSDF has Alpha={alpha_value:.3f} < 1.0, using OmniGlass mapping")
                    mdl_path = copy_mdl_shaders_for_material("OmniGlass", export_file_path, addon_path)
                    material_type = "OmniGlass"
                    attr_map = BlenderMaterialMapping.get_principled_to_omniglass_mapping()
                else:
                    mdl_path = copy_mdl_shaders_for_material("OmniPBR", export_file_path, addon_path)
                    material_type = "OmniPBR"
                    attr_map = BlenderMaterialMapping.get_principled_to_omnipbr_mapping()
            else:
                # Unknown material type - skip processing this material
                # TODO: should we raise?  Undecided.
                print(f"  ⚠️ Unknown material type '{material_type}', skipping material conversion")
                continue

            print(f"✅ Creating {material_type} MDL shader for: {material_path}")
            # print(f"  DEBUG: possible_inputs = {possible_inputs}")
            # print(f"  DEBUG: attrs keys = {attrs.keys() if attrs else 'None'}")
            if attrs:
                # print(f"  DEBUG: values keys = {list(attrs.get('values', {}).keys())[:10]}...")  # First 10
                # print(f"  DEBUG: connections keys = {list(attrs.get('connections', {}).keys())}")
                custom_props = attrs.get("custom_properties", {})
                # if custom_props:
                #     print(f"  DEBUG: custom_properties found = {list(custom_props.keys())}")

            # Create new MDL shader prim
            mdl_shader_prim_path = f"{material_path}/{material_type}_Shader"
            mdl_shader = UsdShade.Shader.Define(stage, mdl_shader_prim_path)

            # Set MDL shader source
            print(f"  📂 Setting MDL source asset path: {mdl_path}")
            mdl_shader.CreateIdAttr(f"mdl:{material_type}")
            mdl_shader.SetSourceAsset(Sdf.AssetPath(mdl_path), "mdl")
            mdl_shader.SetSourceAssetSubIdentifier(material_type, "mdl")

            # Get the shader prim for setting attributes
            shader_prim = stage.GetPrimAtPath(mdl_shader_prim_path)  # noqa F841

            # Process attributes
            values = attrs.get("values", {})
            connections = attrs.get("connections", {})

            use_flags = {}
            for input_name, val in values.items():
                if input_name.lower().startswith("use_") or input_name.lower().startswith("enable_"):
                    # Convert to bool (Blender stores as int 0/1)
                    use_flags[input_name] = bool(int(val)) if isinstance(val, (int, float)) else bool(val)

            mapped_count = 0
            skipped_inputs = []

            # Track UV transform values from Mapping nodes
            # We'll use the first one encountered (typically from the main albedo/diffuse texture)
            global_texture_scale = None
            global_texture_rotate = None
            global_texture_translate = None

            # Pre-scan for ORM textures - these need special handling
            orm_texture_found = False
            orm_texture_path = None
            for input_name in possible_inputs:
                if input_name in connections:
                    tex_info = connections[input_name]
                    texture_path = tex_info.get("texture_path", "")
                    if texture_path:
                        # Check if this is an ORM texture (case-insensitive)
                        texture_lower = texture_path.lower()
                        if texture_lower.endswith("_orm.png") or "_orm." in texture_lower:
                            orm_texture_found = True
                            orm_texture_path = texture_path
                            print(f"  🎨 Detected ORM texture: {texture_path}")
                            break

            # If ORM texture is found, map it to ORM_texture input
            if orm_texture_found and orm_texture_path:
                try:
                    abs_tex_path = resolve_blender_path(orm_texture_path)
                    if export_file_path:
                        parent_dir = os.path.dirname(export_file_path)
                        textures_dir = os.path.join(parent_dir, "textures")
                        if os.path.exists(textures_dir):
                            file_name = os.path.basename(abs_tex_path)
                            rel_tex_path = f"./textures/{file_name}"
                        else:
                            rel_tex_path = abs_tex_path
                    else:
                        rel_tex_path = abs_tex_path

                    mdl_shader.CreateInput("ORM_texture", Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath(rel_tex_path))
                    print(f"  ⮑ Mapped ORM texture to inputs:ORM_texture: {rel_tex_path}")
                    mapped_count += 1

                    orm_texture_attr = mdl_shader.GetInput("ORM_texture").GetAttr()
                    orm_texture_attr.SetColorSpace("raw")
                    mapped_count += 1

                    # Set required ORM parameters
                    # When using ORM texture, disable individual texture influences since R/M channels come from ORM
                    mdl_shader.CreateInput("enable_ORM_texture", Sdf.ValueTypeNames.Bool).Set(True)
                    mdl_shader.CreateInput("reflection_roughness_texture_influence", Sdf.ValueTypeNames.Float).Set(1.0)
                    mdl_shader.CreateInput("metallic_texture_influence", Sdf.ValueTypeNames.Float).Set(1.0)
                    print("  ⮑ Set ORM parameters: enable_ORM_texture=True, texture_influences=1.0")
                    mapped_count += 3
                except Exception as e:
                    print(f"    ⚠️ Could not set ORM_texture: {e}")

            for input_name in possible_inputs:
                if input_name not in attr_map:
                    skipped_inputs.append(input_name)
                    continue

                attr_info = attr_map[input_name]

                # Handle special case for Albedo Map and similar texture/color pairs
                if isinstance(attr_info, dict):
                    # Check for corresponding "use_" flag or connection
                    # e.g., "Albedo Map" might have "Use Albedo Map" or "use_albedo_texture" flag
                    use_texture = False

                    # First check if there's a texture connection
                    if input_name in connections:
                        use_texture = True

                    # Also check for explicit use_ flags
                    for flag_name, flag_val in use_flags.items():
                        # Match patterns like "Use Albedo Map", "use_diffuse_texture", etc.
                        flag_lower = flag_name.lower().replace(" ", "_")
                        input_lower = input_name.lower().replace(" ", "_")
                        if (
                            input_lower in flag_lower
                            or flag_lower.replace("use_", "").replace("enable_", "") in input_lower
                        ):
                            use_texture = flag_val
                            break

                    if use_texture and "texture" in attr_info:
                        attr_info = attr_info["texture"]
                    elif "color" in attr_info:
                        attr_info = attr_info["color"]
                    else:
                        continue

                if not isinstance(attr_info, list):
                    continue

                usd_attr_name, input_type = attr_info

                try:
                    # DEBUG: Show what we're processing
                    # print(f"    DEBUG: Processing input '{input_name}' -> usd_attr='{usd_attr_name}', type='{input_type}', in_connections={input_name in connections}")

                    # Skip roughness and metallic textures if ORM texture is being used
                    if orm_texture_found and usd_attr_name in ["reflectionroughness_texture", "metallic_texture"]:
                        print(f"  ⮑ Skipping {usd_attr_name} (using ORM texture instead)")
                        continue

                    if input_type == "texture" and input_name in connections:
                        # Handle texture
                        tex_info = connections[input_name]
                        texture_path = tex_info.get("texture_path", "")
                        # print(f"    DEBUG: Found texture connection for '{input_name}': {texture_path}")
                        if texture_path:
                            # Resolve texture path
                            abs_tex_path = resolve_blender_path(texture_path)
                            if export_file_path:
                                parent_dir = os.path.dirname(export_file_path)
                                textures_dir = os.path.join(parent_dir, "textures")
                                if os.path.exists(textures_dir):
                                    file_name = os.path.basename(abs_tex_path)
                                    rel_tex_path = f"./textures/{file_name}"
                                else:
                                    rel_tex_path = abs_tex_path
                            else:
                                rel_tex_path = abs_tex_path

                            # Create the texture input
                            mdl_shader.CreateInput(usd_attr_name, Sdf.ValueTypeNames.Asset)
                            texture_attr = mdl_shader.GetInput(usd_attr_name).GetAttr()
                            texture_attr.Set(Sdf.AssetPath(rel_tex_path))

                            # Determine colorspace for this texture
                            # OmniGlass materials need ALL textures flagged as "raw" to prevent linearization
                            # because the shader handles color space internally
                            if material_type == "OmniGlass":
                                colorspace = "raw"
                                print(f"  ⮑ Setting {usd_attr_name} colorspace to 'raw' (OmniGlass material)")
                            # If artists are using custom properties (like Albedo_Tint),
                            # AND this is an albedo/diffuse texture, force colorspace to "raw"
                            # because the tint is applied in linear space
                            elif usd_attr_name in ["diffuse_texture", "diffuse_color_texture"] and bool(custom_props):
                                # Custom workflow detected - use raw colorspace
                                # The artist is doing color corrections in linear space
                                colorspace = "raw"
                                print(f"  ⮑ Setting {usd_attr_name} colorspace to 'raw' (custom properties detected)")
                            else:
                                # Standard workflow - use Blender's colorspace setting
                                blender_colorspace = tex_info.get("texture_colorspace", "sRGB")
                                colorspace = blender_to_kit_color(blender_colorspace)

                            # Set the colorspace metadata on the texture attribute
                            texture_attr.SetColorSpace(colorspace)
                            mapped_count += 1

                            # Check if this texture has UV transform values from a Mapping node
                            texture_scale = tex_info.get("texture_scale")
                            if texture_scale and len(texture_scale) >= 2:
                                if global_texture_scale is None:
                                    global_texture_scale = texture_scale
                                    print(
                                        f"  ⮑ Found texture_scale from Mapping node for '{input_name}': ({texture_scale[0]}, {texture_scale[1]})"
                                    )

                            texture_rotate = tex_info.get("texture_rotate")
                            if texture_rotate is not None:
                                if global_texture_rotate is None:
                                    global_texture_rotate = texture_rotate
                                    print(
                                        f"  ⮑ Found texture_rotate from Mapping node for '{input_name}': {texture_rotate:.2f}°"
                                    )

                            texture_translate = tex_info.get("texture_translate")
                            if texture_translate and len(texture_translate) >= 2:
                                if global_texture_translate is None:
                                    global_texture_translate = texture_translate
                                    print(
                                        f"  ⮑ Found texture_translate from Mapping node for '{input_name}': ({texture_translate[0]}, {texture_translate[1]})"
                                    )
                    elif input_name in values:
                        o_value = values[input_name]

                        if input_type == "float":
                            float_val = float(o_value)

                            # Scale down bump_factor by 10x (Blender normals are 10x stronger than OmniPBR)
                            # if usd_attr_name == "bump_factor":
                            #     float_val = float_val * 0.1
                            #     print(f"  ⮑ Scaled bump_factor from {float(o_value):.2f} to {float_val:.2f} (Blender->OmniPBR adjustment)")

                            mdl_shader.CreateInput(usd_attr_name, Sdf.ValueTypeNames.Float).Set(float_val)
                            mapped_count += 1
                        elif input_type == "int":
                            mdl_shader.CreateInput(usd_attr_name, Sdf.ValueTypeNames.Int).Set(int(o_value))
                            mapped_count += 1
                        elif input_type == "bool":
                            # Blender uses int (0/1) for booleans in material nodes
                            # Convert to actual bool - handles int, float, or bool input
                            if isinstance(o_value, (int, float)):
                                bool_val = bool(int(o_value))
                            else:
                                bool_val = bool(o_value)
                            mdl_shader.CreateInput(usd_attr_name, Sdf.ValueTypeNames.Bool).Set(bool_val)
                            mapped_count += 1
                        elif input_type == "color":
                            # Set color value directly
                            color_value = o_value
                            mdl_shader.CreateInput(usd_attr_name, Sdf.ValueTypeNames.Color3f).Set(
                                color_to_vec3f(color_value)
                            )
                            mapped_count += 1
                        elif input_type == "float2":
                            if hasattr(o_value, "__len__") and len(o_value) >= 2:
                                mdl_shader.CreateInput(usd_attr_name, Sdf.ValueTypeNames.Float2).Set(
                                    Gf.Vec2f(o_value[0], o_value[1])
                                )
                            mapped_count += 1
                except Exception as e:
                    print(f"    ⚠️ Could not set {usd_attr_name}: {e}")

            # Process custom properties (e.g., Albedo_Tint node)
            # TODO: eventually i imagine there'll be more.
            custom_props = attrs.get("custom_properties", {})
            if custom_props and not material_type == "OmniGlass":
                # Mapping: node_key -> (mdl_param, param_type, socket_type, socket_name_or_index)
                # socket_type can be 'input' or 'output'
                # socket_name_or_index can be string name or integer index
                custom_node_mappings = {
                    # TODO: I'm not sure how to scale this... this is so custom to what light speed wants.
                    # TODO: I guess it will just fail silently if the node is not found, then user can manually re add it.
                    # Albedo_Tint is a Mix node (ShaderNodeMix) with multiple typed inputs:
                    # Index 6: 'A' (Color) - [0.5, 0.5, 0.5, 1.0]
                    # Index 7: 'B' (Color) - [1.0, 0.044, 0.046, 1.0] <- This is the tint color we want!
                    "Albedo_Tint": ("diffuse_tint", "color", "input", 7),
                    "albedo_tint": ("diffuse_tint", "color", "input", 7),
                }

                for node_key, (
                    mdl_param,
                    param_type,
                    socket_type,
                    socket_name_or_index,
                ) in custom_node_mappings.items():
                    if node_key in custom_props:
                        node_data = custom_props[node_key]

                        # Get the appropriate socket collection (inputs or outputs)
                        sockets = node_data.get(socket_type + "s", {})  # 'inputs' or 'outputs'

                        # Try to get the socket value by name or index
                        socket_data = sockets.get(socket_name_or_index)

                        if socket_data:
                            # Extract value from the socket data structure
                            value = socket_data.get("value") if isinstance(socket_data, dict) else socket_data

                            if value is not None:
                                try:
                                    if param_type == "color":
                                        # Special case: diffuse_tint needs linear-to-sRGB conversion
                                        # because the albedo texture is set to "raw" colorspace
                                        if mdl_param == "diffuse_tint":
                                            # Convert from Blender's linear color space to sRGB
                                            srgb_color = linear_color_to_srgb(value)
                                            mdl_shader.CreateInput(mdl_param, Sdf.ValueTypeNames.Color3f).Set(
                                                color_to_vec3f(srgb_color)
                                            )
                                            print(
                                                f"  ⮑ Set {mdl_param} from custom node '{node_key}' {socket_type}[{socket_name_or_index}]:"
                                            )
                                            print(
                                                f"      Linear: ({value[0]:.6f}, {value[1]:.6f}, {value[2]:.6f}) → sRGB: ({srgb_color[0]:.3f}, {srgb_color[1]:.3f}, {srgb_color[2]:.3f})"
                                            )
                                        else:
                                            # Other colors: use as-is (already in linear space, which is fine for USD)
                                            mdl_shader.CreateInput(mdl_param, Sdf.ValueTypeNames.Color3f).Set(
                                                color_to_vec3f(value)
                                            )
                                            print(
                                                f"  ⮑ Set {mdl_param} from custom node '{node_key}' {socket_type}[{socket_name_or_index}]: {value}"
                                            )
                                        mapped_count += 1
                                    elif param_type == "float":
                                        mdl_shader.CreateInput(mdl_param, Sdf.ValueTypeNames.Float).Set(float(value))
                                        print(
                                            f"  ⮑ Set {mdl_param} from custom node '{node_key}' {socket_type}[{socket_name_or_index}]: {value}"
                                        )
                                        mapped_count += 1
                                    elif param_type == "bool":
                                        bool_val = bool(int(value)) if isinstance(value, (int, float)) else bool(value)
                                        mdl_shader.CreateInput(mdl_param, Sdf.ValueTypeNames.Bool).Set(bool_val)
                                        print(
                                            f"  ⮑ Set {mdl_param} from custom node '{node_key}' {socket_type}[{socket_name_or_index}]: {bool_val}"
                                        )
                                        mapped_count += 1
                                except Exception as e:
                                    print(f"    ⚠️ Could not set {mdl_param} from custom node '{node_key}': {e}")
                        break  # TODO: how should we handle multiple nodes named the same.... not sure.

            # Apply material-type-specific defaults
            # TODO: I hate this, but depending on the material type used in blender, there could be zero correlation to this.
            # Setting at .01 just makes it default clear glass.... maybe i can latch onto the nonvisual sensor
            if material_type == "OmniGlass":
                # OmniGlass default: set frosting roughness to 0.01 for subtle frosting effect
                mdl_shader.CreateInput("frosting_roughness", Sdf.ValueTypeNames.Float).Set(0.01)
                print("  ⮑ Set OmniGlass default: frosting_roughness = 0.01")

            # Apply normal map flip settings based on "Invert Green" node detection
            if has_invert_green_node:
                mdl_shader.CreateInput("flip_tangent_u", Sdf.ValueTypeNames.Bool).Set(False)
                mdl_shader.CreateInput("flip_tangent_v", Sdf.ValueTypeNames.Bool).Set(True)
                print("  ⮑ Set normal map flip: flip_tangent_u=False, flip_tangent_v=True (Invert Green detected)")
                mapped_count += 2
            else:
                # Set defaults even if no Invert Green node
                print("  ⮑ Normal map default detected...")
                mdl_shader.CreateInput("flip_tangent_u", Sdf.ValueTypeNames.Bool).Set(False)
                mdl_shader.CreateInput("flip_tangent_v", Sdf.ValueTypeNames.Bool).Set(False)
                print("  ⮑ Set normal map default: flip_tangent_u=False")
                print("  ⮑ Set normal map default: flip_tangent_v=False")
                mapped_count += 2

            # Apply global UV transform values if found from Mapping nodes
            if global_texture_scale is not None:
                mdl_shader.CreateInput("texture_scale", Sdf.ValueTypeNames.Float2).Set(
                    Gf.Vec2f(global_texture_scale[0], global_texture_scale[1])
                )
                print(f"  ⮑ Set texture_scale: ({global_texture_scale[0]}, {global_texture_scale[1]})")
                mapped_count += 1

            if global_texture_rotate is not None:
                mdl_shader.CreateInput("texture_rotate", Sdf.ValueTypeNames.Float).Set(float(global_texture_rotate))
                print(f"  ⮑ Set texture_rotate: {global_texture_rotate:.2f}°")
                mapped_count += 1

            if global_texture_translate is not None:
                mdl_shader.CreateInput("texture_translate", Sdf.ValueTypeNames.Float2).Set(
                    Gf.Vec2f(global_texture_translate[0], global_texture_translate[1])
                )
                print(f"  ⮑ Set texture_translate: ({global_texture_translate[0]}, {global_texture_translate[1]})")
                mapped_count += 1

            # Create shader output and connect to material's MDL surface
            mdl_shader_output = mdl_shader.CreateOutput("out", Sdf.ValueTypeNames.Token)
            mdl_surface_output = material.CreateSurfaceOutput("mdl")
            mdl_surface_output.ConnectToSource(mdl_shader_output)

            print(f"  ⮑ Created MDL shader at {mdl_shader_prim_path}")
            print(f"  ⮑ Mapped {mapped_count} attributes from Blender material")
            # if skipped_inputs:
            #     print(f"  DEBUG: Skipped inputs (not in attr_map): {skipped_inputs}")

        except Exception as e:
            print(f"❌ Error processing material '{prim.GetPath()}': {e}")
            traceback.print_exc()
            continue

    print("🔍 Finished MDL shader creation for materials.")


def convert_attr_type(attr, attr_type=Sdf.ValueTypeNames.Token, split_value=False):
    v = attr.Get()
    attr_name = attr.GetName()
    prim = attr.GetPrim()
    prim.RemoveProperty(attr_name)

    if split_value is True:
        print(f"original v: {v}")
        # Split on comma and strip whitespace from each token
        v = [token.strip() for token in v.split(",") if token.strip()]
        print(f"new v: {v}")

    a = prim.CreateAttribute(attr_name, attr_type)
    a.Set(v)

    return a


def convert_string_to_token_attr(string_attr, array=False):
    print(f"string_attr: {string_attr}")
    v = string_attr.Get()
    print(f"vstring attr name: {v}")
    print(f"type of v: {type(v)}")
    attr_name = string_attr.GetName()
    print(f"attr_name: {attr_name}")
    prim = string_attr.GetPrim()
    print(f"prim: {prim}")
    prim.RemoveProperty(attr_name)

    if array is True:
        a = prim.CreateAttribute(attr_name, Sdf.ValueTypeNames.TokenArray)
        # Check if v is already a list/token array
        if isinstance(v, list):
            # If it's already a list, use it directly
            a.Set(v)
        elif not isinstance(v, str):
            # If it's not a string, convert to string then split
            v_arr = str(v)
            a.Set(v_arr)
        else:
            # If it's a string, split it
            a.Set(v)
    else:
        a = prim.CreateAttribute(attr_name, Sdf.ValueTypeNames.Token)
        a.Set(v)

    return a


# def validate_stage(stage):
#     # Add content-pipeline to Python path
#     content_pipeline_path = r"D:\content-pipeline\_build\windows-x86_64\release\exts\omni.cip.avsim\omni\cip\avsim"
#     if os.path.exists(content_pipeline_path) and content_pipeline_path not in sys.path:
#         sys.path.append(content_pipeline_path)

#     import omni.asset_validator.simready
#     import importlib
#     importlib.reload(omni.asset_validator.simready)

#     # Reload the module
#     import omni.asset_validator.simready.vehicleCapability
#     importlib.reload(omni.asset_validator.simready.vehicleCapability)
#     print(omni.asset_validator.simready.vehicleCapability)

#     # Create engine
#     simready_vehicle_rules = (
#         omni.asset_validator.simready.GroundTruthCapabilityChecker,
#         omni.asset_validator.simready.NonVisualSensorCapabilityChecker,
#         omni.asset_validator.simready.VisualSensorCapabilityChecker,
#         omni.asset_validator.simready.VehicleCapabilityChecker,
#     )
#     engine = omni.asset_validator.ValidationEngine()
#     for checker in simready_vehicle_rules:
#         engine.enableRule(checker)

#     rules = omni.asset_validator.registry.get_category_rules_registry().get_rules("Geometry")
#     for rule in rules:
#         print(f"Disabling {rule}")
#         engine.disableRule(rule)

#     print_result(engine.validate(stage))


def fix_material_binding(prim, old_scope_prefix, new_scope_prefix, stage):
    """
    Rebinds a material based on the new scope prefix.
    """
    binding_api = UsdShade.MaterialBindingAPI(prim)
    result = binding_api.ComputeBoundMaterial()

    if not result:
        return  # No material bound

    bound_material = result[0]
    if not bound_material:
        return

    old_path = bound_material.GetPath()
    if old_path.HasPrefix(old_scope_prefix):
        relative_path = old_path.MakeRelativePath(old_scope_prefix)
        new_path = new_scope_prefix.AppendPath(relative_path)

        new_prim = stage.GetPrimAtPath(new_path)

        if new_prim.IsValid():
            print(f"✅ Rebinding {prim.GetPath()} → {new_path}")
            binding_api.Bind(UsdShade.Material(new_prim))
        else:
            print(f"⚠️ Material not found at {new_path}")


def move_children(old_parent, new_parent_path, stage, recurse=True):
    """
    Recursive Func to move children of an old parent to a new parent.
    """
    for child in old_parent.GetChildren():
        relative_name = child.GetName()
        new_child_path = new_parent_path.AppendChild(relative_name)

        # Define new prim with same type
        new_child = stage.DefinePrim(new_child_path, child.GetTypeName())

        # Copy attributes safely
        for attr in child.GetAttributes():
            attr_name = attr.GetName()
            attr_type = attr.GetTypeName()
            value = attr.Get()

            if value is not None:
                try:
                    new_attr = new_child.CreateAttribute(attr_name, attr_type)
                    new_attr.Set(value)
                except Exception as e:
                    print(f"⚠️ Skipping {attr.GetPath()}: {e}")

        # Recurse
        if recurse:
            move_children(child, new_child_path, stage)


def copy_materials(old_mat_prim, new_scope_prefix, stage):
    """
    Recursively copy materials from old parent to new parent.
    """
    # Get all materials from old parent
    src_layer = stage.GetEditTarget().GetLayer()
    children_of_old_mat = old_mat_prim.GetChildren()
    for child in children_of_old_mat:
        new_path = new_scope_prefix.AppendChild(child.GetName())
        Sdf.CopySpec(src_layer, child.GetPath(), src_layer, new_path)


def print_result(result):
    """Format and print given result."""
    result_text = ""

    for issue in result.issues():
        if not issue.at:
            result_text = result_text + f"ISSUE: {issue.message}\nSUGGESTION: {issue.suggestion}\n\n{'-'*150}\n\n"
        else:
            result_text = (
                result_text
                + f"ISSUE: {issue.message}\nSUGGESTION: {issue.suggestion} at {issue.at.as_str()}\n\n{'-'*150}\n\n"
            )

    result_text = result_text + "\nValidation Done."
    print(result_text)


def create_physics_material(stage, material_prim):
    """
    Creates a physics material from a material prim's custom properties.

    If the material has explicit physics properties (from Blender), they will be set.
    If not (e.g., from Kit/Omniverse), we still create the physics material schema
    but leave attributes unset so Kit can auto-compute them.
    """
    # Check if material has physics properties from Blender
    has_blender_physics_props = False
    blender_physics_attrs = []
    for attr in material_prim.GetAttributes():
        if attr.GetName().startswith("pxr:usd:physics_"):
            has_blender_physics_props = True
            blender_physics_attrs.append(attr)

    # Create physics material under PhysicsMaterials scope
    physics_scope = UsdGeom.Scope.Define(stage, "/RootNode/PhysicsMaterials")

    material_name = material_prim.GetName()
    physics_material_path = f"{physics_scope.GetPath()}/physics_mat_{material_name}"

    # Create physics material using MaterialAPI
    physics_material_prim = UsdShade.Material.Define(stage, physics_material_path)
    physics_material = UsdPhysics.MaterialAPI.Apply(physics_material_prim.GetPrim())

    # If we have explicit Blender physics properties, set them
    if has_blender_physics_props:
        print(f"  Creating physics material with Blender properties for: {material_name}")
        for attr in blender_physics_attrs:
            if attr.GetName() == "pxr:usd:physics_density":
                physics_material.CreateDensityAttr().Set(attr.Get())
            elif attr.GetName() == "pxr:usd:physics_dynamicFriction":
                physics_material.CreateDynamicFrictionAttr().Set(attr.Get())
            elif attr.GetName() == "pxr:usd:physics_restitution":
                physics_material.CreateRestitutionAttr().Set(attr.Get())
            elif attr.GetName() == "pxr:usd:physics_staticFriction":
                physics_material.CreateStaticFrictionAttr().Set(attr.Get())
    else:
        # No Blender properties - create empty physics material for Kit to auto-compute
        print(f"  Creating empty physics material for Kit auto-compute: {material_name}")
        # Just apply the schema, don't set any attributes
        # Kit/Omniverse will compute density, friction, restitution based on material type

    return physics_material_prim


def bind_physics_material(stage, mesh_prim, physics_material, mass, center_of_mass, inertia, principal_axes):
    """
    Binds a physics material to a mesh prim, setup collider, mass, center of mass, and inertia.

    If physics_material is None, we still apply the collision schema so Kit can handle physics,
    but without explicit material properties (Kit will auto-compute).
    """
    # Apply CollisionAPI to the mesh - this is required for physics even without a material
    mesh_collision_api = UsdPhysics.CollisionAPI.Apply(mesh_prim)
    mesh_coll_prim = mesh_collision_api.GetPrim()
    approx_attr = mesh_coll_prim.CreateAttribute("physics:approximation", Sdf.ValueTypeNames.Token)
    approx_attr.Set("convexDecomposition")

    # Bind the physics material if we have one
    if physics_material:
        binding_api = UsdShade.MaterialBindingAPI.Apply(mesh_prim)
        binding_api.Bind(physics_material, UsdShade.Tokens.weakerThanDescendants, materialPurpose="physics")
        print("  Bound physics material to mesh")
    else:
        print("  Applied collision schema without material binding (Kit will auto-compute)")

    # Set mass properties
    mass_api = UsdPhysics.MassAPI.Apply(mesh_prim)
    mass_api.CreateMassAttr().Set(mass)

    print(f"Setting center of mass: {center_of_mass}")
    mass_api.CreateCenterOfMassAttr().Set(center_of_mass)

    if inertia:
        # Create inertia attribute manually since MassAPI doesn't have CreateInertiaAttr()
        # Inertia should be a Vec3f representing the diagonal elements (Ixx, Iyy, Izz)
        print(f"Setting inertia: {inertia}")
        list_inertia = list(inertia)
        if isinstance(list_inertia, list) and len(list_inertia) == 3:
            inertia_vec = Gf.Vec3f(list_inertia[0], list_inertia[1], list_inertia[2])
            # Use the standard USD Physics inertia attribute name
            mesh_prim.CreateAttribute("physics:diagonalInertia", Sdf.ValueTypeNames.Vector3f).Set(inertia_vec)
            print(f"  ✅ Set diagonal inertia to: {inertia_vec}")
        elif isinstance(inertia, Gf.Vec3f):
            # If already a Vec3f, use directly
            mesh_prim.CreateAttribute("physics:diagonalInertia", Sdf.ValueTypeNames.Vector3f).Set(inertia)
            print(f"  ✅ Set diagonal inertia to: {inertia}")
        else:
            print(f"  ⚠️ Invalid inertia format: {inertia} (expected list of 3 values or Gf.Vec3f)")

    if principal_axes:
        print(f"Setting principal axis: {principal_axes}")
        # Convert principal_axes to Gf.Quatf for proper USD quaternion storage
        # principal_axes should be in (w, x, y, z) format

        if isinstance(principal_axes, Gf.Vec4d):
            # Convert Vec4d to Quatf (assuming w, x, y, z format)
            quat = Gf.Quatf(principal_axes[0], principal_axes[1], principal_axes[2], principal_axes[3])
            mesh_prim.CreateAttribute("physics:principalAxes", Sdf.ValueTypeNames.Quatf).Set(quat)
            print(f"  ✅ Set principal axes to: {quat}")
        else:
            print(f"  ⚠️ Invalid principal axes format: {principal_axes} for principal_axes (expected type Gf.Vec4d)")


def print_geometry_hierarchy(stage, geo_scope_path):
    """
    Print the hierarchy under the geometry scope to help debug path issues
    """

    print(f"\n--- GEOMETRY HIERARCHY UNDER {geo_scope_path} ---")
    geo_scope = stage.GetPrimAtPath(geo_scope_path)
    if not geo_scope.IsValid():
        print(f"Geometry scope at {geo_scope_path} is not valid!")
        return

    def print_hierarchy(prim, indent=0):
        print(f"{' ' * indent}└─ {prim.GetName()} ({prim.GetTypeName()})")
        for child in prim.GetChildren():
            print_hierarchy(child, indent + 2)

    for child in geo_scope.GetChildren():
        print_hierarchy(child)
    print("--- END GEOMETRY HIERARCHY ---\n")


def set_joint_attributes(
    joint_usd_prim,
    source_prim,
    joint_prim,
    geo_scope_path,
    stage,
    body0_prim,
    body1_prim,
    body0_mesh_prim,
    body1_mesh_prim,
):
    """Copy joint attributes from source prim to joint prim"""
    # Get the underlying Usd.Prim object
    print(f"set jt attr, source_prim: {source_prim}")
    print(f"set jt attr, joint_usd_prim: {joint_usd_prim}")

    def convert_to_radians_to_degrees(radians):
        return radians * (180 / math.pi)

    # TODO: this causes infinite loop... figure out why later
    # copy_dcc_attrs(source_prim, joint_usd_prim)

    def to_axis_token(axis):
        # Needing to support local axis's for artists
        # Normalize input to x, y, z

        if isinstance(axis, str):
            return Tf.Token(axis) if hasattr(Tf, "Token") else axis

        if isinstance(axis, (Gf.Vec3d, Gf.Vec3f)):
            x, y, z = float(axis[0]), float(axis[1]), float(axis[2])
        elif isinstance(axis, (list, tuple)) and len(axis) == 3:
            x, y, z = map(float, axis)
        else:
            raise TypeError(f"axis must be (list|tuple|Gf.Vec3*), got {type(axis)}")

        # Pick dominant world axis
        ax = max((abs(x), "X"), (abs(y), "Y"), (abs(z), "Z"))[1]

        # Use Tf.Token if available; otherwise just return the string
        return Tf.Token(ax) if hasattr(Tf, "Token") else ax

    # First copy all omni:simready:physx from source
    for attr in source_prim.GetAttributes():
        if attr.GetName().startswith("omni:simready:"):
            name = attr.GetName()
            value = attr.Get()
            joint_usd_prim.CreateAttribute(name, attr.GetTypeName()).Set(value)

    if source_prim.HasAttribute("pxr:usd:physics:joint:body0") and source_prim.HasAttribute(
        "pxr:usd:physics:joint:body1"
    ):
        # Create target arrays with only valid paths/prims
        body0_targets = []
        body1_targets = []

        if body0_mesh_prim and body0_mesh_prim.IsValid():
            body0_targets.append(body0_mesh_prim.GetPath())
            print(f"  ✅ Setting joint body0 target to: {body0_mesh_prim.GetPath()}")
        else:
            print("  ⚠️ No valid body0 mesh prim found for joint")

        if body1_mesh_prim and body1_mesh_prim.IsValid():
            body1_targets.append(body1_mesh_prim.GetPath())
            print(f"  ✅ Setting joint body1 target to: {body1_mesh_prim.GetPath()}")
        else:
            print("  ⚠️ No valid body1 mesh prim found for joint")

        joint_prim.CreateBody0Rel().SetTargets(body0_targets)
        joint_prim.CreateBody1Rel().SetTargets(body1_targets)

    if source_prim.HasAttribute("pxr:usd:physics:joint:axis"):
        axis = source_prim.GetAttribute("pxr:usd:physics:joint:axis").Get()

        print(f"set jt attr, axis: {axis}")
        print(type(axis))

        axis = to_axis_token(axis)

        joint_prim.CreateAxisAttr().Set(axis)

    # TODO: have these match schema exactly...
    if source_prim.HasAttribute("pxr:usd:physics:joint:lowerLimit"):
        if source_prim.GetAttribute("pxr:usd:physics:joint:type").Get() == "revolute":
            joint_type = source_prim.GetAttribute("pxr:usd:physics:joint:type").Get()
            if joint_type == "revolute":
                lower_limit = source_prim.GetAttribute("pxr:usd:physics:joint:lowerLimit").Get()
                # Handle infinite limits
                if isinstance(lower_limit, str):
                    if lower_limit == "-inf":
                        joint_prim.CreateLowerLimitAttr().Set(float("-inf"))
                    elif lower_limit == "inf":
                        joint_prim.CreateLowerLimitAttr().Set(float("inf"))
                    else:
                        # Try to convert string to float and then to degrees
                        try:
                            lower_limit = float(lower_limit)
                            lower_limit_degrees = lower_limit
                            joint_prim.CreateLowerLimitAttr().Set(lower_limit_degrees)
                        except ValueError:
                            print(f"Warning: Could not convert lower_limit '{lower_limit}' to float")
                else:
                    lower_limit_degrees = lower_limit
                    joint_prim.CreateLowerLimitAttr().Set(lower_limit_degrees)
        elif source_prim.GetAttribute("pxr:usd:physics:joint:type").Get() == "prismatic":
            lower_limit = source_prim.GetAttribute("pxr:usd:physics:joint:lowerLimit").Get()
            joint_prim.CreateLowerLimitAttr().Set(lower_limit)

    if source_prim.HasAttribute("pxr:usd:physics:joint:upperLimit"):
        if source_prim.GetAttribute("pxr:usd:physics:joint:type").Get() == "revolute":
            upper_limit = source_prim.GetAttribute("pxr:usd:physics:joint:upperLimit").Get()
            # Handle infinite limits
            if isinstance(upper_limit, str):
                if upper_limit == "inf":
                    joint_prim.CreateUpperLimitAttr().Set(float("inf"))
                elif upper_limit == "-inf":
                    joint_prim.CreateUpperLimitAttr().Set(float("-inf"))
                else:
                    # Try to convert string to float and then to degrees
                    try:
                        upper_limit = float(upper_limit)
                        upper_limit_degrees = upper_limit
                        joint_prim.CreateUpperLimitAttr().Set(upper_limit_degrees)
                    except ValueError:
                        print(f"Warning: Could not convert upper_limit '{upper_limit}' to float")
            else:
                upper_limit_degrees = upper_limit
                joint_prim.CreateUpperLimitAttr().Set(upper_limit_degrees)
        elif source_prim.GetAttribute("pxr:usd:physics:joint:type").Get() == "prismatic":
            upper_limit = source_prim.GetAttribute("pxr:usd:physics:joint:upperLimit").Get()
            joint_prim.CreateUpperLimitAttr().Set(upper_limit)

    # Spherical joint limits
    if source_prim.HasAttribute("pxr:usd:physics:coneAngle0Limit"):
        if source_prim.GetAttribute("pxr:usd:physics:joint:type").Get() == "spherical":
            cone0limit = source_prim.GetAttribute("pxr:usd:physics:coneAngle0Limit").Get()
            cone0limit_degrees = convert_to_radians_to_degrees(cone0limit)
            joint_prim.CreateConeAngle0LimitAttr().Set(cone0limit_degrees)
    if source_prim.HasAttribute("pxr:usd:physics:coneAngle1Limit"):
        if source_prim.GetAttribute("pxr:usd:physics:joint:type").Get() == "spherical":
            cone1limit = source_prim.GetAttribute("pxr:usd:physics:coneAngle1Limit").Get()
            cone1limit_degrees = convert_to_radians_to_degrees(cone1limit)
            joint_prim.CreateConeAngle1LimitAttr().Set(cone1limit_degrees)

    # localPos0
    # postion of current joint is based on the position of the parent joint, must negate parent's transforms as well.
    if source_prim.HasAttribute("pxr:usd:physics:localPos0"):
        from_dcc_attr = source_prim.GetAttribute("pxr:usd:physics:localPos0").Get()
        # Create the physics:localPos0 attribute if it doesn't exist
        if joint_usd_prim.HasAttribute("physics:localPos0"):
            local_pos_attr = joint_usd_prim.GetAttribute("physics:localPos0")
            from_dcc_attr_set = Gf.Vec3f(from_dcc_attr)
            local_pos_attr.Set(from_dcc_attr_set)

    if source_prim.HasAttribute("pxr:usd:physics:localPos1"):
        from_dcc_attr = source_prim.GetAttribute("pxr:usd:physics:localPos1").Get()
        if joint_usd_prim.HasAttribute("physics:localPos1"):
            local_pos_attr = joint_usd_prim.GetAttribute("physics:localPos1")
            from_dcc_attr_set = Gf.Vec3f(from_dcc_attr)
            local_pos_attr.Set(from_dcc_attr_set)

    if source_prim.HasAttribute("pxr:usd:physics:localRot0"):
        from_dcc_attr = source_prim.GetAttribute("pxr:usd:physics:localRot0").Get()
        if joint_usd_prim.HasAttribute("physics:localRot0"):
            local_rot_attr = joint_usd_prim.GetAttribute("physics:localRot0")
            print(f"set jt attr, localRot0: {from_dcc_attr}")
            print(f"Type: {type(from_dcc_attr)}")
            print(f"Length check: {len(from_dcc_attr) if hasattr(from_dcc_attr, '__len__') else 'no __len__'}")

            # Convert to GfQuatf - handle different input types
            quat = None

            # Check for 4-component data first (quaternion)
            if hasattr(from_dcc_attr, "__len__") and len(from_dcc_attr) == 4:
                print("Detected 4-component data (quaternion)")
                quat = Gf.Quatf(
                    float(from_dcc_attr[0]), float(from_dcc_attr[1]), float(from_dcc_attr[2]), float(from_dcc_attr[3])
                )
            # Check for 3-component data (Euler angles)
            elif hasattr(from_dcc_attr, "__len__") and len(from_dcc_attr) == 3:
                print("Detected 3-component data (Euler angles)")
                # 3-component Euler angles in radians (x, y, z)
                # Convert Euler to quaternion using Gf.Rotation
                euler_x, euler_y, euler_z = float(from_dcc_attr[0]), float(from_dcc_attr[1]), float(from_dcc_attr[2])
                print(f"Euler angles in radians: x={euler_x}, y={euler_y}, z={euler_z}")
                print(
                    f"Euler angles in degrees: x={math.degrees(euler_x):.2f}°, y={math.degrees(euler_y):.2f}°, z={math.degrees(euler_z):.2f}°"
                )

                # Create rotation from Euler angles (in degrees for Gf.Rotation)
                rot = (
                    Gf.Rotation(Gf.Vec3d(1, 0, 0), math.degrees(euler_x))
                    * Gf.Rotation(Gf.Vec3d(0, 1, 0), math.degrees(euler_y))
                    * Gf.Rotation(Gf.Vec3d(0, 0, 1), math.degrees(euler_z))
                )
                quat_d = rot.GetQuat()
                quat = Gf.Quatf(
                    quat_d.GetReal(), quat_d.GetImaginary()[0], quat_d.GetImaginary()[1], quat_d.GetImaginary()[2]
                )
                print(f"Converted to quaternion: {quat}")
            else:
                print("WARNING: Unexpected data format for localRot0, cannot convert to quaternion")

            if quat:
                print(f"Quaternion conversion successful, setting localRot0: {quat}")
                local_rot_attr.Set(quat)
            else:
                print("ERROR: Failed to create quaternion from localRot0 data")

    # TODO: localRot1 doesn't seem necesary.  But if conversion needed, then it would be the same as LocRot0.

    # Break Force / Break Torque
    if source_prim.HasAttribute("pxr:usd:physics:breakForce"):
        break_force_attr = source_prim.GetAttribute("pxr:usd:physics:breakForce")
        if break_force_attr and break_force_attr.HasValue():
            try:
                break_force = float(break_force_attr.Get())
                if break_force is not None:
                    joint_prim.CreateBreakForceAttr().Set(float(break_force))
                    print(f"  ✅ Set breakForce to {break_force}")
            except Exception as e:
                print(f"  ⚠️ Failed to set breakForce: {e}")

    if source_prim.HasAttribute("pxr:usd:physics:breakTorque"):
        break_torque_attr = source_prim.GetAttribute("pxr:usd:physics:breakTorque")
        if break_torque_attr and break_torque_attr.HasValue():
            try:
                break_torque = float(break_torque_attr.Get())
                if break_torque is not None:
                    joint_prim.CreateBreakTorqueAttr().Set(float(break_torque))
                    print(f"  ✅ Set breakTorque to {break_torque}")
            except Exception as e:
                print(f"  ⚠️ Failed to set breakTorque: {e}")

    # Drive API - Linear Drive
    has_linear_drive = False
    for attr in source_prim.GetAttributes():
        if attr.GetName().startswith("drive:linear:physics:"):
            has_linear_drive = True
            break

    if has_linear_drive:
        # Apply PhysicsDriveAPI:linear schema
        joint_usd_prim.ApplyAPI(UsdPhysics.DriveAPI, "linear")
        print("  ✅ Applied PhysicsDriveAPI:linear schema")

        # Copy linear drive attributes
        if source_prim.HasAttribute("drive:linear:physics:type"):
            drive_type = source_prim.GetAttribute("drive:linear:physics:type").Get()
            joint_usd_prim.CreateAttribute("drive:linear:physics:type", Sdf.ValueTypeNames.Token).Set(drive_type)
            print(f"  ✅ Set linear drive type: {drive_type}")

        if source_prim.HasAttribute("drive:linear:physics:maxForce"):
            max_force = source_prim.GetAttribute("drive:linear:physics:maxForce").Get()
            joint_usd_prim.CreateAttribute("drive:linear:physics:maxForce", Sdf.ValueTypeNames.Float).Set(max_force)
            print(f"  ✅ Set linear drive maxForce: {max_force}")

        if source_prim.HasAttribute("drive:linear:physics:targetPosition"):
            target_pos = source_prim.GetAttribute("drive:linear:physics:targetPosition").Get()
            joint_usd_prim.CreateAttribute("drive:linear:physics:targetPosition", Sdf.ValueTypeNames.Float).Set(
                target_pos
            )
            print(f"  ✅ Set linear drive targetPosition: {target_pos}")

        if source_prim.HasAttribute("drive:linear:physics:targetVelocity"):
            target_vel = source_prim.GetAttribute("drive:linear:physics:targetVelocity").Get()
            joint_usd_prim.CreateAttribute("drive:linear:physics:targetVelocity", Sdf.ValueTypeNames.Float).Set(
                target_vel
            )
            print(f"  ✅ Set linear drive targetVelocity: {target_vel}")

        if source_prim.HasAttribute("drive:linear:physics:damping"):
            damping = source_prim.GetAttribute("drive:linear:physics:damping").Get()
            joint_usd_prim.CreateAttribute("drive:linear:physics:damping", Sdf.ValueTypeNames.Float).Set(damping)
            print(f"  ✅ Set linear drive damping: {damping}")

        if source_prim.HasAttribute("drive:linear:physics:stiffness"):
            stiffness = source_prim.GetAttribute("drive:linear:physics:stiffness").Get()
            joint_usd_prim.CreateAttribute("drive:linear:physics:stiffness", Sdf.ValueTypeNames.Float).Set(stiffness)
            print(f"  ✅ Set linear drive stiffness: {stiffness}")

    # Drive API - Angular Drive
    has_angular_drive = False
    for attr in source_prim.GetAttributes():
        if attr.GetName().startswith("drive:angular:physics:"):
            has_angular_drive = True
            break

    if has_angular_drive:
        # Apply PhysicsDriveAPI:angular schema
        joint_usd_prim.ApplyAPI(UsdPhysics.DriveAPI, "angular")
        print("  ✅ Applied PhysicsDriveAPI:angular schema")

        # Copy angular drive attributes
        if source_prim.HasAttribute("drive:angular:physics:type"):
            drive_type = source_prim.GetAttribute("drive:angular:physics:type").Get()
            joint_usd_prim.CreateAttribute("drive:angular:physics:type", Sdf.ValueTypeNames.Token).Set(drive_type)
            print(f"  ✅ Set angular drive type: {drive_type}")

        if source_prim.HasAttribute("drive:angular:physics:maxForce"):
            max_force = source_prim.GetAttribute("drive:angular:physics:maxForce").Get()
            joint_usd_prim.CreateAttribute("drive:angular:physics:maxForce", Sdf.ValueTypeNames.Float).Set(max_force)
            print(f"  ✅ Set angular drive maxForce: {max_force}")

        if source_prim.HasAttribute("drive:angular:physics:targetPosition"):
            target_pos = source_prim.GetAttribute("drive:angular:physics:targetPosition").Get()
            # Convert from degrees to radians for USD
            target_pos_rad = math.radians(target_pos)
            joint_usd_prim.CreateAttribute("drive:angular:physics:targetPosition", Sdf.ValueTypeNames.Float).Set(
                target_pos_rad
            )
            print(f"  ✅ Set angular drive targetPosition: {target_pos}° ({target_pos_rad} rad)")

        if source_prim.HasAttribute("drive:angular:physics:targetVelocity"):
            target_vel = source_prim.GetAttribute("drive:angular:physics:targetVelocity").Get()
            # Convert from degrees/sec to radians/sec for USD
            target_vel_rad = math.radians(target_vel)
            joint_usd_prim.CreateAttribute("drive:angular:physics:targetVelocity", Sdf.ValueTypeNames.Float).Set(
                target_vel_rad
            )
            print(f"  ✅ Set angular drive targetVelocity: {target_vel}°/s ({target_vel_rad} rad/s)")

        if source_prim.HasAttribute("drive:angular:physics:damping"):
            damping = source_prim.GetAttribute("drive:angular:physics:damping").Get()
            joint_usd_prim.CreateAttribute("drive:angular:physics:damping", Sdf.ValueTypeNames.Float).Set(damping)
            print(f"  ✅ Set angular drive damping: {damping}")

        if source_prim.HasAttribute("drive:angular:physics:stiffness"):
            stiffness = source_prim.GetAttribute("drive:angular:physics:stiffness").Get()
            joint_usd_prim.CreateAttribute("drive:angular:physics:stiffness", Sdf.ValueTypeNames.Float).Set(stiffness)
            print(f"  ✅ Set angular drive stiffness: {stiffness}")


def detect_root_hierarchy(stage: Usd.Stage, dp) -> tuple[bool, str]:
    """
    Stage check to determine if an asset has a logical root.
    A logicial root in this case is defined as a group of xforms or meshes that are nested under a single xform/prim.
    Artist translation: Artist has grouped meshes under a single empty/locator, so they can move the entire group as a single object.
    Returns: True if a logical root is found, and the path to the logical root.
    Misc: Will return False if there's too many nested prims.  Will only pass if there's only 1 logical root.
    """

    candidate_roots = []
    for prim in stage.Traverse():
        if prim.GetTypeName() == "Xform" and prim.GetName() != dp.GetName() and "OmniKit" not in str(prim.GetPath()):
            children = list(prim.GetChildren())
            if len(children) >= 2:
                candidate_roots.append(prim)

    if len(candidate_roots) == 1:
        logical_root = candidate_roots[0]
        return (True, logical_root)
    elif len(candidate_roots) > 1:
        print("Your asset has too many nested prims, try only nesting your meshes under 1 empty!!")
        print(f"Debug Candidates: {candidate_roots}")
        return (False, "")
    else:
        return (False, "")


class SimReadyUSDHook(bpy.types.USDHook):
    """
    Implementation of USD IO hooks for exporting Simready Asset
    hook will fire off with every use export...
    User can unregister and re-register to disable/enable
    """

    bl_idname = "SimReady_USDHook"
    bl_label = "SimReadyUSDHook"

    @staticmethod
    def on_export(export_context):
        # Only run if DS_CORE initiated the export (read from module to avoid Scene write in timer context)
        try:
            from ..library import run_export_gui

            active_hook = getattr(run_export_gui, "_active_usd_hook", "")
        except ImportError:
            active_hook = bpy.context.scene.get("active_usd_hook", "")

        if active_hook != "SIMREADY_CORE":
            print(f"SRSHook: Skipping (active_usd_hook='{active_hook}', expected 'SIMREADY_CORE')")
            return

        settings_prefs = get_prefs()
        settings = settings_prefs.settings
        skip_usd_hook = settings.debug_no_usd_hook

        if skip_usd_hook:
            print("Skipping USD Hook")
            return

        # get global simready metadata
        global_metadata = bpy.context.scene.global_metadata
        wikidata_query = global_metadata.wikidata_query if global_metadata.wikidata_query else ""
        wikidata_result_id = global_metadata.wikidata_result_id if global_metadata.wikidata_result_id else ""
        wikidata_result_label = global_metadata.wikidata_result_label if global_metadata.wikidata_result_label else ""
        wikidata_result_description = (  # noqa F841
            global_metadata.wikidata_result_description if global_metadata.wikidata_result_description else ""
        )
        global_caption = global_metadata.global_caption if global_metadata.global_caption else ""

        print(
            f"Export: Global metadata - Query: '{wikidata_query}', ID: '{wikidata_result_id}', Label: '{wikidata_result_label}', Caption: '{global_caption[:50] if global_caption else 'None'}...'"
        )

        # Get the current UI state at export time
        export_props = bpy.context.scene.export_props
        poseable_only = export_props.poseable_only
        LOGICAL_HIERARCHY = bool(poseable_only)

        stage = export_context.get_stage()
        defaultPrim = stage.GetDefaultPrim()
        root_layer = stage.GetRootLayer()
        export_file_path = root_layer.realPath if root_layer else None
        dense_caption_attr = None

        # Add global simready metadata to defaultPrim using SemanticsAPI
        if defaultPrim and defaultPrim.IsValid():
            # Create or get the defaultPrim
            default_prim = stage.GetPrimAtPath(defaultPrim.GetPath())

            if default_prim and default_prim.IsValid():
                # Add wikidata class metadata using SemanticsAPI pattern
                if wikidata_query:
                    # Create the legacy attribute for the query (preserves spaces)
                    query_attr = default_prim.CreateAttribute(
                        LEGACY_SEMANTICS_CLASS_DATA_ATTR_NAME, Sdf.ValueTypeNames.String
                    )
                    query_attr.Set(wikidata_query)

                    # Create the type attribute
                    type_attr = default_prim.CreateAttribute(
                        LEGACY_SEMANTICS_CLASS_TYPE_ATTR_NAME, Sdf.ValueTypeNames.String
                    )
                    type_attr.Set(LEGACY_SEMANTICS_CLASS_ATTR_VALUE)

                    # Add the SemanticsAPI schema
                    default_prim.AddAppliedSchema("SemanticsLabelsAPI:wikidata_class")

                    # Create the new semantics attribute
                    semantics_attr = default_prim.CreateAttribute(
                        SEMANTICS_CLASS_ATTR_NAME, Sdf.ValueTypeNames.TokenArray
                    )
                    semantics_attr.Set([wikidata_query])
                    default_prim.AddAppliedSchema("SemanticsAPI:wikidata_class")

                # Add wikidata qcode metadata using SemanticsAPI pattern
                if wikidata_result_id:
                    # Create the legacy attribute for the qcode
                    qcode_attr = default_prim.CreateAttribute(
                        LEGACY_SEMANTICS_QCODE_DATA_ATTR_NAME, Sdf.ValueTypeNames.String
                    )
                    qcode_attr.Set(wikidata_result_id)

                    # Create the type attribute
                    qcode_type_attr = default_prim.CreateAttribute(
                        LEGACY_SEMANTICS_QCODE_TYPE_ATTR_NAME, Sdf.ValueTypeNames.String
                    )
                    qcode_type_attr.Set(LEGACY_SEMANTICS_QCODE_ATTR_VALUE)

                    # Add the SemanticsAPI schema
                    default_prim.AddAppliedSchema("SemanticsLabelsAPI:wikidata_qcode")

                    # Create the new semantics attribute
                    qcode_semantics_attr = default_prim.CreateAttribute(
                        SEMANTICS_QCODE_ATTR_NAME, Sdf.ValueTypeNames.TokenArray
                    )
                    qcode_semantics_attr.Set([wikidata_result_id])
                    default_prim.AddAppliedSchema("SemanticsAPI:wikidata_qcode")

                print(
                    f"Added wikidata metadata to defaultPrim using SemanticsAPI: Query='{wikidata_query}', ID='{wikidata_result_id}'"
                )

            else:
                print("Warning: defaultPrim is not valid, cannot add wikidata metadata")
        else:
            print("Warning: No defaultPrim found, cannot add wikidata metadata")

        # Get asset profile data and apply to custom data
        # TODO: today everything is a prop, but we need hooks to determine what type of asset this is.
        # TODO: determine profile number somehow...

        profile = "Prop-Robotics-Neutral"

        # Add profile back to blender properties
        if hasattr(bpy.context.scene, "asset_profiles"):
            # Map the profile string to the enum value
            profile_mapping = {
                "Prop-Robotics-Neutral": "NEUTRAL",
                # Add more mappings as needed
            }

            # Set the selected profile in Blender properties
            if profile in profile_mapping:
                bpy.context.scene.asset_profiles.selected_profile = profile_mapping[profile]
                print(f"Set asset profile to: {profile_mapping[profile]}")
            else:
                print(f"Warning: Unknown profile '{profile}' - not setting in Blender properties")

        # write asset profile to Usd custom layer data
        if profile:
            custom_layer_data = root_layer.customLayerData or {}

            custom_layer_data["SimReady_Metadata"] = {
                "asset_type": "prop",
                "validation": {"profile": profile, "profile_version": "1.0.0"},
            }

            root_layer.customLayerData = custom_layer_data

        # Now update all materials to generate MaterialX or MDL Shaders (USD Preview has already been made)
        if not settings.debug_no_mdl:
            try:
                # we need the export file path to resolve paths to textures and portable shaders.
                append_neutral_materials(stage, export_file_path)
            except Exception as e:
                import traceback

                print(f"Error appending neutral materials: {e}")
                traceback.print_exc()
                # Fail silently...

        # Now determine if we are exporting material X.
        if export_props.use_materialx:
            try:
                modify_materialx_shaders(stage)
            except Exception as e:
                import traceback

                print(f"Error modifying materialX shaders: {e}")
                traceback.print_exc()
                # Fail silently...

        # Continue with existing export logic
        for prim in stage.Traverse():

            # grasp vectors sent as curves, ensure their visualization attr's are sane.
            if prim.GetTypeName() == "BasisCurves":
                set_usd_curve_attrs(prim)

                # Set purpose to 'guide' for the BasisCurves prim
                imageable = UsdGeom.Imageable(prim)
                imageable.CreatePurposeAttr().Set(UsdGeom.Tokens.guide)

                # Set purpose to 'guide' parent prim
                parent_prim = prim.GetParent()
                if parent_prim and parent_prim.IsValid():
                    parent_imageable = UsdGeom.Imageable(parent_prim)
                    parent_imageable.CreatePurposeAttr().Set(UsdGeom.Tokens.guide)

            # 3.0.C1.01 - Semantic QCode requirement
            if prim.HasAttribute(LEGACY_SEMANTICS_CLASS_DATA_ATTR_NAME):
                v = prim.GetAttribute(LEGACY_SEMANTICS_CLASS_DATA_ATTR_NAME).Get(Usd.TimeCode.EarliestTime())
                v = [v] if v else []
                a = prim.CreateAttribute(LEGACY_SEMANTICS_CLASS_TYPE_ATTR_NAME, Sdf.ValueTypeNames.String)
                a.Set(LEGACY_SEMANTICS_CLASS_ATTR_VALUE)
                prim.AddAppliedSchema("SemanticsLabelsAPI:wikidata_class")

                a = prim.CreateAttribute(SEMANTICS_CLASS_ATTR_NAME, Sdf.ValueTypeNames.TokenArray)
                a.Set(v)
                prim.AddAppliedSchema("SemanticsAPI:wikidata_class")

            if prim.HasAttribute(LEGACY_SEMANTICS_QCODE_DATA_ATTR_NAME):
                v = prim.GetAttribute(LEGACY_SEMANTICS_QCODE_DATA_ATTR_NAME).Get(Usd.TimeCode.EarliestTime())
                v = [v] if v else []
                a = prim.CreateAttribute(LEGACY_SEMANTICS_QCODE_TYPE_ATTR_NAME, Sdf.ValueTypeNames.String)
                a.Set(LEGACY_SEMANTICS_QCODE_ATTR_VALUE)
                prim.AddAppliedSchema("SemanticsLabelsAPI:wikidata_qcode")

                a = prim.CreateAttribute(SEMANTICS_QCODE_ATTR_NAME, Sdf.ValueTypeNames.TokenArray)
                a.Set(v)
                prim.AddAppliedSchema("SemanticsAPI:wikidata_qcode")

            # 3.0.C1.02: Dense Caption Requirement
            if prim.HasAttribute(DOC_ATTR_NAME):
                dense_caption_attr = prim.GetAttribute(DOC_ATTR_NAME)

            # 3.0.C2.01: Non Visual Material Assignment
            if prim.HasAttribute(NONVISUAL_BASE_ATTR_NAME):
                convert_attr_type(prim.GetAttribute(NONVISUAL_BASE_ATTR_NAME))

            if prim.HasAttribute(NONVISUAL_COATING_ATTR_NAME):
                convert_attr_type(prim.GetAttribute(NONVISUAL_COATING_ATTR_NAME))

            if prim.HasAttribute(NONVISUAL_ATTRIBUTES_ATTR_NAME):
                print(f"NONVISUAL_ATTRIBUTES_ATTR_NAME: {prim.GetAttribute(NONVISUAL_ATTRIBUTES_ATTR_NAME).Get()}")
                convert_attr_type(
                    prim.GetAttribute(NONVISUAL_ATTRIBUTES_ATTR_NAME),
                    attr_type=Sdf.ValueTypeNames.TokenArray,
                    split_value=True,
                )

            # 5.0.C0.02: Vehicle Parts Annotation
            if prim.HasAttribute(VEHICLE_PART_ATTR_NAME):
                convert_attr_type(prim.GetAttribute(VEHICLE_PART_ATTR_NAME))

            # # 5.0.C0.02: Lights
            if prim.HasAttribute(LIGHT_INTENSITY_ATTR_NAME_BLENDER_MIN) and prim.HasAttribute(
                LIGHT_INTENSITY_ATTR_NAME_BLENDER_MAX
            ):
                min_value = prim.GetAttribute(LIGHT_INTENSITY_ATTR_NAME_BLENDER_MIN).Get()
                max_value = prim.GetAttribute(LIGHT_INTENSITY_ATTR_NAME_BLENDER_MAX).Get()
                prim.RemoveProperty(LIGHT_INTENSITY_ATTR_NAME_BLENDER_MIN)
                prim.RemoveProperty(LIGHT_INTENSITY_ATTR_NAME_BLENDER_MAX)
                a = prim.CreateAttribute(LIGHT_INTENSITY_ATTR_NAME, Sdf.ValueTypeNames.Double2)
                a.Set(Gf.Vec2d(min_value, max_value))

            if prim.HasAttribute(LIGHT_ATTR_NAME):
                convert_attr_type(
                    prim.GetAttribute(LIGHT_ATTR_NAME),
                    attr_type=Sdf.ValueTypeNames.TokenArray,
                    split_value=True,
                )

            if prim.HasAttribute(LIGHT_COLOR_ATTR_NAME):
                v = prim.GetAttribute(LIGHT_COLOR_ATTR_NAME).Get()
                prim.RemoveProperty(LIGHT_COLOR_ATTR_NAME)
                a = prim.CreateAttribute(LIGHT_COLOR_ATTR_NAME, Sdf.ValueTypeNames.Color3d)
                a.Set(v)

            if prim.HasAttribute(LIGHT_DURATION_ATTR_NAME):
                convert_attr_type(
                    prim.GetAttribute(LIGHT_DURATION_ATTR_NAME),
                    Sdf.ValueTypeNames.Float,
                )

        # Root Prim operations
        children = stage.GetPseudoRoot().GetChildren()
        if len(children) != 1:
            raise RuntimeError(f"More than one root prim in stage {children}")

        root_prim = children[0]

        # 3.0.C1.02: Dense Caption Requirement
        if dense_caption_attr:
            root_prim.SetDocumentation(dense_caption_attr.Get())
            dense_caption_attr.GetPrim().RemoveProperty(dense_caption_attr.GetName())

        # Collect relationships to either build collections or rebuild the hiearchy
        relationships = build_relationship_dict(LOGICAL_HIERARCHY)

        print(relationships)

        stage.SetEditTarget(stage.GetRootLayer())

        old_scope_prefix = Sdf.Path("/RootNode/_materials")
        new_scope_prefix = Sdf.Path("/RootNode/Materials")
        old_mat_prim = stage.GetPrimAtPath(old_scope_prefix)

        # Create new Materials scope
        UsdGeom.Scope.Define(stage, new_scope_prefix)

        # Only attempt to copy materials if the old materials scope exists
        if old_mat_prim and old_mat_prim.IsValid():
            # move materials under newly created Materials scope
            copy_materials(old_mat_prim, new_scope_prefix, stage)

            # rebind materials to original materials
            for prim in stage.Traverse():
                fix_material_binding(prim, old_scope_prefix, new_scope_prefix, stage)

            # Remove old materials scope after copying
            stage.RemovePrim(old_scope_prefix)
        else:
            print("No existing materials scope found at /RootNode/_materials")

        # convert materials
        # TODO: Will probably come back to this when requirements defined on what type of materials are needed.
        # convert_materials(stage)

        stage.RemovePrim(old_scope_prefix)
        rootLayer = stage.GetRootLayer()
        defaultPrim = stage.GetDefaultPrim()

        # create a Geometry Scope
        geo_scope_path = Sdf.Path("/RootNode/Geometry")
        UsdGeom.Scope.Define(stage, geo_scope_path)

        # check if there's a logical root
        has_logical_root, logical_root = detect_root_hierarchy(stage, defaultPrim)

        if has_logical_root:
            logical_root_name = logical_root.GetName()

        # create a ReferencePrims scope
        ref_scope_path = Sdf.Path("/RootNode/ReferencePrims")
        UsdGeom.Scope.Define(stage, ref_scope_path)

        # Move all curves to Grasp scope
        grasp_scope_path = Sdf.Path("/RootNode/Grasp")
        UsdGeom.Scope.Define(stage, grasp_scope_path)

        # move geometry to scope
        source_parent = "/RootNode"
        target_parent = "/RootNode/Geometry"
        target_grasp_parent = "/RootNode/Grasp"
        do_not_move = ["vehicle", "Materials", "Omniverse", "Render", "Geometry", "_joint", "Reference", "env_light"]

        source_prim = stage.GetPrimAtPath(source_parent)

        for child in source_prim.GetChildren():
            name = child.GetName()
            path_str = str(child.GetPath())

            print(f"staring to move {name} to {target_parent}")

            if not any(skip in path_str for skip in do_not_move) and "grasp" not in path_str.lower():
                old_path = child.GetPath()
                new_path = Sdf.Path(f"{target_parent}/{name}")
                # Move spec
                Sdf.CopySpec(rootLayer, old_path, rootLayer, new_path)
                stage.RemovePrim(old_path)

                # Ensure moved prim has xform ops (required for HI.009 validation)
                moved_prim = stage.GetPrimAtPath(new_path)
                if moved_prim.IsValid() and moved_prim.IsA(UsdGeom.Xformable):
                    ensure_xformable_attributes(moved_prim)
            elif "joint" in path_str:
                old_path = child.GetPath()
                new_path = Sdf.Path(f"{ref_scope_path}/{name}")
                Sdf.CopySpec(rootLayer, old_path, rootLayer, new_path)
                stage.RemovePrim(old_path)
            elif "identifier" in path_str:
                old_path = child.GetPath()
                print(f"old_path: {old_path}")
                new_path = Sdf.Path(f"{target_grasp_parent}/{name}")
                Sdf.CopySpec(rootLayer, old_path, rootLayer, new_path)
                stage.RemovePrim(old_path)

                # set to invisible (will annoy artists)
                curr_prim = stage.GetPrimAtPath(new_path)
                if curr_prim.IsValid():
                    curr_prim.GetAttribute("visibility").Set(UsdGeom.Tokens.invisible)

            # remove anything of type DomeLight
            elif child.GetTypeName() == "DomeLight" or child.GetName() == "env_light":
                stage.RemovePrim(child.GetPath())

        if not LOGICAL_HIERARCHY:
            # Process physics materials
            material_prims = [prim for prim in stage.Traverse() if prim.IsA(UsdShade.Material)]
            for material_prim in material_prims:
                physics_material = create_physics_material(stage, material_prim)
                if physics_material:
                    # Find all meshes bound to this material
                    for prim in stage.Traverse():
                        if prim.IsA(UsdGeom.Mesh):
                            binding_api = UsdShade.MaterialBindingAPI(prim)
                            bound_material = binding_api.ComputeBoundMaterial()
                            if bound_material and bound_material[0].GetPath() == material_prim.GetPath():
                                mesh_parent = prim.GetParent()
                                mass, center_of_mass, inertia, principal_axes = get_mesh_physics_properties(mesh_parent)
                                bind_physics_material(
                                    stage, prim, physics_material, mass, center_of_mass, inertia, principal_axes
                                )

        # DEBUG
        # print(relationships)
        # print("USD Version:", Usd.GetVersion())

        if LOGICAL_HIERARCHY:
            move_prims_under_parents(stage, relationships)
        else:
            create_usd_collections_from_mapping(stage, relationships)

            # ONLY BUILD JOINTS IF NOT POSEABLE BODY... PHYSICS IS DISABLED FOR POSEABLE BODIES

            # Build Scope for Joints
            joint_scope_path = Sdf.Path("/RootNode/Joints")
            UsdGeom.Scope.Define(stage, joint_scope_path)

            # If reference prim has attributes "pxr:usd:physics", then create a joint and use attrs to create
            # the schema for the joint... loop through stage again, TODO: optimize the loop eventually
            collider_objects = define_collision_collection_geo()

            for prim in stage.Traverse():

                # TODO: Maybe we can assume that _joint is going to be the common name for a ref prim that needs to be a joint?
                # Maybe we can house a list of common things that users would call their joints. (i.e. hinge...)
                if "_joint" in prim.GetName() and prim.HasAttribute("pxr:usd:physics:joint:type"):
                    print(f"prim: {prim.GetName()} is a joint")
                    print(f"prim: {prim.GetName()} has pxr:usd:physics")
                    # create a joint prim under the joints scope, first find the attribute that contains the joint type
                    joint_type = prim.GetAttribute("pxr:usd:physics:joint:type").Get()
                    print(f"joint_type: {joint_type}")

                    joint_prim_name = f"joint_{prim.GetName()}"

                    if joint_type:
                        if joint_type == "revolute":
                            joint_prim = UsdPhysics.RevoluteJoint.Define(
                                stage, joint_scope_path.AppendChild(joint_prim_name)
                            )
                        elif joint_type == "prismatic":
                            joint_prim = UsdPhysics.PrismaticJoint.Define(
                                stage, joint_scope_path.AppendChild(joint_prim_name)
                            )
                        elif joint_type == "distance":
                            joint_prim = UsdPhysics.DistanceJoint.Define(
                                stage, joint_scope_path.AppendChild(joint_prim_name)
                            )
                        elif joint_type == "gear":
                            joint_prim = UsdPhysics.GearJoint.Define(
                                stage, joint_scope_path.AppendChild(joint_prim_name)
                            )
                        elif joint_type == "spherical":
                            joint_prim = UsdPhysics.SphericalJoint.Define(
                                stage, joint_scope_path.AppendChild(joint_prim_name)
                            )
                        elif joint_type == "d6":
                            joint_prim = UsdPhysics.D6Joint.Define(stage, joint_scope_path.AppendChild(joint_prim_name))
                        elif joint_type == "rack_and_pinion":
                            joint_prim = UsdPhysics.RackPinionJoint.Define(
                                stage, joint_scope_path.AppendChild(joint_prim_name)
                            )
                        elif joint_type == "fixed":
                            joint_prim = UsdPhysics.FixedJoint.Define(
                                stage, joint_scope_path.AppendChild(joint_prim_name)
                            )

                        joint_usd_prim = stage.GetPrimAtPath(joint_scope_path.AppendChild(joint_prim_name))

                        # Get body0 and body1 from the reference prim
                        body0 = prim.GetAttribute("pxr:usd:physics:joint:body0").Get()
                        body1 = prim.GetAttribute("pxr:usd:physics:joint:body1").Get()

                        # Different possible path patterns for finding the mesh
                        if has_logical_root:
                            body0_parent_path = f"{geo_scope_path}/{logical_root_name}/{body0}"
                        else:
                            body0_parent_path = f"{geo_scope_path}/{body0}"

                        body0_mesh_paths = [
                            f"{body0_parent_path}/{body0.replace('_obj', '_mesh')}",  # Common pattern
                            f"{body0_parent_path}/mesh",  # Simple "mesh" child
                            f"{body0_parent_path}/{body0}",  # Same name as parent
                            f"{geo_scope_path}/{body0}",  # Direct reference
                        ]

                        if has_logical_root:
                            body1_parent_path = f"{geo_scope_path}/{logical_root_name}/{body1}"
                        else:
                            body1_parent_path = f"{geo_scope_path}/{body1}"

                        body1_mesh_paths = [
                            f"{body1_parent_path}/{body1.replace('_obj', '_mesh')}",  # Common pattern
                            f"{body1_parent_path}/mesh",  # Simple "mesh" child
                            f"{body1_parent_path}/{body1}",  # Same name as parent
                            f"{geo_scope_path}/{body1}",  # Direct reference
                        ]

                        # Find valid paths
                        body0_prim = None
                        body0_parent_prim = None
                        body0_mesh_prim = None
                        body0_mesh_path = None

                        # Check parent path first
                        body0_parent_prim = stage.GetPrimAtPath(body0_parent_path)

                        # Then check for a valid mesh
                        for path in body0_mesh_paths:
                            temp_prim = stage.GetPrimAtPath(path)
                            if temp_prim.IsValid() and temp_prim.IsA(UsdGeom.Mesh):
                                body0_mesh_prim = temp_prim
                                body0_mesh_path = path
                                break

                        # Same for body1
                        body1_prim = None
                        body1_parent_prim = None
                        body1_mesh_prim = None
                        body1_mesh_path = None

                        # Check parent path
                        body1_parent_prim = stage.GetPrimAtPath(body1_parent_path)

                        # Then check for a valid mesh
                        for path in body1_mesh_paths:
                            temp_prim = stage.GetPrimAtPath(path)
                            if temp_prim.IsValid() and temp_prim.IsA(UsdGeom.Mesh):
                                body1_mesh_prim = temp_prim
                                body1_mesh_path = path
                                break

                        # Debug print to understand what's found
                        print(f"Joint '{joint_prim_name}' connecting:")
                        print(f"  body0: '{body0}'")
                        print(
                            f"    parent: '{body0_parent_path}' - Exists: {body0_parent_prim.IsValid() if body0_parent_prim else False}"
                        )
                        print(
                            f"    mesh: '{body0_mesh_path}' - Exists: {body0_mesh_prim.IsValid() if body0_mesh_prim else False}"
                        )
                        print(f"  body1: '{body1}'")
                        print(
                            f"    parent: '{body1_parent_path}' - Exists: {body1_parent_prim.IsValid() if body1_parent_prim else False}"
                        )
                        print(
                            f"    mesh: '{body1_mesh_path}' - Exists: {body1_mesh_prim.IsValid() if body1_mesh_prim else False}"
                        )

                        # Only apply RigidBodyAPI to valid parent prims
                        if body0_parent_prim and body0_parent_prim.IsValid():
                            body0_prim = body0_parent_prim
                            UsdPhysics.RigidBodyAPI.Apply(body0_prim)

                        else:
                            print(f"⚠️ Cannot apply RigidBodyAPI - no valid prim for body0: {body0}")

                        if body1_parent_prim and body1_parent_prim.IsValid():
                            body1_prim = body1_parent_prim
                            UsdPhysics.RigidBodyAPI.Apply(body1_prim)

                        else:
                            print(f"⚠️ Cannot apply RigidBodyAPI - no valid prim for body1: {body1}")

                        # Pass all the found prims and paths to the set_joint_attributes function
                        set_joint_attributes(
                            joint_usd_prim=joint_usd_prim,
                            source_prim=prim,
                            joint_prim=joint_prim,
                            geo_scope_path=geo_scope_path,
                            stage=stage,
                            body0_prim=body0_prim,
                            body1_prim=body1_prim,
                            body0_mesh_prim=body0_mesh_prim,
                            body1_mesh_prim=body1_mesh_prim,
                        )
                elif (
                    "_joint" in prim.GetName()
                    and not prim.HasAttribute("pxr:usd:physics:joint:type")
                    and "identifier" not in prim.GetName()
                ):
                    # For multibody assets, move colliders under vis meshes that have the same joint constraints.
                    is_multibody = move_colliders_to_matching_vis_meshes(stage, root_layer)
                    if is_multibody:
                        break

                    prim_name = prim.GetName()
                    collection_api = Usd.CollectionAPI(prim, str(prim_name))

                    # TODO: For _joints, this will ONLY be one target, this won't work for mulitple targets (i.e. AVSim)
                    # For unibody assets, find the linked object and move the colliders under it
                    try:
                        linked_obj_path = collection_api.GetIncludesRel().GetTargets()[0]
                        linked_obj_prim = stage.GetPrimAtPath(linked_obj_path)
                        UsdPhysics.RigidBodyAPI.Apply(linked_obj_prim)

                        # Move collider objects under the linked_obj_prim
                        for collider_name in collider_objects:
                            # Find the collider prim in the stage
                            collider_prim = None
                            for stage_prim in stage.Traverse():
                                if stage_prim.GetName() == collider_name:
                                    collider_prim = stage_prim
                                    break

                            if collider_prim and collider_prim.IsValid():
                                old_path = collider_prim.GetPath()
                                new_path = linked_obj_prim.GetPath().AppendChild(collider_name)

                                # Copy the spec to new location
                                Sdf.CopySpec(root_layer, old_path, root_layer, new_path)
                                new_prim = stage.GetPrimAtPath(new_path)

                                # Set visibility to False for the collider
                                # TODO: might need the purpose to be guide, but not sure yet.
                                if new_prim.IsA(UsdGeom.Xformable):
                                    xformable = UsdGeom.Xformable(new_prim)
                                    xformable.CreateVisibilityAttr().Set(UsdGeom.Tokens.invisible)

                                stage.RemovePrim(old_path)
                                print(f"✅ Moved collider '{collider_name}' under '{linked_obj_prim.GetPath()}'")
                            else:
                                print(f"⚠️ Collider prim '{collider_name}' not found in stage")

                    except Exception as e:
                        print(f"⚠️ No linked object found for {prim_name} - {e}")
                        pass

            grasp_identifier_scope_path = Sdf.Path("/RootNode/Grasp")
            grasp_prim = stage.GetPrimAtPath(grasp_identifier_scope_path)
            if grasp_prim.IsValid():
                for child in grasp_prim.GetChildren():
                    print(f"child: {child.GetName()}")
                    # move identifier under the targeted object
                    # Get prim attribute that has the body
                    old_path = child.GetPath()
                    target_body = child.GetAttribute("intersection_object").Get()
                    print(f"target_body: {target_body}")

                    if target_body is not None:

                        # parse geometry scope to find the target body
                        geo_scope_path = Sdf.Path("/RootNode/Geometry")
                        target_body_path = f"{geo_scope_path}/{target_body}"

                        # Check if the target body prim exists before attempting to copy
                        target_body_prim = stage.GetPrimAtPath(target_body_path)
                        if not target_body_prim.IsValid():
                            print(
                                f"⚠️ Warning: Target body '{target_body}' does not exist at path '{target_body_path}'. Skipping grasp identifier '{child.GetName()}'."
                            )
                            continue

                        # Ensure target body prim has xform ops (required for HI.009 validation)
                        if target_body_prim.IsA(UsdGeom.Xformable):
                            ensure_xformable_attributes(target_body_prim)

                        new_path = Sdf.Path(f"{target_body_path}/{child.GetName()}")

                        Sdf.CopySpec(rootLayer, old_path, rootLayer, new_path)

                        # Decompose the matrix and properly offset the identifier to the new parent prim
                        prim_orig = stage.GetPrimAtPath(old_path)
                        prim_target = stage.GetPrimAtPath(new_path)

                        world_transform_inverse = (
                            UsdGeom.Xformable(prim_orig)
                            .ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                            .GetInverse()
                        )
                        local_transform = UsdGeom.Xformable(prim_target).ComputeParentToWorldTransform(
                            Usd.TimeCode.Default()
                        )

                        relative_matrix = world_transform_inverse * -local_transform

                        translation, rotation, scale = decompose_matrix(relative_matrix)

                        # Always add xform ops to grasp identifiers (required for HI.009 validation)
                        new_prim = stage.GetPrimAtPath(new_path)
                        new_xform = UsdGeom.Xformable(new_prim)
                        new_xform.ClearXformOpOrder()
                        translate_op = new_xform.AddTranslateOp()
                        rotate_op = new_xform.AddRotateXYZOp()
                        scale_op = new_xform.AddScaleOp()

                        translate_op.Set(translation)
                        rotate_op.Set(rotation)
                        scale_op.Set(scale)

                        stage.RemovePrim(old_path)

                        # set to invisible (will annoy artists)
                        curr_prim = stage.GetPrimAtPath(new_path)
                        if curr_prim.IsValid():
                            curr_prim.GetAttribute("visibility").Set(UsdGeom.Tokens.invisible)

            # Print geometry hierarchy to help debug prim path issues
            print_geometry_hierarchy(stage, geo_scope_path)

        stage.Save()

        # Dense caption global
        if global_caption and defaultPrim and defaultPrim.IsValid():
            default_prim = stage.GetPrimAtPath(defaultPrim.GetPath())
            if default_prim and default_prim.IsValid():
                existing_attr = default_prim.GetAttribute("omni:simready:documentation")
                if existing_attr:
                    default_prim.RemoveProperty("omni:simready:documentation")

                # Create the dense caption attribute on the defaultPrim
                caption_attr = default_prim.CreateAttribute("omni:simready:documentation", Sdf.ValueTypeNames.String)
                caption_attr.Set(str(global_caption))

        # Validate the stage
        # Disable this for now... will update when i get the full scope of the validator
        # print (f"Validating stage: {root_layer.realPath}")
        # input_uri, filename_full = os.path.split(str(root_layer.realPath))
        # filename = os.path.splitext(filename_full)[0]
        # output_uri = input_uri
        # os.makedirs(output_uri, exist_ok=True)  # Create directory if it doesn't exist
        # asset_type = "prop"
        # validate_stage(stage, input_uri, filename, asset_type, output_uri)


def get_mesh_physics_properties(mesh_prim) -> tuple[float, Gf.Vec3f, Gf.Vec3d]:
    """
    Extracts mass, center of mass, inertia, and principal axis properties from a mesh prim.
    Returns a tuple of (mass, center_of_mass, inertia, principal_axes) with default values if not found.
    """
    mass = 0.0
    center_of_mass = Gf.Vec3f(0.0, 0.0, 0.0)
    inertia = None
    principal_axes = None

    for attr in mesh_prim.GetAttributes():
        if attr.GetName() == "pxr:usd:physics_mass":
            mass = attr.Get()
        elif attr.GetName() == "pxr:usd:physics_centerofmass":
            center_of_mass = attr.Get()
        elif attr.GetName() == "pxr:usd:physics_inertia":
            inertia = attr.Get()
        elif attr.GetName() == "pxr:physics:principalAxes":
            # Retrieve as quaternion if stored as Quatf, otherwise convert from list/Vec4f
            principal_axes = attr.Get()

    return mass, center_of_mass, inertia, principal_axes


def create_and_bind_material(prim, stage, root_path):
    """
    Create a material for a BasisCurves prim based on its name and bind it.

    Args:
        prim: The BasisCurves prim
        stage: The USD stage
        root_path: Root path for material creation
    """
    # Get the prim name for the material
    prim_name = prim.GetName()
    material_name = f"mat_{prim_name}"

    # Define material path under Materials scope
    material_path = f"{root_path}/Materials/{material_name}"

    # Check if material already exists
    existing_material = stage.GetPrimAtPath(material_path)
    if existing_material.IsValid():
        # Material already exists, just bind it
        material = UsdShade.Material(existing_material)
    else:
        # Create new material
        material = UsdShade.Material.Define(stage, material_path)

        # Create a PreviewSurface shader for the curve
        shader = UsdShade.Shader.Define(stage, f"{material_path}/PreviewSurface")
        shader.CreateIdAttr("UsdPreviewSurface")

        # Set a default color (can be customized)
        # Using a visible color for curves - bright cyan/blue
        diffuse_color_input = shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f)
        diffuse_color_input.Set(Gf.Vec3f(0.0, 0.8, 1.0))

        # Set emissive color to make curves more visible
        emissive_color_input = shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f)
        emissive_color_input.Set(Gf.Vec3f(0.0, 0.4, 0.5))

        # Create shader output
        shader_output = shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)

        # Connect material surface output to shader
        material_surface_output = material.CreateSurfaceOutput()
        material_surface_output.ConnectToSource(shader_output)

    # Bind material to the curve prim
    binding_api = UsdShade.MaterialBindingAPI.Apply(prim)
    binding_api.Bind(material)

    print(f"✅ Created and bound material '{material_name}' to curve '{prim.GetPath()}'")


def set_usd_curve_attrs(prim):
    """set curve widths to something reasonable and ensure xform ops exist"""
    curves = UsdGeom.Curves(prim)
    curves.GetWidthsAttr().Set([0.01, 0.01])

    # Ensure the curve has xform ops (required for tests)
    xformable = UsdGeom.Xformable(prim)

    # Check if xformOpOrder exists and has operations
    if not xformable.GetXformOpOrderAttr().HasValue():
        # Add basic transform operations if none exist
        xformable.ClearXformOpOrder()
        xformable.AddTranslateOp()
        xformable.AddRotateXYZOp()
        xformable.AddScaleOp()
        print(f"  ⮑ Added Xformable operations to curve '{prim.GetPath()}'")
    else:
        # Verify the operations are valid
        xform_ops = xformable.GetOrderedXformOps()
        if not xform_ops:
            # If xformOpOrder exists but no valid ops, clear and add defaults
            xformable.ClearXformOpOrder()
            xformable.AddTranslateOp()
            xformable.AddRotateXYZOp()
            xformable.AddScaleOp()
            print(f"  ⮑ Reset invalid Xformable operations on curve '{prim.GetPath()}'")


def validate_orm_texture_settings(stage):
    """
    Validate ORM texture settings across all materials in a USD stage.

    When enable_ORM_texture is True, the individual texture influences MUST be 0.0
    because roughness and metallic data come from the ORM texture's channels:
    - O channel = Occlusion (AO)
    - R channel = Roughness
    - M channel = Metallic

    Args:
        stage: USD stage to validate

    Returns:
        dict: {
            'total_materials': int,
            'materials_with_orm': int,
            'valid_materials': int,
            'invalid_materials': list of dict with {
                'material_name': str,
                'shader_path': str,
                'issues': list of str
            }
        }
    """
    result = {"total_materials": 0, "materials_with_orm": 0, "valid_materials": 0, "invalid_materials": []}

    # Traverse all materials in the stage
    for prim in stage.Traverse():
        if prim.GetTypeName() != "Material":
            continue

        result["total_materials"] += 1
        material_name = prim.GetName()

        # Get UsdShade.Material
        usd_material = UsdShade.Material(prim)

        # Check both surface outputs (standard and MDL)
        outputs_to_check = [usd_material.GetSurfaceOutput(), usd_material.GetOutput("mdl:surface")]

        for surface_output in outputs_to_check:
            if not surface_output or not surface_output.HasConnectedSource():
                continue

            # Get connected shader
            connected = surface_output.GetConnectedSource()
            if not connected:
                continue

            shader_source = connected[0]
            shader_prim = shader_source.GetPrim() if shader_source else None  # noqa F841

            if not shader_prim:
                continue

            shader = UsdShade.Shader(shader_prim)
            shader_id = shader.GetShaderId()

            # Only check OmniPBR shaders (MDL shaders that support ORM)
            if "OmniPBR" not in str(shader_id) and "mdl:" not in str(shader_id):
                continue

            # Check for enable_ORM_texture input
            enable_orm_input = shader.GetInput("enable_ORM_texture")
            if not enable_orm_input:
                continue

            enable_orm_attr = enable_orm_input.GetAttr()
            if not enable_orm_attr or not enable_orm_attr.HasValue():
                continue

            enable_orm = enable_orm_attr.Get()
            if not enable_orm:
                continue

            # Material has ORM enabled
            result["materials_with_orm"] += 1
            issues = []

            # Check roughness influence
            roughness_input = shader.GetInput("reflection_roughness_texture_influence")
            if roughness_input:
                roughness_attr = roughness_input.GetAttr()
                if roughness_attr and roughness_attr.HasValue():
                    roughness_val = roughness_attr.Get()
                    if roughness_val != 0.0:
                        issues.append(
                            f"reflection_roughness_texture_influence = {roughness_val} (should be 0.0 when ORM is enabled)"
                        )

            # Check metallic influence
            metallic_input = shader.GetInput("metallic_texture_influence")
            if metallic_input:
                metallic_attr = metallic_input.GetAttr()
                if metallic_attr and metallic_attr.HasValue():
                    metallic_val = metallic_attr.Get()
                    if metallic_val != 0.0:
                        issues.append(
                            f"metallic_texture_influence = {metallic_val} (should be 0.0 when ORM is enabled)"
                        )

            # Record results
            if issues:
                result["invalid_materials"].append(
                    {"material_name": material_name, "shader_path": str(shader_prim.GetPath()), "issues": issues}
                )
            else:
                result["valid_materials"] += 1

    return result
