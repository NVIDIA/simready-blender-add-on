# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy
from bpy.props import BoolProperty, CollectionProperty, StringProperty
from bpy.types import PropertyGroup

from .pt_learning import ASSET_panel_common

DEFAULT_GROUPS = [
    (
        "GEOMETRY",
        [
            "AXIS: Z-UP, X - front axis",
            "UNITS: 1 unit — 1 meter",
            "Asset has 0.0.0 location, 1.0 scale, 0.0 rotation",
            "One asset per USD file",
            "Separate Dynamic Objects",
            "Separate Moving Parts",
            "Separate Glass Parts (or transparent plastic)",
            "Multiple materials Per Mesh Allowed",
            "Main object pivots are centered and properly placed",
            "Each of the individual parts has their pivots at their center of rotation",
            "Geometry must be a solid mesh with no holes",
            "Glass parts must be double-sided",
            "Separate Moving Parts don't intersect each other",
            "Geometry must be clean (no n-gons)",
            "Geometry produces correct shading",
            "Geometry is optimized (no extra loops/polygons)",
            "Decals are used without a transparent background; use geometry or unique textures (e.g., for brand names)",
        ],
    ),
    (
        "UVs",
        [
            "Optionally use UDIMs",
            "Unwrap for tile textures",
            "No visible seams on UVs",
            "No stretched UV's in visible zones",
            "Texel density min 3000 per meter with 4k texture (for each Island)",
            "No zero UV areas on mapping (unmapped polygons)",
        ],
    ),
    (
        "TEXTURES",
        [
            "Textures are 8-bit RGB",
            "PNG uses proper texture name",
            "Use Correct PBR values",
            "Albedo map should have suffix _alb",
            "Normal map should have suffix _nor",
            "ORM (AO, Roughness, Metalness) map should have suffix _orm",
            "Roughness map can be separate if used for glass with suffix _rou",
            "Emissive mapshould have suffix _emi",
            "When feasible, create albedo with 50% gray base value",
        ],
    ),
]

TOOLTIP_HINTS = {
    # Example overrides; defaults will be generated if not present
    "AXIS: Z-UP, X - front axis": "Ensure scene axes are set: Z up, and the front of the asset points towards +X forward",
    "UNITS: 1 unit — 1 meter": "Ensure the asset is scaled to 1 unit = 1 meter",
    "Asset has 0.0.0 location, 1.0 scale, 0.0 rotation": "Ensure the asset is located at the origin, has a scale of 1.0, and no rotation",
    "One asset per USD file": "Ensure the asset is exported as a single USD file",
    "Separate Dynamic Objects": "Ensure dynamic objects are separate mesh objects",
    "Separate Moving Parts": "Ensure moving parts/components are separate mesh objects",
    "Separate Glass Parts (or transparent plastic)": "Ensure glass parts (or transparent plastic) are separate mesh objects",
    "Multiple materials Per Mesh Allowed": "You can have multiple materials per mesh, but you must ensure that the materials are properly separated and not overlapping",
    "Main object pivots are centered and properly placed": "Ensure the main object has its pivots centered and properly placed",
    "Each of the individual parts has their pivots at their center of rotation": "Ensure each of the individual parts has its pivots at their center of rotation",
    "Geometry must be a solid mesh with no holes": "Ensure the geometry is a solid mesh with no holes",
    "Glass parts must be double-sided": "Ensure the glass parts are double-sided",
    "Separate Moving Parts don't intersect each other": "Ensure the separate moving parts do not intersect each other as it will create collision issues",
    "Geometry must be clean (no n-gons)": "Ensure the geometry is clean (no n-gons)",
    "Geometry produces correct shading": "Ensure the geometry produces correct shading",
    "Geometry is optimized (no extra loops/polygons)": "Ensure the geometry is optimized (no extra loops/polygons)",
    "Decals are used without a transparent background": "Ensure the decals are used without a transparent background; use geometry or unique textures (e.g., for brand names)",
    "Optionally use UDIMs": "You can use UDIMs, but it is not required",
    "Unwrap for tile textures": "Ensure the textures are unwrapped so they tile correctly",
    "No visible seams on UVs": "Ensure the UV's have no visible seams",
    "No stretched UV's in visible zones": "Ensure the UV's have no stretched UV's in visible zones",
    "Texel density min 3000 per meter with 4k texture (for each Island)": "Ensure the texel density is at least 3000 per meter with 4k texture (for each Island)",
    "No zero UV areas on mapping (unmapped polygons)": "Ensure the UV's have no zero UV areas on mapping (unmapped polygons)",
    "Textures are 8-bit RGB": "Ensure the textures are 8-bit RGB - no alpha or higher bit depth",
    "PNG uses proper texture name": "Ensure the texture name follows the naming convention",
    "Use Correct PBR values": "Ensure the PBR values are correct for the material",
    "Albedo map should have suffix _alb": "Ensure the albedo map name has suffix _alb to indicate that it is an albedo texture",
    "Normal map should have suffix _nor": "Ensure the normal map name has suffix _nor to indicate that it is a normal texture",
    "ORM (AO, Roughness, Metalness) map should have suffix _orm": "Ensure the ORM map name has suffix _orm to indicate that it is an ORM texture",
    "Roughness map can be separate if used for glass with suffix _rou": "If using a separate roughness map for glass, the texture name should have suffix _rou",
    "Emissive mapshould have suffix _emi": "Ensure the emissive map name has suffix _emi to indicate that it is an emissive texture",
    "When feasible, create albedo with 50% gray base value": "For human-made surfaces (painted metal/plastic/rubber) with low color variance, ensure the albedo is created with a 50% gray base to enable colorization in engine",
}


class ArtistChecklistSubItem(PropertyGroup):
    label: StringProperty(name="Task")
    done: BoolProperty(name="Done", default=False, description="Mark this checklist item complete")
    tip: StringProperty(name="Tooltip", default="")


class ArtistChecklistGroup(PropertyGroup):
    title: StringProperty(name="Title")
    items: CollectionProperty(type=ArtistChecklistSubItem)


class ArtistChecklistProps(PropertyGroup):
    groups: CollectionProperty(type=ArtistChecklistGroup)


class CORE_OT_artist_checklist_launch(bpy.types.Operator):
    bl_idname = "core.artist_checklist_launch"
    bl_label = "SimReady Checklist"
    bl_description = "Launch the SimReady Checklist"
    bl_options = {"REGISTER", "UNDO"}

    def ensure_defaults(self, context):
        props = context.scene.artist_checklist
        if len(props.groups) == 0:
            for group_title, subitems in DEFAULT_GROUPS:
                group = props.groups.add()
                group.title = group_title
                for sub in subitems:
                    item = group.items.add()
                    item.label = sub
                    item.tip = TOOLTIP_HINTS.get(sub, f"{group_title} — {sub}")

    def invoke(self, context, event):
        self.ensure_defaults(context)
        return context.window_manager.invoke_props_dialog(self, width=700)

    def draw(self, context):
        layout = self.layout
        props = context.scene.artist_checklist

        for g_idx, group in enumerate(props.groups, start=1):
            box = layout.box()
            box.label(text=f"{g_idx}. {group.title}")
            col = box.column(align=True)
            for i_idx, item in enumerate(group.items, start=1):
                letter = chr(ord("A") + i_idx - 1)
                row = col.row(align=True)
                row.prop(item, "done", text="")  # checkbox
                row.label(text=f"{letter}: {item.label}")  # label
                info = row.operator("core.artist_checklist_tip", text="", icon="INFO", emboss=False)
                info.tip = item.tip

        layout.separator()
        row_actions = layout.row(align=True)
        row_actions.operator("core.artist_checklist_reset", text="Reset", icon="LOOP_BACK")
        row_actions.operator("core.artist_checklist_mark_all", text="Mark All", icon="CHECKMARK")

    def execute(self, context):
        return {"FINISHED"}


class CORE_OT_artist_checklist_reset(bpy.types.Operator):
    bl_idname = "core.artist_checklist_reset"
    bl_label = "Reset Checklist"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        props = context.scene.artist_checklist
        for group in props.groups:
            for item in group.items:
                item.done = False
        return {"FINISHED"}


class CORE_OT_artist_checklist_mark_all(bpy.types.Operator):
    bl_idname = "core.artist_checklist_mark_all"
    bl_label = "Mark All Complete"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        props = context.scene.artist_checklist
        for group in props.groups:
            for item in group.items:
                item.done = True
        return {"FINISHED"}


class CORE_OT_artist_checklist_tip(bpy.types.Operator):
    bl_idname = "core.artist_checklist_tip"
    bl_label = "Info"
    bl_options = {"INTERNAL"}

    tip: StringProperty(default="")

    @classmethod
    def description(cls, context, properties):
        try:
            return properties.tip or "Info"
        except Exception:
            return "Info"

    def execute(self, context):
        return {"FINISHED"}


class CORE_PT_artist_checklist(ASSET_panel_common, bpy.types.Panel):
    bl_idname = "CORE_PT_ArtistChecklist"
    bl_label = "SimReady Checklist"
    bl_order = 2

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator(CORE_OT_artist_checklist_launch.bl_idname, text="Launch")
