# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#

import math
import re
from dataclasses import dataclass
from math import radians
from typing import Any, List, Optional, Tuple, Union

import bpy
from bpy.types import Operator
from mathutils import Matrix, Vector

# import from visualizer methods
from .physics_visualizers_operators import (
    add_empty,
    axis_basis,
    ensure_widget_collection,
    get_or_add_limit_constraint,
    set_collection_visibility,
)

# LAZY IMPORT: markdown is imported only when needed (after dependency check)
# import markdown  # Moved to lazy import in functions that use it


# Constants for standard collection names
SIMREADY_COLLECTIONS = {"Geometry": "obj", "ReferencePrims": "joint", "Colliders": "collider"}

# Google Drive URL mapping for videos
SR_PSY_VIDEO_URL_MAPPING = {
    "chapter1_fixed_joint.mp4": "https://drive.google.com/file/d/12wi0nNxe-O4EsOTDjy4Cbk_IVulm7oT1/view?usp=drive_link",
    "chapter2_revolute_joint.mp4": "https://drive.google.com/file/d/1eaK9Klje1YfHGyujRnFs8eQM-WRX-qqw/view?usp=drive_link",
    "chapter3_grasp_vectors.mp4": "https://drive.google.com/file/d/1Hq0LREWzWokBg8lh8Eep-j3-aUGRevf-/view?usp=drive_link",
}


# TODO: use original mapping table to organize maps below
joint_items = [
    ("fixed", "Fixed", "Rigid connection, no relative motion (like welding two parts)"),
    ("revolute", "Revolute (Hinge)", "Rotational joint around one axis (like a door hinge or axle)"),
    ("prismatic", "Prismatic (Slider)", "Linear sliding along one axis (like a drawer or piston)"),
    ("spherical", "Spherical (Ball)", "Free rotation in all directions (like a ball-and-socket)"),
    ("distance", "Distance (Spring)", "Keeps two points at fixed distance, allows rotation (like a rope or rod)"),
    ("d6", "D6 (Six DoF)", "Configurable joint with limits on all 6 degrees of freedom"),
    ("gear", "Gear", "Links rotation between two revolute joints (image: gears)"),
    ("rack_and_pinion", "Rack and Pinion", "Links rotary to linear motion (like a steering system)"),
]


axis_items = [
    ("X", "X Axis", "Axis aligned along X"),
    ("Y", "Y Axis", "Axis aligned along Y"),
    ("Z", "Z Axis", "Axis aligned along Z"),
    ("LOCAL_X", "Local X Axis", "Axis aligned along object's local X"),
    ("LOCAL_Y", "Local Y Axis", "Axis aligned along object's local Y"),
    ("LOCAL_Z", "Local Z Axis", "Axis aligned along object's local Z"),
]

###################################
### START ARTIST FRIENDLY MAPZ ####


@dataclass
class BreakStrengthValues:
    """Dataclass containing break strength values for different materials."""

    paper: Tuple[float, float] = (2, 0.5)  # Very fragile
    cloth_rope: Tuple[float, float] = (8, 3)  # Moderate tension strength
    plastic: Tuple[float, float] = (25, 8)  # Flexible plastic parts
    glass: Tuple[float, float] = (15, 5)  # measured lightbulb values
    wood: Tuple[float, float] = (40, 15)  # Small wooden joints/dowels
    steel: Tuple[float, float] = (2000, 800)  # x10 measured values, Metal fasteners/brackets
    diamond: Tuple[float, float] = (10000, 4000)  # x10 measured values, pretty much unbreakable
    unbreakable: Tuple[float, float] = (float("inf"), float("inf"))

    def get(self, key: str, default: Tuple[float, float] = (0.0, 0.0)) -> Tuple[float, float]:
        """Get break strength values by key, similar to dict.get()"""
        return getattr(self, key, default)


@dataclass
class DampingValues:
    """Dataclass containing damping values for different levels."""

    no_damping: float = 0.0
    light_damping: float = 0.1
    medium_damping: float = 0.5
    heavy_damping: float = 1.0
    overdamped: float = 2.0

    def get(self, key: str, default: float = 0.0) -> float:
        """Get damping value by key, similar to dict.get()"""
        return getattr(self, key, default)


@dataclass
class StiffnessValues:
    """Dataclass containing stiffness values for different levels."""

    soft: float = 1.0
    springy: float = 10.0
    balanced: float = 50.0
    strong: float = 100.0
    rigid: float = 500.0
    unyielding: float = 1000.0

    def get(self, key: str, default: float = 0.0) -> float:
        """Get stiffness value by key, similar to dict.get()"""
        return getattr(self, key, default)


@dataclass
class BounceThresholdValues:
    """Dataclass containing bounce threshold values for different levels."""

    low: float = 0.1
    medium: float = 1.0
    high: float = 5.0
    auto: Optional[float] = None

    def get(self, key: str, default: float = 1.0) -> Optional[float]:
        """Get bounce threshold value by key, similar to dict.get()"""
        return getattr(self, key, default)


# Create instances of the dataclasses
break_strength_values = BreakStrengthValues()
damping_values = DampingValues()
stiffness_values = StiffnessValues()
bounce_threshold_values = BounceThresholdValues()

# Keep the original items for UI compatibility
break_strength_items = [
    ("paper", "Paper", "Extremely fragile, tears very easily"),
    ("cloth_rope", "Cloth or Rope", "Soft, flexible, very weak (like cloth or rope)"),
    ("plastic", "Plastic", "Low strength, breaks under small load"),
    ("wood", "Wood", "Moderate strength, resists medium force"),
    ("glass", "Glass", "Brittle, breaks under compression"),
    ("steel", "Steel", "High strength, resists large force"),
    ("diamond", "Diamond", "Extremely high strength, nearly unbreakable"),
    ("unbreakable", "Unbreakable", "Joint will never break (infinite strength)"),
]

damping_items = [
    ("no_damping", "No Damping", "Oscillates freely, no resistance (e.g., pendulum in vacuum)"),
    ("light_damping", "Light Damping", "Some resistance, still oscillates (e.g., guitar string)"),
    ("medium_damping", "Medium Damping", "Oscillates briefly then settles (e.g., car suspension)"),
    ("heavy_damping", "Heavy Damping", "Returns smoothly, no bounce (e.g., cabinet hinge)"),
    ("overdamped", "Overdamped", "Slow return, no bounce, sluggish (e.g., lab equipment)"),
]

stiffness_items = [
    ("soft", "Soft", "Very low stiffness, floppy joint (1.0)"),
    ("springy", "Springy", "Low stiffness (10.0)"),
    ("balanced", "Balanced", "Moderate stiffness (50.0)"),
    ("strong", "Strong", "High stiffness (100.0)"),
    ("rigid", "Rigid", "Very stiff (500.0)"),
    ("unyielding", "Unyielding", "Locked (1000.0)"),
]

bounce_threshold_items = [
    ("low", "Low (Always Bounce)", "Apply bounce even at low collision speeds (e.g. ping pong)"),
    ("medium", "Medium (Normal Bounce)", "Bounce on moderate impacts (e.g. furniture)"),
    ("high", "High (Hard Impact Only)", "Only bounce when slammed (e.g. rock on concrete)"),
    ("auto", "Auto (Calculated)", "Use default value based on stiffness and restitution"),
]


@dataclass
class EnumToFloatMaps:
    """Dataclass containing mappings from enum keys to value dataclasses."""

    stiffness_enum: StiffnessValues = None
    stiffness_enum_linear: StiffnessValues = None
    stiffness_enum_distance: StiffnessValues = None
    stiffness_enum_cone: StiffnessValues = None
    spring_stiffness_enum: StiffnessValues = None
    damping: DampingValues = None
    damping_linear: DampingValues = None
    damping_distance: DampingValues = None
    damping_cone: DampingValues = None
    bounce_threshold: BounceThresholdValues = None
    bounce_threshold_linear: BounceThresholdValues = None
    bounce_threshold_distance: BounceThresholdValues = None
    bounce_threshold_cone: BounceThresholdValues = None
    d6_xrot_stiffness: StiffnessValues = None
    d6_yrot_stiffness: StiffnessValues = None
    d6_zrot_stiffness: StiffnessValues = None
    d6_xpos_stiffness: StiffnessValues = None
    d6_ypos_stiffness: StiffnessValues = None
    d6_zpos_stiffness: StiffnessValues = None
    d6_xrot_damping: DampingValues = None
    d6_yrot_damping: DampingValues = None
    d6_zrot_damping: DampingValues = None
    d6_xpos_damping: DampingValues = None
    d6_ypos_damping: DampingValues = None
    d6_zpos_damping: DampingValues = None
    break_strength: BreakStrengthValues = None

    def __post_init__(self):
        """Initialize all fields with the appropriate dataclass instances."""
        if self.stiffness_enum is None:
            self.stiffness_enum = stiffness_values
        if self.stiffness_enum_linear is None:
            self.stiffness_enum_linear = stiffness_values
        if self.stiffness_enum_distance is None:
            self.stiffness_enum_distance = stiffness_values
        if self.stiffness_enum_cone is None:
            self.stiffness_enum_cone = stiffness_values
        if self.spring_stiffness_enum is None:
            self.spring_stiffness_enum = stiffness_values
        if self.damping is None:
            self.damping = damping_values
        if self.damping_linear is None:
            self.damping_linear = damping_values
        if self.damping_distance is None:
            self.damping_distance = damping_values
        if self.damping_cone is None:
            self.damping_cone = damping_values
        if self.bounce_threshold is None:
            self.bounce_threshold = bounce_threshold_values
        if self.bounce_threshold_linear is None:
            self.bounce_threshold_linear = bounce_threshold_values
        if self.bounce_threshold_distance is None:
            self.bounce_threshold_distance = bounce_threshold_values
        if self.bounce_threshold_cone is None:
            self.bounce_threshold_cone = bounce_threshold_values
        if self.d6_xrot_stiffness is None:
            self.d6_xrot_stiffness = stiffness_values
        if self.d6_yrot_stiffness is None:
            self.d6_yrot_stiffness = stiffness_values
        if self.d6_zrot_stiffness is None:
            self.d6_zrot_stiffness = stiffness_values
        if self.d6_xpos_stiffness is None:
            self.d6_xpos_stiffness = stiffness_values
        if self.d6_ypos_stiffness is None:
            self.d6_ypos_stiffness = stiffness_values
        if self.d6_zpos_stiffness is None:
            self.d6_zpos_stiffness = stiffness_values
        if self.d6_xrot_damping is None:
            self.d6_xrot_damping = damping_values
        if self.d6_yrot_damping is None:
            self.d6_yrot_damping = damping_values
        if self.d6_zrot_damping is None:
            self.d6_zrot_damping = damping_values
        if self.d6_xpos_damping is None:
            self.d6_xpos_damping = damping_values
        if self.d6_ypos_damping is None:
            self.d6_ypos_damping = damping_values
        if self.d6_zpos_damping is None:
            self.d6_zpos_damping = damping_values
        if self.break_strength is None:
            self.break_strength = break_strength_values

    def get(self, key: str) -> Union[StiffnessValues, DampingValues, BounceThresholdValues, BreakStrengthValues]:
        """Get the appropriate value dataclass by key."""
        return getattr(self, key)


# Create instance of the enum mapping dataclass
ENUM_TO_FLOAT_MAPS = EnumToFloatMaps()

### END ARTIST FRIENDLY MAPS ###
################################

# Certain schema items in joints have
# special namespace that doesn't match
# conventions.
JOINT_NAME_SCHEMA_MAP = {
    "D6Joint": "",
    "FixedJoint": "",
    "RevoluteJoint": "angular",
    "PrismaticJoint": "linear",
    "SphericalJoint": "cone",
    "DistanceJoint": "distance",
}


@dataclass
class JointExportMap:
    """Dataclass containing mappings from UI keys to USD export keys."""

    # Core fields
    joint_type: str = "pxr:usd:physics:joint:type"
    joint_local_pos_0: str = "pxr:usd:physics:localPos0"
    joint_local_pos_1: str = "pxr:usd:physics:localPos1"
    joint_local_rot_0: str = "pxr:usd:physics:localRot0"
    joint_local_rot_1: str = "pxr:usd:physics:localRot1"
    joint_axis: str = "pxr:usd:physics:joint:axis"
    body_0: str = "pxr:usd:physics:joint:body0"
    body_1: str = "pxr:usd:physics:joint:body1"
    break_strength: List[str] = None

    # Revolute
    lower_limit_deg: str = "pxr:usd:physics:joint:lowerLimit"
    upper_limit_deg: str = "pxr:usd:physics:joint:upperLimit"

    # Prismatic
    min_dist_prismatic: str = "pxr:usd:physics:joint:lowerLimit"
    max_dist_prismatic: str = "pxr:usd:physics:joint:upperLimit"

    # Distance
    min_dist: str = "pxr:usd:physics:minDistance"
    max_dist: str = "pxr:usd:physics:maxDistance"

    # Gear joint
    gear_hinge_0: str = "pxr:usd:physics:joint:hinge0"
    gear_hinge_1: str = "pxr:usd:physics:joint:hinge1"
    gear_ratio: str = "pxr:usd:physics:joint:gearRatio"

    # Spherical joint
    cone_angle_0: str = "pxr:usd:physics:coneAngle0Limit"
    cone_angle_1: str = "pxr:usd:physics:coneAngle1Limit"

    # Rack & pinion
    rp_hinge: str = "pxr:usd:physics:hinge"
    rp_prismatic: str = "pxr:usd:physics:prismatic"
    rp_ratio: str = "pxr:usd:physics:joint:ratio"

    # D6 joint
    d6_xrot_low_limit: str = "pxr:usd:limit:rotX:physics:low"
    d6_xrot_upper_limit: str = "pxr:usd:limit:rotX:physics:high"
    d6_yrot_low_limit: str = "pxr:usd:limit:rotY:physics:low"
    d6_yrot_upper_limit: str = "pxr:usd:limit:rotY:physics:high"
    d6_zrot_low_limit: str = "pxr:usd:limit:rotZ:physics:low"
    d6_zrot_upper_limit: str = "pxr:usd:limit:rotZ:physics:high"
    d6_xpos_low_limit: str = "pxr:usd:limit:transX:physics:low"
    d6_xpos_upper_limit: str = "pxr:usd:limit:transX:physics:high"
    d6_ypos_low_limit: str = "pxr:usd:limit:transY:physics:low"
    d6_ypos_upper_limit: str = "pxr:usd:limit:transY:physics:high"
    d6_zpos_low_limit: str = "pxr:usd:limit:transZ:physics:low"
    d6_zpos_upper_limit: str = "pxr:usd:limit:transZ:physics:high"

    def __post_init__(self):
        """Initialize list fields."""
        if self.break_strength is None:
            self.break_strength = ["pxr:usd:physics:breakForce", "pxr:usd:physics:breakTorque"]

    def items(self):
        """Return items like a dictionary for compatibility."""
        return [(key, value) for key, value in self.__dict__.items()]

    def get(self, key: str, default: Any = None) -> Any:
        """Get value by key, similar to dict.get()."""
        return getattr(self, key, default)


# Create instance of the joint export map dataclass
JOINT_EXPORT_MAP = JointExportMap()


@dataclass
class JointTypeFields:
    """Dataclass containing field lists for different joint types."""

    fixed: List[str] = None
    revolute: List[str] = None
    prismatic: List[str] = None
    distance: List[str] = None
    spherical: List[str] = None
    d6: List[str] = None
    rack_and_pinion: List[str] = None
    gear: List[str] = None

    def __post_init__(self):
        """Initialize all field lists."""
        if self.fixed is None:
            self.fixed = [
                "joint_type",
                "body_0",
                "body_1",
                "joint_local_pos_0",
                "joint_local_pos_1",
                "joint_local_rot_0",
                "joint_local_rot_1",
                "joint_friction",
                "maximum_joint_velocity",
                "armature",
                "break_strength",
            ]
        if self.revolute is None:
            self.revolute = [
                "joint_type",
                "body_0",
                "body_1",
                "joint_axis",
                "joint_local_pos_0",
                "joint_local_pos_1",
                "joint_local_rot_0",
                "joint_local_rot_1",
                "lower_limit_deg",
                "upper_limit_deg",
                "infinite_limit_deg",
                "damping",
                "restitution",
                "stiffness_enum",
                "bounce_threshold",
                "break_strength",
                "joint_friction",
                "maximum_joint_velocity",
                "armature",
            ]
        if self.prismatic is None:
            self.prismatic = [
                "joint_type",
                "body_0",
                "body_1",
                "joint_axis",
                "joint_local_pos_0",
                "joint_local_pos_1",
                "joint_local_rot_0",
                "joint_local_rot_1",
                "min_dist_prismatic",
                "max_dist_prismatic",
                "restitution_linear",
                "bounce_threshold_linear",
                "damping_linear",
                "stiffness_enum_linear",
                "break_strength",
                "joint_friction",
                "maximum_joint_velocity",
                "armature",
            ]
        if self.distance is None:
            self.distance = [
                "joint_type",
                "body_0",
                "body_1",
                "joint_local_pos_0",
                "joint_local_pos_1",
                "min_dist",
                "max_dist",
                "restitution_distance",
                "bounce_threshold_distance",
                "damping_distance",
                "stiffness_enum_distance",
                "break_strength",
                "spring_enabled",
                "spring_stiffness_enum",
                "spring_damping",
                "joint_friction",
                "maximum_joint_velocity",
                "armature",
            ]
        if self.spherical is None:
            self.spherical = [
                "joint_type",
                "body_0",
                "body_1",
                "joint_axis",
                "break_strength",
                "joint_local_pos_0",
                "joint_local_pos_1",
                "cone_angle_0",
                "cone_angle_1",
                "bounce_threshold_cone",
                "damping_cone",
                "restitution_cone",
                "stiffness_enum_cone",
                "joint_friction",
                "maximum_joint_velocity",
                "armature",
            ]
        if self.d6 is None:
            self.d6 = [
                "joint_type",
                "body_0",
                "body_1",
                "break_strength",
                "joint_local_pos_0",
                "joint_local_pos_1",
                "joint_friction",
                "maximum_joint_velocity",
                "armature",
                "d6_xrot_low_limit",
                "d6_xrot_upper_limit",
                "d6_xrot_restitution",
                "d6_xrot_bounce_thresh",
                "d6_xrot_stiffness",
                "d6_xrot_damping",
                "d6_yrot_low_limit",
                "d6_yrot_upper_limit",
                "d6_yrot_restitution",
                "d6_yrot_bounce_thresh",
                "d6_yrot_stiffness",
                "d6_yrot_damping",
                "d6_zrot_low_limit",
                "d6_zrot_upper_limit",
                "d6_zrot_restitution",
                "d6_zrot_bounce_thresh",
                "d6_zrot_stiffness",
                "d6_zrot_damping",
                "d6_xpos_low_limit",
                "d6_xpos_upper_limit",
                "d6_xpos_restitution",
                "d6_xpos_bounce_thresh",
                "d6_xpos_stiffness",
                "d6_xpos_damping",
                "d6_ypos_low_limit",
                "d6_ypos_upper_limit",
                "d6_ypos_restitution",
                "d6_ypos_bounce_thresh",
                "d6_ypos_stiffness",
                "d6_ypos_damping",
                "d6_zpos_low_limit",
                "d6_zpos_upper_limit",
                "d6_zpos_restitution",
                "d6_zpos_bounce_thresh",
                "d6_zpos_stiffness",
                "d6_zpos_damping",
            ]
        if self.rack_and_pinion is None:
            self.rack_and_pinion = [
                "joint_type",
                "body_0",
                "body_1",
                "joint_local_pos_0",
                "joint_local_pos_1",
                "rp_hinge",
                "rp_prismatic",
                "rp_ratio",
            ]
        if self.gear is None:
            self.gear = [
                "joint_type",
                "body_0",
                "body_1",
                "joint_local_pos_0",
                "joint_local_pos_1",
                "gear_hinge_0",
                "gear_hinge_1",
                "gear_ratio",
            ]

    def get(self, key: str, default: List[str] = None) -> List[str]:
        """Get field list by joint type, similar to dict.get()."""
        if default is None:
            default = []
        return getattr(self, key, default)


# Create instance of the joint type fields dataclass
JOINT_TYPE_FIELDS = JointTypeFields()

###################################
### REVERSE MAPPING FUNCTIONS ####
###################################


def create_reverse_export_map():
    """Create a reverse mapping from USD keys to UI keys."""
    reverse_map = {}
    for ui_key, usd_key in JOINT_EXPORT_MAP.items():
        if isinstance(usd_key, list):
            # For break_strength which maps to multiple USD keys
            for key in usd_key:
                reverse_map[key] = ui_key
        else:
            reverse_map[usd_key] = ui_key
    return reverse_map


# Create the reverse mapping
REVERSE_EXPORT_MAP = create_reverse_export_map()


def create_joint_type_specific_reverse_maps():
    """Create joint-type-specific reverse mappings for ambiguous USD properties."""
    joint_type_maps = {}

    # Revolute joint mapping
    joint_type_maps["revolute"] = {
        "pxr:usd:physics:joint:lowerLimit": "lower_limit_deg",
        "pxr:usd:physics:joint:upperLimit": "upper_limit_deg",
    }

    # Prismatic joint mapping
    joint_type_maps["prismatic"] = {
        "pxr:usd:physics:joint:lowerLimit": "min_dist_prismatic",
        "pxr:usd:physics:joint:upperLimit": "max_dist_prismatic",
    }

    # Distance joint mapping
    joint_type_maps["distance"] = {
        "pxr:usd:physics:minDistance": "min_dist",
        "pxr:usd:physics:maxDistance": "max_dist",
    }

    # Spherical joint mapping
    joint_type_maps["spherical"] = {
        "pxr:usd:physics:coneAngle0Limit": "cone_angle_0",
        "pxr:usd:physics:coneAngle1Limit": "cone_angle_1",
    }

    # D6 joint mapping
    joint_type_maps["d6"] = {
        "pxr:usd:limit:rotX:physics:low": "d6_xrot_low_limit",
        "pxr:usd:limit:rotX:physics:high": "d6_xrot_upper_limit",
        "pxr:usd:limit:rotY:physics:low": "d6_yrot_low_limit",
        "pxr:usd:limit:rotY:physics:high": "d6_yrot_upper_limit",
        "pxr:usd:limit:rotZ:physics:low": "d6_zrot_low_limit",
        "pxr:usd:limit:rotZ:physics:high": "d6_zrot_upper_limit",
        "pxr:usd:limit:transX:physics:low": "d6_xpos_low_limit",
        "pxr:usd:limit:transX:physics:high": "d6_xpos_upper_limit",
        "pxr:usd:limit:transY:physics:low": "d6_ypos_low_limit",
        "pxr:usd:limit:transY:physics:high": "d6_ypos_upper_limit",
        "pxr:usd:limit:transZ:physics:low": "d6_zpos_low_limit",
        "pxr:usd:limit:transZ:physics:high": "d6_zpos_upper_limit",
    }

    # Gear joint mapping
    joint_type_maps["gear"] = {
        "pxr:usd:physics:joint:hinge0": "gear_hinge_0",
        "pxr:usd:physics:joint:hinge1": "gear_hinge_1",
        "pxr:usd:physics:joint:gearRatio": "gear_ratio",
    }

    # Rack and pinion joint mapping
    joint_type_maps["rack_and_pinion"] = {
        "pxr:usd:physics:hinge": "rp_hinge",
        "pxr:usd:physics:prismatic": "rp_prismatic",
        "pxr:usd:physics:joint:ratio": "rp_ratio",
    }

    return joint_type_maps


# Create joint-type-specific reverse mappings
JOINT_TYPE_SPECIFIC_MAPS = create_joint_type_specific_reverse_maps()


def create_reverse_enum_maps():
    """Create reverse mappings from float values back to enum keys."""
    reverse_maps = {}

    # Reverse break strength mapping
    break_strength_reverse = {}
    for key, (force, torque) in break_strength_values.__dict__.items():
        if not key.startswith("_"):
            break_strength_reverse[(force, torque)] = key
    reverse_maps["break_strength"] = break_strength_reverse

    # Reverse damping mapping
    damping_reverse = {}
    for key, value in damping_values.__dict__.items():
        if not key.startswith("_"):
            damping_reverse[value] = key
    reverse_maps["damping"] = damping_reverse
    reverse_maps["damping_linear"] = damping_reverse
    reverse_maps["damping_distance"] = damping_reverse
    reverse_maps["damping_cone"] = damping_reverse
    reverse_maps["d6_xrot_damping"] = damping_reverse
    reverse_maps["d6_yrot_damping"] = damping_reverse
    reverse_maps["d6_zrot_damping"] = damping_reverse
    reverse_maps["d6_xpos_damping"] = damping_reverse
    reverse_maps["d6_ypos_damping"] = damping_reverse
    reverse_maps["d6_zpos_damping"] = damping_reverse

    # Reverse stiffness mapping
    stiffness_reverse = {}
    for key, value in stiffness_values.__dict__.items():
        if not key.startswith("_"):
            stiffness_reverse[value] = key
    reverse_maps["stiffness_enum"] = stiffness_reverse
    reverse_maps["stiffness_enum_linear"] = stiffness_reverse
    reverse_maps["stiffness_enum_distance"] = stiffness_reverse
    reverse_maps["stiffness_enum_cone"] = stiffness_reverse
    reverse_maps["spring_stiffness_enum"] = stiffness_reverse
    reverse_maps["d6_xrot_stiffness"] = stiffness_reverse
    reverse_maps["d6_yrot_stiffness"] = stiffness_reverse
    reverse_maps["d6_zrot_stiffness"] = stiffness_reverse
    reverse_maps["d6_xpos_stiffness"] = stiffness_reverse
    reverse_maps["d6_ypos_stiffness"] = stiffness_reverse
    reverse_maps["d6_zpos_stiffness"] = stiffness_reverse

    # Reverse bounce threshold mapping
    bounce_threshold_reverse = {}
    for key, value in bounce_threshold_values.__dict__.items():
        if not key.startswith("_"):
            bounce_threshold_reverse[value] = key
    reverse_maps["bounce_threshold"] = bounce_threshold_reverse
    reverse_maps["bounce_threshold_linear"] = bounce_threshold_reverse
    reverse_maps["bounce_threshold_distance"] = bounce_threshold_reverse
    reverse_maps["bounce_threshold_cone"] = bounce_threshold_reverse

    return reverse_maps


# Create the reverse enum mappings
REVERSE_ENUM_MAPS = create_reverse_enum_maps()


def find_closest_enum_value(value, reverse_map, tolerance=0.001):
    """Find the closest enum key for a given float value."""
    if value in reverse_map:
        return reverse_map[value]

    # Find closest match within tolerance
    for enum_value, enum_key in reverse_map.items():
        if enum_value is not None and abs(value - enum_value) <= tolerance:
            return enum_key

    # If no close match found, return the default
    return "medium_damping" if "damping" in str(reverse_map) else "balanced"


def get_world_axis_vector(joint_axis, obj):
    """
    Convert joint axis enum to world space vector.

    Args:
        joint_axis: The joint axis enum value (X, Y, Z, LOCAL_X, LOCAL_Y, LOCAL_Z)
        obj: The object to get local axes from (for local axis calculations)

    Returns:
        Vector: The axis vector in world space
    """
    from mathutils import Vector

    if joint_axis in ["X", "Y", "Z"]:
        # World axes
        if joint_axis == "X":
            return Vector((1.0, 0.0, 0.0))
        elif joint_axis == "Y":
            return Vector((0.0, 1.0, 0.0))
        elif joint_axis == "Z":
            return Vector((0.0, 0.0, 1.0))
    elif joint_axis in ["LOCAL_X", "LOCAL_Y", "LOCAL_Z"] and obj:
        # Local axes - transform to world space
        if joint_axis == "LOCAL_X":
            local_axis = Vector((1.0, 0.0, 0.0))
        elif joint_axis == "LOCAL_Y":
            local_axis = Vector((0.0, 1.0, 0.0))
        elif joint_axis == "LOCAL_Z":
            local_axis = Vector((0.0, 0.0, 1.0))

        # Transform local axis to world space using object's rotation
        world_axis = obj.matrix_world.to_3x3() @ local_axis
        return world_axis.normalized()

    # Fallback to world X axis
    return Vector((1.0, 0.0, 0.0))


def calculate_adaptive_empty_size(obj, default_size=1.0, min_size=0.05, max_size=2.0):
    """
    Calculate appropriate empty display size based on object dimensions.

    Args:
        obj: The Blender object to measure (should be a MESH, CURVE, or other geometry type)
        default_size: Base size for a 2-meter object (default: 1.0)
        min_size: Minimum empty size to prevent it from being too small (default: 0.05)
        max_size: Maximum empty size to prevent it from being too large (default: 2.0)

    Returns:
        float: The calculated empty display size
    """
    if not obj:
        return default_size

    # Don't calculate bounds for empty objects - they don't have meaningful geometry dimensions
    if obj.type == "EMPTY":
        return default_size

    # Get object dimensions in world space
    # This accounts for object scale
    dimensions = obj.dimensions

    # Use the maximum dimension as the characteristic size
    max_dimension = max(dimensions.x, dimensions.y, dimensions.z)

    # If object has no dimensions (e.g., point cloud, curve with no thickness), use default
    if max_dimension < 0.001:
        return default_size

    # Scale the empty size proportionally to object size
    # A 2-meter object gets default_size (1.0), smaller/larger objects scale accordingly
    # Using a slightly smaller factor (0.4) so the empty doesn't overwhelm small objects
    calculated_size = (max_dimension / 2.0) * default_size * 0.8

    # Clamp to min/max range
    return max(min_size, min(calculated_size, max_size))


def sync_ui_from_object_custom_props(obj, props):
    """Sync UI properties from object custom properties."""
    if not obj or obj.type != "EMPTY":
        return False

    # Get all physics-related custom properties
    custom_props = {k: v for k, v in obj.items() if k.startswith(("pxr:usd:physics", "omni:simready:physx"))}

    if not custom_props:
        return False

    # Track which properties we've set to avoid conflicts
    set_properties = set()

    # First pass: handle break strength (special case with multiple USD keys)
    break_force_key = "pxr:usd:physics:breakForce"
    break_torque_key = "pxr:usd:physics:breakTorque"

    if break_force_key in custom_props and break_torque_key in custom_props:
        force = custom_props[break_force_key]
        torque = custom_props[break_torque_key]

        # Handle case where Blender might store infinity as string
        if isinstance(force, str) and force.lower() in ["inf", "infinity"]:
            force = float("inf")
        if isinstance(torque, str) and torque.lower() in ["inf", "infinity"]:
            torque = float("inf")

        # Find matching break strength enum
        break_strength_reverse = REVERSE_ENUM_MAPS["break_strength"]
        for (enum_force, enum_torque), enum_key in break_strength_reverse.items():

            # Handle infinity values specially
            if math.isinf(force) and math.isinf(enum_force) and math.isinf(torque) and math.isinf(enum_torque):
                props.break_strength = enum_key
                set_properties.add("break_strength")
                break
            elif (
                not math.isinf(force)
                and not math.isinf(enum_force)
                and not math.isinf(torque)
                and not math.isinf(enum_torque)
            ):
                # Regular finite value comparison
                if abs(force - enum_force) <= 0.001 and abs(torque - enum_torque) <= 0.001:
                    props.break_strength = enum_key
                    set_properties.add("break_strength")
                    break
            # else:
            #     print(f"Debug: Mismatched infinity/finite values - skipping {enum_key}")

        if "break_strength" not in set_properties:
            print(f"Warning: No matching break_strength found for ({force}, {torque})")

    # Second pass: handle joint_type first to update UI
    joint_type_key = "pxr:usd:physics:joint:type"
    if joint_type_key in custom_props:
        joint_type_value = custom_props[joint_type_key]

        # No mapping needed - UI and USD use the same joint type names
        # Just use the value directly
        old_joint_type = props.joint_type  # noqa F841
        props.joint_type = joint_type_value
        set_properties.add("joint_type")

        # Force UI update to show correct fields for this joint type
        try:
            # Trigger the joint_type_update function to reset properties
            props.joint_type_update(bpy.context)

            # Trigger UI refresh
            props.ui_refresh_trigger += 1

        except Exception as e:
            print(f"Warning: Failed to update UI for joint type: {e}")
    else:
        print("No joint type found in custom properties - keeping current UI joint type")

    # Get the current joint type for context-aware mapping
    current_joint_type = props.joint_type

    # Third pass: handle all other properties
    for usd_key, value in custom_props.items():
        # Skip break strength keys and joint_type as they're handled above
        if usd_key in [break_force_key, break_torque_key, joint_type_key]:
            continue

        # Try joint-type-specific mapping first
        ui_key = None
        mapping_type = "general"
        if current_joint_type in JOINT_TYPE_SPECIFIC_MAPS:
            ui_key = JOINT_TYPE_SPECIFIC_MAPS[current_joint_type].get(usd_key)
            if ui_key:
                mapping_type = f"joint-specific ({current_joint_type})"

        # Fall back to general reverse mapping if not found
        if not ui_key:
            ui_key = REVERSE_EXPORT_MAP.get(usd_key)
            mapping_type = "general"

        # Special handling for ambiguous joint limits
        if usd_key in ["pxr:usd:physics:joint:lowerLimit", "pxr:usd:physics:joint:upperLimit"]:
            # If joint type is not detected or not in specific maps, try to infer from context
            if not ui_key or current_joint_type not in JOINT_TYPE_SPECIFIC_MAPS:
                # Try to determine joint type from other properties or UI state
                if hasattr(props, "lower_limit_deg") and hasattr(props, "upper_limit_deg"):
                    # UI has revolute joint properties, assume revolute
                    if usd_key == "pxr:usd:physics:joint:lowerLimit":
                        ui_key = "lower_limit_deg"
                    else:  # upperLimit
                        ui_key = "upper_limit_deg"
                    mapping_type = "inferred-revolute"
                elif hasattr(props, "min_dist_prismatic") and hasattr(props, "max_dist_prismatic"):
                    # UI has prismatic joint properties, assume prismatic
                    if usd_key == "pxr:usd:physics:joint:lowerLimit":
                        ui_key = "min_dist_prismatic"
                    else:  # upperLimit
                        ui_key = "max_dist_prismatic"
                    mapping_type = "inferred-prismatic"  # noqa F841

            # Apply reverse offset for prismatic joint limits
            if ui_key in ["min_dist_prismatic", "max_dist_prismatic"]:
                # Get the joint axis from the object's custom properties or UI
                joint_axis = None
                if "pxr:usd:physics:joint:axis" in custom_props:
                    joint_axis = custom_props["pxr:usd:physics:joint:axis"]
                elif hasattr(props, "joint_axis"):
                    joint_axis = props.joint_axis

                if joint_axis:
                    # Extract location component based on joint axis
                    axis_to_component = {"X": obj.location.x, "Y": obj.location.y, "Z": obj.location.z}
                    axis_component = axis_to_component.get(joint_axis, 0.0)

                    # Reverse the offset: stored_value + object_location_component = ui_value
                    value = value + axis_component

        if not ui_key or ui_key in set_properties:
            continue

        # Check if this UI property exists
        if not hasattr(props, ui_key):
            continue

        # Handle different property types
        try:
            if ui_key == "joint_axis":
                # Handle joint_axis - it can be stored as either a string enum or a vector
                if isinstance(value, str) and value in ["X", "Y", "Z", "LOCAL_X", "LOCAL_Y", "LOCAL_Z"]:
                    # Direct enum string (this is how it's currently stored)
                    props.joint_axis = value
                    # Update axis_mode based on the axis type
                    if value.startswith("LOCAL_"):
                        joint_axis_mode = "LOCAL"  # noqa F841
                    else:
                        joint_axis_mode = "WORLD"  # noqa F841
                    set_properties.add(ui_key)
                elif isinstance(value, (list, tuple)) and len(value) == 3:
                    # Vector format - try to match to closest axis
                    x, y, z = value
                    # For now, default to world axes when reading vectors
                    # TODO: Could implement more sophisticated matching to local axes
                    if abs(x) > 0.9:
                        props.joint_axis = "X"
                        props.axis_mode = "WORLD"
                    elif abs(y) > 0.9:
                        props.joint_axis = "Y"
                        props.axis_mode = "WORLD"
                    elif abs(z) > 0.9:
                        props.joint_axis = "Z"
                        props.axis_mode = "WORLD"
                    else:
                        # Default to X axis if no clear match
                        props.joint_axis = "X"
                        props.axis_mode = "WORLD"
                    set_properties.add(ui_key)
                else:
                    print(f"Warning: Unknown joint_axis format: {value} (type: {type(value)})")

            elif ui_key in ["body_0", "body_1", "gear_hinge_0", "gear_hinge_1", "rp_hinge", "rp_prismatic"]:
                # Handle object references - these need special handling
                # The custom property stores the object name as a string
                if isinstance(value, str) and value:  # Check for non-empty string
                    # Find the object by name
                    obj_ref = bpy.data.objects.get(value)
                    if obj_ref:
                        setattr(props, ui_key, obj_ref)
                        set_properties.add(ui_key)
                    else:
                        print(f"Warning: Object '{value}' not found for {ui_key}")
                else:
                    print(f"Warning: Invalid value for {ui_key}: {value} (type: {type(value)})")
                continue

            elif ui_key in REVERSE_ENUM_MAPS:
                # Handle enum properties that need reverse mapping
                reverse_map = REVERSE_ENUM_MAPS[ui_key]
                enum_key = find_closest_enum_value(value, reverse_map)
                setattr(props, ui_key, enum_key)
                set_properties.add(ui_key)

            elif ui_key in ["lower_limit_deg", "upper_limit_deg"]:
                # Handle revolute joint limits with potential infinite values
                if isinstance(value, str) and value in ["inf", "-inf"]:
                    # Set infinite limit checkbox and don't set the numeric values
                    props.infinite_limit_deg = True
                    set_properties.add("infinite_limit_deg")
                    # Skip setting the actual limit value since it's infinite
                    continue
                elif isinstance(value, float) and (value == float("inf") or value == float("-inf")):
                    # Also handle numeric infinity
                    props.infinite_limit_deg = True
                    set_properties.add("infinite_limit_deg")
                    continue
                else:
                    # Normal finite limit value
                    # Values stored in USD are in degrees, but the UI property has unit="ROTATION"
                    # Blender expects radians internally and can display as degrees in the UI
                    # So we need to convert degrees -> radians before storing (always)
                    value_in_radians = math.radians(value)
                    props.infinite_limit_deg = False
                    setattr(props, ui_key, value_in_radians)
                    set_properties.add(ui_key)
                    set_properties.add("infinite_limit_deg")

            else:
                # Handle direct value assignment (floats, vectors, etc.)
                print(f"UI Key: {ui_key}, Value: {value}")
                setattr(props, ui_key, value)
                set_properties.add(ui_key)

        except Exception as e:
            print(f"Warning: Failed to sync {ui_key} from {usd_key}: {e}")
            continue

    # Handle Drive API properties
    # Linear Drive
    if "drive:linear:physics:type" in obj.keys():
        props.drive_linear_enabled = True
        props.drive_linear_type = obj.get("drive:linear:physics:type", "force")
        props.drive_linear_max_force = obj.get("drive:linear:physics:maxForce", 0.0)
        props.drive_linear_target_position = obj.get("drive:linear:physics:targetPosition", 0.0)
        props.drive_linear_target_velocity = obj.get("drive:linear:physics:targetVelocity", 0.0)
        props.drive_linear_damping = obj.get("drive:linear:physics:damping", 0.0)
        props.drive_linear_stiffness = obj.get("drive:linear:physics:stiffness", 0.0)
        set_properties.add("drive_linear_enabled")

    # Angular Drive
    if "drive:angular:physics:type" in obj.keys():
        props.drive_angular_enabled = True
        props.drive_angular_type = obj.get("drive:angular:physics:type", "force")
        props.drive_angular_max_force = obj.get("drive:angular:physics:maxForce", 0.0)
        props.drive_angular_target_position = obj.get("drive:angular:physics:targetPosition", 0.0)
        props.drive_angular_target_velocity = obj.get("drive:angular:physics:targetVelocity", 0.0)
        props.drive_angular_damping = obj.get("drive:angular:physics:damping", 0.0)
        props.drive_angular_stiffness = obj.get("drive:angular:physics:stiffness", 0.0)
        set_properties.add("drive_angular_enabled")

    return len(set_properties) > 0


# -------------------------------------------------------------------
# Methods
# -------------------------------------------------------------------
# Global timer handle
_intersection_timer = None
_debug_enabled = False  # Set to False to disable debug prints
# Track last synced object to prevent excessive syncing
_last_synced_object = None
# Re-entrancy guard: prevents depsgraph handlers from triggering each other recursively
_in_depsgraph_handler = False


def delayed_auto_sync():
    """Delayed auto-sync function to ensure UI is ready."""
    try:
        if not bpy.context.active_object:
            return

        obj = bpy.context.active_object
        if obj.type != "EMPTY":
            return

        props = bpy.context.scene.joint_attribute_props
        if not props.auto_sync_ui:
            return

        # Check if object has physics properties
        custom_props = {k: v for k, v in obj.items() if k.startswith(("pxr:usd:physics", "omni:simready:physx"))}
        if not custom_props:
            return

        # Sync UI from object custom properties
        success = sync_ui_from_object_custom_props(obj, props)
        if success:
            global _last_synced_object
            _last_synced_object = obj

            # Force UI refresh
            for area in bpy.context.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except Exception as e:
        print(f"Delayed auto-sync failed: {e}")


@bpy.app.handlers.persistent
def on_object_selection_change(scene):
    """Handler to automatically sync UI when objects are selected."""
    global _last_synced_object, _in_depsgraph_handler
    if _in_depsgraph_handler:
        return

    if not hasattr(scene, "joint_attribute_props"):
        return

    props = scene.joint_attribute_props

    # Update constraint system state when selection changes (deferred to avoid
    # modifying scene properties from within the depsgraph callback).
    if not bpy.app.timers.is_registered(_deferred_constraint_state_update):
        bpy.app.timers.register(_deferred_constraint_state_update, first_interval=0.0)

    # Only auto-sync if enabled
    if not props.auto_sync_ui:
        return

    # Get the active object
    if not bpy.context.active_object:
        _last_synced_object = None
        return

    obj = bpy.context.active_object

    # Only sync for empty objects with physics properties
    if obj.type != "EMPTY":
        _last_synced_object = None
        return

    # Check if we already synced this object recently
    if _last_synced_object == obj:
        return

    # Check if object has physics properties
    custom_props = {k: v for k, v in obj.items() if k.startswith(("pxr:usd:physics", "omni:simready:physx"))}
    if not custom_props:
        _last_synced_object = None
        return

    # Use a timer to delay the sync until after the UI is drawn
    bpy.app.timers.register(delayed_auto_sync, first_interval=0.1)


def _deferred_constraint_state_update():
    """Deferred callback that calls update_constraint_system_state outside the depsgraph handler."""
    try:
        update_constraint_system_state(bpy.context)
    except Exception:
        pass
    return None  # run once


def normalize_revolute_limits(lower_rad, upper_rad) -> Tuple[float, float]:
    """Normalize revolute joint limits to avoid Euler discontinuities.

    Adjusts -180° lower limit to -179° to prevent simulation issues at the discontinuity.
    Physics engines struggle with limits exactly at -180°.

    Args:
        lower_rad: Lower limit in radians
        upper_rad: Upper limit in radians

    Returns:
        Tuple of (normalized_lower_rad, normalized_upper_rad)
    """
    lower_deg = math.degrees(lower_rad)
    upper_deg = math.degrees(upper_rad)

    # If lower limit is -180°, offset it to -179° to avoid discontinuity
    if abs(lower_deg - (-180.0)) < 0.01:  # Check if approximately -180°
        lower_deg = -179.0

    if abs(lower_deg - (-360.0)) < 0.01:
        lower_deg = -359.0

    if abs(upper_deg - 180.0) < 0.01:
        upper_deg = 179.0

    if abs(upper_deg - 360.0) < 0.01:
        upper_deg = 359.0

    return lower_deg, upper_deg


def debug_print(message):
    """Debug print helper"""
    if _debug_enabled:
        print(f"[GRASP DEBUG] {message}")


def _deferred_grasp_update():
    """Deferred callback that performs scene mutations outside the depsgraph handler.

    Change detection prevents unnecessary RNA mutations. Writing to RNA properties
    triggers new depsgraph updates, which would re-invoke this timer in a tight loop
    and interfere with modal operators like the viewport transform widget.
    Only mutate when a grasp point has actually moved.
    """
    global _in_depsgraph_handler
    try:
        scene = bpy.context.scene
        if not hasattr(scene, "grasp_point_props"):
            return None
        grasp_props = scene.grasp_point_props
        debug_print(f"Deferred update: {len(grasp_props.grasp_pairs)} grasp pairs")

        _EPSILON = 1e-6
        any_changed = False

        _in_depsgraph_handler = True
        try:
            for pair in grasp_props.grasp_pairs:
                try:
                    pair_changed = False

                    if pair.grasp_point_1:
                        new_pos_1 = pair.grasp_point_1.location.copy()
                        if (new_pos_1 - pair.point_1_position).length > _EPSILON:
                            pair.point_1_position = new_pos_1
                            pair_changed = True

                    if pair.grasp_point_2:
                        new_pos_2 = pair.grasp_point_2.location.copy()
                        if (new_pos_2 - pair.point_2_position).length > _EPSILON:
                            pair.point_2_position = new_pos_2
                            pair_changed = True

                    if pair_changed and pair.grasp_point_1 and pair.grasp_point_2:
                        distance = (pair.point_2_position - pair.point_1_position).length
                        pair.point_distance = distance
                        line_object = regenerate_grasp_line(pair)
                        if line_object:
                            line_object["intersections_dirty"] = True
                            debug_print(f"Marked {line_object.name} as dirty")
                        else:
                            debug_print(f"Failed to get/create line object for pair {pair.name}")
                        any_changed = True
                except Exception as e:
                    debug_print(f"Error updating grasp pair: {e}")
                    continue
        finally:
            _in_depsgraph_handler = False

        if any_changed:
            start_intersection_timer()
    except Exception as e:
        debug_print(f"Error in _deferred_grasp_update: {e}")
    return None  # run once


@bpy.app.handlers.persistent
def update_grasp_point_positions(scene):
    """Update grasp point positions when objects move.

    Scene mutations are deferred to a timer to avoid re-triggering the depsgraph
    from within a depsgraph handler (which causes infinite recursion / stack overflow).
    """
    global _in_depsgraph_handler
    if _in_depsgraph_handler:
        return
    try:
        debug_print("Handler triggered")
        if hasattr(scene, "grasp_point_props") and len(scene.grasp_point_props.grasp_pairs) > 0:
            debug_print("Scheduling deferred grasp update")
            if not bpy.app.timers.is_registered(_deferred_grasp_update):
                bpy.app.timers.register(_deferred_grasp_update, first_interval=0.0)
        else:
            debug_print("No grasp_point_props found on scene")
    except Exception as e:
        debug_print(f"Error in update_grasp_point_positions handler: {e}")


def intersection_timer_callback():
    """Timer callback to update intersections when context is available"""
    try:
        debug_print("Timer callback triggered")

        # Check if we're in a valid state for intersection detection
        if not hasattr(bpy.context, "scene"):
            debug_print("No scene in context, retrying...")
            return 0.5  # Try again in 0.5 seconds

        if not hasattr(bpy.context.scene, "grasp_point_props"):
            debug_print("No grasp_point_props in scene, stopping timer")
            return None  # Stop timer

        # Check context mode - be more permissive
        debug_print(f"Current mode: {bpy.context.mode}")
        if bpy.context.mode not in ["OBJECT", "EDIT_MESH"]:
            debug_print("Not in suitable mode, retrying...")
            return 0.5  # Try again based on this number

        scene = bpy.context.scene
        grasp_props = scene.grasp_point_props
        debug_print(f"Processing {len(grasp_props.grasp_pairs)} pairs")
        debug_print(f"Grasp props: {grasp_props.grasp_pairs}")
        debug_print(f"Grasp props index: {grasp_props.active_pair_index}")

        # Update intersections for pairs that need it
        updated_count = 0
        dirty_count = 0

        for i, pair in enumerate(grasp_props.grasp_pairs):
            index = i
            debug_print(f"grasp pair line object: {pair.line_object.name}")
            debug_print(f"Current index: {index}")
            debug_print(f"Pair name: {pair.name}")

            if index == 0:
                line_name = "grasp_identifier"
            else:
                # TODO: even this might not be 100% reliable...might need to refactor.
                index_str = f"{index:03d}"
                line_name = f"grasp_identifier.{index_str}"

            debug_print(f"Looking for line object with name: {line_name}")
            line_object = bpy.data.objects.get(line_name)

            if not line_object:
                # Use consistent naming pattern: grasp_identifier.001, grasp_identifier.002, etc.
                base_name = f"grasp_identifier.{index_str}"
                line_object = bpy.data.objects.get(base_name)

                # If not found, try with numbering suffixes
                if not line_object:
                    for obj in bpy.data.objects:
                        if obj.name.startswith(base_name + "."):
                            line_object = obj
                            debug_print(f"Found line with numbering suffix: {obj.name}")
                            break

                if line_object:
                    debug_print(f"Found line: {line_object.name}")
                else:
                    debug_print(f"Line object not found for base name: {base_name}")

            if line_object and line_object.get("intersections_dirty", False):
                dirty_count += 1
                debug_print(f"Processing dirty line: {line_object.name}")

                try:
                    # Make sure detect_intersections_hybrid function exists and works
                    intersections = detect_intersections_hybrid(bpy.context, pair)
                    debug_print(f"Found {len(intersections) if intersections else 0} intersections")
                    debug_print(f"Intersections: {intersections}")

                    if intersections:
                        primary_intersection = intersections[0]
                        line_object["intersection_object"] = primary_intersection["object"].name
                        line_object["intersection_location"] = primary_intersection["location"]
                        line_object["intersection_normal"] = primary_intersection["normal"]
                        line_object["intersection_face_index"] = primary_intersection["face_index"]
                        debug_print(f"Stored intersection with {primary_intersection['object'].name}")
                    else:
                        # Clear intersection data
                        cleared_props = []
                        for prop in [
                            "intersection_object",
                            "intersection_location",
                            "intersection_normal",
                            "intersection_face_index",
                        ]:
                            if prop in line_object:
                                del line_object[prop]
                                cleared_props.append(prop)
                        debug_print(f"Cleared intersection properties: {cleared_props}")

                    line_object["intersections_dirty"] = False
                    updated_count += 1

                except Exception as e:
                    debug_print(f"Error updating intersections for {line_object.name}: {e}")
                    line_object["intersections_dirty"] = False  # Clear to avoid infinite retries

        debug_print(f"Updated {updated_count} of {dirty_count} dirty intersections")

        # Check if there are still dirty intersections
        remaining_dirty = 0
        for pair in grasp_props.grasp_pairs:
            line_name = f"grasp_line_{pair.name}"
            line_object = bpy.data.objects.get(line_name)
            if line_object and line_object.get("intersections_dirty", False):
                remaining_dirty += 1

        debug_print(f"Remaining dirty intersections: {remaining_dirty}")

        if remaining_dirty > 0:
            return 1.0  # Continue timer, but less frequently
        else:
            debug_print("All intersections updated, stopping timer")
            return None  # Stop timer

    except Exception as e:
        debug_print(f"Error in intersection timer callback: {e}")
        import traceback

        traceback.print_exc()
        return None  # Stop timer on error


def start_intersection_timer():
    """Start the intersection update timer if not already running"""
    global _intersection_timer

    if _intersection_timer is None:
        debug_print("Starting intersection timer")
        try:
            _intersection_timer = bpy.app.timers.register(intersection_timer_callback, first_interval=0.1)
            debug_print("Timer registered successfully")
        except Exception as e:
            debug_print(f"Failed to register timer: {e}")
            _intersection_timer = None
    else:
        debug_print("Timer already running")


def stop_intersection_timer():
    """Stop the intersection update timer"""
    global _intersection_timer

    if _intersection_timer is not None:
        debug_print("Stopping intersection timer")
        try:
            if bpy.app.timers.is_registered(intersection_timer_callback):
                bpy.app.timers.unregister(intersection_timer_callback)
                debug_print("Timer unregistered successfully")
        except Exception as e:
            debug_print(f"Error unregistering timer: {e}")
        _intersection_timer = None


def force_update_intersections():
    """Force immediate intersection update - call this from UI for testing"""
    debug_print("Force updating intersections")

    if not hasattr(bpy.context.scene, "grasp_point_props"):
        debug_print("No grasp props found")
        return

    grasp_props = bpy.context.scene.grasp_point_props
    for pair in grasp_props.grasp_pairs:
        line_object = bpy.data.objects.get(f"grasp_line_{pair.name}")
        if line_object:
            line_object["intersections_dirty"] = True
            debug_print(f"Marked {line_object.name} as dirty")

    # Start timer
    start_intersection_timer()


# Register cleanup on file load
@bpy.app.handlers.persistent
def cleanup_timers(dummy):
    """Clean up timers when loading new file"""
    stop_intersection_timer()


@bpy.app.handlers.persistent
def enforce_referenceprims_contents(scene):
    col = bpy.data.collections.get("ReferencePrims")
    if not col:
        return

    allowed_types = {"EMPTY"}
    invalid_objs = []

    for obj in list(col.objects):
        if obj.type not in allowed_types:
            # Save original name
            original_name = obj.get("_original_name")
            fallback_name = re.sub(r"(_(obj|joint|collider)_\d{2})$", "", obj.name)

            # Unlink from ReferencePrims
            col.objects.unlink(obj)

            # Link back to Scene Collection
            bpy.context.scene.collection.objects.link(obj)

            # Restore original name or fallback
            obj.name = original_name if original_name else fallback_name

            # Clean up custom props
            obj.get("_original_name") and obj.pop("_original_name")

            # Collect for grouped message
            invalid_objs.append(obj.name)

    # Show a single grouped popup
    if invalid_objs:
        msg = "These objects are not empties and were moved back:\n" + "\n".join(f"• {name}" for name in invalid_objs)
        show_popup("Invalid ReferencePrims Objects", msg)


def auto_rename_object(obj, suffix, alt_name=None) -> str:
    auto_name = obj.name
    try:
        if not obj:
            return None

        if alt_name:
            auto_name = alt_name
        # Skip if already compliant
        if re.match(rf"^.+_{suffix}_\d{{2}}$", auto_name):
            return obj.name

        is_dup = bool(re.search(r"\.\d{3}$", auto_name))
        was_done = obj.get("_renamed", False)
        expected_name = obj.get("_renamed_as", None)

        # Reset _renamed flag if:
        # 1. Object has .001 suffix (was duplicated by Blender)
        # 2. Object name doesn't match what we renamed it to (artist renamed it manually)
        if was_done and (is_dup or (expected_name and obj.name != expected_name)):
            obj["_renamed"] = False
            was_done = False

        if was_done and not is_dup:
            return

        all_obj_names = {o.name for o in bpy.data.objects}
        all_mesh_names = {m.name for m in bpy.data.meshes}

        # Strip .001, .002 etc.
        base_name = re.sub(r"\.\d{3}$", "", auto_name)
        m = re.match(rf"(.+?)_{suffix}_(\d{{2}})$", base_name)
        if m:
            base = m.group(1)
        else:
            base = re.sub(rf"(_{suffix}|_mesh)(_\d{{2}})?$", "", base_name)

        # Find next free index
        i = 0
        while True:
            new_obj_name = f"{base}_{suffix}_{i:02d}"
            new_mesh_name = f"{base}_mesh_{i:02d}"
            obj_available = new_obj_name not in all_obj_names
            mesh_available = (
                suffix != "obj" or obj.type != "MESH" or not obj.data or new_mesh_name not in all_mesh_names
            )
            if obj_available and mesh_available:
                break
            i += 1

        # Rename object
        if obj.name != new_obj_name:
            obj.name = new_obj_name
            all_obj_names.add(new_obj_name)

        # Rename mesh data if needed
        if suffix == "obj" and obj.type == "MESH" and obj.data:
            if obj.data.name != new_mesh_name:
                obj.data.name = new_mesh_name
                all_mesh_names.add(new_mesh_name)

        obj["_renamed"] = True
        obj["_renamed_as"] = obj.name  # Store the name we renamed it to
        return obj.name

    except Exception as e:
        print(f"❌ Rename failed for {obj.name}: {e}")
        return None


def auto_rename_objects(scene):
    try:
        # collection → suffix mapping
        simready_collections = {
            "Geometry": "obj",
            "ReferencePrims": "joint",
            "Colliders": "collider",
        }

        # cache existing names to avoid collisions
        all_obj_names = {o.name for o in bpy.data.objects}
        all_mesh_names = {m.name for m in bpy.data.meshes}

        # Get the Export collection
        export_collection = bpy.data.collections.get("Export")
        if not export_collection:
            # print("❌ Export collection not found")
            return

        for col_name, suffix in simready_collections.items():
            # Look for collection under Export
            col = None
            for child in export_collection.children:
                if child.name == col_name:
                    col = child
                    break

            if not col:
                continue

            for obj in col.objects:
                name = obj.name

                # Skip rename if naming is already compliant
                if re.match(rf"^.+_{suffix}_\d{{2}}$", name):
                    continue

                # strip off any .### from object or mesh
                base_name = re.sub(r"\.\d{3}$", "", name)

                # if matches Base_suffix_XX, grab that base
                m = re.match(rf"(.+?)_{suffix}_(\d{{2}})$", base_name)
                if m:
                    base = m.group(1)
                else:
                    # drop any existing _suffix or _mesh_XX
                    base = re.sub(rf"(_{suffix}|_mesh)(_\d{{2}})?$", "", base_name)

                # find next free index that works for both object and mesh
                i = 0
                while True:
                    new_obj_name = f"{base}_{suffix}_{i:02d}"
                    new_mesh_name = f"{base}_mesh_{i:02d}"

                    # check if both names are available (or mesh name not needed)
                    obj_available = new_obj_name not in all_obj_names
                    mesh_available = (
                        suffix != "obj" or obj.type != "MESH" or not obj.data or new_mesh_name not in all_mesh_names
                    )

                    if obj_available and mesh_available:
                        break
                    i += 1

                # rename the object
                if obj.name != new_obj_name:
                    obj.name = new_obj_name
                    all_obj_names.add(new_obj_name)

                # rename mesh data to use the same index as the object
                if suffix == "obj" and obj.type == "MESH" and obj.data:
                    if obj.data.name != new_mesh_name:
                        obj.data.name = new_mesh_name
                        all_mesh_names.add(new_mesh_name)

                # mark as renamed to prevent re-renaming
                obj["_renamed"] = True
                obj["_renamed_as"] = obj.name  # Store the name we renamed it to

    except Exception as e:
        print(f"❌ Rename failed: {e}")


def show_popup(title, message):
    def draw(self, context):
        for line in message.split("\n"):
            self.layout.label(text=line)

    bpy.context.window_manager.popup_menu(draw, title=title, icon="ERROR")


def ensure_export_geometry_collection():
    """Ensure Export/Geometry collection structure exists"""
    # Create parent Export collection if it doesn't exist
    export_collection = bpy.data.collections.get("Export")
    if not export_collection:
        export_collection = bpy.data.collections.new("Export")
        bpy.context.scene.collection.children.link(export_collection)

    # Create Geometry collection under Export if it doesn't exist
    geometry_collection = bpy.data.collections.get("Geometry")
    if not geometry_collection:
        geometry_collection = bpy.data.collections.new("Geometry")
        export_collection.children.link(geometry_collection)
    elif geometry_collection.name not in export_collection.children:
        # If Geometry collection exists but isn't under Export, move it
        for parent in geometry_collection.users_collection:
            parent.children.unlink(geometry_collection)
        export_collection.children.link(geometry_collection)

    return geometry_collection


def bounding_boxes_overlap(obj1, obj2):
    """Check if two objects' bounding boxes overlap"""
    if not obj1.bound_box or not obj2.bound_box:
        return False

    # Get world space bounding boxes
    bbox1 = [obj1.matrix_world @ Vector(corner) for corner in obj1.bound_box]
    bbox2 = [obj2.matrix_world @ Vector(corner) for corner in obj2.bound_box]

    # Get min/max for each axis
    min1 = Vector((min(v[0] for v in bbox1), min(v[1] for v in bbox1), min(v[2] for v in bbox1)))
    max1 = Vector((max(v[0] for v in bbox1), max(v[1] for v in bbox1), max(v[2] for v in bbox1)))
    min2 = Vector((min(v[0] for v in bbox2), min(v[1] for v in bbox2), min(v[2] for v in bbox2)))
    max2 = Vector((max(v[0] for v in bbox2), max(v[1] for v in bbox2), max(v[2] for v in bbox2)))

    # Check overlap on all axes
    return (
        min1.x <= max2.x
        and max1.x >= min2.x
        and min1.y <= max2.y
        and max1.y >= min2.y
        and min1.z <= max2.z
        and max1.z >= min2.z
    )


def detect_intersections_hybrid(context, grasp_pair):
    """Detect intersections using existing curve + raycast for precision"""
    if not grasp_pair.line_object:
        return []

    curve_obj = grasp_pair.line_object
    intersections = []

    # First pass: use bounding box overlap for quick filtering
    potential_intersections = []
    for obj in context.scene.objects:
        if obj.type == "MESH" and bounding_boxes_overlap(curve_obj, obj):
            potential_intersections.append(obj)

    # Second pass: use raycast for precise intersection detection
    point_a = grasp_pair.point_1_position
    point_b = grasp_pair.point_2_position
    direction = (point_b - point_a).normalized()
    distance = (point_b - point_a).length

    for obj in potential_intersections:
        # Cast ray to see if it actually hits this object
        hit, location, normal, face_index, hit_obj, matrix = context.scene.ray_cast(
            context.evaluated_depsgraph_get(), point_a, direction, distance=distance
        )

        if hit and hit_obj == obj:
            intersections.append({"object": obj, "location": location, "normal": normal, "face_index": face_index})

    return intersections


def regenerate_grasp_line(grasp_pair):
    """Regenerate the line between grasp points"""
    if not grasp_pair.grasp_point_1 or not grasp_pair.grasp_point_2:
        return None

    point_a = grasp_pair.grasp_point_1.location
    point_b = grasp_pair.grasp_point_2.location

    # If line object doesn't exist, create it
    if not grasp_pair.line_object:
        # Create curve directly instead of converting from mesh
        curve_data = bpy.data.curves.new("grasp_identifier_curve", "CURVE")
        line_object = bpy.data.objects.new("grasp_identifier", curve_data)

        # Ensure Export/Geometry collection exists and link the object to it
        geometry_collection = ensure_export_geometry_collection()
        geometry_collection.objects.link(line_object)

        # Create a new spline
        spline = curve_data.splines.new("POLY")
        spline.points.add(1)  # We need 2 points total (0 and 1)

        # Set the points
        spline.points[0].co = (point_a.x, point_a.y, point_a.z, 1.0)
        spline.points[1].co = (point_b.x, point_b.y, point_b.z, 1.0)

        # Store reference to the line object
        grasp_pair.line_object = line_object
    else:
        # Update existing curve object
        line_object = grasp_pair.line_object

        # Check if it's a curve object
        if line_object.type == "CURVE" and line_object.data:
            curve_data = line_object.data

            # Clear existing splines
            curve_data.splines.clear()

            # Create a new spline
            spline = curve_data.splines.new("POLY")
            spline.points.add(1)  # We need 2 points total (0 and 1)

            # Set the points
            spline.points[0].co = (point_a.x, point_a.y, point_a.z, 1.0)
            spline.points[1].co = (point_b.x, point_b.y, point_b.z, 1.0)

            # No need to call update() - the dependency graph will handle it
        else:
            # Fallback: recreate the line if it's not a curve
            bpy.data.objects.remove(line_object, do_unlink=True)
            grasp_pair.line_object = None
            return regenerate_grasp_line(grasp_pair)

    return grasp_pair.line_object


def ensure_joint_naming_convention(asset_name: str) -> str:
    """
    Ensures the asset name follows: <name>_joint_<index> or <name>_obj_<index>
    """
    if "obj" in asset_name:
        return re.sub(r"_obj(?=_|$)", "_joint", asset_name)
    else:
        match = re.match(r"(.+?)(?:\.(\d+))?$", asset_name)
        if match:
            base, index = match.groups()
            index = index.lstrip("0").zfill(2) if index else "00"
            return f"{base}_joint_{index}"
        else:
            return f"{asset_name}_joint_01"


def find_childof_target(obj):
    for con in obj.constraints:
        if con.type == "CHILD_OF" and con.target and con.target.type == "EMPTY":
            return con.target
    return None


def is_constraint_system_setup(body_0, body_1, selected_empty):
    """
    Check if the CHILD_OF constraint system is already set up between the bodies and selected empty.

    The expected hierarchy is:
    - body_0 -> body_0_empty
    - body_1 -> body_1_empty
    - body_1_empty -> selected_empty (which should be body_1_empty itself)
    - selected_empty -> body_0_empty

    Args:
        body_0: First body object
        body_1: Second body object
        selected_empty: Selected empty object (should be body_1_empty)

    Returns:
        bool: True if constraint system is already set up, False otherwise
    """
    if not all([body_0, body_1, selected_empty]):
        return False

    # Check if body_0 has a CHILD_OF constraint to an empty
    body_0_empty = find_childof_target(body_0)
    if not body_0_empty:
        return False

    # Check if body_1 has a CHILD_OF constraint to an empty
    body_1_empty = find_childof_target(body_1)
    if not body_1_empty:
        return False

    # The selected_empty should be the body_1_empty
    if selected_empty != body_1_empty:
        return False

    # Check if body_1_empty (selected_empty) has a CHILD_OF constraint to body_0_empty
    for constraint in body_1_empty.constraints:
        if constraint.type == "CHILD_OF" and constraint.target and constraint.target == body_0_empty:
            return True

    return False


def update_constraint_system_state(context):
    """
    Update the constraint system state property and trigger UI refresh.

    Args:
        context: Blender context
    """
    props = context.scene.joint_attribute_props
    obj = context.active_object

    # Check current constraint system state
    current_state = False
    if props.body_0 and props.body_1 and obj and obj.type == "EMPTY":
        current_state = is_constraint_system_setup(props.body_0, props.body_1, obj)

    # Update property if state changed
    if props.constraint_system_setup != current_state:
        props.constraint_system_setup = current_state

        # Trigger UI refresh
        props.ui_refresh_trigger += 1

        # Force area redraw
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


# --------------------------
# Operators
# --------------------------

### START GRASP OPERATORS ###
#############################


class SRCORE_OT_create_grasp_points(Operator):
    bl_idname = "sr_core.create_grasp_points"
    bl_label = "Create Grasp Points"
    bl_description = "Create two empty objects with sphere display for grasp point setup"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        grasp_props = scene.grasp_point_props

        # Create a new grasp pair
        new_pair = grasp_props.grasp_pairs.add()

        # Create first grasp point
        bpy.ops.object.empty_add(type="SPHERE", location=(-0.5, 0, 0))
        grasp_point_1 = context.active_object
        grasp_point_1.name = f"Grasp_Point_{len(grasp_props.grasp_pairs)}_1"
        grasp_point_1.empty_display_size = grasp_props.global_sphere_size

        # Create second grasp point
        bpy.ops.object.empty_add(type="SPHERE", location=(0.5, 0, 0))
        grasp_point_2 = context.active_object
        grasp_point_2.name = f"Grasp_Point_{len(grasp_props.grasp_pairs)}_2"
        grasp_point_2.empty_display_size = grasp_props.global_sphere_size

        # Assign to the new pair
        new_pair.grasp_point_1 = grasp_point_1
        new_pair.grasp_point_2 = grasp_point_2

        # Update positions
        new_pair.point_1_position = grasp_point_1.location
        new_pair.point_2_position = grasp_point_2.location

        # Calculate distance
        distance = (grasp_point_2.location - grasp_point_1.location).length
        new_pair.point_distance = distance

        # Set as active pair
        grasp_props.active_pair_index = len(grasp_props.grasp_pairs) - 1

        # Create the line between grasp points
        line_object = regenerate_grasp_line(new_pair)

        # Detect intersections with the grasp line using hybrid approach
        intersections = detect_intersections_hybrid(context, new_pair)

        # Store intersection data on the line object
        if line_object and intersections:
            # Store only the first (primary) intersecting object
            primary_intersection = intersections[0]
            line_object["intersection_object"] = primary_intersection["object"].name
            line_object["intersection_location"] = primary_intersection["location"]
            line_object["intersection_normal"] = primary_intersection["normal"]
            line_object["intersection_face_index"] = primary_intersection["face_index"]

            # Report the primary intersection
            obj_name = primary_intersection["object"].name
            location = primary_intersection["location"]
            intersection_msg = (
                f"Line intersects with: {obj_name} at ({location.x:.3f}, {location.y:.3f}, {location.z:.3f})"
            )
            print(f"🔍 {intersection_msg}")
            self.report({"INFO"}, intersection_msg)
        else:
            # Clear intersection data if no intersections
            if line_object:
                # Remove intersection properties if they exist
                for prop in [
                    "intersection_object",
                    "intersection_location",
                    "intersection_normal",
                    "intersection_face_index",
                ]:
                    if prop in line_object:
                        del line_object[prop]

            print("🔍 No intersections detected with grasp line")

        print(f"✅ Line created between {grasp_point_1.name} and {grasp_point_2.name}")

        self.report({"INFO"}, f"Created grasp pair {len(grasp_props.grasp_pairs)} with distance: {distance:.3f}m")
        return {"FINISHED"}


class SRCORE_OT_update_grasp_positions(Operator):
    bl_idname = "sr_core.update_grasp_positions"
    bl_label = "Update Grasp Positions"
    bl_description = "Update the tracked positions of all grasp points"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        grasp_props = scene.grasp_point_props

        # Update all grasp pairs
        for pair in grasp_props.grasp_pairs:
            # Update position 1
            if pair.grasp_point_1:
                pair.point_1_position = pair.grasp_point_1.location

            # Update position 2
            if pair.grasp_point_2:
                pair.point_2_position = pair.grasp_point_2.location

            # Calculate distance if both points exist
            if pair.grasp_point_1 and pair.grasp_point_2:
                distance = (pair.point_2_position - pair.point_1_position).length
                pair.point_distance = distance

        return {"FINISHED"}


class SRCORE_OT_set_sphere_size(Operator):
    bl_idname = "sr_core.set_sphere_size"
    bl_label = "Set Sphere Size"
    bl_description = "Set the display size for all grasp point spheres"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        grasp_props = scene.grasp_point_props

        # Update sphere size for all grasp pairs
        for pair in grasp_props.grasp_pairs:
            if pair.grasp_point_1:
                pair.grasp_point_1.empty_display_size = grasp_props.global_sphere_size

            if pair.grasp_point_2:
                pair.grasp_point_2.empty_display_size = grasp_props.global_sphere_size

        return {"FINISHED"}


class SRCORE_OT_clear_grasp_points(Operator):
    bl_idname = "sr_core.clear_grasp_points"
    bl_label = "Clear All Grasp Points"
    bl_description = "Remove all grasp points and clear properties"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        grasp_props = scene.grasp_point_props

        # Remove all objects from scene
        for pair in grasp_props.grasp_pairs:
            if pair.grasp_point_1:
                bpy.data.objects.remove(pair.grasp_point_1, do_unlink=True)

            if pair.grasp_point_2:
                bpy.data.objects.remove(pair.grasp_point_2, do_unlink=True)

            # Remove line object if it exists
            if pair.line_object:
                bpy.data.objects.remove(pair.line_object, do_unlink=True)

        # Clear all pairs
        grasp_props.grasp_pairs.clear()
        grasp_props.active_pair_index = 0

        self.report({"INFO"}, "Cleared all grasp points")
        return {"FINISHED"}


class SRCORE_OT_remove_grasp_pair(Operator):
    bl_idname = "sr_core.remove_grasp_pair"
    bl_label = "Remove Grasp Pair"
    bl_description = "Remove the selected grasp pair"
    bl_options = {"REGISTER", "UNDO"}

    pair_index: bpy.props.IntProperty(
        name="Pair Index", description="Index of the grasp pair to remove", default=0, min=0
    )

    def execute(self, context):
        scene = context.scene
        grasp_props = scene.grasp_point_props

        if self.pair_index < len(grasp_props.grasp_pairs):
            pair = grasp_props.grasp_pairs[self.pair_index]

            # Remove objects from scene
            if pair.grasp_point_1:
                bpy.data.objects.remove(pair.grasp_point_1, do_unlink=True)

            if pair.grasp_point_2:
                bpy.data.objects.remove(pair.grasp_point_2, do_unlink=True)

            # Remove line object if it exists
            if pair.line_object:
                bpy.data.objects.remove(pair.line_object, do_unlink=True)

            # Remove the pair from collection
            grasp_props.grasp_pairs.remove(self.pair_index)

            # Adjust active index if needed
            if grasp_props.active_pair_index >= len(grasp_props.grasp_pairs):
                grasp_props.active_pair_index = max(0, len(grasp_props.grasp_pairs) - 1)

            self.report({"INFO"}, f"Removed grasp pair {self.pair_index + 1}")

        return {"FINISHED"}


### START JOINT OPERATORS ###
#############################


class SRCORE_OT_apply_joint_settings(Operator):
    bl_idname = "sr_core.apply_joint_settings"
    bl_label = "Apply Joint Settings to Selected"
    bl_description = "Writes the joint settings to custom properties on selected empties"
    bl_options = {"REGISTER", "UNDO"}

    """
    Main operator that applies all the joint attributes:
    1. Builds the constraint system
    2. Accesses and builds the visualizer widgets
    3. Applies pxr attributes to the reference prims
    """

    def clear_simready_joint_properties(self, obj):
        keys_to_remove = [
            k
            for k in obj.keys()
            if k.startswith("pxr:usd:") or k.startswith("omni:simready:physx") or k.startswith("drive:")
        ]

        # Removes all data first, then adds new data
        for key in keys_to_remove:
            del obj[key]

    def delete_visualizer_widgets(self, obj, preserve_if_body1=True):
        """Delete widgets/visualizers associated with the given object.

        Args:
            obj: The object (usually an empty) to delete visualizers from
            preserve_if_body1: If True, check if obj is body1/child in another joint and preserve accordingly
        """
        # Check if this object (or the mesh it constrains) is body1 (child) in another joint
        is_body1_in_other_joint = False

        if preserve_if_body1:
            # Check if this object has a CHILD_OF constraint (meaning it's a child in a joint)
            if obj.type == "EMPTY":
                # For empties, check if they constrain a mesh that has CHILD_OF
                for con in obj.constraints:
                    if con.type == "CHILD_OF" and con.target and con.target.type == "EMPTY":
                        is_body1_in_other_joint = True
                        break

                # Also check constrained mesh objects
                for o in bpy.data.objects:
                    if o.type == "MESH":
                        for con in o.constraints:
                            if con.type == "CHILD_OF" and con.target == obj:
                                # This empty is the target of a CHILD_OF, so it's part of a joint
                                is_body1_in_other_joint = True
                                break
                    if is_body1_in_other_joint:
                        break
            else:
                # For mesh objects, directly check for CHILD_OF constraint
                for con in obj.constraints:
                    if con.type == "CHILD_OF" and con.target and con.target.type == "EMPTY":
                        is_body1_in_other_joint = True
                        break

        if is_body1_in_other_joint:
            print(f"Preserving visualizers and constraints on {obj.name} (body1/child in another joint)")
            return

        # 1. Delete widget empties and their children
        # Build a comprehensive list of all empties to delete
        objects_to_find = []

        # Find by property (jw_target)
        for ob in bpy.data.objects:
            if ob.type == "EMPTY" and ob.get("jw_target") == obj.name:
                if ob not in objects_to_find:
                    objects_to_find.append(ob)

        # Find by name patterns (in case properties aren't set or objects were renamed)
        name_patterns = [
            f"AxisFrame_{obj.name}",
            f"RingRoot_{obj.name}",
            f"Origin_{obj.name}",
        ]

        for pattern in name_patterns:
            # Check for exact match and Blender's auto-renamed versions (e.g., .001, .002)
            for ob in bpy.data.objects:
                if ob.type == "EMPTY":
                    # Check exact match or starts with pattern followed by . or end of string
                    if ob.name == pattern or ob.name.startswith(pattern + "."):
                        if ob not in objects_to_find:
                            objects_to_find.append(ob)
                            print(f"Found visualizer widget to delete: {ob.name}")

        # Collect all objects to delete (including children) first
        objects_to_delete = set()

        def collect_with_children(o):
            """Recursively collect object and its children."""
            if o in objects_to_delete:
                return
            objects_to_delete.add(o)
            # Use try/except to handle invalid references
            try:
                for ch in list(o.children):
                    collect_with_children(ch)
            except (ReferenceError, AttributeError):
                pass

        # Collect all objects and their children
        for ob_to_collect in objects_to_find:
            try:
                collect_with_children(ob_to_collect)
            except (ReferenceError, AttributeError):
                pass

        # Now delete them all at once
        deleted_count = 0
        for ob_to_delete in list(objects_to_delete):
            try:
                if ob_to_delete.name in bpy.data.objects:
                    obj_name = ob_to_delete.name
                    bpy.data.objects.remove(ob_to_delete, do_unlink=True)
                    deleted_count += 1
                    print(f"Deleted visualizer object: {obj_name}")
            except (ReferenceError, AttributeError):
                # Object was already deleted or is invalid
                pass

        if deleted_count > 0:
            print(f"Total deleted: {deleted_count} visualizer objects for {obj.name}")

        # Force update after deletion to ensure it's processed before creating new widgets
        if objects_to_delete:
            bpy.context.view_layer.update()

        # 2. Remove JointLimit constraint from the object
        for con in list(obj.constraints):
            if con.name == "JointLimit":
                obj.constraints.remove(con)
                print(f"Removed JointLimit constraint from {obj.name}")

        # 3. Remove RNA property overrides from the object (if they exist as ID properties)
        # Note: RNA properties registered on bpy.types.Object persist, but we need to
        # reset them to defaults or clear any custom values set on this specific object
        rna_props_to_reset = [
            "jw_rotation_limit_min_rna",
            "jw_rotation_limit_max_rna",
            "jw_translation_limit_min_rna",
            "jw_translation_limit_max_rna",
            "jw_translation_default",
            "jw_rotation_default",
        ]

        # Try to remove them from ID properties if they were stored there
        for prop_name in rna_props_to_reset:
            if prop_name in obj.keys():
                del obj[prop_name]
                print(f"Cleared RNA property: {prop_name} from {obj.name}")

    def execute(self, context):
        props = context.scene.joint_attribute_props
        physx_enabled = props.physx_enabled
        joint_type = props.joint_type
        joint_axis = props.joint_axis
        prismatic_min_dist = props.min_dist_prismatic
        prismatic_max_dist = props.max_dist_prismatic

        # check if unibody is enabled
        unibody = props.uni_body

        if physx_enabled:
            physx_enabled = False

        # Disable operator if unibody is enabled
        if unibody:
            self.report({"ERROR"}, "This operator is disabled when unibody is enabled!")
            return {"CANCELLED"}

        allowed_fields = set(JOINT_TYPE_FIELDS.get(joint_type, []))

        if not props.body_0 or not props.body_1:
            self.report({"ERROR"}, "Both body_0 and body_1 must be assigned!")
            return {"CANCELLED"}

        # Check for self-joint (body0 == body1)
        if props.body_0 == props.body_1:
            print(f"Warning: Creating a self-joint (body0 and body1 are the same object: {props.body_0.name})")
            # This is allowed but may have special handling

        # This section creates the empty hierarchy and CHILD_OF constraints
        parent = props.body_0
        child = props.body_1

        # Auto rename objects before we start, and update joint_attribute_props
        parent_name = auto_rename_object(parent, "obj")
        child_name = auto_rename_object(child, "obj")

        print(f"parent_name: {parent_name}")
        print(f"child_name: {child_name}")

        # Check if rename was successful
        if parent_name is None:
            self.report({"ERROR"}, "Failed to rename parent object.")
            return {"CANCELLED"}
        if child_name is None:
            self.report({"ERROR"}, "Failed to rename child object.")
            return {"CANCELLED"}

        simready_collection_names = ["Geometry", "ReferencePrims", "Colliders"]

        export_col = bpy.data.collections.get("Export")
        if not export_col:
            export_col = bpy.data.collections.new("Export")
            context.scene.collection.children.link(export_col)

        simready_subcols = {}
        for name in simready_collection_names:
            col = bpy.data.collections.get(name)
            if not col:
                col = bpy.data.collections.new(name)
                export_col.children.link(col)
            elif col.name not in export_col.children:
                for parent_col in col.users_collection:
                    parent_col.children.unlink(col)
                export_col.children.link(col)
            simready_subcols[name] = col

        geometry_col = simready_subcols["Geometry"]
        refprim_col = simready_subcols["ReferencePrims"]

        for obj in (parent, child):
            # Unlink from all collections
            for col in obj.users_collection:
                if col != geometry_col:
                    col.objects.unlink(obj)

            # Link to geometry_col if not already
            if obj.name not in geometry_col.objects:
                geometry_col.objects.link(obj)

        child_location = child.location.copy()
        child_rotation = child.rotation_euler.copy()
        child_name = child.name

        parent_location = parent.location.copy()
        parent_rotation = parent.rotation_euler.copy()
        parent_name = parent.name

        # Helper function to check if an empty name is compatible with an object name
        def empty_belongs_to_object(empty, obj):
            """Check if the empty's name matches the expected pattern for this object.

            For example:
            - Cube_obj_05 should have Cube_joint_05
            - If the empty is Cube_joint_00, it doesn't belong to Cube_obj_05
            """
            if not empty or not obj:
                return False

            # Extract base and index from object name (e.g., Cube_obj_05 -> Cube, 05)
            obj_match = re.match(r"^(.+?)_obj_(\d{2})$", obj.name)
            if not obj_match:
                return False

            obj_base = obj_match.group(1)
            obj_index = obj_match.group(2)

            # Check if empty name matches expected pattern (e.g., Cube_joint_05)
            expected_empty_name = f"{obj_base}_joint_{obj_index}"

            return empty.name == expected_empty_name

        # Find existing reference prims (empties) for both parent and child
        existing_parent_empty = find_childof_target(parent)
        existing_child_empty = find_childof_target(child)

        # Save names BEFORE deletion (in case one deletion affects the other)
        parent_empty_name = existing_parent_empty.name if existing_parent_empty else None
        child_empty_name = existing_child_empty.name if existing_child_empty else None

        # Validate that existing empties actually belong to these objects
        # This handles the case where an object was duplicated and inherited constraints
        # pointing to the original object's empty
        parent_empty_is_valid = empty_belongs_to_object(existing_parent_empty, parent)
        child_empty_is_valid = empty_belongs_to_object(existing_child_empty, child)

        # If the parent's empty doesn't belong to it (wrong name), invalidate it
        if existing_parent_empty and not parent_empty_is_valid:
            print(
                f"Parent empty {parent_empty_name} doesn't match parent object {parent.name} - will delete and recreate"
            )
            # Don't reuse it - treat as if it doesn't exist for reuse purposes
            # but we still need to delete it to clean up the wrong constraint

        # Same for child
        if existing_child_empty and not child_empty_is_valid:
            print(f"Child empty {child_empty_name} doesn't match child object {child.name} - will delete and recreate")

        # Determine if parent is body1 in another joint (has existing empty with correct name)
        # If so, we'll REUSE that empty as parent_empty instead of deleting and recreating
        parent_is_body1_elsewhere = existing_parent_empty is not None and parent_empty_is_valid

        # Check if child is also body1 in another joint (joint chaining scenario)
        # This happens when you create Joint A->B, then Joint B->C
        # In the second joint, B is the parent (body0) and C is the child (body1)
        # But B already has an empty from the first joint where it was body1
        child_is_body1_elsewhere = existing_child_empty is not None and child_empty_is_valid

        # Check if parent and child share the same empty (direct joint chain)
        # This happens when body1 of joint1 becomes body0 of joint2
        empties_are_same = (
            existing_parent_empty is not None
            and existing_child_empty is not None
            and existing_parent_empty == existing_child_empty
        )

        # Handle existing empties not like a Noob
        # Always delete empties with invalid names (from duplicated objects)
        if existing_parent_empty and (not parent_empty_is_valid or not parent_is_body1_elsewhere):
            # Delete parent empty if:
            # 1. It has an invalid name (doesn't match this object), OR
            # 2. Parent is NOT body1 in another joint
            # Delete visualizers first
            self.delete_visualizer_widgets(existing_parent_empty, preserve_if_body1=False)
            # Remove the empty itself
            bpy.data.objects.remove(existing_parent_empty, do_unlink=True)
            print(f"Deleted existing parent empty: {parent_empty_name}")
            # If we deleted it because of invalid name, clear the reference
            if not parent_empty_is_valid:
                existing_parent_empty = None
                # If parent and child empties were the same, also clear child reference
                if empties_are_same:
                    existing_child_empty = None
                    print("Also cleared child empty reference (same as parent)")
        elif parent_is_body1_elsewhere:
            print(f"Reusing existing parent empty: {parent_empty_name} (parent is body1 in another joint)")

        if existing_child_empty and not empties_are_same:
            # Delete child empty if it's not the same as the parent empty
            # Always delete if invalid name (from duplicated object)
            if not child_empty_is_valid:
                print(f"Deleting child empty with invalid name: {child_empty_name}")
            # Delete visualizers first (check if still valid)
            try:
                self.delete_visualizer_widgets(existing_child_empty, preserve_if_body1=False)
                # Remove the empty itself
                bpy.data.objects.remove(existing_child_empty, do_unlink=True)
                print(f"Deleted existing child empty: {child_empty_name}")
                # Clear reference if invalid
                if not child_empty_is_valid:
                    existing_child_empty = None
            except ReferenceError:
                # Child empty was already deleted (cascade from parent deletion)
                print(f"Child empty was already deleted: {child_empty_name}")
        elif empties_are_same:
            print(f"Skipping deletion of child empty: {child_empty_name} (same as parent empty in joint chain)")

        # Clear constraints from mesh objects intelligently
        # For parent: Only clear if it doesn't have existing CHILD_OF (not body1 elsewhere)
        if not parent_is_body1_elsewhere:
            parent.constraints.clear()
            print(f"Cleared constraints from {parent.name}")
        else:
            print(f"Preserving constraints on {parent.name} (body1 in another joint)")

        # For child: Only clear if it's not body1 in another joint (joint chaining)
        if not child_is_body1_elsewhere:
            child.constraints.clear()
            print(f"Cleared constraints from {child.name}")
        else:
            print(f"Preserving constraints on {child.name} (body1 in another joint)")

        # Create or reuse parent empty
        if parent_is_body1_elsewhere and existing_parent_empty:
            # Reuse the existing empty - parent is already constrained to it
            parent_empty = existing_parent_empty
            print(f"Reusing parent empty: {parent_empty.name}")
        else:
            # Create fresh parent empty
            bpy.ops.object.select_all(action="DESELECT")
            bpy.ops.object.empty_add(type="PLAIN_AXES", location=parent_location)
            parent_empty = context.active_object
            parent_empty.rotation_euler = parent_rotation

            # Set adaptive empty display size based on parent object dimensions
            parent_empty.empty_display_size = calculate_adaptive_empty_size(parent)

            if "Empty" in parent_empty.name:
                alt_name = re.sub(r"_obj_\d{2}", "", parent_name)
                auto_rename_object(parent_empty, "joint", alt_name)
            else:
                auto_rename_object(parent_empty, "joint")

        # Link to ReferencePrims and unlink from others
        for col in parent_empty.users_collection:
            if col != refprim_col:
                col.objects.unlink(parent_empty)
        if parent_empty.name not in refprim_col.objects:
            refprim_col.objects.link(parent_empty)

        # Constraint parent mesh to empty (only if not already constrained)
        if not parent_is_body1_elsewhere:
            parent.select_set(True)
            context.view_layer.objects.active = parent
            parent_constraint = parent.constraints.new("CHILD_OF")
            parent_constraint.name = f"ChildOf_{parent_empty.name}"
            parent_constraint.target = parent_empty
        else:
            print(f"Parent {parent.name} already constrained to {parent_empty.name}")

        # Create or reuse child empty
        if child_is_body1_elsewhere and existing_child_empty and not empties_are_same:
            # Verify the child empty still exists before trying to reuse it
            try:
                # Test if object is still valid by accessing a property
                _ = existing_child_empty.name
                # Reuse the existing child empty - child is already constrained to it from another joint
                child_empty = existing_child_empty
                print(f"Reusing child empty: {child_empty.name} (child is body1 in another joint)")
            except ReferenceError:
                # Object was deleted, create a new one
                print("Child empty was deleted, creating new one")
                existing_child_empty = None
                child_is_body1_elsewhere = False
                # Fall through to create new empty

        if not (child_is_body1_elsewhere and existing_child_empty and not empties_are_same):
            # Create fresh child empty
            bpy.ops.object.select_all(action="DESELECT")
            bpy.ops.object.empty_add(type="PLAIN_AXES", location=child_location)
            child_empty = context.active_object
            child_empty.rotation_euler = child_rotation

            # Set adaptive empty display size based on child object dimensions
            child_empty.empty_display_size = calculate_adaptive_empty_size(child)

            # Use auto_rename_object to handle naming properly
            if "Empty" in child_empty.name:
                alt_name = re.sub(r"_obj_\d{2}", "", child_name)
                auto_rename_object(child_empty, "joint", alt_name)
            else:
                auto_rename_object(child_empty, "joint")

        for col in child_empty.users_collection:
            if col != refprim_col:
                col.objects.unlink(child_empty)

        for col in parent_empty.users_collection:
            if col != refprim_col:
                col.objects.unlink(parent_empty)

        if child_empty.name not in refprim_col.objects:
            refprim_col.objects.link(child_empty)

        if parent_empty.name not in refprim_col.objects:
            refprim_col.objects.link(parent_empty)

        # setup child mesh -> reference prim constraint (only if not already constrained)
        if not child_is_body1_elsewhere:
            child_empty.select_set(True)
            context.view_layer.objects.active = child

            child_constraint = child.constraints.new("CHILD_OF")
            child_constraint.name = f"ChildOf_{child_empty.name}"
            child_constraint.target = child_empty
            print(f"Created constraint from {child.name} to {child_empty.name}")
        else:
            print(f"Child {child.name} already constrained to {child_empty.name}")

        # Now setup relationship between child and parent refprims
        constraint_child_ref = child_empty.constraints.new("CHILD_OF")
        constraint_child_ref.name = f"ChildOf_{parent_empty.name}"
        constraint_child_ref.target = parent_empty

        # SELECT CHILD EMPTY for applying joint settings
        bpy.ops.object.select_all(action="DESELECT")
        child_empty.select_set(True)
        context.view_layer.objects.active = child_empty

        # Set local position of body 0 joint
        if joint_type in {"revolute", "spherical", "fixed"}:
            obj = context.active_object

            # Find parent through ChildOf constraint
            parent_target = None
            for constraint in obj.constraints:
                if constraint.type == "CHILD_OF" and constraint.target:
                    parent_target = constraint.target

            # Get local transform by multiplying world transform with inverse of parent's world transform
            local_matrix = parent_target.matrix_world.inverted() @ obj.matrix_world
            local_location = local_matrix.translation

            # Set local position of body 0 joint
            props.joint_local_pos_0 = local_location

        elif joint_type == "prismatic":
            obj = context.active_object
            # Find parent through ChildOf constraint
            parent_target = None
            for constraint in obj.constraints:
                if constraint.type == "CHILD_OF" and constraint.target:
                    parent_target = constraint.target

            local_matrix = parent_target.matrix_world.inverted() @ obj.matrix_world
            local_location = local_matrix.translation

            # Get parent transform information
            parent_location = parent_target.location

            local_location_negate_axis = Vector((local_location.x, local_location.y, local_location.z))  # noqa F841
            parent_location_negate_axis = Vector((parent_location.x, local_location.y, parent_location.z))

            new_local_location_negate_axis = Vector((local_location.x, parent_location_negate_axis.y, local_location.z))
            identity = Vector((0.0, 0.0, 0.0))

            props.joint_local_pos_0 = new_local_location_negate_axis
            props.joint_local_pos_1 = identity

        # Now apply joint settings to the child_empty (which is now selected and active)

        # init visualizer connection
        scene_collection = bpy.context.scene.collection
        coll = ensure_widget_collection()
        set_collection_visibility(not props.show_widgets)

        # Axis frame: oriented so local Z is the joint axis
        basis = axis_basis(joint_axis)

        # Normalize revolute joint limits to avoid Euler discontinuity
        normalized_lower_limit = props.lower_limit_deg
        normalized_upper_limit = props.upper_limit_deg

        if joint_type == "revolute":
            normalized_lower_limit, normalized_upper_limit = normalize_revolute_limits(
                props.lower_limit_deg, props.upper_limit_deg
            )

        # Keep track of all created empties to unlink from scene collection
        created_empties = []

        # SETUP physics attributes on the child_empty (the joint reference prim)
        obj = child_empty

        # Clear attributes and start adding new attributes
        self.clear_simready_joint_properties(obj)

        # Handle joint visualizer creation
        if props.joint_type == "revolute":
            # Calculate the final rotation: object's rotation in world space + basis rotation
            final_matrix = obj.matrix_world @ basis

            # Create axis_frame at world origin first
            axis_frame = add_empty(f"AxisFrame_{obj.name}", None, Matrix.Identity(4), "ARROWS", 0.25, coll)
            created_empties.append(axis_frame)
            if axis_frame.name not in coll.objects:
                coll.objects.link(axis_frame)

            # Set rotation from the final matrix (object's rotation + basis)
            axis_frame.rotation_euler = final_matrix.to_euler()
            axis_frame.location = obj.matrix_world.translation

            # We'll copy CHILD_OF constraints below, but if there aren't any,
            # we need a COPY_LOCATION to track the object's position
            # Check if object has CHILD_OF constraints
            has_child_of = any(c.type == "CHILD_OF" for c in obj.constraints)
            if not has_child_of:
                # No CHILD_OF, so use COPY_LOCATION to track position
                copy_loc = axis_frame.constraints.new("COPY_LOCATION")
                copy_loc.target = obj
                copy_loc.name = "Track_Position"
        else:
            # For PRISMATIC, create at the object's world position with basis rotation
            axis_frame = add_empty(f"AxisFrame_{obj.name}", None, obj.matrix_world @ basis, "ARROWS", 0.25, coll)
            created_empties.append(axis_frame)

        if axis_frame.name not in coll.objects:
            coll.objects.link(axis_frame)
            # Parent normally (needs to rotate with object)
            axis_frame.parent = obj
            axis_frame.matrix_parent_inverse = Matrix.Identity(4)
            # Set local transform with basis rotation
            axis_frame.matrix_local = basis

        # Tag the frame so we can find it later
        axis_frame["jw_target"] = obj.name
        axis_frame["joint_type"] = joint_type
        axis_frame["jw_axis"] = joint_axis

        # Set jw_type for revolute joints (gizmo system expects this)
        # if joint_type == "revolute":
        #     axis_frame["joint_type"] = "revolute"

        # Copy any CHILD_OF constraints from the target object to the axis_frame
        # This ensures the axis_frame follows the same parent hierarchy
        for con in obj.constraints:
            if con.type == "CHILD_OF":
                new_con = axis_frame.constraints.new("CHILD_OF")
                new_con.target = con.target
                new_con.subtarget = con.subtarget
                new_con.use_location_x = con.use_location_x
                new_con.use_location_y = con.use_location_y
                new_con.use_location_z = con.use_location_z
                new_con.use_rotation_x = con.use_rotation_x
                new_con.use_rotation_y = con.use_rotation_y
                new_con.use_rotation_z = con.use_rotation_z
                new_con.use_scale_x = con.use_scale_x
                new_con.use_scale_y = con.use_scale_y
                new_con.use_scale_z = con.use_scale_z
                new_con.influence = con.influence
                new_con.name = f"Copy_{con.name}"

        # Create handles
        if props.joint_type == "prismatic":
            # Prismatic slides along the joint axis.
            # Visualization is handled by GPU drawing via the GizmoGroup.
            # Control is via arrow gizmos bound to RNA properties on the object.

            # Calculate default range based on object size
            bbox_max = max(obj.dimensions) if obj.dimensions.length > 0 else 1.0  # noqa F841

            # Get the object's current local position
            # We need to read the object's location property which is in parent space
            # Since the axis_frame will be parented to obj, we need obj's local position
            current_local = obj.location.copy()

            # Store default translation for reset functionality
            obj.jw_translation_default = current_local

            # Determine which component is the joint axis
            if joint_axis == "X":
                current_pos_on_axis = current_local.x
            elif joint_axis == "Y":
                current_pos_on_axis = current_local.y
            else:  # 'Z'
                current_pos_on_axis = current_local.z

            # Create a marker at origin
            origin = add_empty(
                f"Origin_{obj.name}",
                parent=axis_frame,
                matrix=Matrix.Identity(4),
                empty_display="PLAIN_AXES",
                size=0.1,
                coll=coll,
            )
            created_empties.append(origin)

            # Store metadata for GPU drawing
            origin["jw_axis"] = joint_axis

            # Initialize RNA properties from props values set by the artist
            # These will be used by the visualizer gizmos
            obj.jw_translation_limit_min_rna = prismatic_min_dist
            obj.jw_translation_limit_max_rna = prismatic_max_dist

            # Store the initial offset on the axis_frame for visualization
            # This is fixed at creation time and should not change
            axis_frame["jw_initial_offset"] = current_pos_on_axis

            # Store any existing CHILD_OF constraints so we can recreate them in the right order
            child_of_constraints = []
            for con in obj.constraints:
                if con.type == "CHILD_OF":
                    child_of_constraints.append(
                        {
                            "target": con.target,
                            "subtarget": con.subtarget,
                            "use_location_x": con.use_location_x,
                            "use_location_y": con.use_location_y,
                            "use_location_z": con.use_location_z,
                            "use_rotation_x": con.use_rotation_x,
                            "use_rotation_y": con.use_rotation_y,
                            "use_rotation_z": con.use_rotation_z,
                            "use_scale_x": con.use_scale_x,
                            "use_scale_y": con.use_scale_y,
                            "use_scale_z": con.use_scale_z,
                            "influence": con.influence,
                            "name": con.name,
                        }
                    )

            # Remove existing CHILD_OF constraints
            for con in list(obj.constraints):
                if con.type == "CHILD_OF":
                    obj.constraints.remove(con)

            # Create constraint and set limits based on chosen axis
            con = get_or_add_limit_constraint(obj, "prismatic")
            con.owner_space = "WORLD"
            con.use_transform_limit = True

            # Enable limits for the selected axis
            if joint_axis == "X":
                con.use_min_x = True
                con.use_max_x = True
                con.use_min_y = True
                con.use_max_y = True
                con.use_min_z = True
                con.use_max_z = True
                con.min_x = obj.jw_translation_limit_min_rna
                con.max_x = obj.jw_translation_limit_max_rna
                # Lock Y and Z at current position
                con.min_y = current_local.y
                con.max_y = current_local.y
                con.min_z = current_local.z
                con.max_z = current_local.z
            elif joint_axis == "Y":
                con.use_min_x = True
                con.use_max_x = True
                con.use_min_y = True
                con.use_max_y = True
                con.use_min_z = True
                con.use_max_z = True
                con.min_y = obj.jw_translation_limit_min_rna
                con.max_y = obj.jw_translation_limit_max_rna
                # Lock X and Z at current position
                con.min_x = current_local.x
                con.max_x = current_local.x
                con.min_z = current_local.z
                con.max_z = current_local.z
            else:  # 'Z'
                con.use_min_x = True
                con.use_max_x = True
                con.use_min_y = True
                con.use_max_y = True
                con.use_min_z = True
                con.use_max_z = True
                con.min_z = obj.jw_translation_limit_min_rna
                con.max_z = obj.jw_translation_limit_max_rna
                # Lock X and Y at current position
                con.min_x = current_local.x
                con.max_x = current_local.x
                con.min_y = current_local.y
                con.max_y = current_local.y

            # Recreate CHILD_OF constraints - they will be added after the LIMIT constraint
            # Then move them to the beginning so they're evaluated first
            for child_of_data in child_of_constraints:
                new_con = obj.constraints.new("CHILD_OF")
                new_con.target = child_of_data["target"]
                new_con.subtarget = child_of_data["subtarget"]
                new_con.use_location_x = child_of_data["use_location_x"]
                new_con.use_location_y = child_of_data["use_location_y"]
                new_con.use_location_z = child_of_data["use_location_z"]
                new_con.use_rotation_x = child_of_data["use_rotation_x"]
                new_con.use_rotation_y = child_of_data["use_rotation_y"]
                new_con.use_rotation_z = child_of_data["use_rotation_z"]
                new_con.use_scale_x = child_of_data["use_scale_x"]
                new_con.use_scale_y = child_of_data["use_scale_y"]
                new_con.use_scale_z = child_of_data["use_scale_z"]
                new_con.influence = child_of_data["influence"]
                new_con.name = child_of_data["name"]

                # Move this constraint to the top (index 0) so it's evaluated first
                # obj.constraints.move(len(obj.constraints) - 1, 0)

        else:  # REVOLUTE
            # Revolute spins around the joint axis.
            current_rotation = obj.rotation_euler.copy()

            # Store default rotation for reset functionality
            obj.jw_rotation_default = current_rotation

            # Calculate radius based on the child mesh's bounding box for appropriate scaling
            # Use the same adaptive sizing logic as empty display size for consistency
            # Arc visualizers use default_size=1.2 for better visibility, min_size=0.015 for tiny objects
            R = calculate_adaptive_empty_size(child, default_size=1.2, min_size=0.025, max_size=2.0)
            print(f"Arc visualizer radius for {child.name}: {R}")

            # Root for ring UI (shares axis_frame's orientation)
            ring_root = add_empty(
                f"RingRoot_{obj.name}",
                parent=axis_frame,
                matrix=Matrix.Identity(4),
                empty_display="PLAIN_AXES",
                size=0.01,
                coll=coll,
            )

            created_empties.append(ring_root)

            # Store metadata for GPU drawing and gizmo positioning
            ring_root["jw_radius"] = R
            ring_root["jw_axis"] = joint_axis  # Store the axis for drawing

            # Initialize RNA properties from props values set by the artist (convert degrees to radians)
            # These will be used by the visualizer gizmos
            obj.jw_rotation_limit_min_rna = radians(normalized_lower_limit)
            obj.jw_rotation_limit_max_rna = radians(normalized_upper_limit)

            # Store any existing CHILD_OF constraints so we can recreate them in the right order
            child_of_constraints = []
            for con in obj.constraints:
                if con.type == "CHILD_OF":
                    child_of_constraints.append(
                        {
                            "target": con.target,
                            "subtarget": con.subtarget,
                            "use_location_x": con.use_location_x,
                            "use_location_y": con.use_location_y,
                            "use_location_z": con.use_location_z,
                            "use_rotation_x": con.use_rotation_x,
                            "use_rotation_y": con.use_rotation_y,
                            "use_rotation_z": con.use_rotation_z,
                            "use_scale_x": con.use_scale_x,
                            "use_scale_y": con.use_scale_y,
                            "use_scale_z": con.use_scale_z,
                            "influence": con.influence,
                            "name": con.name,
                        }
                    )

            # Remove existing CHILD_OF constraints
            for con in list(obj.constraints):
                if con.type == "CHILD_OF":
                    obj.constraints.remove(con)

            # Create constraint and set limits based on chosen axis
            con = get_or_add_limit_constraint(obj, "revolute")
            con.owner_space = "LOCAL"
            con.use_transform_limit = True

            # TODO: FIDDLE WITH THIS TO GET VISUALIZER TO DISPLAY CORRECT
            # TODO: THERE ARE LOTS OF EDGE CASES HERE TO CONSIDER...

            # Enable limits for the selected axis only
            if props.joint_axis == "X":
                con.use_limit_x = True
                con.use_limit_y = False
                con.use_limit_z = False
                con.min_x = obj.jw_rotation_limit_min_rna
                con.max_x = obj.jw_rotation_limit_max_rna
                # con.min_y = current_rotation.y
                # con.max_y = current_rotation.y
                # con.min_z = current_rotation.z
                # con.max_z = current_rotation.z
            elif props.joint_axis == "Y":
                con.use_limit_x = False
                con.use_limit_y = True
                con.use_limit_z = False
                con.min_y = obj.jw_rotation_limit_min_rna
                con.max_y = obj.jw_rotation_limit_max_rna
                # con.min_x = current_rotation.x
                # con.max_x = current_rotation.x
                # con.min_z = current_rotation.z
                # con.max_z = current_rotation.z
            else:  # 'Z'
                con.use_limit_x = False
                con.use_limit_y = False
                con.use_limit_z = True
                con.min_z = obj.jw_rotation_limit_min_rna
                con.max_z = obj.jw_rotation_limit_max_rna
                # con.min_x = current_rotation.x
                # con.max_x = current_rotation.x
                # con.min_y = current_rotation.y
                # con.max_y = current_rotation.y

            # Recreate CHILD_OF constraints - they will be added after the LIMIT constraint
            # Then move them to the beginning so they're evaluated first
            for child_of_data in child_of_constraints:
                new_con = obj.constraints.new("CHILD_OF")
                new_con.target = child_of_data["target"]
                new_con.subtarget = child_of_data["subtarget"]
                new_con.use_location_x = child_of_data["use_location_x"]
                new_con.use_location_y = child_of_data["use_location_y"]
                new_con.use_location_z = child_of_data["use_location_z"]
                new_con.use_rotation_x = child_of_data["use_rotation_x"]
                new_con.use_rotation_y = child_of_data["use_rotation_y"]
                new_con.use_rotation_z = child_of_data["use_rotation_z"]
                new_con.use_scale_x = child_of_data["use_scale_x"]
                new_con.use_scale_y = child_of_data["use_scale_y"]
                new_con.use_scale_z = child_of_data["use_scale_z"]
                new_con.influence = child_of_data["influence"]
                new_con.name = child_of_data["name"]

                # TODO: this is how you move constraint indexes around, in this case, last index is what we want.
                # obj.constraints.move(len(obj.constraints) - 1, 0)

        # Link all created empties to the widget collection first (so they're not orphaned)
        for empty in created_empties:
            if empty.name not in coll.objects:
                coll.objects.link(empty)

        # Now unlink all created empties from the scene collection
        for empty in created_empties:
            if empty.name in scene_collection.objects:
                scene_collection.objects.unlink(empty)

        # only handling joints attributes that need export to USD
        # TODO: maybe making this overly complicated by validating the attributes...
        # TODO: usd export would fail anyways if it can't find the attribute.
        for ui_key, usd_key in JOINT_EXPORT_MAP.items():

            if ui_key not in allowed_fields:
                continue

            # Handle physx-only keys
            if isinstance(usd_key, tuple):
                usd_key, tag = usd_key
                if tag == "physx" and not physx_enabled:
                    continue

            # Check the prop actually exists
            if ui_key not in props.__annotations__:
                continue

            try:
                value = getattr(props, ui_key)

                # Skip uninitialized or invalid deferred types
                if type(value).__name__ == "_PropertyDeferred":
                    continue

                # UI and USD both use the same simple joint type names
                # No conversion needed for joint_type
                if ui_key == "joint_type":
                    print(f"Using joint_type: '{value}'")

                # Use normalized limits for revolute joints to avoid Euler flips
                if joint_type == "revolute":
                    if ui_key == "lower_limit_deg":
                        # Check if infinite limit is enabled
                        if props.infinite_limit_deg:
                            value = "-inf"  # Lower limit uses negative infinity
                        else:
                            value = normalized_lower_limit
                    elif ui_key == "upper_limit_deg":
                        # Check if infinite limit is enabled
                        if props.infinite_limit_deg:
                            value = "inf"  # Upper limit uses positive infinity
                        else:
                            value = normalized_upper_limit

                # Handle joint type prismatic special case for max dist, min dist
                if joint_type == "prismatic" and ui_key in ["min_dist_prismatic", "max_dist_prismatic"]:

                    # Extract location component based on joint axis
                    axis_to_component = {"X": obj.location.x, "Y": obj.location.y, "Z": obj.location.z}
                    axis_component = axis_to_component.get(joint_axis, None)

                    print(f"axis component: {axis_component}")

                    # Adjust the value based on the axis component
                    if ui_key == "min_dist_prismatic":
                        value = prismatic_min_dist - axis_component
                    elif ui_key == "max_dist_prismatic":
                        value = prismatic_max_dist - axis_component

                # Special handling for joint local rotations - use actual locator rotation
                if ui_key in ["joint_local_rot_0", "joint_local_rot_1"]:
                    # Get the rotation from the empty object (locator)
                    # USD expects quaternions (w, x, y, z) for localRot0/localRot1
                    # Convert from Blender's rotation to quaternion
                    rotation_quat = obj.rotation_euler.to_quaternion()
                    # Store as (w, x, y, z) - USD physics convention
                    value = (rotation_quat.w, rotation_quat.x, rotation_quat.y, rotation_quat.z)
                    print(
                        f"Setting {ui_key} from locator rotation: quat(w={value[0]:.3f}, x={value[1]:.3f}, y={value[2]:.3f}, z={value[3]:.3f})"
                    )

                # Special handling for joint_axis - convert to USD format
                if ui_key == "joint_axis":

                    # Handle case where value might be a vector from existing data
                    if isinstance(value, (list, tuple)) and len(value) == 3:
                        # Convert existing vector data to closest world axis
                        x, y, z = value
                        if abs(x) > 0.9:
                            axis_str = "X"
                        elif abs(y) > 0.9:
                            axis_str = "Y"
                        elif abs(z) > 0.9:
                            axis_str = "Z"
                        else:
                            axis_str = "X"  # fallback
                        obj[usd_key] = axis_str
                    elif value in ["X", "Y", "Z"]:
                        # World axes - use directly
                        obj[usd_key] = value
                    elif value in ["LOCAL_X", "LOCAL_Y", "LOCAL_Z"] and obj:
                        # Local axes - find closest world axis
                        world_axis_vector = get_world_axis_vector(value, obj)

                        # Find which world axis this local axis is closest to
                        world_axes = {
                            "X": Vector((1.0, 0.0, 0.0)),
                            "Y": Vector((0.0, 1.0, 0.0)),
                            "Z": Vector((0.0, 0.0, 1.0)),
                        }

                        best_axis = "X"
                        best_dot = 0.0

                        for axis_name, axis_vector in world_axes.items():
                            dot_product = abs(world_axis_vector.dot(axis_vector))
                            if dot_product > best_dot:
                                best_dot = dot_product
                                best_axis = axis_name

                        obj[usd_key] = best_axis
                    else:
                        # Fallback to X axis
                        obj[usd_key] = "X"
                    continue

                # Convert PointerProperty (Object) to string name
                if isinstance(value, bpy.types.ID):
                    value = value.name if value else ""

                # Convert enums to numeric values (if needed)
                if hasattr(ENUM_TO_FLOAT_MAPS, ui_key):
                    value_dataclass = ENUM_TO_FLOAT_MAPS.get(ui_key)

                    if ui_key == "break_strength":
                        force, torque = value_dataclass.get(value, (0.0, 0.0))
                        if isinstance(usd_key, list):
                            for i, k in enumerate(usd_key):
                                obj[k] = (force, torque)[i]
                    else:
                        value = value_dataclass.get(value, 0.0)
                        if value is not None:
                            obj[usd_key] = value
                            print(f"{ui_key}: {value}")

                if not isinstance(usd_key, list):
                    obj[usd_key] = value
                    # Debug output for rotation properties
                    if ui_key in ["joint_local_rot_0", "joint_local_rot_1"]:
                        print(f"Stored {usd_key} = {value} (type: {type(value)})")

                # TODO: Add visualizer creation here

            except Exception as e:
                self.report({"WARNING"}, f"Failed to set {usd_key} on {obj.name}: {e}")
                continue

        # Write Drive API properties if enabled
        # Linear Drive
        if props.drive_linear_enabled:
            obj["drive:linear:physics:type"] = props.drive_linear_type
            obj["drive:linear:physics:maxForce"] = props.drive_linear_max_force
            obj["drive:linear:physics:targetPosition"] = props.drive_linear_target_position
            obj["drive:linear:physics:targetVelocity"] = props.drive_linear_target_velocity
            obj["drive:linear:physics:damping"] = props.drive_linear_damping
            obj["drive:linear:physics:stiffness"] = props.drive_linear_stiffness

        # Angular Drive
        if props.drive_angular_enabled:
            obj["drive:angular:physics:type"] = props.drive_angular_type
            obj["drive:angular:physics:maxForce"] = props.drive_angular_max_force
            obj["drive:angular:physics:targetPosition"] = props.drive_angular_target_position
            obj["drive:angular:physics:targetVelocity"] = props.drive_angular_target_velocity
            obj["drive:angular:physics:damping"] = props.drive_angular_damping
            obj["drive:angular:physics:stiffness"] = props.drive_angular_stiffness

        # Update constraint system state after successful setup
        update_constraint_system_state(context)

        # Force viewport and gizmo refresh to display new visualizers
        # Multiple updates are needed to ensure gizmo system detects changes
        context.view_layer.update()

        # Force depsgraph update
        try:
            context.evaluated_depsgraph_get().update()
        except Exception:
            pass

        # Force a second round of updates (gizmos need this to detect changes)
        context.view_layer.update()
        try:
            dg = context.evaluated_depsgraph_get()
            dg.update()
        except Exception:
            pass

        # Tag all 3D viewports for redraw
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

        # Force scene update to trigger gizmo refresh
        try:
            context.scene.update_tag()
        except Exception:
            pass

        self.report({"INFO"}, f"Joint setup complete: {parent.name} <-- {child.name} ({joint_type} joint)")
        return {"FINISHED"}


class SRCORE_OT_sync_ui_from_object(Operator):
    bl_idname = "sr_core.sync_ui_from_object"
    bl_label = "Sync UI from Selected Object"
    bl_description = "Reads custom properties from selected object and populates the UI"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if not context.active_object:
            self.report({"ERROR"}, "No object selected!")
            return {"CANCELLED"}

        obj = context.active_object
        props = context.scene.joint_attribute_props

        if obj.type != "EMPTY":
            self.report({"ERROR"}, "Selected object must be an Empty!")
            return {"CANCELLED"}

        # Check if object has physics properties
        custom_props = {k: v for k, v in obj.items() if k.startswith(("pxr:usd:physics", "omni:simready:physx"))}
        if not custom_props:
            self.report({"WARNING"}, "Selected object has no physics properties!")
            return {"CANCELLED"}

        # Sync UI from object custom properties
        success = sync_ui_from_object_custom_props(obj, props)

        if success:
            self.report({"INFO"}, f"UI synced from {obj.name} - {len(custom_props)} properties loaded")

            # Force UI update
            for area in context.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()

            # Also force a property update to refresh the UI
            try:
                context.scene.update_tag()
                # Trigger UI refresh
                props.ui_refresh_trigger += 1
            except Exception:
                pass
        else:
            self.report({"WARNING"}, "No properties could be synced from selected object")

        return {"FINISHED"}


class SRCORE_OT_apply_drive_preset(Operator):
    bl_idname = "sr_core.apply_drive_preset"
    bl_label = "Apply Drive Preset"
    bl_description = "Apply the selected drive preset configuration"
    bl_options = {"REGISTER", "UNDO"}

    drive_mode: bpy.props.EnumProperty(
        name="Drive Mode",
        description="Whether this is a linear or angular drive preset",
        items=[
            ("linear", "Linear", "Linear drive preset"),
            ("angular", "Angular", "Angular drive preset"),
        ],
        default="linear",
    )

    def execute(self, context):
        props = context.scene.joint_attribute_props

        # Get the selected preset from the property
        if self.drive_mode == "linear":
            preset_type = props.drive_linear_preset
        else:
            preset_type = props.drive_angular_preset

        # Button preset configuration
        if preset_type == "button":
            if self.drive_mode == "linear":
                # Enable linear drive
                props.drive_linear_enabled = True
                props.drive_linear_type = "force"
                props.drive_linear_max_force = 1000000.0  # Very high value = not limited
                props.drive_linear_target_position = 0.0
                props.drive_linear_target_velocity = 0.35
                props.drive_linear_damping = 0.1
                props.drive_linear_stiffness = 0.0

                self.report({"INFO"}, "Button preset applied to Linear Drive")

            elif self.drive_mode == "angular":
                # Enable angular drive
                props.drive_angular_enabled = True
                props.drive_angular_type = "force"
                props.drive_angular_max_force = 1000000.0  # Very high value = not limited
                props.drive_angular_target_position = 0.0
                props.drive_angular_target_velocity = 0.35
                props.drive_angular_damping = 0.1
                props.drive_angular_stiffness = 0.0

                self.report({"INFO"}, "Button preset applied to Angular Drive")
        elif preset_type == "drawer":
            if self.drive_mode == "linear":
                # Enable linear drive
                props.drive_linear_enabled = True
                props.drive_linear_type = "force"
                props.drive_linear_max_force = 1000000.0
                props.drive_linear_target_position = 1.0
                props.drive_linear_target_velocity = -5.0
                props.drive_linear_damping = 0.1
                props.drive_linear_stiffness = 0.0

                self.report({"INFO"}, "Drawer preset applied to Linear Drive")
            elif self.drive_mode == "angular":
                # Enable angular drive
                props.drive_angular_enabled = True
                props.drive_angular_type = "force"
                props.drive_angular_max_force = 1000000.0  # Very high value = not limited

        # Force UI refresh
        try:
            for area in context.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
            context.scene.update_tag()
        except Exception:
            pass

        return {"FINISHED"}


class SRCORE_OT_copy_empty_position(Operator):
    bl_idname = "sr_core.copy_empty_position"
    bl_label = "Copy Empty Position (Revolute)"
    bl_description = "Copy the selected empty's position to the specified property, accounting for parent transforms"

    target_prop: bpy.props.StringProperty(
        name="Target Property", description="The property to copy the position to", default=""
    )

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "EMPTY":
            self.report({"ERROR"}, "Please select an Empty object")
            return {"CANCELLED"}

        props = context.scene.joint_attribute_props
        if hasattr(props, self.target_prop):
            # Find parent through ChildOf constraint
            parent = None
            for constraint in obj.constraints:
                if constraint.type == "CHILD_OF" and constraint.target:
                    parent = constraint.target
                    break

            # Calculate relative transform
            if parent:
                # Get local transform by multiplying world transform with inverse of parent's world transform
                local_matrix = parent.matrix_world.inverted() @ obj.matrix_world
                local_location = local_matrix.translation
            else:
                local_location = obj.location

            setattr(props, self.target_prop, local_location)
            return {"FINISHED"}
        else:
            self.report({"ERROR"}, f"Property {self.target_prop} not found")
            return {"CANCELLED"}


class SRCORE_OT_copy_empty_position_fixed(Operator):
    bl_idname = "sr_core.copy_empty_position_fixed"
    bl_label = "Copy Empty Position (Fixed)"
    bl_description = "Copy the selected empty's position to the specified property, accounting for parent transforms"

    target_prop: bpy.props.StringProperty(
        name="Target Property", description="The property to copy the position to", default=""
    )

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "EMPTY":
            self.report({"ERROR"}, "Please select an Empty object")
            return {"CANCELLED"}

        props = context.scene.joint_attribute_props
        if hasattr(props, self.target_prop):
            # Fixed joints will just use the child's position
            local_location = obj.location

            setattr(props, self.target_prop, local_location)
            return {"FINISHED"}
        else:
            self.report({"ERROR"}, f"Property {self.target_prop} not found")
            return {"CANCELLED"}


class SRCORE_OT_copy_empty_pos_prismatic(Operator):
    bl_idname = "sr_core.copy_empty_pos_prismatic"
    bl_label = "Copy Empty Position (Prismatic)"
    bl_description = "Copy the selected empty's position to the specified property, just take actual position"

    target_prop: bpy.props.StringProperty(
        name="Target Property", description="The property to copy the position to", default=""
    )

    target_prop_2: bpy.props.StringProperty(
        name="Target Property 2", description="The 2nd property to copy the position to", default=""
    )

    def execute(self, context):
        obj = context.active_object
        scene = context.scene  # noqa F841

        if not obj or obj.type != "EMPTY":
            self.report({"ERROR"}, "Please select an Empty object")
            return {"CANCELLED"}

        props = context.scene.joint_attribute_props
        if hasattr(props, self.target_prop):
            # Find parent through ChildOf constraint
            parent = None
            for constraint in obj.constraints:
                if constraint.type == "CHILD_OF" and constraint.target:
                    parent = constraint.target
                    break

            # Calculate relative transform
            if parent:
                # Get local transform by multiplying world transform with inverse of parent's world transform
                local_matrix = parent.matrix_world.inverted() @ obj.matrix_world
                local_location = local_matrix.translation

                # Get parent transform information
                parent_location = parent.location

                local_location_negate_axis = Vector((local_location.x, 0.0, local_location.z))  # noqa F841
                parent_location_negate_axis = Vector((parent_location.x, -local_location.y, parent_location.z))

                print(f"child negated Location: {local_location_negate_axis}")
                print(f"Parent negated Location: {parent_location_negate_axis}")

                setattr(props, self.target_prop, local_location_negate_axis)
                setattr(props, self.target_prop_2, parent_location_negate_axis)

                return {"FINISHED"}

            else:
                local_location = obj.location
                parent_location = obj.location
                setattr(props, self.target_prop, local_location)
                setattr(props, self.target_prop_2, parent_location)

            return {"FINISHED"}
        else:
            self.report({"ERROR"}, f"Property {self.target_prop} not found")
            return {"CANCELLED"}


class SRCORE_OT_calc_min_max_limits_prismatic(Operator):
    bl_idname = "sr_core.calc_min_max_limits_prismatic"
    bl_label = "Calculate Min/Max Limits (Prismatic)"
    bl_description = "Calculate the min and max limits for the prismatic joint based on the selected empty's position"

    target_prop: bpy.props.StringProperty(
        name="Target Property", description="The property to copy the position to", default=""
    )

    def calc_min_max_limits(self, obj, context):
        current_location = obj.location
        limit_loc_min = 0.0
        limit_loc_max = 0.0

        props = context.scene.joint_attribute_props
        if hasattr(props, self.target_prop):
            # Find LIMIT_LOCATION constraint
            for constraint in obj.constraints:
                if constraint.type == "LIMIT_LOCATION":
                    # Get the min/max values based on the axis
                    if constraint.use_min_y:
                        limit_loc_min = constraint.min_y - current_location.y
                    if constraint.use_max_y:
                        limit_loc_max = constraint.max_y - current_location.y
                    if constraint.use_min_x:
                        limit_loc_min = constraint.min_x - current_location.x
                    if constraint.use_max_x:
                        limit_loc_max = constraint.max_x - current_location.x
                    if constraint.use_min_z:
                        limit_loc_min = constraint.min_z - current_location.z
                    if constraint.use_max_z:
                        limit_loc_max = constraint.max_z - current_location.z

                    return (limit_loc_min, limit_loc_max)

            # If no constraints found, return default values
            return (0.0, 0.0)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != "EMPTY":
            self.report({"ERROR"}, "Please select an Empty object")
            return {"CANCELLED"}

        props = context.scene.joint_attribute_props
        if hasattr(props, self.target_prop):
            min_limit, max_limit = self.calc_min_max_limits(obj, context)
            print(f"min_limit: {min_limit}")
            print(f"max_limit: {max_limit}")

            # Extract the appropriate component based on the target property
            if self.target_prop == "min_dist_prismatic":
                # For prismatic joints, we want the Y component
                value = min_limit
            elif self.target_prop == "max_dist_prismatic":
                value = max_limit

            setattr(props, self.target_prop, value)
            return {"FINISHED"}


class SRCORE_OT_create_simready_collections(Operator):
    bl_idname = "sr_core.create_simready_collections"
    bl_label = "Create SimReady Collections"
    bl_description = "Create standard collections for SimReady workflow"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # Create parent Export collection if it doesn't exist
        export_collection = bpy.data.collections.get("Export")
        if not export_collection:
            export_collection = bpy.data.collections.new("Export")
            context.scene.collection.children.link(export_collection)

        # Create child collections under Export
        for name in SIMREADY_COLLECTIONS:
            if name not in bpy.data.collections:
                new_col = bpy.data.collections.new(name)
                export_collection.children.link(new_col)
            else:
                # If collection exists but isn't under Export, move it
                existing_col = bpy.data.collections[name]
                if existing_col.name not in export_collection.children:
                    # Unlink from current parent
                    for parent in existing_col.users_collection:
                        parent.children.unlink(existing_col)
                    # Link to Export collection
                    export_collection.children.link(existing_col)

        self.report({"INFO"}, "SimReady collections created under Export collection")
        return {"FINISHED"}


class SRCORE_OT_rename_simready_objects(Operator):
    bl_idname = "sr_core.rename_simready_collection_objects"
    bl_label = "Rename SimReady Objects"
    bl_description = "Ensure proper naming based on SimReady collections"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        auto_rename_objects(context.scene)
        self.report({"INFO"}, "Objects renamed based on collection")
        return {"FINISHED"}


class SRCORE_OT_build_unibody_constraints(Operator):
    bl_idname = "sr_core.build_unibody_constraints"
    bl_label = "Build Uni-body Constraints"
    bl_description = "Build the uni-body constraints"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        j_property = context.scene.joint_attribute_props
        body = j_property.body_0

        if not body:
            self.report({"ERROR"}, "No body assigned.")
            return {"CANCELLED"}

        # Auto rename objects before we start, and update joint_attribute_props
        body_name = auto_rename_object(body, "obj")

        # Check if rename was successful
        if body_name is None:
            self.report({"ERROR"}, "Failed to rename body object.")
            return {"CANCELLED"}

        j_property.body_0 = bpy.data.objects.get(body_name)

        simready_collection_names = ["Geometry", "ReferencePrims", "Colliders"]

        export_col = bpy.data.collections.get("Export")
        if not export_col:
            export_col = bpy.data.collections.new("Export")
            context.scene.collection.children.link(export_col)

        simready_subcols = {}
        for name in simready_collection_names:
            col = bpy.data.collections.get(name)
            if not col:
                col = bpy.data.collections.new(name)
                export_col.children.link(col)
            elif col.name not in export_col.children:
                for parent_col in col.users_collection:
                    parent_col.children.unlink(col)
                export_col.children.link(col)
            simready_subcols[name] = col

        geometry_col = simready_subcols["Geometry"]
        refprim_col = simready_subcols["ReferencePrims"]

        # Unlink from all collections and link to geometry collection
        for col in body.users_collection:
            if col != geometry_col:
                col.objects.unlink(body)

        if body.name not in geometry_col.objects:
            geometry_col.objects.link(body)

        # Store body transform
        body_location = body.location.copy()
        body_rotation = body.rotation_euler.copy()
        body_name = body.name

        # Check if empty already exists
        existing_empty = find_childof_target(body)

        if existing_empty:
            body_empty = existing_empty
        else:
            # Create new empty for the body
            body_base_name = ensure_joint_naming_convention(body_name)  # noqa F841
            bpy.ops.object.select_all(action="DESELECT")
            bpy.ops.object.empty_add(type="PLAIN_AXES", location=body_location)
            body_empty = context.active_object
            body_empty.rotation_euler = body_rotation
            auto_rename_object(body_empty, "joint")

            # Link to ReferencePrims and unlink from others
            for col in body_empty.users_collection:
                if col != refprim_col:
                    col.objects.unlink(body_empty)
            if body_empty.name not in refprim_col.objects:
                refprim_col.objects.link(body_empty)

            # Constraint body mesh to empty
            body.select_set(True)
            context.view_layer.objects.active = body
            body_constraint = body.constraints.new("CHILD_OF")
            body_constraint.name = f"ChildOf_{body_empty.name}"
            body_constraint.target = body_empty

        # Select the empty and finish
        bpy.ops.object.select_all(action="DESELECT")
        body_empty.select_set(True)
        context.view_layer.objects.active = body_empty

        self.report({"INFO"}, f"Child Of constraint added from {body.name} to {body_empty.name}")
        return {"FINISHED"}
