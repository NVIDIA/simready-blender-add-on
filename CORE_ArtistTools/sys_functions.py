# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import importlib
import importlib.metadata
import importlib.util
import os
import site
import subprocess
import sys

# Flag to track if we need to show restart warning
_restart_warning_needed = False

user_site = site.getusersitepackages()
if user_site not in sys.path:
    sys.path.append(user_site)

python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
potential_user_site = os.path.join(
    os.path.expanduser("~"), "AppData", "Roaming", "Python", f"Python{python_version.replace('.', '')}", "site-packages"
)
if os.path.exists(potential_user_site) and potential_user_site not in sys.path:
    sys.path.append(potential_user_site)

REQUIRED_PACKAGES = [
    "PySide6",
    "pillow",
    "pypng",
    "torch",
    "torchvision",
    "transformers",
    "requests",
    "urllib3",
    "charset_normalizer",
    "markdown",
    "typing_extensions",
]


def is_package_installed(package):
    """Check if a package is installed in Blender's Python environment.

    This function tries multiple methods to reliably detect installed packages:
    1. Using importlib.metadata (Python 3.8+)
    2. Trying to import the package directly
    3. Falling back to importlib.util.find_spec
    """
    # Method 1: Using importlib.metadata (most reliable for installed packages)
    try:
        importlib.metadata.distribution(package)
        return True
    except (importlib.metadata.PackageNotFoundError, ModuleNotFoundError):
        pass

    # Method 2: Try importing the package directly
    try:
        __import__(package)
        return True
    except ImportError:
        pass

    # Method 3: Fall back to importlib.util.find_spec
    return importlib.util.find_spec(package) is not None


def is_blender_in_standard_path():
    """Check if Blender is installed in a standard Windows path.

    Returns:
        tuple: (is_standard, blender_path, reason)
    """
    blender_exe = sys.executable
    blender_path = os.path.dirname(blender_exe)

    # Standard paths to check
    standard_paths = [
        "C:\\Program Files\\Blender Foundation",
        "C:\\Program Files (x86)\\Blender Foundation",
    ]

    # Check if Blender is in a standard path
    for standard_path in standard_paths:
        if blender_path.upper().startswith(standard_path.upper()):
            return (True, blender_path, "Standard installation path")

    # Check if it's in a portable/custom location
    return (False, blender_path, "Non-standard installation path detected")


def check_installation_safety():
    """Check if pip installations could potentially overwrite Blender's libraries.

    Returns:
        tuple: (is_safe, warning_message)
    """
    is_standard, blender_path, reason = is_blender_in_standard_path()

    if not is_standard:
        warning = (
            f"⚠ WARNING: Non-standard Blender installation detected!\n"
            f"   Location: {blender_path}\n"
            f"   Reason: {reason}\n"
            f"   All packages will be installed to user directory to prevent conflicts.\n"
            f"   This protects Blender's bundled libraries (like USD/pxr)."
        )
        return (False, warning)

    return (True, "Standard Blender installation - safe for installation")


def ensure_pip():
    """Ensure that pip is available in Blender's Python environment."""
    if not is_package_installed("pip"):
        print("Pip not found. Bootstrapping ensurepip...")
        subprocess.run([sys.executable, "-m", "ensurepip", "--user"], check=True)


def install_package(package):
    """Installs a package using Blender's Python environment.

    ALWAYS installs to user directory (--user flag) to prevent overwriting
    Blender's bundled libraries, especially important for non-standard installations.
    """
    print(f"Installing package: {package}...")

    # Always upgrade pip to user directory
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "--user", "pip", "setuptools", "wheel"], check=True
    )

    # Special handling for torch and torchvision - install CPU-only versions to avoid DLL issues
    # IMPORTANT: Always use --user flag to prevent overwriting Blender's libraries
    if package == "torch":
        print("Installing PyTorch CPU-only version (compatible with Blender)...")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "torch",
                "--user",  # CRITICAL: --user flag
                "--index-url",
                "https://download.pytorch.org/whl/cpu",
            ],
            check=True,
        )
    elif package == "torchvision":
        print("Installing torchvision CPU-only version (compatible with Blender)...")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "torchvision",
                "--user",  # CRITICAL: --user flag
                "--index-url",
                "https://download.pytorch.org/whl/cpu",
            ],
            check=True,
        )
    else:
        subprocess.run([sys.executable, "-m", "pip", "install", package, "--user"], check=True)


def check_and_install_dependencies():
    """Check if required packages are installed and install them if necessary.

    Returns:
        bool: True if all packages are already installed, False if packages were just installed (requires restart)
    """
    global _restart_warning_needed

    # Check installation safety
    is_safe, safety_message = check_installation_safety()
    if not is_safe:
        print("=" * 80)
        print(safety_message)
        print("=" * 80)

    ensure_pip()
    missing_packages = [pkg for pkg in REQUIRED_PACKAGES if not is_package_installed(pkg)]

    if missing_packages:
        print(f"Missing packages detected: {missing_packages}")
        print("=" * 80)
        print("INSTALLING REQUIRED PACKAGES - Please wait...")
        print("All packages will be installed to user directory:")
        print(f"  {site.getusersitepackages()}")
        print("=" * 80)

        for package in missing_packages:
            try:
                install_package(package)
            except subprocess.CalledProcessError as e:
                print(f"ERROR: Failed to install {package}: {e}")
                _restart_warning_needed = True
                return False

        # Refresh sys.path to pick up newly installed packages
        importlib.invalidate_caches()
        user_site = site.getusersitepackages()
        if user_site not in sys.path:
            sys.path.append(user_site)

        print("=" * 80)
        print("INSTALLATION COMPLETE!")
        print("Please restart Blender for changes to take effect.")
        print("=" * 80)

        _restart_warning_needed = True
        return False  # Indicate restart needed
    else:
        print("All required packages are already installed.")
        return True  # All good, no restart needed


def install_requirements():
    """Install packages listed in the requirements.txt file.

    This function reads from a local requirements.txt file and installs all
    packages with their specific versions and hashes. Uses --user flag to
    prevent overwriting Blender's bundled libraries.

    On Blender 5.1+ (Python 3.13), pip is invoked via the bundled Python 3.11.9
    so that mujoco-usd-converter's Requires-Python constraint (<3.13) is satisfied.

    Returns:
        bool: True if installation succeeded, False if there was an error
    """
    global _restart_warning_needed

    from . import python_compat  # noqa: PLC0415

    requirements_path = os.path.join(os.path.dirname(__file__), "requirements.txt")

    if not os.path.exists(requirements_path):
        print(f"requirements.txt not found at {requirements_path}.")
        return True  # Not an error, just nothing to install

    print("=" * 80)
    print(f"Installing packages from {requirements_path}...")
    print("All packages will be installed to user directory:")
    print(f"  {site.getusersitepackages()}")
    print("=" * 80)

    # Ensure the compatible Python is available before invoking pip
    if python_compat.needs_external_python():
        try:
            python_compat.ensure_external_python()
        except Exception as exc:
            print(f"ERROR: Could not prepare bundled Python 3.11.9: {exc}")
            _restart_warning_needed = True
            return False

    python_exe = python_compat.get_mjcf_python()

    try:
        # Use --user flag to install to user directory (safe for all installations)
        subprocess.run([python_exe, "-m", "pip", "install", "--user", "-r", requirements_path], check=True)

        # Refresh sys.path to pick up newly installed packages
        importlib.invalidate_caches()
        user_site = site.getusersitepackages()
        if user_site not in sys.path:
            sys.path.append(user_site)

        print("=" * 80)
        print("REQUIREMENTS.TXT INSTALLATION COMPLETE!")
        print("Please restart Blender for changes to take effect.")
        print("=" * 80)

        _restart_warning_needed = True
        return True

    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to install requirements: {e}")
        _restart_warning_needed = True
        return False


def should_show_restart_warning():
    """Check if restart warning should be shown."""
    return _restart_warning_needed


# MJCF CONVERTER


def get_scripts_directory():
    """Get the Scripts directory path for the current Python installation.

    On Blender 5.1+ (Python 3.13) the MJCF converter packages are installed
    under the Python 3.11 user directory (because mujoco-usd-converter only
    supports >=3.10,<3.13 and all pip calls are redirected to the bundled
    Python 3.11.9). We therefore hardcode the version to "3.11" in that case
    so the converter executable is found at the correct path.
    """
    from . import (  # noqa: PLC0415 -- intentional late import (avoids circular)
        python_compat,
    )

    # When running under Python 3.13 (Blender 5.1+), the converter was installed
    # via the bundled Python 3.11, so the Scripts dir is always Python311/Scripts.
    if python_compat.needs_external_python():
        user_scripts_dir = os.path.join(
            os.path.expanduser("~"),
            "AppData",
            "Roaming",
            "Python",
            "Python311",
            "Scripts",
        )
        print(f"python_compat: using Python 3.11 Scripts directory: {user_scripts_dir}")
        return user_scripts_dir

    # Method 1: Check if we're using user site-packages (most common for Blender)
    user_site = site.getusersitepackages()
    if user_site in sys.path:
        # If using user site-packages, look for user Scripts directory
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        user_scripts_dir = os.path.join(
            os.path.expanduser("~"),
            "AppData",
            "Roaming",
            "Python",
            f"Python{python_version.replace('.', '')}",
            "Scripts",
        )

        if os.path.exists(user_scripts_dir):
            print(f"Found user Scripts directory: {user_scripts_dir}")
            return user_scripts_dir

    # Method 2: Try to get from sys.executable (system installation)
    if sys.executable:
        # Get the directory containing the Python executable
        python_dir = os.path.dirname(sys.executable)
        scripts_dir = os.path.join(python_dir, "Scripts")

        if os.path.exists(scripts_dir):
            print(f"Found system Scripts directory: {scripts_dir}")
            return scripts_dir

    # Method 3: Try to find it using site module (fallback)
    try:
        # Get all site-packages directories
        site_packages = site.getsitepackages()
        for site_pkg in site_packages:
            # Go up from site-packages to find Scripts directory
            potential_scripts = os.path.join(os.path.dirname(site_pkg), "Scripts")
            if os.path.exists(potential_scripts):
                print(f"Found Scripts directory via site module: {potential_scripts}")
                return potential_scripts
    except Exception:
        pass

    # Method 4: Fallback to user directory
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    user_scripts_dir = os.path.join(
        os.path.expanduser("~"), "AppData", "Roaming", "Python", f"Python{python_version.replace('.', '')}", "Scripts"
    )
    print(f"Using fallback user Scripts directory: {user_scripts_dir}")
    return user_scripts_dir


def is_executable_in_path(executable_name):
    """Check if an executable is available in the system PATH."""
    print(f"DEBUG: Looking for executable: '{executable_name}'")
    print(f"DEBUG: Current PATH: {os.environ.get('PATH', 'NOT SET')[:500]}")

    try:
        result = subprocess.run([executable_name, "--help"], capture_output=True, timeout=5)
        print(f"DEBUG: Found it! Return code: {result.returncode}")
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"DEBUG: Failed with error: {type(e).__name__}: {e}")
        return False


def get_available_converter():
    """Get the name of the available USD converter executable.

    Returns:
        str: The name of the available converter executable ('mujoco_usd_converter')
        None: If converter is not available
    """
    # mujoco_usd_converter.exe should be in the user scripts directory
    user_scripts_dir = get_scripts_directory()

    # adding it to path:
    if user_scripts_dir not in os.environ["PATH"]:
        os.environ["PATH"] = user_scripts_dir + os.pathsep + os.environ["PATH"]

    if is_executable_in_path("mujoco_usd_converter"):
        return "mujoco_usd_converter"
    else:
        return None
