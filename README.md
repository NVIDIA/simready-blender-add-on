# CORE Artist Tools

## Introduction

CORE Artist Tools is a collection of Blender add-ons for creating SimReady Assets, tailored for Blender 5.1.

## Getting Started

For all docs to get you started, please read the [SimReady Blender Addon Landing Page](Docs/simready-blender-addon-landing.md).


### Prerequisites

- Blender 5.1 installed on your machine.

### Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd simready-blender-addons
   ```

2. **Build the add-on package**

   ```bash
   python CORE_SysUtils/package/make_core_zip.py
   ```

   Output: `SimReady_Blender_CORE_<version>.zip` in the repo root (version is read from [`VERSION.md`](VERSION.md)).

3.  **Alternative - Download addon directly**

      - [Latest release](https://github.com/NVIDIA/simready-blender-add-on/releases/tag/Latest)

4. **Install in Blender**

   - Open Blender → `Edit` → `Preferences` → `Install...`
   - Select `SimReady_Blender_CORE_<version>.zip` from the repo root.

## Project structure

```
simready-blender-addons/
├── CORE_ArtistTools/             # Main Blender add-on 
├── CORE_ArtistTools_Resources/   # Companion resources 
├── CORE_SysUtils/                # Build/utility scripts used by repo
├── Docs/                         # e2e User Guides, landing doc
```

## License

This project is licensed under the **Apache License 2.0** — see the [LICENSE](LICENSE) file for details.

```text
SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
SPDX-License-Identifier: Apache-2.0
```
