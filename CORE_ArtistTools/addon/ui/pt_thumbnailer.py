# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""
Thumbnail / turntable workflow.

Compositor order: loading the rig may append compositor nodes from the template blend;
thumbnail rendering temporarily disables scene compositor nodes (use_nodes) for a clean
still; after rig load the addon may turn compositor use off on the scene until the user
needs it again.
"""

import math
import os
import re
import shutil
import time
from pathlib import Path
from typing import Optional

import addon_utils
import bpy
import mathutils
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, StringProperty
from PIL import Image

from .thumbnailer_constants import (
    ADDON_SIMREADY_CORE_NAME,
    COL_EXPORT,
    COL_GEOMETRY,
    COL_LIGHT_LINKING_EXPORT,
    COL_SHADOW_LINKING_EXPORT,
    COL_THUMBNAIL,
    DCC_SOURCE_DIR,
    LIGHT_FILL,
    LIGHT_KEY,
    LIGHT_RIM,
    LIGHT_SHADOW,
    OBJ_GROUND_PLANE,
    OBJ_THUMBNAIL_CAMERA,
    OBJ_THUMBNAIL_TARGET,
    PRESET_OUTDOOR,
    PRESET_STUDIO,
    REL_SIMREADY_THUMBS,
    REL_TEMPLATE_ENVIRONMENTS,
    RIG_OUTDOOR_BLEND,
    RIG_STUDIO_BLEND,
)


def resolve_asset_root_from_blend_dir(blend_dir: str) -> str:
    """Walk parents for ``dcc_source``; otherwise use three-level dirname fallback."""
    root_candidate = blend_dir
    asset_root: Optional[str] = None
    for _ in range(6):
        if os.path.basename(root_candidate).lower() == DCC_SOURCE_DIR.lower():
            asset_root = os.path.dirname(root_candidate)
            break
        parent = os.path.dirname(root_candidate)
        if parent == root_candidate:
            break
        root_candidate = parent
    if asset_root is None:
        asset_root = os.path.dirname(os.path.dirname(os.path.dirname(blend_dir)))
    return asset_root


def has_export_in_collection() -> bool:
    """check if a valid asset is loaded"""
    export_lower = COL_EXPORT.lower()
    for col in bpy.data.collections:
        if col.name.lower() == export_lower:
            return True
    return False


def set_view3d_to_camera_view(context) -> bool:
    """Switch a 3D Viewport to look through the active scene camera (Numpad 0). Returns True if applied."""
    try:
        area = context.area
        if area and area.type == "VIEW_3D":
            for region in area.regions:
                if region.type == "WINDOW":
                    space = area.spaces[0] if area.spaces else None
                    if space is not None and getattr(space, "type", None) == "VIEW_3D":
                        with context.temp_override(
                            window=context.window,
                            screen=context.screen,
                            area=area,
                            region=region,
                            space_data=space,
                            scene=context.scene,
                            view_layer=context.view_layer,
                        ):
                            bpy.ops.view3d.view_camera()
                        return True
    except Exception as e:
        print(f"[Thumbnailer] set_view3d_to_camera_view (context area): {e}")
    try:
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type != "VIEW_3D":
                    continue
                for region in area.regions:
                    if region.type != "WINDOW":
                        continue
                    space = area.spaces[0] if area.spaces else None
                    if space is None or getattr(space, "type", None) != "VIEW_3D":
                        continue
                    try:
                        with context.temp_override(
                            window=window,
                            screen=window.screen,
                            area=area,
                            region=region,
                            space_data=space,
                            scene=context.scene,
                            view_layer=context.view_layer,
                        ):
                            bpy.ops.view3d.view_camera()
                        return True
                    except Exception as e2:
                        print(f"[Thumbnailer] set_view3d_to_camera_view: {e2}")
    except Exception as e:
        print(f"[Thumbnailer] set_view3d_to_camera_view: {e}")
    return False


def preferred_cycles_device() -> str:
    """Return ``GPU`` if any non-CPU Cycles device is enabled, else ``CPU``."""
    try:
        addon_prefs = bpy.context.preferences.addons.get("cycles")
        if addon_prefs is None:
            return "CPU"
        cprefs = addon_prefs.preferences
        try:
            cprefs.get_devices()
        except Exception:
            pass
        for dev in getattr(cprefs, "devices", []) or []:
            try:
                if getattr(dev, "type", "CPU") != "CPU" and getattr(dev, "use", False):
                    return "GPU"
            except Exception:
                continue
        return "CPU"
    except Exception:
        return "CPU"


def set_render_settings(
    image_path,
    format,
    x_res,
    y_res,
    percent_res,
    render_engine,
    render_device,
    render_samples,
    denoise,
) -> None:
    """Set camera and render values for thumbnails and turntables.

    Pass ``render_device=None`` to pick GPU when available, otherwise CPU.
    """
    if render_device is None:
        render_device = preferred_cycles_device()
    bpy.context.scene.render.filepath = image_path
    bpy.context.scene.render.image_settings.file_format = format
    bpy.context.scene.render.resolution_x = x_res
    bpy.context.scene.render.resolution_y = y_res
    bpy.context.scene.render.resolution_percentage = percent_res

    scene = bpy.context.scene
    scene.render.engine = render_engine
    scene.cycles.device = render_device
    scene.cycles.samples = render_samples
    scene.cycles.use_denoising = denoise


#
# Removed old renderer UI enums and lists; rendering is configured explicitly in operators
#

LIGHTING_PRESET_ITEMS = [
    (PRESET_STUDIO, "Studio Lighting", ""),
    (PRESET_OUTDOOR, "Outdoor Lighting", ""),
]


#
# Removed old PropertyGroups for renderer UI: RenderResProps, RenderingTypeProps, RenderingSamplesProps
#


class ProgressBarProps(bpy.types.PropertyGroup):
    progress: FloatProperty(name="Progress", default=0.0, min=0.0, max=1.0)


class CameraSettingsProps(bpy.types.PropertyGroup):
    """Camera settings exposed in the panel"""

    def _update_camera_type(self, context):
        try:
            cam_obj = bpy.data.objects.get(OBJ_THUMBNAIL_CAMERA) or context.scene.camera
        except Exception:
            cam_obj = context.scene.camera
        try:
            if cam_obj and getattr(cam_obj, "type", "") == "CAMERA" and getattr(cam_obj, "data", None):
                if self.camera_type == "PERSP":
                    cam_obj.data.type = "PERSP"
                elif self.camera_type == "ORTHO":
                    cam_obj.data.type = "ORTHO"
        except Exception:
            pass

    camera_type: EnumProperty(
        name="Type",
        description="Camera projection type",
        items=[("PERSP", "Perspective Camera", ""), ("ORTHO", "Orthographic Camera", "")],
        default="PERSP",
        update=_update_camera_type,
    )


class CameraTargetProps(bpy.types.PropertyGroup):
    """Controls for moving the Thumbnail_Target prim"""

    def _update_x(self, context):
        try:
            tgt = bpy.data.objects.get(OBJ_THUMBNAIL_TARGET)
            if tgt:
                tgt.location.x = float(self.target_x)
        except Exception:
            pass

    def _update_y(self, context):
        try:
            tgt = bpy.data.objects.get(OBJ_THUMBNAIL_TARGET)
            if tgt:
                tgt.location.y = float(self.target_y)
        except Exception:
            pass

    def _update_z(self, context):
        try:
            tgt = bpy.data.objects.get(OBJ_THUMBNAIL_TARGET)
            if tgt:
                tgt.location.z = float(self.target_z)
        except Exception:
            pass

    target_x: FloatProperty(name="X", default=0.0, update=_update_x)
    target_y: FloatProperty(name="Y", default=0.0, update=_update_y)
    target_z: FloatProperty(name="Z", default=0.0, update=_update_z)


class AssetVariantProps(bpy.types.PropertyGroup):
    """Property group for asset variant number"""

    def validate_variant(self, context):
        """Ensure variant number is always 2 digits"""
        variant = self.variant_number
        if variant and variant.isdigit():
            if len(variant) == 1:
                # Pad with leading zero
                self.variant_number = f"0{variant}"
            elif len(variant) > 2:
                # Truncate to 2 digits
                self.variant_number = variant[:2]
        elif not variant.isdigit():
            # Reset to default if invalid
            self.variant_number = "01"

    variant_number: StringProperty(
        name="Asset Variant",
        description="2-digit variant number for the asset (e.g., 01, 02, 10)",
        default="01",
        maxlen=2,
        update=validate_variant,
    )


def orbit_light_around_target(light_name: str, angle_radians: float) -> None:
    """Reposition a light around Thumbnail_Target on XY plane by angle, keeping radius and height."""
    try:
        light_obj = bpy.data.objects.get(light_name)
        target_obj = bpy.data.objects.get(OBJ_THUMBNAIL_TARGET)
        if light_obj is None or target_obj is None:
            return

        target_loc = target_obj.location.copy()
        vec = light_obj.location - target_loc
        radius_xy = math.hypot(vec.x, vec.y)
        z_offset = vec.z

        if radius_xy == 0.0:
            radius_xy = 1.0

        new_x = math.cos(angle_radians) * radius_xy
        new_y = math.sin(angle_radians) * radius_xy
        light_obj.location = (target_loc.x + new_x, target_loc.y + new_y, target_loc.z + z_offset)
    except Exception:
        pass


def get_light_xy_angle(light_name: str):
    """Get the XY-plane angle (radians) of a light around Thumbnail_Target."""
    try:
        light_obj = bpy.data.objects.get(light_name)
        target_obj = bpy.data.objects.get(OBJ_THUMBNAIL_TARGET)
        if light_obj is None or target_obj is None:
            return None
        vec = light_obj.location - target_obj.location
        return math.atan2(vec.y, vec.x)  # returns in [-pi, pi]
    except Exception:
        return None


def get_light_power(light_name: str):
    """Get the light energy (power) in Blender units (Watts for most light types)."""
    try:
        light_obj = bpy.data.objects.get(light_name)
        if light_obj is None or light_obj.type != "LIGHT":
            return None
        light_data = light_obj.data
        return getattr(light_data, "energy", None)
    except Exception:
        return None


def get_light_z(light_name: str):
    """Get the world-space Z location of a light."""
    try:
        light_obj = bpy.data.objects.get(light_name)
        if light_obj is None:
            return None
        return float(light_obj.location.z)
    except Exception:
        return None


def get_light_scale(light_name: str):
    """Get a representative uniform scale for a light object (uses X component)."""
    try:
        light_obj = bpy.data.objects.get(light_name)
        if light_obj is None:
            return None
        # Assume uniform scale in rig; use X as canonical
        return float(light_obj.scale.x)
    except Exception:
        return None


def get_light_scale_vec(light_name: str):
    """Get the full XYZ scale vector for a light object."""
    try:
        light_obj = bpy.data.objects.get(light_name)
        if light_obj is None:
            return None
        s = light_obj.scale
        return (float(s.x), float(s.y), float(s.z))
    except Exception:
        return None


class LightingOrientationProps(bpy.types.PropertyGroup):
    """Angles to orbit lighting around the subject"""

    def _update_key(self, context):
        orbit_light_around_target(LIGHT_KEY, self.key_angle)

    def _update_fill(self, context):
        orbit_light_around_target(LIGHT_FILL, self.fill_angle)

    def _update_rim(self, context):
        orbit_light_around_target(LIGHT_RIM, self.rim_angle)

    def _update_shadow(self, context):
        orbit_light_around_target(LIGHT_SHADOW, self.shadow_angle)

    def _update_key_power(self, context):
        try:
            light_obj = bpy.data.objects.get(LIGHT_KEY)
            if light_obj and light_obj.type == "LIGHT":
                light_obj.data.energy = max(0.0, self.key_power)
        except Exception:
            pass

    def _update_fill_power(self, context):
        try:
            light_obj = bpy.data.objects.get(LIGHT_FILL)
            if light_obj and light_obj.type == "LIGHT":
                light_obj.data.energy = max(0.0, self.fill_power)
        except Exception:
            pass

    def _update_rim_power(self, context):
        try:
            light_obj = bpy.data.objects.get(LIGHT_RIM)
            if light_obj and light_obj.type == "LIGHT":
                light_obj.data.energy = max(0.0, self.rim_power)
        except Exception:
            pass

    def _update_shadow_power(self, context):
        try:
            light_obj = bpy.data.objects.get(LIGHT_SHADOW)
            if light_obj and light_obj.type == "LIGHT":
                light_obj.data.energy = max(0.0, self.shadow_power)
        except Exception:
            pass

    key_angle: FloatProperty(
        name="Key", subtype="ANGLE", default=0.0, min=-6.283185307179586, max=6.283185307179586, update=_update_key
    )
    fill_angle: FloatProperty(
        name="Fill", subtype="ANGLE", default=0.0, min=-6.283185307179586, max=6.283185307179586, update=_update_fill
    )
    rim_angle: FloatProperty(
        name="Rim", subtype="ANGLE", default=0.0, min=-6.283185307179586, max=6.283185307179586, update=_update_rim
    )
    shadow_angle: FloatProperty(
        name="Shadow",
        subtype="ANGLE",
        default=0.0,
        min=-6.283185307179586,
        max=6.283185307179586,
        update=_update_shadow,
    )

    key_power: FloatProperty(
        name="Power", subtype="POWER", default=100.0, min=0.0, max=100000.0, update=_update_key_power
    )
    fill_power: FloatProperty(
        name="Power", subtype="POWER", default=50.0, min=0.0, max=100000.0, update=_update_fill_power
    )
    rim_power: FloatProperty(
        name="Power", subtype="POWER", default=25.0, min=0.0, max=100000.0, update=_update_rim_power
    )
    shadow_power: FloatProperty(
        name="Power", subtype="POWER", default=25.0, min=0.0, max=100000.0, update=_update_shadow_power
    )

    # Altitude (Z) offsets relative to baseline captured on rig load
    def _update_key_altitude(self, context):
        try:
            light_obj = bpy.data.objects.get(LIGHT_KEY)
            if light_obj:
                light_obj.location.z = self.baseline_key_z + self.key_altitude
        except Exception:
            pass

    def _update_fill_altitude(self, context):
        try:
            light_obj = bpy.data.objects.get(LIGHT_FILL)
            if light_obj:
                light_obj.location.z = self.baseline_fill_z + self.fill_altitude
        except Exception:
            pass

    def _update_rim_altitude(self, context):
        try:
            light_obj = bpy.data.objects.get(LIGHT_RIM)
            if light_obj:
                light_obj.location.z = self.baseline_rim_z + self.rim_altitude
        except Exception:
            pass

    def _update_shadow_altitude(self, context):
        try:
            light_obj = bpy.data.objects.get(LIGHT_SHADOW)
            if light_obj:
                light_obj.location.z = self.baseline_shadow_z + self.shadow_altitude
        except Exception:
            pass

    key_altitude: FloatProperty(name="Altitude", default=0.0, update=_update_key_altitude)
    fill_altitude: FloatProperty(name="Altitude", default=0.0, update=_update_fill_altitude)
    rim_altitude: FloatProperty(name="Altitude", default=0.0, update=_update_rim_altitude)
    shadow_altitude: FloatProperty(name="Altitude", default=0.0, update=_update_shadow_altitude)

    # Hidden baselines for Z positions
    baseline_key_z: FloatProperty(name="Baseline Key Z", default=0.0, options={"HIDDEN"})
    baseline_fill_z: FloatProperty(name="Baseline Fill Z", default=0.0, options={"HIDDEN"})
    baseline_rim_z: FloatProperty(name="Baseline Rim Z", default=0.0, options={"HIDDEN"})
    baseline_shadow_z: FloatProperty(name="Baseline Shadow Z", default=0.0, options={"HIDDEN"})

    # Scale controls (absolute, uniform)
    def _update_key_scale(self, context):
        try:
            light_obj = bpy.data.objects.get(LIGHT_KEY)
            if light_obj:
                m = max(0.01, min(10.0, float(self.key_scale)))
                bx, by, bz = self.baseline_key_scale_vec
                light_obj.scale = (bx * m, by * m, bz * m)
        except Exception:
            pass

    def _update_fill_scale(self, context):
        try:
            light_obj = bpy.data.objects.get(LIGHT_FILL)
            if light_obj:
                m = max(0.01, min(10.0, float(self.fill_scale)))
                bx, by, bz = self.baseline_fill_scale_vec
                light_obj.scale = (bx * m, by * m, bz * m)
        except Exception:
            pass

    def _update_rim_scale(self, context):
        try:
            light_obj = bpy.data.objects.get(LIGHT_RIM)
            if light_obj:
                m = max(0.01, min(10.0, float(self.rim_scale)))
                bx, by, bz = self.baseline_rim_scale_vec
                light_obj.scale = (bx * m, by * m, bz * m)
        except Exception:
            pass

    def _update_shadow_scale(self, context):
        try:
            light_obj = bpy.data.objects.get(LIGHT_SHADOW)
            if light_obj:
                m = max(0.01, min(10.0, float(self.shadow_scale)))
                bx, by, bz = self.baseline_shadow_scale_vec
                light_obj.scale = (bx * m, by * m, bz * m)
        except Exception:
            pass

    key_scale: FloatProperty(name="Scale", default=1.0, min=0.01, max=10.0, update=_update_key_scale)
    fill_scale: FloatProperty(name="Scale", default=1.0, min=0.01, max=10.0, update=_update_fill_scale)
    rim_scale: FloatProperty(name="Scale", default=1.0, min=0.01, max=10.0, update=_update_rim_scale)
    # Baseline scale vectors captured on rig load
    baseline_key_scale_vec: FloatVectorProperty(
        name="Baseline Key Scale", size=3, default=(1.0, 1.0, 1.0), options={"HIDDEN"}
    )
    baseline_fill_scale_vec: FloatVectorProperty(
        name="Baseline Fill Scale", size=3, default=(1.0, 1.0, 1.0), options={"HIDDEN"}
    )
    baseline_rim_scale_vec: FloatVectorProperty(
        name="Baseline Rim Scale", size=3, default=(1.0, 1.0, 1.0), options={"HIDDEN"}
    )
    shadow_scale: FloatProperty(name="Scale", default=1.0, min=0.01, max=10.0, update=_update_shadow_scale)
    baseline_shadow_scale_vec: FloatVectorProperty(
        name="Baseline Shadow Scale", size=3, default=(1.0, 1.0, 1.0), options={"HIDDEN"}
    )


def apply_variant_to_filename(filename: str, variant_number: str) -> str:
    """
    Apply variant number to filename, replacing existing variant suffix if present.

    Looks for a pattern of _XX at the end of the filename (where XX is 2 digits)
    and replaces it with the new variant number. If no variant suffix exists,
    appends the variant number.

    Examples:
        "sm_asset_01" + "02" -> "sm_asset_02"
        "sm_asset_v01_05" + "03" -> "sm_asset_v01_03"
        "sm_asset" + "01" -> "sm_asset_01"

    Args:
        filename: The base filename without extension
        variant_number: The 2-digit variant number to apply

    Returns:
        Filename with variant number applied
    """
    # Ensure variant is 2 digits
    if len(variant_number) == 1:
        variant_number = f"0{variant_number}"
    elif len(variant_number) != 2 or not variant_number.isdigit():
        variant_number = "01"  # Fallback to default

    # Pattern to match _XX at the end where XX is exactly 2 digits
    pattern = r"_(\d{2})$"

    match = re.search(pattern, filename)

    if match:
        # Found existing variant suffix - replace it
        existing_variant = match.group(1)
        if existing_variant != variant_number:
            # Replace the existing variant with the new one
            return re.sub(pattern, f"_{variant_number}", filename)
        else:
            # Same variant, no change needed
            return filename
    else:
        # No variant suffix found - append it
        return f"{filename}_{variant_number}"


def find_collection_child_for_target(parent_coll, target_coll):
    """Return ``CollectionChild`` under ``parent_coll`` whose linked collection is ``target_coll``.

    Prefer ``collection_children[].collection`` identity/name match. On Blender 5.x, linking via
    ``Collection.children.link`` can leave a parallel ``collection_children`` row with
    ``collection`` unset while ``light_linking`` still applies to that row — fall back to the
    child index under ``parent_coll.children`` and optionally repair ``collection`` when writable.
    """
    if parent_coll is None or target_coll is None:
        return None
    target_name = getattr(target_coll, "name", None)
    for ch in getattr(parent_coll, "collection_children", []) or []:
        coll = getattr(ch, "collection", None)
        if coll == target_coll:
            return ch
        if target_name and coll is not None and coll.name == target_name:
            return ch

    # Fallback: align with Collection.children order (light-link rows mirror child list).
    try:
        kids = list(getattr(parent_coll, "children", []))
    except Exception:
        kids = []
    try:
        cc_list = list(getattr(parent_coll, "collection_children", []) or [])
    except Exception:
        cc_list = []

    def _kid_matches(c):
        if c is None:
            return False
        if c == target_coll:
            return True
        return bool(target_name) and getattr(c, "name", None) == target_name

    for i, c in enumerate(kids):
        if not _kid_matches(c):
            continue
        if i >= len(cc_list):
            break
        ch = cc_list[i]
        coll = getattr(ch, "collection", None)
        if coll is not None and coll != target_coll:
            if not (target_name and getattr(coll, "name", None) == target_name):
                continue
        if coll is None:
            try:
                ch.collection = target_coll
            except Exception:
                pass
        return ch

    # Single child / single collection_child (common receiver-only-Export case)
    if len(kids) == 1 and len(cc_list) == 1 and _kid_matches(kids[0]):
        ch = cc_list[0]
        if getattr(ch, "collection", None) is None:
            try:
                ch.collection = target_coll
            except Exception:
                pass
        return ch

    return None


def _receiver_collection_for_shadow_light():
    """Prefer ``Light_Shadow.light_linking.receiver_collection``, then named collection."""
    lo = bpy.data.objects.get(LIGHT_SHADOW)
    if lo is not None:
        oll = getattr(lo, "light_linking", None)
        if oll is not None:
            r = getattr(oll, "receiver_collection", None)
            if r is not None:
                return r
    return bpy.data.collections.get(COL_LIGHT_LINKING_EXPORT)


def apply_export_light_linking_exclude() -> bool:
    """Set EXCLUDE light-link state on Export under the shadow light's receiver collection."""
    try:
        if hasattr(bpy.context, "view_layer") and bpy.context.view_layer is not None:
            bpy.context.view_layer.update()
    except Exception:
        pass

    recv = _receiver_collection_for_shadow_light()
    if recv is None:
        print(
            f"[Thumbnailer] Receiver collection not found (light {LIGHT_SHADOW} / "
            f"{COL_LIGHT_LINKING_EXPORT}); skip light-link EXCLUDE"
        )
        return False
    exp = bpy.data.collections.get(COL_EXPORT)
    if exp is None:
        print("[Thumbnailer] Export collection not found; skip light-link EXCLUDE")
        return False

    ch = find_collection_child_for_target(recv, exp)
    if ch is None:
        try:
            kid_names = [getattr(c, "name", "?") for c in getattr(recv, "children", []) or []]
        except Exception:
            kid_names = []
        try:
            cc_names = [
                getattr(getattr(c, "collection", None), "name", "?")
                for c in getattr(recv, "collection_children", []) or []
            ]
        except Exception:
            cc_names = []
        print(
            f"[Thumbnailer] {COL_EXPORT} not resolved under receiver "
            f"(receiver.children: {kid_names!r}, collection_children[].collection: {cc_names!r}); "
            f"skip EXCLUDE this pass"
        )
        return False
    ll = getattr(ch, "light_linking", None)
    if ll is None:
        print("[Thumbnailer] CollectionChild has no light_linking; skip EXCLUDE")
        return False
    try:
        ll.link_state = "EXCLUDE"
        return True
    except Exception as e:
        print(f"[Thumbnailer] Could not set light link EXCLUDE: {e}")
        return False


# One-shot timer retries EXCLUDE after depsgraph settles (see schedule_light_exclude_retry_timer).
_thumb_light_exclude_timer_ref = [None]


def schedule_light_exclude_retry_timer() -> None:
    """Retry ``apply_export_light_linking_exclude`` until success or attempts exhausted."""
    old = _thumb_light_exclude_timer_ref[0]
    if old is not None:
        try:
            bpy.app.timers.unregister(old)
        except Exception:
            pass
        _thumb_light_exclude_timer_ref[0] = None

    remaining = [18]  # ~18 * 0.08s + initial delay

    def _tick():
        if not getattr(bpy.context, "view_layer", None):
            _thumb_light_exclude_timer_ref[0] = None
            return None
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass
        if apply_export_light_linking_exclude():
            print("[Thumbnailer] Light-link EXCLUDE succeeded (deferred retry)")
            light_ok, shadow_ok, lines = validate_shadow_light_linking_state(LIGHT_SHADOW)
            for ln in lines:
                print(f"[Thumbnailer] {ln}")
            _thumb_light_exclude_timer_ref[0] = None
            return None
        remaining[0] -= 1
        if remaining[0] <= 0:
            print("[Thumbnailer] Light-link EXCLUDE: deferred retries exhausted")
            light_ok, shadow_ok, lines = validate_shadow_light_linking_state(LIGHT_SHADOW)
            for ln in lines:
                print(f"[Thumbnailer] {ln}")
            _thumb_light_exclude_timer_ref[0] = None
            return None
        return 0.08

    _thumb_light_exclude_timer_ref[0] = _tick
    bpy.app.timers.register(_tick, first_interval=0.06)


def cancel_light_exclude_retry_timer() -> None:
    """Stop deferred light-link EXCLUDE retries (e.g. on add-on disable)."""
    old = _thumb_light_exclude_timer_ref[0]
    if old is not None:
        try:
            bpy.app.timers.unregister(old)
        except Exception:
            pass
        _thumb_light_exclude_timer_ref[0] = None


def validate_shadow_light_linking_state(light_name: str = LIGHT_SHADOW):
    """
    Confirm shadow light setup: Export excluded from illumination (receiver), Export in shadow blocker.

    Returns:
        (light_exclude_ok, shadow_link_ok, message_lines)
    """
    lines = []
    light_ok = False
    shadow_ok = False
    lo = bpy.data.objects.get(light_name)
    if not lo or getattr(lo, "type", None) != "LIGHT":
        lines.append(f"Object {light_name!r} missing or not a light")
        return light_ok, shadow_ok, lines
    oll = getattr(lo, "light_linking", None)
    if oll is None:
        lines.append("Object.light_linking not available (Blender version?)")
        return light_ok, shadow_ok, lines
    exp = bpy.data.collections.get(COL_EXPORT)

    recv = _receiver_collection_for_shadow_light()
    if recv is None:
        lines.append("Light receiver collection not resolved")
    elif exp is None:
        lines.append(f"{COL_EXPORT} collection not found (light linking check skipped)")
    else:
        ch = find_collection_child_for_target(recv, exp)
        if ch is None:
            try:
                kid_names = [getattr(c, "name", "?") for c in getattr(recv, "children", []) or []]
            except Exception:
                kid_names = []
            lines.append(
                f"Light linking: {COL_EXPORT} not under receiver "
                f"(children: {kid_names!r}; expected under {COL_LIGHT_LINKING_EXPORT})"
            )
        else:
            st = getattr(ch.light_linking, "link_state", None)
            if st == "EXCLUDE":
                light_ok = True
                lines.append(f"Light linking: {COL_EXPORT} is EXCLUDE (shadow light will not illuminate Export)")
            else:
                lines.append(f"Light linking: {COL_EXPORT} link_state is {st!r} (expected EXCLUDE)")

    blk = bpy.data.collections.get(COL_SHADOW_LINKING_EXPORT)
    if blk is None:
        blk = getattr(oll, "blocker_collection", None)
    if blk is None:
        lines.append("Shadow blocker collection not resolved")
    elif exp is None:
        pass
    else:
        child_names = [c.name for c in getattr(blk, "children", [])]
        if exp.name in child_names:
            shadow_ok = True
            lines.append(f"Shadow linking: {COL_EXPORT} is linked under {COL_SHADOW_LINKING_EXPORT}")
        else:
            lines.append(
                f"Shadow linking: {COL_EXPORT} not under {COL_SHADOW_LINKING_EXPORT} " f"(children: {child_names})"
            )

    return light_ok, shadow_ok, lines


class ASSET_panel_common:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    bl_options = {"DEFAULT_CLOSED"}


class CORE_OT_Load_Lighting_Rig(bpy.types.Operator):
    """Load the template lighting rig and environment"""

    bl_idname = "core.load_lighting_rig"
    bl_label = "LOAD LIGHTING RIG"
    bl_description = (
        "Loads the lights, camera, and background for thumbnail and turntable rendering. "
        "May import compositor nodes from the template; the addon typically turns scene "
        "compositing off afterward until you enable it again."
    )

    def load_world_from_rig(self, rig_path) -> bool:
        """Append the first World datablock from the rig .blend and set it on the active scene."""
        if not os.path.exists(rig_path):
            return False
        # Discover available worlds in the library
        with bpy.data.libraries.load(rig_path, link=False) as (data_from, data_to):
            if not getattr(data_from, "worlds", None) or len(data_from.worlds) == 0:
                return False
            world_name_to_load = data_from.worlds[0]
        # Track existing world names to detect the newly appended one
        existing_names = {w.name for w in bpy.data.worlds}
        # Append the chosen world
        with bpy.data.libraries.load(rig_path, link=False) as (data_from, data_to):
            data_to.worlds = [world_name_to_load]
        # Find the newly appended world by name difference
        new_world = None
        for w in bpy.data.worlds:
            if w.name not in existing_names:
                new_world = w
                break
        if new_world is None:
            # Fallback: try by requested name
            new_world = bpy.data.worlds.get(world_name_to_load)
        if new_world is None:
            return False
        # Replace scene world and clean up old if unused
        old_world = bpy.context.scene.world
        bpy.context.scene.world = new_world
        try:
            if old_world and old_world != new_world and getattr(old_world, "users", 1) == 0:
                bpy.data.worlds.remove(old_world)
        except Exception:
            pass
        return True

    def _replicate_compositor_nodes(self, source_scene, dest_scene):
        """Copy compositing nodes and links from source_scene to dest_scene."""
        if source_scene is None or dest_scene is None:
            print("Warning: source or dest scene is None")
            return
        try:
            source_scene.use_nodes = True
        except Exception:
            pass
        try:
            dest_scene.use_nodes = True
        except Exception:
            pass
        if source_scene.node_tree is None or dest_scene.node_tree is None:
            print(
                f"Warning: node_tree is None (source: {source_scene.node_tree is not None}, dest: {dest_scene.node_tree is not None})"
            )
            return
        src_tree = source_scene.node_tree
        dst_tree = dest_scene.node_tree
        print(f"Replicating {len(src_tree.nodes)} nodes from {source_scene.name} to {dest_scene.name}")
        # Clear destination nodes
        for n in list(dst_tree.nodes):
            try:
                dst_tree.nodes.remove(n)
            except Exception:
                pass
        name_to_node = {}
        # Create nodes
        for n in src_tree.nodes:
            try:
                new_n = dst_tree.nodes.new(n.bl_idname)
            except Exception:
                # Fallback for unknown nodes
                continue
            new_n.name = n.name
            new_n.label = n.label
            try:
                new_n.location = n.location.copy()
            except Exception:
                pass
            try:
                new_n.width = n.width
                new_n.height = n.height
                new_n.hide = getattr(n, "hide", False)
            except Exception:
                pass
            # Try to copy node properties (generic)
            try:
                for prop in n.bl_rna.properties:
                    pid = prop.identifier
                    if prop.is_readonly or pid in {
                        "name",
                        "label",
                        "location",
                        "width",
                        "height",
                        "inputs",
                        "outputs",
                        "select",
                        "parent",
                        "bl_idname",
                        "type",
                        "rna_type",
                    }:
                        continue
                    try:
                        setattr(new_n, pid, getattr(n, pid))
                    except Exception:
                        pass
            except Exception:
                pass
            # Copy input default values when not linked
            for idx, inp in enumerate(n.inputs):
                if not inp.is_linked:
                    try:
                        new_inp = new_n.inputs[idx]
                        if hasattr(inp, "default_value") and hasattr(new_inp, "default_value"):
                            new_inp.default_value = inp.default_value
                    except Exception:
                        pass
            name_to_node[n.name] = new_n
        # Recreate links
        for l in src_tree.links:  # noqa E741
            try:
                from_n = name_to_node.get(l.from_node.name)
                to_n = name_to_node.get(l.to_node.name)
                if from_n is None or to_n is None:
                    continue
                # Prefer matching sockets by name; fallback to index if needed
                from_sock = None
                to_sock = None
                try:
                    for s in from_n.outputs:
                        if s.name == l.from_socket.name:
                            from_sock = s
                            break
                except Exception:
                    pass
                if from_sock is None:
                    try:
                        from_sock = from_n.outputs[l.from_socket.index]
                    except Exception:
                        from_sock = None
                try:
                    for s in to_n.inputs:
                        if s.name == l.to_socket.name:
                            to_sock = s
                            break
                except Exception:
                    pass
                if to_sock is None:
                    try:
                        to_sock = to_n.inputs[l.to_socket.index]
                    except Exception:
                        to_sock = None
                if from_sock is None or to_sock is None:
                    continue
                dst_tree.links.new(from_sock, to_sock)
            except Exception:
                pass
        # Ensure a valid Render Layers input driving Alpha Over image input (third input)
        try:
            alpha_node = None
            for n in dst_tree.nodes:
                if n.bl_idname == "CompositorNodeAlphaOver":
                    alpha_node = n
                    break
            if alpha_node is not None:
                # Remove existing links on third input if any
                try:
                    third_input = alpha_node.inputs[2]
                    if hasattr(third_input, "links"):
                        for link in list(third_input.links):
                            try:
                                dst_tree.links.remove(link)
                            except Exception:
                                pass
                except Exception:
                    pass
                # Create a new Render Layers node and wire its Image output
                try:
                    rl_node = dst_tree.nodes.new("CompositorNodeRLayers")
                    # Try to position it to the left of alpha node
                    try:
                        rl_node.location = (alpha_node.location.x - 300, alpha_node.location.y)
                    except Exception:
                        pass
                    # Set scene and layer if available
                    try:
                        rl_node.scene = bpy.context.scene
                    except Exception:
                        pass
                    try:
                        if hasattr(bpy.context, "view_layer") and hasattr(rl_node, "layer"):
                            rl_node.layer = bpy.context.view_layer.name
                    except Exception:
                        pass
                    # Link Image output to third input of Alpha Over
                    out_socket = None
                    try:
                        out_socket = rl_node.outputs.get("Image", None)
                    except Exception:
                        out_socket = None
                    if out_socket is None:
                        try:
                            out_socket = rl_node.outputs[0]
                        except Exception:
                            out_socket = None
                    if out_socket is not None:
                        dst_tree.links.new(out_socket, alpha_node.inputs[2])
                except Exception:
                    pass
                # Ensure Alpha Over output drives Composite and Viewer inputs
                try:
                    alpha_out = None
                    try:
                        alpha_out = alpha_node.outputs.get("Image", None)
                    except Exception:
                        alpha_out = None
                    if alpha_out is None:
                        try:
                            alpha_out = alpha_node.outputs[0]
                        except Exception:
                            alpha_out = None
                    if alpha_out is not None:
                        # Composite
                        composite_node = None
                        for n in dst_tree.nodes:
                            if n.bl_idname == "CompositorNodeComposite":
                                composite_node = n
                                break
                        if composite_node is None:
                            try:
                                composite_node = dst_tree.nodes.new("CompositorNodeComposite")
                                try:
                                    composite_node.location = (alpha_node.location.x + 300, alpha_node.location.y)
                                except Exception:
                                    pass
                            except Exception:
                                composite_node = None
                        if composite_node is not None:
                            try:
                                # Clear existing links on first input
                                comp_in = composite_node.inputs[0]
                                for link in list(comp_in.links):
                                    try:
                                        dst_tree.links.remove(link)
                                    except Exception:
                                        pass
                                dst_tree.links.new(alpha_out, comp_in)
                            except Exception:
                                pass
                        # Viewer
                        viewer_node = None
                        for n in dst_tree.nodes:
                            if n.bl_idname == "CompositorNodeViewer":
                                viewer_node = n
                                break
                        if viewer_node is None:
                            try:
                                viewer_node = dst_tree.nodes.new("CompositorNodeViewer")
                                try:
                                    viewer_node.location = (alpha_node.location.x + 300, alpha_node.location.y - 200)
                                except Exception:
                                    pass
                            except Exception:
                                viewer_node = None
                        if viewer_node is not None:
                            try:
                                view_in = viewer_node.inputs[0]
                                for link in list(view_in.links):
                                    try:
                                        dst_tree.links.remove(link)
                                    except Exception:
                                        pass
                                dst_tree.links.new(alpha_out, view_in)
                            except Exception:
                                pass
                except Exception:
                    pass
        except Exception:
            pass

    def load_compositor_from_rig(self, rig_path) -> bool:
        """Append one scene from rig .blend and replicate its compositor into current scene."""
        if not os.path.exists(rig_path):
            return False
        # Find a scene to import from the rig
        with bpy.data.libraries.load(rig_path, link=False) as (data_from, data_to):
            scene_names = getattr(data_from, "scenes", []) or []
            if not scene_names:
                return False
            src_scene_name = scene_names[0]
        # Track existing scenes to identify the appended one
        existing_scene_names = {s.name for s in bpy.data.scenes}
        with bpy.data.libraries.load(rig_path, link=False) as (data_from, data_to):
            data_to.scenes = [src_scene_name]
        appended_scene = None
        for s in bpy.data.scenes:
            if s.name not in existing_scene_names:
                appended_scene = s
                break
        if appended_scene is None:
            appended_scene = bpy.data.scenes.get(src_scene_name)
        if appended_scene is None:
            return False
        # Replicate nodes
        try:
            print(f"Attempting to replicate compositor from {appended_scene.name} to {bpy.context.scene.name}")
            # Ensure compositor is enabled on source scene before accessing node_tree
            try:
                appended_scene.use_nodes = True
            except Exception:
                pass
            # Check if node_tree exists and has nodes
            if (
                hasattr(appended_scene, "node_tree")
                and appended_scene.node_tree is not None
                and len(appended_scene.node_tree.nodes) > 0
            ):
                print(f"Source scene has {len(appended_scene.node_tree.nodes)} compositor nodes")
                self._replicate_compositor_nodes(appended_scene, bpy.context.scene)
                dest_nodes = (
                    bpy.context.scene.node_tree.nodes
                    if (hasattr(bpy.context.scene, "node_tree") and bpy.context.scene.node_tree)
                    else []
                )
                print(f"Compositor nodes replicated. Current scene now has {len(dest_nodes)} nodes")
            else:
                print(f"Warning: Source scene '{appended_scene.name}' has no compositor nodes to replicate")
        except Exception as e:
            print(f"Error replicating compositor nodes: {e}")
            import traceback

            traceback.print_exc()
        # Remove the appended scene to avoid clutter
        try:
            bpy.data.scenes.remove(appended_scene)
        except Exception:
            pass
        return True

    def load_lighting_rig(self, rig_path) -> bool:
        # Remove existing THUMBNAIL collection and its contents if present
        if COL_THUMBNAIL in bpy.data.collections:

            def remove_collection_recursive(coll):
                for child in list(coll.children):
                    remove_collection_recursive(child)
                for obj in list(coll.objects):
                    try:
                        bpy.data.objects.remove(obj, do_unlink=True)
                    except Exception:
                        pass
                try:
                    bpy.data.collections.remove(coll, do_unlink=True)
                except Exception:
                    pass

            existing = bpy.data.collections[COL_THUMBNAIL]
            # Unlink from scene if linked
            scene_collection = bpy.context.scene.collection
            if existing.name in scene_collection.children:
                try:
                    scene_collection.children.unlink(existing)
                except Exception:
                    pass
            remove_collection_recursive(existing)

        if os.path.exists(rig_path):  # make sure path is valid
            with bpy.data.libraries.load(rig_path, link=False) as (data_from, data_to):
                if COL_THUMBNAIL in data_from.collections:
                    data_to.collections = [COL_THUMBNAIL]
                else:
                    print(f"{COL_THUMBNAIL} collection not found in {rig_path}")
                    return False

            linked_collection = bpy.data.collections[COL_THUMBNAIL]
            scene_collection = bpy.context.scene.collection

            if linked_collection.name not in scene_collection.children:
                scene_collection.children.link(linked_collection)

            children = list(scene_collection.children)
            if children[0].name != linked_collection.name:
                scene_collection.children.unlink(linked_collection)
                scene_collection.children.link(linked_collection)
                for coll in children:
                    if coll != linked_collection:
                        scene_collection.children.unlink(coll)
                        scene_collection.children.link(coll)

            print(f"Linked {COL_THUMBNAIL} from {rig_path}")
            return True

        print(f"{rig_path} does not appear to be a valid path - check project_config.toml")
        return False

    def setup_blender_connections(self) -> bool:
        # Ensure a world is assigned to the scene and has an environment texture node
        scene = bpy.context.scene
        if scene.world is None:
            # Prefer an existing world if available, otherwise create a new one
            if bpy.data.worlds:
                scene.world = bpy.data.worlds[0]
            else:
                scene.world = bpy.data.worlds.new("World")
        world = scene.world
        world.use_nodes = True
        nodes = world.node_tree.nodes

        # Ensure an environment texture is available and linked to Background
        env_node = None
        for node in nodes:
            if node.type == "TEX_ENVIRONMENT":
                env_node = node
                break
        if not env_node:
            env_node = nodes.new("ShaderNodeTexEnvironment")
            background = nodes.get("Background")
            if background:
                world.node_tree.links.new(env_node.outputs[0], background.inputs[0])
        return True

    def frame_asset_offset(self) -> bool:
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.scene.camera = bpy.data.objects[OBJ_THUMBNAIL_CAMERA]

        collection = bpy.data.collections.get(COL_GEOMETRY)
        if not collection:
            raise RuntimeError(f"Collection '{COL_GEOMETRY}' not found")

        has_mesh = False
        for obj in collection.all_objects:
            if obj.type == "MESH":
                has_mesh = True
                break
        if not has_mesh:
            raise RuntimeError(f"No mesh objects found in '{COL_GEOMETRY}'")

        min_corner = mathutils.Vector((float("inf"), float("inf"), float("inf")))
        max_corner = mathutils.Vector((float("-inf"), float("-inf"), float("-inf")))
        for obj in collection.all_objects:
            if obj.type == "MESH":
                for corner in [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]:
                    min_corner = mathutils.Vector((min(min_corner[i], corner[i]) for i in range(3)))
                    max_corner = mathutils.Vector((max(max_corner[i], corner[i]) for i in range(3)))
        center = (min_corner + max_corner) / 2

        target_obj = bpy.data.objects[OBJ_THUMBNAIL_TARGET]
        tw = target_obj.matrix_world.copy()
        tw.translation = center
        target_obj.matrix_world = tw
        print(f"Moved Thumbnail_Target to world bounds centroid {tuple(center)}")
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass

        for obj in collection.all_objects:
            if obj.type == "MESH":
                obj.select_set(True)
        for obj in bpy.context.selected_objects:
            bpy.context.view_layer.objects.active = obj
            break
        bpy.ops.view3d.camera_to_view_selected()
        bpy.ops.object.select_all(action="DESELECT")

        # offset Ground Plane if asset below origin
        if min_corner[2] < 0:
            print("Asset appears below origin...")
            bpy.data.objects[OBJ_GROUND_PLANE].location = (0, 0, min_corner[2])
            print(f"Moved Ground Plane to {min_corner[2]} to match offset")
        else:
            print(f"Asset is above ground plane {min_corner[2]} - ok")

        # offset camera along z-axis by percentage
        cam = bpy.context.scene.camera
        cam_location = cam.location
        world_origin = mathutils.Vector((0.0, 0.0, 0.0))
        distance = (cam_location - world_origin).length
        move_distance = distance * 0.25
        local_z = cam.matrix_world.to_3x3() @ mathutils.Vector((0, 0, 1))
        cam.location += local_z.normalized() * move_distance
        new_distance = (cam.location - world_origin).length
        print(f"Camera offset to {new_distance:.4f} after framing")

        # Adjust light distances and initial scale proportionally to asset size
        try:
            target_loc = target_obj.matrix_world.translation.copy()
            # Use the larger XY extent as a sizing reference
            dx = max_corner.x - min_corner.x
            dy = max_corner.y - min_corner.y
            asset_xy_extent = max(abs(dx), abs(dy))
            # Desired radius places lights around the asset; expand by ~5x for more distance
            desired_radius = max(0.25, asset_xy_extent * 0.75 * 5.0)
            angles = bpy.context.scene.lighting_orientation_props

            # CAPTURE BASELINE SCALES FIRST from the freshly loaded rig
            for name, scale_prop, base_scale_prop in [
                (LIGHT_KEY, "key_scale", "baseline_key_scale_vec"),
                (LIGHT_FILL, "fill_scale", "baseline_fill_scale_vec"),
                (LIGHT_RIM, "rim_scale", "baseline_rim_scale_vec"),
                (LIGHT_SHADOW, "shadow_scale", "baseline_shadow_scale_vec"),
            ]:
                light_obj = bpy.data.objects.get(name)
                if light_obj:
                    scale_vec = get_light_scale_vec(name)
                    if scale_vec is not None:
                        setattr(angles, base_scale_prop, scale_vec)

            # NOW apply distance and scale adjustments
            for name, scale_prop, base_scale_prop in [
                (LIGHT_KEY, "key_scale", "baseline_key_scale_vec"),
                (LIGHT_FILL, "fill_scale", "baseline_fill_scale_vec"),
                (LIGHT_RIM, "rim_scale", "baseline_rim_scale_vec"),
                (LIGHT_SHADOW, "shadow_scale", "baseline_shadow_scale_vec"),
            ]:
                light_obj = bpy.data.objects.get(name)
                if not light_obj:
                    continue
                # Move along the light's current look vector (toward/away from target)
                vec = light_obj.location - target_loc
                current_radius = math.sqrt(vec.x * vec.x + vec.y * vec.y + vec.z * vec.z)
                if current_radius > 1e-6:
                    unit_dir = mathutils.Vector(
                        (vec.x / current_radius, vec.y / current_radius, vec.z / current_radius)
                    )
                else:
                    unit_dir = mathutils.Vector((1.0, 0.0, 0.0))
                new_loc = target_loc + unit_dir * desired_radius
                light_obj.location = new_loc
                # Compute and apply scale multiplier relative to baseline
                try:
                    ratio = desired_radius / max(current_radius, 1e-6)
                    # Clamp multiplier per request
                    multiplier = max(0.01, min(10.0, float(ratio)))
                    setattr(angles, scale_prop, multiplier)
                except Exception:
                    pass
            print(f"Adjusted light distances to ~{desired_radius:.3f} and scaled lights proportionally")
        except Exception:
            pass

        # Turntable path is no longer used; camera orbit handled procedurally during rendering
        print("Framed asset and adjusted camera; turntable path not used")

        return True

    def load_hdr_to_blender(self, filepath) -> bool:
        """Load HDR file into Blender's world material"""

        scene = bpy.context.scene
        # Prefer the scene's world, fallback to any world, or create one
        world = scene.world
        if world is None:
            world = bpy.data.worlds[0] if bpy.data.worlds else bpy.data.worlds.new("World")
            try:
                scene.world = world
            except Exception:
                pass
        world.use_nodes = True
        nodes = world.node_tree.nodes

        # TODO: BRANDON, I don't think you want to be setting this if you have defaults in the template environments
        # background = nodes.get("Background")
        # if background:
        #     try:
        #         if "-30" in filepath:
        #             background.inputs[1].default_value = 150
        #         elif "-20" in filepath:
        #             background.inputs[1].default_value = 2
        #         else:
        #             background.inputs[1].default_value = 1
        #     except Exception:
        #         pass

        # Find or create environment texture node and set the image
        env_node = None
        for node in nodes:
            if node.type == "TEX_ENVIRONMENT":
                env_node = node
                break
        if not env_node:
            env_node = nodes.new("ShaderNodeTexEnvironment")
            background = nodes.get("Background")
            if background:
                try:
                    world.node_tree.links.new(env_node.outputs[0], background.inputs[0])
                except Exception:
                    pass

        try:
            env_node.image = bpy.data.images.load(filepath)
            env_node.projection = "MIRROR_BALL" if "uffizi" in filepath else "EQUIRECTANGULAR"
        except Exception:
            return False
        return True

    def execute(self, context):
        if has_export_in_collection():
            self.setup_blender_connections()

            # Ensure Film > Transparent is turned off in Render properties
            try:
                bpy.context.scene.render.film_transparent = False
            except Exception:
                pass

            core_path = None
            for mod in addon_utils.modules():
                if mod.bl_info["name"] == ADDON_SIMREADY_CORE_NAME:
                    core_path = os.path.dirname(mod.__file__)
                    break

            if core_path is None:
                self.report({"ERROR"}, f"{ADDON_SIMREADY_CORE_NAME} addon path not found")
                return {"CANCELLED"}

            core_resources_path = os.path.join(os.path.dirname(core_path), "CORE_ArtistTools_Resources")
            # Choose lighting rig based on preset selection
            preset = context.scene.core_lighting_preset
            if preset == PRESET_STUDIO:
                rig_filename = RIG_STUDIO_BLEND
            else:
                rig_filename = RIG_OUTDOOR_BLEND
            lighting_rig_path = os.path.join(core_resources_path, *REL_TEMPLATE_ENVIRONMENTS, rig_filename)
            print(f"Lighting Rig path: {lighting_rig_path}")
            hdr_path = os.path.join(os.path.dirname(lighting_rig_path), "textures", "rostock_arches_4k.exr")
            if not self.load_lighting_rig(lighting_rig_path):
                self.report({"ERROR"}, f"Failed to load lighting rig ({COL_THUMBNAIL} missing or invalid path)")
                try:
                    context.scene.core_lighting_rig_loaded = False
                except Exception:
                    pass
                return {"CANCELLED"}
            # Stage 1: Create empty Light/Shadow Linking collections on Light_Shadow
            try:
                light_obj = bpy.data.objects.get(LIGHT_SHADOW)
                if light_obj is not None:
                    try:
                        bpy.ops.object.select_all(action="DESELECT")
                    except Exception:
                        pass
                    try:
                        light_obj.select_set(True)
                    except Exception:
                        pass
                    try:
                        bpy.context.view_layer.objects.active = light_obj
                    except Exception:
                        pass
                    try:
                        bpy.ops.object.light_linking_receiver_collection_new()
                    except Exception:
                        pass
                    try:
                        bpy.ops.object.light_linking_blocker_collection_new()
                    except Exception:
                        pass
                    # Stage 2: Rename newly created linking collections and nest Export under them
                    try:
                        exp_coll = bpy.data.collections.get(COL_EXPORT)
                        ll = getattr(light_obj, "light_linking", None)
                        if ll is not None:
                            # Receiver linking collection
                            try:
                                recv_coll = getattr(ll, "receiver_collection", None)
                                if recv_coll:
                                    try:
                                        recv_coll.name = COL_LIGHT_LINKING_EXPORT
                                    except Exception:
                                        pass
                                    # Ensure Export is a child of the receiver linking collection
                                    if exp_coll is not None:
                                        try:
                                            if exp_coll.name not in [c.name for c in recv_coll.children]:
                                                recv_coll.children.link(exp_coll)
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                            # Blocker linking collection
                            try:
                                blk_coll = getattr(ll, "blocker_collection", None)
                                if blk_coll:
                                    try:
                                        blk_coll.name = COL_SHADOW_LINKING_EXPORT
                                    except Exception:
                                        pass
                                    if exp_coll is not None:
                                        try:
                                            if exp_coll.name not in [c.name for c in blk_coll.children]:
                                                blk_coll.children.link(exp_coll)
                                        except Exception:
                                            pass
                            except Exception:
                                pass

                        else:
                            print("[Thumbnailer] Stage 2: light_linking not found - skip assignment")
                    except Exception:
                        pass
                    print("[Thumbnailer] Stage 1: Created receiver/blocker linking collections on Light_Shadow")
                else:
                    print("[Thumbnailer] Stage 1: Light_Shadow not found - skipping linking collection creation")
            except Exception:
                pass

            # Turn off lighting for Export collection via light linking when available
            print("[Thumbnailer] Applying light-link EXCLUDE for Export (when supported)")
            applied = apply_export_light_linking_exclude()
            light_ok, shadow_ok, vlines = validate_shadow_light_linking_state(LIGHT_SHADOW)
            for ln in vlines:
                print(f"[Thumbnailer] {ln}")
            if not (applied and light_ok):
                schedule_light_exclude_retry_timer()
            if light_ok and shadow_ok:
                self.report(
                    {"INFO"},
                    "Shadow light: Export light-link is EXCLUDE; shadow linking includes Export",
                )
            elif light_ok or shadow_ok:
                self.report(
                    {"WARNING"},
                    "Shadow light linking partially verified — see console for [Thumbnailer] lines",
                )
            else:
                self.report(
                    {"WARNING"},
                    "Shadow light linking check failed — see console for [Thumbnailer] lines",
                )
            if not applied and not light_ok:
                self.report(
                    {"WARNING"},
                    "Could not apply light-link EXCLUDE for Export (receiver/collection_child missing?)",
                )

            # Replace /World with the one from the rig file
            try:
                self.load_world_from_rig(lighting_rig_path)
            except Exception:
                pass
            # Import and apply the compositing network from the rig file
            try:
                self.load_compositor_from_rig(lighting_rig_path)
            except Exception:
                pass
            self.load_hdr_to_blender(hdr_path)
            context.space_data.shading.type = "RENDERED"
            try:
                self.frame_asset_offset()
            except RuntimeError as e:
                self.report({"ERROR"}, str(e))
                try:
                    context.scene.core_lighting_rig_loaded = False
                except Exception:
                    pass
                return {"CANCELLED"}
            # Initialize Camera Target sliders from current Thumbnail_Target
            try:
                tgt = bpy.data.objects.get(OBJ_THUMBNAIL_TARGET)
                if tgt:
                    tp = getattr(context.scene, "camera_target_props", None)
                    if tp is not None:
                        tp.target_x = float(tgt.location.x)
                        tp.target_y = float(tgt.location.y)
                        tp.target_z = float(tgt.location.z)
            except Exception:
                pass
            # Capture baseline transform for the Thumbnail_Camera so it can be reset later
            try:
                cam = bpy.data.objects.get(OBJ_THUMBNAIL_CAMERA)
                if cam:
                    cam["_core_baseline_loc"] = (float(cam.location.x), float(cam.location.y), float(cam.location.z))
                    cam["_core_baseline_rot"] = (
                        float(cam.rotation_euler.x),
                        float(cam.rotation_euler.y),
                        float(cam.rotation_euler.z),
                    )
                    try:
                        cam["_core_baseline_lens"] = float(cam.data.lens)
                    except Exception:
                        pass
                    # Sync camera type enum in UI to actual camera data type
                    try:
                        cam_props = context.scene.camera_settings_props
                        cam_props.camera_type = "ORTHO" if cam.data.type == "ORTHO" else "PERSP"
                    except Exception:
                        pass
            except Exception:
                pass
            # Initialize UI light angles from current rig so controls match absolute placement
            try:
                angles = context.scene.lighting_orientation_props
                key_a = get_light_xy_angle(LIGHT_KEY)
                if key_a is not None:
                    angles.key_angle = key_a
                fill_a = get_light_xy_angle(LIGHT_FILL)
                if fill_a is not None:
                    angles.fill_angle = fill_a
                rim_a = get_light_xy_angle(LIGHT_RIM)
                if rim_a is not None:
                    angles.rim_angle = rim_a
                shadow_a = get_light_xy_angle(LIGHT_SHADOW)
                if shadow_a is not None:
                    angles.shadow_angle = shadow_a
                # Initialize power values from rig lights
                key_p = get_light_power(LIGHT_KEY)
                if key_p is not None:
                    angles.key_power = key_p
                fill_p = get_light_power(LIGHT_FILL)
                if fill_p is not None:
                    angles.fill_power = fill_p
                rim_p = get_light_power(LIGHT_RIM)
                if rim_p is not None:
                    angles.rim_power = rim_p
                shadow_p = get_light_power(LIGHT_SHADOW)
                if shadow_p is not None:
                    angles.shadow_power = shadow_p
                # Initialize altitude baselines from current lights and reset offsets
                key_z = get_light_z(LIGHT_KEY)
                if key_z is not None:
                    angles.baseline_key_z = key_z
                    angles.key_altitude = 0.0
                fill_z = get_light_z(LIGHT_FILL)
                if fill_z is not None:
                    angles.baseline_fill_z = fill_z
                    angles.fill_altitude = 0.0
                rim_z = get_light_z(LIGHT_RIM)
                if rim_z is not None:
                    angles.baseline_rim_z = rim_z
                    angles.rim_altitude = 0.0
                shadow_z = get_light_z(LIGHT_SHADOW)
                if shadow_z is not None:
                    angles.baseline_shadow_z = shadow_z
                    angles.shadow_altitude = 0.0
                # Baseline scales were already captured during frame_asset_offset
                # before scale multipliers were applied, so no need to reset them here
            except Exception:
                pass
            # Mark rig as loaded on success
            try:
                context.scene.core_lighting_rig_loaded = True
            except Exception:
                pass
            # Ensure Compositing 'Use Nodes' is disabled on the scene
            try:
                if hasattr(bpy.context, "scene") and bpy.context.scene is not None:
                    try:
                        bpy.context.scene.use_nodes = False
                        print("[Thumbnailer] Compositing: Use Nodes disabled on scene")
                    except Exception:
                        pass
            except Exception:
                pass
            return {"FINISHED"}
        else:
            print("No Export collection present - no asset detected - cancelling")
            try:
                context.scene.core_lighting_rig_loaded = False
            except Exception:
                pass
            return {"CANCELLED"}


THUMB_RENDER_TIMEOUT_S = 60.0
THUMB_TIMER_INTERVAL_S = 0.25
GIF_FRAME_DURATION_MS = 50


class CORE_OT_Auto_Thumbnail(bpy.types.Operator):
    """Run Load Lighting Rig, set 3D view to camera, then Render Thumbnail (new asset, no rig yet)."""

    bl_idname = "core.auto_thumbnail"
    bl_label = "AUTO THUMBNAIL"
    bl_description = (
        "Load the lighting rig, switch the 3D view to the active camera, then render a thumbnail. "
        "For new assets when no rig is loaded; when a rig is already present, use Render Thumbnail"
    )
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context) -> bool:
        rig_loaded = getattr(context.scene, "core_lighting_rig_loaded", False) or (
            COL_THUMBNAIL in bpy.data.collections
        )
        if rig_loaded:
            return False
        if not bpy.data.filepath:
            return False
        if not has_export_in_collection():
            return False
        return True

    def execute(self, context):
        load_res = bpy.ops.core.load_lighting_rig()
        if load_res != {"FINISHED"}:
            self.report(
                {"ERROR"},
                "Auto Thumbnail: lighting rig did not load. See prior messages in the status bar, or use Load Lighting Rig to retry.",
            )
            return {"CANCELLED"}
        if not set_view3d_to_camera_view(context):
            self.report(
                {"WARNING"},
                "Auto Thumbnail: no 3D Viewport was switched to camera (render will still run).",
            )
        render_res = bpy.ops.core.render_thumbnail("INVOKE_DEFAULT")
        if render_res == {"CANCELLED"}:
            self.report(
                {"ERROR"},
                "Auto Thumbnail: could not start render. Save the file, ensure a writable SimReady thumbs path, and try again.",
            )
            return {"CANCELLED"}
        return render_res


class CORE_OT_Render_Thumbnail(bpy.types.Operator):
    """Render still; follow up on a timer (no blocking sleep) to copy into the Nucleus 256x256 path."""

    bl_idname = "core.render_thumbnail"
    bl_label = "Render Thumbnail"
    bl_description = "Render a SimReady compliant thumbnail of the asset"
    bl_options = {"REGISTER"}

    _timer = None
    _thumbnail_path: str = ""
    _thumbs_256_dir: Optional[Path] = None
    _wait_start: float = 0.0
    _timeout: float = THUMB_RENDER_TIMEOUT_S
    _prev_use_nodes = None
    _prev_display_mode = None

    def _cleanup_timer(self, context):
        if self._timer is not None:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
        self._timer = None

    def _restore_render_ui(self, context):
        scene = context.scene
        if self._prev_display_mode is not None:
            try:
                scene.render.display_mode = self._prev_display_mode
            except Exception:
                pass
        if self._prev_use_nodes is not None:
            try:
                scene.use_nodes = self._prev_use_nodes
            except Exception:
                pass

    def _write_256_thumbnail(self) -> None:
        """Copy full-res PNG into the 256x256 subfolder (fixed Nucleus path; same resolution as main file)."""
        if not self._thumbnail_path or self._thumbs_256_dir is None:
            return
        dest_path = self._thumbs_256_dir / os.path.basename(self._thumbnail_path)
        try:
            shutil.copy2(self._thumbnail_path, dest_path)
        except Exception as e:
            print(f"[Thumbnailer] Failed to copy thumbnail to 256x256 folder: {e}")

    def cancel(self, context):
        self._restore_render_ui(context)
        self._cleanup_timer(context)

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        if os.path.isfile(self._thumbnail_path):
            self._restore_render_ui(context)
            self._write_256_thumbnail()
            self._cleanup_timer(context)
            self.report({"INFO"}, f"Thumbnail saved to {self._thumbnail_path}")
            return {"FINISHED"}

        if time.monotonic() - self._wait_start > self._timeout:
            self._restore_render_ui(context)
            self._cleanup_timer(context)
            self.report(
                {"WARNING"},
                "Thumbnail file not found after render; 256x256 folder copy skipped",
            )
            return {"FINISHED"}

        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        file_path = bpy.data.filepath
        if not file_path:
            self.report({"WARNING"}, "Save the blend file before rendering a thumbnail")
            return {"CANCELLED"}

        if not has_export_in_collection():
            self.report({"WARNING"}, "No Export collection — asset not detected")
            return {"CANCELLED"}

        filename, _ = os.path.splitext(os.path.basename(file_path))
        blend_dir = os.path.dirname(file_path)
        asset_root = resolve_asset_root_from_blend_dir(blend_dir)
        thumbs_dir = os.path.join(asset_root, *REL_SIMREADY_THUMBS)
        try:
            os.makedirs(thumbs_dir, exist_ok=True)
        except Exception as e:
            self.report({"ERROR"}, f"Failed to create thumbnail output directory {thumbs_dir}: {e}")
            return {"CANCELLED"}

        if not filename.lower().startswith("sm_"):
            filename_w_prefix = f"sm_{filename}"
        else:
            filename_w_prefix = filename

        variant_number = context.scene.asset_variant_props.variant_number
        filename_w_variant = apply_variant_to_filename(filename_w_prefix, variant_number)
        thumbnail_path = os.path.join(thumbs_dir, f"{filename_w_variant}.usd.png")

        thumbs_256_dir = Path(thumbs_dir) / "256x256"
        try:
            thumbs_256_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.report({"ERROR"}, f"Failed to create thumbnail directory {thumbs_256_dir}: {e}")
            return {"CANCELLED"}

        scene = context.scene
        self._thumbnail_path = thumbnail_path
        self._thumbs_256_dir = thumbs_256_dir
        self._wait_start = time.monotonic()
        self._timeout = THUMB_RENDER_TIMEOUT_S

        set_render_settings(thumbnail_path, "PNG", 800, 600, 100, "CYCLES", None, 128, True)

        self._prev_display_mode = getattr(scene.render, "display_mode", None)
        self._prev_use_nodes = scene.use_nodes
        try:
            scene.use_nodes = False
        except Exception as e:
            print(f"Warning: Could not disable compositor: {e}")
            self._prev_use_nodes = None

        try:
            if self._prev_display_mode is not None:
                scene.render.display_mode = "WINDOW"
            bpy.ops.render.render("INVOKE_DEFAULT", write_still=True)
        except Exception as e:
            print(f"Failed to render image: {e}")
            self._restore_render_ui(context)
            self.report({"ERROR"}, f"Render failed: {e}")
            return {"CANCELLED"}

        wm = context.window_manager
        self._timer = wm.event_timer_add(THUMB_TIMER_INTERVAL_S, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}


class CORE_OT_Select_Light_Prim(bpy.types.Operator):
    "Select a light in the scene by name"

    bl_idname = "core.select_light_prim"
    bl_label = "Select Light"
    bl_description = "Select the specified light object in the scene"

    light_name: StringProperty(name="Light Name", default="")

    @classmethod
    def poll(cls, context):
        return hasattr(bpy, "data") and hasattr(bpy.data, "objects")

    def execute(self, context):
        try:
            light_obj = bpy.data.objects.get(self.light_name)
            if not light_obj:
                self.report({"WARNING"}, f"Light '{self.light_name}' not found")
                return {"CANCELLED"}
            # Deselect all, select target, set active
            try:
                bpy.ops.object.select_all(action="DESELECT")
            except Exception:
                pass
            try:
                light_obj.select_set(True)
            except Exception:
                pass
            try:
                context.view_layer.objects.active = light_obj
            except Exception:
                pass
            return {"FINISHED"}
        except Exception:
            return {"CANCELLED"}


class CORE_OT_Toggle_Safe_Areas(bpy.types.Operator):
    "Toggle safe areas overlay in all 3D viewports"

    bl_idname = "core.toggle_safe_areas"
    bl_label = "Toggle Safe Areas"
    bl_description = "Toggle display of safe areas in camera view overlays"

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        toggled = False
        # Try active space first
        try:
            space = context.space_data
            if space and getattr(space, "type", None) == "VIEW_3D":
                overlay = getattr(space, "overlay", None)
                if overlay and hasattr(overlay, "show_safe_areas"):
                    overlay.show_safe_areas = not bool(overlay.show_safe_areas)
                    toggled = True
        except Exception:
            pass
        # Iterate all VIEW_3D spaces in all windows
        try:
            for window in bpy.context.window_manager.windows:
                screen = window.screen
                for area in screen.areas:
                    if area.type == "VIEW_3D":
                        for sp in area.spaces:
                            if sp.type == "VIEW_3D":
                                overlay = getattr(sp, "overlay", None)
                                if overlay and hasattr(overlay, "show_safe_areas"):
                                    overlay.show_safe_areas = not bool(overlay.show_safe_areas)
                                    toggled = True
        except Exception:
            pass
        # Fallback: toggle on camera data if available
        try:
            cam_obj = bpy.data.objects.get(OBJ_THUMBNAIL_CAMERA) or context.scene.camera
            if cam_obj and getattr(cam_obj, "data", None) and hasattr(cam_obj.data, "show_safe_areas"):
                cam_obj.data.show_safe_areas = not bool(cam_obj.data.show_safe_areas)
                toggled = True
        except Exception:
            pass
        return {"FINISHED"} if toggled else {"CANCELLED"}


class CORE_OT_Render_Turntable(bpy.types.Operator):
    "Render a turntable animation of an asset"

    bl_idname = "core.render_turntable"
    bl_label = "Render Turntable Animation"
    bl_description = "Render a 100-frame turntable animated GIF of the asset"

    # Modal state
    _timer = None
    _phase = None  # 'render', 'assemble', 'cleanup', 'done'
    _waiting_for_render = False
    _start_frame = 1
    _end_frame = 101
    _current_frame = 1
    _filename = ""
    _output_folder = ""
    _png_list = None
    _total_steps = 0
    _current_step = 0
    _last_image_path = ""
    # Camera orbit state (when using Thumbnail_Camera)
    _cam = None
    _target = None
    _radius_xy = 0.0
    _z_value = 0.0
    _start_angle = 0.0
    _orig_loc = None
    _orig_rot = None
    _orig_lens = None
    _temp_track = None

    @classmethod
    def poll(cls, context):
        return context is not None and hasattr(context, "scene")

    def _begin_progress(self, context, total_steps):
        wm = context.window_manager
        wm.progress_begin(0, total_steps)
        context.scene.progress_bar_props.progress = 0.0

    def _update_progress(self, context):
        wm = context.window_manager
        wm.progress_update(self._current_step)
        if self._total_steps > 0:
            context.scene.progress_bar_props.progress = self._current_step / self._total_steps

    def _end_progress(self, context):
        wm = context.window_manager
        try:
            wm.progress_update(self._total_steps)
        except Exception:
            pass
        try:
            wm.progress_end()
        except Exception:
            pass

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        # If Blender render job is running, wait until it completes
        try:
            if self._waiting_for_render and getattr(bpy.app, "is_job_running", None):
                if bpy.app.is_job_running("RENDER"):
                    return {"RUNNING_MODAL"}
                else:
                    # Render finished
                    self._waiting_for_render = False
                    # Count step for the finished frame
                    self._current_step += 1
                    self._update_progress(context)
            elif self._waiting_for_render:
                # Fallback check when is_job_running is unavailable: poll file existence
                if os.path.exists(self._last_image_path):
                    self._waiting_for_render = False
                    self._current_step += 1
                    self._update_progress(context)
                else:
                    return {"RUNNING_MODAL"}
        except Exception:
            pass

        if self._phase == "render":
            if self._current_frame < self._end_frame:
                # Start next frame render
                try:
                    # Position the thumbnail camera around the target for this frame (no keyframes)
                    if self._cam and self._target:
                        frac = (self._current_frame - self._start_frame) / max(1, (self._end_frame - self._start_frame))
                        angle = self._start_angle + (2.0 * math.pi * frac)
                        if self._radius_xy <= 0.0:
                            self._radius_xy = 1.0
                        tgt = self._target.location
                        new_x = math.cos(angle) * self._radius_xy
                        new_y = math.sin(angle) * self._radius_xy
                        self._cam.location = (tgt.x + new_x, tgt.y + new_y, self._z_value)
                    bpy.context.scene.frame_set(self._current_frame)
                    image_path = f"{self._output_folder}/{self._filename}_turntable_{self._current_frame}.PNG"
                    bpy.context.scene.render.filepath = image_path
                    self._last_image_path = image_path
                    set_render_settings(image_path, "PNG", 400, 300, 100, "CYCLES", None, 64, True)
                    bpy.ops.render.render("INVOKE_DEFAULT", write_still=True)
                    self._png_list.append(image_path)
                    self._waiting_for_render = True
                    self._current_frame += 1
                    return {"RUNNING_MODAL"}
                except Exception:
                    self.cancel(context)
                    self.report({"ERROR"}, "Failed to render frame")
                    return {"CANCELLED"}
            else:
                self._phase = "assemble"
                return {"RUNNING_MODAL"}

        if self._phase == "assemble":
            try:
                turntable_gif_path = f"{self._output_folder}/{self._filename}_turntable.gif"
                frames_open = []
                try:
                    for image_path in self._png_list:
                        src = Image.open(image_path)
                        try:
                            frames_open.append(src.copy())
                        finally:
                            src.close()
                    if not frames_open:
                        raise ValueError("No frames to assemble")
                    frames_open[0].save(
                        turntable_gif_path,
                        format="GIF",
                        append_images=frames_open[1:],
                        save_all=True,
                        duration=GIF_FRAME_DURATION_MS,
                        loop=0,
                    )
                finally:
                    for fr in frames_open:
                        try:
                            fr.close()
                        except Exception:
                            pass
                self._current_step += 1
                self._update_progress(context)
                self._phase = "cleanup"
                return {"RUNNING_MODAL"}
            except Exception:
                self.cancel(context)
                self.report({"ERROR"}, "Failed to assemble GIF")
                return {"CANCELLED"}

        if self._phase == "cleanup":
            try:
                if self._png_list:
                    # Delete a few per tick to keep UI responsive
                    for _ in range(min(10, len(self._png_list))):
                        png = self._png_list.pop(0)
                        try:
                            os.remove(png)
                        except Exception:
                            pass
                        self._current_step += 1
                        self._update_progress(context)
                    return {"RUNNING_MODAL"}
                else:
                    self._phase = "done"
            except Exception:
                self._phase = "done"

        if self._phase == "done":
            # Restore camera transform and remove temporary constraint
            try:
                if self._cam:
                    if self._orig_loc is not None:
                        self._cam.location = self._orig_loc
                    if self._orig_rot is not None:
                        self._cam.rotation_euler = self._orig_rot
                    try:
                        if self._orig_lens is not None and hasattr(self._cam.data, "lens"):
                            self._cam.data.lens = float(self._orig_lens)
                    except Exception:
                        pass
                    if self._temp_track and self._temp_track in self._cam.constraints:
                        try:
                            self._cam.constraints.remove(self._temp_track)
                        except Exception:
                            pass
            except Exception:
                pass
            self._end_progress(context)
            try:
                context.scene.progress_bar_props.progress = 1.0
            except Exception:
                pass
            self.cancel(context)
            return {"FINISHED"}

        return {"RUNNING_MODAL"}

    def execute(self, context):
        file_path = bpy.data.filepath
        if not file_path:
            print("You can't render a thumbnail for an undefined asset - save first")
            return {"CANCELLED"}

        if has_export_in_collection():
            filename = os.path.splitext(os.path.basename(file_path))[0]
            blend_dir = os.path.dirname(file_path)
            asset_root = resolve_asset_root_from_blend_dir(blend_dir)
            turntable_path = os.path.join(asset_root, *REL_SIMREADY_THUMBS)
            try:
                os.makedirs(turntable_path, exist_ok=True)
            except Exception as e:
                print(f"Failed to create turntable output directory {turntable_path}: {e}")
                return {"CANCELLED"}
            # Use the Thumbnail_Camera for the turntable orbit
            try:
                self._cam = bpy.data.objects.get(OBJ_THUMBNAIL_CAMERA)
                self._target = bpy.data.objects.get(OBJ_THUMBNAIL_TARGET)
                if self._cam is None or self._target is None:
                    print(f"Missing {OBJ_THUMBNAIL_CAMERA} or {OBJ_THUMBNAIL_TARGET} - cancelling")
                    return {"CANCELLED"}
                bpy.context.scene.camera = self._cam
                # Capture original transform and compute orbit parameters
                vec = self._cam.location - self._target.location
                self._radius_xy = math.hypot(vec.x, vec.y)
                self._z_value = float(self._cam.location.z)
                self._start_angle = math.atan2(vec.y, vec.x)
                self._orig_loc = self._cam.location.copy()
                self._orig_rot = self._cam.rotation_euler.copy()
                try:
                    self._orig_lens = float(self._cam.data.lens)
                except Exception:
                    self._orig_lens = None
                # Ensure the camera looks at the target during orbit via a temporary Track To
                try:
                    self._temp_track = self._cam.constraints.new(type="TRACK_TO")
                    self._temp_track.target = self._target
                    self._temp_track.track_axis = "TRACK_NEGATIVE_Z"
                    self._temp_track.up_axis = "UP_Y"
                except Exception:
                    self._temp_track = None
            except Exception:
                print(f"Failed to initialize {OBJ_THUMBNAIL_CAMERA} for turntable - cancelling")
                return {"CANCELLED"}

            # Add sm_ prefix if not present
            if not filename.lower().startswith("sm_"):
                filename_w_prefix = f"sm_{filename}"
            else:
                filename_w_prefix = filename

            # Get variant number from scene property and apply it
            variant_number = context.scene.asset_variant_props.variant_number
            filename_w_variant = apply_variant_to_filename(filename_w_prefix, variant_number)

            # Initialize modal state
            self._start_frame = 1
            self._end_frame = 101
            self._current_frame = self._start_frame
            self._filename = filename_w_variant
            self._output_folder = turntable_path
            self._png_list = []
            total_frames = max(0, self._end_frame - self._start_frame)
            self._total_steps = total_frames + 1 + total_frames
            self._current_step = 0
            self._phase = "render"
            self._waiting_for_render = False

            self._begin_progress(context, self._total_steps)

            wm = context.window_manager
            self._timer = wm.event_timer_add(0.1, window=context.window)
            wm.modal_handler_add(self)
            return {"RUNNING_MODAL"}

        else:
            print("No Export collection present - no asset detected - cancelling")
            return {"CANCELLED"}

    def cancel(self, context):
        if self._timer:
            try:
                wm = context.window_manager
                wm.event_timer_remove(self._timer)
            except Exception:
                pass
        self._timer = None


class CORE_OT_Reset_Thumbnail_Camera(bpy.types.Operator):
    "Reset Thumbnail Camera to baseline transform"

    bl_idname = "core.reset_thumbnail_camera"
    bl_label = "Reset Camera"
    bl_description = "Reset the Thumbnail Camera back to the saved baseline"

    @classmethod
    def poll(cls, context):
        return OBJ_THUMBNAIL_CAMERA in bpy.data.objects

    def execute(self, context):
        try:
            cam = bpy.data.objects.get(OBJ_THUMBNAIL_CAMERA)
            if not cam:
                self.report({"ERROR"}, f"{OBJ_THUMBNAIL_CAMERA} not found")
                return {"CANCELLED"}
            base_loc = cam.get("_core_baseline_loc")
            base_rot = cam.get("_core_baseline_rot")
            base_lens = cam.get("_core_baseline_lens")

            # Convert IDPropertyArray to tuple if needed
            def _to_tuple3(val):
                try:
                    if val is None:
                        return None
                    if hasattr(val, "__len__") and len(val) == 3:
                        return (float(val[0]), float(val[1]), float(val[2]))
                except Exception:
                    return None
                return None

            loc3 = _to_tuple3(base_loc)
            rot3 = _to_tuple3(base_rot)
            if loc3:
                cam.location.x, cam.location.y, cam.location.z = loc3
            if rot3:
                cam.rotation_euler.x, cam.rotation_euler.y, cam.rotation_euler.z = rot3
            try:
                if base_lens is not None and hasattr(cam.data, "lens"):
                    cam.data.lens = float(base_lens)
            except Exception:
                pass
            # Ensure camera is active
            try:
                context.scene.camera = cam
            except Exception:
                pass
            try:
                context.view_layer.update()
            except Exception:
                pass
            return {"FINISHED"}
        except Exception:
            self.report({"ERROR"}, "Failed to reset camera")
            return {"CANCELLED"}


class CORE_PT_Thumbnailer(ASSET_panel_common, bpy.types.Panel):
    """Thumbnail Panel in N-Panel"""

    bl_idname = "CORE_PT_Thumbnailer"
    bl_label = "Thumbnailer"
    bl_order = 17

    def draw(self, context):
        box = self.layout.column(align=True)

        auto_row = box.row(align=True)
        auto_row.scale_y = 2.5
        auto_row.operator(CORE_OT_Auto_Thumbnail.bl_idname, icon="IMAGE_DATA")

        # Add asset variant number input at the top
        variant_row = box.row(align=True)
        variant_row.prop(context.scene.asset_variant_props, "variant_number", text="Asset Variant")

        line_00 = box.row(align=True)
        line_00.prop(context.scene, "core_lighting_preset", text="Lighting Environment")
        line_01 = box.row(align=True)
        line_01.scale_y = 1.0
        line_01.operator(CORE_OT_Load_Lighting_Rig.bl_idname, text="LOAD LIGHTING RIG", icon="LIGHT")
        # Section label for camera-related controls
        box.label(text="Camera Controls")

        # Disable downstream controls until rig is loaded
        rig_loaded = getattr(context.scene, "core_lighting_rig_loaded", False) or (
            COL_THUMBNAIL in bpy.data.collections
        )
        controls = box.column(align=True)
        controls.enabled = rig_loaded
        # Camera controls (moved above lighting)
        cam_section = controls.column(align=True)
        cam_row = cam_section.row(align=True)
        cam_op = cam_row.operator(CORE_OT_Select_Light_Prim.bl_idname, text="CAMERA", icon="VIEW_CAMERA")
        if cam_op:
            cam_op.light_name = OBJ_THUMBNAIL_CAMERA
        # Toggle Safe Areas button
        toggle_row = cam_section.row(align=True)
        toggle_row.operator("core.toggle_safe_areas", text="Toggle Safe Areas", icon="OVERLAY")
        try:
            cam_obj = bpy.data.objects.get(OBJ_THUMBNAIL_CAMERA) or context.scene.camera
        except Exception:
            cam_obj = context.scene.camera
        cam_props = getattr(context.scene, "camera_settings_props", None)
        if cam_props is not None:
            cam_section.prop(cam_props, "camera_type", text="")
            # Show focal length or ortho scale depending on selected type
            if cam_obj and getattr(cam_obj, "type", "") == "CAMERA" and getattr(cam_obj, "data", None):
                if cam_props.camera_type == "PERSP":
                    cam_section.prop(cam_obj.data, "lens", text="Focal Length")
                elif cam_props.camera_type == "ORTHO":
                    cam_section.prop(cam_obj.data, "ortho_scale", text="Ortho Scale")
        # Camera target sliders
        cam_section.separator()
        cam_section.label(text="Camera Target Position")
        target_props = getattr(context.scene, "camera_target_props", None)
        if target_props is not None:
            row_t = cam_section.row(align=True)
            row_t.prop(target_props, "target_x", text="X")
            row_t.prop(target_props, "target_y", text="Y")
            row_t.prop(target_props, "target_z", text="Z")
        # Place Reset Camera as the final camera control
        cam_section.separator()
        cam_section.operator(CORE_OT_Reset_Thumbnail_Camera.bl_idname, text="Reset Camera", icon="VIEW_CAMERA")
        # Lighting orientation controls
        controls.separator()
        controls.label(text="Lighting Controls")
        angles = context.scene.lighting_orientation_props
        # Key light
        key_col = controls.column(align=True)
        key_row = key_col.row(align=True)
        key_op = key_row.operator(CORE_OT_Select_Light_Prim.bl_idname, text="KEY LIGHT", icon="LIGHT")
        if key_op:
            key_op.light_name = LIGHT_KEY
        key_col.prop(angles, "key_power", text="Power")
        key_col.prop(angles, "key_angle", text="Orientation")
        key_col.prop(angles, "key_altitude", text="Altitude")
        key_col.prop(angles, "key_scale", text="Scale")
        controls.separator()
        # Fill light
        fill_col = controls.column(align=True)
        fill_row = fill_col.row(align=True)
        fill_op = fill_row.operator(CORE_OT_Select_Light_Prim.bl_idname, text="FILL LIGHT", icon="LIGHT")
        if fill_op:
            fill_op.light_name = LIGHT_FILL
        fill_col.prop(angles, "fill_power", text="Power")
        fill_col.prop(angles, "fill_angle", text="Orientation")
        fill_col.prop(angles, "fill_altitude", text="Altitude")
        fill_col.prop(angles, "fill_scale", text="Scale")
        controls.separator()
        # Rim light
        rim_col = controls.column(align=True)
        rim_row = rim_col.row(align=True)
        rim_op = rim_row.operator(CORE_OT_Select_Light_Prim.bl_idname, text="RIM LIGHT", icon="LIGHT")
        if rim_op:
            rim_op.light_name = LIGHT_RIM
        rim_col.prop(angles, "rim_power", text="Power")
        rim_col.prop(angles, "rim_angle", text="Orientation")
        rim_col.prop(angles, "rim_altitude", text="Altitude")
        rim_col.prop(angles, "rim_scale", text="Scale")
        controls.separator()
        # Shadow light
        shadow_col = controls.column(align=True)
        shadow_row = shadow_col.row(align=True)
        shadow_op = shadow_row.operator(CORE_OT_Select_Light_Prim.bl_idname, text="SHADOW LIGHT", icon="LIGHT")
        if shadow_op:
            shadow_op.light_name = LIGHT_SHADOW
        shadow_col.prop(angles, "shadow_power", text="Power")
        shadow_col.prop(angles, "shadow_angle", text="Orientation")
        shadow_col.prop(angles, "shadow_altitude", text="Altitude")
        shadow_col.prop(angles, "shadow_scale", text="Scale")

        line_03 = controls.row(align=True)
        line_03.operator(CORE_OT_Render_Thumbnail.bl_idname, text="Render Thumbnail", icon="FILE_IMAGE")
        line_04 = controls.row(align=True)
        line_04.operator(CORE_OT_Render_Turntable.bl_idname, text="Render Turntable Anim", icon="ORIENTATION_GIMBAL")
        line_05 = box.row(align=True)
        percent_complete = int(context.scene.progress_bar_props.progress * 100)
        line_05.label(text=f"Turntable Progress: {percent_complete}%")
