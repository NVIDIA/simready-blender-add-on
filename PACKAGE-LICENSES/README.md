# Third-Party Package Licenses

This directory contains license notices for the third-party software that
the SimReady Blender add-ons either install at runtime or bundle verbatim
inside this repository:

- **Runtime-installed packages** are downloaded from PyPI (or the PyTorch
  CPU wheel index) into Blender's user `site-packages` the first time the
  add-on starts. They are **not redistributed inside this repository**.
- **Bundled components** physically ship in this repository (and in the
  public GitHub mirror) under `CORE_ArtistTools/python/`. Top-level
  attribution for these artifacts is also surfaced in the root
  [`NOTICE`](../NOTICE) file, as required by Apache 2.0 Section 4(d).

The notices below satisfy the attribution requirements of the upstream
licenses regardless of where the code is fetched from.

Each `<package>-LICENSE.txt` file follows the same layout:

1. Package title
2. Copyright holder(s)
3. License body (or summary, for very short permissive licenses)
4. `Source:` upstream repository / PyPI page
5. `License:` SPDX identifier (or closest equivalent)
6. Optional note explaining how the package is used in this repo

## How the package list is derived

The set of packages tracked here is the union of three places in the repo:

| Source file | Purpose |
| --- | --- |
| `CORE_ArtistTools/package_checksums.json` | Pinned wheel checksums for packages downloaded by the installer. |
| `CORE_ArtistTools/requirements.txt` | Hash-pinned requirements for the MJCF-to-USD pipeline (installed under the bundled Python 3.11 user site on Blender 5.1+). |
| `CORE_ArtistTools/sys_functions.py` (`REQUIRED_PACKAGES`) | Direct dependencies installed into Blender's Python user site by the add-on bootstrapper. |

Transitive dependencies pulled in via `requirements.txt` are also covered so
that license attribution is complete for the wheels physically installed on
disk.

## Package index

### Bundled in this repository

These artifacts physically ship in the repo under `CORE_ArtistTools/python/`
(LFS-tracked) and reach the public GitHub mirror, so a top-level
[`NOTICE`](../NOTICE) plus the entries below provide the required
attribution. They are not pinned in `requirements.txt` /
`package_checksums.json` / `REQUIRED_PACKAGES`; versions are pinned
statically in `tools/scripts/regenerate_package_licenses.py` under
`bundled=True`.

| Package | License | File | Bundled as |
| --- | --- | --- | --- |
| python (CPython 3.11.9 Windows embed) | PSF-2.0 | `python-LICENSE.txt` | `CORE_ArtistTools/python/python-3.11.9-embed-amd64.zip` |
| get-pip | MIT | `get-pip-LICENSE.txt` | `CORE_ArtistTools/python/get-pip.py` |
| pip 26.0.1 | MIT | `pip-LICENSE.txt` | embedded inside `CORE_ArtistTools/python/get-pip.py` |

### Direct dependencies (CORE_ArtistTools REQUIRED_PACKAGES)

| Package | License | File |
| --- | --- | --- |
| PySide6 | LGPL-3.0-only | `PySide6-LICENSE.txt` |
| pillow | HPND | `pillow-LICENSE.txt` |
| pypng | MIT | `pypng-LICENSE.txt` |
| torch | BSD-3-Clause | `torch-LICENSE.txt` |
| torchvision | BSD-3-Clause | `torchvision-LICENSE.txt` |
| transformers | Apache-2.0 | `transformers-LICENSE.txt` |
| requests | Apache-2.0 | `requests-LICENSE.txt` |
| urllib3 | MIT | `urllib3-LICENSE.txt` |
| charset_normalizer | MIT | `charset_normalizer-LICENSE.txt` |
| markdown | BSD-3-Clause | `markdown-LICENSE.txt` |
| typing-extensions | PSF-2.0 | `typing-extensions-LICENSE.txt` |

### MJCF-to-USD pipeline (`CORE_ArtistTools/requirements.txt`)

| Package | License | File |
| --- | --- | --- |
| mujoco-usd-converter | Apache-2.0 | `mujoco-usd-converter-LICENSE.txt` |
| mujoco | Apache-2.0 | `mujoco-LICENSE.txt` |
| usd-exchange | Apache-2.0 | `usd-exchange-LICENSE.txt` |
| absl-py | Apache-2.0 | `absl-py-LICENSE.txt` |
| etils | Apache-2.0 | `etils-LICENSE.txt` |
| fsspec | BSD-3-Clause | `fsspec-LICENSE.txt` |
| numpy-stl | BSD-3-Clause | `numpy-stl-LICENSE.txt` |
| numpy | BSD-3-Clause | `numpy-LICENSE.txt` |
| pyopengl | BSD-3-Clause-like (PyOpenGL) | `pyopengl-LICENSE.txt` |
| tinyobjloader | MIT | `tinyobjloader-LICENSE.txt` |
| zipp | MIT | `zipp-LICENSE.txt` |
| importlib_resources | Apache-2.0 | `importlib_resources-LICENSE.txt` |
| glfw | MIT (Python bindings) / zlib (native lib) | `glfw-LICENSE.txt` |
| python-utils | BSD-3-Clause | `python-utils-LICENSE.txt` |

## Regenerating these files

This folder is **machine-maintained** by
`tools/scripts/regenerate_package_licenses.py`. Do not edit `*-LICENSE.txt`
by hand -- your changes will be overwritten the next time someone runs the
regenerator. Edit the script's `PACKAGES` map instead.

The regenerator collects verbatim upstream license text using the following
strategies, in order, per package:

1. Read `LICENSE` / `NOTICE` out of an installed wheel's
   `<name>-<ver>.dist-info/` directory on disk (most authoritative -- it is
   the file the maintainer published on PyPI).
2. Fetch `LICENSE` / `NOTICE` from a curated URL map pinned to the project's
   forge (GitHub, GitLab, etc.) at the version declared in
   `requirements.txt` / `package_checksums.json`.
3. If both strategies fail, keep the previous file body and stamp
   `[STATUS: STALE]` in the footer so reviewers know it was not refreshed.

Every file ends with a deterministic footer of the form:

```
Source: <upstream URL>
License: <SPDX>
Pinned version: <version-or-"(unpinned)">
Text provenance: installed wheel (...) | network: <url> | kept previous body | placeholder
[STATUS: VERBATIM-WHEEL | VERBATIM-NETWORK | STALE]
Note: <optional>
```

### Usage

```powershell
# Refresh everything (best results when the addon's dependencies are installed locally).
tools\scripts\regenerate_package_licenses.bat

# Refresh a single package.
tools\scripts\regenerate_package_licenses.bat --package numpy

# CI guard: exits non-zero if any file would change.
tools\scripts\regenerate_package_licenses.bat --check

# Offline (no internet): only use installed wheels.
tools\scripts\regenerate_package_licenses.bat --no-network
```

On Linux/macOS use `tools/scripts/regenerate_package_licenses.sh` (same flags).

### When you add or remove a package

When you add or pin a new package in `package_checksums.json`,
`requirements.txt`, or `sys_functions.REQUIRED_PACKAGES`:

1. Add a matching `PackageSpec(...)` entry to the `PACKAGES` dict in
   `tools/scripts/regenerate_package_licenses.py`. The minimum fields are
   `name`, `spdx`, `source_url`, and at least one `license_urls` entry.
2. Run `tools\scripts\regenerate_package_licenses.bat` once to write
   `PACKAGE-LICENSES/<package>-LICENSE.txt`.
3. Update the package index table above.

When you remove a package, delete its license file, its `PACKAGES` entry,
and its table row so that the notices stay accurate.

The regenerator emits a warning (and a non-zero exit code) if it sees a
package declared in `requirements.txt`/`package_checksums.json`/`REQUIRED_PACKAGES`
that has no `PackageSpec` entry, so step 1 above is hard to miss.
