# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
import bpy
from bpy.props import BoolProperty, StringProperty


class GlobalMetadataProps(bpy.types.PropertyGroup):
    """Property group for storing global metadata that will be used in defaultPrim during export"""

    # Wikidata properties for global storage
    wikidata_query: StringProperty(
        name="Global Wikidata Query",
        description="Wikidata search query stored globally for this Blender file",
        default="",
    )

    wikidata_query_id: StringProperty(
        name="Global Wikidata Query ID",
        description="Wikidata query ID stored globally for this Blender file",
        default="",
    )

    wikidata_result_id: StringProperty(
        name="Global Wikidata ID", description="Selected Wikidata ID stored globally for this Blender file", default=""
    )

    wikidata_result_label: StringProperty(
        name="Global Wikidata Label",
        description="Selected Wikidata label stored globally for this Blender file",
        default="",
    )

    wikidata_result_description: StringProperty(
        name="Global Wikidata Description",
        description="Selected Wikidata description stored globally for this Blender file",
        default="",
    )

    # Global dense caption properties
    global_caption: StringProperty(
        name="Global Dense Caption",
        description="Write your own dense caption, or let AI try and have a turn at it",
        default="",
    )

    global_caption_manual: BoolProperty(
        name="Manual Caption",
        description="Manual: Write your own caption. Manual Off: AI will try and generate a caption",
        default=True,
    )

    global_caption_generation_failed: BoolProperty(
        name="Global Caption Generation Failed",
        description="Whether automatic caption generation failed for the global caption",
        default=False,
    )

    wikidata_use_id: BoolProperty(
        name="Use Wikidata ID", description="Whether to use the Wikidata ID for the global metadata", default=False
    )
