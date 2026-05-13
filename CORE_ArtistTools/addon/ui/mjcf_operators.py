# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET

import bpy
import mathutils

from ... import python_compat

######################
### MJCF Operators ###
######################


class SRCORE_OT_import_mjcf_with_converter(bpy.types.Operator):
    bl_idname = "sr_core.import_mjcf_with_converter"
    bl_label = "Import MJCF"
    bl_description = "Import a MuJoCo model from an MJCF file"
    bl_options = {"REGISTER", "UNDO"}

    filepath: bpy.props.StringProperty(
        name="File Path", description="Path to the MJCF file", subtype="FILE_PATH", default="", maxlen=1024
    )

    filter_glob: bpy.props.StringProperty(default="*.xml", options={"HIDDEN"}, maxlen=255)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        # Get the checkbox value
        use_included_colliders = context.scene.joint_attribute_props.use_included_colliders
        import_mjcf_with_converter(self.filepath, use_included_colliders)
        return {"FINISHED"}


class SRCORE_OT_export_mjcf(bpy.types.Operator):
    bl_idname = "sr_core.export_mjcf"
    bl_label = "Export as USD"
    bl_description = "Export a USD file from the current scene"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        export_usd()
        return {"FINISHED"}


class SRCORE_OT_repair_mujoco_converter(bpy.types.Operator):
    bl_idname = "sr_core.repair_mujoco_converter"
    bl_label = "Repair MuJoCo Converter"
    bl_description = "Reinstall and repair the MuJoCo USD converter if it's not working"
    bl_options = {"REGISTER"}

    def execute(self, context):
        from ..library import repair_mujoco_converter

        def log_callback(message):
            """Print log messages to Blender's info area."""
            self.report({"INFO"}, message)

        print("\n" + "=" * 60)
        print("Starting MuJoCo Converter Repair...")
        print("=" * 60)

        # Run the repair process
        success, report = repair_mujoco_converter.repair_mujoco_converter(log_callback)

        # Show summary
        if success:
            self.report({"INFO"}, "Repair completed successfully! Please restart Blender.")
        else:
            self.report({"WARNING"}, "Repair completed with errors. Check console for details.")

        print("\n" + "=" * 60)
        print("Repair Complete - Please restart Blender")
        print("=" * 60 + "\n")

        return {"FINISHED"}


def menu_func_import_mjcf(self, context):
    """Add MJCF import to File > Import menu"""
    self.layout.operator(SRCORE_OT_import_mjcf_with_converter.bl_idname, text="MJCF (MuJoCo) (.xml)")


######################
### MJCF Methods #####
######################


def clear_scene():
    """Clear existing objects in the scene"""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def convert_mujoco_to_blender_coords(vec):
    """Convert from MuJoCo to Blender coordinate system"""
    if vec is None:
        return None
    # Swap X and Y, negate new Y (old X)
    return mathutils.Vector((vec[1], -vec[0], vec[2]))


def create_vector(xyz_str):
    """Convert space-separated XYZ string to Vector"""
    if xyz_str:
        coords = [float(val) for val in xyz_str.split()]
        if len(coords) == 3:
            return mathutils.Vector(coords)
    return None


def parse_fromto(fromto_str):
    """Parse 'fromto' attribute to start and end points"""
    if fromto_str:
        values = [float(val) for val in fromto_str.split()]
        if len(values) == 6:
            return mathutils.Vector(values[:3]), mathutils.Vector(values[3:])
    return None, None


def parse_color(rgba_str):
    """Parse RGBA color string to a color tuple"""
    if rgba_str:
        values = [float(val) for val in rgba_str.split()]
        if len(values) >= 3:
            # Make sure we have 4 values (add alpha=1 if missing)
            if len(values) == 3:
                values.append(1.0)
            return tuple(values)
    return (0.8, 0.8, 0.8, 1.0)  # Default gray


def create_material(name, color_rgba):
    """Create a new material with the given color"""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color_rgba
    bsdf.inputs["Alpha"].default_value = color_rgba[3]

    if color_rgba[3] < 1.0:
        mat.blend_method = "BLEND"

    return mat


def create_geom(geom, parent_obj=None, default_rgba=None):
    """Create Blender object from MuJoCo geom"""
    geom_type = geom.get("type", "sphere")
    name = geom.get("name", f"Geom_{geom_type}")

    # Get position and convert coordinates
    mj_pos = create_vector(geom.get("pos", "0 0 0"))
    pos = convert_mujoco_to_blender_coords(mj_pos)

    # Get size
    size_str = geom.get("size", "0.1")
    sizes = [float(s) for s in size_str.split()]

    # Get color
    rgba_str = geom.get("rgba")
    if rgba_str:
        color_rgba = parse_color(rgba_str)
    else:
        color_rgba = default_rgba or (0.8, 0.6, 0.4, 1.0)  # Default from the example

    # Handle different geom types
    if geom_type == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=sizes[0], location=pos)
        obj = bpy.context.active_object

    elif geom_type == "ellipsoid":
        if len(sizes) == 3:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=pos)
            obj = bpy.context.active_object
            obj.scale = (sizes[0], sizes[1], sizes[2])
        else:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=sizes[0], location=pos)
            obj = bpy.context.active_object

    elif geom_type == "box":
        if len(sizes) == 1:
            dimensions = (sizes[0], sizes[0], sizes[0])
        elif len(sizes) == 3:
            dimensions = tuple(sizes)
        else:
            dimensions = (sizes[0], sizes[0], sizes[0])
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=pos)  # Size 2 because it's -1 to 1
        obj = bpy.context.active_object
        obj.scale = (dimensions[0], dimensions[1], dimensions[2])

    elif geom_type == "cylinder":
        radius = sizes[0]
        height = 2.0 * sizes[1] if len(sizes) > 1 else 2.0 * sizes[0]
        bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=height, location=pos)
        obj = bpy.context.active_object

    elif geom_type == "capsule" or geom_type == "plane":
        # Handle fromto for capsule
        fromto = geom.get("fromto")
        if fromto:
            mj_start, mj_end = parse_fromto(fromto)
            if mj_start and mj_end:
                # Convert coordinates
                start = convert_mujoco_to_blender_coords(mj_start)
                end = convert_mujoco_to_blender_coords(mj_end)

                # Calculate direction and length
                direction = end - start
                length = direction.length
                center = (start + end) / 2

                # Create capsule
                if geom_type == "capsule":
                    # Create cylinder
                    bpy.ops.mesh.primitive_cylinder_add(radius=sizes[0], depth=length, location=center)
                    obj = bpy.context.active_object

                    # Align cylinder with direction
                    z_axis = mathutils.Vector((0, 0, 1))
                    direction.normalize()

                    if abs(direction.dot(z_axis) - 1.0) > 0.001:  # Not already aligned
                        rotation_axis = z_axis.cross(direction)
                        if rotation_axis.length > 0.001:  # Valid rotation axis
                            rotation_angle = z_axis.angle(direction)
                            obj.rotation_euler = mathutils.Quaternion(rotation_axis, rotation_angle).to_euler()

                    # Add hemisphere caps
                    bpy.ops.mesh.primitive_uv_sphere_add(radius=sizes[0], location=start)
                    cap1 = bpy.context.active_object
                    bpy.ops.mesh.primitive_uv_sphere_add(radius=sizes[0], location=end)
                    cap2 = bpy.context.active_object

                    # Join the objects
                    cap1.select_set(True)
                    cap2.select_set(True)
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.join()
                elif geom_type == "plane":
                    bpy.ops.mesh.primitive_plane_add(size=1, location=pos)
                    obj = bpy.context.active_object
                    if len(sizes) >= 2:
                        obj.scale = (sizes[0], sizes[1], 1)
            else:
                # Fallback: create at specified position
                bpy.ops.mesh.primitive_cylinder_add(radius=sizes[0], depth=0.2, location=pos)
                obj = bpy.context.active_object
        else:
            # Fallback: create at specified position
            if geom_type == "capsule":
                bpy.ops.mesh.primitive_cylinder_add(radius=sizes[0], depth=0.2, location=pos)
                obj = bpy.context.active_object
            elif geom_type == "plane":
                bpy.ops.mesh.primitive_plane_add(size=1, location=pos)
                obj = bpy.context.active_object
                if len(sizes) >= 2:
                    obj.scale = (sizes[0], sizes[1], 1)
    else:
        # Default: create a sphere
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, location=pos)
        obj = bpy.context.active_object

    # Set name
    obj.name = name

    # Create and assign material
    mat = create_material(f"Mat_{name}", color_rgba)
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    # Parent to provided object if any
    if parent_obj:
        obj.parent = parent_obj

    return obj


def create_joint(joint, parent_obj=None):
    """Create a Blender empty to represent a MuJoCo joint"""
    joint_type = joint.get("type", "hinge")
    name = joint.get("name", f"Joint_{joint_type}")

    # Create an empty to represent the joint
    bpy.ops.object.empty_add(type="ARROWS")  # Use ARROWS for better visualization
    joint_obj = bpy.context.active_object
    joint_obj.name = name

    # Scale the empty to be more visible
    joint_obj.empty_display_size = 0.05

    # Color based on joint type
    if joint_type == "hinge":
        joint_obj.color = (1.0, 0.0, 0.0, 1.0)  # Red
    elif joint_type == "ball":
        joint_obj.color = (0.0, 1.0, 0.0, 1.0)  # Green
    elif joint_type == "slide":
        joint_obj.color = (0.0, 0.0, 1.0, 1.0)  # Blue
    elif joint_type == "free":
        joint_obj.color = (1.0, 1.0, 0.0, 1.0)  # Yellow

    # Get joint axis
    axis_str = joint.get("axis")
    if axis_str:
        mj_axis = create_vector(axis_str)
        if mj_axis:
            # Convert axis (direction vector, so only apply rotation part of transform)
            # For vectors, we swap X,Y and negate the new Y
            axis = mathutils.Vector((mj_axis[1], -mj_axis[0], mj_axis[2]))

            # Calculate rotation to align Z axis with joint axis
            z_axis = mathutils.Vector((0, 0, 1))
            axis.normalize()

            if abs(axis.dot(z_axis) - 1.0) > 0.001:  # Not already aligned
                rotation_axis = z_axis.cross(axis)
                if rotation_axis.length > 0.001:  # Valid rotation axis
                    rotation_angle = z_axis.angle(axis)
                    joint_obj.rotation_euler = mathutils.Quaternion(rotation_axis, rotation_angle).to_euler()

    # Parent relationships
    if parent_obj:
        joint_obj.parent = parent_obj

    return joint_obj


def create_site(site, parent_obj=None, site_dict=None):
    """Create a Blender empty to represent a MuJoCo site"""
    name = site.get("name", "Site")

    # Get position and convert coordinates
    mj_pos = create_vector(site.get("pos", "0 0 0"))
    pos = convert_mujoco_to_blender_coords(mj_pos)

    # Get size
    size_str = site.get("size", "0.01")
    sizes = [float(s) for s in size_str.split()]
    size = sizes[0]

    # Create visible sphere to represent the site
    bpy.ops.mesh.primitive_uv_sphere_add(radius=size, location=pos)
    site_obj = bpy.context.active_object
    site_obj.name = name

    # Make sites a distinct color
    mat = create_material(f"Mat_{name}", (1.0, 0.0, 1.0, 1.0))  # Magenta
    site_obj.data.materials.append(mat)

    # Parent to provided object if any
    if parent_obj:
        site_obj.parent = parent_obj

    # Store in dictionary if provided
    if site_dict is not None and name:
        site_dict[name] = site_obj

    return site_obj


def create_tendons(root, site_objects):
    """Create tendon visualizations for all tendons in the model"""
    print("Creating tendons...")
    # Find all tendon elements in the model
    tendon_parent = root.find("tendon")

    if tendon_parent is None:
        print("No tendon element found in the model")
        return

    # Process spatial tendons
    for spatial in tendon_parent.findall("spatial"):
        width = float(spatial.get("width", "0.005"))
        name = spatial.get("name", "Tendon")
        limited = spatial.get("limited", "false") == "true"

        # Get the list of sites for this tendon
        site_list = []
        for site_elem in spatial.findall("site"):
            site_name = site_elem.get("site")
            if site_name in site_objects:
                site_list.append(site_objects[site_name])

        # Need at least 2 sites to create a tendon
        if len(site_list) < 2:
            print(f"Tendon {name} has fewer than 2 sites, skipping")
            continue

        print(f"Creating tendon {name} connecting {len(site_list)} sites")

        # Create a curve for the tendon
        curve = bpy.data.curves.new(name, "CURVE")
        curve.dimensions = "3D"

        # Add thickness to the curve
        curve.bevel_depth = width

        # Create a spline in the curve
        spline = curve.splines.new("POLY")
        spline.points.add(len(site_list) - 1)  # One point per site

        # Set the points locations
        for i, site in enumerate(site_list):
            spline.points[i].co = (*site.location, 1.0)  # 4D homogeneous coords

        # Create the object with the curve data
        tendon_obj = bpy.data.objects.new(f"Tendon_{name}", curve)
        bpy.context.collection.objects.link(tendon_obj)

        # Create a material for the tendon
        color = (1.0, 0.0, 0.0, 1.0) if limited else (0.0, 0.7, 1.0, 1.0)
        mat = create_material(f"Mat_Tendon_{name}", color)
        tendon_obj.data.materials.append(mat)


def process_body(body_elem, parent_obj=None, site_objects=None, default_rgba=None):
    """Process a MuJoCo body element"""
    # Create an empty for the body
    mj_pos = create_vector(body_elem.get("pos", "0 0 0"))
    pos = convert_mujoco_to_blender_coords(mj_pos)

    name = body_elem.get("name", "Body_Empty")

    bpy.ops.object.empty_add(type="PLAIN_AXES", location=pos)
    body_obj = bpy.context.active_object
    body_obj.name = name

    # Parent to provided object if any
    if parent_obj:
        body_obj.parent = parent_obj

    # Process joints within this body
    for joint_elem in body_elem.findall("joint"):
        joint_obj = create_joint(joint_elem, parent_obj=body_obj)  # noqa F841

    # Process geoms within this body
    for geom_elem in body_elem.findall("geom"):
        geom_obj = create_geom(geom_elem, parent_obj=body_obj, default_rgba=default_rgba)  # noqa F841

    # Process sites within this body
    for site_elem in body_elem.findall("site"):
        site_obj = create_site(site_elem, parent_obj=body_obj, site_dict=site_objects)  # noqa F841

    # Process child bodies recursively
    for child_body in body_elem.findall("body"):
        process_body(child_body, parent_obj=body_obj, site_objects=site_objects, default_rgba=default_rgba)

    return body_obj


def import_mjcf(file_path):
    """Import MJCF file into Blender"""
    # Parse XML
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Set up unit scale
    # MuJoCo uses meters, Blender default is also in meters
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0

    # Get default settings
    default_rgba = None
    default_elem = root.find("default")
    if default_elem is not None:
        default_geom = default_elem.find("geom")
        if default_geom is not None:
            rgba_str = default_geom.get("rgba")
            if rgba_str:
                default_rgba = parse_color(rgba_str)

    # Dictionary to store site objects
    site_objects = {}

    # Create a root empty
    bpy.ops.object.empty_add(type="PLAIN_AXES")
    mujoco_root = bpy.context.active_object
    mujoco_root.name = f"MuJoCo_{os.path.basename(file_path)}"

    # Process world geoms
    worldbody = root.find("worldbody")
    if worldbody is not None:
        # Process lights
        for light_elem in worldbody.findall("light"):
            mj_pos = create_vector(light_elem.get("pos", "0 0 0"))
            pos = convert_mujoco_to_blender_coords(mj_pos)

            # Get light color
            diffuse_str = light_elem.get("diffuse")
            color = parse_color(diffuse_str) if diffuse_str else (1.0, 1.0, 1.0, 1.0)

            # Get light direction
            mj_dir = create_vector(light_elem.get("dir", "0 0 -1"))
            if mj_dir:
                # Convert direction vector
                dir = mathutils.Vector((mj_dir[1], -mj_dir[0], mj_dir[2]))
                dir.normalize()

                # Create light
                if dir.length > 0:
                    # This is a directional or spot light
                    bpy.ops.object.light_add(type="SPOT", location=pos)
                    light_obj = bpy.context.active_object

                    # Set direction
                    light_obj.rotation_euler = dir.to_track_quat("Z", "Y").to_euler()
                else:
                    # This is a point light
                    bpy.ops.object.light_add(type="POINT", location=pos)
                    light_obj = bpy.context.active_object
            else:
                # Default: point light
                bpy.ops.object.light_add(type="POINT", location=pos)
                light_obj = bpy.context.active_object

            # Set light name
            name = light_elem.get("name", "Light")
            light_obj.name = f"Light_{name}"

            # Set light color
            light_obj.data.color = color[:3]

            # Parent to root
            light_obj.parent = mujoco_root

        # Process world geoms
        for geom_elem in worldbody.findall("geom"):
            geom_obj = create_geom(geom_elem, parent_obj=mujoco_root, default_rgba=default_rgba)  # noqa F841

        # Process sites in worldbody
        for site_elem in worldbody.findall("site"):
            site_obj = create_site(site_elem, parent_obj=mujoco_root, site_dict=site_objects)  # noqa F841

        # Process bodies
        for body_elem in worldbody.findall("body"):
            body_obj = process_body(  # noqa F841
                body_elem, parent_obj=mujoco_root, site_objects=site_objects, default_rgba=default_rgba
            )

    # Print all site objects
    print("Site objects:")
    for name, obj in site_objects.items():
        print(f"  {name}: {obj.name} at {obj.location}")

    # Process tendons
    create_tendons(root, site_objects)

    print("MJCF import complete!")


def validate_mjcf_file(file_path: str) -> bool:
    """Validate MJCF file for security and basic structure.

    This function performs basic validation to ensure the file is a valid MJCF file
    and doesn't contain potentially malicious content.

    Args:
        file_path (str): Path to the MJCF file to validate

    Returns:
        bool: True if file is valid, False otherwise
    """
    try:
        # Check file size (prevent extremely large files)
        file_size = os.path.getsize(file_path)
        max_size = 100 * 1024 * 1024  # 100MB limit
        if file_size > max_size:
            print(f"ERROR: MJCF file too large ({file_size / 1024 / 1024:.1f}MB). Maximum allowed: 100MB")
            return False

        # Check file extension
        if not file_path.lower().endswith(".xml"):
            print("ERROR: MJCF file must have .xml extension")
            return False

        # Try to parse as XML and check for basic MJCF structure
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Check if root element is 'mujoco'
        if root.tag != "mujoco":
            print("ERROR: MJCF file must have 'mujoco' as root element")
            return False

        # Check for potentially dangerous elements (custom scripts, etc.)
        dangerous_elements = ["script", "exec", "system", "command"]
        for elem in root.iter():
            if elem.tag.lower() in dangerous_elements:
                print(f"ERROR: MJCF file contains potentially dangerous element: {elem.tag}")
                return False

        # Check for reasonable number of elements (prevent DoS)
        element_count = len(list(root.iter()))
        max_elements = 10000  # Reasonable limit for MJCF files
        if element_count > max_elements:
            print(f"ERROR: MJCF file contains too many elements ({element_count}). Maximum allowed: {max_elements}")
            return False

        return True

    except ET.ParseError as e:
        print(f"ERROR: Invalid XML in MJCF file: {e}")
        return False
    except Exception as e:
        print(f"ERROR: Failed to validate MJCF file: {e}")
        return False


def import_mjcf_with_converter_sandboxed(file_path: str, use_included_colliders: bool) -> bool:
    """Import MJCF file using the mjc-usd-converter in a sandboxed environment.

    This function creates a completely isolated environment for the converter process,
    preventing it from accessing Blender's Python environment or internal state.

    Args:
        file_path (str): Path to the MJCF file to import
        use_included_colliders (bool): Whether to include colliders in the hierarchy

    Returns:
        bool: True if import was successful, False otherwise
    """
    # Validate the MJCF file first
    if not validate_mjcf_file(file_path):
        return False

    # On Blender 5.1+ (Python 3.13) extract and configure the bundled Python 3.11.9
    # so that all subsequent subprocess calls can use a compatible interpreter.
    if python_compat.needs_external_python():
        try:
            python_compat.ensure_external_python()
        except Exception as exc:
            print(f"ERROR: Failed to set up bundled Python 3.11.9: {exc}")
            return False

    # Find output directory in hierarchy of simready
    if not bpy.data.filepath:

        def draw_save_reminder(self, _):
            self.layout.label(text="Please save the blender file first.")

        bpy.context.window_manager.popup_menu(draw_save_reminder, title="Save Required", icon="ERROR")
        print("ERROR: Blender file not saved, please save it first")
        return False

    blend_filepath = bpy.data.filepath
    dcc_source_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(blend_filepath))))
    if not os.path.basename(dcc_source_dir) == "dcc_source":
        print("ERROR: Not in dcc_source directory, please save the blender file in the dcc_source directory")
        return False

    output_dir = os.path.join(dcc_source_dir, "working", "reference", "from_objaverse")
    os.makedirs(output_dir, exist_ok=True)  # create output directory if it doesn't exist

    # Get the available converter executable
    from ... import sys_functions

    converter_name = sys_functions.get_available_converter()
    if not converter_name:
        print("ERROR: No MJCF converter found. Please install mujoco-usd-converter.")
        return False

    print(f"DEBUG: Using converter: {converter_name}")
    print(f"DEBUG: Input file: {file_path}")
    print(f"DEBUG: Output directory: {output_dir}")

    # Verify the converter can import its dependencies
    try:
        import subprocess

        test_result = subprocess.run(
            [python_compat.get_mjcf_python(), "-c", "import mujoco_usd_converter; print('Dependencies OK')"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if test_result.returncode != 0:
            print("WARNING: Converter dependency check failed!")
            print(f"  Return code: {test_result.returncode}")
            print(f"  Stdout: {test_result.stdout}")
            print(f"  Stderr: {test_result.stderr}")
            print("  This may indicate missing packages. Continuing anyway...")
        else:
            print(f"DEBUG: Converter dependency check passed: {test_result.stdout.strip()}")
    except Exception as e:
        print(f"WARNING: Could not verify converter dependencies: {e}")

    # Create a temporary directory for the sandboxed process
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a minimal Python script that will run the converter
        sandbox_script = os.path.join(temp_dir, "sandbox_converter.py")

        # Write the sandbox script with more debugging
        with open(sandbox_script, "w") as f:
            f.write('''#!/usr/bin/env python3
import os
import sys
import subprocess
import json
import tempfile
import shutil

def clean_usd_from_path(path_string, separator):
    """Remove USD-related paths from a PATH-like string."""
    if not path_string:
        return path_string
    paths = path_string.split(separator)
    # Filter out paths containing 'USD' (case-insensitive) unless they contain 'usdex' or 'usd-core'
    cleaned_paths = []
    for p in paths:
        p_upper = p.upper()
        # Keep usdex and usd-core paths (from pip packages)
        if 'USDEX' in p_upper or 'USD-CORE' in p_upper or 'SITE-PACKAGES' in p_upper:
            cleaned_paths.append(p)
        # Remove system USD paths (including C:\\USD)
        elif 'USD' in p_upper and ('\\\\USD\\\\' in p_upper or '/USD/' in p_upper or p_upper.endswith('\\\\USD') or p_upper.endswith('/USD') or 'C:\\\\USD' in p_upper):
            print(f"DEBUG: Removing USD path: {p}")
        else:
            cleaned_paths.append(p)
    return separator.join(cleaned_paths)

def run_converter_sandboxed():
    """Run the MJCF converter in a sandboxed environment."""
    try:
        # Read input parameters from environment variables
        input_file = os.environ.get('MJCF_INPUT_FILE')
        output_dir = os.environ.get('MJCF_OUTPUT_DIR')
        converter_name = os.environ.get('MJCF_CONVERTER_NAME')
        
        print(f"DEBUG: Input file: {input_file}")
        print(f"DEBUG: Output directory: {output_dir}")
        print(f"DEBUG: Converter: {converter_name}")
        
        if not all([input_file, output_dir, converter_name]):
            print("ERROR: Missing required environment variables")
            return False
        
        # Verify input file exists
        if not os.path.exists(input_file):
            print(f"ERROR: Input file does not exist: {input_file}")
            return False
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        print(f"DEBUG: Output directory created/verified: {output_dir}")
        
        # List files in output directory before conversion
        print("DEBUG: Files in output directory before conversion:")
        if os.path.exists(output_dir):
            for file in os.listdir(output_dir):
                print(f"  - {file}")
        
        # Run the converter with cleaned environment
        env = os.environ.copy()
        
        # Remove problematic Blender environment variables
        problematic_vars = [
            'BLENDER_SYSTEM_SCRIPTS', 
            'BLENDER_USER_SCRIPTS',
            'PYTHONPATH',  # Remove PYTHONPATH to prevent conflicts
            'PXR_PLUGINPATH_NAME',
            'PXR_USD_WINDOWS_DLL_PATH',
        ]
        for var in problematic_vars:
            if var in env:
                print(f"DEBUG: Removing environment variable: {var}")
                del env[var]
        
        # Clean PATH to remove system USD installations
        if 'PATH' in env:
            separator = ';' if sys.platform == 'win32' else ':'
            original_path = env['PATH']
            cleaned_path = clean_usd_from_path(original_path, separator)
            if cleaned_path != original_path:
                env['PATH'] = cleaned_path
                print(f"DEBUG: Cleaned PATH environment variable")
        
        # Force Python to use only user site-packages for USD
        # This prevents conflicts with system USD installations
        import site
        user_site = site.getusersitepackages()
        if user_site:
            print(f"DEBUG: Setting PYTHONPATH to user site-packages: {user_site}")
            env['PYTHONPATH'] = user_site
        
        print(f"DEBUG: Running converter: {converter_name} {input_file} {output_dir}")
        
        # Run the converter
        result = subprocess.run(
            [converter_name, input_file, output_dir],
            env=env,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        print(f"DEBUG: Converter return code: {result.returncode}")
        print(f"DEBUG: Converter stdout: {result.stdout}")
        print(f"DEBUG: Converter stderr: {result.stderr}")
        
        # If we got no output at all, try to diagnose the issue
        if result.returncode != 0 and not result.stdout and not result.stderr:
            print("ERROR: Converter failed with no output - attempting diagnostics...")
            # Check if the converter can import its dependencies
            try:
                diag_result = subprocess.run(
                    [sys.executable, "-c", "import mujoco_usd_converter; print('Import successful')"],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                print(f"DIAGNOSTIC: Import test return code: {diag_result.returncode}")
                print(f"DIAGNOSTIC: Import test stdout: {diag_result.stdout}")
                print(f"DIAGNOSTIC: Import test stderr: {diag_result.stderr}")
            except Exception as diag_err:
                print(f"DIAGNOSTIC: Import test failed: {diag_err}")
        
        if result.returncode != 0:
            print(f"ERROR: Converter failed with return code {result.returncode}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False
        
        # List files in output directory after conversion
        print("DEBUG: Files in output directory after conversion:")
        if os.path.exists(output_dir):
            for file in os.listdir(output_dir):
                print(f"  - {file}")
        
        # Check if any USD files were created
        usd_files = [f for f in os.listdir(output_dir) if f.endswith('.usd') or f.endswith('.usda')]
        if not usd_files:
            print("WARNING: No USD files were created by the converter")
            return False
        
        print(f"SUCCESS: Created {len(usd_files)} USD file(s): {usd_files}")
        return True
        
    except subprocess.TimeoutExpired:
        print("ERROR: Converter timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error in sandboxed converter: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_converter_sandboxed()
    sys.exit(0 if success else 1)
''')

        # Set up environment variables for the sandboxed process
        env = os.environ.copy()
        env["MJCF_INPUT_FILE"] = file_path
        env["MJCF_OUTPUT_DIR"] = output_dir
        env["MJCF_CONVERTER_NAME"] = converter_name

        # Remove problematic environment variables that can cause USD conflicts
        problematic_vars = [
            "BLENDER_SYSTEM_SCRIPTS",
            "BLENDER_USER_SCRIPTS",
            "PYTHONPATH",
            "PXR_PLUGINPATH_NAME",
            "PXR_USD_WINDOWS_DLL_PATH",
        ]
        for var in problematic_vars:
            if var in env:
                print(f"DEBUG: Removing environment variable: {var}")
                del env[var]

        # Clean PATH to remove system USD installations
        if "PATH" in env:
            separator = ";" if sys.platform == "win32" else ":"
            paths = env["PATH"].split(separator)
            cleaned_paths = []
            for p in paths:
                p_upper = p.upper()
                # Keep usdex and usd-core paths (from pip packages)
                if "USDEX" in p_upper or "USD-CORE" in p_upper or "SITE-PACKAGES" in p_upper:
                    cleaned_paths.append(p)
                # Remove system USD paths (including C:\USD)
                elif "USD" in p_upper and (
                    "\\USD\\" in p_upper
                    or "/USD/" in p_upper
                    or p_upper.endswith("\\USD")
                    or p_upper.endswith("/USD")
                    or "C:\\USD" in p_upper
                ):
                    print(f"DEBUG: Removing USD path from PATH: {p}")
                else:
                    cleaned_paths.append(p)
            env["PATH"] = separator.join(cleaned_paths)
            print("DEBUG: Cleaned PATH environment variable")

        # Force Python to use only user site-packages for USD
        # This prevents conflicts with system USD installations
        import site

        user_site = site.getusersitepackages()
        if user_site:
            print(f"DEBUG: Setting PYTHONPATH to user site-packages: {user_site}")
            env["PYTHONPATH"] = user_site

        try:
            # Run the sandboxed script with minimal restrictions
            print("DEBUG: Starting sandboxed converter process...")

            # Get list of existing files before conversion
            existing_files = set()
            if os.path.exists(output_dir):
                for file in os.listdir(output_dir):
                    if file.lower().endswith((".usd", ".usda", ".usdc")):
                        existing_files.add(file)

            # print(f"DEBUG: Existing USD files before conversion: {list(existing_files)}")

            # Set conversion start time BEFORE running the converter
            import time

            conversion_start_time = time.time()

            result = subprocess.run(
                [python_compat.get_mjcf_python(), sandbox_script],
                env=env,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=temp_dir,  # Set working directory to temp dir
            )

            print(f"DEBUG: Sandbox process return code: {result.returncode}")
            print(f"DEBUG: Sandbox stdout: {result.stdout}")
            if result.stderr:
                print(f"DEBUG: Sandbox stderr: {result.stderr}")

            if result.returncode != 0:
                print(f"ERROR: Sandboxed converter failed with return code {result.returncode}")
                print(f"STDOUT: {result.stdout}")
                print(f"STDERR: {result.stderr}")
                return False

            # Get list of files after conversion
            current_files = set()
            if os.path.exists(output_dir):
                for file in os.listdir(output_dir):
                    if file.lower().endswith((".usd", ".usda", ".usdc")):
                        current_files.add(file)

            print(f"DEBUG: Current USD files after conversion: {list(current_files)}")

            # Find newly created files
            newly_created_files = current_files - existing_files
            print(f"DEBUG: Newly created files (by comparison): {list(newly_created_files)}")

            # Check if any USD files were created (using timestamp method as backup)
            newly_created = get_recent_usd_files(output_dir, conversion_start_time)

            print(f"DEBUG: Newly created USD files (by timestamp): {newly_created}")

            # Use the comparison method if timestamp method found nothing
            if not newly_created and newly_created_files:
                newly_created = [os.path.join(output_dir, file) for file in newly_created_files]
                print(f"DEBUG: Using comparison method, found: {newly_created}")

            if newly_created:
                for usd_file in newly_created:
                    import_usd_file(usd_file, use_included_colliders)
                return True
            else:
                print("WARNING: No new USD files were created")
                return False

        except subprocess.TimeoutExpired:
            print("ERROR: Sandboxed converter timed out after 5 minutes")
            return False
        except Exception as e:
            print(f"ERROR: Failed to run sandboxed converter: {e}")
            import traceback

            traceback.print_exc()
            return False


def import_mjcf_with_converter(file_path: str, use_included_colliders: bool) -> bool:
    """Import MJCF file using the mjc-usd-converter.

    Args:
        file_path (str): Path to the MJCF file to import
        use_included_colliders (bool): Whether to include colliders in the hierarchy

    Returns:
        bool: True if import was successful, False otherwise
    """
    # Use the sandboxed version for security
    return import_mjcf_with_converter_sandboxed(file_path, use_included_colliders)


def get_recent_usd_files(directory: str, start_time: float) -> list[str]:
    """Get USD files that were created or modified after a specific time.

    Args:
        directory (str): Directory to search
        start_time (float): Timestamp to compare against

    Returns:
        list: List of USD file paths that are newer than start_time
    """
    usd_extensions = [".usd", ".usda", ".usdc"]
    usd_files = []
    if os.path.exists(directory):
        for file in os.listdir(directory):
            if any(file.lower().endswith(ext) for ext in usd_extensions):
                file_path = os.path.join(directory, file)
                try:
                    # Get both modification time and creation time
                    mtime = os.path.getmtime(file_path)
                    ctime = os.path.getctime(file_path)

                    # Consider file "new" if either modification or creation time is after start_time
                    # Also add a small buffer (1 second) to handle timing precision issues
                    if mtime > (start_time - 1) or ctime > (start_time - 1):
                        usd_files.append(file_path)
                        print(
                            f"DEBUG: Found recent USD file: {file} (mtime: {mtime}, ctime: {ctime}, start_time: {start_time})"
                        )
                except OSError as e:
                    print(f"DEBUG: Could not get file times for {file}: {e}")
    return usd_files


def import_usd_file(file_path: str, use_included_colliders: bool) -> None:
    """Import a USD file into Blender and reorganize its hierarchy.

    Args:
        file_path (str): Path to the USD file
        use_included_colliders (bool): Whether to include colliders in the hierarchy
    """
    existing_objects = set(bpy.context.scene.objects)
    existing_images = set(bpy.data.images.keys())

    try:
        bpy.ops.wm.usd_import(filepath=file_path)  # Import USD file
        copy_imported_textures(existing_images)  # Copy newly imported textures
        new_objects = set(bpy.context.scene.objects) - existing_objects  # Get new objects added to scene
        root_object = None
        for obj in new_objects:  # Find root object
            if obj.parent is None or obj.parent not in new_objects:
                root_object = obj
                break
        if root_object is None:
            root_object = next(iter(new_objects))
        vis_meshes, joints = reorganize_asset_hierarchy(root_object.name, use_included_colliders)
        # Normalize position to ground plane (FEATURE 01 requirement for runtime testing)
        normalize_asset_position(vis_meshes, joints, use_included_colliders)
        material_type = "glass"
        if use_included_colliders:
            assign_materials_to_collection("Colliders", material_type)
        else:
            assign_materials_to_collection("Geometry", material_type)
        assign_physics_properties_to_joints(vis_meshes, joints)
        print("✅ USD imported successfully")
    except ReferenceError:
        print("⚠️ Some objects were recreated during import (this is expected behavior)")
        print("✅ USD imported with warnings")
    except Exception as e:
        print(f"ERROR: Failed to import USD file: {e}")
        import traceback

        traceback.print_exc()


def copy_imported_textures(existing_images: set[str]) -> None:
    """Copy newly imported texture files to dcc_source/texture/ and simready_usd/textures/

    Args:
        existing_images (set): Set of image names that existed before import
    """
    if not bpy.data.filepath:
        return

    new_images = set(bpy.data.images.keys()) - existing_images
    if not new_images:
        return

    blend_filepath = bpy.data.filepath
    dcc_source_dir = os.path.dirname(os.path.dirname(os.path.dirname(blend_filepath)))
    if not os.path.basename(dcc_source_dir) == "dcc_source":
        return

    project_root = os.path.dirname(dcc_source_dir)
    texture_dir = os.path.join(dcc_source_dir, "texture")
    simready_texture_dir = os.path.join(project_root, "simready_usd", "textures")
    os.makedirs(texture_dir, exist_ok=True)
    os.makedirs(simready_texture_dir, exist_ok=True)

    for image_name in new_images:
        image = bpy.data.images[image_name]
        if not hasattr(image, "filepath") or not image.filepath:
            continue
        source_path = bpy.path.abspath(image.filepath)
        if not os.path.exists(source_path):
            continue
        filename = os.path.basename(source_path)
        try:
            shutil.copy2(source_path, os.path.join(texture_dir, filename))
            shutil.copy2(source_path, os.path.join(simready_texture_dir, filename))
            print(f"✅ Copied texture {filename} to {texture_dir} and {simready_texture_dir}")
        except Exception as e:
            print(f"ERROR: Failed to copy texture {filename}: {e}")


def reorganize_asset_hierarchy(root_name: str, use_included_colliders: bool) -> tuple[list[str], list[str]]:
    """Reorganize the asset hierarchy of a unibody or multibody object.

    Args:
        root_name (str): Name of the object to reorganize.
        use_included_colliders (bool): Whether to include colliders in the hierarchy.

    Returns:
        tuple[list[str], list[str]]: List of vis meshes and joints
    """
    # Get root object
    root_obj = bpy.data.objects.get(root_name)
    if not root_obj:
        print(f"Root object '{root_name}' not found")
        return [], []

    # Find first object with mesh children
    object_obj = None

    def is_child_of(obj, root):
        current = obj
        while current.parent:
            current = current.parent
            if current == root:
                return True
        return False

    all_objects = [root_obj] + [obj for obj in bpy.data.objects if is_child_of(obj, root_obj)]
    for obj in all_objects:
        if any(child.type == "MESH" for child in obj.children):
            object_obj = obj
            break

    print(f"object_obj: {object_obj}")
    if not object_obj:
        object_obj = root_obj

    # Recreate collections with the following hierarchy:
    # - Export
    #   -> Geometry
    #   -> ReferencePrims
    #   -> Colliders
    for name in ["Export", "Geometry", "ReferencePrims", "Colliders"]:
        if name in bpy.data.collections:  # remove existing collections
            bpy.data.collections.remove(bpy.data.collections[name])
    export_collection = bpy.data.collections.new("Export")
    geometry_collection = bpy.data.collections.new("Geometry")
    prims_collection = bpy.data.collections.new("ReferencePrims")
    colliders_collection = bpy.data.collections.new("Colliders")
    if bpy.context.scene:  # link collections to scene
        bpy.context.scene.collection.children.link(export_collection)
    export_collection.children.link(geometry_collection)
    export_collection.children.link(prims_collection)
    export_collection.children.link(colliders_collection)

    vis_meshes = _process_vis_meshes(object_obj, geometry_collection)
    joints = _process_fixed_joints(object_obj, prims_collection, len(vis_meshes))
    if len(vis_meshes) > 1:
        _add_constraints_to_joints(joints, vis_meshes)
    _assign_vis_meshes_to_joints(vis_meshes, joints)
    if use_included_colliders:
        _process_colliders(object_obj, colliders_collection, vis_meshes, joints)
    _cleanup_old_hierarchy(root_obj)
    print(f"✅ Reorganized '{root_name}' hierarchy successfully!")
    return vis_meshes, joints


def assign_materials_to_collection(collection_name: str, material_type: str) -> None:
    """Assign a material to objects in a collection.

    Args:
        collection_name (str): Name of the collection to assign materials to
        material_type (str): Type of material to assign.
    """
    collection = bpy.data.collections.get(collection_name)
    if not collection:
        return False

    for obj in collection.objects:
        if obj.type != "MESH":
            continue

        if len(obj.data.materials) == 0:
            obj.data.materials.append(None)

        if obj.data.materials[0] is None:
            mat_name = f"{obj.name}_default_mat"
            new_mat = bpy.data.materials.new(mat_name)
            new_mat.use_nodes = True
            obj.data.materials[0] = new_mat

        mat = obj.data.materials[0]
        mat.simready_props.physx_material_type = material_type

        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        try:
            bpy.ops.simready.assign_physx_properties()  # Assign with CORE_ArtistTools operator
            print(f"✅ Physics properties assigned to '{obj.name}'")
        except Exception as e:
            print(f"Error: Failed to assign physics properties to '{obj.name}': {e}")


def assign_physics_properties_to_joints(vis_meshes: list[bpy.types.Object], joints: list[bpy.types.Object]) -> None:
    """Assign physics properties to joints.

    Args:
        vis_meshes (list[bpy.types.Object]): List of vis meshes
        joints (list[bpy.types.Object]): List of joints
    """
    if not joints:
        return False

    props = bpy.context.scene.joint_attribute_props

    for i, joint in enumerate(joints):
        try:
            # Check if the joint object is still valid (hasn't been deleted)
            _ = joint.name  # This will raise ReferenceError if object was deleted
        except ReferenceError:
            print(f"⚠️ Joint at index {i} was deleted during processing, skipping...")
            continue

        try:
            if not any(constraint.type == "CHILD_OF" for constraint in joint.constraints):
                print(f"No ChildOf constraint found for '{joint.name}'")
                continue
            child_of_constraint = next(constraint for constraint in joint.constraints if constraint.type == "CHILD_OF")
            parent = child_of_constraint.target
            if parent is None:
                print(f"No target found for '{joint.name}'")
                continue

            # Assign required properties to the joint for the SR_Next_Physics_Joints operator to work
            props.body_0 = vis_meshes[joints.index(parent)]
            props.body_1 = vis_meshes[i]
            if "fixed" in joint.name:
                props.joint_type = "fixed"

            # Select the current joint in the viewport
            bpy.ops.object.select_all(action="DESELECT")
            joint.select_set(True)
            bpy.context.view_layer.objects.active = joint

            bpy.ops.sr_core.copy_empty_position(
                target_prop="joint_local_pos_0"
            )  # Update the localPos0 property of the joint
            print(f"✅ Local position copied to '{joint.name}' successfully!")

            bpy.ops.sr_core.apply_joint_settings()  # Assign with SR_Next_Physics_Joints operator
            print(f"✅ Joint settings applied to '{joint.name}' successfully!")

        except ReferenceError:
            # Joint was deleted during apply_joint_settings() - this is expected behavior
            print(f"⚠️ Joint at index {i} was recreated by apply_joint_settings(), this is normal")
            continue
        except Exception as e:
            print(f"Error: Failed to process joint at index {i}: {e}")


def export_usd() -> bool:
    """Export the current scene to USD.
    Only exports objects that are in the 'Export' collection.

    Returns:
        bool: True if the USD was successfully exported, False otherwise.
    """
    # Find output directory in hierarchy of simready
    if not bpy.data.filepath:

        def draw_save_reminder(self, context):
            self.layout.label(text="Please save the blender file first.")

        bpy.context.window_manager.popup_menu(draw_save_reminder, title="Save Required", icon="ERROR")
        print("ERROR: Blender file not saved, please save it first")
        return False
    blend_filepath = bpy.data.filepath
    blend_filename = os.path.splitext(os.path.basename(blend_filepath))[0]
    dcc_source_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(blend_filepath))))
    if not os.path.basename(dcc_source_dir) == "dcc_source":
        print("ERROR: Not in dcc_source directory, please save the blender file in the dcc_source directory")
        return False
    project_root = os.path.dirname(dcc_source_dir)
    simready_usd_dir = os.path.join(project_root, "simready_usd")
    os.makedirs(simready_usd_dir, exist_ok=True)
    output_path = os.path.join(simready_usd_dir, f"{blend_filename}.usd")

    # Only export objects in the Export collection
    export_col = bpy.data.collections.get("Export")
    if not export_col:
        return False
    bpy.ops.object.select_all(action="DESELECT")
    objects_to_export = []
    for obj in export_col.all_objects:
        obj.select_set(True)
        objects_to_export.append(obj.name)
    if not objects_to_export:

        def draw_warning(self, context):
            self.layout.label(text="The 'Export' collection is empty.")
            self.layout.label(text="Please add objects to the Export collection.")

        bpy.context.window_manager.popup_menu(draw_warning, title="Export Collection Empty", icon="ERROR")
        return False

    bpy.ops.wm.usd_export(
        filepath=output_path, root_prim_path="/RootNode", triangulate_meshes=True, selected_objects_only=True
    )

    # Show success popup
    def draw_popup(self, context):
        self.layout.label(text="USD saved at:")
        path_parts = output_path.replace("\\", "/").split("/")
        if len(path_parts) > 7:
            half_length = len(path_parts) // 2
            first_part = "/".join(path_parts[:half_length])
            last_parts = "/".join(path_parts[half_length:])
            self.layout.label(text=f"{first_part}/")
            self.layout.label(text=f"{last_parts}")
        else:
            self.layout.label(text=f"Saved to: {output_path}")

    bpy.context.window_manager.popup_menu(draw_popup, title="Export Completed", icon="EXPORT")
    print("✅ USD exported successfully")
    return True


def _process_vis_meshes(
    object_obj: bpy.types.Object, geometry_collection: bpy.types.Collection
) -> list[bpy.types.Object]:
    """Process and move vis meshes to geometry collection.

    Args:
        object_obj (bpy.types.Object): The object to process
        geometry_collection (bpy.types.Collection): The collection to link vis meshes to

    Returns:
        list[bpy.types.Object]: List of vis meshes
    """
    vis_meshes = []
    for child in object_obj.children:
        if "vis" not in child.name:
            continue

        # Name vis mesh object as `vis_mesh_name_obj` and mesh as `vis_mesh_name_mesh`
        if "_obj" not in child.name:
            child.name = child.name + "_obj"
        desired_mesh_name = child.name.replace("_obj", "_mesh")
        if desired_mesh_name in bpy.data.meshes:
            old_mesh = bpy.data.meshes[desired_mesh_name]
            bpy.data.meshes.remove(old_mesh)
        child.data.name = desired_mesh_name

        child.parent = None
        _apply_scale_transform(child)
        _unlink_from_collections(child)
        geometry_collection.objects.link(child)
        vis_meshes.append(child)
    return vis_meshes


def _process_fixed_joints(
    object_obj: bpy.types.Object, prims_collection: bpy.types.Collection, vis_mesh_count: int
) -> list[bpy.types.Object]:
    """Process joints and ensure we have enough for each vis mesh.
    If there is only one vis mesh, create an empty joint.

    Args:
        object_obj (bpy.types.Object): The object to process
        prims_collection (bpy.types.Collection): The collection to link joints to
        vis_mesh_count (int): The number of vis meshes

    Returns:
        list[bpy.types.Object]: List of joints
    """
    joints = []
    joint_count = 0
    for child in object_obj.children:
        if "PhysicsFixedJoint" in child.name:
            _unlink_from_collections(child)
            child.parent = None
            if vis_mesh_count == 1:  # Unibody only has one empty joint
                child.name = "empty_joint_00"
                prims_collection.objects.link(child)
                joints.append(child)
                return joints
            child.name = f"physics_fixed_joint_{joint_count:02d}"
            prims_collection.objects.link(child)
            joints.append(child)
            joint_count += 1
    # Duplicate joints if needed
    while joint_count < vis_mesh_count and joints:
        last_joint = joints[-1]
        joint_copy = last_joint.copy()
        joint_copy.name = f"physics_fixed_joint_{joint_count:02d}"
        prims_collection.objects.link(joint_copy)
        joints.append(joint_copy)
        joint_count += 1
    return joints


def _add_constraints_to_joints(joints: list[bpy.types.Object], vis_meshes: list[bpy.types.Object]) -> None:
    """Add constraints to joints where the joint of the largest vis mesh is the parent of the other joints.

    Args:
        joints (list[bpy.types.Object]): List of joints
        vis_meshes (list[bpy.types.Object]): List of vis meshes
    """
    largest_vis_mesh_index = 0
    largest_vis_mesh_volume = get_bounding_box_volume(vis_meshes[0])
    for i, vis_mesh in enumerate(vis_meshes):
        volume = get_bounding_box_volume(vis_mesh)
        if volume > largest_vis_mesh_volume:
            largest_vis_mesh_volume = volume
            largest_vis_mesh_index = i
    largest_vis_mesh_joint = joints[largest_vis_mesh_index]
    for i, joint in enumerate(joints):
        if i != largest_vis_mesh_index:
            constraint = joint.constraints.new(type="CHILD_OF")
            if hasattr(constraint, "target"):
                constraint.target = largest_vis_mesh_joint
            constraint.name = f"ChildOf_{largest_vis_mesh_joint.name}"


def _assign_vis_meshes_to_joints(vis_meshes: list[bpy.types.Object], joints: list[bpy.types.Object]) -> None:
    """Process vis meshes and joints.
    If there is only one vis mesh, assign it to the first joint (_empty_joint_00).

    Args:
        vis_meshes (list[bpy.types.Object]): List of vis meshes
        joints (list[bpy.types.Object]): List of joints
    """
    if len(vis_meshes) == 1:
        _assign_object_to_joint(vis_meshes[0], joints[0])
    else:
        for i, vis_mesh in enumerate(vis_meshes):
            _assign_object_to_joint(vis_mesh, joints[i])


def _process_colliders(
    object_obj: bpy.types.Object,
    colliders_collection: bpy.types.Collection,
    vis_meshes: list[bpy.types.Object],
    joints: list[bpy.types.Object],
) -> None:
    """Process colliders and assign them to joints based on overlap.

    Args:
        object_obj (bpy.types.Object): The object to process
        colliders_collection (bpy.types.Collection): The collection to link colliders to
        vis_meshes (list[bpy.types.Object]): List of vis meshes
        joints (list[bpy.types.Object]): List of joints
    """
    for child in object_obj.children:
        if "coll" not in child.name:
            continue
        _unlink_from_collections(child)
        child.parent = None
        colliders_collection.objects.link(child)
        _apply_scale_transform(child)
        overlapping_pairs = _find_overlapping_vis_meshes(child, vis_meshes)
        if (
            len(overlapping_pairs) == 1
        ):  # If there is only one overlapping vis mesh, assign the collider to the joint of that vis mesh
            _assign_object_to_joint(child, joints[overlapping_pairs[0][1]])
        elif len(overlapping_pairs) > 1:  # If there are multiple overlapping vis meshes, find the best match
            best_match_index = _find_best_match_vis_mesh(child, overlapping_pairs, vis_meshes)
            _assign_object_to_joint(child, joints[best_match_index])
        else:
            pass  # Collider does not overlap with any vis mesh


def _find_overlapping_vis_meshes(
    collider: bpy.types.Object, vis_meshes: list[bpy.types.Object]
) -> list[tuple[bpy.types.Object, int, float]]:
    """Find all vis meshes that overlap with the collider.

    Args:
        collider (bpy.types.Object): The collider to process
        vis_meshes (list[bpy.types.Object]): List of vis meshes

    Returns:
        list[tuple[bpy.types.Object, int, float]]: List of overlapping pairs
    """
    overlapping_pairs = []
    for i, vis_mesh in enumerate(vis_meshes):
        overlap = bounding_boxes_overlap(collider, vis_mesh)
        if overlap > 0:
            # print(f"Collider {collider.name} overlaps with vis mesh {i}: {vis_mesh.name}; overlap = {overlap}")
            overlapping_pairs.append((collider, i, overlap))
    return overlapping_pairs


def _find_best_match_vis_mesh(
    collider: bpy.types.Object,
    overlapping_pairs: list[tuple[bpy.types.Object, int, float]],
    vis_meshes: list[bpy.types.Object],
) -> int:
    """Find the best match vis mesh from overlapping pairs.

    Args:
        collider (bpy.types.Object): The collider to process
        overlapping_pairs (list[tuple[bpy.types.Object, int, float]]): List of overlapping pairs
        vis_meshes (list[bpy.types.Object]): List of vis meshes

    Returns:
        int: Index of the best match vis mesh
    """
    # Find the best match vis mesh by the largest overlap volume
    data = []  # (distance, overlap_volume, vis_index)
    collider_center = get_bounding_box_center(collider)
    for collider_index, vis_index, overlap_volume in overlapping_pairs:
        vis_center = get_bounding_box_center(vis_meshes[vis_index])
        distance = (collider_center - vis_center).length
        data.append((overlap_volume, distance, collider_index, vis_index))
    largest_overlap_volume = max(data, key=lambda x: x[0])[0]
    best_match_pair_indices = [
        i for i, (overlap_volume, _, _, _) in enumerate(data) if overlap_volume == largest_overlap_volume
    ]
    if len(best_match_pair_indices) > 1:
        # If there are multiple vis meshes with the same overlap volume, choose the one with the smallest distance
        best_match_pair_index = min(best_match_pair_indices, key=lambda i: data[i][1])
    else:
        best_match_pair_index = best_match_pair_indices[0]
    # If there are multiple vis meshes with the same overlap volume and distance, choose the one with the smallest volume
    best_match_pair_indices = [
        i
        for i, (overlap_volume, distance, _, _) in enumerate(data)
        if overlap_volume == data[best_match_pair_index][0] and distance == data[best_match_pair_index][1]
    ]
    if len(best_match_pair_indices) > 1:
        best_match_pair_index = min(best_match_pair_indices, key=lambda i: data[i][2])
    else:
        best_match_pair_index = best_match_pair_indices[0]
    return data[best_match_pair_index][3]


def _assign_object_to_joint(object: bpy.types.Object, joint: bpy.types.Object) -> None:
    """Assign an object to a joint using constraints.

    Args:
        object (bpy.types.Object): The object to assign
        joint (bpy.types.Object): The joint to assign the object to
    """
    constraint = object.constraints.new(type="CHILD_OF")
    if hasattr(constraint, "target"):
        constraint.target = joint
    constraint.name = f"ChildOf_{joint.name}"


def _unlink_from_collections(obj: bpy.types.Object) -> None:
    """Unlink an object from all collections.

    Args:
        obj (bpy.types.Object): The object to unlink
    """
    for collection in obj.users_collection:
        collection.objects.unlink(obj)


def _apply_scale_transform(obj: bpy.types.Object) -> None:
    """Apply scale transform to an object.

    Args:
        obj (bpy.types.Object): The object to apply the scale transform to
    """
    if bpy.context.view_layer:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


def _cleanup_old_hierarchy(root_obj: bpy.types.Object) -> None:
    """Remove the old root object and its hierarchy.

    Args:
        root_obj (bpy.types.Object): The root object to remove
    """
    _remove_recursive(root_obj)
    bpy.data.objects.remove(root_obj, do_unlink=True)


def _remove_recursive(obj: bpy.types.Object) -> None:
    """Recursively remove an object and its children.

    Args:
        obj (bpy.types.Object): The object to remove
    """
    for child in obj.children:
        _remove_recursive(child)
        bpy.data.objects.remove(child, do_unlink=True)


def get_bounding_box(obj: bpy.types.Object) -> list[mathutils.Vector]:
    """Get world space bounding box corners of an object.

    Args:
        obj (bpy.types.Object): The object to get the bounding box of

    Returns:
        list[mathutils.Vector]: List of world space bounding box corners
    """
    return [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]


def get_bounding_box_center(obj: bpy.types.Object) -> mathutils.Vector:
    """Get the center point of an object's bounding box.

    Args:
        obj (bpy.types.Object): The object to get the center of

    Returns:
        mathutils.Vector: Center point of the bounding box
    """
    bbox = get_bounding_box(obj)
    return sum(bbox, mathutils.Vector()) / len(bbox)


def get_bounding_box_volume(obj: bpy.types.Object) -> float:
    """Get the volume of an object's bounding box.

    Args:
        obj (bpy.types.Object): The object to get the volume of

    Returns:
        float: Volume of the bounding box
    """
    bbox = get_bounding_box(obj)
    dims = [(max(v[i] for v in bbox) - min(v[i] for v in bbox)) for i in range(3)]
    return abs(dims[0] * dims[1] * dims[2])


def bounding_boxes_overlap(obj1: bpy.types.Object, obj2: bpy.types.Object) -> float:
    """Check if two objects' bounding boxes overlap and return overlap volume.

    Args:
        obj1 (bpy.types.Object): The first object
        obj2 (bpy.types.Object): The second object

    Returns:
        float: Overlap volume
    """
    minmax1 = _get_bbox_minmax(get_bounding_box(obj1))
    minmax2 = _get_bbox_minmax(get_bounding_box(obj2))
    overlaps = []
    for i in range(3):
        min1, max1 = minmax1[i]
        min2, max2 = minmax2[i]
        if min1 <= max2 and max1 >= min2:
            overlaps.append(min(max1, max2) - max(min1, min2))
        else:
            return 0
    return overlaps[0] * overlaps[1] * overlaps[2]


def _get_bbox_minmax(bbox: list[mathutils.Vector]) -> list[tuple[float, float]]:
    """Helper to get min/max coordinates from bounding box.

    Args:
        bbox (list[mathutils.Vector]): The bounding box

    Returns:
        list[tuple[float, float]]: List of min/max coordinates
    """
    return [(min(v[i] for v in bbox), max(v[i] for v in bbox)) for i in range(3)]


def normalize_asset_position(
    vis_meshes: list[bpy.types.Object],
    joints: list[bpy.types.Object],
    use_included_colliders: bool = False,
) -> None:
    """Normalize the position of an asset so it sits on the ground plane (Z=0).

    This function calculates the overall bounding box of the entire asset (considering
    all vis_meshes, joints, and colliders together), then translates all objects
    uniformly by the same amount so that the bottom of the asset sits at Z=0.
    This ensures that multi-part assets (like a bottle + cap) move together as a unit.

    Args:
        vis_meshes (list[bpy.types.Object]): List of visual mesh objects
        joints (list[bpy.types.Object]): List of joint objects
        use_included_colliders (bool): Whether colliders are included in the asset
    """
    # Collect all objects that belong to the asset
    all_objects = list(vis_meshes) + list(joints)

    # Add colliders if they exist
    if use_included_colliders:
        colliders_collection = bpy.data.collections.get("Colliders")
        if colliders_collection:
            all_objects.extend(colliders_collection.objects)

    if not all_objects:
        print("WARNING: No objects found to normalize position")
        return

    # CaLculate the overall bounding box by collecting all corners from all objects
    # This ensures we get the true minimum Z of the entire asset assembly
    all_bbox_corners = []
    valid_objects = []

    for obj in all_objects:
        if obj.type not in {"MESH", "EMPTY"}:
            continue
        bbox = get_bounding_box(obj)
        if not bbox:
            continue
        all_bbox_corners.extend(bbox)
        valid_objects.append(obj)

    if not all_bbox_corners:
        print("WARNING: No valid bounding boxes found to normalize position")
        return

    # Find the minimum Z coordinate across all bounding box corners
    # This gives us the bottom of the entire asset assembly
    min_z = min(corner.z for corner in all_bbox_corners)

    # Calculate the translation needed to bring the bottom to Z=0
    translation_z = -min_z

    if abs(translation_z) < 0.0001:  # Already at ground level (within tolerance)
        print(f"Asset already at ground level (min_z: {min_z:.6f})")
        return

    print(f"Normalizing asset position: overall min_z={min_z:.6f}, translating all objects by {translation_z:.6f}")

    # Translate all objects uniformly by the same vector
    # This preserves parent-child relationships and constraints
    translation_vector = mathutils.Vector((0.0, 0.0, translation_z))
    for obj in valid_objects:
        obj.location += translation_vector

    print(f"✅ Asset normalized to ground plane (Z=0) - {len(valid_objects)} objects translated uniformly")
