# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


# Material description constants to avoid duplication
CONCRETE_DESC = "Concrete or cement surfaces"
ASPHALT_DESC = "Asphalt road surfaces and parking lots"
BRICK_DESC = "Brick masonry and brick surfaces"
STONE_DESC = "Natural stone surfaces"
MARBLE_DESC = "Marble surfaces"
GRANITE_DESC = "Granite surfaces"
CERAMIC_DESC = "Ceramic tiles and surfaces"
PLASTER_DESC = "Plaster and stucco surfaces"
DRYWALL_DESC = "Drywall and gypsum board"
METAL_DESC = "Generic metal surfaces"
STEEL_DESC = "Steel surfaces"
ALUMINUM_DESC = "Aluminum surfaces"
COPPER_DESC = "Copper surfaces"
BRASS_DESC = "Brass surfaces"
BRONZE_DESC = "Bronze surfaces"
IRON_DESC = "Iron surfaces"
GOLD_DESC = "Gold surfaces"
SILVER_DESC = "Silver surfaces"
CHROME_DESC = "Chrome plated surfaces"
GLASS_DESC = "Glass or transparent plastic"
PLEXIGLASS_DESC = "Plexiglass or acrylic surfaces"
WOOD_DESC = "Wood fences, tree trunks, barks and branches"
PLANT_DESC = "Plant materials without backscattering (stems, fruit)"
LEAF_DESC = "Thin plant material with backscattering"
GRASS_DESC = "Grass surfaces"
MOSS_DESC = "Moss surfaces"
BARK_DESC = "Tree bark surfaces"
PLASTIC_DESC = "Generic plastic surfaces"
CARBON_FIBER_DESC = "Carbon fiber composite surfaces"
FIBERGLASS_DESC = "Fiberglass composite surfaces"
RUBBER_DESC = "Rubber surfaces"
SILICONE_DESC = "Silicone surfaces"
LATEX_DESC = "Latex surfaces"
FABRIC_DESC = "Fabric and cloth surfaces"
SILK_DESC = "Silk fabric surfaces"
DENIM_DESC = "Denim fabric surfaces"
LEATHER_DESC = "Leather surfaces"
PAINT_DESC = "Thick paint used on road marks"
LACQUER_DESC = "Lacquered surfaces"
POWDER_COAT_DESC = "Powder coated surfaces"
EMISSIVE_DESC = "Emissive surface (i.e. illuminated section of a lamp, light bulb)"
ORGANIC_DESC = "Living surfaces (human, animal)"
FOAM_DESC = "Foam surfaces"
PAPER_DESC = "Paper surfaces"
CARDBOARD_DESC = "Cardboard surfaces"
WAX_DESC = "Wax surfaces"
CLAY_DESC = "Clay surfaces"
DIRT_DESC = "Dirt and soil surfaces"
SNOW_DESC = "Snow surfaces"
ICE_DESC = "Ice surfaces"


def get_mat1_enums():
    """
    This returns the valid options for material names part 1.
    """
    lst = [
        (
            "opaque",
            "opaque",
            "The opaque material is the default and most "
            + "perfomant in simulation and should be used whenever transparency or a more "
            + "specialized material (e.g. retroflectivity) is not required",
        ),
        (
            "trans",
            "transparent",
            "Surface is translucent, and transparency " + "is drawn from the albedo alpha channel.",
        ),
        ("thin", "thin", "Enables backscattering e.g. leaves, cloth, fabric"),
        ("clearcoat", "clearcoat", "Adds a transparent, shiny layer " + "on top of the material surface"),
        ("retro", "retroreflective", "Enabled retro reflection"),
    ]
    return lst


def get_mat2_enums():
    """
    This returns the valid options for material names part 2.
    """
    lst = [
        # Construction & Building Materials
        ("concrete", "concrete", CONCRETE_DESC),
        ("asphalt", "asphalt", ASPHALT_DESC),
        ("brick", "brick", BRICK_DESC),
        ("stone", "stone", STONE_DESC),
        ("marble", "marble", MARBLE_DESC),
        ("granite", "granite", GRANITE_DESC),
        ("ceramic", "ceramic", CERAMIC_DESC),
        # Metals
        ("metal", "metal", METAL_DESC),
        ("steel", "steel", STEEL_DESC),
        ("aluminum", "aluminum", ALUMINUM_DESC),
        ("copper", "copper", COPPER_DESC),
        ("iron", "iron", IRON_DESC),
        ("chrome", "chrome", CHROME_DESC),
        ("gold", "gold", GOLD_DESC),
        ("silver", "silver", SILVER_DESC),
        # Glass & Transparent Materials
        ("glass", "glass", GLASS_DESC),
        ("plexiglass", "plexiglass", PLEXIGLASS_DESC),
        # Wood & Natural Materials
        ("wood", "wood", WOOD_DESC),
        # Plant Materials
        ("plant", "plant", PLANT_DESC),
        ("leaf", "leaf", LEAF_DESC),
        ("grass", "grass", GRASS_DESC),
        ("moss", "moss", MOSS_DESC),
        ("bark", "bark", BARK_DESC),
        # Plastics & Synthetic Materials
        ("plastic", "plastic", PLASTIC_DESC),
        ("carbon_fiber", "carbon_fiber", CARBON_FIBER_DESC),
        ("fiberglass", "fiberglass", FIBERGLASS_DESC),
        # Rubber & Elastic Materials
        ("rubber", "rubber", RUBBER_DESC),
        ("silicone", "silicone", SILICONE_DESC),
        ("latex", "latex", LATEX_DESC),
        # Textiles & Fabrics
        ("fabric", "fabric", FABRIC_DESC),
        ("silk", "silk", SILK_DESC),
        ("denim", "denim", DENIM_DESC),
        ("leather", "leather", LEATHER_DESC),
        # Paints & Coatings
        ("paint", "paint", PAINT_DESC),
        ("lacquer", "lacquer", LACQUER_DESC),
        ("powder_coat", "powder_coat", POWDER_COAT_DESC),
        # Specialized Materials
        ("emissive", "emissive", EMISSIVE_DESC),
        ("organic", "organic", ORGANIC_DESC),
        ("foam", "foam", FOAM_DESC),
        ("paper", "paper", PAPER_DESC),
        ("cardboard", "cardboard", CARDBOARD_DESC),
        ("wax", "wax", WAX_DESC),
        ("clay", "clay", CLAY_DESC),
        ("dirt", "dirt", DIRT_DESC),
        ("snow", "snow", SNOW_DESC),
        ("ice", "ice", ICE_DESC),
    ]

    return lst


mattname_dict = {
    "p1": [
        (
            "opaque",
            "opaque",
            "The opaque material is the default and most "
            + "perfomant in simulation and should be used whenever transparency or a more "
            + "specialized material (e.g. retroflectivity) is not required",
        ),
        (
            "trans",
            "transparent",
            "Surface is translucent, and transparency " + "is drawn from the albedo alpha channel.",
        ),
        ("thin", "thin", "Enables backscattering e.g. leaves, cloth, fabric"),
        ("clearcoat", "clearcoat", "Adds a transparent, shiny layer " + "on top of the material surface"),
        ("retro", "retro", "Enabled retro reflection"),
    ],
    "p2_opaque": [
        # Construction & Building Materials
        ("concrete", "concrete", CONCRETE_DESC),
        ("asphalt", "asphalt", ASPHALT_DESC),
        ("brick", "brick", BRICK_DESC),
        ("stone", "stone", STONE_DESC),
        ("marble", "marble", MARBLE_DESC),
        ("granite", "granite", GRANITE_DESC),
        ("ceramic", "ceramic", CERAMIC_DESC),
        ("plaster", "plaster", PLASTER_DESC),
        ("drywall", "drywall", DRYWALL_DESC),
        # Metals
        ("metal", "metal", METAL_DESC),
        ("steel", "steel", STEEL_DESC),
        ("aluminum", "aluminum", ALUMINUM_DESC),
        ("copper", "copper", COPPER_DESC),
        ("brass", "brass", "Brass surfaces"),
        ("bronze", "bronze", "Bronze surfaces"),
        ("iron", "iron", IRON_DESC),
        ("chrome", "chrome", CHROME_DESC),
        ("gold", "gold", GOLD_DESC),
        ("silver", "silver", SILVER_DESC),
        # Glass & Transparent Materials
        ("glass", "glass", GLASS_DESC),
        ("plexiglass", "plexiglass", PLEXIGLASS_DESC),
        ("crystal", "crystal", "Crystal surfaces"),
        # Wood & Natural Materials
        ("wood", "wood", WOOD_DESC),
        ("oak", "oak", "Oak wood surfaces"),
        ("pine", "pine", "Pine wood surfaces"),
        ("mahogany", "mahogany", "Mahogany wood surfaces"),
        ("bamboo", "bamboo", "Bamboo surfaces"),
        ("cork", "cork", "Cork surfaces"),
        # Plant Materials
        ("plant", "plant", PLANT_DESC),
        ("leaf", "leaf", LEAF_DESC),
        ("grass", "grass", GRASS_DESC),
        ("moss", "moss", MOSS_DESC),
        ("bark", "bark", BARK_DESC),
        # Plastics & Synthetic Materials
        ("plastic", "plastic", PLASTIC_DESC),
        ("vinyl", "vinyl", "Soft vinyl or plastic surfaces (i.e. traffic cone)"),
        ("polyethylene", "polyethylene", "Polyethylene plastic surfaces"),
        ("polypropylene", "polypropylene", "Polypropylene plastic surfaces"),
        ("acrylic", "acrylic", "Acrylic plastic surfaces"),
        ("carbon_fiber", "carbon_fiber", CARBON_FIBER_DESC),
        ("fiberglass", "fiberglass", FIBERGLASS_DESC),
        # Rubber & Elastic Materials
        ("rubber", "rubber", RUBBER_DESC),
        ("silicone", "silicone", SILICONE_DESC),
        ("latex", "latex", LATEX_DESC),
        # Textiles & Fabrics
        ("fabric", "fabric", FABRIC_DESC),
        ("cotton", "cotton", "Cotton fabric surfaces"),
        ("wool", "wool", "Wool fabric surfaces"),
        ("silk", "silk", SILK_DESC),
        ("denim", "denim", DENIM_DESC),
        ("canvas", "canvas", "Canvas fabric surfaces"),
        ("leather", "leather", LEATHER_DESC),
        ("suede", "suede", "Suede leather surfaces"),
        # Paints & Coatings
        ("paint", "paint", PAINT_DESC),
        ("primer", "primer", "Primer paint surfaces"),
        ("varnish", "varnish", "Varnished surfaces"),
        ("lacquer", "lacquer", LACQUER_DESC),
        ("enamel", "enamel", "Enamel paint surfaces"),
        ("powder_coat", "powder_coat", POWDER_COAT_DESC),
        # Specialized Materials
        ("emissive", "emissive", EMISSIVE_DESC),
        ("organic", "organic", ORGANIC_DESC),
        ("foam", "foam", FOAM_DESC),
        ("sponge", "sponge", "Sponge surfaces"),
        ("paper", "paper", PAPER_DESC),
        ("cardboard", "cardboard", CARDBOARD_DESC),
        ("wax", "wax", WAX_DESC),
        ("clay", "clay", CLAY_DESC),
        ("sand", "sand", "Sand surfaces"),
        ("gravel", "gravel", "Gravel surfaces"),
        ("dirt", "dirt", DIRT_DESC),
        ("mud", "mud", "Mud surfaces"),
        ("snow", "snow", SNOW_DESC),
        ("ice", "ice", ICE_DESC),
        ("water", "water", "Water surfaces"),
        ("oil", "oil", "Oil surfaces"),
        ("tar", "tar", "Tar surfaces"),
        ("asphalt_seal", "asphalt_seal", "Asphalt sealant surfaces"),
    ],
    "p2_trans": [
        # Construction & Building Materials
        ("concrete", "concrete", CONCRETE_DESC),
        ("asphalt", "asphalt", ASPHALT_DESC),
        ("brick", "brick", BRICK_DESC),
        ("stone", "stone", STONE_DESC),
        ("marble", "marble", MARBLE_DESC),
        ("granite", "granite", GRANITE_DESC),
        ("ceramic", "ceramic", CERAMIC_DESC),
        ("plaster", "plaster", PLASTER_DESC),
        ("drywall", "drywall", DRYWALL_DESC),
        # Metals
        ("metal", "metal", METAL_DESC),
        ("steel", "steel", STEEL_DESC),
        ("aluminum", "aluminum", ALUMINUM_DESC),
        ("copper", "copper", COPPER_DESC),
        ("brass", "brass", "Brass surfaces"),
        ("bronze", "bronze", "Bronze surfaces"),
        ("iron", "iron", IRON_DESC),
        ("chrome", "chrome", CHROME_DESC),
        ("gold", "gold", GOLD_DESC),
        ("silver", "silver", SILVER_DESC),
        # Glass & Transparent Materials
        ("glass", "glass", GLASS_DESC),
        ("plexiglass", "plexiglass", PLEXIGLASS_DESC),
        ("crystal", "crystal", "Crystal surfaces"),
        # Wood & Natural Materials
        ("wood", "wood", WOOD_DESC),
        ("oak", "oak", "Oak wood surfaces"),
        ("pine", "pine", "Pine wood surfaces"),
        ("mahogany", "mahogany", "Mahogany wood surfaces"),
        ("bamboo", "bamboo", "Bamboo surfaces"),
        ("cork", "cork", "Cork surfaces"),
        # Plant Materials
        ("plant", "plant", PLANT_DESC),
        ("leaf", "leaf", LEAF_DESC),
        ("grass", "grass", GRASS_DESC),
        ("moss", "moss", MOSS_DESC),
        ("bark", "bark", BARK_DESC),
        # Plastics & Synthetic Materials
        ("plastic", "plastic", PLASTIC_DESC),
        ("vinyl", "vinyl", "Soft vinyl or plastic surfaces (i.e. traffic cone)"),
        ("polyethylene", "polyethylene", "Polyethylene plastic surfaces"),
        ("polypropylene", "polypropylene", "Polypropylene plastic surfaces"),
        ("acrylic", "acrylic", "Acrylic plastic surfaces"),
        ("carbon_fiber", "carbon_fiber", CARBON_FIBER_DESC),
        ("fiberglass", "fiberglass", FIBERGLASS_DESC),
        # Rubber & Elastic Materials
        ("rubber", "rubber", RUBBER_DESC),
        ("silicone", "silicone", SILICONE_DESC),
        ("latex", "latex", LATEX_DESC),
        # Textiles & Fabrics
        ("fabric", "fabric", FABRIC_DESC),
        ("cotton", "cotton", "Cotton fabric surfaces"),
        ("wool", "wool", "Wool fabric surfaces"),
        ("silk", "silk", SILK_DESC),
        ("denim", "denim", DENIM_DESC),
        ("canvas", "canvas", "Canvas fabric surfaces"),
        ("leather", "leather", LEATHER_DESC),
        ("suede", "suede", "Suede leather surfaces"),
        # Paints & Coatings
        ("paint", "paint", PAINT_DESC),
        ("primer", "primer", "Primer paint surfaces"),
        ("varnish", "varnish", "Varnished surfaces"),
        ("lacquer", "lacquer", LACQUER_DESC),
        ("enamel", "enamel", "Enamel paint surfaces"),
        ("powder_coat", "powder_coat", POWDER_COAT_DESC),
        # Specialized Materials
        ("emissive", "emissive", EMISSIVE_DESC),
        ("organic", "organic", ORGANIC_DESC),
        ("foam", "foam", FOAM_DESC),
        ("sponge", "sponge", "Sponge surfaces"),
        ("paper", "paper", PAPER_DESC),
        ("cardboard", "cardboard", CARDBOARD_DESC),
        ("wax", "wax", WAX_DESC),
        ("clay", "clay", CLAY_DESC),
        ("sand", "sand", "Sand surfaces"),
        ("gravel", "gravel", "Gravel surfaces"),
        ("dirt", "dirt", DIRT_DESC),
        ("mud", "mud", "Mud surfaces"),
        ("snow", "snow", SNOW_DESC),
        ("ice", "ice", ICE_DESC),
        ("water", "water", "Water surfaces"),
        ("oil", "oil", "Oil surfaces"),
        ("tar", "tar", "Tar surfaces"),
        ("asphalt_seal", "asphalt_seal", "Asphalt sealant surfaces"),
    ],
    "p2_thin": [
        # Glass & Transparent Materials
        ("glass", "glass", GLASS_DESC),
        ("plexiglass", "plexiglass", PLEXIGLASS_DESC),
        ("crystal", "crystal", "Crystal surfaces"),
        # Plant Materials
        ("plant", "plant", PLANT_DESC),
        ("leaf", "leaf", LEAF_DESC),
        ("grass", "grass", GRASS_DESC),
        ("moss", "moss", MOSS_DESC),
        ("bark", "bark", BARK_DESC),
        # Plastics & Synthetic Materials
        ("plastic", "plastic", PLASTIC_DESC),
        ("vinyl", "vinyl", "Soft vinyl or plastic surfaces (i.e. traffic cone)"),
        ("polyethylene", "polyethylene", "Polyethylene plastic surfaces"),
        ("polypropylene", "polypropylene", "Polypropylene plastic surfaces"),
        ("acrylic", "acrylic", "Acrylic plastic surfaces"),
        ("carbon_fiber", "carbon_fiber", CARBON_FIBER_DESC),
        ("fiberglass", "fiberglass", FIBERGLASS_DESC),
        # Rubber & Elastic Materials
        ("rubber", "rubber", RUBBER_DESC),
        ("silicone", "silicone", SILICONE_DESC),
        ("latex", "latex", LATEX_DESC),
        # Textiles & Fabrics
        ("fabric", "fabric", FABRIC_DESC),
        ("cotton", "cotton", "Cotton fabric surfaces"),
        ("wool", "wool", "Wool fabric surfaces"),
        ("silk", "silk", SILK_DESC),
        ("denim", "denim", DENIM_DESC),
        ("canvas", "canvas", "Canvas fabric surfaces"),
        ("leather", "leather", LEATHER_DESC),
        ("suede", "suede", "Suede leather surfaces"),
        # Specialized Materials
        ("organic", "organic", ORGANIC_DESC),
        ("foam", "foam", FOAM_DESC),
        ("sponge", "sponge", "Sponge surfaces"),
        ("paper", "paper", PAPER_DESC),
        ("cardboard", "cardboard", CARDBOARD_DESC),
    ],
    "p2_clearcoat": [
        # Construction & Building Materials
        ("concrete", "concrete", CONCRETE_DESC),
        ("asphalt", "asphalt", ASPHALT_DESC),
        ("brick", "brick", BRICK_DESC),
        ("stone", "stone", STONE_DESC),
        ("marble", "marble", MARBLE_DESC),
        ("granite", "granite", GRANITE_DESC),
        ("ceramic", "ceramic", CERAMIC_DESC),
        ("plaster", "plaster", PLASTER_DESC),
        ("drywall", "drywall", DRYWALL_DESC),
        # Metals
        ("metal", "metal", METAL_DESC),
        ("steel", "steel", STEEL_DESC),
        ("aluminum", "aluminum", ALUMINUM_DESC),
        ("copper", "copper", COPPER_DESC),
        ("brass", "brass", "Brass surfaces"),
        ("bronze", "bronze", "Bronze surfaces"),
        ("iron", "iron", IRON_DESC),
        ("chrome", "chrome", CHROME_DESC),
        ("gold", "gold", GOLD_DESC),
        ("silver", "silver", SILVER_DESC),
        # Glass & Transparent Materials
        ("glass", "glass", GLASS_DESC),
        ("plexiglass", "plexiglass", PLEXIGLASS_DESC),
        ("crystal", "crystal", "Crystal surfaces"),
        # Wood & Natural Materials
        ("wood", "wood", WOOD_DESC),
        ("oak", "oak", "Oak wood surfaces"),
        ("pine", "pine", "Pine wood surfaces"),
        ("mahogany", "mahogany", "Mahogany wood surfaces"),
        ("bamboo", "bamboo", "Bamboo surfaces"),
        ("cork", "cork", "Cork surfaces"),
        # Plant Materials
        ("plant", "plant", PLANT_DESC),
        ("leaf", "leaf", LEAF_DESC),
        ("grass", "grass", GRASS_DESC),
        ("moss", "moss", MOSS_DESC),
        ("bark", "bark", BARK_DESC),
        # Plastics & Synthetic Materials
        ("plastic", "plastic", PLASTIC_DESC),
        ("vinyl", "vinyl", "Soft vinyl or plastic surfaces (i.e. traffic cone)"),
        ("polyethylene", "polyethylene", "Polyethylene plastic surfaces"),
        ("polypropylene", "polypropylene", "Polypropylene plastic surfaces"),
        ("acrylic", "acrylic", "Acrylic plastic surfaces"),
        ("carbon_fiber", "carbon_fiber", CARBON_FIBER_DESC),
        ("fiberglass", "fiberglass", FIBERGLASS_DESC),
        # Rubber & Elastic Materials
        ("rubber", "rubber", RUBBER_DESC),
        ("silicone", "silicone", SILICONE_DESC),
        ("latex", "latex", LATEX_DESC),
        # Textiles & Fabrics
        ("fabric", "fabric", FABRIC_DESC),
        ("cotton", "cotton", "Cotton fabric surfaces"),
        ("wool", "wool", "Wool fabric surfaces"),
        ("silk", "silk", SILK_DESC),
        ("denim", "denim", DENIM_DESC),
        ("canvas", "canvas", "Canvas fabric surfaces"),
        ("leather", "leather", LEATHER_DESC),
        ("suede", "suede", "Suede leather surfaces"),
        # Paints & Coatings
        ("paint", "paint", PAINT_DESC),
        ("primer", "primer", "Primer paint surfaces"),
        ("varnish", "varnish", "Varnished surfaces"),
        ("lacquer", "lacquer", LACQUER_DESC),
        ("enamel", "enamel", "Enamel paint surfaces"),
        ("powder_coat", "powder_coat", POWDER_COAT_DESC),
        # Specialized Materials
        ("emissive", "emissive", EMISSIVE_DESC),
        ("organic", "organic", ORGANIC_DESC),
        ("foam", "foam", FOAM_DESC),
        ("sponge", "sponge", "Sponge surfaces"),
        ("paper", "paper", PAPER_DESC),
        ("cardboard", "cardboard", CARDBOARD_DESC),
        ("wax", "wax", WAX_DESC),
        ("clay", "clay", CLAY_DESC),
        ("sand", "sand", "Sand surfaces"),
        ("gravel", "gravel", "Gravel surfaces"),
        ("dirt", "dirt", DIRT_DESC),
        ("mud", "mud", "Mud surfaces"),
        ("snow", "snow", SNOW_DESC),
        ("ice", "ice", ICE_DESC),
        ("water", "water", "Water surfaces"),
        ("oil", "oil", "Oil surfaces"),
        ("tar", "tar", "Tar surfaces"),
        ("asphalt_seal", "asphalt_seal", "Asphalt sealant surfaces"),
    ],
    "p2_retro": [
        # Construction & Building Materials
        ("concrete", "concrete", CONCRETE_DESC),
        ("asphalt", "asphalt", ASPHALT_DESC),
        ("brick", "brick", BRICK_DESC),
        ("stone", "stone", STONE_DESC),
        ("marble", "marble", MARBLE_DESC),
        ("granite", "granite", GRANITE_DESC),
        ("ceramic", "ceramic", CERAMIC_DESC),
        ("plaster", "plaster", PLASTER_DESC),
        ("drywall", "drywall", DRYWALL_DESC),
        # Metals
        ("metal", "metal", METAL_DESC),
        ("steel", "steel", STEEL_DESC),
        ("aluminum", "aluminum", ALUMINUM_DESC),
        ("copper", "copper", COPPER_DESC),
        ("brass", "brass", "Brass surfaces"),
        ("bronze", "bronze", "Bronze surfaces"),
        ("iron", "iron", IRON_DESC),
        ("chrome", "chrome", CHROME_DESC),
        ("gold", "gold", GOLD_DESC),
        ("silver", "silver", SILVER_DESC),
        # Glass & Transparent Materials
        ("glass", "glass", GLASS_DESC),
        ("plexiglass", "plexiglass", PLEXIGLASS_DESC),
        ("crystal", "crystal", "Crystal surfaces"),
        # Wood & Natural Materials
        ("wood", "wood", WOOD_DESC),
        ("oak", "oak", "Oak wood surfaces"),
        ("pine", "pine", "Pine wood surfaces"),
        ("mahogany", "mahogany", "Mahogany wood surfaces"),
        ("bamboo", "bamboo", "Bamboo surfaces"),
        ("cork", "cork", "Cork surfaces"),
        # Plant Materials
        ("plant", "plant", PLANT_DESC),
        ("leaf", "leaf", LEAF_DESC),
        ("grass", "grass", GRASS_DESC),
        ("moss", "moss", MOSS_DESC),
        ("bark", "bark", BARK_DESC),
        # Plastics & Synthetic Materials
        ("plastic", "plastic", PLASTIC_DESC),
        ("vinyl", "vinyl", "Soft vinyl or plastic surfaces (i.e. traffic cone)"),
        ("polyethylene", "polyethylene", "Polyethylene plastic surfaces"),
        ("polypropylene", "polypropylene", "Polypropylene plastic surfaces"),
        ("acrylic", "acrylic", "Acrylic plastic surfaces"),
        ("carbon_fiber", "carbon_fiber", CARBON_FIBER_DESC),
        ("fiberglass", "fiberglass", FIBERGLASS_DESC),
        # Rubber & Elastic Materials
        ("rubber", "rubber", RUBBER_DESC),
        ("silicone", "silicone", SILICONE_DESC),
        ("latex", "latex", LATEX_DESC),
        # Textiles & Fabrics
        ("fabric", "fabric", FABRIC_DESC),
        ("cotton", "cotton", "Cotton fabric surfaces"),
        ("wool", "wool", "Wool fabric surfaces"),
        ("silk", "silk", SILK_DESC),
        ("denim", "denim", DENIM_DESC),
        ("canvas", "canvas", "Canvas fabric surfaces"),
        ("leather", "leather", LEATHER_DESC),
        ("suede", "suede", "Suede leather surfaces"),
        # Paints & Coatings
        ("paint", "paint", PAINT_DESC),
        ("primer", "primer", "Primer paint surfaces"),
        ("varnish", "varnish", "Varnished surfaces"),
        ("lacquer", "lacquer", LACQUER_DESC),
        ("enamel", "enamel", "Enamel paint surfaces"),
        ("powder_coat", "powder_coat", POWDER_COAT_DESC),
        # Specialized Materials
        ("emissive", "emissive", EMISSIVE_DESC),
        ("organic", "organic", ORGANIC_DESC),
        ("foam", "foam", FOAM_DESC),
        ("sponge", "sponge", "Sponge surfaces"),
        ("paper", "paper", PAPER_DESC),
        ("cardboard", "cardboard", CARDBOARD_DESC),
        ("wax", "wax", WAX_DESC),
        ("clay", "clay", CLAY_DESC),
        ("sand", "sand", "Sand surfaces"),
        ("gravel", "gravel", "Gravel surfaces"),
        ("dirt", "dirt", DIRT_DESC),
        ("mud", "mud", "Mud surfaces"),
        ("snow", "snow", SNOW_DESC),
        ("ice", "ice", ICE_DESC),
        ("water", "water", "Water surfaces"),
        ("oil", "oil", "Oil surfaces"),
        ("tar", "tar", "Tar surfaces"),
        ("asphalt_seal", "asphalt_seal", "Asphalt sealant surfaces"),
    ],
}


assetname_dict = {
    "types": [
        ("prop", "prop", "Choose this option when working with props." + ""),
        ("vehicle", "vehicle", "Choose this option when working with vehicles" + ""),
    ],
    "categories": [
        (
            "@",
            "roadside",
            "Most assets should be assigned the roadside category unless " + "they are soley used for traffic control.",
        ),
        (
            "traf",
            "traffic",
            "Use only for assets that directly control vehicle traffic."
            + "\n\nIf an asset can be used in traffic and in non-traffic areas then it should be "
            + "assigned the roadside category.",
        ),
    ],
    "classes_traffic": [
        ("lane", "lanekeeping", "Asset is designed specifically for  lanekeeping."),
        (
            "barrier",
            "barrier",
            "Asset is meant to be a barrier to vehicle traffic and cannot be used outside " + "of a traffic lane.",
        ),
        ("spd", "speed control", "Asset is used for vehicle speed control"),
    ],
    "classes_roadside": [
        ("strt", "street furniture", "Typical props found along roadside (e.g. parking meters, benches)."),
        ("bldg", "building", "Building"),
        (
            "sct",
            "scatter",
            "Assets to be scattered over road and walkways: litter, fall leaves, pebbles, etc. "
            + "\n\nLiving plants scattered over terrain should use the vegetation class."
            + "\n\nSince scattered objects are built in clumps, they are considered fixed and not movable.",
        ),
        (
            "obs",
            "obstacle (VRRD)",
            "Asset built for use as vehicle-relevant road debris."
            + "\n\nThese assets might also be placed in walkways and near the road."
            + "\n\nAll obstacles are considered movable objects.",
        ),
        (
            "pole",
            "pole",
            "vertical pole-like objects such as sign posts, and mailbox posts, etc."
            + "\n\nThis tool provides only a simple form of naming for poles and does not capture complex details"
            + "such as diameter and height, etc. (the type of information that you would want for assets that "
            + "need to capture this data e.g. traffic poles.",
        ),
        (
            "sgn",
            "signage",
            "A sign asset that do not affect vehicle traffic. "
            + "\n\nUse this for signs on buildings, walls and that are placed on walkways or storefronts.",
        ),
        ("constr", "construction zone", "Asset built for construction zones."),
        ("emerg", "emergency zone", "Asset built for emergency zones such as accident sites."),
        ("veg", "vegetation", "Specifically live vegetation planted in pots or ground, not debris."),
    ],
    "subclasses_vegetation": [
        ("tree", "tree", "Tree"),
        ("plant", "plant", "Any plant that does not fit better into the tree, shrub, or ground cover."),
        ("shrub", "shrub", "Shrub or bush."),
        ("cover", "grnd cover", "Plants meant to be scattered over large areas e.g. grasses, wildflowers, etc."),
    ],
    "subclasses_building": [
        ("cml", "commercial", "Commercial building"),
        ("res", "residential", "Residential building"),
    ],
    "subclasses_fxd_or_mov": [
        ("fxd", "fixed", "Asset is bolted or implanted in place. (i.e. park bench bolted to ground.)"),
        ("mov", "movable", "Asset is movable (i.e. trash can that can tip over and roll.)"),
    ],
    "size": [
        ("!!", "N/A", "Only define size if necessary"),
        ("sm", "small", "Small"),
        ("lrg", "large", "Large"),
    ],
    "style": [
        ("!!", "N/A", "Only define style if necessary"),
        ("mod", "modern", "description"),
        ("vtg", "vintage", "description"),
        ("lcl", "local", "description"),
    ],
    "condition": [
        (
            "!!",
            "N/A",
            "Only define condition if necessary."
            + "\n\nAs a rule, all assets should look roughly a year old, not perfectly new and "
            + "and not excessively worn or damaged. Only use the condition tag if the asset meaningfully "
            + "diverges from the norm.",
        ),
        ("dam", "damaged", "Asset is visibly broken or damaged."),
    ],
    "country": [
        (
            "!!",
            "N/A",
            "Only define region if necessary."
            + "\n\nIf the asset can be used in any region then don't add region information to the name.",
        ),
        ("cn", "China", "Only"),
        ("de", "Germany", "Germany"),
        ("in", "India", "India"),
        ("jp", "Japan", "Japan"),
        ("se", "Sweden", "Sweden"),
        ("tw", "Taiwan", "Taiwan"),
        ("uk", "United Kingdon", "United Kingdon"),
        ("us", "United States", "United States"),
    ],
    "veh_make": [
        (
            "!",
            "CUSTOM",
            "Enter in custom vehicle make." + "\n\nPlease ensure that your vehicle is not available in the dropdown.",
        ),
        (
            "!!",
            "GENERIC",
            "If you are making a generic vehicle then 'model' "
            + "will be replaced with the vehicle category chosen from a list.",
        ),
        # top 50 vehicle brands in US
        # TODO add top Chineese brands
        ("acura", "Acura", ""),
        ("alfa_romeo", "Alfa Romeo", ""),
        ("aston_martin", "Astin Martin", ""),
        ("audi", "Audi", ""),
        ("bentley", "Bentley", ""),
        ("bmw", "BMW", ""),
        ("bugatti", "Bugatti", ""),
        ("buick", "Buick", ""),
        ("cadillac", "Cadillac", ""),
        ("canoo", "Canoo", ""),
        ("chevrolet", "Chevrolet", ""),
        ("chrysler", "Chrysler", ""),
        ("dodge", "Dodge", ""),
        ("ferrari", "Ferrari", ""),
        ("fiat", "Fiat", ""),
        ("ford", "Ford", ""),
        ("genesis", "Genesis", ""),
        ("honda", "Honda", ""),
        ("honey", "Honey", ""),
        ("infiniti", "Infiniti", ""),
        ("jaguar", "Jaguar", ""),
        ("jeep", "Jeep", ""),
        ("hyundai", "Hyundai", ""),
        ("kia", "Kia", ""),
        ("lamborghini", "Lamborghini", ""),
        ("land_rover", "Land Rover", ""),
        ("lexus", "Lexus", ""),
        ("lincoln", "Lincoln", ""),
        ("lotus", "Lotus", ""),
        ("lucid", "Lucid", ""),
        ("maserati", "Maserati", ""),
        ("mazda", "Mazda", ""),
        ("mclaren", "McLaren", ""),
        ("mercedes", "Mercedes Benz", ""),
        ("mini", "Mini", ""),
        ("mitsubishi", "Mitsubishi", ""),
        ("nissan", "Nissan", ""),
        ("oldsmobile", "Oldsmobile", ""),
        ("polestar", "Polestar", ""),
        ("pontiac", "Pontiac", ""),
        ("porsche", "Porsche", ""),
        ("ram", "Ram Trucks", ""),
        ("rimac", "Rimac", ""),
        ("rivian", "Rivian", ""),
        ("rolls_royce", "Rolls-Royce", ""),
        ("subaru", "Subaru", ""),
        ("tesla", "Tesla", ""),
        ("toyota", "Toyota", ""),
        ("volvo", "Volvo", ""),
        ("vw", "Volkswagen", ""),
    ],
}
