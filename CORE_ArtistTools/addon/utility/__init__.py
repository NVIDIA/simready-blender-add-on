# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import bpy  # noqa F401

"""
from .user_messages import ShowMessageBox



classes = (
    ShowMessageBox,
   
)


def register_ui():
    from bpy.utils import register_class
    for cls in classes:
        try:
            register_class(cls)
        except ValueError as e:
            if "already registered" in str(e):
                print(f"Warning: Class {cls.__name__} was already registered, skipping...")
            else:
                raise e


def unregister_ui():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
"""
from .user_messages import *  # noqa: E402, F403
