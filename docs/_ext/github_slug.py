# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""GitHub-flavored heading slug function for MyST-Parser.

Used by ``myst_heading_slug_func`` in ``conf.py`` so that the anchor IDs
Sphinx generates for headings match what github.com would generate for the
same headings. The existing tables of contents in ``Blender_End_to_End.md``
and ``Blender_CORE_Addon_reference.md`` were authored against github.com's
slugger; without this, ~13 in-page links resolve on github.com but break
on the Pages-rendered site.

Algorithm (from the reverse-engineered GitHub spec at
https://gist.github.com/creachadair/e35cefd8e3fbdfe3cce4f6178da1cd70):

1. Lowercase the heading text.
2. Partition the string into "words" (runs of letters, digits, hyphens,
   and underscores: ``[-\\w]+``) separated by runs of "space-or-punct"
   (everything that is not a word character).
3. Drop any leading and trailing space-or-punct runs.
4. Replace each remaining separator run with:
   - a single hyphen if it contains any space or tab character, or
   - the empty string otherwise (e.g. a bare ``/``, ``(``, ``)``).
5. Join the words and replaced separators back together.

This module is referenced as a string (``_ext.github_slug.slug``) so that
Sphinx can cache the configuration; passing the function object directly
defeats Sphinx's ``unpicklable_config`` cache.
"""
from __future__ import annotations

import re

# Words: any run of letters, digits, hyphens, or underscores.
_WORD_RE = re.compile(r"[-\w]+", re.UNICODE)
# Detect whether a separator run contains any whitespace.
_HAS_SPACE_RE = re.compile(r"[ \t]")


def slug(text: str) -> str:
    text = text.lower()
    pieces: list[str] = []
    pos = 0
    last_end = 0
    for m in _WORD_RE.finditer(text):
        sep = text[last_end:m.start()]
        if pieces:  # don't emit a leading separator
            if _HAS_SPACE_RE.search(sep):
                pieces.append("-")
        pieces.append(m.group(0))
        last_end = m.end()
    return "".join(pieces)
