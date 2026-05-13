# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import os

current_dir = os.path.dirname(os.path.abspath(__file__))
import difflib  # noqa E402
import glob  # noqa E402
import os  # noqa E402
import re  # noqa E402
import shutil  # noqa E402
import subprocess  # noqa E402
import tempfile  # noqa E402
from contextlib import suppress  # noqa E402

import bpy  # noqa E402
import png  # noqa E402
from PIL import Image, PngImagePlugin  # noqa E402
from PIL.ExifTags import TAGS  # noqa E402

import CORE_ArtistTools.addon.validators.logging_controller as logger  # noqa E402
from CORE_ArtistTools.addon.validators.system_checks import system_type  # noqa E402
from CORE_ArtistTools.addon.validators.validate_utils import (  # noqa E402
    check_if_in_geometry_collection,
)
from CORE_ArtistTools.addon.validators.validation_base import (  # noqa E402
    Action,
    InstancePlugin,
)


def expand_udim_path(texture_path):
    """
    Expands UDIM texture paths to find all actual tile files on disk.

    Args:
        texture_path: Path that may contain <UDIM> or <udim> placeholder

    Returns:
        List of existing texture file paths. Returns empty list if no files found.
    """
    # Check if path contains UDIM placeholder (case-insensitive)
    if "<udim>" in texture_path.lower():
        # Replace <UDIM> or <udim> with glob pattern to match UDIM numbers (1001-1100 typical range)
        pattern = re.sub(r"<udim>", "*", texture_path, flags=re.IGNORECASE)

        # Find all matching files
        matching_files = glob.glob(pattern)

        # Filter to only include files that match the UDIM numbering pattern (1001-1100+)
        # This ensures we only match actual UDIM tiles and not other files
        udim_files = []
        for file_path in matching_files:
            # Extract the part that replaced <UDIM> and check if it's a valid UDIM number
            # UDIM numbers are typically 1001-1100+ (1001 = U0V0, 1002 = U1V0, 1011 = U0V1, etc.)
            file_basename = os.path.basename(file_path)
            # Check if there's a 4-digit number that could be a UDIM (1001 or higher)
            if re.search(r"10\d{2}", file_basename):
                udim_files.append(file_path)

        return udim_files
    else:
        # Not a UDIM path, return original if it exists
        return [texture_path] if os.path.exists(texture_path) else []


# TODO: Work with perforce permission too.
def set_full_control(filepath):
    if system_type == "Windows":
        try:
            subprocess.run(["icacls", filepath, "/grant", "Everyone:F"], check=True)
            logger.logging.info(f"Set full control for: {filepath}")
        except FileNotFoundError:
            logger.logging.error(f"Error: File not found: {filepath}")
        except PermissionError:
            logger.logging.error(f"Error: Insufficient permissions for: {filepath}")
        except subprocess.CalledProcessError as e:
            logger.logging.error(f"Error: subprocess.CalledProcessError: {e.returncode}")
        except Exception as e:
            logger.logging.error(f"Error: Unexpected error: {e}")

    elif system_type == "Linux":
        try:
            subprocess.run(["setfacl", "-m", "u::rwx,g::rwx,o::rwx", filepath], check=True)
            logger.logging.info(f"Set full control for: {filepath}")
        except FileNotFoundError:
            logger.logging.error(f"Error: File not found: {filepath}")
        except PermissionError:
            logger.error(f"Error: Insufficient permissions for: {filepath}")
        except subprocess.CalledProcessError as e:
            logger.logging.error(f"Error: subprocess.CalledProcessError: {e.returncode}")
        except Exception as e:
            logger.logging.error(f"Error: Unexpected error: {e}")
    elif system_type == "Darwin":
        try:
            subprocess.run(["chmod", "+a", "everyone allow read,write,execute", filepath], check=True)
            logger.logging.info(f"Set full control for: {filepath}")
        except FileNotFoundError:
            logger.logging.error(f"Error: File not found: {filepath}")
        except PermissionError:
            logger.logging.error(f"Error: Insufficient permissions for: {filepath}")
        except subprocess.CalledProcessError as e:
            logger.logging.error(f"Error: subprocess.CalledProcessError: {e.returncode}")
        except Exception as e:
            logger.logging.error(f"Error: Unexpected error: {e}")
    else:
        logger.logging.warning(f"Unsupported platform, your OS is:{system_type}")


def save_permissions(filepath):
    if system_type == "Windows":
        with suppress(Exception):
            subprocess.run(["icacls", filepath, "/save", "permissions.txt"], check=True)
    elif system_type == "Linux":
        with suppress(Exception):
            subprocess.run(["getfacl", "-R", filepath], check=True)
    elif system_type == "Darwin":
        with suppress(Exception):
            subprocess.run(["ls", "-l", filepath], check=True)
    else:
        logger.logging.error(f"Unsupported platform, your OS is:{system_type}")


def restore_permissions(filepath):
    if system_type == "Windows":
        try:
            subprocess.run(["icacls", filepath, "/restore", "permissions.txt"], check=True)
            logger.logging.info(f"Restored permissions for: {filepath}")
        except subprocess.CalledProcessError as e:
            logger.logging.error(f"Error restoring permissions: {e}")
    elif system_type == "Linux":
        try:
            subprocess.run(["setfacl", "-R", filepath], check=True)
            logger.logging.info(f"Restored permissions for: {filepath}")
        except subprocess.CalledProcessError as e:
            logger.logging.error(f"Error restoring permissions: {e}")
    elif system_type == "Darwin":
        try:
            subprocess.run(["chmod", "-R", "u+rwX", filepath], check=True)
            logger.logging.info(f"Restored permissions for: {filepath}")
        except subprocess.CalledProcessError as e:
            logger.logging.error(f"Error restoring permissions: {e}")
    else:
        logger.logging.error(f"Unsupported platform, your OS is:{system_type}")


known_veh_parts = [
    "body",
    "grill",
    "hood",
    "trunk",
    "undercarriage",
    "interior",
    "door_0",
    "door_1",
    "door_2",
    "door_3",
    "door_trunk",
    "door_hood",
    "door_sunroof",
    "glass",
    "glass_0",
    "glass_1",
    "glass_2",
    "glass_3",
    "lights",
    "lights_0",
    "lights_1",
    "lights_trunk",
    "brake_0",
    "brake_1",
    "brake_2",
    "brake_3",
    "wheel_0",
    "wheel_1",
    "wheel_2",
    "wheel_3",
    "wheel_front_0",
    "wheel_front_1",
    "wheel_rear_2",
    "wheel_rear_3",
    "wheel_all_0",
    "wheel_all_1",
    "wheel_all_2",
    "wheel_all_3",
]

known_veh_mats = [
    "CarPaint",
    "Textured",
    "Rubber",
    "Plastic",
    "Chrome",
    "WheelRim",
    "Tire",
    "Muffler",
    "ChromeVariable",
    "BrakeRotor",
    "InteriorRough",
    "InteriorLight",
    "InteriorMedium",
    "InteriorDark",
    "GlassTintMedium",
    "GlassTintDark",
    "GlassWhite",
    "GlassRed",
    "GlassOrange",
    "GlassClear",
    "HeadLights",
    "BrakeLights",
    "ReverseLights",
    "NightLights",
    "BlinkerLights_fl",
    "BlinkerLights_fr",
    "BlinkerLights_rl",
    "BlinkerLights_rr",
    "RunningLights_fl",
    "RunningLights_fr",
    "TailLights_rl",
    "TailLights_rr",
    "BrakeLights_BlinkerLights_rl",
    "BrakeLights_BlinkerLights_rr",
    "BrakeLights_TailLights_rl_BlinkerLights_rl",
    "BrakeLights_TailLights_rr_BlinkerLights_rr",
    "BrakeLights_TailLights_rl",
    "BrakeLights_TailLights_rr",
    "ReflectorRed",
    "ReflectorOrange",
    "ReflectorWhite",
    "FogLights",
    "HighBeamLights",
]

compliant_veh_mats = set(known_veh_mats)

known_mat_prefixes = ["m", "opaque", "trans", "thin", "clearcoat", "retro"]
known_surf_prefixes = [
    "opaque",
    "trans",
    "clear",
    "emissive",
    "glass",
    "metal",
    "paint",
    "concrete",
    "cement",
    "asphalt",
    "wood",
    "plant",
    "leaf",
    "rubber",
    "plastic",
    "vinyl",
    "stone",
    "leather",
    "fabric",
    "organic",
]

complaint_prop_mats = set(known_mat_prefixes)
compliant_surface_mats = set(known_surf_prefixes)


def _parse_first_part(first_part, result):
    """Parse the first part of material name (prefix and surface type)."""
    if "_" in first_part:
        prefix_and_surface = first_part.split("_", 1)
        if len(prefix_and_surface) == 2:
            result["prefix"] = prefix_and_surface[0]
            result["surface_type"] = prefix_and_surface[1]
        else:
            result["errors"].append(f"Invalid prefix/surface format in first part: {first_part}")
            return False
    else:
        # No prefix, first part is surface_type
        result["surface_type"] = first_part
    return True


def _parse_third_part(third_part, result):
    """Parse the third part of material name (description and variants)."""
    if "_" in third_part:
        desc_and_variants = third_part.split("_")
        result["description"] = desc_and_variants[0]
        result["variants"] = desc_and_variants[1:] if len(desc_and_variants) > 1 else []
    else:
        result["description"] = third_part


def _validate_required_components(result):
    """Validate that all required components are present."""
    if not result["surface_type"]:
        result["errors"].append("Missing surface_type")
    if not result["surface_description"]:
        result["errors"].append("Missing surface_description")
    if not result["description"]:
        result["errors"].append("Missing description")


def parse_material_name(mat_name):
    """
    Parse material name according to the pattern:
    <mat_prefix optional>_<surface_type>__<surface_description>__<description>_<variant_optional>_<variant_optional_2>

    Example: m_opaque__aluminium__brushed_a01_01

    Returns:
        dict: Parsed components with keys: prefix, surface_type, surface_description, description, variants
    """
    if not mat_name or not isinstance(mat_name, str):
        return None

    # Initialize result structure
    result = {
        "prefix": None,
        "surface_type": None,
        "surface_description": None,
        "description": None,
        "variants": [],
        "is_valid_format": False,
        "errors": [],
    }

    try:
        # Split by double underscores first to separate main components
        parts = mat_name.split("__")

        if len(parts) < 3:
            result["errors"].append(f"Material name must have at least 3 parts separated by '__': {mat_name}")
            return result

        # Parse first part: <mat_prefix optional>_<surface_type>
        if not _parse_first_part(parts[0], result):
            return result

        # Second part: <surface_description>
        result["surface_description"] = parts[1]

        # Parse third part: <description>_<variant_optional>_<variant_optional_2>
        _parse_third_part(parts[2], result)

        # Validate that we have the required components
        _validate_required_components(result)

        # If no errors, mark as valid format
        if not result["errors"]:
            result["is_valid_format"] = True

    except Exception as e:
        result["errors"].append(f"Error parsing material name: {str(e)}")

    return result


def validate_material_components(parsed_name):
    """
    Validate the components of a parsed material name against known valid values.

    Args:
        parsed_name (dict): Result from parse_material_name()

    Returns:
        dict: Validation results with errors and warnings
    """
    validation_result = {"is_valid": True, "errors": [], "warnings": []}

    if not parsed_name or not parsed_name["is_valid_format"]:
        validation_result["is_valid"] = False
        validation_result["errors"].extend(parsed_name.get("errors", ["Invalid format"]))
        return validation_result

    # Validate prefix (optional)
    if parsed_name["prefix"]:
        if parsed_name["prefix"] not in complaint_prop_mats:
            validation_result["errors"].append(
                f"Invalid material prefix '{parsed_name['prefix']}'. Valid prefixes: {list(complaint_prop_mats)}"
            )
            validation_result["is_valid"] = False

    # Validate surface_type
    if parsed_name["surface_type"] not in compliant_surface_mats:
        validation_result["errors"].append(
            f"Invalid surface type '{parsed_name['surface_type']}'. Valid types: {list(compliant_surface_mats)}"
        )
        validation_result["is_valid"] = False

    # Validate surface_description (no predefined list, but check for basic format)
    if parsed_name["surface_description"]:
        if not parsed_name["surface_description"].replace("_", "").isalnum():
            validation_result["warnings"].append(
                f"Surface description '{parsed_name['surface_description']}' contains non-alphanumeric characters"
            )

    # Validate description (no predefined list, but check for basic format)
    if parsed_name["description"]:
        if not parsed_name["description"].replace("_", "").isalnum():
            validation_result["warnings"].append(
                f"Description '{parsed_name['description']}' contains non-alphanumeric characters"
            )

    # Validate variants (optional, but check format if present)
    for i, variant in enumerate(parsed_name["variants"]):
        if not variant.replace("_", "").isalnum():
            validation_result["warnings"].append(f"Variant {i+1} '{variant}' contains non-alphanumeric characters")

    return validation_result


def test_material_naming_validation():
    """
    Test function to demonstrate material naming validation with various examples.
    This can be called to verify the validation logic works correctly.
    """
    test_cases = [
        # Valid examples (should pass)
        "m_opaque__aluminium__brushed_a01_01",
        "m_opaque__rubber__blackmooth_a01_01",
        "m_opaque__metal__gloss_a01_01",
        "m_opaque__plastic__commandpanel_a01_01",
        "m_opaque__metal__painted_white_gloss_a01_01",
        # Should raise warning (invalid surface type)
        "m_clear__glass__stove_cover_a01_01",  # "clear" is not a valid surface type, should be "trans"
        # Other test cases
        "opaque__metal__steel_clean",
        "trans__glass__clear_thick",
        "thin__plastic__white_matte",
        # Invalid examples
        "invalid_name",
        "opaque_aluminium_brushed",  # Missing double underscores
        "bad_prefix__metal__steel",  # Invalid prefix
        "opaque__bad_surface__steel",  # Invalid surface type
        "opaque__metal__steel__extra_part",  # Too many parts
        "",  # Empty name
        None,  # None name
    ]

    print("=== Material Naming Validation Test ===")
    for test_name in test_cases:
        print(f"\nTesting: '{test_name}'")
        parsed = parse_material_name(test_name)
        if parsed:
            print(f"  Parsed: {parsed}")
            validation = validate_material_components(parsed)
            print(f"  Valid: {validation['is_valid']}")
            if validation["errors"]:
                print(f"  Errors: {validation['errors']}")
            if validation["warnings"]:
                print(f"  Warnings: {validation['warnings']}")
        else:
            print("  Failed to parse")


def find_closest_match(name, valid_names, threshold=0.8):
    """
    Find the closest match for a name in a list of valid names.

    Args:
        name (str): The name to find a match for
        valid_names (list): List of valid names to match against
        threshold (float): Minimum similarity score (0-1) to consider a match

    Returns:
        tuple: (best_match, score) or (None, 0) if no match above threshold
    """
    if not name or not valid_names:
        return None, 0

    # Get the closest match using difflib's get_close_matches
    matches = difflib.get_close_matches(name, valid_names, n=1, cutoff=threshold)

    if matches:
        best_match = matches[0]
        # Calculate similarity score
        score = difflib.SequenceMatcher(None, name, best_match).ratio()
        return best_match, score

    return None, 0


def get_jpg_metadata(image_path):
    image = Image.open(image_path)
    exif_data = image._getexif()
    icc_profile = image.info.get("icc_profile")
    metadata = None

    if exif_data:
        metadata_dict = {TAGS.get(tag, tag): value for tag, value in exif_data.items()}
        for key, value in metadata_dict.items():
            logger.logging.info(f"{key}: {value}")
    else:
        logger.logging.warning("No EXIF metadata found.")

    return [icc_profile, metadata]


def get_png_metadata(pil_image, image_path) -> dict:
    icc_profile = None
    metadata = None

    try:
        if pil_image.mode not in ["RGB", "RGBA"]:
            image = pil_image.convert("RGBA" if "transparency" in pil_image.info else "RGB")
            logger.logging.info(f"Converted to: {image.mode}")
        else:
            image = pil_image

        icc_profile = image.info.get("icc_profile")
        metadata = PngImagePlugin.PngInfo()

        for key, value in image.info.items():
            if isinstance(value, str):  # Only include valid text-based metadata
                metadata.add_text(key, value)

        # header
        try:
            reader = png.Reader(filename=image_path)
            width, height, pixels, meta = reader.read()

            # just debug print to inspect the header
            logger.logging.info(f"Width: {width}, Height: {height}")
            logger.logging.info(f"Bit Depth: {meta['bitdepth']}")
            logger.logging.info(f"Greyscale: {meta['greyscale']}")
            logger.logging.info(f"Interlaced: {meta.get('interlace', 0) == 1}")
        except Exception as e:
            logger.logging.warning(f"Error reading PNG header: {e}")
    except Exception as e:
        logger.logging.warning(f"Error in get_png_metadata: {e}")

    return [icc_profile, metadata]


# TODO: GET EXR METADATA/HEADERS ALSO


def build_new_filepath(original_filepath, blender_file_path, width_adjust=-1, height_adjust=-1) -> str:
    """
    Build a new filepath for the resized texture.
    Returns the new filepath or None if it fails.
    """
    try:
        blender_folder = os.path.dirname(blender_file_path)
        real_texture_dir = os.path.abspath(os.path.join(blender_folder, "..", ".."))
        source_texture_folder = os.path.join(real_texture_dir, "texture")
        file_name, file_ext = os.path.splitext(os.path.basename(original_filepath))
        new_filepath = os.path.join(source_texture_folder, f"{file_name}_resized{file_ext}")

        if os.path.exists(new_filepath):
            save_permissions(new_filepath)
            set_full_control(new_filepath)

        if not os.path.exists(source_texture_folder):
            os.makedirs(source_texture_folder, exist_ok=True)
            logger.logging.info(f"Created texture directory: {source_texture_folder}")

        try:
            if file_ext.lower() == ".png":
                image = Image.open(original_filepath)
                icc_profile, metadata = get_png_metadata(image, original_filepath)
                resized_image = image.resize((width_adjust, height_adjust), Image.LANCZOS)
                resized_image.save(new_filepath, icc_profile=icc_profile, pnginfo=metadata)
            elif file_ext.lower() == ".jpg" or file_ext.lower() == ".jpeg":
                image = Image.open(original_filepath)
                # For JPG, we don't need to handle metadata the same way
                resized_image = image.resize((width_adjust, height_adjust), Image.LANCZOS)
                resized_image.save(new_filepath)
            else:
                # Handle other formats
                image = Image.open(original_filepath)
                resized_image = image.resize((width_adjust, height_adjust), Image.LANCZOS)
                resized_image.save(new_filepath)

            try:
                restore_permissions(new_filepath)
            except subprocess.CalledProcessError as e:
                logger.logging.warning(f"Error restoring permissions: {e}")

            logger.logging.info(f"saving fixed file to: {new_filepath}")
            return new_filepath

        except Exception as e:
            logger.logging.warning(f"Error resizing image: {e}")
            return

    except Exception as e:
        logger.logging.wanring(f"failure in build_new_filepath: {e}")
        return


def back_up_original_texture(original_filepath, blender_file_path) -> str:
    """
    Backup the original texture file to a new file with _backup suffix.
    Returns the backup filepath or None if it fails.
    """

    blender_folder = os.path.dirname(blender_file_path)
    real_texture_dir = os.path.abspath(os.path.join(blender_folder, "..", ".."))
    source_texture_folder = os.path.join(real_texture_dir, "texture")
    file_name, file_ext = os.path.splitext(os.path.basename(original_filepath))
    backup_filepath = os.path.join(source_texture_folder, f"{file_name}_backup{file_ext}")

    logger.logging.info(f"backup_filepath: {backup_filepath}")
    logger.logging.info(f"original_filepath: {original_filepath}")

    if not os.path.exists(source_texture_folder):
        os.makedirs(source_texture_folder, exist_ok=True)

    if os.path.exists(original_filepath):
        save_permissions(original_filepath)
        set_full_control(original_filepath)
        image = Image.open(original_filepath)

        if file_ext.lower() == ".png":
            icc_profile, metadata = get_png_metadata(image, original_filepath)
        elif file_ext.lower() == ".jpg" or file_ext.lower() == ".jpeg":
            # Use get_jpg_metadata with the image object
            icc_profile = image.info.get("icc_profile")
            metadata = None
        else:
            # Default for other formats
            icc_profile = image.info.get("icc_profile")
            metadata = None

        # Save with appropriate parameters based on file type
        if file_ext.lower() == ".png" and metadata:
            try:
                image.save(backup_filepath, icc_profile=icc_profile, pnginfo=metadata)
                try:
                    restore_permissions(backup_filepath)
                except subprocess.CalledProcessError as e:
                    logger.logging.warning(f"Error restoring permissions: {e}")
            except Exception as e:
                logger.logging.warning(f"Error saving backup file: {e}")
        else:
            try:
                image.save(backup_filepath, icc_profile=icc_profile)
                try:
                    restore_permissions(backup_filepath)
                except subprocess.CalledProcessError as e:
                    logger.logging.warning(f"Error restoring permissions: {e}")
            except Exception as e:
                logger.logging.warning(f"Error saving backup file: {e}")

        logger.logging.info(f"saving backup file to: {backup_filepath}")

        return backup_filepath
    return


def update_problematic_assets_after_deletion(plugin, instance, data_key, log_func=print):
    """
    Updates the problematic_assets list in the validator to remove deleted materials/objects.

    Args:
        plugin: The validator plugin instance
        instance: The current validation instance
        data_key: The key in instance.data that contains the list of materials/objects
        log_func: Function to use for logging (default: print)
    """
    # Update the problematic_assets list in the validator
    if hasattr(plugin, "problematic_assets"):
        # Create a new list without the deleted materials/objects
        updated_assets = []
        for asset_tuple in plugin.problematic_assets:
            # Each tuple is (material/object, message)
            asset = asset_tuple[0]
            # For materials, check if they still exist in Blender's data
            if isinstance(asset, bpy.types.Material):
                if asset.name not in bpy.data.materials:
                    log_func("Removed deleted material from problematic_assets list")
                    continue
            # For objects, check if they still exist in Blender's data
            elif isinstance(asset, bpy.types.Object):
                if asset.name not in bpy.data.objects:
                    log_func("Removed deleted object from problematic_assets list")
                    continue
            # Otherwise keep the asset in the list
            updated_assets.append(asset_tuple)

        # Update the validator's problematic_assets list
        plugin.problematic_assets = updated_assets

    # Also update the instance data if the data_key exists
    if data_key and data_key in instance.data:
        if isinstance(instance.data[data_key], list):
            # For materials
            if all(isinstance(item, bpy.types.Material) for item in instance.data[data_key] if item is not None):
                instance.data[data_key] = [
                    mat for mat in instance.data[data_key] if mat is not None and mat.name in bpy.data.materials
                ]
            # For objects
            elif all(isinstance(item, bpy.types.Object) for item in instance.data[data_key] if item is not None):
                instance.data[data_key] = [
                    obj for obj in instance.data[data_key] if obj is not None and obj.name in bpy.data.objects
                ]


def try_copy_via_temp(src, dst):
    """
    Try to copy a file by first copying to a temporary location, then moving to the final destination.
    This can sometimes work around permission issues.

    Args:
        src: Source file path
        dst: Destination file path

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create a temporary file
        temp_dir = tempfile.gettempdir()
        temp_filename = os.path.join(temp_dir, os.path.basename(src))

        logger.logging.info(f"Copying to temporary location: {temp_filename}")

        # Copy to temporary location
        shutil.copy2(src, temp_filename)

        # Create destination directory if it doesn't exist
        dst_dir = os.path.dirname(dst)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)

        # Move from temporary location to destination
        logger.logging.info(f"Moving from temporary location to: {dst}")
        shutil.move(temp_filename, dst)

        return True
    except Exception as e:
        logger.logging.error(f"Error in try_copy_via_temp: {e}")
        return False


# ------------------------------------------------------------------------------------------------
# AUTOFIXERS (MATERIAL)
# ------------------------------------------------------------------------------------------------
class Fix_Unused_Materials(Action):
    label = "Fix Unused Materials"
    on = "failed"

    def process(self, context, plugin):
        def delete_unused_materials():
            success = True
            for instance in context:
                mats_to_delete = instance.data.get("members", [])
                if not mats_to_delete:
                    mats_to_delete = instance.data.get("unused_mats", [])

                if not mats_to_delete:
                    self.log.info("No unused materials found.")
                    success = False
                    for instance in context:
                        instance.data["fix_success"] = success
                    return None

                # Store material names before deletion for reporting
                deleted_material_names = []

                for mat in mats_to_delete:
                    # Store the name before deletion
                    mat_name = mat.name
                    deleted_material_names.append(mat_name)

                    # Remove the material from all object slots and delete the slot
                    for obj in bpy.data.objects:
                        if obj.type == "MESH":
                            # Iterate over material slots in reverse order to safely remove slots
                            for i in range(len(obj.material_slots) - 1, -1, -1):
                                slot = obj.material_slots[i]
                                if slot.material == mat:
                                    # Remove the material slot
                                    obj.active_material_index = i
                                    bpy.ops.object.material_slot_remove({"object": obj})
                                    self.log.info(
                                        f"Removed material slot containing {mat_name} from object {obj.name}."
                                    )

                    # Delete the material regardless of whether it's marked as not fixable by other validators
                    bpy.data.materials.remove(mat, do_unlink=True)
                    self.log.info(f"Material {mat_name} removed.")

            for instance in context:
                instance.data["fix_success"] = success

            return None

        bpy.app.timers.register(delete_unused_materials, first_interval=0.1)


class Fix_Texture_Dims(Action):

    label = "Fix Texture Dims"
    on = "failed"

    def process(self, context, plugin):
        def resize_large_textures():
            success = True
            for instance in context:
                # Retrieve stored problematic objects
                objects_with_large_textures = instance.data.get("members", [])

                if not objects_with_large_textures:
                    objects_with_large_textures = instance.data.get("tex_size_issues", [])

                if not objects_with_large_textures:
                    self.log.info("No textures exceeding size limits found.")
                    success = False
                    for instance in context:
                        instance.data["fix_success"] = success
                    return None  # Stop timer

                for obj in objects_with_large_textures:
                    if not obj or obj.type != "MESH":
                        continue

                    for slot in obj.material_slots:
                        mat = slot.material
                        if not mat or not mat.use_nodes or not mat.node_tree:
                            continue

                        if "figure" in mat.name:
                            continue

                        for node in mat.node_tree.nodes:
                            try:
                                if node.type != "TEX_IMAGE":
                                    continue

                                img = node.image
                                if not hasattr(img, "size") or not img.size:
                                    continue

                                width, height = img.size[0], img.size[1]

                                # Check if texture exceeds size limits
                                if width > 4096 or height > 4096:
                                    # Calculate new dimensions while maintaining aspect ratio
                                    if width >= height:
                                        new_width = 4096
                                        new_height = int((height / width) * 4096)
                                    else:
                                        new_height = 4096
                                        new_width = int((width / height) * 4096)

                                    # Ensure dimensions are even numbers
                                    new_width = new_width if new_width % 2 == 0 else new_width - 1
                                    new_height = new_height if new_height % 2 == 0 else new_height - 1

                                    self.log.info(
                                        f"Resizing texture {img.name} from {width}x{height} to {new_width}x{new_height}"
                                    )

                                    # Get the original filepath
                                    original_filepath = img.filepath
                                    original_name = img.name
                                    current_file = bpy.data.filepath

                                    if original_filepath.startswith("//"):
                                        original_filepath = bpy.path.abspath(original_filepath)

                                    # Create a backup of the original texture
                                    backup_filepath = back_up_original_texture(original_filepath, current_file)
                                    self.log.info(f"Backed up original texture to {backup_filepath}")

                                    if not backup_filepath:
                                        self.log.error(f"Failed to back up texture: {original_filepath}")
                                        success = False

                                    try:
                                        # Create a new filepath with _resized suffix
                                        if original_filepath:
                                            abs_file_path = build_new_filepath(
                                                original_filepath, current_file, new_width, new_height
                                            )
                                            self.log.info(f"new_filepath: {abs_file_path}")

                                            try:
                                                # First check if the image already exists in Blender's data
                                                existing_img = bpy.data.images.get(os.path.basename(abs_file_path))
                                                if existing_img:
                                                    # If it exists, reload it
                                                    existing_img.reload()
                                                    new_img = existing_img
                                                else:
                                                    # Otherwise load it
                                                    new_img = bpy.data.images.load(abs_file_path)

                                                # Pack the image if needed
                                                if img.packed_file:
                                                    new_img.pack()

                                                # Replace the image in the node
                                                node.image = new_img
                                                self.log.info(
                                                    f"Successfully loaded and assigned resized texture from {abs_file_path}"
                                                )
                                            except Exception as e:
                                                self.log.error(f"Error loading resized texture: {e}")
                                                # Fallback to the old method if loading fails
                                                new_img = bpy.data.images.new(
                                                    name=f"{original_name}_corrected",
                                                    width=new_width,
                                                    height=new_height,
                                                )
                                                new_img.filepath = abs_file_path
                                                new_img.reload()
                                                node.image = new_img
                                                self.log.warning("Used fallback method to assign texture")
                                            self.log.info(f"Successfully resized texture to {new_width}x{new_height}")
                                    except Exception as e:
                                        self.log.error(f"Error during texture resize operation: {e}")
                                        success = False
                            except Exception as e:
                                self.log.error(f"Error during texture processing: {e}")
                                success = False

            for instance in context:
                instance.data["fix_success"] = success

            return None

        bpy.app.timers.register(resize_large_textures, first_interval=0.1)


class Fix_VehMatNamesMispelled(Action):
    """Fix vehicle material names by replacing with closest matching valid name"""

    label = "Fix Vehicle Material Names"
    on = "failed"

    def process(self, context, plugin):
        def fix_vehicle_material_names():
            success = True
            for instance in context:
                # Retrieve stored problematic materials
                materials_with_issues = instance.data.get("members", []) or instance.data.get("veh_mat_name_issues", [])

                if not materials_with_issues:
                    self.log.info("No materials with naming issues found.")
                    success = False
                    for instance in context:
                        instance.data["fix_success"] = success
                    return None  # Stop timer

                # reformat warnings list to be a list of materials
                materials_with_issues = [mat for mat, _ in materials_with_issues]

                # Track materials that were fixed
                fixed_materials = []

                # Get fuzzy matches if available
                fuzzy_matches = instance.data.get("fuzzy_matches", {})

                for mat in materials_with_issues:

                    if not mat or "figure" in mat.name:
                        continue

                    # Skip if already a valid name
                    if mat.name in compliant_veh_mats:
                        continue

                    # Check if we have a pre-computed fuzzy match
                    if mat.name in fuzzy_matches:
                        best_match, score = fuzzy_matches[mat.name]
                        # Use a higher threshold for direct material name matching
                        direct_match_threshold = 0.8  # Increased from 0.7 to be more strict
                        if score >= direct_match_threshold:
                            self.log.info(
                                f"Fixing material name: '{mat.name}' -> '{best_match}' (similarity: {score:.2f})"
                            )

                            # Store the original name for reference
                            original_name = mat.name

                            # Rename the material
                            mat.name = best_match
                            fixed_materials.append((original_name, best_match, score))
                            continue
                        else:
                            self.log.info(
                                f"Skipping fix for '{mat.name}': Match score ({score:.2f}) below threshold ({direct_match_threshold})"
                            )

                    # If no pre-computed match, try to find one
                    best_match, score = find_closest_match(mat.name, known_veh_mats)

                    # Use the same threshold for consistency
                    direct_match_threshold = 0.8  # Increased from 0.7 to be more strict
                    if best_match and score >= direct_match_threshold:
                        self.log.info(f"Fixing material name: '{mat.name}' -> '{best_match}' (similarity: {score:.2f})")

                        # Store the original name for reference
                        original_name = mat.name

                        # Rename the material
                        mat.name = best_match
                        fixed_materials.append((original_name, best_match, score))
                    else:
                        if best_match:
                            self.log.info(
                                f"Skipping direct fix for '{mat.name}': Match score ({score:.2f}) below threshold ({direct_match_threshold})"
                            )

                # TODO: move to debug
                if fixed_materials:
                    self.log.info(f"Fixed {len(fixed_materials)} material names:")
                    for original, new, score in fixed_materials:
                        self.log.info(f"  '{original}' -> '{new}' (similarity: {score:.2f})")
                else:
                    self.log.error("No materials could be automatically fixed.")
                    success = False

            for instance in context:
                instance.data["fix_success"] = success

            return None

        bpy.app.timers.register(fix_vehicle_material_names, first_interval=0.1)


class Fix_Texture_Paths(Action):
    """Fix textures that are in the wrong directory by moving them to the correct location"""

    label = "Fix Texture Paths"
    on = "failed"

    def process(self, context, plugin):
        def move_textures_to_correct_location():
            success = True
            for instance in context:
                materials_with_bad_paths = instance.data.get("members", []) or instance.data.get("tex_path_issues", [])
                if not materials_with_bad_paths:
                    self.log.info("No textures with incorrect paths found.")
                    success = False
                    for instance in context:
                        instance.data["fix_success"] = success
                    continue

                blend_filepath = bpy.data.filepath
                blender_folder = os.path.dirname(blend_filepath)
                correct_texture_dir = os.path.abspath(os.path.join(blender_folder, "..", "..", "texture"))

                if not os.path.exists(correct_texture_dir):
                    os.makedirs(correct_texture_dir, exist_ok=True)
                    self.log.info(f"Created texture directory: {correct_texture_dir}")

                for mat in materials_with_bad_paths:
                    if "figure" in mat.name:
                        continue

                    for node in mat.node_tree.nodes:
                        if node.type != "TEX_IMAGE":
                            continue

                        image = getattr(node, "image", None)
                        if image is None:
                            continue

                        original_filepath = image.filepath
                        if original_filepath.startswith("//"):
                            original_filepath = bpy.path.abspath(original_filepath)

                        filepath_abs = os.path.abspath(os.path.normpath(original_filepath))
                        filename = os.path.basename(filepath_abs)

                        backup_filepath = back_up_original_texture(filepath_abs, blend_filepath)
                        if not backup_filepath:
                            self.log.error(f"Failed to back up texture: {filepath_abs}")
                            success = False

                        new_filepath = os.path.join(correct_texture_dir, filename)
                        try:
                            save_permissions(backup_filepath)
                            set_full_control(backup_filepath)
                            shutil.copy2(backup_filepath, new_filepath)
                            try:
                                restore_permissions(backup_filepath)
                            except subprocess.CalledProcessError as e:
                                self.log.error(f"Failed to restore permissions: {e}")
                        except Exception as e:
                            self.log.error(
                                f"Failed to copy texture to correct location: {new_filepath}. Exception: {e}"
                            )
                            success = False

                        if os.path.exists(new_filepath):
                            image.filepath = bpy.path.relpath(new_filepath)
                            image.reload()
                            self.log.info(f"Texture path fixed for: {filename}")
                        else:
                            self.log.error(
                                f"Failed to set texture in the material: {new_filepath}, filepath doesn't exist."
                            )
                            success = False

            # Update the context or instance with the success status
            for instance in context:
                instance.data["fix_success"] = success

            return None  # Stop the timer

        bpy.app.timers.register(move_textures_to_correct_location, first_interval=0.1)


# ------------------------------------------------------------------------------------------------
# VALIDATORS (MATERIAL)
# ------------------------------------------------------------------------------------------------
class Validate_VehMatNames_Mispelled(InstancePlugin):

    label = "Validate Vehicle Material Names Mispelled"

    families = ["material"]
    asset_types = ["vehicle"]
    actions = [Fix_VehMatNamesMispelled]

    def process(self, instance):
        issues = []
        warnings_dict = {}  # noqa: F841
        mats_in_question = set()
        fuzzy_matches = {}

        combined_warnings = {}
        not_fixable_mats = set()  # noqa: F841

        for obj in bpy.context.view_layer.objects:
            if obj.type != "MESH":
                continue

            for slot in obj.material_slots:
                mat = slot.material

                if "figure" in mat.name:
                    continue

                if mat and mat.name not in compliant_veh_mats:
                    # Add the material to our set only once at the beginning
                    # mats_in_question.add(mat)

                    # Try to find a close match using fuzzy matching
                    best_match, score = find_closest_match(mat.name, known_veh_mats)

                    if best_match and score > 0.8:  # High confidence match
                        # Initialize the list of warnings for this material if not already done
                        if mat not in combined_warnings:
                            combined_warnings[mat] = []

                            mats_in_question.add(mat)
                            fuzzy_matches[mat.name] = (best_match, score)
                            # score:.2f means: format 'score' as a float with 2 decimal places
                            # For example, if score is 0.857, it will show as "0.86"
                            combined_warnings[mat].append(
                                f"Material on {obj.name}: '{mat.name}' is similar to valid material '{best_match}' (similarity: {score:.2f})"
                            )
                    # else:
                    #     # No good match found, remove the material from the list
                    #     mats_in_question.remove(mat)
                    #     # combined_warnings[mat].append(f"Material on {obj.name}: won't map to preset vehicle materials with name: '{mat.name}'")

        # Store fuzzy matches for use by the fix action
        instance.data["fuzzy_matches"] = fuzzy_matches

        self.problematic_assets = issues

        warnings_list = []
        for mat, warning_msgs in combined_warnings.items():

            combined_msg = "\n".join(warning_msgs)
            warnings_list.append((mat, combined_msg))

        materials_in_warnings = {}

        for mat, msg in warnings_list:
            if mat.name not in materials_in_warnings:
                materials_in_warnings[mat.name] = 1
            else:
                materials_in_warnings[mat.name] += 1
                self.log.warning(
                    f"WARNING: Material '{mat.name}' appears {materials_in_warnings[mat.name]} times in warnings list"
                )

        instance.data["veh_mat_name_issues"] = warnings_list

        if warnings_list:
            self.warnings = warnings_list
        if issues:
            raise ValueError(msg for _, msg in issues)


class Validate_PropMatNames(InstancePlugin):

    label = "Validate Prop Material Names"

    families = ["material"]
    asset_types = ["all"]
    # actions = []

    def _process_material_slot(self, obj, slot, combined_warnings, objects_in_question, materials_with_issues):
        """Process a single material slot and validate its name."""
        mat = slot.material
        mat_name = mat.name
        self.log.info(f"Material Name: {mat_name}")

        # Skip figure materials
        if "figure" in mat_name:
            return

        # Parse the material name according to the pattern
        parsed_name = parse_material_name(mat_name)

        if not parsed_name:
            combined_warnings[obj].append(f"Material '{mat_name}' on {obj.name}: Failed to parse material name")
            objects_in_question.add(obj)
            materials_with_issues.append(mat)
            return

        # Validate the parsed components
        validation_result = validate_material_components(parsed_name)

        has_errors = False
        has_warnings = False

        # Process errors (these are critical issues)
        if validation_result["errors"]:
            has_errors = True
            for error in validation_result["errors"]:
                combined_warnings[obj].append(f"Material '{mat_name}' on {obj.name}: {error}")

        # Process warnings (these are less critical but worth noting)
        if validation_result["warnings"]:
            has_warnings = True
            for warning in validation_result["warnings"]:
                combined_warnings[obj].append(f"Material '{mat_name}' on {obj.name}: WARNING - {warning}")

        # Add to problematic objects if there are any issues
        if has_errors or has_warnings:
            objects_in_question.add(obj)
            materials_with_issues.append(mat)

    def _process_mesh_objects(self, combined_warnings, objects_in_question, materials_with_issues):
        """Process all mesh objects and their material slots."""
        for obj in bpy.context.view_layer.objects:
            if obj.type != "MESH":
                continue

            # Skip objects that don't exist in a collection called "Geometry"
            if not check_if_in_geometry_collection(obj):
                continue

            if obj not in combined_warnings:
                combined_warnings[obj] = []

            for slot in obj.material_slots:
                self._process_material_slot(obj, slot, combined_warnings, objects_in_question, materials_with_issues)

    def _create_warnings_list(self, combined_warnings):
        """Create a list of warnings from the combined warnings dictionary."""
        warnings_list = []
        for obj, warning_msgs in combined_warnings.items():
            if warning_msgs:
                combined_msg = "\n".join(warning_msgs)
                warnings_list.append((obj, combined_msg))
        return warnings_list

    def _log_duplicate_warnings(self, warnings_list):
        """Log warnings about duplicate objects in the warnings list."""
        objects_in_warnings = {}
        for obj, msg in warnings_list:
            if obj.name not in objects_in_warnings:
                objects_in_warnings[obj.name] = 1
            else:
                objects_in_warnings[obj.name] += 1
                self.log.warning(
                    f"WARNING: Object '{obj.name}' appears {objects_in_warnings[obj.name]} times in warnings list"
                )

    def process(self, instance):
        issues = []
        warnings_dict = {}  # noqa: F841
        objects_in_question = set()
        combined_warnings = {}
        materials_with_issues = []

        # Process all mesh objects and their material slots
        self._process_mesh_objects(combined_warnings, objects_in_question, materials_with_issues)

        instance.data["prop_mat_name_issues"] = list(objects_in_question)
        instance.data["problematic_materials"] = materials_with_issues
        self.problematic_assets = issues

        # Create warnings list and log results
        warnings_list = self._create_warnings_list(combined_warnings)

        self.log.info(f"Found {len(objects_in_question)} objects with material naming issues")
        self.log.info(f"Found {len(materials_with_issues)} materials with naming issues")
        self.log.info(f"Found {len(warnings_list)} unique objects with warnings")

        self._log_duplicate_warnings(warnings_list)

        if warnings_list:
            self.warnings = warnings_list
        if issues:
            raise ValueError(msg for _, msg in issues)


class Validate_Texture_Dims(InstancePlugin):

    label = "Validate Texture Dimensions"

    families = ["mesh"]
    asset_types = ["all"]
    actions = [Fix_Texture_Dims]

    def process(self, instance):

        texture_issues = {}
        objects_in_question = set()
        combined_issues = {}
        disable_fix = False

        for obj in bpy.context.view_layer.objects:
            if obj.type != "MESH":
                continue

            # Skip objects that don't exist in a collection called "Geometry"
            if not check_if_in_geometry_collection(obj):
                continue

            if obj not in combined_issues:
                combined_issues[obj] = []

            with suppress(AttributeError):
                for slot in obj.material_slots:
                    mat = slot.material
                    if mat.use_nodes and mat.node_tree:
                        for node in mat.node_tree.nodes:
                            if node.type == "TEX_IMAGE":
                                img = node.image
                                if hasattr(img, "size") and img.size:
                                    # Check if the texture file exists on disk (handle UDIM textures)
                                    texture_path = os.path.abspath(os.path.normpath(bpy.path.abspath(img.filepath)))
                                    existing_files = expand_udim_path(texture_path)

                                    if not existing_files:
                                        # No files found - either regular texture missing or no UDIM tiles found
                                        is_udim = "<udim>" in texture_path.lower()
                                        error_msg = f"Texture file not found on disk: {texture_path}"
                                        if is_udim:
                                            error_msg = f"No UDIM tiles found for: {texture_path}"

                                        self.log.error(error_msg)
                                        has_issue = True
                                        disable_fix = True
                                        texture_key = f"{img.name}_missing"
                                        if texture_key not in texture_issues:
                                            texture_issues[texture_key] = (obj, error_msg)
                                            combined_issues[obj].append(error_msg)
                                        continue

                                    width, height = img.size[0], img.size[1]
                                    self.log.info(f"Texture {img.name} size: {width}x{height}")
                                    texture_key = f"{img.name}_{width}x{height}"
                                    has_issue = False

                                    if width > 4096 or height > 4096:
                                        self.log.warning(f"Texture {img.name} is too large: {width}x{height}")
                                        has_issue = True
                                        if texture_key not in texture_issues:
                                            issue_msg = f"Texture {img.name} is too large: {width}x{height}"
                                            texture_issues[texture_key] = (obj, issue_msg)
                                            combined_issues[obj].append(issue_msg)

                                    if has_issue:
                                        objects_in_question.add(obj)

        # Some errors should disable the fix action
        if disable_fix:
            self.actions = []

        # Check for duplicate texture keys
        combined_issues_list = []
        for obj, issue_msgs in combined_issues.items():
            if issue_msgs:
                combined_msg = "\n".join(issue_msgs)
                combined_issues_list.append((obj, combined_msg))

        self.log.info(f"Found {len(objects_in_question)} objects with texture size issues")
        self.log.info(f"Found {len(texture_issues)} unique texture size issues")
        self.log.info(f"Found {len(combined_issues_list)} objects with combined issues")

        instance.data["tex_size_issues"] = list(objects_in_question)
        self.problematic_assets = combined_issues_list

        self.warnings = []

        if combined_issues_list:
            raise ValueError(msg for _, msg in combined_issues_list)


class Validate_Texture_Paths(InstancePlugin):

    label = "Validate Textures Paths"

    families = ["mesh"]
    asset_types = ["all"]
    actions = [Fix_Texture_Paths]

    def process(self, instance):

        texture_issues = {}
        materials_with_issues = set()
        blend_filepath = bpy.data.filepath
        disable_fix = False
        combined_issues = {}

        for obj in bpy.context.view_layer.objects:
            if obj.type != "MESH":
                continue

            # Skip objects that don't exist in a collection called "Geometry"
            if not check_if_in_geometry_collection(obj):
                continue

            # Reset has_issue for each object
            has_issue = False

            for slot in obj.material_slots:
                mat = slot.material

                if "figure" in mat.name:
                    continue

                with suppress(AttributeError):
                    if mat.use_nodes and mat.node_tree:
                        for node in mat.node_tree.nodes:
                            if node.type == "TEX_IMAGE":
                                image = node.image

                                texture_path = os.path.abspath(os.path.normpath(bpy.path.abspath(image.filepath)))
                                existing_files = expand_udim_path(texture_path)

                                if not existing_files:
                                    # No files found - either regular texture missing or no UDIM tiles found
                                    is_udim = "<udim>" in texture_path.lower()
                                    error_msg = f"Texture file not found on disk: {texture_path}"
                                    if is_udim:
                                        error_msg = f"No UDIM tiles found for: {texture_path}"

                                    self.log.error(error_msg)
                                    has_issue = True
                                    disable_fix = True
                                    texture_key = f"{image.name}_missing"
                                    if texture_key not in texture_issues:
                                        texture_issues[texture_key] = (obj, error_msg)
                                        if obj not in combined_issues:
                                            combined_issues[obj] = []
                                        combined_issues[obj].append(error_msg)
                                else:
                                    blender_folder = os.path.dirname(blend_filepath)
                                    real_texture_parent = os.path.abspath(os.path.join(blender_folder, "..", ".."))
                                    real_texture_dir = os.path.join(real_texture_parent, "texture")
                                    filepath = bpy.path.abspath(image.filepath)
                                    filepath_abs = os.path.normpath(filepath)
                                    filepath_dir = os.path.dirname(filepath_abs)
                                    filename = os.path.basename(filepath_abs)

                                    # The correct place for blender texture should be in {blender directory} ../../texture
                                    # Autofix: Move/Copy textures to correct location
                                    if filepath_dir != real_texture_dir:
                                        self.log.info(f"filepath_dir: {filepath_dir}")

                                        if filepath_abs not in texture_issues:
                                            issue_msg = f"Texture '{filename}' wrong directory. \nTexture belongs in Source/texture"
                                            has_issue = True
                                            texture_issues[filepath_abs] = (obj, issue_msg)
                                            combined_issues[obj] = []
                                            combined_issues[obj].append(issue_msg)

                                if has_issue:
                                    materials_with_issues.add(mat)

        print(f"materials_with_issues: {materials_with_issues}")

        # Some errors should disable the fix action
        if disable_fix:
            self.actions = []

        combined_issues_list = []
        for obj, issue_msgs in combined_issues.items():
            if issue_msgs:
                combined_msg = "\n".join(issue_msgs)
                combined_issues_list.append((obj, combined_msg))

        self.log.info(f"Found {len(materials_with_issues)} materials with texture path issues")
        self.log.info(f"Found {len(texture_issues)} unique texture path issues")
        self.log.info(f"Found {len(combined_issues_list)} objects with combined issues")

        instance.data["tex_path_issues"] = list(materials_with_issues)
        self.problematic_assets = combined_issues_list

        self.warnings = []

        if combined_issues_list:
            error_messages = [msg for _, msg in combined_issues_list]
            error_message = "\n".join(error_messages) if len(error_messages) > 1 else error_messages[0]
            raise ValueError(error_message)


class Validate_Unused_Materials(InstancePlugin):

    label = "Validate Unused Materials"

    families = ["mesh"]
    asset_types = ["all"]
    actions = [Fix_Unused_Materials]

    def process(self, instance):

        material_issues = {}
        mats_to_delete = set()
        combined_issues = {}

        for mat in bpy.data.materials:
            if mat.users == 0 and "figure" not in mat.name:
                if mat not in combined_issues:

                    combined_issues[mat] = []

                    issue_msg = f"Unused material: {mat.name}"
                    combined_issues[mat].append(issue_msg)
                    mats_to_delete.add(mat)
                    self.log.info(f"mats_to_delete: {mats_to_delete}")

        for obj in instance:
            if obj.type != "MESH":
                continue

            mesh = obj.data
            used_material_indices = set()

            for poly in mesh.polygons:
                used_material_indices.add(poly.material_index)

            for i, slot in enumerate(obj.material_slots):
                mat = slot.material
                if mat and "figure" not in mat.name:
                    if i not in used_material_indices:
                        is_used_elsewhere = False
                        for other_obj in bpy.data.objects:
                            if other_obj.type == "MESH" and other_obj != obj:
                                if mat in [slot.material for slot in other_obj.material_slots]:
                                    is_used_elsewhere = True
                                    break

                        if not is_used_elsewhere:
                            mat_key = f"{mat.name}"
                            if mat_key not in material_issues:
                                issue_msg = f"Unused material: {mat.name} found on object: {obj.name}"
                                material_issues[mat_key] = (mat, issue_msg)
                                if mat not in combined_issues:
                                    combined_issues[mat] = []
                                combined_issues[mat].append(issue_msg)
                            mats_to_delete.add(mat)

        combined_issues_list = []
        for mat, issue_msgs in combined_issues.items():
            if issue_msgs:
                self.log.info(f"logging unused mats: {mats_to_delete}")
                combined_msg = "\n".join(issue_msgs)
                combined_issues_list.append((mat, combined_msg))

        instance.data["unused_mats"] = list(mats_to_delete)
        self.problematic_assets = combined_issues_list

        self.warnings = []

        if combined_issues_list:

            error_messages = [msg for _, msg in combined_issues_list]
            error_message = "\n".join(error_messages) if len(error_messages) > 1 else error_messages[0]
            raise ValueError(error_message)


# ------------------------------------------------------------------------------------------------
# VALIDATORS (SIMREADY PROPERTIES)
# ------------------------------------------------------------------------------------------------
class Validate_SimReady_Nonvisual_Base(InstancePlugin):
    """Validate that materials have required SimReady nonvisual base property"""

    label = "Validate SimReady Nonvisual Base"

    families = ["material"]
    asset_types = ["all"]

    def process(self, instance):
        issues = []
        combined_issues = {}

        for obj in bpy.context.view_layer.objects:
            if obj.type != "MESH":
                continue

            # Skip objects that don't exist in a collection called "Geometry"
            if not check_if_in_geometry_collection(obj):
                continue

            for slot in obj.material_slots:
                mat = slot.material

                if not mat or "figure" in mat.name:
                    continue

                # Check if material has the base property
                base_value = mat.get("omni:simready:nonvisual:base")

                if base_value is None or base_value == "":
                    if mat not in combined_issues:
                        combined_issues[mat] = []
                    combined_issues[mat].append(
                        f"Material '{mat.name}' on object '{obj.name}' is missing SimReady nonvisual:base property"
                    )

        # Create issues list
        for mat, issue_msgs in combined_issues.items():
            if issue_msgs:
                combined_msg = "\n".join(issue_msgs)
                issues.append((mat, combined_msg))

        instance.data["simready_base_issues"] = issues
        self.problematic_assets = issues

        self.warnings = []

        if issues:
            error_messages = [msg for _, msg in issues]
            error_message = "\n".join(error_messages) if len(error_messages) > 1 else error_messages[0]
            raise ValueError(error_message)


class Validate_SimReady_Nonvisual_Coating(InstancePlugin):
    """Validate that materials have required SimReady nonvisual coating property"""

    label = "Validate SimReady Nonvisual Coating"

    families = ["material"]
    asset_types = ["all"]

    def process(self, instance):
        issues = []
        combined_issues = {}

        for obj in bpy.context.view_layer.objects:
            if obj.type != "MESH":
                continue

            # Skip objects that don't exist in a collection called "Geometry"
            if not check_if_in_geometry_collection(obj):
                continue

            for slot in obj.material_slots:
                mat = slot.material

                if not mat or "figure" in mat.name:
                    continue

                # Check if material has the coating property
                coating_value = mat.get("omni:simready:nonvisual:coating")

                if coating_value is None or coating_value == "":
                    if mat not in combined_issues:
                        combined_issues[mat] = []
                    combined_issues[mat].append(
                        f"Material '{mat.name}' on object '{obj.name}' is missing SimReady nonvisual:coating property"
                    )

        # Create issues list
        for mat, issue_msgs in combined_issues.items():
            if issue_msgs:
                combined_msg = "\n".join(issue_msgs)
                issues.append((mat, combined_msg))

        instance.data["simready_coating_issues"] = issues
        self.problematic_assets = issues

        self.warnings = []

        if issues:
            error_messages = [msg for _, msg in issues]
            error_message = "\n".join(error_messages) if len(error_messages) > 1 else error_messages[0]
            raise ValueError(error_message)


class Validate_SimReady_Nonvisual_Attributes(InstancePlugin):
    """Validate that materials have required SimReady nonvisual attributes property"""

    label = "Validate SimReady Nonvisual Attributes"

    families = ["material"]
    asset_types = ["all"]

    def process(self, instance):
        issues = []
        combined_issues = {}

        for obj in bpy.context.view_layer.objects:
            if obj.type != "MESH":
                continue

            # Skip objects that don't exist in a collection called "Geometry"
            if not check_if_in_geometry_collection(obj):
                continue

            for slot in obj.material_slots:
                mat = slot.material

                if not mat or "figure" in mat.name:
                    continue

                # Check if material has the attributes property
                attributes_value = mat.get("omni:simready:nonvisual:attributes")

                if attributes_value is None or attributes_value == "":
                    if mat not in combined_issues:
                        combined_issues[mat] = []
                    combined_issues[mat].append(
                        f"Material '{mat.name}' on object '{obj.name}' is missing SimReady nonvisual:attributes property"
                    )

        # Create issues list
        for mat, issue_msgs in combined_issues.items():
            if issue_msgs:
                combined_msg = "\n".join(issue_msgs)
                issues.append((mat, combined_msg))

        instance.data["simready_attributes_issues"] = issues
        self.problematic_assets = issues

        self.warnings = []

        if issues:
            error_messages = [msg for _, msg in issues]
            error_message = "\n".join(error_messages) if len(error_messages) > 1 else error_messages[0]
            raise ValueError(error_message)


class Validate_Physics_Material_Properties(InstancePlugin):
    """Validate that objects with physics materials have proper physics properties"""

    label = "Validate Physics Material Properties"

    families = ["mesh"]
    asset_types = ["all"]

    def process(self, instance):
        issues = []
        combined_issues = {}
        objects_in_question = set()

        for obj in bpy.context.view_layer.objects:
            if obj.type != "MESH":
                continue

            # Skip objects that don't exist in a collection called "Geometry"
            if not check_if_in_geometry_collection(obj):
                continue

            # Check if any materials have physics type set
            has_physics_material = False
            for slot in obj.material_slots:
                mat = slot.material

                if not mat or "figure" in mat.name:
                    continue

                physics_type = mat.get("pxr:usd:physics_type")
                if physics_type:
                    has_physics_material = True

                    # Validate required physics properties on material
                    required_props = [
                        "pxr:usd:physics_density",
                        "pxr:usd:physics_dynamicFriction",
                        "pxr:usd:physics_staticFriction",
                        "pxr:usd:physics_restitution",
                    ]

                    for prop in required_props:
                        if mat.get(prop) is None:
                            if obj not in combined_issues:
                                combined_issues[obj] = []
                            combined_issues[obj].append(
                                f"Material '{mat.name}' has physics_type but missing property '{prop}' suggest"
                            )
                            objects_in_question.add(obj)
                else:  # add error that material is missing physics material
                    if obj not in combined_issues:
                        combined_issues[obj] = []
                    combined_issues[obj].append(f"Object '{obj.name}' has no physics materials")
                    objects_in_question.add(obj)

            # If object has physics materials, validate object-level properties
            if has_physics_material:
                required_obj_props = [
                    "pxr:usd:physics_mass",
                    "pxr:usd:physics_centerofmass",
                    "pxr:usd:physics_inertia",
                    "pxr:physics:principalAxes",
                ]

                for prop in required_obj_props:
                    if obj.get(prop) is None:
                        if obj not in combined_issues:
                            combined_issues[obj] = []
                        combined_issues[obj].append(
                            f"Object '{obj.name}' has physics materials but missing property '{prop}', \n recommend re-assigning physics properties to the material"
                        )
                        objects_in_question.add(obj)

                # Validate mass is reasonable (not zero or negative)
                mass = obj.get("pxr:usd:physics_mass")
                if mass is not None and mass <= 0:
                    if obj not in combined_issues:
                        combined_issues[obj] = []
                    combined_issues[obj].append(
                        f"Object '{obj.name}' has invalid physics_mass value: {mass} (must be > 0), \n recommend re-assigning physics properties to the material"
                    )
                    objects_in_question.add(obj)

                # Validate diagonal inertia tensor values are positive
                inertia = obj.get("pxr:usd:physics_inertia")
                if inertia is not None:
                    # Inertia should be a 3-component vector [Ixx, Iyy, Izz]
                    try:
                        if len(inertia) != 3:
                            if obj not in combined_issues:
                                combined_issues[obj] = []
                            combined_issues[obj].append(
                                f"Object '{obj.name}' has invalid physics_inertia: expected 3 values, got {len(inertia)}, \n recommend re-assigning physics properties to the material"
                            )
                            objects_in_question.add(obj)
                        else:
                            # Check each diagonal component is positive
                            invalid_components = []
                            for i, value in enumerate(inertia):
                                if value <= 0:
                                    invalid_components.append(f"I{'xyz'[i]}{chr(ord('x')+i)}={value:.6f}")

                            if invalid_components:
                                if obj not in combined_issues:
                                    combined_issues[obj] = []
                                combined_issues[obj].append(
                                    f"Object '{obj.name}' has invalid physics_inertia values (must be > 0): {', '.join(invalid_components)}, \n recommend re-assigning physics properties to the material"
                                )
                                objects_in_question.add(obj)
                    except (TypeError, ValueError) as e:
                        if obj not in combined_issues:
                            combined_issues[obj] = []
                        combined_issues[obj].append(
                            f"Object '{obj.name}' has malformed physics_inertia: {e}, \n recommend re-assigning physics properties to the material"
                        )
                        objects_in_question.add(obj)

                # Validate principal axes format (should be 4-component quaternion [w, x, y, z])
                principal_axes = obj.get("pxr:physics:principalAxes")
                if principal_axes is not None:
                    try:
                        if len(principal_axes) != 4:
                            if obj not in combined_issues:
                                combined_issues[obj] = []
                            combined_issues[obj].append(
                                f"Object '{obj.name}' has invalid physics:principalAxes: expected 4 values (quaternion), got {len(principal_axes)}, \n recommend re-assigning physics properties to the material"
                            )
                            objects_in_question.add(obj)
                    except (TypeError, ValueError) as e:
                        if obj not in combined_issues:
                            combined_issues[obj] = []
                        combined_issues[obj].append(
                            f"Object '{obj.name}' has malformed physics:principalAxes: {e}, \n recommend re-assigning physics properties to the material"
                        )
                        objects_in_question.add(obj)

        # Create issues list
        for obj, issue_msgs in combined_issues.items():
            if issue_msgs:
                combined_msg = "\n".join(issue_msgs)
                issues.append((obj, combined_msg))

        instance.data["physics_property_issues"] = list(objects_in_question)
        self.problematic_assets = issues

        self.log.info(f"Found {len(objects_in_question)} objects with physics property issues")

        self.warnings = []

        if issues:
            error_messages = [msg for _, msg in issues]
            error_message = "\n".join(error_messages) if len(error_messages) > 1 else error_messages[0]
            raise ValueError(error_message)


class Validate_Semantic_Labels(InstancePlugin):
    """Validate that objects have required Wikidata semantic labels"""

    label = "Validate Semantic Labels"

    families = ["mesh"]
    asset_types = ["all"]

    def process(self, instance):
        issues = []
        warnings_list = []
        combined_warnings = {}
        objects_in_question = set()

        # Check global metadata (for defaultPrim/root level)
        scene = bpy.context.scene
        global_metadata = getattr(scene, "global_metadata", None)
        has_valid_global_metadata = False

        if global_metadata:
            # Check if global wikidata metadata is set
            has_query = bool(getattr(global_metadata, "wikidata_query", None))
            has_result_id = bool(getattr(global_metadata, "wikidata_result_id", None))
            has_result_label = bool(getattr(global_metadata, "wikidata_result_label", None))

            # Consider global metadata valid if result_id and label are both set
            has_valid_global_metadata = has_result_id and has_result_label

            print(
                f"Global metadata check - has_query: {has_query}, has_result_id: {has_result_id}, has_result_label: {has_result_label}, has_valid: {has_valid_global_metadata}"
            )

            if has_query and not has_result_id:
                issues.append(
                    "Global metadata has a wikidata query but no result ID stored. "
                    "Please use 'Store for Root Level' button in SimReady Metadata panel."
                )
            elif has_result_id and not has_result_label:
                issues.append(
                    "Global metadata has incomplete wikidata information (missing label). "
                    "Please re-store the metadata in SimReady Metadata panel."
                )
        else:
            print("No global_metadata property group found on scene")

        # If valid global metadata exists, skip mesh-level checks
        # Only check mesh-level if global metadata is not set
        if has_valid_global_metadata:
            # Global metadata is properly set, no need to check individual objects
            print("Valid global metadata found, skipping mesh-level checks")
            pass
        else:
            # No valid global metadata, so we need to check mesh-level semantic labels
            print("No valid global metadata, checking mesh-level semantic labels")
            objects_with_semantic_labels = set()  # Track objects that have complete semantic labels

            for obj in bpy.context.view_layer.objects:
                if obj.type != "MESH":
                    continue

                # Skip objects that don't exist in a collection called "Geometry"
                if not check_if_in_geometry_collection(obj):
                    continue

                if obj not in combined_warnings:
                    combined_warnings[obj] = []

                # Check for semantic properties on object
                wikidata_class = obj.get("semantic:wikidata_class:params:semanticData")
                wikidata_qcode = obj.get("semantic:wikidata_qcode:params:semanticData")

                print(f"Object '{obj.name}' - wikidata_class: {wikidata_class}, wikidata_qcode: {wikidata_qcode}")

                # Check for partial semantic labels (one set but not the other)
                if (wikidata_class and not wikidata_qcode) or (not wikidata_class and wikidata_qcode):
                    combined_warnings[obj].append(
                        f"Object '{obj.name}' has incomplete semantic labels (both class and qcode required)"
                    )
                    objects_in_question.add(obj)
                # If both are set, mark as having semantic labels
                elif wikidata_class and wikidata_qcode:
                    objects_with_semantic_labels.add(obj)

                # Also check mesh data
                if obj.data:
                    mesh_class = obj.data.get("semantic:wikidata_class:params:semanticData")
                    mesh_qcode = obj.data.get("semantic:wikidata_qcode:params:semanticData")

                    print(f"Mesh '{obj.data.name}' - mesh_class: {mesh_class}, mesh_qcode: {mesh_qcode}")

                    if (mesh_class and not mesh_qcode) or (not mesh_class and mesh_qcode):
                        combined_warnings[obj].append(
                            f"Mesh '{obj.data.name}' has incomplete semantic labels (both class and qcode required)"
                        )
                        objects_in_question.add(obj)
                    # If both are set on mesh, mark as having semantic labels
                    elif mesh_class and mesh_qcode:
                        objects_with_semantic_labels.add(obj)

                    # Warn if object and mesh labels don't match
                    if wikidata_class and mesh_class and wikidata_class != mesh_class:
                        combined_warnings[obj].append(
                            f"Object and mesh have different semantic labels (object: '{wikidata_class}', mesh: '{mesh_class}')"
                        )
                        objects_in_question.add(obj)

            # Only add error if no mesh-level semantic labels found at all
            if not objects_with_semantic_labels:
                issues.append(
                    "No semantic labels found. Either set global metadata in SimReady Metadata panel "
                    "or add semantic labels to individual mesh objects."
                )

            print(f"Found {len(objects_with_semantic_labels)} objects with complete semantic labels")

        # Create warnings list
        for obj, warning_msgs in combined_warnings.items():
            if warning_msgs:
                combined_msg = "\n".join(warning_msgs)
                warnings_list.append((obj, combined_msg))

        instance.data["semantic_label_issues"] = list(objects_in_question)
        self.problematic_assets = warnings_list

        print(f"Found {len(objects_in_question)} objects with semantic label issues")

        if warnings_list:
            self.warnings = warnings_list
        if issues:
            raise ValueError("\n".join(issues))


# TODO: need a check to ensure we are using orm, not roughness/metalness maps
# class Validate_Use_Orm(InstancePlugin):
#     label = "Validate Use Orm"
#
#     families = ["mesh"]
#     asset_types = ["all"]

#     def process(self, instance):
#         material_issues = {}
#         mats_to_delete = set()
#         combined_issues = {}

#         for obj in instance:
#             if obj.type != 'MESH':
#                 continue

#             for i, slot in enumerate(obj.material_slots):
#                 mat = slot.material
#                 if mat.use_nodes and mat.node_tree:
