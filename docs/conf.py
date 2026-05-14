# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
_repo_root = _root.parent

# Make the local docs/_ext/ folder importable for myst_heading_slug_func.
sys.path.insert(0, str(_root))

# -- Project information -----------------------------------------------------

project = "SimReady Blender Add-on"
copyright = "2026, NVIDIA Corporation"
author = "NVIDIA"

_version_file = _repo_root / "VERSION.md"
version = _version_file.read_text().strip() if _version_file.exists() else "0.0.0"
release = version

# -- General configuration ---------------------------------------------------

extensions = [
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinx.ext.githubpages",
]

suppress_warnings = [
    "myst.role_unknown",
    "myst.directive_unknown",
]

exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    # FAQ helper videos are tracked via Git LFS and total ~3 GB. They are
    # not referenced from any rendered page, and individual files exceed
    # the GitHub Pages 100 MB per-file limit, so they must never be
    # included in the published site.
    "faq_helpers/**",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = "index"

# -- MyST configuration ------------------------------------------------------

myst_enable_extensions = [
    "colon_fence",
    "substitution",
    "deflist",
    # Enables ![alt](src){w=800px} attribute syntax on inline images so we
    # can carry image widths over from the previous raw <img> tags.
    "attrs_inline",
]

# Auto-generate anchor IDs for headings up to H4. Several existing TOCs
# in our docs link to H4 sub-sections (e.g. "DCC Blender -> SimReady",
# "Apply Physics Materials - FET_003 and FET_004"); without anchors at
# this depth those links 404.
myst_heading_anchors = 4

# The existing TOCs in our docs were authored against github.com's slug
# algorithm (which preserves hyphen-runs from things like "A -> B"). Use a
# matching slug function here so anchors resolve in both places. Passed as
# a string so Sphinx can cache the config.
myst_heading_slug_func = "_ext.github_slug.slug"

# -- HTML output -------------------------------------------------------------

html_theme = "nvidia_sphinx_theme"
html_baseurl = "https://nvidia.github.io/simready-blender-add-on/"

html_theme_options = {
    "secondary_sidebar_items": ["page-toc"],
    "copyright_override": {"start": 2024},
    "pygments_light_style": "tango",
    "pygments_dark_style": "monokai",
    "navigation_depth": 2,
}

html_title = f"{project} v{version}"

html_static_path = ["_static"]

html_show_sourcelink = False

# -- Sphinx-copybutton -------------------------------------------------------

copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True
