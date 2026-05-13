# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import base64
import os
import re
import tempfile
import webbrowser

import bpy

# LAZY IMPORT: markdown is imported only when needed (after dependency check)
# import markdown  # Moved to lazy import in functions that use it

# from .workflow_filter import WorkflowFilterMixin


class ASSET_panel_common:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    bl_options = {"DEFAULT_CLOSED"}


class CORE_OT_open_docs(bpy.types.Operator):
    bl_idname = "core.open_docs"
    bl_label = "Open Documentation"
    bl_description = "Open the documentation for CORE Tools"
    bl_options = {"REGISTER", "UNDO"}

    # MIME type lookup for the image extensions we expect in the docs.
    _MIME_TYPES = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }

    @staticmethod
    def _encode_image_as_data_uri(abs_path):
        """Read an image file from disk and return a base64 data URI, or None on failure."""
        try:
            with open(abs_path, "rb") as img_file:
                img_b64 = base64.b64encode(img_file.read()).decode("utf-8")
        except OSError as e:
            print(f"Warning: Could not read image {abs_path}: {e}")
            return None
        ext = os.path.splitext(abs_path)[1].lower()
        mime = CORE_OT_open_docs._MIME_TYPES.get(ext, "application/octet-stream")
        return f"data:{mime};base64,{img_b64}"

    @staticmethod
    def embed_images_in_markdown(md_content, md_file_path):
        """
        Rewrite image references in the markdown so they render when the file is
        served from a temp directory.

        The current README uses HTML <img> tags with relative `src` attributes
        (e.g. `<img src="./doc_images/foo.png" ...>`). We resolve each src
        against the markdown file's directory and inline the image as a base64
        data URI so the generated HTML is fully self-contained.

        This also keeps backwards compatibility with the older Markdown
        reference-style syntax (`![][imageN]` paired with
        `![imageN](./path/to/image.png)` definitions at the bottom of the file).
        """
        md_dir = os.path.dirname(md_file_path)

        # 1. HTML <img src="..."> tags (the format the new docs use).
        #    Match src values that are unquoted, single-quoted, or double-quoted.
        html_img_pattern = re.compile(
            r"""(<img\b[^>]*?\bsrc\s*=\s*)(["'])([^"']+)\2""",
            re.IGNORECASE,
        )

        def _replace_html_src(match):
            prefix, quote, src = match.group(1), match.group(2), match.group(3)
            if src.startswith(("data:", "http://", "https://")):
                return match.group(0)
            src_path = src.lstrip("/")
            abs_path = os.path.normpath(os.path.join(md_dir, src_path))
            if not os.path.isfile(abs_path):
                print(f"Warning: Image file not found for <img src>: {abs_path}")
                return match.group(0)
            data_uri = CORE_OT_open_docs._encode_image_as_data_uri(abs_path)
            if not data_uri:
                return match.group(0)
            return f"{prefix}{quote}{data_uri}{quote}"

        md_content = html_img_pattern.sub(_replace_html_src, md_content)

        # 2. Markdown inline images: ![alt](path)
        md_inline_pattern = re.compile(r"(!\[[^\]]*\]\()([^)\s]+)(\s*(?:\"[^\"]*\")?\s*\))")

        def _replace_md_inline(match):
            head, src, tail = match.group(1), match.group(2), match.group(3)
            if src.startswith(("data:", "http://", "https://")):
                return match.group(0)
            abs_path = os.path.normpath(os.path.join(md_dir, src.lstrip("/")))
            if not os.path.isfile(abs_path):
                return match.group(0)
            data_uri = CORE_OT_open_docs._encode_image_as_data_uri(abs_path)
            if not data_uri:
                return match.group(0)
            return f"{head}{data_uri}{tail}"

        md_content = md_inline_pattern.sub(_replace_md_inline, md_content)

        # 3. Legacy reference-style images: ![][imageN] paired with
        #    ![imageN](./addon/library/resources/doc_images/imageN.png)
        ref_use_pattern = re.compile(r"!\[\]\[([^\]]+)\]")
        ref_def_pattern = re.compile(r"!\[([^\]]+)\]\(([^)]+)\)")
        ref_map = {name: path for name, path in ref_def_pattern.findall(md_content)}
        for ref_name in set(ref_use_pattern.findall(md_content)):
            ref_path = ref_map.get(ref_name)
            if not ref_path:
                continue
            abs_path = os.path.normpath(os.path.join(md_dir, ref_path.lstrip("./").lstrip("/")))
            if not os.path.isfile(abs_path):
                print(f"Warning: Image file not found for reference {ref_name}: {abs_path}")
                continue
            data_uri = CORE_OT_open_docs._encode_image_as_data_uri(abs_path)
            if not data_uri:
                continue
            md_content = md_content.replace(f"![][{ref_name}]", f"![{ref_name}]({data_uri})")

        return md_content

    def execute(self, context):
        """Open documentation without any specific anchor"""
        return CORE_OT_open_docs.generate_and_open_docs()

    @staticmethod
    def generate_and_open_docs(anchor=None):
        """
        Shared method to generate HTML documentation and open it in browser.

        Args:
            anchor (str, optional): The anchor to navigate to in the documentation
        """
        # Lazy import markdown only when actually needed
        try:
            import markdown
        except ImportError:
            print("ERROR: markdown package is not installed. Please restart Blender after enabling this addon.")
            return {"CANCELLED"}

        md_path = os.path.join(os.path.dirname(__file__), "..", "..", "CORE_ArtistTools_README.md")

        if not os.path.exists(md_path):
            return {"CANCELLED"}

        with open(md_path, "r", encoding="utf-8") as f:
            md_content = f.read()

        # Embed images as base64 data URIs
        md_content = CORE_OT_open_docs.embed_images_in_markdown(md_content, md_path)

        # Generate JavaScript for anchor navigation if anchor is provided
        anchor_script = ""
        if anchor:
            anchor_script = f"""
                <script>
                    // Jump to anchor when page loads
                    window.onload = function() {{
                        console.log('Page loaded, looking for anchor: {anchor}');
                        
                        // Wait a bit for the page to fully render
                        setTimeout(function() {{
                            if ('{anchor}') {{
                                console.log('Searching for anchor: #{anchor}');
                                
                                // Try to find the anchor element
                                var anchorElement = document.querySelector('#{anchor}');
                                console.log('Found anchor element:', anchorElement);
                                
                                if (anchorElement) {{
                                    console.log('Scrolling to anchor element');
                                    // Scroll to the element
                                    anchorElement.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                                }} else {{
                                    console.log('Anchor element not found, trying hash navigation');
                                    // Fallback: try setting the hash directly
                                    window.location.hash = '#{anchor}';
                                }}
                            }} else {{
                                console.log('No anchor specified');
                            }}
                        }}, 500);
                    }};
                </script>
            """

        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Documentation</title>
            <style>
                body {{
                    font-family: "Segoe UI", sans-serif;
                    max-width: 800px;
                    margin: 40px auto;
                    padding: 20px;
                    background: #fdfdfd;
                    color: #333;
                    line-height: 1.6;
                    text-align: left;
                }}
                h1, h2, h3 {{
                    color: #1a202c;
                }}
                pre {{
                    background: #f4f4f4;
                    padding: 10px;
                    overflow-x: auto;
                }}
                code {{
                    font-family: monospace;
                    background: #f0f0f0;
                    padding: 2px 4px;
                    border-radius: 4px;
                }}
                a {{
                    color: #007acc;
                }}
                ul, ol {{
                    padding-left: 1.5em;
                }}
                img {{
                    max-width: 100%;
                    height: auto;
                }}
            </style>
            {anchor_script}
        </head>
        <body>
        {markdown.markdown(md_content, extensions=['toc', 'attr_list', 'codehilite', 'fenced_code', 'md_in_html'])}
        </body>
        </html>
        """

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as temp_file:
            temp_file.write(html_template)
            html_path = f"file://{temp_file.name}"
            webbrowser.open(html_path)

        return {"FINISHED"}


class CORE_OT_open_docs_with_anchor(bpy.types.Operator):
    bl_idname = "core.open_docs_with_anchor"
    bl_label = "Open Documentation with Anchor"
    bl_description = "Open the documentation for CORE Tools with a specific anchor"
    bl_options = {"REGISTER", "UNDO"}

    anchor: bpy.props.StringProperty(
        name="Anchor", description="The anchor to jump to in the documentation", default=""
    )

    def execute(self, context):
        """Open documentation with a specific anchor"""
        return CORE_OT_open_docs.generate_and_open_docs(anchor=self.anchor)


class CORE_PT_documentation(ASSET_panel_common, bpy.types.Panel):
    bl_idname = "CORE_PT_Documentation"
    bl_label = "Learning"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CORE"
    # workflows = ['ALL', 'MUJOCO']

    def draw(self, context):
        layout = self.layout  # noqa F841
        col1 = self.layout.column(align=True)
        box = col1.box()
        col2 = box.column(align=True)

        op = col2.operator("core.open_docs", icon="FILE_TEXT")  # noqa F841
