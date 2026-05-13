# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
from bpy.types import Panel


class CORE_SIMREADY_PT_top_panel(Panel):
    bl_label = "SimReady Metadata"
    bl_idname = "CORE_SIMREADY_PT_top_panel"
    bl_category = "CORE"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 1

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

            # Store for Root Level button - only enabled if we have a selected result
            store_row = layout.row()
            store_row.enabled = scene.wikidata_results != "NONE"
            store_row.operator("metadata.store_for_root", text="Store for Root Level")

        elif has_valid_query and not has_results:
            # Show a hint when query is valid but no results yet
            info_row = layout.row()
            hint_text = "Click Search by ID to find entity" if use_id_mode else "Click Search to find results"
            info_row.label(text=hint_text, icon="INFO")
        elif not has_valid_query:
            # Show a hint when no valid search term
            info_row = layout.row()
            hint_text = "Enter a Wikidata ID above" if use_id_mode else "Enter a search term above"
            info_row.label(text=hint_text, icon="QUESTION")

        # Global Metadata Display Section
        layout.separator()
        box = layout.box()
        box.label(text="Global Metadata (for defaultPrim)", icon="WORLD")

        global_metadata = scene.global_metadata

        if global_metadata.wikidata_query:
            # Show stored global metadata
            query_row = box.row()
            query_row.label(text=f"Query: {global_metadata.wikidata_query}")

            if global_metadata.wikidata_result_id:
                id_row = box.row()
                id_row.label(text=f"ID: {global_metadata.wikidata_result_id}")

                if global_metadata.wikidata_result_label:
                    label_row = box.row()
                    label_row.label(text=f"Label: {global_metadata.wikidata_result_label}")

                if global_metadata.wikidata_result_description:
                    desc_row = box.row()
                    desc_row.label(text=f"Description: {global_metadata.wikidata_result_description}")
            else:
                no_result_row = box.row()
                no_result_row.label(text="No result stored", icon="INFO")
        else:
            no_metadata_row = box.row()
            no_metadata_row.label(text="No global metadata stored", icon="QUESTION")

        # Global Dense Caption Section
        layout.separator()
        caption_box = layout.box()
        caption_box.label(text="Global Dense Caption", icon="TEXT")

        # Show the set manually checkbox
        caption_box.prop(global_metadata, "global_caption_manual")

        # Generate caption button
        button_row = caption_box.row()
        button_row.enabled = not global_metadata.global_caption_manual
        button_row.operator("global.generate_caption", text="Generate Global Caption")

        # Show current global caption if it exists
        if global_metadata.global_caption:
            caption_row = caption_box.row()
            caption_row.label(text=f"Caption: {global_metadata.global_caption}")
        else:
            caption_row = caption_box.row()
            caption_row.label(text="No global caption generated")

        # Manual caption input section
        manual_box = caption_box.box()

        if global_metadata.global_caption_generation_failed or global_metadata.global_caption_manual:
            manual_box.label(text="Enter caption (manually set or AI failed):")
            manual_box.prop(global_metadata, "global_caption", text="Manual Global Caption")
            manual_box.operator("global.generate_caption_manual", text="Apply Manual Global Caption")
        else:
            manual_box.enabled = False
