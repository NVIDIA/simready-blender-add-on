# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy

keys = []


def register_keymap():

    wm = bpy.context.window_manager
    addon_keyconfig = wm.keyconfigs.addon
    kc = addon_keyconfig

    km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
    kmi = km.keymap_items.new("wm.call_menu", "H", "PRESS", ctrl=True, shift=True)
    kmi.properties.name = "SRAT_MT_Main_Menu"
    keys.append((km, kmi))


def unregister_keymap():

    for km, kmi in keys:
        km.keymap_items.remove(kmi)

    keys.clear()
