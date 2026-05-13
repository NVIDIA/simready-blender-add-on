# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


class ValidationContext:
    """Simple context to replace pyblish context"""

    def __init__(self):
        self.data = {}
        self._instances = []

    def add(self, instance):
        """Add an instance to this context"""
        self._instances.append(instance)

    def __iter__(self):
        """Make context iterable over its instances"""
        return iter(self._instances)


class ValidationInstance:
    """Simple instance to replace pyblish instance"""

    def __init__(self, name, family):
        self.name = name
        self.data = {"family": family}
        self._objects = []

    def add(self, obj):
        """Add an object to this instance"""
        self._objects.append(obj)

    def copy_data_from(self, other_instance, keys_to_copy=None):
        """Copy data from another instance, optionally filtering by keys"""
        if keys_to_copy is None:
            for key, value in other_instance.data.items():
                if key != "family":
                    self.data[key] = value
        else:
            for key in keys_to_copy:
                if key in other_instance.data:
                    self.data[key] = other_instance.data[key]

    def __iter__(self):
        """Make instance iterable"""
        return iter(self._objects)
