# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

"""
SimReady USD Import Operator

This module provides roundtrip import functionality for SimReady USD assets
that were exported from Blender using the SimReadyUSDHook.

Key Features:
- Imports USD hierarchy into organized Blender collections
- Converts UsdPreviewSurface materials to Principled BSDF
- Reconstructs SimReady metadata and custom attributes
- Rebuilds constraints from USD Collections
- Imports physics data (joints, colliders, rigid bodies)
- Handles grasp curves and reference prims

See SIMREADY_USD_ROUNDTRIP_ANALYSIS.md for detailed documentation.
"""

import math
import os

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

try:
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade  # noqa F403

    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False
    print("Warning: USD Python bindings not available. SimReady USD import will not work.")


class SIMREADY_OT_import_usd(Operator, ImportHelper):
    """Import SimReady USD file with full metadata reconstruction"""

    bl_idname = "simready.import_usd"
    bl_label = "Import SimReady USD"
    bl_options = {"REGISTER", "UNDO"}

    # File browser properties
    filename_ext = ".usd;.usda;.usdc"
    filter_glob: StringProperty(default="*.usd;*.usda;*.usdc", options={"HIDDEN"})

    # Import options
    # NOTE: Material import is handled automatically by Blender's native USD importer
    # import_materials: BoolProperty(
    #     name="Import Materials",
    #     description="Convert UsdPreviewSurface materials to Blender Principled BSDF",
    #     default=True
    # )

    import_metadata: BoolProperty(
        name="Import Metadata", description="Import SimReady custom attributes and metadata", default=True
    )

    import_physics: BoolProperty(
        name="Import Physics",
        description="Reconstruct physics joints, colliders, and rigid body properties",
        default=True,
    )

    import_collections: BoolProperty(
        name="Reconstruct Collections",
        description="Rebuild Blender collections (Geometry, Grasp, Colliders, etc.)",
        default=True,
    )

    import_constraints: BoolProperty(
        name="Reconstruct Constraints", description="Rebuild Blender constraints from USD Collections", default=True
    )

    organize_hierarchy: BoolProperty(
        name="Organize Hierarchy", description="Reorganize imported objects into SimReady structure", default=True
    )

    @classmethod
    def poll(cls, context):
        return USD_AVAILABLE

    def execute(self, context):
        if not USD_AVAILABLE:
            self.report({"ERROR"}, "USD Python bindings not available. Cannot import USD files.")
            return {"CANCELLED"}

        filepath = self.filepath

        if not os.path.exists(filepath):
            self.report({"ERROR"}, f"File not found: {filepath}")
            return {"CANCELLED"}

        try:
            # Open USD stage
            stage = Usd.Stage.Open(filepath)
            if not stage:
                self.report({"ERROR"}, f"Failed to open USD stage: {filepath}")
                return {"CANCELLED"}

            # Validate SimReady metadata
            is_simready = self.validate_simready_stage(stage)
            if not is_simready:
                self.report(
                    {"WARNING"},
                    "This USD file does not appear to be a SimReady export. "
                    "Attempting import anyway, but some features may not work correctly.",
                )

            # Import using native Blender USD importer first
            self.report({"INFO"}, "Importing USD file using Blender's native importer...")
            bpy.ops.wm.usd_import(filepath=filepath)

            # Post-process to reconstruct SimReady structure
            self.report({"INFO"}, "Post-processing: Reconstructing SimReady structure...")

            if self.organize_hierarchy:
                self.reorganize_hierarchy(stage)

            # Rename _mesh objects to _obj (SimReady naming convention)
            self.rename_mesh_to_obj()

            # NOTE: Blender's native USD importer already handles UsdPreviewSurface → Principled BSDF
            # conversion perfectly. We don't need to do anything extra for materials!
            # Just leaving this here in case we need SimReady-specific material processing later.
            # if self.import_materials:
            #     self.import_simready_materials(stage)

            if self.import_metadata:
                self.import_simready_metadata(stage)

            if self.import_collections:
                self.reconstruct_collections(stage)

            if self.import_constraints:
                self.reconstruct_constraints(stage)

            if self.import_physics:
                self.import_physics_data(stage)

            # Process PhysicsJoint prims and create reference prim empties
            # This must happen BEFORE import_physics_joints since that method
            # expects the reference prims to exist
            if self.import_physics:
                self.process_physics_joint_prims(stage)

            # Import and reconstruct physics joints from USD
            if self.import_physics:
                self.import_physics_joints(stage)

            # Create hierarchy between reference prims (joint chain)
            if self.import_physics:
                self.create_reference_prim_hierarchy()

            # Reconstruct physics visualizers (joint widgets with gizmos)
            if self.import_physics:
                self.reconstruct_physics_visualizers()

            # Trigger physics auto-sync system to start working
            self.trigger_physics_sync()

            self.report({"INFO"}, f"Successfully imported SimReady USD: {os.path.basename(filepath)}")
            return {"FINISHED"}

        except Exception as e:
            import traceback

            self.report({"ERROR"}, f"Failed to import USD: {str(e)}")
            traceback.print_exc()
            return {"CANCELLED"}

    def validate_simready_stage(self, stage):
        """Check if this is a valid SimReady USD export"""
        root_layer = stage.GetRootLayer()
        if not root_layer:
            return False

        custom_data = root_layer.customLayerData
        if not custom_data:
            return False

        simready_metadata = custom_data.get("SimReady_Metadata", None)
        if simready_metadata:
            print(f"Found SimReady metadata: {simready_metadata}")
            return True

        return False

    def set_constraint_inverse(self, obj, constraint):
        """Set the inverse matrix for a CHILD_OF constraint to preserve current transform

        This is equivalent to calling bpy.ops.constraint.childof_set_inverse()
        but works without requiring context override.
        """
        if constraint.type != "CHILD_OF" or not constraint.target:
            return

        # Calculate and set the inverse matrix
        # This preserves the object's current world transform
        constraint.inverse_matrix = constraint.target.matrix_world.inverted()
        print(f"        Set inverse matrix for constraint '{constraint.name}' on {obj.name}")

    def reorganize_hierarchy(self, stage):
        """Reorganize imported USD hierarchy into Blender collections"""
        print("Reorganizing hierarchy...")

        # USD Scopes get imported as Empty objects - we need to clean them up
        # Common scope names from SimReady USD export
        scope_names = [
            "RootNode",
            "Geometry",
            "Materials",
            "Grasp",
            "ReferencePrims",
            "Colliders",
            "Joints",
            "PhysicsMaterials",
        ]

        # First, unparent children of scope empties and delete the scopes
        print("Cleaning up USD Scope empties...")
        for scope_name in scope_names:
            scope_obj = bpy.data.objects.get(scope_name)
            if scope_obj and scope_obj.type == "EMPTY":
                print(f"  Processing scope: {scope_name}")

                # Unparent all children while keeping world transform
                children = [child for child in scope_obj.children]
                for child in children:
                    # Store world matrix
                    world_matrix = child.matrix_world.copy()
                    # Unparent
                    child.parent = None
                    # Restore world transform
                    child.matrix_world = world_matrix
                    print(f"    Unparented: {child.name}")

                # Remove from all collections
                for col in scope_obj.users_collection:
                    col.objects.unlink(scope_obj)

                # Delete the empty
                bpy.data.objects.remove(scope_obj, do_unlink=True)
                print(f"  Deleted scope empty: {scope_name}")

        # Now create our organized collections
        # Note: Materials scope exists in USD but not needed in Blender (materials are on meshes)
        # Note: Grasp objects go into Geometry collection
        collection_names = ["Geometry", "ReferencePrims", "Colliders"]
        export_col = bpy.data.collections.new("Export")

        bpy.context.scene.collection.children.link(export_col)

        for col_name in collection_names:
            if col_name not in bpy.data.collections:
                collection = bpy.data.collections.new(col_name)
                bpy.context.scene.collection.children.link(collection)
                print(f"Created collection: {col_name}")

            if collection.name not in export_col.children:
                export_col.children.link(collection)
                print(f"Linked collection: {col_name} to Export collection")
                bpy.context.scene.collection.children.unlink(collection)

        # Move objects to appropriate collections based on their names/types
        all_objects = list(bpy.context.scene.objects)
        print(f"  Processing {len(all_objects)} objects for sorting...")

        for obj in all_objects:
            # Get the original USD path if stored
            usd_path = obj.get("usd_path", "")  # noqa F841
            obj_name = obj.name.lower()

            # Determine which collection this object belongs to
            target_collection = None

            # Check for joint_ prefix FIRST (before checking for _joint suffix)
            # These are USD-generated PhysicsJoint empties - we need to process them
            if obj.name.startswith("joint_"):
                print(f"  Found USD PhysicsJoint object: {obj.name}")
                # Keep these for now - we'll process them later to create reference prims
                target_collection = "ReferencePrims"
                # Don't skip - move to ReferencePrims and continue processing

            # Grasp objects (curves/identifiers) go into Geometry collection
            if "identifier" in obj_name or "grasp" in obj_name:
                target_collection = "Geometry"
            # Regular meshes (not colliders) go into Geometry
            elif obj.type == "MESH" and "collider" not in obj_name and "collision" not in obj_name:
                target_collection = "Geometry"
            # Curves also go into Geometry (for grasp vectors)
            elif obj.type == "CURVE":
                target_collection = "Geometry"
            # Joint markers and empties go into ReferencePrims
            elif "_joint" in obj_name or obj.type == "EMPTY":
                target_collection = "ReferencePrims"
            # Colliders go into Colliders collection
            elif "collider" in obj_name or "collision" in obj_name:
                target_collection = "Colliders"

            # Move to target collection if determined
            if target_collection:
                self.move_to_collection(obj, target_collection)
                # Remove from Scene Collection if not already
                scene_col = bpy.context.scene.collection
                if obj in scene_col.objects[:]:
                    scene_col.objects.unlink(obj)

    def rename_mesh_to_obj(self):
        """Rename all objects ending with _mesh to _obj (SimReady naming convention)"""
        print("Renaming _mesh objects to _obj...")

        # Find all objects ending with _mesh
        objects_to_rename = []
        for obj in bpy.data.objects:
            if "mesh" in obj.name:
                objects_to_rename.append(obj)

        # Rename them
        for obj in objects_to_rename:
            old_name = obj.name
            # Replace _mesh suffix with _obj
            new_name = old_name.replace("_mesh", "_obj")

            # Check if name already exists
            if new_name in bpy.data.objects:
                print(f"  Warning: Object '{new_name}' already exists, skipping rename of '{old_name}'")
                continue

            obj.name = new_name
            print(f"  Renamed: {old_name} → {new_name}")

        print(f"  Renamed {len(objects_to_rename)} objects from _mesh to _obj")

    def move_to_collection(self, obj, collection_name):
        """Move an object to a specific collection"""
        target_collection = bpy.data.collections.get(collection_name)
        if not target_collection:
            print(f"    Warning: Collection '{collection_name}' not found")
            return

        # Check if already in target collection
        if obj.name in target_collection.objects:
            return

        # Remove from all other collections first (but keep a list to check)
        for col in list(obj.users_collection):
            if col != target_collection:
                col.objects.unlink(obj)

        # Add to target collection
        if obj.name not in target_collection.objects:
            target_collection.objects.link(obj)
            print(f"    Moved '{obj.name}' to collection '{collection_name}'")

    def import_simready_materials(self, stage):
        """Import and convert UsdPreviewSurface materials to Blender Principled BSDF"""
        print("Importing materials...")

        # Find all Material prims in stage
        for prim in stage.Traverse():
            if prim.GetTypeName() != "Material":
                continue

            material_name = prim.GetName()
            print(f"Processing material: {material_name}")

            # Check if material already exists in Blender
            blender_mat = bpy.data.materials.get(material_name)
            if not blender_mat:
                print(f"  Material '{material_name}' not found in Blender, skipping")
                continue

            # Get UsdShade.Material
            usd_material = UsdShade.Material(prim)

            # Find UsdPreviewSurface shader
            surface_output = usd_material.GetSurfaceOutput()
            if not surface_output or not surface_output.HasConnectedSource():
                print(f"  No surface output found for '{material_name}'")
                continue

            # Get connected shader
            shader_source = surface_output.GetConnectedSource()[0]
            shader_prim = shader_source.GetPrim() if shader_source else None

            if not shader_prim:
                print(f"  No shader prim found for '{material_name}'")
                continue

            shader = UsdShade.Shader(shader_prim)
            shader_id = shader.GetShaderId()

            # Only process UsdPreviewSurface shaders
            if shader_id != "UsdPreviewSurface":
                print(f"  Shader is not UsdPreviewSurface (it's '{shader_id}'), skipping")
                continue

            print("  Found UsdPreviewSurface shader, converting...")
            self.convert_usd_preview_surface(blender_mat, shader)

    def convert_usd_preview_surface(self, blender_mat, usd_shader):
        """Convert a UsdPreviewSurface shader to Blender Principled BSDF"""

        if not blender_mat.use_nodes:
            blender_mat.use_nodes = True

        nodes = blender_mat.node_tree.nodes
        links = blender_mat.node_tree.links

        # Find or create Principled BSDF
        principled = None
        for node in nodes:
            if node.type == "BSDF_PRINCIPLED":
                principled = node
                break

        if not principled:
            principled = nodes.new("ShaderNodeBsdfPrincipled")
            principled.location = (0, 0)

        # Find Material Output
        output_node = None
        for node in nodes:
            if node.type == "OUTPUT_MATERIAL":
                output_node = node
                break

        if not output_node:
            output_node = nodes.new("ShaderNodeOutputMaterial")
            output_node.location = (300, 0)

        # Connect Principled to Output if not already
        if not output_node.inputs["Surface"].is_linked:
            links.new(principled.outputs["BSDF"], output_node.inputs["Surface"])

        # Map UsdPreviewSurface inputs to Principled BSDF
        input_mapping = {
            "diffuseColor": "Base Color",
            "metallic": "Metallic",
            "roughness": "Roughness",
            "opacity": "Alpha",
            "emissiveColor": "Emission",
            "ior": "IOR",
            "normal": "Normal",
        }

        for usd_input_name, blender_input_name in input_mapping.items():
            usd_input = usd_shader.GetInput(usd_input_name)
            if not usd_input:
                continue

            # Check if input is connected to a texture
            # GetConnectedSource returns (source, sourceName, sourceType) tuple or empty tuple
            connected_source = usd_input.GetConnectedSource()
            if connected_source and len(connected_source) > 0:
                # Handle texture connection
                source_shader = connected_source[0]  # This is the UsdShade.Shader or ConnectableAPI

                # Get the prim from the source
                try:
                    if hasattr(source_shader, "GetPrim"):
                        source_prim = source_shader.GetPrim()
                    else:
                        # Try to cast to Shader first
                        source_prim = UsdShade.Shader(source_shader).GetPrim()

                    if source_prim and source_prim.IsValid():
                        texture_shader = UsdShade.Shader(source_prim)
                        self.connect_texture(
                            blender_mat, texture_shader, principled, blender_input_name, usd_input_name
                        )
                        print(f"    Connected texture for '{usd_input_name}'")
                    else:
                        print(f"    Warning: Could not get valid prim for connected source on '{usd_input_name}'")
                        # Fall back to value
                        value = usd_input.Get()
                        if value is not None:
                            self.set_principled_input(principled, blender_input_name, value)
                except Exception as e:
                    print(f"    Error connecting texture for '{usd_input_name}': {e}")
                    # Fall back to value
                    value = usd_input.Get()
                    if value is not None:
                        self.set_principled_input(principled, blender_input_name, value)
            else:
                # Handle value input
                value = usd_input.Get()
                if value is not None:
                    self.set_principled_input(principled, blender_input_name, value)

        # Handle opacity for blend mode
        opacity_input = usd_shader.GetInput("opacity")
        if opacity_input:
            opacity_value = opacity_input.Get()
            if opacity_value is not None and opacity_value < 1.0:
                blender_mat.blend_method = "BLEND"
                blender_mat.shadow_method = "CLIP"

        print("    Converted UsdPreviewSurface to Principled BSDF")

    def connect_texture(self, blender_mat, texture_shader, principled, principled_input_name, usd_input_name):
        """Connect a texture node to Principled BSDF input"""

        # Get texture file path
        file_input = texture_shader.GetInput("file")
        if not file_input:
            print(f"      No 'file' input found on texture shader for '{usd_input_name}'")
            return

        file_path = file_input.Get()
        if not file_path:
            print(f"      No file path value for '{usd_input_name}'")
            return

        # Resolve relative path
        file_path = str(file_path)
        original_path = file_path

        # USD paths might be relative - try to resolve them
        if not os.path.isabs(file_path):
            # Try resolving with USD's path resolution
            try:
                resolved = file_input.GetAttr().GetResolveInfo().assetInfo.resolvedPath
                if resolved:
                    file_path = str(resolved)
            except Exception:
                pass

            # If still not absolute and doesn't exist, try relative to USD file
            if not os.path.isabs(file_path) and not os.path.exists(file_path):
                # Get USD file directory from context if available
                if hasattr(self, "filepath") and self.filepath:
                    usd_dir = os.path.dirname(self.filepath)
                    potential_path = os.path.join(usd_dir, file_path)
                    if os.path.exists(potential_path):
                        file_path = potential_path

        # Create or find existing image texture node
        nodes = blender_mat.node_tree.nodes
        links = blender_mat.node_tree.links

        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.location = (-400, 0)
        tex_node.label = f"{usd_input_name}_tex"

        # Load image
        if os.path.exists(file_path):
            try:
                tex_node.image = bpy.data.images.load(file_path, check_existing=True)

                # Set colorspace based on input type
                if usd_input_name in ["normal", "roughness", "metallic"]:
                    tex_node.image.colorspace_settings.name = "Non-Color"
                else:
                    tex_node.image.colorspace_settings.name = "sRGB"

                print(f"      Loaded texture: {os.path.basename(file_path)}")
            except Exception as e:
                print(f"      Error loading texture '{file_path}': {e}")
                return
        else:
            print(f"      Warning: Texture file not found: {file_path} (original: {original_path})")
            # Create placeholder texture node anyway for reference
            tex_node.label = f"MISSING: {os.path.basename(original_path)}"

        # Handle normal map specially
        if principled_input_name == "Normal":
            normal_map = nodes.new("ShaderNodeNormalMap")
            normal_map.location = (-200, -200)
            links.new(tex_node.outputs["Color"], normal_map.inputs["Color"])
            links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])
        else:
            # Direct connection
            if principled_input_name in principled.inputs:
                links.new(tex_node.outputs["Color"], principled.inputs[principled_input_name])

    def set_principled_input(self, principled, input_name, value):
        """Set a Principled BSDF input value"""

        if input_name not in principled.inputs:
            return

        input_socket = principled.inputs[input_name]

        # Handle different value types
        if isinstance(value, (Gf.Vec3f, Gf.Vec3d)):
            input_socket.default_value = (value[0], value[1], value[2], 1.0)
        elif isinstance(value, (float, int)):
            input_socket.default_value = float(value)
        elif isinstance(value, (list, tuple)) and len(value) >= 3:
            input_socket.default_value = (value[0], value[1], value[2], 1.0)

    def import_simready_metadata(self, stage):
        """Import SimReady custom attributes and metadata"""
        print("Importing SimReady metadata...")

        # Get default prim (root)
        default_prim = stage.GetDefaultPrim()
        if not default_prim or not default_prim.IsValid():
            print("  No valid default prim found")
            return

        # Import global metadata to scene properties
        scene = bpy.context.scene

        # Wikidata class
        class_attr = default_prim.GetAttribute("semantics:labels:wikidata_class")
        if class_attr:
            value = class_attr.Get()
            if value and len(value) > 0:
                if hasattr(scene, "global_metadata"):
                    scene.global_metadata.wikidata_query = str(value[0])
                    print(f"  Imported wikidata_query: {value[0]}")

        # Wikidata QCode
        qcode_attr = default_prim.GetAttribute("semantics:labels:wikidata_qcode")
        if qcode_attr:
            value = qcode_attr.Get()
            if value and len(value) > 0:
                if hasattr(scene, "global_metadata"):
                    scene.global_metadata.wikidata_result_id = str(value[0])
                    print(f"  Imported wikidata_qcode: {value[0]}")

        # Dense caption (documentation)
        doc_attr = default_prim.GetAttribute("omni:simready:documentation")
        if doc_attr:
            value = doc_attr.Get()
            if value:
                if hasattr(scene, "global_metadata"):
                    scene.global_metadata.global_caption = str(value)
                    print(f"  Imported dense caption: {value[:50]}...")

        # Import custom attributes on all prims
        for prim in stage.Traverse():
            self.import_prim_custom_attributes(prim)

    def import_prim_custom_attributes(self, prim):
        """Import custom attributes from a USD prim to corresponding Blender object"""

        # Find corresponding Blender object
        prim_name = prim.GetName()
        obj = bpy.data.objects.get(prim_name)

        if not obj:
            return

        # List of SimReady custom attribute prefixes to import
        custom_attr_prefixes = [
            "omni:simready:",
            "pxr:usd:physics",
            "semantics:",
            "userProperties:",
        ]

        for attr in prim.GetAttributes():
            attr_name = attr.GetName()

            # Check if this is a custom attribute we care about
            if not any(attr_name.startswith(prefix) for prefix in custom_attr_prefixes):
                continue

            # Get value
            value = attr.Get()
            if value is None:
                continue

            # Convert USD value to Python/Blender compatible type
            py_value = self.convert_usd_value_to_python(value)

            # Store as custom property on Blender object
            obj[attr_name] = py_value
            print(f"  Imported custom attribute '{attr_name}' = {py_value} on {obj.name}")

    def convert_usd_value_to_python(self, value):
        """Convert USD attribute value to Python type"""

        if isinstance(value, (Gf.Vec2d, Gf.Vec2f, Gf.Vec2i)):
            return [value[0], value[1]]
        elif isinstance(value, (Gf.Vec3d, Gf.Vec3f, Gf.Vec3i)):
            return [value[0], value[1], value[2]]
        elif isinstance(value, (Gf.Vec4d, Gf.Vec4f, Gf.Vec4i)):
            return [value[0], value[1], value[2], value[3]]
        elif isinstance(value, (list, tuple)):
            return [self.convert_usd_value_to_python(v) for v in value]
        elif isinstance(value, str):
            return value
        elif isinstance(value, (int, float, bool)):
            return value
        else:
            # Fallback to string representation
            return str(value)

    def reconstruct_collections(self, stage):
        """Reconstruct Blender collections from USD structure"""
        print("Reconstructing collections...")
        # Most of this is already done in reorganize_hierarchy
        # This is a placeholder for more complex collection logic
        pass

    def reconstruct_constraints(self, stage):
        """Reconstruct Blender constraints from USD Collections

        Collections can be on either:
        1. Reference prims (Blender exports)
        2. Joint prims (non-Blender exports)

        This method handles both cases.
        """
        print("Reconstructing constraints from USD Collections...")

        # Find all prims with USD Collections
        for prim in stage.Traverse():
            # Check if prim has any collections
            collections = Usd.CollectionAPI.GetAllCollections(prim)

            if not collections:
                continue

            prim_name = prim.GetName()
            prim_type = prim.GetTypeName()

            print(f"  Found collections on prim: {prim_name} (type: {prim_type})")

            # Determine if this is a Joint prim or a reference prim
            is_joint_prim = prim_type in [
                "PhysicsRevoluteJoint",
                "PhysicsPrismaticJoint",
                "PhysicsDistanceJoint",
                "PhysicsFixedJoint",
                "PhysicsSphericalJoint",
                "PhysicsJoint",
            ]

            if is_joint_prim:
                # For Joint prims, we need to find the corresponding reference prim
                # The joint stores body1 reference which tells us which body this joint moves
                body1_rel = prim.GetRelationship("physics:body1")
                if not body1_rel:
                    print(f"    Warning: Joint {prim_name} has no body1 relationship")
                    continue

                body1_targets = body1_rel.GetTargets()
                if not body1_targets:
                    print(f"    Warning: Joint {prim_name} has empty body1 targets")
                    continue

                # Get the body1 prim (this is the Mesh)
                body1_mesh_prim = stage.GetPrimAtPath(body1_targets[0])
                if not body1_mesh_prim or not body1_mesh_prim.IsValid():
                    print(f"    Warning: Could not find body1 mesh for joint {prim_name}")
                    continue

                # Get the parent Xform of the Mesh
                body1_xform_prim = body1_mesh_prim.GetParent()
                if not body1_xform_prim or not body1_xform_prim.IsValid():
                    print("    Warning: Could not find parent Xform for body1 mesh")
                    continue

                body1_xform_name = body1_xform_prim.GetName()

                # Find the corresponding reference prim (_joint empty) in Blender
                # Convention: remove _obj suffix and add _joint
                base_name = body1_xform_name.replace("_obj_01", "").replace("_obj", "")
                ref_prim_name = f"{base_name}_joint"

                ref_obj = bpy.data.objects.get(ref_prim_name)
                if not ref_obj:
                    print(f"    Warning: Reference prim '{ref_prim_name}' not found in Blender")
                    print(f"    (derived from body1_xform: {body1_xform_name})")
                    continue

                print(f"    Joint {prim_name} → Reference prim: {ref_prim_name}")
            else:
                # For non-Joint prims (reference prims from Blender exports)
                ref_prim_name = prim_name
                ref_obj = bpy.data.objects.get(ref_prim_name)

                if not ref_obj:
                    print(f"    Warning: Reference object '{ref_prim_name}' not found in Blender")
                    continue

            # Now process the collections and create constraints
            for collection_api in collections:
                collection_name = collection_api.GetName()
                print(f"    Processing collection '{collection_name}'")

                # Get targets (objects to constrain)
                targets = collection_api.GetIncludesRel().GetTargets()

                for target_path in targets:
                    # Get target prim (this is usually a Mesh)
                    target_prim = stage.GetPrimAtPath(target_path)
                    if not target_prim or not target_prim.IsValid():
                        continue

                    # If target is a Mesh, get its parent Xform name
                    if target_prim.GetTypeName() == "Mesh":
                        target_xform = target_prim.GetParent()
                        if target_xform and target_xform.IsValid():
                            target_name = target_xform.GetName()
                        else:
                            target_name = target_prim.GetName()
                    else:
                        target_name = target_prim.GetName()

                    # Try to find the Blender object
                    # First try exact name, then try with _obj suffix replaced
                    target_obj = bpy.data.objects.get(target_name)
                    if not target_obj:
                        # Try replacing _mesh with _obj
                        alt_name = target_name.replace("_mesh", "_obj")
                        target_obj = bpy.data.objects.get(alt_name)

                    if not target_obj:
                        print(f"      Warning: Target object '{target_name}' not found in Blender")
                        continue

                    # Create CHILD_OF constraint from target to reference
                    # Check if constraint already exists
                    existing_constraint = None
                    for con in target_obj.constraints:
                        if con.type == "CHILD_OF" and con.target == ref_obj:
                            existing_constraint = con
                            break

                    if not existing_constraint:
                        constraint = target_obj.constraints.new("CHILD_OF")
                        constraint.target = ref_obj
                        constraint.name = f"SimReady_{collection_name}"
                        self.set_constraint_inverse(target_obj, constraint)
                        print(f"      ✅ Created constraint: {target_obj.name} → {ref_obj.name}")
                    else:
                        print(f"      Constraint already exists: {target_obj.name} → {ref_obj.name}")

    def import_physics_data(self, stage):
        """Import physics data (joints, colliders, rigid bodies)"""
        print("Importing physics data...")

        # This is a complex operation that would require:
        # 1. Finding all UsdPhysics.Joint prims
        # 2. Creating empties or constraints to represent them
        # 3. Storing joint properties as custom properties
        # 4. Finding rigid body prims and storing mass/inertia
        # 5. Moving colliders to proper locations

        # For now, we'll import basic physics properties as custom properties
        for prim in stage.Traverse():
            obj_name = prim.GetName()
            obj = bpy.data.objects.get(obj_name)

            if not obj:
                continue

            # Import mass
            mass_attr = prim.GetAttribute("physics:mass")
            if mass_attr:
                mass_value = mass_attr.Get()
                if mass_value is not None:
                    obj["physics:mass"] = float(mass_value)

            # Import center of mass
            com_attr = prim.GetAttribute("physics:centerOfMass")
            if com_attr:
                com_value = com_attr.Get()
                if com_value:
                    obj["physics:centerOfMass"] = [com_value[0], com_value[1], com_value[2]]

            # Import diagonal inertia
            inertia_attr = prim.GetAttribute("physics:diagonalInertia")
            if inertia_attr:
                inertia_value = inertia_attr.Get()
                if inertia_value:
                    obj["physics:diagonalInertia"] = [inertia_value[0], inertia_value[1], inertia_value[2]]

        print("  Physics import complete (basic properties only)")

    def import_physics_joints(self, stage):
        """Create constraints between _obj and _joint objects based on naming pattern"""
        print("Setting up physics joint constraints...")

        # Pattern: body_obj should be CHILD_OF body_joint
        # Find all objects ending in _obj and match them with _joint objects

        geometry_collection = bpy.data.collections.get("Geometry")
        reference_collection = bpy.data.collections.get("ReferencePrims")

        if not geometry_collection or not reference_collection:
            print("  Warning: Geometry or ReferencePrims collection not found")
            return

        # Process all objects in Geometry collection
        for obj in geometry_collection.objects:
            if not obj.name.endswith("_obj"):
                continue

            # Find matching _joint object
            # Pattern: "hinge_obj" matches "hinge_joint"
            base_name = obj.name[:-4]  # Remove "_obj" suffix
            joint_name = f"{base_name}_joint"

            # Look for the joint in ReferencePrims collection
            joint_obj = None
            for ref_obj in reference_collection.objects:
                if ref_obj.name == joint_name:
                    joint_obj = ref_obj
                    break

            if not joint_obj:
                print(f"  Warning: No matching joint found for {obj.name} (looking for {joint_name})")
                continue

            # Create CHILD_OF constraint: _obj (child) → _joint (parent)
            constraint = obj.constraints.new("CHILD_OF")
            constraint.target = joint_obj
            constraint.name = f"SimReady_Joint_{base_name}"

            print(f"    ✅ Created constraint: {obj.name} (child) → {joint_obj.name} (parent)")

        print("  Physics joint constraints complete")

    def process_physics_joint_prims(self, stage):
        """Process PhysicsJoint prims and create reference prim empties for each body"""
        print("Processing PhysicsJoint prims to create reference prims...")

        geometry_collection = bpy.data.collections.get("Geometry")
        reference_collection = bpy.data.collections.get("ReferencePrims")

        if not geometry_collection or not reference_collection:
            print("  Warning: Geometry or ReferencePrims collection not found")
            return

        # Find all PhysicsJoint prims in the USD stage
        joint_prims = []

        # Debug: print all prim types to see what we're dealing with
        print("  Scanning USD stage for physics joints...")
        print("  Sample of prim types found:")
        sample_count = 0
        for prim in stage.Traverse():
            type_name = prim.GetTypeName()
            prim_path = prim.GetPath()

            # Show first 20 prims to understand structure
            if sample_count < 20:
                print(f"    {prim_path} → type: '{type_name}'")
                sample_count += 1

            # Check if this prim has physics joint schema applied
            # Method 1: Check type name
            if type_name in [
                "PhysicsRevoluteJoint",
                "PhysicsPrismaticJoint",
                "PhysicsDistanceJoint",
                "PhysicsFixedJoint",
                "PhysicsSphericalJoint",
                "PhysicsJoint",
            ]:
                joint_prims.append(prim)
                print(f"  ✅ Found {type_name}: {prim.GetName()} at {prim_path}")
                continue

            # Method 2: Check if prim has physics:body0 and physics:body1 relationships
            # This is more reliable for detecting joints
            if prim.HasRelationship("physics:body0") and prim.HasRelationship("physics:body1"):
                joint_prims.append(prim)
                print(
                    f"  ✅ Found physics joint (by relationships): {prim.GetName()} at {prim_path} (type: {type_name})"
                )

        if not joint_prims:
            print("  ❌ No PhysicsJoint prims found in USD")
            print("  This might indicate:")
            print("    - The USD file doesn't have physics joints")
            print("    - The joints are in a different format")
            print("    - The USD Python bindings aren't recognizing the joint types")
            return

        # Track created reference prims to avoid duplicates
        created_ref_prims = {}

        # Process each joint
        for joint_prim in joint_prims:
            try:
                # Get body references
                body0_rel = joint_prim.GetRelationship("physics:body0")
                body1_rel = joint_prim.GetRelationship("physics:body1")

                if not body0_rel or not body1_rel:
                    print(f"    Warning: Joint {joint_prim.GetName()} missing body relationships")
                    continue

                body0_targets = body0_rel.GetTargets()
                body1_targets = body1_rel.GetTargets()

                if not body0_targets or not body1_targets:
                    print(f"    Warning: Joint {joint_prim.GetName()} has empty body targets")
                    continue

                # Get body prim paths
                body0_path = body0_targets[0]
                body1_path = body1_targets[0]
                body0_mesh_prim = stage.GetPrimAtPath(body0_path)
                body1_mesh_prim = stage.GetPrimAtPath(body1_path)

                if not body0_mesh_prim or not body1_mesh_prim:
                    print(f"    Warning: Could not find body prims for joint {joint_prim.GetName()}")
                    continue

                # CRITICAL: The body paths point to Mesh prims, but Blender imports the parent Xform
                # We need to get the parent Xform name, not the Mesh name
                # Example: /World/Geometry/lid_obj_01/lid_mesh_01 → we want "lid_obj_01"

                # Get parent Xform prims
                body0_xform_prim = body0_mesh_prim.GetParent()
                body1_xform_prim = body1_mesh_prim.GetParent()

                if not body0_xform_prim or not body0_xform_prim.IsValid():
                    print("    Warning: Could not find parent Xform for body0")
                    body0_xform_name = body0_mesh_prim.GetName()  # Fallback
                    body0_mesh_name = body0_mesh_prim.GetName()
                else:
                    body0_xform_name = body0_xform_prim.GetName()  # This is what Blender uses!
                    body0_mesh_name = body0_mesh_prim.GetName()

                if not body1_xform_prim or not body1_xform_prim.IsValid():
                    print("    Warning: Could not find parent Xform for body1")
                    body1_xform_name = body1_mesh_prim.GetName()  # Fallback
                    body1_mesh_name = body1_mesh_prim.GetName()
                else:
                    body1_xform_name = body1_xform_prim.GetName()  # This is what Blender uses!
                    body1_mesh_name = body1_mesh_prim.GetName()

                print(f"    Joint {joint_prim.GetName()}:")
                print(f"      body0_xform: {body0_xform_name} (mesh: {body0_mesh_name})")
                print(f"      body1_xform: {body1_xform_name} (mesh: {body1_mesh_name})")

                # Get joint type
                joint_type_str = joint_prim.GetTypeName().replace("Physics", "").replace("Joint", "").lower()

                # Get joint axis
                axis_attr = joint_prim.GetAttribute("physics:axis")
                axis = "Z"  # default
                if axis_attr and axis_attr.Get():
                    axis = str(axis_attr.Get()).upper()

                # Get joint limits
                lower_limit = None
                upper_limit = None

                if joint_type_str == "revolute":
                    lower_attr = joint_prim.GetAttribute("physics:lowerLimit")
                    upper_attr = joint_prim.GetAttribute("physics:upperLimit")
                    if lower_attr:
                        lower_limit = lower_attr.Get()
                    if upper_attr:
                        upper_limit = upper_attr.Get()
                elif joint_type_str == "prismatic":
                    lower_attr = joint_prim.GetAttribute("physics:lowerLimit")
                    upper_attr = joint_prim.GetAttribute("physics:upperLimit")
                    if lower_attr:
                        lower_limit = lower_attr.Get()
                    if upper_attr:
                        upper_limit = upper_attr.Get()

                # Get local positions (joint anchor points)
                localPos0_attr = joint_prim.GetAttribute("physics:localPos0")
                localPos1_attr = joint_prim.GetAttribute("physics:localPos1")

                localPos0 = None
                localPos1 = None

                if localPos0_attr and localPos0_attr.Get():
                    localPos0 = localPos0_attr.Get()
                    print(f"      localPos0: {localPos0}")

                if localPos1_attr and localPos1_attr.Get():
                    localPos1 = localPos1_attr.Get()
                    print(f"      localPos1: {localPos1}")

                # Create or get reference prim empties for both bodies
                # Reference prim naming convention: remove _obj suffix and add _joint
                def get_ref_prim_name(xform_name):
                    # Remove _obj_01 or _obj suffix if present
                    base_name = xform_name.replace("_obj_01", "").replace("_obj", "")
                    return f"{base_name}_joint"

                body0_ref_name = get_ref_prim_name(body0_xform_name)
                body1_ref_name = get_ref_prim_name(body1_xform_name)

                print(f"      body0_ref_name: {body0_ref_name}")
                print(f"      body1_ref_name: {body1_ref_name}")

                # Find the geometry objects in Blender (using Xform names, not Mesh names)
                body0_obj = bpy.data.objects.get(body0_xform_name)
                body1_obj = bpy.data.objects.get(body1_xform_name)

                if not body0_obj:
                    print(f"      Warning: Body0 object '{body0_xform_name}' not found in Blender")

                if not body1_obj:
                    print(f"      Warning: Body1 object '{body1_xform_name}' not found in Blender")
                    continue

                # Create reference prim empty for body1 (the moving part)
                # Position it using the body1 object's world transform
                if body1_ref_name not in created_ref_prims:
                    ref_empty = bpy.data.objects.new(body1_ref_name, None)
                    ref_empty.empty_display_type = "PLAIN_AXES"
                    ref_empty.empty_display_size = 0.2
                    reference_collection.objects.link(ref_empty)

                    # Use the full world transform of the body object
                    # This includes position, rotation, and scale
                    if body1_obj:
                        ref_empty.matrix_world = body1_obj.matrix_world.copy()
                        print(f"      Positioned {body1_ref_name} using world transform from {body1_xform_name}")
                        print(f"        Location: {ref_empty.location}")
                        print(f"        Rotation: {ref_empty.rotation_euler}")

                    # Store physics joint metadata on the reference prim
                    # Primary values use Xform names (what Blender uses)
                    ref_empty["pxr:usd:physics:joint:type"] = joint_type_str
                    ref_empty["pxr:usd:physics:joint:body0"] = (
                        body0_xform_name  # Use Xform name for Blender compatibility
                    )
                    ref_empty["pxr:usd:physics:joint:body1"] = (
                        body1_xform_name  # Use Xform name for Blender compatibility
                    )
                    ref_empty["pxr:usd:physics:joint:axis"] = axis

                    # Also store the original USD mesh names for reference
                    ref_empty["pxr:usd:physics:joint:body0_mesh"] = body0_mesh_name  # Original USD mesh name
                    ref_empty["pxr:usd:physics:joint:body1_mesh"] = body1_mesh_name  # Original USD mesh name

                    if lower_limit is not None:
                        ref_empty["pxr:usd:physics:joint:lowerLimit"] = float(lower_limit)
                    if upper_limit is not None:
                        ref_empty["pxr:usd:physics:joint:upperLimit"] = float(upper_limit)

                    if localPos0:
                        ref_empty["pxr:usd:physics:localPos0"] = [localPos0[0], localPos0[1], localPos0[2]]
                    if localPos1:
                        ref_empty["pxr:usd:physics:localPos1"] = [localPos1[0], localPos1[1], localPos1[2]]

                    created_ref_prims[body1_ref_name] = ref_empty
                    print(f"    ✅ Created reference prim: {body1_ref_name}")
                else:
                    ref_empty = created_ref_prims[body1_ref_name]
                    print(f"      Reference prim {body1_ref_name} already exists")

                # Create CHILD_OF constraint: body1_obj → ref_empty
                if body1_obj:
                    # Check if constraint already exists
                    has_constraint = False
                    for con in body1_obj.constraints:
                        if con.type == "CHILD_OF" and con.target == ref_empty:
                            has_constraint = True
                            break

                    if not has_constraint:
                        constraint = body1_obj.constraints.new("CHILD_OF")
                        constraint.target = ref_empty
                        constraint.name = f"SimReady_Joint_{body1_ref_name}"
                        self.set_constraint_inverse(body1_obj, constraint)
                        print(f"      Created constraint: {body1_xform_name} → {body1_ref_name}")

            except Exception as e:
                print(f"    Error processing joint {joint_prim.GetName()}: {e}")
                import traceback

                traceback.print_exc()
                continue

        # Now delete the original joint_ objects from Blender (they were imported as empties)
        # We've extracted all the data we need from them
        for obj in list(bpy.data.objects):
            if obj.name.startswith("joint_"):
                print(f"  Removing processed USD joint object: {obj.name}")
                for col in list(obj.users_collection):
                    col.objects.unlink(obj)
                bpy.data.objects.remove(obj, do_unlink=True)

        print(f"  Created {len(created_ref_prims)} reference prim empties")

    def create_reference_prim_hierarchy(self):
        """Create CHILD_OF constraints between reference prims based on body0/body1 relationships

        The body0/body1 names stored on reference prims are now Xform names (e.g., "box_obj_01"),
        which directly match Blender object names. We just need to map them to reference prims.
        """
        print("Creating reference prim hierarchy...")

        # Find collections
        geometry_collection = bpy.data.collections.get("Geometry")
        reference_collection = bpy.data.collections.get("ReferencePrims")

        if not geometry_collection or not reference_collection:
            print("  Missing Geometry or ReferencePrims collection")
            return

        # Build a mapping from Xform name → Reference prim
        xform_to_joint_map = {}

        print("  Building xform → joint mapping...")

        # Map geometry objects to their reference prims via CHILD_OF constraints
        for geom_obj in geometry_collection.objects:
            # Find the CHILD_OF constraint that points to a joint in ReferencePrims
            for constraint in geom_obj.constraints:
                if constraint.type == "CHILD_OF" and constraint.target:
                    target = constraint.target
                    # Verify the target is in ReferencePrims collection
                    if target.name in reference_collection.objects:
                        xform_to_joint_map[geom_obj.name] = target
                        print(f"    {geom_obj.name} → {target.name}")
                        break

        print(f"  Mapped {len(xform_to_joint_map)} geometry objects to joints")

        # Process each _joint object to create joint-to-joint hierarchy
        for joint_obj in reference_collection.objects:

            # Get body0 (parent) and body1 (child) from custom properties
            # These are now Xform names (e.g., "box_obj_01", "lid_obj_01")
            body0_xform_name = joint_obj.get("pxr:usd:physics:joint:body0")
            body1_xform_name = joint_obj.get("pxr:usd:physics:joint:body1")

            if not body0_xform_name or not body1_xform_name:
                print(f"  Skipping {joint_obj.name}: missing body0/body1")
                continue

            print(f"  Processing {joint_obj.name}:")
            print(f"    body0 (xform): {body0_xform_name}")
            print(f"    body1 (xform): {body1_xform_name}")

            # Look up the reference prims for these xforms
            body0_joint = xform_to_joint_map.get(body0_xform_name)
            body1_joint = xform_to_joint_map.get(body1_xform_name)

            if body0_joint:
                print(f"    body0 joint: {body0_joint.name}")
            else:
                print(f"    body0 joint: None ('{body0_xform_name}' might be world/root)")

            if body1_joint:
                print(f"    body1 joint: {body1_joint.name}")
            else:
                print(f"    Warning: Body1 '{body1_xform_name}' has no joint")

            # If both are found and different, create joint hierarchy constraint
            # body1_joint becomes child of body0_joint
            if body0_joint and body1_joint and body0_joint != body1_joint:
                # Check if constraint already exists
                existing_constraint = None
                for con in body1_joint.constraints:
                    if con.type == "CHILD_OF" and con.target == body0_joint:
                        existing_constraint = con
                        break

                if not existing_constraint:
                    constraint = body1_joint.constraints.new("CHILD_OF")
                    constraint.target = body0_joint
                    constraint.name = "SimReady_JointHierarchy"
                    self.set_constraint_inverse(body1_joint, constraint)
                    print(f"    ✅ Created joint hierarchy: {body1_joint.name} (child) → {body0_joint.name} (parent)")
                else:
                    print(f"    Joint hierarchy constraint already exists: {body1_joint.name} → {body0_joint.name}")
            elif not body0_joint and body1_joint:
                # This is the root joint (no parent)
                print(f"    {body1_joint.name} is a root joint (no parent)")

        print("  Reference prim hierarchy complete")

    def reconstruct_physics_visualizers(self):
        """Reconstruct physics visualizers (joint widgets) from imported reference prims"""
        print("Reconstructing physics visualizers...")

        try:

            # Import the visualizer constants and functions
            from .physics_visualizers_operators import (
                ensure_widget_collection,
            )

            print("  Successfully imported visualizer functions")

            # Ensure the widget collection exists
            widget_collection = ensure_widget_collection()
            print(f"  Widget collection: {widget_collection.name}")

            # Find reference prims collection
            reference_collection = bpy.data.collections.get("ReferencePrims")
            if not reference_collection:
                print("  No ReferencePrims collection found")
                return

            print(f"  Found ReferencePrims collection with {len(reference_collection.objects)} objects")

            # Process each _joint object in ReferencePrims
            processed_count = 0
            for joint_obj in reference_collection.objects:
                print(f"  Checking object: {joint_obj.name}")

                # if not joint_obj.name.endswith("_joint"):
                #     print(f"    Skipping: doesn't end with _joint")
                #     continue

                # Debug: print all custom properties
                print(f"    Custom properties: {list(joint_obj.keys())}")

                # Get joint type from custom properties (these were imported from USD)
                joint_type = joint_obj.get("pxr:usd:physics:joint:type")
                if not joint_type:
                    print("    Skipping: no pxr:usd:physics:joint:type in custom properties")
                    continue

                print(f"    Found joint type: {joint_type}")

                # Get body0 and body1 from custom properties
                body0_name = joint_obj.get("pxr:usd:physics:joint:body0")
                body1_name = joint_obj.get("pxr:usd:physics:joint:body1")

                print(f"    Body0: {body0_name}, Body1: {body1_name}")

                if not body0_name or not body1_name:
                    print("    Skipping: missing body references in custom properties")
                    continue

                body0_obj = bpy.data.objects.get(body0_name)
                body1_obj = bpy.data.objects.get(body1_name)

                if not body0_obj or not body1_obj:
                    print(f"    Skipping: bodies not found ({body0_name}, {body1_name})")
                    continue

                print(f"    Creating visualizer for {joint_obj.name} (type: {joint_type})")

                # Get axis from custom properties (default to Z if not specified)
                axis_attr = joint_obj.get("pxr:usd:physics:joint:axis")
                if axis_attr:
                    # Could be a string or a vector - normalize to string
                    if isinstance(axis_attr, str):
                        axis = axis_attr.upper()
                    elif hasattr(axis_attr, "__len__") and len(axis_attr) == 3:
                        # Convert vector to dominant axis
                        abs_vals = [abs(axis_attr[0]), abs(axis_attr[1]), abs(axis_attr[2])]
                        max_idx = abs_vals.index(max(abs_vals))
                        axis = ["X", "Y", "Z"][max_idx]
                    else:
                        axis = "Z"
                else:
                    axis = "Z"

                print(f"    Axis: {axis}")

                # Create widgets based on joint type
                # NOTE: Visualizers go on the _joint object, not the _obj geometry!
                try:
                    if joint_type in ["revolute", "Revolute", "RevoluteJoint"]:
                        self.create_revolute_visualizer(
                            joint_obj, joint_obj, axis, widget_collection  # Use joint_obj as target
                        )
                        processed_count += 1
                    elif joint_type in ["prismatic", "Prismatic", "PrismaticJoint"]:
                        self.create_prismatic_visualizer(
                            joint_obj, joint_obj, axis, widget_collection  # Use joint_obj as target
                        )
                        processed_count += 1
                    else:
                        print(f"    Unsupported joint type: {joint_type}")
                except Exception as e:
                    print(f"    ERROR creating visualizer: {e}")
                    import traceback

                    traceback.print_exc()

            print(f"  Physics visualizers reconstruction complete: {processed_count} visualizers created")

        except Exception as e:
            print(f"  ERROR in reconstruct_physics_visualizers: {e}")
            import traceback

            traceback.print_exc()

    def create_revolute_visualizer(self, joint_obj, target_obj, axis, widget_collection):
        """Create revolute joint visualizer with arc gizmos"""

        from .physics_visualizers_operators import (
            add_empty,
            axis_basis,
            get_or_add_limit_constraint,
            lock_transforms_revolute,
        )

        # Get limits from custom properties (in degrees)
        # Check if the properties actually exist first
        has_lower_limit = "pxr:usd:physics:joint:lowerLimit" in joint_obj
        has_upper_limit = "pxr:usd:physics:joint:upperLimit" in joint_obj

        if not has_lower_limit or not has_upper_limit:
            print(f"    Warning: Revolute joint {joint_obj.name} missing limit properties")
            print(f"      has_lower_limit: {has_lower_limit}, has_upper_limit: {has_upper_limit}")
            # Use defaults only as fallback
            lower_limit_deg = joint_obj.get("pxr:usd:physics:joint:lowerLimit", -45.0)
            upper_limit_deg = joint_obj.get("pxr:usd:physics:joint:upperLimit", 45.0)
        else:
            # Get actual values from the joint
            lower_limit_deg = joint_obj.get("pxr:usd:physics:joint:lowerLimit")
            upper_limit_deg = joint_obj.get("pxr:usd:physics:joint:upperLimit")
            print(f"    Revolute joint {joint_obj.name} limits: [{lower_limit_deg}°, {upper_limit_deg}°]")

        # Check for infinite limits - don't skip, but handle differently
        has_infinite_limits = False
        if isinstance(lower_limit_deg, str):
            if lower_limit_deg in ["inf", "-inf"]:
                has_infinite_limits = True
                print("    Infinite limits detected - will create visualizer with infinite ring")
        if isinstance(upper_limit_deg, str):
            if upper_limit_deg in ["inf", "-inf"]:
                has_infinite_limits = True
                print("    Infinite limits detected - will create visualizer with infinite ring")

        # Check for float inf
        if isinstance(lower_limit_deg, float) and (lower_limit_deg == float("inf") or lower_limit_deg == float("-inf")):
            has_infinite_limits = True
            print("    Infinite limits detected - will create visualizer with infinite ring")
        if isinstance(upper_limit_deg, float) and (upper_limit_deg == float("inf") or upper_limit_deg == float("-inf")):
            has_infinite_limits = True
            print("    Infinite limits detected - will create visualizer with infinite ring")

        # Convert degrees to radians for Blender
        # For infinite limits, use default angles for the RNA properties (they won't be used by gizmo anyway)
        if has_infinite_limits:
            lower_limit_rad = -math.pi  # Default to -180°
            upper_limit_rad = math.pi  # Default to +180°
        else:
            lower_limit_rad = math.radians(float(lower_limit_deg))
            upper_limit_rad = math.radians(float(upper_limit_deg))

        # Create axis frame empty at the joint's position
        axis_frame_name = f"AxisFrame_{target_obj.name}"

        # AxisFrame position = EXACT same world location as reference prim
        # Rotation = 90° rotation based on joint axis (handled by axis_basis)
        axis_rotation = axis_basis(axis)

        # Start with the axis rotation matrix
        axis_matrix = axis_rotation.copy()

        # Set location to EXACT reference prim's world position (no offsets)
        axis_matrix.translation = target_obj.matrix_world.translation.copy()

        print(f"      AxisFrame position: {axis_matrix.translation}")

        axis_frame = add_empty(
            axis_frame_name, parent=None, matrix=axis_matrix, empty_display="ARROWS", size=0.3, coll=widget_collection
        )

        # Set metadata on axis frame
        axis_frame["jw_target"] = target_obj.name
        axis_frame["joint_type"] = "revolute"
        axis_frame["jw_axis"] = axis

        # Store default rotation
        if not hasattr(target_obj, "jw_rotation_default"):
            target_obj.jw_rotation_default = target_obj.rotation_euler.copy()

        # CRITICAL: Force correct constraint order using save-remove-create-recreate pattern
        # This ensures JointLimit is at position 0 in the constraint stack

        # 1. Save any existing CHILD_OF constraints on target_obj AND current world position
        child_of_constraints = []
        for con in target_obj.constraints:
            if con.type == "CHILD_OF":
                child_of_constraints.append(
                    {
                        "target": con.target,
                        "name": con.name,
                        "inverse_matrix": con.inverse_matrix.copy(),
                        "use_location_x": con.use_location_x,
                        "use_location_y": con.use_location_y,
                        "use_location_z": con.use_location_z,
                        "use_rotation_x": con.use_rotation_x,
                        "use_rotation_y": con.use_rotation_y,
                        "use_rotation_z": con.use_rotation_z,
                        "use_scale_x": con.use_scale_x,
                        "use_scale_y": con.use_scale_y,
                        "use_scale_z": con.use_scale_z,
                        "influence": con.influence,
                    }
                )

        # Save world matrix to preserve position when constraints are removed
        saved_world_matrix = target_obj.matrix_world.copy()

        # 2. Remove existing CHILD_OF constraints from target_obj
        for con in list(target_obj.constraints):
            if con.type == "CHILD_OF":
                target_obj.constraints.remove(con)

        # Restore world position after removing constraints
        target_obj.matrix_world = saved_world_matrix

        # 3. Create Joint Limit constraint (now it goes to position 0)
        constraint = get_or_add_limit_constraint(target_obj, "revolute", axis)
        constraint.owner_space = "LOCAL"

        # Set limits based on axis
        if axis == "X":
            constraint.use_limit_x = True
            constraint.min_x = lower_limit_rad
            constraint.max_x = upper_limit_rad
        elif axis == "Y":
            constraint.use_limit_y = True
            constraint.min_y = lower_limit_rad
            constraint.max_y = upper_limit_rad
        else:  # 'Z'
            constraint.use_limit_z = True
            constraint.min_z = lower_limit_rad
            constraint.max_z = upper_limit_rad

        # Format limits for display (handle infinite values)
        if has_infinite_limits:
            limit_display = f"min={lower_limit_deg}°, max={upper_limit_deg}°"
        else:
            limit_display = f"min={lower_limit_deg:.2f}°, max={upper_limit_deg:.2f}°"
        print(f"      Set constraint limits on {target_obj.name}: {limit_display}")

        # Now set RNA properties AFTER constraint exists (so update callback can work)
        # ALWAYS update these values, don't check hasattr
        target_obj.jw_rotation_limit_min_rna = lower_limit_rad
        target_obj.jw_rotation_limit_max_rna = upper_limit_rad

        # Format RNA values for display
        rna_min = math.degrees(target_obj.jw_rotation_limit_min_rna)
        rna_max = math.degrees(target_obj.jw_rotation_limit_max_rna)
        print(f"      Set RNA properties: min={rna_min:.2f}°, max={rna_max:.2f}°")

        # Lock transforms
        lock_transforms_revolute(target_obj)

        # 4. Recreate CHILD_OF constraints on target_obj (now they go AFTER JointLimit)
        for child_of_data in child_of_constraints:
            new_con = target_obj.constraints.new("CHILD_OF")
            new_con.target = child_of_data["target"]
            new_con.name = child_of_data["name"]
            new_con.inverse_matrix = child_of_data["inverse_matrix"]
            new_con.use_location_x = child_of_data["use_location_x"]
            new_con.use_location_y = child_of_data["use_location_y"]
            new_con.use_location_z = child_of_data["use_location_z"]
            new_con.use_rotation_x = child_of_data["use_rotation_x"]
            new_con.use_rotation_y = child_of_data["use_rotation_y"]
            new_con.use_rotation_z = child_of_data["use_rotation_z"]
            new_con.use_scale_x = child_of_data["use_scale_x"]
            new_con.use_scale_y = child_of_data["use_scale_y"]
            new_con.use_scale_z = child_of_data["use_scale_z"]
            new_con.influence = child_of_data["influence"]
            print(f"      Recreated CHILD_OF on {target_obj.name} (target: {child_of_data['target'].name})")

        # 5. Add constraint to axis frame to follow the joint/reference prim
        # The axis frame should track the joint_obj (target_obj), NOT its parent!
        has_child_of = len(child_of_constraints) > 0
        if has_child_of:
            # Create a CHILD_OF constraint from axis_frame to the joint_obj itself
            # NOT to the joint's parent - we want the axis frame to move with this joint
            new_constraint = axis_frame.constraints.new("CHILD_OF")
            new_constraint.target = joint_obj  # Follow the joint/reference prim, not its parent!
            new_constraint.name = f"Track_{joint_obj.name}"
            # Set inverse matrix to preserve axis_frame's current position
            new_constraint.inverse_matrix = joint_obj.matrix_world.inverted()
            print(f"      Added CHILD_OF to {axis_frame.name} → {joint_obj.name}")
        else:
            # If no CHILD_OF constraint on target, track the joint_obj directly
            new_constraint = axis_frame.constraints.new("CHILD_OF")
            new_constraint.target = joint_obj
            new_constraint.name = f"Track_{joint_obj.name}"
            new_constraint.inverse_matrix = joint_obj.matrix_world.inverted()
            print(f"      Added CHILD_OF to {axis_frame.name} → {joint_obj.name}")

        # Create ring root for visualization
        # This is parented to axis_frame and should be at the same world location
        # Use the axis_frame's world matrix so it's positioned correctly
        ring_radius = 0.5
        ring_root_name = f"RingRoot_{target_obj.name}"
        ring_root = add_empty(
            ring_root_name,
            parent=axis_frame,
            matrix=axis_frame.matrix_world.copy(),  # Use parent's world transform
            empty_display="PLAIN_AXES",
            size=0.1,
            coll=widget_collection,
        )
        ring_root["jw_radius"] = ring_radius
        print(f"      Created RingRoot at axis_frame's location (world: {ring_root.matrix_world.translation})")

        # Format final summary message
        if has_infinite_limits:
            limits_str = f"[{lower_limit_deg}°, {upper_limit_deg}°] (infinite)"
        else:
            limits_str = f"[{lower_limit_deg:.2f}°, {upper_limit_deg:.2f}°]"
        print(f"    Created revolute visualizer for {target_obj.name} at axis {axis} with limits {limits_str}")

    def create_prismatic_visualizer(self, joint_obj, target_obj, axis, widget_collection):
        """Create prismatic joint visualizer with arrow gizmos"""

        from .physics_visualizers_operators import (
            add_empty,
            axis_basis,
            get_or_add_limit_constraint,
            lock_transforms_prismatic,
        )

        # Get limits from custom properties (in meters, relative/local to joint)
        # Check if the properties actually exist first
        has_lower_limit = "pxr:usd:physics:joint:lowerLimit" in joint_obj
        has_upper_limit = "pxr:usd:physics:joint:upperLimit" in joint_obj

        if not has_lower_limit or not has_upper_limit:
            print(f"    Warning: Prismatic joint {joint_obj.name} missing limit properties")
            print(f"      has_lower_limit: {has_lower_limit}, has_upper_limit: {has_upper_limit}")
            # Use defaults only as fallback
            lower_limit_local = joint_obj.get("pxr:usd:physics:joint:lowerLimit", -1.0)
            upper_limit_local = joint_obj.get("pxr:usd:physics:joint:upperLimit", 1.0)
        else:
            # Get actual values from the joint
            lower_limit_local = joint_obj.get("pxr:usd:physics:joint:lowerLimit")
            upper_limit_local = joint_obj.get("pxr:usd:physics:joint:upperLimit")
            print(f"    Prismatic joint {joint_obj.name} limits: [{lower_limit_local}, {upper_limit_local}] meters")

        # Get current location of target object
        current_location = target_obj.location.copy()

        # Calculate absolute limits based on axis
        # The limits are stored relative to the joint, so we need to add current position
        if axis == "X":
            lower_limit_abs = current_location.x + float(lower_limit_local)
            upper_limit_abs = current_location.x + float(upper_limit_local)
        elif axis == "Y":
            # Y axis has special handling due to rotation (see sync_rna_to_constraint_prismatic)
            lower_limit_abs = current_location.y - float(upper_limit_local)
            upper_limit_abs = current_location.y - float(lower_limit_local)
        else:  # 'Z'
            lower_limit_abs = current_location.z + float(lower_limit_local)
            upper_limit_abs = current_location.z + float(upper_limit_local)

        # Calculate initial offset (midpoint of the range)
        initial_offset = (lower_limit_abs + upper_limit_abs) / 2.0

        # Create axis frame empty at the midpoint of the limits
        axis_frame_name = f"AxisFrame_{target_obj.name}"
        axis_matrix = target_obj.matrix_world @ axis_basis(axis)

        # Position the axis frame at the midpoint
        if axis == "X":
            axis_matrix.translation.x = initial_offset
        elif axis == "Y":
            axis_matrix.translation.y = initial_offset
        else:  # 'Z'
            axis_matrix.translation.z = initial_offset

        axis_frame = add_empty(
            axis_frame_name, parent=None, matrix=axis_matrix, empty_display="ARROWS", size=0.3, coll=widget_collection
        )

        # Set metadata on axis frame
        axis_frame["jw_target"] = target_obj.name
        axis_frame["joint_type"] = "prismatic"
        axis_frame["jw_axis"] = axis
        axis_frame["jw_initial_offset"] = initial_offset

        # Store default translation
        if not hasattr(target_obj, "jw_translation_default"):
            target_obj.jw_translation_default = target_obj.location.copy()

        # CRITICAL: Force correct constraint order using save-remove-create-recreate pattern
        # This ensures JointLimit is at position 0 in the constraint stack

        # 1. Save any existing CHILD_OF constraints on target_obj AND current world position
        child_of_constraints = []
        for con in target_obj.constraints:
            if con.type == "CHILD_OF":
                child_of_constraints.append(
                    {
                        "target": con.target,
                        "name": con.name,
                        "inverse_matrix": con.inverse_matrix.copy(),
                        "use_location_x": con.use_location_x,
                        "use_location_y": con.use_location_y,
                        "use_location_z": con.use_location_z,
                        "use_rotation_x": con.use_rotation_x,
                        "use_rotation_y": con.use_rotation_y,
                        "use_rotation_z": con.use_rotation_z,
                        "use_scale_x": con.use_scale_x,
                        "use_scale_y": con.use_scale_y,
                        "use_scale_z": con.use_scale_z,
                        "influence": con.influence,
                    }
                )

        # Save world matrix to preserve position when constraints are removed
        saved_world_matrix = target_obj.matrix_world.copy()

        # 2. Remove existing CHILD_OF constraints from target_obj
        for con in list(target_obj.constraints):
            if con.type == "CHILD_OF":
                target_obj.constraints.remove(con)

        # Restore world position after removing constraints
        target_obj.matrix_world = saved_world_matrix

        # 3. Create Joint Limit constraint (now it goes to position 0)
        constraint = get_or_add_limit_constraint(target_obj, "prismatic", axis)
        constraint.owner_space = "WORLD"  # Prismatic uses WORLD space (revolute uses LOCAL)
        constraint.use_transform_limit = True

        # Get current world location to lock non-joint axes
        current_location = target_obj.matrix_world.translation.copy()

        # Set limits based on axis - lock the other two axes at current position
        if axis == "X":
            constraint.use_min_x = True
            constraint.use_max_x = True
            constraint.use_min_y = True
            constraint.use_max_y = True
            constraint.use_min_z = True
            constraint.use_max_z = True
            constraint.min_x = lower_limit_abs
            constraint.max_x = upper_limit_abs
            # Lock Y and Z at current position
            constraint.min_y = current_location.y
            constraint.max_y = current_location.y
            constraint.min_z = current_location.z
            constraint.max_z = current_location.z
        elif axis == "Y":
            constraint.use_min_x = True
            constraint.use_max_x = True
            constraint.use_min_y = True
            constraint.use_max_y = True
            constraint.use_min_z = True
            constraint.use_max_z = True
            constraint.min_y = lower_limit_abs
            constraint.max_y = upper_limit_abs
            # Lock X and Z at current position
            constraint.min_x = current_location.x
            constraint.max_x = current_location.x
            constraint.min_z = current_location.z
            constraint.max_z = current_location.z
        else:  # 'Z'
            constraint.use_min_x = True
            constraint.use_max_x = True
            constraint.use_min_y = True
            constraint.use_max_y = True
            constraint.use_min_z = True
            constraint.use_max_z = True
            constraint.min_z = lower_limit_abs
            constraint.max_z = upper_limit_abs
            # Lock X and Y at current position
            constraint.min_x = current_location.x
            constraint.max_x = current_location.x
            constraint.min_y = current_location.y
            constraint.max_y = current_location.y

        print(f"      Set constraint limits on {target_obj.name}: min={lower_limit_abs:.4f}, max={upper_limit_abs:.4f}")

        # Now set RNA properties AFTER constraint exists (so update callback can work)
        # ALWAYS update these values, don't check hasattr
        target_obj.jw_translation_limit_min_rna = lower_limit_abs
        target_obj.jw_translation_limit_max_rna = upper_limit_abs
        print(
            f"      Set RNA properties: min={target_obj.jw_translation_limit_min_rna:.4f}, max={target_obj.jw_translation_limit_max_rna:.4f}"
        )

        # Lock transforms
        lock_transforms_prismatic(target_obj)

        # 4. Recreate CHILD_OF constraints on target_obj (now they go AFTER JointLimit)
        for child_of_data in child_of_constraints:
            new_con = target_obj.constraints.new("CHILD_OF")
            new_con.target = child_of_data["target"]
            new_con.name = child_of_data["name"]
            new_con.inverse_matrix = child_of_data["inverse_matrix"]
            new_con.use_location_x = child_of_data["use_location_x"]
            new_con.use_location_y = child_of_data["use_location_y"]
            new_con.use_location_z = child_of_data["use_location_z"]
            new_con.use_rotation_x = child_of_data["use_rotation_x"]
            new_con.use_rotation_y = child_of_data["use_rotation_y"]
            new_con.use_rotation_z = child_of_data["use_rotation_z"]
            new_con.use_scale_x = child_of_data["use_scale_x"]
            new_con.use_scale_y = child_of_data["use_scale_y"]
            new_con.use_scale_z = child_of_data["use_scale_z"]
            new_con.influence = child_of_data["influence"]
            print(f"      Recreated CHILD_OF on {target_obj.name} (target: {child_of_data['target'].name})")

        # 5. Add constraint to axis frame to follow the joint/reference prim
        # The axis frame should track the joint_obj (target_obj), NOT its parent!
        if len(child_of_constraints) > 0:
            # Create a CHILD_OF constraint from axis_frame to the joint_obj itself
            # NOT to the joint's parent - we want the axis frame to move with this joint
            new_constraint = axis_frame.constraints.new("CHILD_OF")
            new_constraint.target = joint_obj  # Follow the joint/reference prim, not its parent!
            new_constraint.name = f"Track_{joint_obj.name}"
            # Set inverse matrix to preserve axis_frame's current position
            new_constraint.inverse_matrix = joint_obj.matrix_world.inverted()
            print(f"      Added CHILD_OF to {axis_frame.name} → {joint_obj.name}")
        else:
            # If no CHILD_OF constraint on target, track the joint_obj directly
            new_constraint = axis_frame.constraints.new("CHILD_OF")
            new_constraint.target = joint_obj
            new_constraint.name = f"Track_{joint_obj.name}"
            new_constraint.inverse_matrix = joint_obj.matrix_world.inverted()
            print(f"      Added CHILD_OF to {axis_frame.name} → {joint_obj.name}")

        print(f"    Created prismatic visualizer for {target_obj.name}")

    def trigger_physics_sync(self):
        """Trigger the physics auto-sync system to start working after import"""
        print("Triggering physics auto-sync system...")

        try:
            # Check if auto-sync is enabled
            if hasattr(bpy.context.scene, "joint_attribute_props"):
                props = bpy.context.scene.joint_attribute_props

                # Enable auto-sync if it's not already enabled
                if not props.auto_sync_ui:
                    props.auto_sync_ui = True
                    print("  Enabled auto-sync UI")

                # Force a selection change to trigger the sync handler
                # This will make the physics system recognize imported empties with physics properties
                if bpy.context.active_object:
                    obj = bpy.context.active_object
                    # Deselect and reselect to trigger the handler
                    obj.select_set(False)
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj
                    print("  Triggered selection change to activate physics sync")

                # Force UI refresh
                for area in bpy.context.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()

                print("  Physics auto-sync system ready")
            else:
                print("  Warning: joint_attribute_props not found, physics sync not available")

        except Exception as e:
            print(f"  Warning: Could not trigger physics sync: {e}")
            # Non-critical, continue anyway


def check_orm_texture_settings(shader_prim):
    """
    Check if a USD shader has ORM texture enabled and validate influence settings.
    This only applies to OmniPBR shaders that support ORM texture.  Principled BSDF doesn't care.

    When enable_ORM_texture is True, the individual texture influences should be 0.0
    because roughness and metallic data come from the ORM texture's channels:
    - R channel = Roughness
    - M channel = Metallic

    Args:
        shader_prim: USD shader prim to check

    Returns:
        dict: {
            'has_orm': bool,
            'enable_orm': bool or None,
            'roughness_influence': float or None,
            'metallic_influence': float or None,
            'is_valid': bool,
            'issues': list of str
        }
    """
    result = {
        "has_orm": False,
        "enable_orm": None,
        "roughness_influence": None,
        "metallic_influence": None,
        "is_valid": True,
        "issues": [],
    }

    if not shader_prim or not shader_prim.IsValid():
        return result

    shader = UsdShade.Shader(shader_prim)

    # Check for enable_ORM_texture input
    enable_orm_input = shader.GetInput("enable_ORM_texture")
    if enable_orm_input:
        result["has_orm"] = True
        enable_orm_attr = enable_orm_input.GetAttr()
        if enable_orm_attr and enable_orm_attr.HasValue():
            result["enable_orm"] = enable_orm_attr.Get()

    # Check for roughness influence
    roughness_influence_input = shader.GetInput("reflection_roughness_texture_influence")
    if roughness_influence_input:
        roughness_attr = roughness_influence_input.GetAttr()
        if roughness_attr and roughness_attr.HasValue():
            result["roughness_influence"] = roughness_attr.Get()

    # Check for metallic influence
    metallic_influence_input = shader.GetInput("metallic_texture_influence")
    if metallic_influence_input:
        metallic_attr = metallic_influence_input.GetAttr()
        if metallic_attr and metallic_attr.HasValue():
            result["metallic_influence"] = metallic_attr.Get()

    # Validate: if ORM is enabled, influences should be 0.0
    if result["enable_orm"]:
        if result["roughness_influence"] is not None and result["roughness_influence"] != 0.0:
            result["is_valid"] = False
            result["issues"].append(
                f"ORM texture enabled but reflection_roughness_texture_influence = {result['roughness_influence']} (should be 0.0)"
            )

        if result["metallic_influence"] is not None and result["metallic_influence"] != 0.0:
            result["is_valid"] = False
            result["issues"].append(
                f"ORM texture enabled but metallic_texture_influence = {result['metallic_influence']} (should be 0.0)"
            )

    return result


def menu_func_import(self, context):
    """Add SimReady USD import to File > Import menu"""
    self.layout.operator(SIMREADY_OT_import_usd.bl_idname, text="SimReady USD (.usd)")


classes = (SIMREADY_OT_import_usd,)


def register():
    """Register the import operator"""
    for cls in classes:
        bpy.utils.register_class(cls)

    # Add to import menu
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    """Unregister the import operator"""
    # Remove from import menu
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
