# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy


def SRAT_print_a_thing():
    print("hey, ho . . .I'm the ghost of STEVE BURKE :p")


def NVCAT_display_message(msg_list=[], title="CORE Artist Tools", icon="INFO"):

    lines = msg_list

    print(lines)

    def draw(self, context):

        for n in lines:
            if isinstance(n, list):
                n = ", ".join(n)

            self.layout.label(text=n)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


def NVCAT_no_sel_message():
    NVCAT_display_message(
        [
            "First make a selection, then click button.",
        ],
        title="Nothing Selected",
    )
