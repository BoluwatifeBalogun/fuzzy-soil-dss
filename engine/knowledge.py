"""
Knowledge base for the fuzzy soil selection system.

Everything numeric in here has a source. Values marked "provisional" come from
extension guidance rather than peer-reviewed work and are meant to be confirmed
by a soil scientist (see Chapter Three, Section 3.8 of the seminar report).

Units follow common Nigerian soil-laboratory reporting conventions:
  pH      : water, 1:1 or 1:2.5 suspension
  N       : total nitrogen, g/kg (0.1 % == 1 g/kg)
  P       : available phosphorus, Bray-1, mg/kg
  K       : exchangeable potassium, cmol(+)/kg
  OC      : organic carbon, %
  ECe     : electrical conductivity of the saturated extract, dS/m
  moisture: % of field capacity (0 = oven dry, 100 = field capacity, >100 = waterlogged)
  texture : USDA class, simplified to five groups
"""

FACTORS = {
    "ph": {
        "label": "Soil pH",
        "unit": "pH (water)",
        "universe": (3.0, 10.0),
        "step": 0.1,
        "terms": ["strongly_acidic", "moderately_acidic", "neutral", "moderately_alkaline", "strongly_alkaline"],
        "term_labels": {
            "strongly_acidic": "strongly acidic",
            "moderately_acidic": "moderately acidic",
            "neutral": "neutral",
            "moderately_alkaline": "moderately alkaline",
            "strongly_alkaline": "strongly alkaline",
        },
        "crop_specific": True,
        "help": "Below about 5.5 phosphorus locks up and aluminium can be toxic; above 7.5 iron, zinc and manganese become scarce.",
    },
    "nitrogen": {
        "label": "Total nitrogen",
        "unit": "g/kg",
        "universe": (0.0, 5.0),
        "step": 0.1,
        "terms": ["low", "moderate", "high"],
        "term_labels": {"low": "low", "moderate": "moderate", "high": "high"},
        # breakpoints as (a, b, c, d) trapezoids / (a, b, c) triangles over the universe
        "mfs": {
            "low": ("trap", (0.0, 0.0, 0.8, 1.2)),
            "moderate": ("trap", (0.8, 1.2, 1.8, 2.2)),
            "high": ("trap", (1.8, 2.2, 5.0, 5.0)),
        },
        "source": "Soil-test interpretation classes used by Nigerian laboratories, after Ogunleye et al. (2018): <1 g/kg low, 1 to 2 moderate, >2 high; membership crosses 0.5 at each class boundary",
        "help": "0.1 % total N equals 1 g/kg. Vegetables are heavy feeders, but nitrogen is the easiest deficiency to correct.",
    },
    "phosphorus": {
        "label": "Available phosphorus",
        "unit": "mg/kg (Bray-1)",
        "universe": (0.0, 60.0),
        "step": 0.5,
        "terms": ["low", "moderate", "high"],
        "term_labels": {"low": "low", "moderate": "moderate", "high": "high"},
        "mfs": {
            "low": ("trap", (0.0, 0.0, 6.0, 10.0)),
            "moderate": ("trap", (6.0, 10.0, 18.0, 22.0)),
            "high": ("trap", (18.0, 22.0, 60.0, 60.0)),
        },
        "source": "Bray-1 P classes used by Nigerian laboratories, after Ogunleye et al. (2018): <8 mg/kg low, 8 to 20 moderate, >20 high",
        "help": "Phosphorus availability collapses in strongly acid soils, so a low reading is often a pH problem in disguise.",
    },
    "potassium": {
        "label": "Exchangeable potassium",
        "unit": "cmol/kg",
        "universe": (0.0, 2.0),
        "step": 0.01,
        "terms": ["low", "moderate", "high"],
        "term_labels": {"low": "low", "moderate": "moderate", "high": "high"},
        "mfs": {
            "low": ("trap", (0.0, 0.0, 0.12, 0.18)),
            "moderate": ("trap", (0.12, 0.18, 0.27, 0.33)),
            "high": ("trap", (0.27, 0.33, 2.0, 2.0)),
        },
        "source": "Exchangeable K classes used by Nigerian laboratories, after Ogunleye et al. (2018): <0.15 cmol/kg low, 0.15 to 0.30 moderate, >0.30 high",
        "help": "Fruiting vegetables (tomato, pepper) draw potassium hard during fruit fill.",
    },
    "organic_carbon": {
        "label": "Organic carbon",
        "unit": "%",
        "universe": (0.0, 5.0),
        "step": 0.05,
        "terms": ["very_low", "low", "moderate", "high"],
        "term_labels": {"very_low": "very low", "low": "low", "moderate": "moderate", "high": "high"},
        "mfs": {
            "very_low": ("trap", (0.0, 0.0, 0.4, 0.6)),
            "low": ("trap", (0.4, 0.6, 0.9, 1.1)),
            "moderate": ("trap", (0.9, 1.1, 1.4, 1.6)),
            "high": ("trap", (1.4, 1.6, 5.0, 5.0)),
        },
        "source": "After FAO (1976) and Sys et al. (1993): <0.5 % very low, 0.5 to 1.0 low, 1.0 to 1.5 moderate, >1.5 high",
        "help": "Organic carbon is the best single indicator of how well a sandy Nigerian soil will hold water and nutrients.",
    },
    "ec": {
        "label": "Salinity (ECe)",
        "unit": "dS/m",
        "universe": (0.0, 12.0),
        "step": 0.1,
        "terms": ["low", "moderate", "high", "very_high"],
        "term_labels": {"low": "low", "moderate": "moderate", "high": "high", "very_high": "very high"},
        "crop_specific": True,
        "help": "Salts build up under irrigation and heavy poultry-manure use. Onion and pepper feel it first.",
    },
    "moisture": {
        "label": "Soil moisture",
        "unit": "% of field capacity",
        "universe": (0.0, 120.0),
        "step": 1.0,
        "terms": ["dry", "moist", "wet"],
        "term_labels": {"dry": "dry", "moist": "moist", "wet": "wet / waterlogged"},
        "mfs": {
            "dry": ("trap", (0.0, 0.0, 30.0, 50.0)),
            "moist": ("trap", (30.0, 50.0, 85.0, 100.0)),
            "wet": ("trap", (85.0, 100.0, 120.0, 120.0)),
        },
        "source": "Field capacity convention; expert review",
        "help": "100 % means the soil is holding all the water it can against gravity. Above that it is waterlogged.",
    },
    "texture": {
        "label": "Texture",
        "unit": "class",
        "universe": None,
        "classes": ["sandy", "sandy_loam", "loam", "clay_loam", "clay"],
        "class_labels": {"sandy": "sandy", "sandy_loam": "sandy loam", "loam": "loam", "clay_loam": "clay loam", "clay": "clay"},
        "terms": ["sandy", "sandy_loam", "loam", "clay_loam", "clay"],
        "term_labels": {"sandy": "sandy", "sandy_loam": "sandy loam", "loam": "loam", "clay_loam": "clay loam", "clay": "clay"},
        "source": "FAO (1976); Sys et al. (1993)",
        "help": "Squeeze a moist handful. Sand falls apart; loam holds a shape but crumbles; clay forms a shiny ribbon.",
    },
}

FACTOR_ORDER = ["ph", "nitrogen", "phosphorus", "potassium", "organic_carbon", "ec", "moisture", "texture"]

# Order used to break ties between equally strong limitations: hardest to correct first.
SEVERITY_ORDER = ["texture", "moisture", "ph", "ec", "organic_carbon", "nitrogen", "phosphorus", "potassium"]

# Ratings follow the FAO classes: S1 highly suitable, S2 moderately, S3 marginally, N not suitable.
# Nutrients are capped at S3 because they are correctable; pH, salinity, drainage and texture can reach N.
# Nutrient status is a correctable limitation (Sys et al., 1991), so low N, P or K
# reduces a plot to S2 at most; only near-absent organic matter reaches S3.
_NUTRIENT_RATING = {"low": "S2", "moderate": "S1", "high": "S1"}
_OC_RATING = {"very_low": "S3", "low": "S2", "moderate": "S1", "high": "S1"}
_EC_RATING = {"low": "S1", "moderate": "S2", "high": "S3", "very_high": "N"}
_PH_RATING = {"strongly_acidic": "N", "moderately_acidic": "S2", "neutral": "S1", "moderately_alkaline": "S2", "strongly_alkaline": "N"}

CROPS = {
    "tomato": {
        "name": "Tomato",
        "scientific": "Solanum lycopersicum",
        "blurb": "Nigeria's most valuable vegetable and its most soil-sensitive. Hates wet feet and sour ground.",
        # pH: S1 range, S2 lower band start, S2 upper band end  (Sadiq et al., 2025)
        "ph": {"s1": (6.0, 7.0), "s2_low": 5.0, "s2_high": 8.5, "source": "Sadiq et al. (2025), Heliyon", "provisional": False},
        # Maas-Hoffman: threshold a (dS/m), slope b (% yield loss per dS/m above a)
        "ec": {"a": 2.5, "b": 9.9, "source": "Tanji and Kielen (2002), FAO I&D Paper 61", "provisional": False},
        "moisture_rating": {"dry": "S3", "moist": "S1", "wet": "N"},
        "texture_rating": {"sandy": "S3", "sandy_loam": "S1", "loam": "S1", "clay_loam": "S2", "clay": "N"},
        "accent": "#C8432B",
    },
    "pepper": {
        "name": "Pepper",
        "scientific": "Capsicum annuum / C. chinense",
        "blurb": "Ata rodo, tatase, shombo. Wants warmth, steady moisture and very little salt.",
        "ph": {"s1": (5.8, 6.8), "s2_low": 5.0, "s2_high": 7.8, "source": "Extension guidance; provisional", "provisional": True},
        "ec": {"a": 1.5, "b": 14.0, "source": "Tanji and Kielen (2002)", "provisional": False},
        "moisture_rating": {"dry": "S3", "moist": "S1", "wet": "N"},
        "texture_rating": {"sandy": "S3", "sandy_loam": "S1", "loam": "S1", "clay_loam": "S2", "clay": "S3"},
        "accent": "#B8232B",
    },
    "okra": {
        "name": "Okra",
        "scientific": "Abelmoschus esculentus",
        "blurb": "Forgiving and heat-loving. Tolerates a wider pH band and poorer soils than most.",
        "ph": {"s1": (5.8, 7.0), "s2_low": 5.0, "s2_high": 8.0, "source": "FAO Ecocrop; provisional", "provisional": True},
        "ec": {"a": 2.0, "b": 10.0, "source": "No published threshold; treated as moderately sensitive (provisional)", "provisional": True},
        "moisture_rating": {"dry": "S3", "moist": "S1", "wet": "S3"},
        "texture_rating": {"sandy": "S2", "sandy_loam": "S1", "loam": "S1", "clay_loam": "S2", "clay": "S3"},
        "accent": "#3F7D3A",
    },
    "onion": {
        "name": "Onion",
        "scientific": "Allium cepa",
        "blurb": "The north's cash crop. Shallow roots, salt-sensitive at the seedling stage, needs loose soil for bulbing.",
        "ph": {"s1": (6.0, 7.0), "s2_low": 5.5, "s2_high": 7.8, "source": "Extension guidance; provisional", "provisional": True},
        "ec": {"a": 1.2, "b": 16.0, "source": "Tanji and Kielen (2002); Shannon and Grieve (1999)", "provisional": False},
        "moisture_rating": {"dry": "S3", "moist": "S1", "wet": "N"},
        "texture_rating": {"sandy": "S2", "sandy_loam": "S1", "loam": "S1", "clay_loam": "S3", "clay": "N"},
        "accent": "#8E4B9E",
    },
    "cabbage": {
        "name": "Cabbage",
        "scientific": "Brassica oleracea var. capitata",
        "blurb": "Jos Plateau's favourite. A heavy feeder that wants cool nights, plenty of nitrogen and firm loam.",
        "ph": {"s1": (6.0, 7.0), "s2_low": 5.5, "s2_high": 7.8, "source": "Extension guidance; provisional", "provisional": True},
        "ec": {"a": 1.8, "b": 9.7, "source": "Tanji and Kielen (2002)", "provisional": False},
        "moisture_rating": {"dry": "S3", "moist": "S1", "wet": "S3"},
        "texture_rating": {"sandy": "S3", "sandy_loam": "S2", "loam": "S1", "clay_loam": "S1", "clay": "S3"},
        "accent": "#2F6B5E",
    },
    "amaranth": {
        "name": "Amaranth (green)",
        "scientific": "Amaranthus cruentus",
        "blurb": "Efo tete. Ready in four weeks, grown on every peri-urban plot in Lagos. Tolerant, but not of salt.",
        "ph": {"s1": (6.0, 7.0), "s2_low": 5.5, "s2_high": 8.0, "source": "Extension guidance; provisional", "provisional": True},
        "ec": {"a": 2.0, "b": 7.6, "source": "Spinach used as proxy, Tanji and Kielen (2002); provisional", "provisional": True},
        "moisture_rating": {"dry": "S3", "moist": "S1", "wet": "S3"},
        "texture_rating": {"sandy": "S2", "sandy_loam": "S1", "loam": "S1", "clay_loam": "S2", "clay": "S3"},
        "accent": "#5C8A2B",
    },
}

CROP_ORDER = ["tomato", "pepper", "okra", "onion", "cabbage", "amaranth"]


def rating_table(crop_key):
    """Return {factor: {term: rating}} for a crop."""
    c = CROPS[crop_key]
    return {
        "ph": dict(_PH_RATING),
        "nitrogen": dict(_NUTRIENT_RATING),
        "phosphorus": dict(_NUTRIENT_RATING),
        "potassium": dict(_NUTRIENT_RATING),
        "organic_carbon": dict(_OC_RATING),
        "ec": dict(_EC_RATING),
        "moisture": dict(c["moisture_rating"]),
        "texture": dict(c["texture_rating"]),
    }


# Advice shown when a factor limits the plot. Keyed by factor then term.
ADVICE = {
    "ph": {
        "strongly_acidic": "pH is far too low. Apply agricultural lime (2 to 4 t/ha depending on texture) and retest after one season before planting. Or choose another plot.",
        "moderately_acidic": "Slightly sour. Lime at 1 to 2 t/ha, or work in wood ash and well-rotted manure, then recheck. Most vegetables will still grow with reduced yield.",
        "moderately_alkaline": "Slightly alkaline; iron and zinc may go short. Add organic matter and, where available, elemental sulphur. Avoid wood ash.",
        "strongly_alkaline": "Strongly alkaline, likely with free carbonates. Correcting this is slow and expensive; prefer another plot for vegetables.",
    },
    "nitrogen": {
        "low": "Nitrogen is low. Incorporate poultry manure or compost before planting and side-dress with urea or NPK after establishment. Legume rotation helps between seasons.",
        "moderate": "Nitrogen is only moderate. A light top-dressing will usually close the gap for a leafy or fruiting crop.",
    },
    "phosphorus": {
        "low": "Phosphorus is low. Band single super phosphate or NPK at planting. If pH is also low, lime first or the phosphorus will lock up.",
        "moderate": "Phosphorus is moderate. A starter dose at transplanting is enough for most vegetables.",
    },
    "potassium": {
        "low": "Potassium is low. Fruiting vegetables will suffer. Apply muriate of potash or a high-K NPK, and return crop residues.",
        "moderate": "Potassium is moderate. Supplement during fruit set for tomato and pepper.",
    },
    "organic_carbon": {
        "very_low": "Almost no organic matter. The soil will not hold water or nutrients. Add 10 t/ha or more of compost or manure and mulch heavily.",
        "low": "Organic carbon is low. Add 5 to 10 t/ha of well-decomposed manure or compost and keep the surface mulched.",
        "moderate": "Organic carbon is moderate; maintain it with residue return and a yearly manure application.",
    },
    "ec": {
        "moderate": "Salts are starting to build up. Leach with good-quality water before planting, reduce poultry manure, and avoid saline irrigation water.",
        "high": "Salinity is high enough to cut yield by a quarter or more. Leach heavily, improve drainage, and consider a more tolerant crop.",
        "very_high": "Salinity is well above what this crop tolerates. Yield loss would exceed half. Reclaim with leaching and drainage, or do not plant vegetables here.",
    },
    "moisture": {
        "dry": "The soil is dry. Irrigate to field capacity before transplanting and mulch to hold moisture. Check that water will be available through the season.",
        "wet": "The soil is waterlogged. Raise beds (20 to 30 cm) and cut drains before planting. Roots of this crop will rot in standing water.",
    },
    "texture": {
        "sandy": "Very sandy. Water and nutrients drain through quickly. Add organic matter, irrigate little and often, and split fertiliser applications.",
        "sandy_loam": "Sandy loam is slightly light for this crop; organic matter will improve water holding.",
        "clay_loam": "Clay loam is slightly heavy for this crop. Use raised beds and avoid working it wet.",
        "clay": "Heavy clay. Poor aeration and drainage for this crop. Raised beds with plenty of organic matter, or choose a lighter plot.",
    },
}

# Six agro-ecological zones. Presets are representative sketches, not measured values.
ZONES = {
    "sahel": {
        "name": "Sahel",
        "tagline": "Dry, sandy, hot. Irrigated vegetable gardens along rivers and fadamas.",
        "preset": {"ph": 7.2, "nitrogen": 0.5, "phosphorus": 6.0, "potassium": 0.18, "organic_carbon": 0.3, "ec": 2.2, "moisture": 35, "texture": "sandy"},
        "notes": "Very low organic matter and rising salinity under irrigation are the usual limits. Onion does well on the lighter soils with care.",
        "palette": "#D9A441",
    },
    "sudan": {
        "name": "Sudan savanna",
        "tagline": "The onion and tomato belt. Light soils, long dry season, fadama irrigation.",
        "preset": {"ph": 6.4, "nitrogen": 0.8, "phosphorus": 9.0, "potassium": 0.22, "organic_carbon": 0.55, "ec": 1.1, "moisture": 50, "texture": "sandy_loam"},
        "notes": "Soils are workable but hungry. Kano, Kadawa and Sokoto-Rima schemes supply much of the country's dry-season tomato and onion.",
        "palette": "#C98C2D",
    },
    "guinea": {
        "name": "Guinea savanna",
        "tagline": "The middle belt. Deeper soils, two shorter seasons, the Jos Plateau's cool highlands.",
        "preset": {"ph": 5.9, "nitrogen": 1.1, "phosphorus": 11.0, "potassium": 0.24, "organic_carbon": 0.95, "ec": 0.5, "moisture": 60, "texture": "sandy_loam"},
        "notes": "Generally the most forgiving zone for vegetables. Plateau and Kaduna grow cabbage, carrot and tomato for the whole country.",
        "palette": "#8B9A2E",
    },
    "derived": {
        "name": "Derived savanna",
        "tagline": "Forest that became grassland. Loamy, moderately acid, fertile where organic matter is kept up.",
        "preset": {"ph": 5.7, "nitrogen": 1.3, "phosphorus": 12.0, "potassium": 0.26, "organic_carbon": 1.2, "ec": 0.4, "moisture": 65, "texture": "loam"},
        "notes": "Oyo, Ekiti and Kogi growers do well with tomato and pepper if acidity is watched.",
        "palette": "#5E8A3A",
    },
    "forest": {
        "name": "Humid forest",
        "tagline": "Lagos, Ogun, the south-east. Acid sandy loams, high rainfall, year-round leafy vegetables.",
        "preset": {"ph": 5.2, "nitrogen": 1.4, "phosphorus": 8.0, "potassium": 0.19, "organic_carbon": 1.3, "ec": 0.6, "moisture": 75, "texture": "sandy_loam"},
        "notes": "Acidity is the standing problem. Amaranth, okra and pepper thrive; tomato struggles in the wet months.",
        "palette": "#2F6B3A",
    },
    "coastal": {
        "name": "Coastal and mangrove",
        "tagline": "The Niger Delta and the Lagos lagoon fringe. Heavy, wet, sometimes salty.",
        "preset": {"ph": 4.9, "nitrogen": 1.8, "phosphorus": 7.0, "potassium": 0.30, "organic_carbon": 2.2, "ec": 3.0, "moisture": 100, "texture": "clay_loam"},
        "notes": "Waterlogging, acidity and tidal salt limit most vegetables. Raised beds and fresh water are non-negotiable.",
        "palette": "#1F5F66",
    },
}

ZONE_ORDER = ["sahel", "sudan", "guinea", "derived", "forest", "coastal"]

STATES = {
    "Abia": "forest", "Adamawa": "guinea", "Akwa Ibom": "forest", "Anambra": "forest", "Bauchi": "sudan",
    "Bayelsa": "coastal", "Benue": "guinea", "Borno": "sahel", "Cross River": "forest", "Delta": "forest",
    "Ebonyi": "derived", "Edo": "forest", "Ekiti": "derived", "Enugu": "derived", "FCT Abuja": "guinea",
    "Gombe": "sudan", "Imo": "forest", "Jigawa": "sudan", "Kaduna": "guinea", "Kano": "sudan",
    "Katsina": "sudan", "Kebbi": "sudan", "Kogi": "guinea", "Kwara": "guinea", "Lagos": "forest",
    "Nasarawa": "guinea", "Niger": "guinea", "Ogun": "forest", "Ondo": "forest", "Osun": "derived",
    "Oyo": "derived", "Plateau": "guinea", "Rivers": "coastal", "Sokoto": "sudan", "Taraba": "guinea",
    "Yobe": "sahel", "Zamfara": "sudan",
}

OUTPUT = {
    "universe": (0.0, 100.0),
    "terms": {
        "not_suitable": ("trap", (0.0, 0.0, 15.0, 30.0)),
        "marginally_suitable": ("tri", (20.0, 37.0, 55.0)),
        "moderately_suitable": ("tri", (45.0, 62.0, 80.0)),
        "highly_suitable": ("trap", (70.0, 85.0, 100.0, 100.0)),
    },
    "classes": [  # (lower bound inclusive, code, label)
        (75.0, "S1", "Highly suitable"),
        (50.0, "S2", "Moderately suitable"),
        (25.0, "S3", "Marginally suitable"),
        (0.0, "N", "Not suitable"),
    ],
    "term_class": {"not_suitable": "N", "marginally_suitable": "S3", "moderately_suitable": "S2", "highly_suitable": "S1"},
}
