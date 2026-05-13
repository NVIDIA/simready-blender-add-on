# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""
Python compatibility shim for Blender 5.1+ (Python 3.13).

mujoco-usd-converter and usd-exchange only support Python >=3.10,<3.13.
Blender 5.1 ships Python 3.13, which falls outside that range.

This module ships a bundled Python 3.11.9 embeddable distribution alongside
the addon. When Blender's Python is 3.13+, all MJCF converter subprocess calls
are redirected to the bundled Python 3.11.9 instead of sys.executable.

The --user install scheme is preserved: packages install to
%APPDATA%/Roaming/Python/Python311/site-packages, which is the same location
used when running Blender 5.0 (also Python 3.11). So any packages the user
already installed under Blender 5.0 are immediately reusable here.
"""

import os
import subprocess
import sys
import zipfile

# Directory containing this file (CORE_ArtistTools/)
_ADDON_DIR = os.path.dirname(os.path.abspath(__file__))

# Directory where the bundled zip and get-pip.py live
_PYTHON_BUNDLE_DIR = os.path.join(_ADDON_DIR, "python")

# Where the embeddable Python will be extracted to
_PYTHON_EXTRACTED_DIR = os.path.join(_PYTHON_BUNDLE_DIR, "python-3.11.9")

# Sentinel file that confirms setup is complete
_SETUP_MARKER = os.path.join(_PYTHON_EXTRACTED_DIR, ".setup_complete")


def needs_external_python() -> bool:
    """Return True when Blender's Python is outside mujoco-usd-converter's supported range.

    mujoco-usd-converter declares Requires-Python: >=3.10,<3.13.
    Blender 5.1 ships Python 3.13, which falls outside that range.
    """
    return sys.version_info >= (3, 13)


def get_external_python_exe() -> str:
    """Return the path to the bundled Python 3.11.9 executable."""
    return os.path.join(_PYTHON_EXTRACTED_DIR, "python.exe")


def _configure_pth_file(extracted_dir: str) -> None:
    """Enable user site-packages in the embeddable Python layout.

    The embeddable zip ships with python311._pth that has 'import site'
    commented out, which disables --user installs and site-packages entirely.
    We uncomment that line so pip --user works correctly.
    """
    pth_candidates = [f for f in os.listdir(extracted_dir) if f.endswith("._pth")]
    for pth_name in pth_candidates:
        pth_path = os.path.join(extracted_dir, pth_name)
        with open(pth_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        new_content = content.replace("#import site", "import site")
        if new_content != content:
            with open(pth_path, "w", encoding="utf-8") as fh:
                fh.write(new_content)
            print(f"python_compat: enabled site-packages in {pth_name}")


def _bootstrap_pip(extracted_dir: str) -> None:
    """Install pip into the embeddable Python using the bundled get-pip.py."""
    get_pip_path = os.path.join(_PYTHON_BUNDLE_DIR, "get-pip.py")
    if not os.path.exists(get_pip_path):
        raise FileNotFoundError(
            f"python_compat: get-pip.py not found at {get_pip_path}. " "The addon bundle may be incomplete."
        )

    python_exe = os.path.join(extracted_dir, "python.exe")
    print("python_compat: bootstrapping pip for bundled Python 3.11.9...")
    result = subprocess.run(
        [python_exe, get_pip_path, "--user"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        print(f"python_compat: pip bootstrap stdout: {result.stdout}")
        print(f"python_compat: pip bootstrap stderr: {result.stderr}")
        raise RuntimeError(f"python_compat: failed to bootstrap pip (exit {result.returncode})")
    print("python_compat: pip bootstrapped successfully.")


def ensure_external_python() -> str:
    """Extract, configure, and pip-bootstrap the bundled Python 3.11.9 (idempotent).

    On subsequent calls, the setup marker file is found and the function
    returns immediately.

    Returns:
        str: Path to the python.exe inside the extracted distribution.

    Raises:
        FileNotFoundError: If the bundled zip is missing.
        RuntimeError: If any setup step fails.
    """
    if os.path.exists(_SETUP_MARKER):
        return get_external_python_exe()

    zip_path = os.path.join(_PYTHON_BUNDLE_DIR, "python-3.11.9-embed-amd64.zip")
    if not os.path.exists(zip_path):
        raise FileNotFoundError(
            f"python_compat: bundled Python zip not found at {zip_path}. " "The addon bundle may be incomplete."
        )

    print(f"python_compat: extracting {zip_path} -> {_PYTHON_EXTRACTED_DIR}")
    os.makedirs(_PYTHON_EXTRACTED_DIR, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(_PYTHON_EXTRACTED_DIR)

    _configure_pth_file(_PYTHON_EXTRACTED_DIR)
    _bootstrap_pip(_PYTHON_EXTRACTED_DIR)

    # Write marker so we skip all this on next call
    with open(_SETUP_MARKER, "w") as fh:
        fh.write("setup complete\n")

    return get_external_python_exe()


def get_mjcf_python() -> str:
    """Return the Python executable to use for MJCF converter subprocesses.

    - Blender <=5.0 (Python <=3.12): returns sys.executable (no change)
    - Blender 5.1+ (Python 3.13+): extracts + returns bundled Python 3.11.9
    """
    if not needs_external_python():
        return sys.executable
    return ensure_external_python()


def get_mjcf_scripts_dir() -> str:
    """Return the user Scripts directory where mujoco_usd_converter.exe is installed.

    When using bundled Python 3.11.9 (Blender 5.1+), the --user install target
    is %APPDATA%/Roaming/Python/Python311/Scripts -- the same path that Blender
    5.0 (also Python 3.11) would use, so already-installed converters are found.

    When using Blender's own Python (<=3.12), delegates to the existing
    get_scripts_directory() logic in sys_functions.py.
    """
    if not needs_external_python():
        # Let sys_functions handle it for the non-3.13 case
        from . import sys_functions

        return sys_functions.get_scripts_directory()

    # For Python 3.13 callers: force resolution to the Python 3.11 user Scripts dir
    user_scripts = os.path.join(
        os.path.expanduser("~"),
        "AppData",
        "Roaming",
        "Python",
        "Python311",
        "Scripts",
    )
    return user_scripts
