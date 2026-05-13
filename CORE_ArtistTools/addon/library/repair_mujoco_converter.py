# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
"""
Repair/reinstall the MuJoCo USD Converter from within Blender.
This module provides functions to diagnose and fix converter installation issues.
"""

import site
import subprocess
import sys


def _get_python() -> str:
    """Return the Python executable to use for MJCF-related subprocess calls.

    On Blender 5.1+ (Python 3.13) this returns the bundled Python 3.11.9 path
    because mujoco-usd-converter only supports Python >=3.10,<3.13.
    On earlier Blender versions it returns sys.executable unchanged.
    """
    try:
        from ... import python_compat

        return python_compat.get_mjcf_python()
    except Exception:
        return sys.executable


def get_user_site_packages():
    """Get the user site-packages directory."""
    return site.getusersitepackages()


def get_user_scripts_directory():
    """Get the user Scripts directory where executables are installed."""
    user_site = get_user_site_packages()
    # Replace site-packages with Scripts
    return user_site.replace("site-packages", "Scripts")


def uninstall_package(package_name):
    """Uninstall a package using pip.

    Args:
        package_name (str): Name of the package to uninstall

    Returns:
        tuple: (success, message)
    """
    try:
        print(f"Uninstalling {package_name}...")
        result = subprocess.run(
            [_get_python(), "-m", "pip", "uninstall", "-y", package_name], capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return (True, f"Successfully uninstalled {package_name}")
        else:
            # Package might not be installed, which is fine
            return (True, f"{package_name} was not installed or already removed")
    except Exception as e:
        return (False, f"Error uninstalling {package_name}: {e}")


def clean_pip_cache():
    """Clean the pip cache.

    Returns:
        tuple: (success, message)
    """
    try:
        print("Cleaning pip cache...")
        result = subprocess.run(
            [_get_python(), "-m", "pip", "cache", "purge"], capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return (True, "Pip cache cleaned successfully")
        else:
            return (False, f"Failed to clean pip cache: {result.stderr}")
    except Exception as e:
        return (False, f"Error cleaning pip cache: {e}")


def upgrade_pip():
    """Upgrade pip, setuptools, and wheel.

    Returns:
        tuple: (success, message)
    """
    try:
        print("Upgrading pip, setuptools, and wheel...")
        result = subprocess.run(
            [_get_python(), "-m", "pip", "install", "--upgrade", "--user", "pip", "setuptools", "wheel"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return (True, "Pip upgraded successfully")
        else:
            return (False, f"Failed to upgrade pip: {result.stderr}")
    except Exception as e:
        return (False, f"Error upgrading pip: {e}")


def install_from_requirements(requirements_path):
    """Install packages from requirements.txt.

    Args:
        requirements_path (str): Path to requirements.txt file

    Returns:
        tuple: (success, message)
    """
    try:
        print(f"Installing from {requirements_path}...")
        result = subprocess.run(
            [_get_python(), "-m", "pip", "install", "--user", "-r", requirements_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            return (True, "Packages installed successfully")
        else:
            return (False, f"Failed to install packages: {result.stderr}")
    except Exception as e:
        return (False, f"Error installing packages: {e}")


def install_package(package_name):
    """Install a single package.

    Args:
        package_name (str): Name of the package to install

    Returns:
        tuple: (success, message)
    """
    try:
        print(f"Installing {package_name}...")
        result = subprocess.run(
            [_get_python(), "-m", "pip", "install", "--user", package_name], capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            return (True, f"Successfully installed {package_name}")
        else:
            return (False, f"Failed to install {package_name}: {result.stderr}")
    except Exception as e:
        return (False, f"Error installing {package_name}: {e}")


def verify_import(module_name):
    """Verify that a module can be imported.

    Args:
        module_name (str): Name of the module to import

    Returns:
        tuple: (success, message)
    """
    try:
        result = subprocess.run(
            [_get_python(), "-c", f"import {module_name}; print('SUCCESS')"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and "SUCCESS" in result.stdout:
            return (True, f"Successfully imported {module_name}")
        else:
            return (False, f"Failed to import {module_name}: {result.stderr}")
    except Exception as e:
        return (False, f"Error testing import of {module_name}: {e}")


def check_executable_exists(executable_name):
    """Check if an executable exists in the user Scripts directory.

    Args:
        executable_name (str): Name of the executable (e.g., 'mujoco_usd_converter.exe')

    Returns:
        tuple: (exists, path)
    """
    import os

    scripts_dir = get_user_scripts_directory()
    exe_path = os.path.join(scripts_dir, executable_name)
    return (os.path.exists(exe_path), exe_path)


def repair_mujoco_converter(log_callback=None):
    """Complete repair process for the MuJoCo USD Converter.

    Args:
        log_callback (callable, optional): Function to call with log messages

    Returns:
        tuple: (success, detailed_report)
    """
    import os

    def log(message):
        """Helper to log messages."""
        print(message)
        if log_callback:
            log_callback(message)

    report = []
    overall_success = True

    log("=" * 60)
    log("MuJoCo USD Converter Repair Process")
    log("=" * 60)
    log("")

    # Step 1: Uninstall existing packages
    log("Step 1: Uninstalling existing packages...")
    for package in ["mujoco-usd-converter", "usd-exchange", "mujoco"]:
        success, msg = uninstall_package(package)
        log(f"  {msg}")
        report.append((package, "uninstall", success, msg))
    log("")

    # Step 2: Clean pip cache
    log("Step 2: Cleaning pip cache...")
    success, msg = clean_pip_cache()
    log(f"  {msg}")
    report.append(("pip-cache", "clean", success, msg))
    log("")

    # Step 3: Upgrade pip
    log("Step 3: Upgrading pip...")
    success, msg = upgrade_pip()
    log(f"  {msg}")
    report.append(("pip", "upgrade", success, msg))
    if not success:
        overall_success = False
    log("")

    # Step 4: Install packages
    log("Step 4: Installing packages...")

    # Try to find requirements.txt
    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    requirements_path = os.path.join(addon_dir, "requirements.txt")

    if os.path.exists(requirements_path):
        log(f"  Using requirements.txt: {requirements_path}")
        success, msg = install_from_requirements(requirements_path)
        log(f"  {msg}")
        report.append(("requirements.txt", "install", success, msg))
        if not success:
            overall_success = False
    else:
        log("  requirements.txt not found, installing individual package...")
        success, msg = install_package("mujoco-usd-converter")
        log(f"  {msg}")
        report.append(("mujoco-usd-converter", "install", success, msg))
        if not success:
            overall_success = False
    log("")

    # Step 5: Verify installation
    log("Step 5: Verifying installation...")

    for module in ["mujoco_usd_converter", "usdex.core", "mujoco"]:
        success, msg = verify_import(module)
        log(f"  {msg}")
        report.append((module, "verify", success, msg))
        if not success and module == "mujoco_usd_converter":
            overall_success = False
    log("")

    # Step 6: Check executable
    log("Step 6: Checking converter executable...")
    exists, exe_path = check_executable_exists("mujoco_usd_converter.exe")
    if exists:
        log(f"  SUCCESS: Found mujoco_usd_converter.exe at {exe_path}")
        report.append(("executable", "check", True, f"Found at {exe_path}"))
    else:
        log(f"  WARNING: mujoco_usd_converter.exe not found at {exe_path}")
        report.append(("executable", "check", False, f"Not found at {exe_path}"))
    log("")

    log("=" * 60)
    if overall_success:
        log("Repair completed successfully!")
        log("Please restart Blender for changes to take effect.")
    else:
        log("Repair completed with some errors.")
        log("Please check the messages above for details.")
    log("=" * 60)

    return (overall_success, report)


if __name__ == "__main__":
    # When run directly, execute the repair
    success, report = repair_mujoco_converter()
    sys.exit(0 if success else 1)
