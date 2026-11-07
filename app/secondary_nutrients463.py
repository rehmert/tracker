"""Release 463: shared nutrient units and secondary-user keys.

All nutrients are amounts per serving in private product JSON.
Unknown values remain None. The first five fields retain their
existing meanings and storage formats.
"""

MACROS = (
    ("energy", "Calories", "kcal"),
    ("proteins", "Protein", "g"),
    ("carbohydrates", "Carbohydrates", "g"),
    ("fat", "Fat", "g"),
    ("fiber", "Fiber", "g"),
)

MICROS = (
    ("sugars", "Sugar", "g"),
    ("saturated-fat", "Saturated Fat", "g"),
    ("sodium", "Sodium", "mg"),
    ("potassium", "Potassium", "mg"),
    ("calcium", "Calcium", "mg"),
    ("iron", "Iron", "mg"),
    ("magnesium", "Magnesium", "mg"),
    ("vitamin-c", "Vitamin C", "mg"),
    ("vitamin-d", "Vitamin D", "mcg"),
    ("vitamin-b12", "Vitamin B12", "mcg"),
    ("cholesterol", "Cholesterol", "mg"),
)

ALL = MACROS + MICROS
NUTRIENTS = tuple(item[0] for item in ALL)

REMOTE_KEYS = {
    "energy": "energy-kcal",
    **{key: key for key in NUTRIENTS if key != "energy"},
}

# Open Food Facts commonly reports these as grams.
OFF_MG = frozenset({
    "sodium", "potassium", "calcium", "iron",
    "magnesium", "vitamin-c", "cholesterol",
})
OFF_MCG = frozenset({"vitamin-d", "vitamin-b12"})

assert len(NUTRIENTS) == 16
assert len(set(NUTRIENTS)) == len(NUTRIENTS)
