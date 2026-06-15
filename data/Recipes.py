"""
Character unlock graph for DBZ Budokai Tenkaichi 2.

Two unlock kinds:
  FUSION  - combine two ingredients/characters in Evolution Z -> Item Fusion.
            Logic: state.has(A) and state.has(B).
  BATTLE  - "Defeat X with Y" / "Unlock scenario Z" condition.
            Logic: scenario access (the character is a mission reward).
  STARTER - available from the start (no unlock); not a check.

Source: community fusion guide, normalized to the 129-entry CHARACTERS roster
in data.py. Ingredient names are either FUSION_ITEM_ADDR keys or CHARACTERS
names (a fusion may consume an already-unlocked character).

NOTE: the guide had typos / name drift vs the in-game roster. NAME_FIXES maps
guide spellings onto the canonical roster/ingredient names. Anything still
unresolved is reported by validate() so it can be corrected against the game.
"""

from . import Constants as data

# Guide-spelling -> canonical (roster or fusion-item) name.
NAME_FIXES = {
    "Kibitoshin": "Kibitokai",                   # roster spelling
    "Supreme Kai": "Supreme Kai",                # roster has "Superme Kai" (sic) - see ROSTER_TYPOS
    "Fruit of the Gods": "Fruit of the Tree of Might",
    "Lower-Class Saiyan Soldier": "Lower class Saiyan",
    "Reconstructive Surgery": "Remodeling surgery",
    "Suicide Bomb": "Self Destruction",
    "Self Destruct": "Self Destruction",
    "Evil Human Cannonball": "Human gunman's gun",
    "Cell Perfect Form": "Cell Perfect Form",
    "Vegeta (second form)": "Vegeta (second form)",
}

# The roster itself contains a few misspellings; map canonical -> actual flag key.
ROSTER_TYPOS = {
    "Supreme Kai": "Supreme Kai",   # data.py CHARACTERS uses "Supreme Kai"
}

# kind, result_name : requirement
# For FUSION: ("FUSION", [ingredientA, ingredientB])
# For BATTLE: ("BATTLE", scenario_name_or_None)   (None = generic/early)
# For STARTER: ("STARTER", None)
RECIPES = {
    # ---- item fusions (combine A + B) ----
    "Full Power Frieza": ("FUSION", ["Ultimate transformation", "Frieza Final Form"]),
    "Android 13":             ("FUSION", ["Computer", "Hatred"]),
    "Fusion Android 13":      ("FUSION", ["Android 13", "Parts of #14/#15"]),
    "Baby Vegeta":            ("FUSION", ["Baby", "Vegeta (second form)"]),
    "Bojack":                 ("FUSION", ["Unsealed", "Galactic Warrior"]),
    "Broly":                  ("FUSION", ["Son of Paragus", "Hatred of Goku"]),
    "Cooler":                 ("FUSION", ["Frieza's brother", "Hatred of Goku"]),
    "Cooler Final Form":      ("FUSION", ["Ultimate transformation", "Cooler"]),
    "Cui":                    ("FUSION", ["Vegeta's rival", "Frieza's soldier"]),
    "Full Power Bojack":      ("FUSION", ["Ultimate transformation", "Bojack"]),
    "Garlic Jr.":             ("FUSION", ["Makyo Star (fusion)", "Dead Zone"]),
    "General Tao":            ("FUSION", ["Bros. of Crane Hermit", "Memorial campaign"]),
    "Hirudegarn":             ("FUSION", ["Hirudegarn's top half", "Hirudegarn's lower half"]),
    "Janemba":                ("FUSION", ["Saike demon", "People's bad energy"]),
    "Kibitokai":              ("FUSION", ["Kibito", "Supreme Kai"]),
    "Legendary Super Saiyan Broly": ("FUSION", ["Super Saiyan Broly", "breakthrough the limit"]),
    "Slug":                   ("FUSION", ["Namekian", "Mutation"]),
    "Master Roshi":           ("FUSION", ["Master Roshi's pupil", "Fox Mask"]),  # see note
    "MAX Power Master Roshi": ("FUSION", ["Master Roshi", "Seriousness"]),
    "Mecha Frieza":           ("FUSION", ["Remodeling surgery", "Full Power Frieza"]),
    "Meta-Cooler":            ("FUSION", ["Big Gete Star", "Cooler"]),
    "Omega Shenron":          ("FUSION", ["Syn Shenron", "Ultimate Dragonball"]),
    "Salza":                  ("FUSION", ["Cooler's soldier", "Armored cavalry"]),
    "Super 17":               ("FUSION", ["HFIL fighter #17", "Android #17"]),
    "Super Baby 1":           ("FUSION", ["Baby Vegeta", "Lower class Saiyan"]),
    "Super Baby 2":           ("FUSION", ["Super Baby 1", "Power from lower class"]),
    "Super Garlic Jr.":       ("FUSION", ["Garlic Jr.", "Giant Form"]),
    "Super Janemba":          ("FUSION", ["Janemba", "Ultimate transformation"]),
    "Super Saiyan Broly":     ("FUSION", ["Broly", "Super Saiyan"]),
    "Syn Shenron":            ("FUSION", ["Evil Dragon", "Negative Energy"]),
    "Turles":                 ("FUSION", ["Lower class Saiyan", "Fruit of the Tree of Might"]),
    "Zangya":                 ("FUSION", ["The Flowers of Evil", "Galactic Warrior"]),
    "Zarbon Post Transformation": ("FUSION", ["Unsealed", "Zarbon"]),
    "Great Ape Baby":         ("FUSION", ["Super Baby 2", "Artificial Blutz wave"]),
    # Great Apes via Power Ball + base char
    "Great Ape Bardock":      ("FUSION", ["Power Ball", "Bardock"]),
    "Great Ape Nappa":        ("FUSION", ["Power Ball", "Nappa"]),
    "Great Ape Raditz":       ("FUSION", ["Power Ball", "Raditz"]),
    "Great Ape Turles":       ("FUSION", ["Power Ball", "Turles"]),
    "Great Ape Vegeta":       ("FUSION", ["Power Ball", "Vegeta (Scouter)"]),
    "Super Slug":             ("FUSION", ["Slug", "Giant Form"]),  # roster: "Super Slug"? see note

    # ---- battle-condition unlocks (mission rewards) ----
    "Bardock":                ("BATTLE", "Lord Slug"),
    "Burter":                 ("BATTLE", "Frieza Saga"),
    "Cell 1st Form":          ("BATTLE", "Android Saga"),
    "Cell 2nd Form":          ("BATTLE", "Android Saga"),
    "Cell Perfect Form":      ("BATTLE", "Android Saga"),
    "Perfect Cell":           ("FUSION", ["Self Destruction", "Cell Perfect Form"]),
    "Cell Jr.":               ("BATTLE", "Android Saga"),
    "Demon King Dabura":      ("BATTLE", "Majin Buu Saga"),
    "Dr. Gero":               ("BATTLE", "Android Saga"),
    "Ginyu":                  ("BATTLE", "Frieza Saga"),
    "Jeice":                  ("BATTLE", "Frieza Saga"),
    "Guldo":                  ("BATTLE", "Frieza Saga"),
    "Recoome":                ("BATTLE", "Frieza Saga"),
    "Hercule":                ("BATTLE", "Android Saga"),
    "Pikkon":                 ("BATTLE", "Fusion Reborn"),
    "Pan":                    ("BATTLE", "Wrath of the Dragon"),
    "Tapion":                 ("BATTLE", "Wrath of the Dragon"),
    "Kid Buu":                ("BATTLE", "Majin Buu Saga"),
    "Super Buu":              ("BATTLE", "Majin Buu Saga"),
    "Majin Vegeta":           ("BATTLE", "Majin Buu Saga"),
    "Gotenks":                ("BATTLE", "Majin Buu Saga"),
    "Vegito":                 ("BATTLE", "Majin Buu Saga"),
    "Super Vegito":           ("BATTLE", "Majin Buu Saga"),  # beat Super Buu Gohan in "Savior Appears"
    # Super Buu's two absorbed forms — both fuse from regular Super Buu:
    "Super Buu 1":            ("FUSION", ["Absorb Gotenks", "Super Buu"]),  # Gotenks Absorbed
    "Super Buu 2":            ("FUSION", ["Absorb Gohan", "Super Buu"]),    # Gohan Absorbed
    # Trunks (base) is a DEFAULT UNLOCK (available from the start) — no check.
    # (Removed from recipes so Recipes.starters() treats him as a starter.)
    "Uub":                    ("BATTLE", "Wrath of the Dragon"),
    "Majuub":                 ("BATTLE", "Baby, The Avenger"),
    "Super Saiyan 4 Goku":    ("BATTLE", "Baby, The Avenger"),
    "Super Saiyan 4 Vegeta":  ("BATTLE", "Evil Dragon of Absolute Destruction"),
    "Super Saiyan 4 Gogeta":  ("BATTLE", "Evil Dragon of Absolute Destruction"),
    "Kid Goku":               ("BATTLE", None),
    "Yajirobe":               ("BATTLE", "Saiyan Saga"),
    "Supreme Kai":            ("BATTLE", "Majin Buu Saga"),
    "Videl":                  ("BATTLE", "Majin Buu Saga"),
    "Great Saiyaman":         ("BATTLE", "Bojack Unbound"),
    "Great Saiyaman 2":       ("BATTLE", "Broly: The Second Coming"),
    "Super Gogeta":           ("BATTLE", "Fusion Reborn"),

    # Transformations gained by battle (SS ladders) - tie to their saga:
    "Super Saiyan Goku":      ("BATTLE", "Frieza Saga"),
    "Super Saiyan 2 Goku":    ("BATTLE", "Majin Buu Saga"),
    "Super Saiyan 3 Goku":    ("BATTLE", "Majin Buu Saga"),
    "Super Saiyan 2 Teen Gohan": ("BATTLE", "Android Saga"),
    "Super Saiyan Trunks":    ("BATTLE", "Android Saga"),
    "Super Saiyan Trunks (Sword)": ("BATTLE", "Android Saga"),
    "Super Trunks":           ("BATTLE", "Android Saga"),
    "Super Vegeta":           ("BATTLE", "Android Saga"),
    "Super Saiyan 2 Vegeta":  ("BATTLE", "Majin Buu Saga"),
    "Super Gotenks":          ("BATTLE", "Majin Buu Saga"),
    "Super Gotenks 3":        ("BATTLE", "Majin Buu Saga"),
    "Ultimate Gohan":         ("BATTLE", "Majin Buu Saga"),
    "Super Saiyan Goten":     ("BATTLE", "Bojack Unbound"),
    "Super Saiyan Kid Trunks":("BATTLE", "Bojack Unbound"),
}

# Everything in the roster NOT in RECIPES is treated as a STARTER (base form,
# available from the start). Computed in starters().


def _canon(name: str) -> str:
    return NAME_FIXES.get(name, name)


def starters() -> list[str]:
    """Roster characters with no unlock recipe = starters."""
    return [c for c in data.CHARACTERS if c not in RECIPES]


def ingredient_demand() -> dict:
    """Fusion ITEMS are CONSUMED when fused (roster characters used as
    ingredients are NOT consumed — having them unlocked is enough). To unlock
    every fusion character once, each fusion-item ingredient must be supplied as
    many times as it is consumed across all recipes — including transitively,
    when a fusion result is itself an ingredient of another fusion (it must be
    re-produced, consuming its fusion items again).

    Returns {fusion_item_name: copies_needed}, counting ONLY fusion-item
    ingredients. Roster-character ingredients are skipped (not consumed)."""
    roster = set(data.CHARACTERS)
    fusion_items = set(data.FUSION_ITEM_ADDR.keys())
    demand: dict = {}

    def add(result):
        entry = RECIPES.get(result)
        if not entry or entry[0] != "FUSION":
            return
        for ing in entry[1]:
            canon = _canon(ing)
            if canon in roster and canon in RECIPES and RECIPES[canon][0] == "FUSION":
                # ingredient is itself a FUSION character -> must be re-fused,
                # which re-consumes ITS fusion items (recurse).
                add(canon)
            elif canon in fusion_items:
                # consumable fusion item -> count a copy
                demand[canon] = demand.get(canon, 0) + 1
            else:
                # roster-character ingredient (starter or battle-unlock): NOT
                # consumed, so it needs no extra copies. Skip.
                pass

    for result, (kind, _ings) in RECIPES.items():
        if kind == "FUSION":
            add(result)
    return demand


def validate() -> dict:
    """Check that every recipe result is in the roster and every ingredient
    resolves to either a fusion item or a roster character. Returns a report."""
    roster = set(data.CHARACTERS)
    fusion_items = set(data.FUSION_ITEM_ADDR.keys())
    known = roster | fusion_items

    unknown_results = []
    unknown_ingredients = []
    bad_scenarios = []
    scenarios = {s for s, _ in data.SCENARIOS}

    for result, (kind, req) in RECIPES.items():
        if result not in roster:
            unknown_results.append(result)
        if kind == "FUSION":
            for ing in req:
                if _canon(ing) not in known:
                    unknown_ingredients.append((result, ing))
        elif kind == "BATTLE":
            if req is not None and req not in scenarios:
                bad_scenarios.append((result, req))

    return {
        "total_recipes": len(RECIPES),
        "fusion": sum(1 for k, _ in RECIPES.values() if k == "FUSION"),
        "battle": sum(1 for k, _ in RECIPES.values() if k == "BATTLE"),
        "starters": len(starters()),
        "unknown_results": unknown_results,
        "unknown_ingredients": unknown_ingredients,
        "bad_scenarios": bad_scenarios,
    }
