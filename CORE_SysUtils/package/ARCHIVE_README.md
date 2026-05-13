# SimReady Blender Addon Archive Builder

> **STATUS — historical reference only.**
> The `archive` command described below was part of the legacy `tools/python/repolib/` toolchain, which was removed when the repo migrated to NVIDIA Omniverse `repo_man` (see [`docs/REPO_TOOLS.md`](../../docs/REPO_TOOLS.md)).
> The `make_core_zip*.py` and `make_lightspeed_packages.py` scripts in this folder are still here but are not currently wired into any `repo` command. The page below is preserved as a spec — if/when archiving is reinstated, this is the behavior to recreate.
> For day-to-day add-on packaging today, use **`./repo.bat package`**, which produces individual zips under `_build/packages/`.

## Overview

The `archive` command creates distribution-ready archives for SimReady Blender addons. It generates:

1. **Individual addon zips** - Separate archives for each addon with proper naming
2. **Master 7z archive** - A compressed archive containing all addon zips

## Usage

### Basic Command

```bash
tools\bat\repo.bat archive
```

This will automatically:
- Use version `"0"` (default)
- Use current year and month
- Create archives in `_build/archives/`

**Result:** `simready-blender-addons@2025.10.0-x86x64.7z`

### Release Build with Version

For release builds, specify the version manually:

```bash
# Specify release version (e.g., from git branch release/16.1.9)
tools\bat\repo.bat archive --version 16.1.9
```

**Result:** `simready-blender-addons@2025.10.16.1.9-x86x64.7z`

### Advanced Options

```bash
# Specify custom year and month
tools\bat\repo.bat archive --year 2025 --month 8

# Combine all options for a specific release
tools\bat\repo.bat archive --version 16.1.9 --year 2025 --month 8
```

**Result:** `simready-blender-addons@2025.8.16.1.9-x86x64.7z`

## Archive Naming Convention

All archives follow this naming pattern:
```
<addon-name>@<year>.<month>.<version>-x86x64.<extension>
```

### Example Output

**Default build (version 0):**
- `simready-blender-coretools@2025.10.0-x86x64.zip`
- `simready-blender-physicstools@2025.10.0-x86x64.zip`
- `simready-blender-addons@2025.10.0-x86x64.7z` (master archive)

**Release build with --version 16.1.9:**
- `simready-blender-coretools@2025.10.16.1.9-x86x64.zip`
- `simready-blender-physicstools@2025.10.16.1.9-x86x64.zip`
- `simready-blender-addons@2025.10.16.1.9-x86x64.7z` (master archive)

## Addon Contents

### Core Tools (`simready-blender-coretools`)
- `CORE_ArtistTools/`
- `CORE_ArtistTools_Resources/`

### Physics Tools (`simready-blender-physicstools`)
- `SR_Next_Physics_Joints/`

## Requirements

- **7-Zip**: Must be installed at one of these locations:
  - `C:\Program Files\7-Zip\7z.exe`
  - `C:\Program Files (x86)\7-Zip\7z.exe`
  - Or available in system PATH

Download 7-Zip from: https://www.7-zip.org/

## Output Location

Archives are created in:
```
<repo-root>/_build/archives/
```

The directory is cleaned before each build.

## Integration with Build Pipeline

### GitLab CI Example

This command can be integrated into CI/CD pipelines:

```yaml
job-archive:
  artifacts:
    paths:
      - _build/archives/*
  needs:
    - job: job-0-setup
      artifacts: true
  rules:
    - !reference [.rules-workflow, rules]
  script:
    # Extract version from branch name (e.g., release/16.1.9)
    - |
      $branch = git rev-parse --abbrev-ref HEAD
      if ($branch -match 'release/(\d+\.\d+\.\d+)') {
        $version = $matches[1]
        ./tools/bat/repo.bat archive --version $version
      } else {
        ./tools/bat/repo.bat archive
      }
  stage: build
  tags:
    - os/windows
```

Or use manual version tagging:

```bash
# Example: GitLab CI with explicit version
repo.bat archive --version 16.1.9 --year 2025 --month 10
```

## Differences from Legacy Scripts

The new `archive` command replaces the old manual scripts:
- `CORE_SysUtils/package/make_core_zip.py` ❌ (legacy)
- `CORE_SysUtils/package/make_sr_physics_zip.py` ❌ (legacy)

**Advantages:**
- ✅ Consistent naming convention
- ✅ Automatic version extraction
- ✅ Creates master 7z archive
- ✅ Integrated with repo build system
- ✅ Configurable via command-line arguments

## Version Management

### Default Behavior

By default, the version is set to `"0"`. This allows for flexible version control:

```bash
# Default version "0"
tools\bat\repo.bat archive
# Creates: simready-blender-addons@2025.10.0-x86x64.7z
```

### Release Versioning

For releases, manually specify the version based on your release branch:

```bash
# Release version (e.g., from git branch release/16.1.9)
tools\bat\repo.bat archive --version 16.1.9
# Creates: simready-blender-addons@2025.10.16.1.9-x86x64.7z
```

### Why Not Auto-Extract from Addon?

Version numbers are now managed independently from the addon's `bl_info` to allow:
- **Manual control** over release versioning
- **Git branch-based** version tracking (e.g., `release/16.1.9`)
- **Flexibility** for hotfix numbering outside of addon version bumps
- **CI/CD integration** with external version management systems

