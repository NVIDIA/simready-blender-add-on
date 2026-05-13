# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

# name checking functions

import re

import bpy


def ValidateNames(objs, test):
    """
    objs: a single object or an iterable collection of objects to validate
    test: string value to determine which validation test is run
          (only a single test can be run at one time)

            'veh_parts': check fitness of incoming object names for vehicle parts
            'veh_mats': check the materials names assigned to parts for fitness for vehicles
            'mats': check material names for compliance w/ material segmentation requirements
    """

    C = bpy.context  # noqa F841
    D = bpy.data  # noqa F841
    objs = C.selected_objects  # noqa F841

    # STEP ONE
    # Set up variables and known names
    known_veh_parts = (
        "body",
        "grill",
        "hood",
        "trunk",
        "undercarriage",
        "interior",
        "door_0",
        "door_1",
        "door_2",
        "door_3",
        "door_trunk",
        "door_hood",
        "door_sunroof",
        "glass",
        "glass_0",
        "glass_1",
        "glass_2",
        "glass_3",
        "lights",
        "lights_0",
        "lights_1",
        "lights_trunk",
        "brake_0",
        "brake_1",
        "brake_2",
        "brake_3",
        "wheel_0",
        "wheel_1",
        "wheel_2",
        "wheel_3",
        "wheel_front_0",
        "wheel_front_1",
        "wheel_rear_2",
        "wheel_rear_3",
        "wheel_all_0",
        "wheel_all_1",
        "wheel_all_2",
        "wheel_all_3",
    )

    known_veh_mats = (
        "CarPaint",
        "Textured",
        "Rubber",
        "Plastic",
        "Chrome",
        "WheelRim",
        "Tire",
        "Muffler",
        "ChromeVariable",
        "BrakeRotor",
        "InteriorRough",
        "InteriorLight",
        "InteriorMedium",
        "InteriorDark",
        "GlassTintMedium",
        "GlassTintDark",
        "GlassWhite",
        "GlassRed",
        "GlassOrange",
        "GlassClear",
        "HeadLights",
        "BrakeLights",
        "ReverseLights",
        "NightLights",
        "BlinkerLights_fl",
        "BlinkerLights_fr",
        "BlinkerLights_rl",
        "BlinkerLights_rr",
        "RunningLights_fl",
        "RunningLights_fr",
        "TailLights_rl",
        "TailLights_rr",
        "BrakeLights_BlinkerLights_rl",
        "BrakeLights_BlinkerLights_rr",
        "BrakeLights_TailLights_rl_BlinkerLights_rl",
        "BrakeLights_TailLights_rr_BlinkerLights_rr",
        "BrakeLights_TailLights_rl",
        "BrakeLights_TailLights_rr",
        "ReflectorRed",
        "ReflectorOrange",
        "ReflectorWhite",
        "FogLights",
        "HighBeamLights",
    )

    known_mat_prefixes = (
        "opaque",
        "trans",
        "thin",
        "clearcoat",
        "retro",
    )
    known_surf_prefixes = (
        "emissive",
        "glass",
        "metal",
        "paint",
        "concrete",
        "cement",
        "asphalt",
        "wood",
        "plant",
        "leaf",
        "rubber",
        "plastic",
        "viny;",
        "stone",
        "leather",
        "fabric",
        "organic",
    )

    # result array prototypes
    names_known = []
    names_unknown = []
    names_probable = []  # noqa F841
    names_bad = []
    names_sim = []
    names_ref = ()
    mat_names_found = []
    resultstring = []  # noqa F841

    # STEP TWO.
    # Add test names to array
    if test == "veh_parts":
        for each in objs:
            names_unknown.append(each.name)
    else:
        for each in objs:
            if each.type == "MESH":
                mats = each.data.materials
                for mat in mats:
                    if mat and mat.name not in mat_names_found:
                        mat_names_found.append(mat.name)

        names_unknown = mat_names_found

    # STEP THREE.
    # Test names against known obj or mat names
    if test == "veh_parts":
        names_ref = known_veh_parts
    elif test == "veh_mats":
        names_ref = known_veh_mats
    else:
        pass

    if names_ref:
        count = len(names_unknown)
        if count:
            for i in reversed(range(count)):
                name = names_unknown[i]
                if name in names_ref:
                    names_known.append(name)
                    names_unknown.remove(name)
                else:
                    pass

    # STEP FOUR.
    # search for malformed names (e.g. illegal characters, uppercase, etc.)
    count = len(names_unknown)
    if count:
        for i in reversed(range(count)):
            name = names_unknown[i]
            result = re.search(r"[a-z0-9_-]+", name)
            if result and result[0] == name:
                pass
            else:
                names_bad.append(name)
                names_unknown.remove(name)

    # STEP FIVE.
    # Search for DS2 material names
    if test != "veh_parts":
        count = len(names_unknown)
        if count:
            for i in reversed(range(count)):
                name = names_unknown[i]
                nameparts = (name).split("__")
                if len(nameparts) == 3:
                    if nameparts[0] in known_mat_prefixes and nameparts[1] in known_surf_prefixes:
                        names_sim.append(name)
                        names_unknown.remove(name)
                    else:
                        names_bad.append(name)
                        names_unknown.remove(name)

    # STEP SIX.
    # More refined tests
    count = len(names_unknown)
    if count:
        for i in reversed(range(count)):
            name = names_unknown[i]
            result1 = re.search(r"[_]{2}", name)
            print(result1)
            result2 = re.search(r"[-]{2}", name)
            if result1 or result2:
                names_bad.append(name)
                names_unknown.remove(name)

    pt_known = []
    if names_known:
        pt_known = [("KNOWN:"), (names_known), "\n"]
    pt_sim = []
    if names_sim:
        pt_sim = [("SIM COMPLIANT:"), (names_sim), "\n"]
    pt_unkown = []
    if names_unknown:
        pt_unkown = [("UNKOWN:"), (names_unknown), "\n"]
    pt_bad = []
    if names_bad:
        pt_bad = [("BAD NAME:"), (names_bad), "\n"]

    rslt = pt_known + pt_sim + pt_unkown + pt_bad
    return rslt


if __name__ == "__main__":

    # CHOOSE TESTS TO ENABLE
    #############################################################################
    rslt = ValidateNames(objs, "veh_parts")  # noqa F821 # Validate Vehicle Part Names
    print("\n\n", rslt)
    rslt = ValidateNames(objs, "veh_mats")  # noqa F821 # Validate Vehicle Material Names
    print("\n\n", rslt)
    # ValidateNames(objs,"mats")         # Validate Material Names (Non Vehicles)
    #############################################################################
